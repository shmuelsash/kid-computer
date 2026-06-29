"""Test setup: force pygame into headless mode so tests run in CI with no
display or audio device.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
