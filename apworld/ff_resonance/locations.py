from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType, Region

from .data import BOSSES, CHESTS, CONTINENT_UNLOCKS, CRYSTALS, FINAL_AREA, ITEMS, OPEN_AREA, SHINIES, TABLET_SHINIES
from .items import FRAGMENT_NAME, GAME, FFResonanceItem, create_item, progression_ids

if TYPE_CHECKING:
    from .world import FFResonanceWorld

ALL_LOCATIONS = CHESTS + SHINIES + CRYSTALS + TABLET_SHINIES + BOSSES
LOCATION_NAME_TO_ID: dict[str, int] = {loc["name"]: loc["id"] for loc in ALL_LOCATIONS}
LOCATION_KEY_TO_ID: dict[str, int] = {loc["key"]: loc["id"] for loc in ALL_LOCATIONS}

location_name_groups: dict[str, set[str]] = {}
for _loc in ALL_LOCATIONS:
    location_name_groups.setdefault(_loc["region"], set()).add(_loc["name"])
location_name_groups["Chests"] = {loc["name"] for loc in CHESTS}
location_name_groups["Shinies"] = {loc["name"] for loc in SHINIES}
location_name_groups["Crystals"] = {loc["name"] for loc in CRYSTALS}
location_name_groups["Tablet Shard Shinies"] = {loc["name"] for loc in TABLET_SHINIES}
location_name_groups["Fragment Bosses"] = {loc["name"] for loc in BOSSES if loc["fragment"]}

# Round 60: at party level 28 Sephiroth took no damage, even with enemy scaling at its lowest. So
# priority_bosses does not put a needed item on him.
SEPHIROTH = "boss:9138"

GOAL_EVENT = "Story Goal"
SHARD_GOAL_EVENT = "Tablet Shard Goal"
VICTORY = "Victory"

UNLOCK_NAMES = {continent: ITEMS[ap_id]["name"] for continent, ap_id in CONTINENT_UNLOCKS.items()}


class FFResonanceLocation(Location):
    game = GAME


def create_regions_and_locations(world: FFResonanceWorld) -> None:
    """
    One region per continent, each behind its unlock item. The Crystal Tower and the goal need
    every unlock: the tower is open from the start in game, but it is the end of the road, and
    this keeps what the player needs out of it until the continents are done. Everything on a
    continent counts as reachable once it opens.
    """
    player = world.player
    menu = Region("Menu", player, world.multiworld)
    world.multiworld.regions.append(menu)
    regions = {OPEN_AREA: menu}

    def add_region(name: str, rule) -> None:
        region = Region(name, player, world.multiworld)
        world.multiworld.regions.append(region)
        menu.connect(region, f"To {name}", rule)
        regions[name] = region

    for continent, unlock in UNLOCK_NAMES.items():
        add_region(continent, lambda state, unlock=unlock: state.has(unlock, player))
    every_unlock = list(UNLOCK_NAMES.values())
    add_region(FINAL_AREA, lambda state: state.has_all(every_unlock, player))

    chosen = list(CHESTS)
    if world.options.include_shinies:
        chosen += SHINIES
    if world.options.include_crystals:
        chosen += CRYSTALS
    if world.options.include_tablet_shards:
        chosen += TABLET_SHINIES
    if world.options.include_bosses:
        chosen += BOSSES
    excluded = world.options.excluded_regions.value
    in_pool = set(progression_ids(world))

    for loc in chosen:
        region = regions[loc["area"]]
        location = FFResonanceLocation(player, loc["name"], loc["id"], region)
        # A place with no route on the open world start may only hold filler.
        if loc["region"] in excluded or not loc["open_world"]:
            location.progress_type = LocationProgressType.EXCLUDED
        # Oblivion Palace's chests open as Tablet Shards are turned in (3 for the first, 99 for
        # the last). With the shards not in the pool, logic cannot count them: filler only.
        if "shards" in loc:
            if world.options.include_tablet_shards:
                location.access_rule = lambda state, n=loc["shards"]: state.has("Tablet Shard", player, n)
            else:
                location.progress_type = LocationProgressType.EXCLUDED
        # Doors that test a key item (data/gates.tsv). With the item not in the pool, logic
        # cannot count the copy the game hands out: filler only.
        if "needs" in loc:
            if in_pool.issuperset(loc["needs"]):
                names = [ITEMS[ap_id]["name"] for ap_id in loc["needs"]]
                location.access_rule = lambda state, names=names: state.has_all(names, player)
            else:
                location.progress_type = LocationProgressType.EXCLUDED
        if (world.options.priority_bosses and loc.get("fragment") is False and loc["key"] != SEPHIROTH
                and location.progress_type == LocationProgressType.DEFAULT):
            location.progress_type = LocationProgressType.PRIORITY
        region.locations.append(location)
        # Round 59: a story boss gives a Crystal Fragment, always its own.
        if loc.get("fragment"):
            location.place_locked_item(create_item(world, FRAGMENT_NAME))
        if loc["vanilla"] is not None:
            world.vanilla_items.append(loc["vanilla"])

    if world.options.goal.value == world.options.goal.option_tablet_shards:
        goal_region = menu
        needed = world.options.tablet_shards_required.value
        goal = FFResonanceLocation(player, SHARD_GOAL_EVENT, None, goal_region)
        goal.access_rule = lambda state: state.has("Tablet Shard", player, needed)
    else:
        goal_region = regions[FINAL_AREA]
        goal = FFResonanceLocation(player, GOAL_EVENT, None, goal_region)
        # The final boss lock: the starting party counts, so only the members beyond it are items.
        members = max(0, world.final_boss_characters - len(world.starting_party))
        visions = world.final_boss_visions
        fragments = world.final_boss_fragments
        goal.access_rule = lambda state: (state.has_group("Party Members", player, members) and
                                          state.has_group("Visions", player, visions) and
                                          state.has(FRAGMENT_NAME, player, fragments))
    goal.place_locked_item(FFResonanceItem(VICTORY, ItemClassification.progression, None, player))
    goal_region.locations.append(goal)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY, player)
