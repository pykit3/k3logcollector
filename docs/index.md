# k3logcollector

[![Action-CI](https://github.com/pykit3/k3logcollector/actions/workflows/python-package.yml/badge.svg)](https://github.com/pykit3/k3logcollector/actions/workflows/python-package.yml)
[![Documentation Status](https://readthedocs.org/projects/k3logcollector/badge/?version=stable)](https://k3logcollector.readthedocs.io/en/stable/?badge=stable)
[![Package](https://img.shields.io/pypi/pyversions/k3logcollector)](https://pypi.org/project/k3logcollector)

Log collector for scanning and aggregating log files. Scans log files on local machine, collects interested logs, and sends them somewhere for display.

k3logcollector is a component of [pykit3](https://github.com/pykit3) project: a python3 toolkit set.

## Installation

```bash
pip install k3logcollector
```

## Quick Start

```python
from k3logcollector import collector

def send_log(log_entry):
    print(log_entry)

# Configure log files to scan
conf = {
    'my_log': {
        'file_path': '/var/log/myapp.log',
        'is_first_line': lambda line: line.startswith('['),
        'get_level': lambda log: 'error' if 'ERROR' in log else 'info',
        'parse': lambda log: {
            'log_ts': 1234567890,
            'level': 'error',
            'source_file': 'app.py',
            'line_number': 42,
        },
        'level': ['error', 'warning'],
    }
}

# Run the collector
collector.run(node_ip='192.168.1.1', send_log=send_log, conf=conf)
```

## API Reference

::: k3logcollector

## License

The MIT License (MIT) - Copyright (c) 2015 Zhang Yanpo (张炎泼)
