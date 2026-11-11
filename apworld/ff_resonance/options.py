from dataclasses import dataclass

from Options import Choice, DefaultOnToggle, OptionGroup, OptionSet, PerGameCommonOptions, Range, Visibility

from .data import BOSSES, CHESTS, CRYSTALS, SHINIES, TABLET_SHINIES


class Goal(Choice):
    """
    What completes your seed.
    final_boss: win the last battle at the top of the Crystal Tower. The way up stays sealed until
    you have the party members, visions and Crystal Fragments that final_boss_characters,
    final_boss_visions and final_boss_fragments ask for.
    tablet_shards: receive the number of Tablet Shards set by tablet_shards_required. Only shards
    received from Archipelago count.
    """
    display_name = "Goal"
    option_tablet_shards = 0
    option_final_boss = 1
    alias_story_checkpoint = 1
    default = 1


FRAGMENT_BOSSES = sum(1 for boss in BOSSES if boss["fragment"])


class TabletShardsRequired(Range):
    """With the tablet_shards goal: how many of the 99 Tablet Shards you must receive."""
    display_name = "Tablet Shards Required"
    range_start = 1
    range_end = 99
    default = 50


class FinalBossCharacters(Range):
    """
    With the final_boss goal: how many party members you need before the way to the top of the
    Crystal Tower opens. Your starting party counts.
    """
    display_name = "Final Boss Characters"
    range_start = 0
    range_end = 8
    default = 6


class FinalBossVisions(Range):
    """With the final_boss goal: how many visions you need before the way to the top of the Crystal Tower opens."""
    display_name = "Final Boss Visions"
    range_start = 0
    range_end = 26
    default = 12


class FinalBossFragments(Range):
    """
    With the final_boss goal: how many Crystal Fragments you need before the way to the top of the
    Crystal Tower opens. A story boss gives one when you beat it.
    """
    display_name = "Final Boss Fragments"
    range_start = 0
    range_end = FRAGMENT_BOSSES
    default = 4


class StartingContinent(Choice):
    """
    The continent you can land on at the start. Each other continent opens when you receive its
    Unlock item.
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
    How many party members you start with, all at level 1. With shuffle_party_members on, the
    others are items you can find.
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
    """The first party member, who leads the party."""
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


# The location options are always on for players; they stay settable for test seeds.
class IncludeShinies(DefaultOnToggle):
    """The shining spots on the world map are locations."""
    display_name = "Include Shinies"
    visibility = Visibility.none


class IncludeTabletShards(DefaultOnToggle):
    """The shinies that hold a Tablet Shard are locations, and the 99 shards are items."""
    display_name = "Include Tablet Shards"
    visibility = Visibility.none


class IncludeCrystals(DefaultOnToggle):
    """The crystals in the Sanctums of Light are locations."""
    display_name = "Include Crystals"
    visibility = Visibility.none


class IncludeBosses(DefaultOnToggle):
    """
    Boss fights are locations. The 15 cave masters and the optional bosses hold shuffled items.
    A story boss holds a Crystal Fragment.
    """
    display_name = "Include Bosses"
    visibility = Visibility.none


class ExcludedRegions(OptionSet):
    """
    Regions where you only find your own filler items, never anything another player needs. Use
    this for areas you do not want to play.
    """
    display_name = "Excluded Regions"
    valid_keys = sorted({loc["region"] for loc in CHESTS + SHINIES + CRYSTALS + TABLET_SHINIES + BOSSES})


class ShufflePartyMembers(DefaultOnToggle):
    """
    The party members you do not start with are items. One you receive joins at your party's
    average level. With this off, only your starting party plays.
    """
    display_name = "Shuffle Party Members"


class ShuffleVisions(DefaultOnToggle):
    """The 26 visions are items. With this off, they are not in the item pool."""
    display_name = "Shuffle Visions"


class ShuffleKeyItems(DefaultOnToggle):
    """
    The key items are items: keys, key cards, quest items and Colosseum proofs. Some doors and
    chests need them.
    """
    display_name = "Shuffle Key Items"


@dataclass
class FFResonanceOptions(PerGameCommonOptions):
    goal: Goal
    tablet_shards_required: TabletShardsRequired
    final_boss_characters: FinalBossCharacters
    final_boss_visions: FinalBossVisions
    final_boss_fragments: FinalBossFragments
    starting_continent: StartingContinent
    starting_roster: StartingRoster
    starting_character_1: StartingCharacter1
    starting_character_2: StartingCharacter2
    starting_character_3: StartingCharacter3
    starting_character_4: StartingCharacter4
    include_shinies: IncludeShinies
    include_crystals: IncludeCrystals
    include_tablet_shards: IncludeTabletShards
    include_bosses: IncludeBosses
    excluded_regions: ExcludedRegions
    shuffle_party_members: ShufflePartyMembers
    shuffle_visions: ShuffleVisions
    shuffle_key_items: ShuffleKeyItems


option_groups = [
    OptionGroup("Goal", [Goal, TabletShardsRequired, FinalBossCharacters, FinalBossVisions, FinalBossFragments]),
    OptionGroup("Start", [StartingContinent, StartingRoster, StartingCharacter1, StartingCharacter2,
                          StartingCharacter3, StartingCharacter4]),
    OptionGroup("Locations", [ExcludedRegions]),
    OptionGroup("Items", [ShufflePartyMembers, ShuffleVisions, ShuffleKeyItems]),
]
