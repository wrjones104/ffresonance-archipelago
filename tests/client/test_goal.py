"""The client's goal: Tablet Shards counted from the items received."""

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
from worlds.ff_resonance.client import SHARD_ITEM, FFResonanceContext  # noqa: E402

failures = 0


def check(name, cond):
    global failures
    print(("ok  " if cond else "FAIL") + " " + name)
    failures += 0 if cond else 1


def connect(ctx, seed, slot_data):
    ctx.reset_server_state()
    ctx.on_package("RoomInfo", {"seed_name": seed})
    ctx.team, ctx.slot = 0, 1
    ctx.on_package("Connected", {"slot_data": slot_data})


async def main():
    folder = tempfile.mkdtemp()
    ctx = FFResonanceContext(None, None, folder)
    in_path = os.path.join(folder, "ap_in.txt")
    shard = lambda player=1: NetworkItem(SHARD_ITEM, 1, player, 0)

    connect(ctx, "G1", {"goal": "tablet_shards", "tablet_shards_required": 2, "open_world": True})
    text = open(in_path, encoding="utf-8").read()
    check("no scaling line on the bridge", "cfg\tscale" not in text)
    check("no shards, no goal", not ctx.goal_reached())

    ctx.player_names = {1: "Me", 2: "Rat"}
    ctx.items_received = [shard()]
    ctx.write_new_items()
    check("one shard is not enough", not ctx.goal_reached())
    ctx.items_received = [shard(), shard(2)]
    ctx.write_new_items()
    lines = [line for line in open(in_path, encoding="utf-8").read().splitlines() if line.startswith("item")]
    check("own shard counts up", lines[0].endswith("Tablet Shard (1/2)"))
    check("a sent shard counts up", lines[1].endswith("Tablet Shard (2/2) from Rat"))
    check("enough shards complete the goal", ctx.goal_reached())
    ctx.max_story = 9999
    ctx.items_received = []
    check("the story does not count for the shard goal", not ctx.goal_reached())

    connect(ctx, "G2", {"goal": "story_checkpoint", "goal_story_checkpoint": 8020})
    ctx.items_received = [shard(), shard()]
    ctx.max_story = 8019
    check("shards do not count for the story goal", not ctx.goal_reached())
    ctx.max_story = 8020
    check("the story goal", ctx.goal_reached())

    # Round 58: the final boss lock's counts go to the mod each time they change
    from worlds.ff_resonance.data import ITEMS, UNIT_ITEM_BASE
    vision_ids = sorted(ap_id for ap_id, info in ITEMS.items() if info["category"] == "vision")
    connect(ctx, "G4", {"goal": "story_checkpoint", "starting_party": [1001, 1002],
                        "final_boss_characters": 4, "final_boss_visions": 2})
    lock_lines = lambda: [line for line in open(in_path, encoding="utf-8").read().splitlines() if line.startswith("cfg\tfinalboss")]
    ctx.items_received = []
    ctx.write_lock()
    check("the starting party counts", lock_lines()[-1] == "cfg\tfinalboss\t2\t4\t0\t2")
    ctx.write_lock()
    check("written once while nothing changes", len(lock_lines()) == 1)
    ctx.items_received = [NetworkItem(UNIT_ITEM_BASE + 1003, 1, 1, 0), NetworkItem(UNIT_ITEM_BASE + 1001, 1, 1, 0),
                          NetworkItem(vision_ids[0], 1, 1, 0), NetworkItem(vision_ids[0], 1, 1, 0)]
    ctx.write_lock()
    check("a starter received again and a repeated vision count once", lock_lines()[-1] == "cfg\tfinalboss\t3\t4\t1\t2")
    connect(ctx, "G5", {"goal": "tablet_shards", "tablet_shards_required": 1})
    ctx.items_received = [shard(), shard()]
    ctx.write_new_items()
    shard_lines = [line for line in open(in_path, encoding="utf-8").read().splitlines() if line.startswith("item")]
    check("past the goal only the count shows", shard_lines[-1].endswith("Tablet Shard (2)"))

    # Round 58: the final boss goal is the mod's `won 9056` line, or the ending's story 9000
    out_path = os.path.join(folder, "ap_out.txt")
    connect(ctx, "G6", {"goal": "final_boss"})
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("hello\t0.45.0\nseed\tG6:0:1\nstory\t8050\n")
    ctx.read_new_output()
    check("story 8050 is not the final boss", not ctx.goal_reached())
    with open(out_path, "a", encoding="utf-8") as f:
        f.write("won\t9056\n")
    ctx.read_new_output()
    check("the last battle won", ctx.goal_reached() and "Sol" in ctx.goal_text())
    connect(ctx, "G7", {"goal": "final_boss"})
    check("a new seed starts with no battles won", not ctx.goal_reached())
    ctx.max_story = 9000
    check("the ending's 9000 if the win was missed", ctx.goal_reached())

    connect(ctx, "G3", {"goal_story_checkpoint": 1130})
    check("a seed before world 0.7.0 has the story goal", ctx.goal_kind == "story_checkpoint" and ctx.goal == 1130)

    if ctx.keep_alive_task:
        ctx.keep_alive_task.cancel()


asyncio.run(main())
print("failures:", failures)
sys.exit(1 if failures else 0)
