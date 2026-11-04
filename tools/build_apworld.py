"""Builds dist/ff_resonance.apworld from apworld/ff_resonance.

    python tools/build_apworld.py

An .apworld is a zip whose top folder is the world package. Drop it into Archipelago's
custom_worlds folder. The packaged archipelago.json is the source one plus the container fields
Archipelago's own "Build APWorlds" component adds (worlds/Files.py, APWorldContainer).
"""

import json
import os
import zipfile

CONTAINER_FIELDS = {"compatible_version": 7, "version": 7}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "apworld", "ff_resonance")
DIST = os.path.join(ROOT, "dist")
OUT = os.path.join(DIST, "ff_resonance.apworld")


def main() -> None:
    os.makedirs(DIST, exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, dirs, files in os.walk(SRC):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(files):
                if name.endswith((".pyc", ".pyo")) or (folder == SRC and name == "archipelago.json"):
                    continue
                full = os.path.join(folder, name)
                z.write(full, os.path.join("ff_resonance", os.path.relpath(full, SRC)))
                count += 1
        with open(os.path.join(SRC, "archipelago.json"), encoding="utf-8") as f:
            manifest = json.load(f)
        manifest.update(CONTAINER_FIELDS)
        z.writestr("ff_resonance/archipelago.json", json.dumps(manifest))
        count += 1
    print(f"{count} files -> {OUT}")


if __name__ == "__main__":
    main()
