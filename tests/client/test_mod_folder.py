"""Checks that the client finds the FFRArchipelago folder from the Mods folder and from Steam's library list."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

AP = str(paths.APTEST)
paths.install_world()
sys.path.insert(0, AP)
os.chdir(AP)

from worlds.ff_resonance.client import MOD_IN_LIBRARY, library_mod_folders, resolve_mod_folder  # noqa: E402

failures = 0


def check(name, cond):
    global failures
    print(("ok  " if cond else "FAIL") + " " + name)
    failures += 0 if cond else 1


def install_mod(folder: str) -> None:
    os.makedirs(os.path.join(folder, "Scripts"))
    Path(folder, "Scripts", "main.lua").write_text("", encoding="utf-8")


root = tempfile.mkdtemp()

mods = os.path.join(root, "game", "ue4ss", "Mods")
mod = os.path.join(mods, "FFRArchipelago")
install_mod(mod)
check("Mods folder resolves to FFRArchipelago", resolve_mod_folder(mods) == mod)
check("FFRArchipelago folder stays as given", resolve_mod_folder(mod) == mod)
empty = os.path.join(root, "empty")
os.makedirs(empty)
check("folder without the mod stays as given", resolve_mod_folder(empty) == empty)

steam = os.path.join(root, "Steam")
second_library = os.path.join(root, "SteamLibrary")
os.makedirs(steam)
install_mod(os.path.join(second_library, MOD_IN_LIBRARY))
escaped = second_library.replace("\\", "\\\\")
vdf = ('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"' + steam.replace("\\", "\\\\") + '"\n\t}\n'
       '\t"1"\n\t{\n\t\t"path"\t\t"' + escaped + '"\n\t}\n}\n')
found = library_mod_folders(steam, vdf)
expected = os.path.join(os.path.normcase(second_library), MOD_IN_LIBRARY)
check("mod found in second Steam library", found == [expected])

install_mod(os.path.join(steam, MOD_IN_LIBRARY))
found = library_mod_folders(steam.replace("\\", "/").lower(), vdf)
check("Steam's own folder listed once", len(found) == 2)

sys.exit(1 if failures else 0)
