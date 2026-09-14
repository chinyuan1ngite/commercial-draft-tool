"""Compatibility alias for 1688 browser navigation recovery."""

from importlib import import_module
import sys


_implementation = import_module(".platforms.alibaba1688.browser_navigation", __package__)
sys.modules[__name__] = _implementation
