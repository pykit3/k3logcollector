from importlib.metadata import version

__version__ = version("k3logcollector")

from .collector import run

__all__ = ["run"]
