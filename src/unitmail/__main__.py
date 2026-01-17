#!/usr/bin/env python3
"""
Allow running unitmail as a module: python -m unitmail

This enables the following usage:
    python -m unitmail [OPTIONS]

Which is equivalent to:
    unitmail [OPTIONS]
"""

from unitmail.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
