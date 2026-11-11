"""The client's world_version(), from the world folder and from the built .apworld in
custom_worlds, inside a scratch Archipelago copy. Also: start_session writes a `client` line."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

HERE = Path(__file__).resolve().parent
AP = str(paths.APTEST)
REPO = str(paths.REPO)
PY = str(paths.AP_PYTHON)
VERSION = paths.world_version()
subprocess.run([PY, str(paths.TOOLS / "build_apworld.py")], check=True, capture_output=True)

# 1. the folder copy, refreshed from the repo
dst = str(paths.install_world())
code = r'''
import os, sys, tempfile
sys.path.insert(0, os.getcwd())
from worlds.ff_resonance.client import world_version, FFResonanceContext
print("VERSION", world_version())
import asyncio
async def main():
    folder = tempfile.mkdtemp()
    ctx = FFResonanceContext(None, None, folder)
    ctx.session_key = "S:0:1"
    ctx.start_session()
    print("INBOX", open(os.path.join(folder, "ap_in.txt")).read().replace("\t", "|").replace("\n", "/"))
    ctx.start_session()   # a reconnect: the same file, one more client line
    print("INBOX2", open(os.path.join(folder, "ap_in.txt")).read().replace("\t", "|").replace("\n", "/"))
    # The seed's start settings: written once, however often the client reconnects.
    slot = {"open_world": True, "starting_party": [1007, 1006], "include_tablet_shards": True, "minimap_chest_icons": 2}
    ctx.write_config(slot)
    ctx.write_config(slot)
    text = open(os.path.join(folder, "ap_in.txt")).read()
    print("CONFIG", text.count("cfg\topenworld\t1\n"), text.count("cfg\tparty\t1007,1006\n"), text.count("cfg\tshards\t1\n"), text.count("cfg\tchesticons\t2\n"))
    if ctx.keep_alive_task: ctx.keep_alive_task.cancel()
asyncio.run(main())
'''
out = subprocess.run([PY, "-c", code], cwd=AP, capture_output=True, text=True)
assert "CONFIG 1 1 1 1" in out.stdout, out.stdout + out.stderr
print(out.stdout[-600:], out.stderr[-1500:] if out.returncode else "")
assert f"VERSION {VERSION}" in out.stdout
assert f"INBOX seed|S:0:1/cfg|blank|1/client|{VERSION}/" in out.stdout
assert f"INBOX2 seed|S:0:1/cfg|blank|1/client|{VERSION}/client|{VERSION}/" in out.stdout

# 2. the built .apworld, loaded from custom_worlds with the folder copy moved away
hold = os.path.join(tempfile.gettempdir(), "ffrap_world_hold")
if os.path.exists(hold):
    shutil.rmtree(hold)
shutil.move(dst, hold)
cw = os.path.join(AP, "custom_worlds")
os.makedirs(cw, exist_ok=True)
shutil.copy(os.path.join(REPO, "dist", "ff_resonance.apworld"), cw)
try:
    code2 = r'''
import os, sys
sys.path.insert(0, os.getcwd())
import worlds  # loads custom_worlds
from worlds.ff_resonance import client
print("FILE", client.__file__)
print("VERSION", client.world_version())
'''
    out = subprocess.run([PY, "-c", code2], cwd=AP, capture_output=True, text=True)
    print(out.stdout[-600:], out.stderr[-1500:] if out.returncode else "")
    assert ".apworld" in out.stdout and f"VERSION {VERSION}" in out.stdout
finally:
    os.remove(os.path.join(cw, "ff_resonance.apworld"))
    shutil.move(hold, dst)
print("client version: ok")
