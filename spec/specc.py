#!/usr/bin/env python3
"""Entry point of the spec compiler; the code lives in specclib/."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from specclib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
