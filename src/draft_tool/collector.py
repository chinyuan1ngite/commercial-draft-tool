"""Compatibility alias for the 1688 collector implementation."""

from importlib import import_module
import sys


_implementation = import_module(".platforms.alibaba1688.collector", __package__)

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
