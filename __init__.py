"""
#   Name

logcollector

Scan log files on local machine, collector all interested logs, and send
to somewhere for display.

#   Description

We may want to see all error logs on all machines, so we need to collector
logs, and save it in somewhere. This module is used to collector logs on one
machine.

Normally, same error info will be loged repeatedly, we do not want
to save duplicated log info, so logs produced by same source file at
same line number in one second will be combined.

#   Conf

configuration for log files. It is a dict, the key is the log name, the value
is the configuration for the log.

## file_path

the path of the log file.

## is_first_line

is a callback function.
The argument to this function is a line in log file, if the line is the
first line of a log, then return `True`, otherwise return `False`.

## get_level

is a callback function.
The argument to this function is the complete log string, which may contains
multiple lines. It should return the level of the log, which is a string.

## parse

is a callback function.
The argument to this function is the complete log string, which may contains
multiple lines. It should return a dict contains following fields.

-   log_ts:
    the timestamp of this log, such as `1523936052`, is a integer.

-   level:
    the level of this log, such as 'info'.

-   source_file:
    the source file in which the log was produced.

-   line_number:
    the number of the line at which the log was produced.

## level

is a list, used to specify the interested log levels.

"""

from .collector import run

__all__ = ["run"]


def __getattr__(name: str) -> str:
    # importlib.metadata takes about 20 ms to import, so it is loaded only
    # when __version__ is read
    if name != "__version__":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    from importlib.metadata import version

    return version("k3logcollector")
