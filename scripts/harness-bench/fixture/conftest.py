"""Rend le paquet taskmgr importable depuis les tests sans installation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
