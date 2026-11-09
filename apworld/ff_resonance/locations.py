from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType, Region

from .data import CHESTS, CONTINENT_UNLOCKS, FINAL_AREA, ITEMS, OPEN_AREA, SHINIES
from .items import GAME, FFResonanceItem

if TYPE_CHECKING:
    from .world import FFResonanceWorld

ALL_LOCATIONS = CHESTS + SHINIES
LOCATION_NAME_TO_ID: dict[str, int] = {loc["name"]: loc["id"] for loc in ALL_LOCATIONS}
LOCATION_KEY_TO_ID: dict[str, int] = {loc["key"]: loc["id"] for loc in ALL_LOCATIONS}

location_name_groups: dict[str, set[str]] = {}
for _loc in ALL_LOCATIONS:
    location_name_groups.setdefault(_loc["region"], set()).add(_loc["name"])
location_name_groups["Chests"] = {loc["name"] for loc in CHESTS}
location_name_groups["Shinies"] = {loc["name"] for loc in SHINIES}

GOAL_EVENT = "Story Goal"
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
    excluded = world.options.excluded_regions.value

    for loc in chosen:
        region = regions[loc["area"]]
        location = FFResonanceLocation(player, loc["name"], loc["id"], region)
        # A place with no route on the open world start may only hold filler.
        if loc["region"] in excluded or not loc["open_world"]:
            location.progress_type = LocationProgressType.EXCLUDED
        region.locations.append(location)
        world.vanilla_items.append(loc["vanilla"])

    goal_region = regions[FINAL_AREA]
    goal = FFResonanceLocation(player, GOAL_EVENT, None, goal_region)
    goal.place_locked_item(FFResonanceItem(VICTORY, ItemClassification.progression, None, player))
    goal_region.locations.append(goal)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY, player)
