"""Shared import-by-path helper for the tests in this directory.

The scripts under test live outside any package (``design/``, ``sim/``,
``layout/``), so each test loads them by file path.  The module is registered
in ``sys.modules`` before it executes, which dataclasses and ``pickle`` inside
the loaded script require.
"""

import importlib.util
import sys
from pathlib import Path


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
