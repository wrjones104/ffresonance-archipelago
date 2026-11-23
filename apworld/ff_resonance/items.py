from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification, LocationProgressType
from Options import OptionError

from .data import (ADAMANTITE_ITEM, AIRSHIP_ITEM, CAPABILITIES, CHOCOBO_ITEM, CONTINENT_UNLOCKS, FILLER_VALUE, FORGE,
                   FRAGMENT_ITEM, ITEMS, MAGICITE_ITEMS, POOL_ADDITIONS, PROGRESSION, RADAR_ITEM, RADAR_PARTS,
                   UNIT_ITEM_BASE)

if TYPE_CHECKING:
    from .world import FFResonanceWorld

GAME = "Final Fantasy Resonance"
FRAGMENT_NAME = ITEMS[FRAGMENT_ITEM]["name"]

ITEM_NAME_TO_ID: dict[str, int] = {info["name"]: ap_id for ap_id, info in ITEMS.items()}

# Continent unlocks are what the logic reads. Party members, visions and key items are marked
# progression too so future logic changes do not alter item IDs or classes.
# Equipment is useful, so hints and fill treat it as worth something. Round 74: Magicite awakens
# Visions, and boss logic counts it (boss_logic.awakening). There are many copies, so it skips
# balancing. Tablet Shards too: Oblivion Palace's chests and the shard goal count them. Round 75:
# every shard is progression from create_item, as Universal Tracker makes its items that way and
# counted none of the shards when only the pool's copies were marked.
CLASSIFICATIONS = {
    "consumable": ItemClassification.filler,
    "equipment": ItemClassification.useful,
    "magicite": ItemClassification.progression_skip_balancing,
    "shard": ItemClassification.progression_skip_balancing,
    "gil": ItemClassification.filler,
    "party": ItemClassification.progression,
    "vision": ItemClassification.progression,
    "key": ItemClassification.progression,
    "continent": ItemClassification.progression,
    "fragment": ItemClassification.progression,
    "vehicle": ItemClassification.progression,
    "radar": ItemClassification.progression,
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
STARTER_VISIONS = (13024001, 13045001)      # Tronn and Leah (Mitra story C01_014_03)
# Round 104: the visions that cast Cure or Esuna unawakened (data/game/capabilities.tsv).
HEALING_VISIONS = sorted({ap_id for capability in ("heal", "cleanse")
                          for ap_id, needed in CAPABILITIES[capability]["vision"].items() if needed == 0})


class FFResonanceItem(Item):
    game = GAME


def create_item(world: FFResonanceWorld, name: str) -> FFResonanceItem:
    ap_id = ITEM_NAME_TO_ID[name]
    return FFResonanceItem(name, CLASSIFICATIONS[ITEMS[ap_id]["category"]], ap_id, world.player)


def progression_ids(world: FFResonanceWorld) -> list[int]:
    """
    The progression items the options put in the pool, one of each: every continent's unlock but
    the starting continent's, every party member but those the player starts with, and the
    Chocobo and the Airship when the player does not start with them.
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
    if not world.options.start_with_chocobo:
        chosen.append(CHOCOBO_ITEM)
    if not world.options.start_with_airship:
        chosen.append(AIRSHIP_ITEM)
    # Three Progressive Radars replace individual radar parts when radar treasures are included.
    if world.options.include_radar_treasures:
        chosen = [ap_id for ap_id in chosen if ap_id not in RADAR_PARTS] + [RADAR_ITEM] * 3
    return chosen


def additions(world: FFResonanceWorld) -> list[int]:
    """Items no location holds: the gear of data/pool_additions.tsv, then extra_magicite split
    evenly over the three tiers, lowest first. The pool drops them from the end when short."""
    count = world.options.extra_magicite.value
    tiers = len(MAGICITE_ITEMS)
    magicite = [ap_id for tier, ap_id in enumerate(MAGICITE_ITEMS)
                for _ in range(count // tiers + (tier < count % tiers))]
    return list(POOL_ADDITIONS) + magicite


def create_all_items(world: FFResonanceWorld) -> None:
    """
    One item per location. Each location's own vanilla content goes into the pool, then each
    progression item takes the place of one filler item (a consumable or gil), picked at random.
    Then each addition takes the place of the cheapest filler left.
    """
    pool_ids = list(world.vanilla_items)
    # Round 97: a progression item a chosen location holds (a lab key card on its own spot) is in
    # the pool already.
    held = set(pool_ids)
    extra = [ap_id for ap_id in progression_ids(world) if ap_id not in held] + list(world.extra_items)
    filler_at = [i for i, ap_id in enumerate(pool_ids) if ITEMS[ap_id]["category"] in FILLER_CATEGORIES]
    if len(extra) > len(filler_at):
        raise OptionError(f"{world.player_name}: {len(extra)} items to add, but only {len(filler_at)} "
                          f"filler items to replace. Turn off a shuffle option.")
    taken = set(world.random.sample(filler_at, len(extra)))
    # Round 104: the random tiebreak keeps the same Potion from always going first.
    cheapest = sorted((i for i in filler_at if i not in taken),
                      key=lambda i: (FILLER_VALUE[pool_ids[i]], world.random.random()))
    # Excluded locations (the Oblivion Palace's, excluded_regions, the yaml's exclude_locations) take
    # filler only, so that much filler stays.
    excluded = {loc.name for loc in world.get_locations() if loc.progress_type == LocationProgressType.EXCLUDED}
    excluded |= world.options.exclude_locations.value & {loc.name for loc in world.get_locations()}
    room = max(0, len(cheapest) - len(excluded))
    added = additions(world)
    if len(added) > room:
        logging.warning(f"{world.player_name}: {len(added) - room} of {len(added)} added items left out: "
                        f"{len(cheapest)} filler items are left, and {len(excluded)} excluded locations need filler.")
        added = added[:room]
    taken.update(cheapest[:len(added)])
    pool_ids = [ap_id for i, ap_id in enumerate(pool_ids) if i not in taken]
    # Round 105: the forge's locations hold the Adamantite its weapons cost, one each, less the copies
    # in the pool already (the key item's). The rest of its locations get filler, below.
    forged = []
    if world.options.include_aileens_forge:
        forged = [ADAMANTITE_ITEM] * max(0, len(FORGE) - (pool_ids + extra).count(ADAMANTITE_ITEM))
    pool = [create_item(world, ITEMS[ap_id]["name"]) for ap_id in pool_ids + extra + added + forged]
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    pool += [world.create_filler() for _ in range(unfilled - len(pool))]
    world.multiworld.itempool += pool
    # The starting continent's unlock is handed over at the start, through the normal item path.
    world.multiworld.push_precollected(create_item(world, ITEMS[CONTINENT_UNLOCKS[world.starting_continent]]["name"]))
    if not world.options.shuffle_visions:
        for ap_id in STARTER_VISIONS:
            world.multiworld.push_precollected(create_item(world, ITEMS[ap_id]["name"]))
    elif world.options.early_healing_vision:
        healer = world.random.choice(HEALING_VISIONS)
        world.multiworld.local_early_items[world.player][ITEMS[healer]["name"]] = 1


def get_filler_item_name(world: FFResonanceWorld) -> str:
    return world.random.choice(FILLER_NAMES)
