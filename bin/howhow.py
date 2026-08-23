#!/usr/bin/env python3
"""Portable source-tree entrypoint: python bin/howhow.py ..."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from howhow.__main__ import main
raise SystemExit(main())
