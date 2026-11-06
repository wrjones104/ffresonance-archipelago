from collections.abc import Mapping
from typing import Any, ClassVar

import settings
from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld, World

from . import items, locations
from . import options as ffr_options

# The bridge protocol between the client and the in-game mod. The client refuses a mod that
# reports an older one.
MOD_PROTOCOL = 1


class FFResonanceSettings(settings.Group):
    class ModFolder(settings.UserFolderPath):
        """
        The FFRArchipelago mod's folder inside the game's UE4SS Mods folder. The client and the
        mod talk through text files in it.
        """
        description = "FFRArchipelago mod folder"

    mod_folder: ModFolder = ModFolder(
        "C:/Program Files (x86)/Steam/steamapps/common/FINAL FANTASY RESONANCE/FFRS/Binaries/Win64/ue4ss/Mods/FFRArchipelago"
    )


class FFResonanceWebWorld(WebWorld):
    theme = "ocean"
    tutorials = [
        Tutorial(
            "Multiworld Setup Guide",
            "Setting up Final Fantasy Resonance for Archipelago.",
            "English",
            "setup_en.md",
            "setup/en",
            ["wrjones104"],
        )
    ]
    option_groups = ffr_options.option_groups


class FFResonanceWorld(World):
    """
    Final Fantasy Resonance, played with a UE4SS mod that grants received items in game and
    reports opened chests and picked-up shinies. Chests that hold consumables, equipment or gil
    are shuffled. Party members, visions and key items can be added to the pool as well; the
    story still hands out its own copies.
    """

    game = items.GAME
    web = FFResonanceWebWorld()
    options_dataclass = ffr_options.FFResonanceOptions
    options: ffr_options.FFResonanceOptions
    settings: ClassVar[FFResonanceSettings]
    settings_key = "ff_resonance_options"

    item_name_to_id = items.ITEM_NAME_TO_ID
    location_name_to_id = locations.LOCATION_NAME_TO_ID
    item_name_groups = items.item_name_groups
    location_name_groups = locations.location_name_groups

    def __init__(self, multiworld, player):
        super().__init__(multiworld, player)
        self.vanilla_items: list[int] = []

    def create_regions(self) -> None:
        locations.create_regions_and_locations(self)

    def create_items(self) -> None:
        items.create_all_items(self)

    def create_item(self, name: str) -> items.FFResonanceItem:
        return items.create_item(self, name)

    def get_filler_item_name(self) -> str:
        return items.get_filler_item_name(self)

    def fill_slot_data(self) -> Mapping[str, Any]:
        return {
            **self.options.as_dict("goal_story_checkpoint", "include_shinies"),
            "mod_protocol": MOD_PROTOCOL,
        }
