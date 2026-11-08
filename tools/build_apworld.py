"""Builds dist/ff_resonance.apworld from apworld/ff_resonance.

    python tools/build_apworld.py

An .apworld is a zip whose top folder is the world package. Drop it into Archipelago's
custom_worlds folder. The packaged archipelago.json is the source one plus the container fields
Archipelago's own "Build APWorlds" component adds (worlds/Files.py, APWorldContainer).
"""

import json
from pathlib import Path
import zipfile

CONTAINER_FIELDS = {"compatible_version": 7, "version": 7}

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "apworld" / "ff_resonance"
DIST = ROOT / "dist"
OUT = DIST / "ff_resonance.apworld"


def main() -> None:
    DIST.mkdir(exist_ok=True)
    count = 0
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        for file in sorted(SRC.rglob("*")):
            if file.is_dir() or file.suffix in (".pyc", ".pyo") or "__pycache__" in file.parts or file == SRC / "archipelago.json":
                continue
            z.write(file, Path("ff_resonance") / file.relative_to(SRC))
            count += 1

        manifest = json.loads((SRC / "archipelago.json").read_text(encoding="utf-8"))
        manifest.update(CONTAINER_FIELDS)
        z.writestr("ff_resonance/archipelago.json", json.dumps(manifest))
        count += 1

    print(f"{count} files -> {OUT}")


if __name__ == "__main__":
    main()
