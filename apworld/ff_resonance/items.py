from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification
from Options import OptionError

from .data import CHESTS, CONTINENT_UNLOCKS, FRAGMENT_ITEM, ITEMS, PROGRESSION, UNIT_ITEM_BASE

if TYPE_CHECKING:
    from .world import FFResonanceWorld

GAME = "Final Fantasy Resonance"
FRAGMENT_NAME = ITEMS[FRAGMENT_ITEM]["name"]

ITEM_NAME_TO_ID: dict[str, int] = {info["name"]: ap_id for ap_id, info in ITEMS.items()}

# Continent unlocks are what the logic reads (world 0.4.0). Party members, visions and key items
# are progression too (world 0.3.0), though no logic reads them yet: they are marked so the logic
# can use them later without a change of item ids or classes.
# Equipment is useful, so hints and fill treat it as worth something.
CLASSIFICATIONS = {
    "consumable": ItemClassification.filler,
    "equipment": ItemClassification.useful,
    "magicite": ItemClassification.useful,
    "shard": ItemClassification.useful,
    "gil": ItemClassification.filler,
    "party": ItemClassification.progression,
    "vision": ItemClassification.progression,
    "key": ItemClassification.progression,
    "continent": ItemClassification.progression,
    "fragment": ItemClassification.progression,
}

item_name_groups: dict[str, set[str]] = {
    "Consumables": {i["name"] for i in ITEMS.values() if i["category"] == "consumable"},
    "Equipment": {i["name"] for i in ITEMS.values() if i["category"] == "equipment"},
    "Gil": {i["name"] for i in ITEMS.values() if i["category"] == "gil"},
    "Party Members": {i["name"] for i in ITEMS.values() if i["category"] == "party"},
    "Visions": {i["name"] for i in ITEMS.values() if i["category"] == "vision"},
    "Key Items": {i["name"] for i in ITEMS.values() if i["category"] == "key"},
    "Continent Unlocks": {i["name"] for i in ITEMS.values() if i["category"] == "continent"},
}

FILLER_NAMES = sorted(item_name_groups["Consumables"])
FILLER_CATEGORIES = {"consumable", "gil"}
SHARDS_FOR_CHESTS = max(c.get("shards", 0) for c in CHESTS)


class FFResonanceItem(Item):
    game = GAME


def create_item(world: FFResonanceWorld, name: str) -> FFResonanceItem:
    ap_id = ITEM_NAME_TO_ID[name]
    return FFResonanceItem(name, CLASSIFICATIONS[ITEMS[ap_id]["category"]], ap_id, world.player)


def progression_ids(world: FFResonanceWorld) -> list[int]:
    """
    The progression items the options put in the pool, one of each: every continent's unlock but
    the starting continent's, and every party member but those the player starts with.
    """
    start = world.starting_continent
    chosen = [ap_id for name, ap_id in CONTINENT_UNLOCKS.items() if name != start]
    if world.options.shuffle_party_members:
        starters = {UNIT_ITEM_BASE + unit for unit in world.starting_party}
        chosen += [ap_id for ap_id in PROGRESSION["party"] if ap_id not in starters]
    if world.options.shuffle_visions:
        chosen += PROGRESSION["vision"]
    if world.options.shuffle_key_items:
        chosen += PROGRESSION["key"]
    return chosen


def create_all_items(world: FFResonanceWorld) -> None:
    """
    One item per location. Each location's own vanilla content goes into the pool, then each
    progression item takes the place of one filler item (a consumable or gil), picked at random.
    """
    pool_ids = list(world.vanilla_items)
    extra = progression_ids(world)
    filler_at = [i for i, ap_id in enumerate(pool_ids) if ITEMS[ap_id]["category"] in FILLER_CATEGORIES]
    if len(extra) > len(filler_at):
        raise OptionError(f"{world.player_name}: {len(extra)} items to add, but only {len(filler_at)} "
                          f"filler items to replace. Turn off a shuffle option.")
    for i in sorted(world.random.sample(filler_at, len(extra)), reverse=True):
        pool_ids.pop(i)
    pool = [create_item(world, ITEMS[ap_id]["name"]) for ap_id in pool_ids + extra]
    # The logic counts only progression items, so just the shards the goal and Oblivion Palace's
    # chests ask for are marked. The player can still finish with any shards: the client counts
    # them all.
    marked = SHARDS_FOR_CHESTS if world.options.include_tablet_shards else 0
    if world.options.goal.value == world.options.goal.option_tablet_shards:
        marked = max(marked, world.options.tablet_shards_required.value)
    shards = [item for item in pool if item.name == "Tablet Shard"]
    for item in shards[:marked]:
        item.classification = ItemClassification.progression_skip_balancing
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    pool += [world.create_filler() for _ in range(unfilled - len(pool))]
    world.multiworld.itempool += pool
    # The starting continent's unlock is handed over at the start, through the normal item path.
    world.multiworld.push_precollected(create_item(world, ITEMS[CONTINENT_UNLOCKS[world.starting_continent]]["name"]))


def get_filler_item_name(world: FFResonanceWorld) -> str:
    return world.random.choice(FILLER_NAMES)
