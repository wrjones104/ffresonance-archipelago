"""tools/package_release.py: the release's three files, and the builds they carry.

    python tests/tools/test_package_release.py
"""

import json
from pathlib import Path
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

sys.path.insert(0, str(paths.REPO / "tools"))
import package_release  # noqa: E402

SHIPPED_MOD_FILES = {"FFRArchipelago/enabled.txt", "FFRArchipelago/Assets/archipelago_logo.png",
                     *(f"FFRArchipelago/Scripts/{name}" for name in package_release.MOD_SCRIPTS)}

out = Path(tempfile.mkdtemp(prefix="ffrap_release_"))
release = package_release.package(out)
assert {p.name for p in out.iterdir()} == {"FFRArchipelago.zip", "ff_resonance.apworld", "Final Fantasy Resonance.yaml"}

with zipfile.ZipFile(out / "FFRArchipelago.zip") as z:
    names = set(z.namelist())
    assert names == SHIPPED_MOD_FILES, names ^ SHIPPED_MOD_FILES
    unpacked = Path(tempfile.mkdtemp(prefix="ffrap_unpacked_"))
    z.extractall(unpacked)
assert package_release.mod_build(unpacked / "FFRArchipelago") == release["mod_build"], "the zip carries the build named"

with zipfile.ZipFile(out / "ff_resonance.apworld") as z:
    manifest = json.loads(z.read("ff_resonance/archipelago.json"))
assert manifest["build"] == release["world_build"] and manifest["world_version"] == release["world"]
assert release["mod"] == package_release.mod_version()
print("package release:", release, "ok")
