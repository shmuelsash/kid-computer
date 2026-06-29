"""Allow ``python -m kidcomputer``."""

import sys

from kidcomputer.app import main

if __name__ == "__main__":
    sys.exit(main())
