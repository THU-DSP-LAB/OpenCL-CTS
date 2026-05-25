#!/usr/bin/env python3
"""Compatibility entry for the Ventus OpenCL-CTS parallel runner."""

from cts_runner.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
