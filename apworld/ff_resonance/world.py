from collections.abc import Mapping
from typing import Any, ClassVar

import settings
from BaseClasses import Tutorial
from worlds.AutoWorld import WebWorld, World

from . import items, locations
from . import options as ffr_options

# The bridge protocol between the client and the in-game mod. The client refuses a mod that
# reports an older one.
MOD_PROTOCOL = 2

ALL_PARTY_MEMBERS = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008]


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
    reports opened chests and picked-up shinies. A seed starts in the open world with one
    continent to land on; Unlock items open the others. Chests that hold consumables, equipment
    or gil are shuffled, and party members, visions and key items can be added to the pool.
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
        self.starting_party: list[int] = []
        self.starting_continent = ""
        self.final_boss_characters = 0
        self.final_boss_visions = 0
        self.final_boss_fragments = 0

    def generate_early(self) -> None:
        if self.options.goal.value == ffr_options.Goal.option_tablet_shards:
            self.options.include_tablet_shards.value = 1      # the goal's items must be in the pool
        self.starting_continent = self.options.starting_continent.current_key.capitalize()
        picks = [self.options.starting_character_1, self.options.starting_character_2,
                 self.options.starting_character_3, self.options.starting_character_4]
        for pick in picks[:self.options.starting_roster.value]:
            unit = pick.value
            if unit in self.starting_party:      # a repeat becomes someone not chosen yet
                unit = self.random.choice([u for u in ALL_PARTY_MEMBERS if u not in self.starting_party and
                                           u not in [p.value for p in picks[:self.options.starting_roster.value]]])
            self.starting_party.append(unit)
        # Round 58: the final boss lock (Worlds Collide style). It belongs to the story goal: the
        # shard goal never needs the last fight. A count the pool cannot meet is lowered to what
        # it can.
        if self.options.goal.value == ffr_options.Goal.option_final_boss:
            most_characters = len(ALL_PARTY_MEMBERS) if self.options.shuffle_party_members else len(self.starting_party)
            most_visions = len(items.item_name_groups["Visions"]) if self.options.shuffle_visions else 0
            self.final_boss_characters = min(self.options.final_boss_characters.value, most_characters)
            self.final_boss_visions = min(self.options.final_boss_visions.value, most_visions)
            if self.options.include_bosses:
                self.final_boss_fragments = self.options.final_boss_fragments.value

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
            **self.options.as_dict("tablet_shards_required", "include_shinies", "include_crystals",
                                   "include_tablet_shards", "include_bosses",
                                   "start_with_chocobo", "start_with_airship"),
            "goal": self.options.goal.current_key,
            "mod_protocol": MOD_PROTOCOL,
            "open_world": True,
            "starting_party": self.starting_party,
            "final_boss_characters": self.final_boss_characters,
            "final_boss_visions": self.final_boss_visions,
            "final_boss_fragments": self.final_boss_fragments,
            "starting_continent": self.starting_continent,
        }
