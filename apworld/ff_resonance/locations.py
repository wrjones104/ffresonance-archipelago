from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType, Region

from .data import CHESTS, SHINIES
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


class FFResonanceLocation(Location):
    game = GAME


def create_regions_and_locations(world: FFResonanceWorld) -> None:
    """
    The MVP is one region. Nothing the story needs is shuffled, so every location is reachable
    from the start as far as logic goes. Late-game locations are simply late.
    """
    menu = Region("Menu", world.player, world.multiworld)
    world.multiworld.regions.append(menu)

    chosen = list(CHESTS)
    if world.options.include_shinies:
        chosen += SHINIES
    excluded = world.options.excluded_regions.value

    for loc in chosen:
        location = FFResonanceLocation(world.player, loc["name"], loc["id"], menu)
        if loc["region"] in excluded:
            location.progress_type = LocationProgressType.EXCLUDED
        menu.locations.append(location)
        world.vanilla_items.append(loc["vanilla"])

    goal = FFResonanceLocation(world.player, GOAL_EVENT, None, menu)
    goal.place_locked_item(FFResonanceItem(VICTORY, ItemClassification.progression, None, world.player))
    menu.locations.append(goal)
    world.multiworld.completion_condition[world.player] = lambda state: state.has(VICTORY, world.player)
