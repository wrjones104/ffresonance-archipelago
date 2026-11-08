"""Where the tests find things. Override with environment variables when your layout differs.

- FFRAP_APTEST: a scratch copy of an Archipelago checkout for the client tests
  (make it with `python tests/make_aptest.py`). Default: %LOCALAPPDATA%/ffrap-aptest.
- FFRAP_AP_PYTHON: a Python with Archipelago's requirements installed, used to run the client
  tests. Default: the venv of C:/Projects/archipelago.
"""

import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "FFRArchipelago"
SCRIPTS = MOD / "Scripts"
WORLD = REPO / "apworld" / "ff_resonance"
TOOLS = REPO / "tools"
DIST_APWORLD = REPO / "dist" / "ff_resonance.apworld"

APTEST = Path(os.environ.get("FFRAP_APTEST") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "ffrap-aptest")
AP_PYTHON = Path(os.environ.get("FFRAP_AP_PYTHON") or r"C:\Projects\archipelago\venv\Scripts\python.exe")


def install_world() -> Path:
    """Copies the repo's world into the scratch Archipelago copy (never into your own checkout)."""
    dst = APTEST / "worlds" / "ff_resonance"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WORLD, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def world_version() -> str:
    return json.loads((WORLD / "archipelago.json").read_text(encoding="utf-8"))["world_version"]
