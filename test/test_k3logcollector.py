import os
import re
import time
import unittest
from types import SimpleNamespace
from unittest import mock

import k3cat
import k3log
import k3thread
import k3time
import k3ut

import k3logcollector
from k3logcollector import cache_flusher, collector, scanner

dd = k3ut.dd

this_base = os.path.dirname(__file__)

standard_level = {
    "ERROR": "error",
    "WARNING": "warning",
    "INFO": "info",
}


def is_first_line(line):
    return True


def parse(log_str):
    r = re.match(r"^\[(.+?),(.+?),(.+?),(.+?),(\d+?),(\w+?)]", log_str)

    time_str = r.group(1)

    log_dt = k3time.parse(time_str, "mysql")
    log_ts = int(time.mktime(log_dt.timetuple()))

    source_file = r.group(4)
    line_number = int(r.group(5))
    level = standard_level[r.group(6)]

    log_info = {
        "log_ts": log_ts,
        "level": level,
        "source_file": source_file,
        "line_number": line_number,
    }

    return log_info


class TestLogcollector(unittest.TestCase):
    def _clean(self):
        for log_name in ("test_log", "test_log_no_merge"):
            log_path = os.path.join(this_base, log_name + ".out")
            # k3cat saves the read offset of each file under /tmp and trusts it
            # while the inode matches, so a record from an earlier run can make
            # the scanner skip new lines.
            offset_path = k3cat.Cat(log_path).stat_path()
            for p in (log_path, offset_path):
                try:
                    os.unlink(p)
                except OSError as e:
                    dd(repr(e))

    def setUp(self):
        self._clean()

    def tearDown(self):
        self._clean()

    def log(self, log_name="test_log"):
        logger = k3log.make_logger(base_dir=this_base, log_name=log_name)

        cnt = 1
        while True:
            logger.info("info")
            logger.warning("warn")
            logger.error("error")
            time.sleep(0.001)
            cnt += 1
            if cnt > 100:
                break

    def get_level(self, log_str):
        for k in standard_level:
            if k in log_str:
                return k.lower()
        return "unknown"

    def test_run_is_exported(self):
        self.assertIs(collector.run, k3logcollector.run)

    def test_basic(self):
        log_entries = []

        def send_log(log_entry):
            log_entries.append(log_entry)

        kwargs = {
            "node_id": "123abc",
            "node_ip": "1.2.3.4",
            "send_log": send_log,
            "conf": {
                "my_test_log": {
                    "file_path": os.path.join(this_base, "test_log.out"),
                    "level": ["error"],
                    "get_level": self.get_level,
                    "is_first_line": is_first_line,
                    "parse": parse,
                },
            },
        }

        k3thread.daemon(self.log)
        k3thread.daemon(collector.run, kwargs=kwargs)
        time.sleep(8)

        dd(log_entries)
        log_cnt = 0
        for le in log_entries:
            log_cnt += le["count"]
        dd(log_cnt)

        self.assertEqual(100, log_cnt)
        self.assertEqual("error", log_entries[0]["level"])
        self.assertEqual("my_test_log", log_entries[0]["log_name"])
        self.assertEqual("test_log.out", log_entries[0]["log_file"])

    def test_no_merge(self):
        log_entries = []

        def send_log(log_entry):
            log_entries.append(log_entry)

        kwargs = {
            "node_id": "123abc",
            "node_ip": "1.2.3.4",
            "send_log": send_log,
            "conf": {
                "my_test_log": {
                    "file_path": os.path.join(this_base, "test_log_no_merge.out"),
                    "level": ["error"],
                    "get_level": self.get_level,
                    "is_first_line": is_first_line,
                    "parse": parse,
                    "merge": False,
                },
            },
        }

        # Use a log file of its own, because the collector threads of test_basic
        # never stop and would take the lines of a shared file.
        k3thread.daemon(self.log, args=("test_log_no_merge",))
        k3thread.daemon(collector.run, kwargs=kwargs)
        time.sleep(8)

        self.assertEqual(100, len(log_entries))
        self.assertEqual("error", log_entries[0]["level"])


class TestCache(unittest.TestCase):
    def test_put_into_cache_counts_repeated_lines(self):
        # Lines from the same source line in the same second merge into the
        # latest entry, which counts them.
        cache = {}
        first = {"log_ts": 10, "source_file": "a.py", "line_number": 3, "count": 1, "content": "1"}
        second = {"log_ts": 10, "source_file": "a.py", "line_number": 3, "count": 1, "content": "2"}
        other = {"log_ts": 10, "source_file": "a.py", "line_number": 4, "count": 1, "content": "3"}
        for entry in (first, second, other):
            scanner.put_into_cache(cache, entry)

        want = {
            10: {
                "a.py": {
                    3: {"log_ts": 10, "source_file": "a.py", "line_number": 3, "count": 2, "content": "2"},
                    4: {"log_ts": 10, "source_file": "a.py", "line_number": 4, "count": 1, "content": "3"},
                }
            }
        }
        self.assertEqual(want, cache)

    def test_flush_cache_in_ts_order(self):
        cache = {ts: {"a.py": {1: f"a{ts}"}, "b.py": {2: f"b{ts}"}} for ts in (104, 100, 102, 101, 103)}
        queued = []
        with mock.patch("time.time", return_value=200):
            cache_flusher.flush_cache(cache, SimpleNamespace(put=queued.append), merge=True)

        want = ["a100", "b100", "a101", "b101", "a102", "b102", "a103", "b103", "a104", "b104"]
        self.assertEqual(want, queued)
        self.assertEqual({}, cache)

    def test_flush_cache_two_second_boundary(self):
        # The latest bucket stays in the cache while it is less than 2 seconds
        # old, because more lines of that second may still come.
        cases = (
            (101.9, ["e99"], {100: {"a.py": {1: "e100"}}}),
            (102, ["e99", "e100"], {}),
        )
        for now, want_queued, want_cache in cases:
            cache = {99: {"a.py": {1: "e99"}}, 100: {"a.py": {1: "e100"}}}
            queued = []
            with mock.patch("time.time", return_value=now):
                cache_flusher.flush_cache(cache, SimpleNamespace(put=queued.append), merge=True)

            self.assertEqual(want_queued, queued, now)
            self.assertEqual(want_cache, cache, now)

    def test_flush_cache_no_merge(self):
        # Without merge, the cache maps a source file to its entries, and a
        # flush sends all of them.
        cache = {"a.py": ["a1", "a2"], "b.py": ["b1"]}
        queued = []
        cache_flusher.flush_cache(cache, SimpleNamespace(put=queued.append), merge=False)

        self.assertEqual(["a1", "a2", "b1"], queued)
        self.assertEqual({}, cache)
