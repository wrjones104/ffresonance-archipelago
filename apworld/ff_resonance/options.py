from dataclasses import dataclass

from Options import DefaultOnToggle, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .data import CHESTS, SHINIES


class GoalStoryCheckpoint(Range):
    """
    The story checkpoint that completes your goal. The game counts story progress from 1020 to
    8050, and the thousands digit is the chapter: 2010 is early in chapter 2.
    8050 is the last checkpoint the game's story conditions test. Whether the ending reaches it
    has not been confirmed yet. For a short test seed, pick something like 1130.
    """
    display_name = "Goal Story Checkpoint"
    range_start = 1020
    range_end = 8050
    default = 8050


class IncludeShinies(Toggle):
    """
    EXPERIMENTAL. Adds the shining spots ("shinies") that hold consumables, equipment or gil as
    locations: 92, all on the world map, read from the game's own files. Shinies elsewhere hold
    Tablet Shards or key items, so they are not locations. Shinies still give their vanilla item
    as well, because the mod cannot replace a shiny's reward yet.
    """
    display_name = "Include Shinies"


class ExcludedRegions(OptionSet):
    """
    Regions whose chests and shinies may only hold filler from your own game, never anything
    another player needs. Use this for areas you cannot go back to, or do not want to play.
    """
    display_name = "Excluded Regions"
    valid_keys = sorted({loc["region"] for loc in CHESTS + SHINIES})


class ShufflePartyMembers(DefaultOnToggle):
    """
    EXPERIMENTAL. Adds the party members who join after the prologue (Fina, Lid, Nichol,
    Archwitch Fina, Jake, Sakura) to the item pool. One received joins the active party when there is room, and the
    roster otherwise. The story still has them join at their usual time, so for now this lets
    them join early. There is no logic for them yet.
    """
    display_name = "Shuffle Party Members"


class ShuffleVisions(DefaultOnToggle):
    """
    EXPERIMENTAL. Adds all 26 visions to the item pool. A vision received before the story gives
    the first ones (in the Town of Mitra) waits, and goes in once the save owns a vision. The
    story still gives its own. There is no logic for them yet.
    """
    display_name = "Shuffle Visions"


class ShuffleKeyItems(DefaultOnToggle):
    """
    EXPERIMENTAL. Adds the key items and artifacts to the item pool, one of each (43): keys,
    quest items, Colosseum proofs and artifacts such as the Transporter. Left out: the DLC items,
    Magicite, Tablet Shards and the items with no English name. The story still hands out its
    own. There is no logic for them yet.
    """
    display_name = "Shuffle Key Items"


@dataclass
class FFResonanceOptions(PerGameCommonOptions):
    goal_story_checkpoint: GoalStoryCheckpoint
    include_shinies: IncludeShinies
    excluded_regions: ExcludedRegions
    shuffle_party_members: ShufflePartyMembers
    shuffle_visions: ShuffleVisions
    shuffle_key_items: ShuffleKeyItems


option_groups = [
    OptionGroup("Goal", [GoalStoryCheckpoint]),
    OptionGroup("Locations", [IncludeShinies, ExcludedRegions]),
    OptionGroup("Items", [ShufflePartyMembers, ShuffleVisions, ShuffleKeyItems]),
]
