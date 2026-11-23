"""Round 77: ap_in.txt deleted while the client is connected is written again, whole."""

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

from NetUtils import NetworkItem  # noqa: E402
from worlds.ff_resonance.client import FFResonanceContext  # noqa: E402

POTION, POTION_X2 = 1001, 1002
SESSION_KEY = "S77:0:1"
SLOT_DATA = {"open_world": True, "starting_party": [1004, 1005]}


async def main():
    folder = tempfile.mkdtemp()
    os.makedirs(os.path.join(folder, "Scripts"))
    open(os.path.join(folder, "Scripts", "main.lua"), "w").close()
    ctx = FFResonanceContext(None, None, folder)

    async def fake_send(msgs):
        pass

    ctx.send_msgs = fake_send
    ctx.session_key, ctx.slot, ctx.team = SESSION_KEY, 1, 0
    ctx.player_names = {1: "Jones"}
    ctx.slot_data = SLOT_DATA
    ctx.start_session()
    ctx.write_config(SLOT_DATA)
    ctx.items_received = [NetworkItem(POTION, 1, 1, 0), NetworkItem(POTION_X2, 2, 1, 0)]
    ctx.write_new_items()
    in_path = os.path.join(folder, "ap_in.txt")
    assert ctx.restore_session_file() is False, "the file is there: nothing to do"

    os.remove(in_path)
    assert ctx.restore_session_file() is True
    ctx.write_new_items()
    lines = open(in_path, encoding="utf-8").read().splitlines()
    assert lines[0] == f"seed\t{SESSION_KEY}", lines[0]
    assert "cfg\topenworld\t1" in lines and "cfg\tparty\t1004,1005" in lines, lines
    assert "cfg\tforge\t0" in lines, "round 105: a seed without the option has no forge locations"
    assert "cfg\tkeyitems\t1" in lines, "round 107: key items are shuffled by default, also in old seeds"
    items = [line.split("\t")[1] for line in lines if line.startswith("item\t")]
    assert items == ["0", "1"], "every item again, from index 0: " + str(items)
    print("ok  ap_in.txt written again after a delete")


asyncio.run(main())
