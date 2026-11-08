"""Checks the client's session key with the 0.6.7 behaviour (seed_name never set from RoomInfo)."""

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

failures = 0


def check(name, cond):
    global failures
    print(("ok  " if cond else "FAIL") + " " + name)
    failures += 0 if cond else 1


def connect(ctx, seed, slot=1):
    ctx.reset_server_state()
    if hasattr(ctx, "server_seed_name"):
        ctx.server_seed_name = None  # simulate 0.6.7: never set
    ctx.seed_name = None
    if seed is not None:
        ctx.on_package("RoomInfo", {"seed_name": seed})
    ctx.team, ctx.slot = 0, slot
    ctx.on_package("Connected", {"slot_data": {"goal_story_checkpoint": 1130}})


async def main():
    folder = tempfile.mkdtemp()
    ctx = FFResonanceContext(None, None, folder)

    connect(ctx, "11111111111111111111")
    check("key uses RoomInfo seed", ctx.session_key == "11111111111111111111:0:1")
    with open(os.path.join(folder, "ap_in.txt"), encoding="utf-8") as f:
        first = f.readline().rstrip("\n")
    check("ap_in seed line", first == "seed\t11111111111111111111:0:1")

    connect(ctx, "22222222222222222222")
    check("new seed gives new key", ctx.session_key == "22222222222222222222:0:1")

    connect(ctx, None)
    check("no seed name: not connected to bridge", ctx.session_key is None)

    ctx.reset_server_state()
    check("reset clears room seed", ctx.room_seed_name is None)

    if ctx.keep_alive_task:
        ctx.keep_alive_task.cancel()


asyncio.run(main())
print("failures:", failures)
sys.exit(1 if failures else 0)
