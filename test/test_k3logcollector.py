import os
import re
import time
import unittest

import k3cat
import k3log
import k3thread
import k3time
import k3ut

import k3logcollector
from k3logcollector import collector

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
