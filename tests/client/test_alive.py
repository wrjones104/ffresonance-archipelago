"""Round 116: the client's heartbeat. ap_alive.txt holds the time and the session while the client is
connected to its slot, is rewritten every ALIVE_SECONDS, and goes away on a disconnect."""

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

from worlds.ff_resonance.client import ALIVE_SECONDS, FFResonanceContext  # noqa: E402

SESSION_KEY = "S116:0:1"
CONNECTED_AT = 1_800_000_000.0


async def main():
    folder = tempfile.mkdtemp()
    os.makedirs(os.path.join(folder, "Scripts"))
    open(os.path.join(folder, "Scripts", "main.lua"), "w").close()
    ctx = FFResonanceContext(None, None, folder)
    alive = os.path.join(folder, "ap_alive.txt")

    ctx.clear_alive()
    assert not os.path.exists(alive), "nothing written before a connection"

    ctx.session_key, ctx.slot, ctx.team = SESSION_KEY, 1, 0
    ctx.write_alive(CONNECTED_AT)
    assert open(alive, encoding="utf-8").read() == f"{int(CONNECTED_AT)}\t{SESSION_KEY}\n"

    ctx.write_alive(CONNECTED_AT + ALIVE_SECONDS / 2)
    assert open(alive, encoding="utf-8").read().startswith(f"{int(CONNECTED_AT)}\t"), "not rewritten every poll"
    ctx.write_alive(CONNECTED_AT + ALIVE_SECONDS)
    assert open(alive, encoding="utf-8").read().startswith(f"{int(CONNECTED_AT + ALIVE_SECONDS)}\t")

    ctx.reset_server_state()
    assert not os.path.exists(alive), "a disconnect takes the heartbeat away"
    ctx.clear_alive()
    print("ok  ap_alive.txt while connected, gone after")


asyncio.run(main())
