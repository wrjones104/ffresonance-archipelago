"""Makes the scratch Archipelago copy the client tests run in.

    python tests/make_aptest.py [path to your Archipelago checkout]

The client tests import Archipelago's CommonClient and need the world under worlds/. They copy
the world into this scratch copy, so your own checkout is never changed. The copy leaves out
.git, venvs and caches. It goes to FFRAP_APTEST, or %LOCALAPPDATA%/ffrap-aptest.
"""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import APTEST  # noqa: E402

source = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(r"C:\Projects\archipelago")
if not (source / "CommonClient.py").exists():
    sys.exit(f"{source} does not look like an Archipelago checkout (no CommonClient.py)")
if APTEST.exists():
    shutil.rmtree(APTEST)
shutil.copytree(source, APTEST, ignore=shutil.ignore_patterns(
    ".git", "venv", ".venv", "__pycache__", "build", "dist", "*.pyc", "Players", "output", "logs"))
print(f"{source} -> {APTEST}")
