from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import Item, ItemClassification

from .data import ITEMS

if TYPE_CHECKING:
    from .world import FFResonanceWorld

GAME = "Final Fantasy Resonance"

ITEM_NAME_TO_ID: dict[str, int] = {info["name"]: ap_id for ap_id, info in ITEMS.items()}

# The MVP has no progression items: key items and story items stay where the game puts them,
# so the story can always be finished. Equipment is marked useful, so hints and fill treat it
# as worth something.
CLASSIFICATIONS = {
    "consumable": ItemClassification.filler,
    "equipment": ItemClassification.useful,
    "gil": ItemClassification.filler,
}

item_name_groups: dict[str, set[str]] = {
    "Consumables": {i["name"] for i in ITEMS.values() if i["category"] == "consumable"},
    "Equipment": {i["name"] for i in ITEMS.values() if i["category"] == "equipment"},
    "Gil": {i["name"] for i in ITEMS.values() if i["category"] == "gil"},
}

FILLER_NAMES = sorted(item_name_groups["Consumables"])


class FFResonanceItem(Item):
    game = GAME


def create_item(world: FFResonanceWorld, name: str) -> FFResonanceItem:
    ap_id = ITEM_NAME_TO_ID[name]
    return FFResonanceItem(name, CLASSIFICATIONS[ITEMS[ap_id]["category"]], ap_id, world.player)


def create_all_items(world: FFResonanceWorld) -> None:
    """One item per location: each location's own vanilla content goes into the pool."""
    pool = [create_item(world, ITEMS[ap_id]["name"]) for ap_id in world.vanilla_items]
    unfilled = len(world.multiworld.get_unfilled_locations(world.player))
    pool += [world.create_filler() for _ in range(unfilled - len(pool))]
    world.multiworld.itempool += pool


def get_filler_item_name(world: FFResonanceWorld) -> str:
    return world.random.choice(FILLER_NAMES)
