"""Builds a release's three files into dist/release/v<world version>/.

    python tools/package_release.py

- FFRArchipelago.zip: the mod folder (enabled.txt, Scripts, Assets), to extract into ue4ss\\Mods.
- ff_resonance.apworld: built by tools/build_apworld.py.
- Final Fantasy Resonance.yaml: the template player yaml.

It stops when the shipped files (FFRArchipelago/ and apworld/) have changes that are not committed,
so every release is a commit. It prints the versions, the builds and the release's title.
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

import build_apworld

ROOT = build_apworld.ROOT
MOD = ROOT / "FFRArchipelago"
TEMPLATE = ROOT / "apworld" / "Final Fantasy Resonance.yaml"
NOTES = ROOT / "docs" / "releases"
MOD_SCRIPTS = ("main.lua", "game.lua", "bridge.lua", "field_items.lua", "quests.lua")   # B.SCRIPTS in bridge.lua


def mod_build(folder: Path) -> str:
    """The mod's build as bridge.build makes it: FNV-1a over its scripts, carriage returns left out."""
    h = 2166136261
    for name in MOD_SCRIPTS:
        for byte in (folder / "Scripts" / name).read_bytes().replace(b"\r", b""):
            h = ((h ^ byte) * 16777619) & 0xFFFFFFFF
    return f"{h:08x}"


def mod_version() -> str:
    return re.search(r'local VERSION = "([^"]+)"', (MOD / "Scripts" / "main.lua").read_text(encoding="utf-8")).group(1)


def world_version() -> str:
    return json.loads((build_apworld.SRC / "archipelago.json").read_text(encoding="utf-8"))["world_version"]


def uncommitted() -> list[str]:
    status = subprocess.run(["git", "status", "--porcelain", "--", "FFRArchipelago", "apworld"],
                            capture_output=True, text=True, check=True, cwd=ROOT)
    return status.stdout.splitlines()


def package(out: Path) -> dict[str, str]:
    """Writes the three files into `out` and returns the versions and builds they carry."""
    out.mkdir(parents=True, exist_ok=True)
    mod_files = [MOD / "enabled.txt", *sorted((MOD / "Scripts").glob("*.lua")), *sorted((MOD / "Assets").iterdir())]
    with zipfile.ZipFile(out / "FFRArchipelago.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for file in mod_files:
            z.write(file, Path("FFRArchipelago") / file.relative_to(MOD))
    build_apworld.main()
    shutil.copy2(build_apworld.OUT, out / build_apworld.OUT.name)
    shutil.copy2(TEMPLATE, out / TEMPLATE.name)
    with zipfile.ZipFile(out / build_apworld.OUT.name) as z:
        world_build = json.loads(z.read("ff_resonance/archipelago.json"))["build"]
    return {"world": world_version(), "world_build": world_build, "mod": mod_version(), "mod_build": mod_build(MOD)}


def main() -> int:
    changed = uncommitted()
    if changed:
        print("Commit these first, so the release is a commit:\n  " + "\n  ".join(changed))
        return 1
    world = world_version()
    out = build_apworld.DIST / "release" / f"v{world}"
    if out.exists():
        shutil.rmtree(out)
    release = package(out)
    print(f"Release v{release['world']} (apworld {release['world']}, mod {release['mod']}) -> {out}")
    print(f"  apworld build {release['world_build']}, mod build {release['mod_build']}")
    if not (NOTES / f"v{world}.md").exists():
        print(f"  no release notes yet: docs/releases/v{world}.md")
    # The template comes from the Launcher's "Generate Template Options", which writes the world's
    # version into its requires block; an older one means it was not made again for this release.
    if f"Final Fantasy Resonance: {world} " not in TEMPLATE.read_text(encoding="utf-8-sig"):
        print(f"  the template yaml does not require world {world}: generate it again from the Launcher")
    return 0


if __name__ == "__main__":
    sys.exit(main())
