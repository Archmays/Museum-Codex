#!/usr/bin/env python3
"""Run the Python suite with process-level network primitives disabled."""

from __future__ import annotations

import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def _blocked(*_args, **_kwargs):
    raise AssertionError("Python tests attempted real network access")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    suite = unittest.defaultTestLoader.discover("tests")
    with (
        patch.object(socket, "create_connection", _blocked),
        patch.object(socket, "getaddrinfo", _blocked),
        patch.object(socket.socket, "connect", _blocked),
        patch.object(socket.socket, "connect_ex", _blocked),
    ):
        result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
