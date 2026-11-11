from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, OptionSet, PerGameCommonOptions, Range, Toggle

from .data import CHESTS, CRYSTALS, SHINIES, TABLET_SHINIES


class Goal(Choice):
    """
    What completes your seed.
    tablet_shards: receive the number of Tablet Shards set by tablet_shards_required. This turns
    on include_tablet_shards. Shards you only hold in game do not count: they must come from
    Archipelago.
    story_checkpoint: reach goal_story_checkpoint. EXPERIMENTAL: no seed has reached one yet.
    """
    display_name = "Goal"
    option_tablet_shards = 0
    option_story_checkpoint = 1
    default = 0


class TabletShardsRequired(Range):
    """How many of the 99 Tablet Shards you must receive, when the goal is tablet_shards."""
    display_name = "Tablet Shards Required"
    range_start = 1
    range_end = 99
    default = 50


class GoalStoryCheckpoint(Range):
    """
    The story checkpoint that completes your goal, when the goal is story_checkpoint. A seed
    starts in the open world at story 8000, so the goal must be past that. 8050 is the last
    checkpoint the game's story conditions test. Whether the ending reaches it has not been
    confirmed yet.
    """
    display_name = "Goal Story Checkpoint"
    range_start = 8001
    range_end = 8050
    default = 8050


class StartingContinent(Choice):
    """
    The continent you can land on from the start. Every other continent needs its Unlock item,
    which the logic places where you can reach it. Weigh the options for a random start.
    """
    display_name = "Starting Continent"
    option_grandshelt = 0
    option_lanzelt = 1
    option_kolobos = 2
    option_dirnado = 3
    option_olderion = 4
    option_zoldaad = 5
    option_mysidia = 6
    option_gronoa = 7
    option_pharm = 8
    default = 0


class StartingRoster(Range):
    """
    How many party members you start with, from 1 to 4, all at level 1. The rest are in the item pool when
    shuffle_party_members is on. Weigh the values for a random size, for example {1: 0, 2: 50}.
    """
    display_name = "Starting Roster"
    range_start = 1
    range_end = 4
    default = 2


class StartingCharacter(Choice):
    """A party member at the start. Only the first starting_roster of these four count."""
    option_rain = 1001
    option_lasswell = 1002
    option_fina = 1003
    option_lid = 1004
    option_nichol = 1005
    option_archwitch_fina = 1006
    option_jake = 1007
    option_sakura = 1008

    @classmethod
    def from_text(cls, text: str) -> "StartingCharacter":
        # So a yaml can say "Archwitch Fina" as well as "archwitch_fina".
        return super().from_text(text.strip().replace(" ", "_"))


class StartingCharacter1(StartingCharacter):
    """The first party member, who leads the party. Weigh the options for a random pick."""
    display_name = "Starting Character 1"
    default = 1001


class StartingCharacter2(StartingCharacter):
    """The second party member, if starting_roster is 2 or more. A repeat is swapped for someone else."""
    display_name = "Starting Character 2"
    default = 1002


class StartingCharacter3(StartingCharacter):
    """The third party member, if starting_roster is 3 or more. A repeat is swapped for someone else."""
    display_name = "Starting Character 3"
    default = 1003


class StartingCharacter4(StartingCharacter):
    """The fourth party member, if starting_roster is 4. A repeat is swapped for someone else."""
    display_name = "Starting Character 4"
    default = 1004


class IncludeShinies(Toggle):
    """
    EXPERIMENTAL. Adds the shining spots ("shinies") that hold consumables, equipment or gil as
    locations: 92, all on the world map, read from the game's own files. A shiny that is a
    location gives 1 gil, and the check is the real reward. Shinies elsewhere hold Tablet Shards
    or key items, so they are not locations.
    """
    display_name = "Include Shinies"


class IncludeTabletShards(Toggle):
    """
    EXPERIMENTAL. Makes the 99 shinies that hold a Tablet Shard locations, and puts the 99 Tablet
    Shards in the item pool. Such a shiny gives 1 gil, and the check is the real reward. The
    tablet_shards goal turns this on.
    """
    display_name = "Include Tablet Shards"


class IncludeCrystals(Toggle):
    """
    EXPERIMENTAL. Makes the 16 crystals in the Sanctums of Light locations. Touching one skips the
    summoning scene and the questions, and gives its check, which can be anything in the multiworld.
    """
    display_name = "Include Crystals"


class ExcludedRegions(OptionSet):
    """
    Regions whose chests and shinies may only hold filler from your own game, never anything
    another player needs. Use this for areas you cannot go back to, or do not want to play.
    """
    display_name = "Excluded Regions"
    valid_keys = sorted({loc["region"] for loc in CHESTS + SHINIES + CRYSTALS + TABLET_SHINIES})


class ShufflePartyMembers(DefaultOnToggle):
    """
    Adds every party member you do not start with to the item pool. One received joins at your
    party's average level, in the active party when there is room and the roster otherwise.
    With this off, they never join.
    """
    display_name = "Shuffle Party Members"


class ShuffleVisions(DefaultOnToggle):
    """
    EXPERIMENTAL. Adds all 26 visions to the item pool. There is no logic for them yet.
    """
    display_name = "Shuffle Visions"


class MinimapChestIcons(DefaultOnToggle):
    """
    Shows treasure chests on the mini-map, as icons. The game hides them; this is what the
    TreasureMinimap mod does, built in. Only on this seed's save.
    """
    display_name = "Mini-map Chest Icons"


class ShuffleKeyItems(DefaultOnToggle):
    """
    EXPERIMENTAL. Adds the key items to the item pool, one of each (29): keys, quest items and
    Colosseum proofs. Left out: artifacts, the DLC items, Magicite, Tablet Shards and the items
    with no English name. The story still hands out its own. There is no logic for them yet.
    """
    display_name = "Shuffle Key Items"


@dataclass
class FFResonanceOptions(PerGameCommonOptions):
    goal: Goal
    tablet_shards_required: TabletShardsRequired
    goal_story_checkpoint: GoalStoryCheckpoint
    starting_continent: StartingContinent
    starting_roster: StartingRoster
    starting_character_1: StartingCharacter1
    starting_character_2: StartingCharacter2
    starting_character_3: StartingCharacter3
    starting_character_4: StartingCharacter4
    include_shinies: IncludeShinies
    include_crystals: IncludeCrystals
    include_tablet_shards: IncludeTabletShards
    excluded_regions: ExcludedRegions
    shuffle_party_members: ShufflePartyMembers
    shuffle_visions: ShuffleVisions
    shuffle_key_items: ShuffleKeyItems
    minimap_chest_icons: MinimapChestIcons


option_groups = [
    OptionGroup("Goal", [Goal, TabletShardsRequired, GoalStoryCheckpoint]),
    OptionGroup("Start", [StartingContinent, StartingRoster, StartingCharacter1, StartingCharacter2,
                          StartingCharacter3, StartingCharacter4]),
    OptionGroup("Locations", [IncludeShinies, IncludeTabletShards, IncludeCrystals, ExcludedRegions]),
    OptionGroup("Items", [ShufflePartyMembers, ShuffleVisions, ShuffleKeyItems]),
    OptionGroup("Comfort", [MinimapChestIcons]),
]
