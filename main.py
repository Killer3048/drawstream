#!/usr/bin/env python3
"""Convenience runner so `python main.py` starts the stream app."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from draw_stream.main import main as run_app  # noqa: E402


if __name__ == "__main__":
    asyncio.run(run_app())
