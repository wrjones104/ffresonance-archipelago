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

    connect(ctx, "G3", {"goal_story_checkpoint": 1130})
    check("a seed before world 0.7.0 has the story goal", ctx.goal_kind == "story_checkpoint" and ctx.goal == 1130)

    if ctx.keep_alive_task:
        ctx.keep_alive_task.cancel()


asyncio.run(main())
print("failures:", failures)
sys.exit(1 if failures else 0)
