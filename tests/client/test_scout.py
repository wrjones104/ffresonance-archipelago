"""The client's location scouting (world 0.1.4): the request, and the scout lines it writes."""

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
from worlds.ff_resonance.client import FFResonanceContext, LOCATION_ID_TO_KEY  # noqa: E402
from worlds.ff_resonance.locations import LOCATION_KEY_TO_ID  # noqa: E402

failures = 0


def check(name, cond, detail=""):
    global failures
    print(("ok  " if cond else "FAIL") + " " + name + ("" if cond else f": {detail}"))
    failures += 0 if cond else 1


async def main():
    folder = tempfile.mkdtemp()
    ctx = FFResonanceContext(None, None, folder)
    sent = []

    async def fake_send(msgs):
        sent.extend(msgs)

    ctx.send_msgs = fake_send
    ctx.session_key, ctx.slot, ctx.team = "S:0:1", 1, 0
    ctx.player_names = {1: "Jones", 2: "Alice"}
    ctx.start_session()

    keys = ["chest:3001:0", "chest:3001:1"]
    ids = [LOCATION_KEY_TO_ID[k] for k in keys]
    ctx.server_locations = set(ids) | {999999999}
    ctx.scout_locations()
    await asyncio.sleep(0)
    check("one LocationScouts request", len(sent) == 1 and sent[0]["cmd"] == "LocationScouts", sent)
    check("only our locations, no hints", sent and sent[0]["locations"] == sorted(ids) and sent[0]["create_as_hint"] == 0, sent)

    # the item names come from the data package; a lookup stand-in keeps the test off the network
    ctx.item_names.lookup_in_slot = lambda item, slot: {500: "Tent", 7001: "Hookshot"}.get(item, f"Item {item}")
    items = [NetworkItem(500, ids[0], 1, 0), NetworkItem(7001, ids[1], 2, 1), NetworkItem(1, 999999999, 2, 0)]
    written = ctx.write_scouts(items)
    with open(os.path.join(folder, "ap_in.txt"), encoding="utf-8") as f:
        text = f.read()
    check("two scout lines", written == 2, written)
    check("own item line", "scout\tchest:3001:0\tTent\tJones\t0\t1\n" in text, text)
    check("other player's line", "scout\tchest:3001:1\tHookshot\tAlice\t1\t0\n" in text, text)
    check("raw lists are read too", ctx.write_scouts([[500, ids[0], 1, 0]]) == 1)

    # a reconnect to the same session: the file has scout lines, so no second request
    sent.clear()
    ctx2 = FFResonanceContext(None, None, folder)
    ctx2.send_msgs = fake_send
    ctx2.session_key, ctx2.slot, ctx2.team = "S:0:1", 1, 0
    ctx2.start_session()
    ctx2.server_locations = set(ids)
    ctx2.scout_locations()
    await asyncio.sleep(0)
    check("no second request on reconnect", sent == [], sent)
    check("LOCATION_ID_TO_KEY reverses the table", LOCATION_ID_TO_KEY[ids[0]] == keys[0])
    for c in (ctx, ctx2):
        if c.keep_alive_task:
            c.keep_alive_task.cancel()


asyncio.run(main())
print("failures:", failures)
sys.exit(1 if failures else 0)
