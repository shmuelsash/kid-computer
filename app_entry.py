"""PyInstaller entry script.

A flat top-level module is the simplest, most reliable thing to point
PyInstaller at. It just calls the real entry point.
"""

import sys

from kidcomputer.app import main

if __name__ == "__main__":
    sys.exit(main())
