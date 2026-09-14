"""Compatibility alias for 1688 seller category capture."""

from importlib import import_module
import sys


_implementation = import_module(".platforms.alibaba1688.category_capture", __package__)

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
