"""Round 83: the mod starts ap_out.txt over for a new seed, and the client must see it even when
the new file is already longer than what it read of the old one (2026-11-18: a chest check was
never sent until the client was restarted)."""

import asyncio
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

from worlds.ff_resonance.client import FFResonanceContext  # noqa: E402
from worlds.ff_resonance.locations import LOCATION_KEY_TO_ID  # noqa: E402

OLD_SEED = "92996176478067067407:0:1"
NEW_SEED = "41007366389886491127:0:1"
FIRST_CHEST, SECOND_CHEST = "chest:2020:0", "chest:2020:1"

# What the mod wrote in the 2026-11-18 log: an Archipelago new game linked to the old seed, then
# the client's new seed, with item 0 applied in the same tick.
OLD_FILE = f"hello\t0.62.0\t2\nseed\t{OLD_SEED}\nstory\t1000\nstory\t1005\n"
NEW_FILE = f"hello\t0.62.0\t2\nseed\t{NEW_SEED}\napplied\t0\tok\tflag 1421 = true\n"

failures = 0


def check(name, ok):
    global failures
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failures += 1


def write(path, text, mode="w"):
    with open(path, mode, encoding="utf-8", newline="\n") as f:
        f.write(text)


async def main():
    folder = tempfile.mkdtemp()
    out_path = os.path.join(folder, "ap_out.txt")
    ctx = FFResonanceContext(None, None, folder)
    ctx.session_key, ctx.slot, ctx.team = NEW_SEED, 1, 0
    check("the test's chest keys are locations", FIRST_CHEST in LOCATION_KEY_TO_ID and SECOND_CHEST in LOCATION_KEY_TO_ID)
    check("the new file is not shorter than the old one, as in the log", len(NEW_FILE) >= len(OLD_FILE))

    write(out_path, OLD_FILE)
    ctx.start_session()
    checks, _ = ctx.read_new_output()
    check("the old seed's file gives nothing", not checks)

    write(out_path, NEW_FILE)
    write(out_path, f"story\t8000\ncheck\t{FIRST_CHEST}\n", "a")
    checks, story = ctx.read_new_output()
    check("the check after the mod's new seed line is sent", checks == {LOCATION_KEY_TO_ID[FIRST_CHEST]})
    check("the story after it counts", story == 8000)

    write(out_path, f"hello\t0.62.0\t2\nseed\t{NEW_SEED}\ncheck\t{SECOND_CHEST}\n", "a")
    checks, _ = ctx.read_new_output()
    check("a game restart appends: only the new check, not the old ones again",
          checks == {LOCATION_KEY_TO_ID[SECOND_CHEST]})
    ctx.keep_alive_task.cancel()


asyncio.run(main())
print("failures:", failures)
sys.exit(1 if failures else 0)
