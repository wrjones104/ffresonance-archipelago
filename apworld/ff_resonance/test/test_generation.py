from argparse import Namespace

from BaseClasses import CollectionState, ItemClassification, LocationProgressType, MultiWorld
from worlds import AutoWorld
from worlds.AutoWorld import call_all
from test.general import gen_steps

from ..data import ADAMANTITE_ITEM, AIRSHIP_ITEM, FORGE, BOSSES, CHESTS, FILLER_VALUE, FRAGMENTS, GIFTS, CHOCOBO_ITEM, MAGICITE_ITEMS, NO_ROUTE, POOL_ADDITIONS, RADAR, RADAR_ITEM, RADAR_PARTS, RADAR_PART_CHESTS, CONTINENT_UNLOCKS, CRYSTALS, FRAGMENT_ITEM, ITEMS, NO_BOX, SIDE_QUESTS, TABLET_SHINIES, PROGRESSION, SHINIES, SHUFFLE_ID_LIMIT, UNIT_ITEM_BASE
from ..boss_logic import awakening, has_capability
from ..items import CLASSIFICATIONS, FILLER_CATEGORIES, FRAGMENT_NAME, HEALING_VISIONS, additions, item_name_groups
from ..locations import GOAL_EVENT, LOCATION_KEY_TO_ID, SEPHIROTH, VICTORY
from ..options import ExcludedRegions, ExtraMagicite, FinalBossFragments, Goal, TabletShardsRequired
from . import FFResonanceTestBase

# Round 77: location names are readable now; tests that pick a place by its number use the key.
NAME_OF_KEY = {loc["key"]: loc["name"] for loc in CHESTS + SHINIES + RADAR + TABLET_SHINIES + RADAR_PART_CHESTS}

ARTIFACT_IDS = (30000, 30018)    # DT_ArtifactItemData's rows
LAST_PALACE_CHEST = "chest:2031:24"   # Oblivion Palace's 4-Star Chamber: all 99 shards
PALACE_SHARDS = 99
MARAUDER, LIQUID_THUNDER, ANTLION = 9079, 9083, 9060   # battle groups: a cave master, a story boss, an optional boss
TARTAROSAURUS, BELMODAR, THE_HUNGER = 9112, 9004, 9012   # tier D, and two tier A with no needs
QUEST_LOCATIONS = 28    # round 78: the quest log's 33, less the Mechabo three and two boss quests
QUEST_SECOND_REWARDS = 17   # round 98: 9 quests give a second item or a vision, 8 give gil
# Quest items the game never tests (docs/side_quests.md, section 2): out of the pool.
QUEST_ONLY_ITEMS = (20020, 20023, 20024, 20025, 20026, 20027, 20028, 20029, 20030, 20031, 20032)
CAVE_MASTERS, STORY_BOSSES, OPTIONAL_BOSSES = 15, 21, 4   # round 71: ten more story bosses; round 72: Behemoth out
FRAGMENT_BOSSES = CAVE_MASTERS + STORY_BOSSES + OPTIONAL_BOSSES   # round 97: every boss gives one
# Round 97: the NPC gifts are always locations, but the Magi-tenna's, which goes with the radar.
GIFTS_ON = [g for g in GIFTS if not g.get("radar_part")]
GIFT_EXTRAS = [i for g in GIFTS_ON for i in g.get("extra", [])]
BASE = CHESTS + GIFTS_ON
EARLY_LEVEL, FINA_GROUP_HEAL_LEVEL, MAX_LEVEL = 3, 25, 99   # boss levels: Fina has Cure at 3
RIBBON = 12065001
FORGE_WEAPONS = 8   # round 105: Aileen's forge, one Adamantite a weapon
RIBBONS = 2     # round 104: Ribbon is a rare steal and a story boss's drop, so no location holds one
HEALERS = {"Leah (Vision)", "Ayaka (Vision)", "Warrior of Light (Vision)", "Cecil (Vision)", "Tidus (Vision)",
           "Y'shtola (Vision)", "Lightning (Vision)"}


def chest_location(test, key):
    name = next(c["name"] for c in CHESTS if c["key"] == key)
    return test.multiworld.get_location(name, test.player)


class TestDefault(FFResonanceTestBase):
    def test_chests_are_the_only_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {c["name"] for c in BASE})

    def test_pool_is_the_vanilla_contents_with_progression_in_place_of_filler(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        starters = {UNIT_ITEM_BASE + 1001, UNIT_ITEM_BASE + 1002}
        unlocks = [ap_id for name, ap_id in CONTINENT_UNLOCKS.items() if name != "Grandshelt"]
        extra = [i for i in PROGRESSION["party"] if i not in starters] + PROGRESSION["vision"] + PROGRESSION["key"] + unlocks
        self.assertEqual(len(pool), len(BASE))
        for ap_id in extra:
            self.assertEqual(pool.count(ap_id), 1, ITEMS[ap_id]["name"])
        rest = list(pool)
        added = additions(self.world)
        for ap_id in extra + GIFT_EXTRAS + added:
            rest.remove(ap_id)
        vanilla = [c["vanilla"] for c in BASE]
        for ap_id in rest:
            vanilla.remove(ap_id)            # every other item is some location's vanilla content
        self.assertEqual(len(vanilla), len(extra) + len(GIFT_EXTRAS) + len(added))
        self.assertTrue(all(ITEMS[ap_id]["category"] in FILLER_CATEGORIES for ap_id in vanilla))

    def test_the_pool_has_the_gear_no_location_holds(self) -> None:
        """Round 104: two Ribbons and one of each enemy-only accessory (data/pool_additions.tsv)."""
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(pool.count(RIBBON), RIBBONS)
        for ap_id in set(POOL_ADDITIONS):
            self.assertFalse([c for c in CHESTS if c["vanilla"] == ap_id], ITEMS[ap_id]["name"])
            self.assertEqual(pool.count(ap_id), POOL_ADDITIONS.count(ap_id), ITEMS[ap_id]["name"])
            self.assertEqual(CLASSIFICATIONS[ITEMS[ap_id]["category"]], ItemClassification.useful)

    def test_additions_take_the_cheapest_filler(self) -> None:
        """Progression takes filler at random; the additions then take the cheapest left. So every
        filler item still in the pool is worth at least as much as each one the additions took."""
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        left = [ap_id for ap_id in pool if ap_id in FILLER_VALUE]
        gone = [c["vanilla"] for c in BASE if c["vanilla"] in FILLER_VALUE]
        for ap_id in left:
            gone.remove(ap_id)
        floor = min(FILLER_VALUE[ap_id] for ap_id in left)
        cheap = [ap_id for ap_id in gone if FILLER_VALUE[ap_id] <= floor]
        self.assertGreaterEqual(len(cheap), len(additions(self.world)))

    def test_a_healing_vision_is_placed_early(self) -> None:
        early = self.multiworld.local_early_items[self.player]
        self.assertEqual(len(early), 1)
        self.assertIn(next(iter(early)), HEALERS)
        self.assertEqual({ITEMS[ap_id]["name"] for ap_id in HEALING_VISIONS}, HEALERS)

    def test_progression_items_are_progression(self) -> None:
        for item in self.multiworld.itempool:
            if item.player == self.player and ITEMS[item.code]["category"] in ("party", "vision", "key", "continent", "magicite"):
                self.assertTrue(item.advancement, item.name)

    def test_goal_is_reachable(self) -> None:
        self.assertBeatable(False)
        self.collect_all_but(())
        self.assertBeatable(True)

    def test_the_start_is_one_continent(self) -> None:
        state = self.multiworld.state
        self.assertTrue(state.has("Grandshelt Unlock", self.player), "precollected")
        self.assertTrue(state.can_reach_region("Grandshelt", self.player))
        self.assertFalse(state.can_reach_region("Pharm", self.player))
        self.assertFalse(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(state))
        self.assertNotIn("Grandshelt Unlock", [i.name for i in self.multiworld.itempool if i.player == self.player])

    def test_each_unlock_opens_its_continent(self) -> None:
        self.collect_by_name(["Pharm Unlock"])
        self.assertTrue(self.multiworld.state.can_reach_region("Pharm", self.player))
        self.assertTrue(chest_location(self, "chest:3260:2").can_reach(self.multiworld.state), "Mt. Reizan, below Ignis")
        self.assertFalse(self.multiworld.state.can_reach_region("Gronoa", self.player))

    def test_places_with_no_route_are_not_locations(self) -> None:
        """Round 72: the burning Grandshelt Castle (3020) is the prologue's: its chests are not
        locations. The Imperial Residences (2113) are reached by the Zoldaad streetcar. Round 73:
        the attacked Old Town of Olderion (3090) is chapter 3's."""
        self.assertTrue(NO_ROUTE and all(key.startswith(("chest:3020:", "chest:3090:")) or key == "chest:2012:1"
                                         for key in NO_ROUTE))
        self.assertNotIn("chest:2012:1", LOCATION_KEY_TO_ID, "the castle room the user could not find (round 72)")
        for chest in range(3):
            self.assertNotIn(f"chest:3090:{chest}", LOCATION_KEY_TO_ID, "Old Town, Olderion (round 73)")
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("Grandshelt Castle Chest 8", names)
        self.assertNotIn("Old Town, Olderion Chest 1", names)
        residences = self.multiworld.get_location("Zoldaad - Residential District - West House Chest", self.player)
        self.assertEqual(residences.progress_type, LocationProgressType.DEFAULT)
        self.assertEqual(residences.parent_region.name, "Zoldaad")
        # Round 44 walked into the Earth Shrine's inner part and opened its chests.
        self.assertNotEqual(self.multiworld.get_location("Grandshelt - Earth Shrine - Interior Central-East Alcove Chest", self.player).progress_type,
                            LocationProgressType.EXCLUDED)

    def test_fina_psyche_is_behind_tellus(self) -> None:
        """Round 71: Fina's Psyche is reached past Tellus (Tower of Mysidia, tier B): a third party
        member and two continents, on top of Mysidia. Round 73: and Wind, a healer, and a group heal
        or Earth resistance. Fina heals, Jake has Wind."""
        chest = self.multiworld.get_location("Mysidia - Fina's Psyche - West Camp Tent NE Corner Chest", self.player)
        self.assertNotEqual(chest.progress_type, LocationProgressType.EXCLUDED)
        # Round 74: Tower of Mysidia Chest 3, on the top floor, is past Tellus too (a tester's seed).
        top = chest_location(self, "chest:3200:2")
        self.collect_by_name(["Mysidia Unlock", "Fina"])
        self.assertTrue(chest_location(self, "chest:3200:0").can_reach(self.multiworld.state), "the tower's lower floors")
        self.assertFalse(chest.can_reach(self.multiworld.state), "no Wind")
        self.assertFalse(top.can_reach(self.multiworld.state), "no Wind")
        self.collect_by_name(["Jake"])
        self.assertTrue(chest.can_reach(self.multiworld.state))
        self.assertTrue(top.can_reach(self.multiworld.state))

    def test_gronoa_plateau_is_behind_lux(self) -> None:
        """Round 74 (a tester): Lux on the Rugged Mountain Path holds Gronoa's south-west plateau
        (Duggle, Gronoa Shrine, Sanctissimus Shrine), and the airship cannot land there. Lux is
        tier C: four party members, four continents, a group heal or a revive. She acts twice a
        turn, so one member more."""
        duggle = chest_location(self, "chest:2160:0")
        self.collect_by_name(["Gronoa Unlock"])
        self.assertTrue(chest_location(self, "chest:2150:0").can_reach(self.multiworld.state), "Gaberada's side")
        self.assertTrue(chest_location(self, "chest:3230:0").can_reach(self.multiworld.state), "the path before Lux")
        self.assertFalse(duggle.can_reach(self.multiworld.state), "the airship is no way past Lux")
        self.collect_by_name(["Pharm Unlock", "Mysidia Unlock", "Fina", "Nichol"])
        self.assertFalse(duggle.can_reach(self.multiworld.state), "four members")
        self.collect_by_name(["Jake"])
        self.assertTrue(duggle.can_reach(self.multiworld.state))

    def test_pharm_plateau_is_behind_ignis(self) -> None:
        """Round 74: Ignis at the top of Mt. Reizan (tier C) holds Lake Ryusei, the Forest Path and
        the Wandering Lands. The mountain's own chests are below him."""
        forest = chest_location(self, "chest:3271:0")
        self.collect_by_name(["Pharm Unlock"])
        self.assertTrue(chest_location(self, "chest:3260:2").can_reach(self.multiworld.state))
        self.assertFalse(forest.can_reach(self.multiworld.state))
        self.collect_by_name(["Gronoa Unlock", "Mysidia Unlock", "Fina", "Nichol"])
        self.assertTrue(forest.can_reach(self.multiworld.state))

    def test_sanctissimus_is_behind_its_first_three_bosses(self) -> None:
        """Round 72: Sanctissimus Shrine's chests are past Archaeoaevis, Dad Bomb and Test Rider
        (tier C): four party members and four continents, on top of Gronoa. Round 73: and a group
        heal or a revive, which Fina has from level 25. Round 74: Dad Bomb, Test Rider and Lux (on
        the way) act twice a turn, so five members."""
        chest = self.multiworld.get_location("Gronoa - Sanctissimus Shrine - Upper East Hall NW Corner Chest", self.player)
        self.collect_by_name(["Gronoa Unlock", "Pharm Unlock", "Mysidia Unlock"])
        self.collect_by_name(["Nichol", "Lid", "Jake"])
        self.assertFalse(chest.can_reach(self.multiworld.state), "no group heal or revive")
        self.remove_by_name(["Lid"])
        self.collect_by_name(["Fina"])
        self.assertTrue(chest.can_reach(self.multiworld.state))
        self.remove_by_name(["Nichol"])
        self.assertFalse(chest.can_reach(self.multiworld.state), "four members are not enough")

    def test_zoldaad_dungeon_needs_its_key(self) -> None:
        chest = self.multiworld.get_location("Zoldaad - Dungeon - East Wing West Cell Chest", self.player)
        self.collect_by_name(["Zoldaad Unlock"])
        self.assertFalse(chest.can_reach(self.multiworld.state))
        self.collect_by_name(["Dungeon Key"])
        self.assertTrue(chest.can_reach(self.multiworld.state))

    def test_abandoned_cabin_needs_its_key(self) -> None:
        # Round 106 (the user): the cabin's door says it is locked without the Cabin Key.
        chest = self.multiworld.get_location("Pharm - Abandoned Cabin - NW Corner Chest", self.player)
        self.collect_by_name(["Pharm Unlock"])
        self.assertFalse(chest.can_reach(self.multiworld.state))
        self.collect_by_name(["Cabin Key"])
        self.assertTrue(chest.can_reach(self.multiworld.state))

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal"], "final_boss")
        self.assertEqual(slot_data["mod_protocol"], 2)
        self.assertEqual(slot_data["world_build"], "dev", "round 74: a world run from its folder")
        self.assertEqual(slot_data["starting_party"], [1001, 1002])
        self.assertEqual(slot_data["starting_continent"], "Grandshelt")
        self.assertIs(slot_data["open_world"], True)
        self.assertEqual(slot_data["start_with_chocobo"], 1)
        self.assertEqual(slot_data["start_with_airship"], 1)

    def test_the_chocobo_is_not_in_the_pool(self) -> None:
        self.assertNotIn(CHOCOBO_ITEM, [i.code for i in self.multiworld.itempool if i.player == self.player])


class TestChocoboItem(FFResonanceTestBase):
    options = {"start_with_chocobo": False}

    def test_the_chocobo_takes_a_filler_place(self) -> None:
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(len(pool), len(BASE))
        chocobos = [i for i in pool if i.code == CHOCOBO_ITEM]
        self.assertEqual(len(chocobos), 1)
        self.assertTrue(chocobos[0].advancement)
        self.assertEqual(ITEMS[CHOCOBO_ITEM]["game_id"], 30002, "the game's Choboco Saddle")

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["start_with_chocobo"], 0)


class TestAirshipItem(FFResonanceTestBase):
    """Round 69: on foot from Grandshelt. The bridges and the ferry need only the far side's unlock."""
    options = {"start_with_airship": False, "include_crystals": True}

    def test_the_airship_is_a_progression_item(self) -> None:
        airships = [i for i in self.multiworld.itempool if i.player == self.player and i.code == AIRSHIP_ITEM]
        self.assertEqual(len(airships), 1)
        self.assertTrue(airships[0].advancement)
        self.assertEqual(self.world.fill_slot_data()["start_with_airship"], 0)

    def test_walk_and_sail_without_the_airship(self) -> None:
        state = self.multiworld.state
        self.collect_by_name(["Lanzelt Unlock", "Kolobos Unlock", "Dirnado Unlock", "Mysidia Unlock"])
        for continent in ("Grandshelt", "Lanzelt", "Kolobos", "Dirnado"):
            self.assertTrue(state.can_reach_region(continent, self.player), continent)
        self.assertFalse(state.can_reach_region("Mysidia", self.player), "Mysidia has no port and no bridge")
        self.assertFalse(state.can_reach_region("Olderion", self.player), "no Olderion Unlock")
        self.collect_by_name(["Airship"])
        self.assertTrue(state.can_reach_region("Mysidia", self.player))

    def test_a_bridge_needs_the_far_side(self) -> None:
        self.collect_by_name(["Kolobos Unlock"])
        self.assertFalse(self.multiworld.state.can_reach_region("Kolobos", self.player), "Lanzelt is between")

    def test_an_airship_only_place_needs_it(self) -> None:
        """Round 71: the Sanctum of Light (Clive) in Grandshelt is reached only from the air."""
        self.collect_by_name(["Grandshelt Unlock", "Lanzelt Unlock"])
        self.assertTrue(self.multiworld.state.can_reach_region("Grandshelt", self.player))
        sanctum = self.multiworld.get_location("Sanctum of Light (Clive)", self.player)
        self.assertFalse(sanctum.can_reach(self.multiworld.state))
        self.collect_by_name(["Airship"])
        self.assertTrue(sanctum.can_reach(self.multiworld.state))

    def test_the_tower_needs_the_airship(self) -> None:
        self.collect_all_but(["Airship"])
        self.assertFalse(self.multiworld.state.can_reach_region("Crystal Tower", self.player))
        self.assertFalse(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(self.multiworld.state))

    def test_the_tower_third_section_is_past_behemoth(self) -> None:
        """Round 73 (the user): the tower's first two sections need only the Airship. Chests 3 and 6
        to 9 are past Behemoth, which needs a tier B party with Wind or Light."""
        self.collect_by_name(["Airship"])
        state = self.multiworld.state
        for n in (1, 2, 4, 5, 10, 11):
            self.assertTrue(self.multiworld.get_location(NAME_OF_KEY[f"chest:3280:{n - 1}"], self.player).can_reach(state), n)
        third = [self.multiworld.get_location(NAME_OF_KEY[f"chest:3280:{n - 1}"], self.player) for n in (3, 6, 7, 8, 9)]
        self.assertFalse(any(chest.can_reach(state) for chest in third))
        self.assertFalse(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(state))
        self.collect_all_but([])
        self.assertTrue(all(chest.can_reach(self.multiworld.state) for chest in third))


class TestAirshipOnlyShinies(FFResonanceTestBase):
    options = {"start_with_airship": False, "include_shinies": True}

    def test_olderion_landing_spots_need_the_airship(self) -> None:
        """Round 73 (the user): four world map shinies in Olderion are reached only from the air."""
        self.collect_by_name(["Lanzelt Unlock", "Olderion Unlock"])
        self.assertTrue(self.multiworld.state.can_reach_region("Olderion", self.player), "by the bridge and the ferry")
        shinies = [self.multiworld.get_location(NAME_OF_KEY[f"shiny:1000:{n}"], self.player) for n in (36, 39, 68, 145)]
        self.assertFalse(any(shiny.can_reach(self.multiworld.state) for shiny in shinies))
        self.collect_by_name(["Airship"])
        self.assertTrue(all(shiny.can_reach(self.multiworld.state) for shiny in shinies))


class TestAirshipItemFromMysidia(FFResonanceTestBase):
    """Round 69: a start with no port and no bridge still generates: the Airship is found there."""
    options = {"start_with_airship": False, "starting_continent": "mysidia"}

    def test_only_mysidia_at_first(self) -> None:
        state = self.multiworld.state
        self.assertTrue(state.can_reach_region("Mysidia", self.player))
        self.collect_by_name(["Lanzelt Unlock"])
        self.assertFalse(state.can_reach_region("Lanzelt", self.player))


class TestAirshipItemRealDefaults(FFResonanceTestBase, real_defaults=True):
    """Round 69: the full pool (shinies, crystals, bosses) fills with the airship off, from Pharm."""
    options = {"start_with_airship": False, "starting_continent": "pharm"}

    def test_the_airship_is_in_the_pool(self) -> None:
        self.assertIn(AIRSHIP_ITEM, [i.code for i in self.multiworld.itempool if i.player == self.player])


class TestDirnadoOnFoot(FFResonanceTestBase, real_defaults=True):
    """Round 73: the user's seed. On foot from Dilmagia, Liquid Thunder (tier B) holds the rest of
    Dirnado: three party members and a second continent, or the Airship to fly over it."""
    options = {"start_with_airship": False, "starting_continent": "dirnado", "starting_roster": 2,
               "starting_character_1": "Lasswell", "starting_character_2": "Archwitch Fina", "shuffle_visions": True,
               "include_side_quests": True}
    # Round 97 (the user): both end in the Dwarven Forge, past Liquid Thunder, and were in logic at once.
    FORGE_QUESTS = ("Quest: Lyrical Riddles", "Quest: Elven Maven")

    def reachable(self, name: str) -> bool:
        return self.multiworld.get_location(name, self.player).can_reach(self.multiworld.state)

    def test_forge_quests_wait_for_liquid_thunder(self) -> None:
        for name in self.FORGE_QUESTS:
            self.assertFalse(self.reachable(name), name)
        self.collect_by_name(["Lid", "Lanzelt Unlock", "Leah (Vision)"])
        for name in self.FORGE_QUESTS:
            self.assertTrue(self.reachable(name), name)

    def test_forge_quests_by_airship(self) -> None:
        self.collect_by_name(["Airship"])
        for name in self.FORGE_QUESTS:
            self.assertTrue(self.reachable(name), name)

    def test_only_dilmagia_at_first(self) -> None:
        self.assertTrue(self.reachable("Dirnado - Dilmagia - NE Branch Corridor Chest"))
        self.assertTrue(self.reachable("Dirnado - Shipyard - Upper East Dock Tip Chest"))
        self.assertTrue(self.reachable("Dirnado - Mt. Thunderclap - Far-East Loop Bend Tablet Shard"))
        for name in ("Mt. Thunderclap: Liquid Thunder", "Dirnado - Mt. Thunderclap - Lower-Central Alcove Chest", "Dirnado - Dwarven Forge - SE Corridor Alcove Chest",
                     "Dwarven Forge: Mom Bomb", "Dirnado - World Map - Shiny on Rocky Cove SE of Sanctum of Onion Knight", "Sanctum of Light (Zidane)"):
            self.assertFalse(self.reachable(name), name)

    def test_liquid_thunder_opens_the_rest(self) -> None:
        """Round 73: it needs Earth and a healer too. Lid's Mechabo Kick is Earth from level 1."""
        self.collect_by_name(["Lid"])
        self.assertFalse(self.reachable("Mt. Thunderclap: Liquid Thunder"), "a second continent too")
        self.collect_by_name(["Lanzelt Unlock"])
        self.assertFalse(self.reachable("Mt. Thunderclap: Liquid Thunder"), "no healer")
        self.collect_by_name(["Leah (Vision)"])
        for name in ("Mt. Thunderclap: Liquid Thunder", "Dirnado - Dwarven Forge - SE Corridor Alcove Chest", "Dirnado - Wind Shrine - Upper-West Corridor Chest",
                     "Sanctum of Light (Zidane)"):
            self.assertTrue(self.reachable(name), name)

    def test_the_airship_flies_over_it(self) -> None:
        self.collect_by_name(["Airship"])
        self.assertFalse(self.reachable("Mt. Thunderclap: Liquid Thunder"))
        self.assertTrue(self.reachable("Dirnado - Dwarven Forge - SE Corridor Alcove Chest"))
        self.assertTrue(self.reachable("Dirnado - Wind Shrine - Upper-West Corridor Chest"))


DRAGONS_MAW_CHESTS = [f"chest:3010:{n}" for n in range(7)]
DRAGONS_MAW_NORTH_SHINY = "shiny:1000:149"


class TestDragonsMaw(FFResonanceTestBase):
    """Round 78 (the user): every chest in Dragon's Maw is past Intangir, airship or not. The seed
    started with the airship, which put all of Dragon's Maw in logic while Intangir was not."""
    options = {"start_with_airship": True, "starting_continent": "pharm", "include_shinies": True}

    def test_dragons_maw_needs_intangir(self) -> None:
        state = self.multiworld.state
        chests = [chest_location(self, key) for key in DRAGONS_MAW_CHESTS]
        north = self.multiworld.get_location(NAME_OF_KEY[DRAGONS_MAW_NORTH_SHINY], self.player)
        self.assertTrue(north.can_reach(state), "the airship lands by the north door")
        self.assertEqual([c.name for c in chests if c.can_reach(state)], [], "not before Intangir")
        self.collect_all_but([])
        self.assertTrue(all(c.can_reach(state) for c in chests))


class TestDragonsMawOnFoot(FFResonanceTestBase):
    """Round 74 (a tester): on foot, Intangir (tier D) holds the world map past Dragon's Maw's north
    door. Tier D wants the Airship, and the Airship lands on the north side, so on foot that shiny
    needs the Airship."""
    options = {"start_with_airship": False, "starting_continent": "pharm", "include_shinies": True}

    def test_the_north_side_needs_the_airship(self) -> None:
        north = self.multiworld.get_location(NAME_OF_KEY[DRAGONS_MAW_NORTH_SHINY], self.player)
        self.assertFalse(north.can_reach(self.multiworld.state))
        self.collect_by_name(["Airship"])
        self.assertTrue(north.can_reach(self.multiworld.state))
        self.assertFalse(chest_location(self, "chest:3010:0").can_reach(self.multiworld.state), "Intangir")


class TestUnshuffledVisions(FFResonanceTestBase):
    """Round 71 (the user's change): with visions not shuffled, Tronn and Leah come at the start and
    each sanctum holds its own vision."""
    options = {"shuffle_visions": False}

    def test_starters_are_given(self) -> None:
        state = self.multiworld.state
        self.assertTrue(state.has("Tronn (Vision)", self.player) and state.has("Leah (Vision)", self.player))

    def test_each_sanctum_holds_its_own_vision(self) -> None:
        for crystal in CRYSTALS:
            location = self.multiworld.get_location(crystal["name"], self.player)
            self.assertEqual(location.item.code, crystal["vision"], crystal["name"])

    def test_no_vision_in_the_pool(self) -> None:
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertFalse([i.name for i in pool if ITEMS[i.code]["category"] == "vision"])

    def test_no_early_vision(self) -> None:
        self.assertFalse(self.multiworld.local_early_items[self.player])


class TestTrackerRebuild(FFResonanceTestBase):
    """Round 72: Universal Tracker builds the world again from the slot data alone. A seed that
    started on foot in Mysidia showed 0 locations in logic: the tracker had rolled its own start."""
    options = {"start_with_airship": False, "starting_continent": "mysidia", "starting_character_1": "jake",
               "starting_character_2": "nichol", "shuffle_key_items": False}

    def rebuilt(self):
        slot_data = self.world.interpret_slot_data(dict(self.world.fill_slot_data()))
        multiworld = MultiWorld(1)
        multiworld.game[1] = self.game
        multiworld.player_name = {1: "Tracker"}
        multiworld.set_seed(None)
        args = Namespace()
        for name, option in AutoWorld.AutoWorldRegister.world_types[self.game].options_dataclass.type_hints.items():
            setattr(args, name, {1: option.from_any(option.default)})     # a tracker with no yaml
        multiworld.set_options(args)
        multiworld.re_gen_passthrough = {self.game: slot_data}
        multiworld.state = CollectionState(multiworld)
        for step in gen_steps:
            if step in ("generate_output",):
                continue
            call_all(multiworld, step)
        return multiworld

    def test_the_rebuild_is_the_same_world(self) -> None:
        multiworld = self.rebuilt()
        world = multiworld.worlds[1]
        self.assertEqual(world.starting_continent, "Mysidia")
        self.assertEqual(world.starting_party, self.world.starting_party)
        self.assertFalse(world.options.start_with_airship)
        self.assertFalse(world.options.shuffle_key_items)
        state = CollectionState(multiworld)
        state.collect(world.create_item("Mysidia Unlock"), True)
        in_logic = [loc for loc in multiworld.get_locations(1) if loc.address and loc.can_reach(state)]
        self.assertTrue(in_logic, "the start's locations are in logic")
        self.assertTrue(all(loc.parent_region.name == "Mysidia" for loc in in_logic))


class TestRadarTreasures(FFResonanceTestBase):
    """Round 72: the airship radar's 13 treasures are locations, opened by three Progressive Radars
    (1 to 5, 6 to 9, 10 to 13) in place of the radar's three parts."""
    options = {"include_radar_treasures": True, "start_with_airship": False}

    def test_three_radars_in_place_of_the_parts(self) -> None:
        pool = [i.code for i in self.multiworld.itempool if i.player == self.player]
        self.assertEqual(pool.count(RADAR_ITEM), 3)
        self.assertFalse(set(RADAR_PARTS) & set(pool))
        self.assertEqual(len(RADAR), 13)

    def test_the_resonance_stone_chest_is_a_location(self) -> None:
        # Round 75: Mt. Reizan's chest kept its vanilla Resonance Stone, so a tester found the
        # radar part the Progressive Radars replace. The mod empties it; here it is a location.
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertIn("Pharm - Mt. Reizan - South Base Corner Chest", names)
        self.assertEqual([c["key"] for c in RADAR_PART_CHESTS], ["chest:3260:3"])

    def test_tiers_and_the_airship(self) -> None:
        state = self.multiworld.state
        first, sixth, last = (self.multiworld.get_location(NAME_OF_KEY[f"radar:{n}"], self.player) for n in (1, 6, 13))
        radars = self.get_items_by_name("Progressive Radar")
        self.collect(radars[0])
        self.assertFalse(first.can_reach(state), "they lie at sea: the Airship first")
        self.collect_by_name(["Airship"])
        self.assertTrue(first.can_reach(state))
        self.assertFalse(sixth.can_reach(state))
        self.collect(radars[1])
        self.assertTrue(sixth.can_reach(state))
        self.assertFalse(last.can_reach(state))
        self.collect(radars[2])
        self.assertTrue(last.can_reach(state))

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["include_radar_treasures"], 1)


class TestSideQuests(FFResonanceTestBase):
    """Round 78: the rewards of 28 quests from the game's quest log are locations. A quest needs
    the continents its steps are on, and the Airship for steps aboard it when the player starts
    on foot (docs/side_quests.md)."""
    options = {"include_side_quests": True, "start_with_airship": False, "starting_continent": "grandshelt"}

    def quest(self, name):
        return self.multiworld.get_location(f"Quest: {name}", self.player)

    def test_quests_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertEqual(len(SIDE_QUESTS), QUEST_LOCATIONS + QUEST_SECOND_REWARDS)
        self.assertTrue({q["name"] for q in SIDE_QUESTS} <= names)
        self.assertIn('Quest: "Reunion"', names)
        self.assertIn('Quest: "Reunion" - Second Reward', names)

    def test_second_rewards_go_to_the_pool(self) -> None:
        """Round 98 (the user): a quest's second reward is a location of its own, with the same
        logic as the quest. Its item or gil goes into the pool; a vision is there already."""
        by_key = {q["key"]: q for q in SIDE_QUESTS}
        secrets, riddles = by_key["quest2:16"], by_key["quest2:18"]
        self.assertEqual(ITEMS[secrets["vanilla"]]["name"], "Magicite Shard")
        self.assertEqual(ITEMS[riddles["vanilla"]]["name"], "800 Gil")
        self.assertIn(riddles["vanilla"], self.world.vanilla_items, "filler: a progression item may take its place")
        amelia = by_key["quest2:22"]
        self.assertIsNone(amelia["vanilla"])
        self.assertNotIn("vision", by_key["quest:22"], "the quest's own location holds the Magicite")
        for second in (q for q in SIDE_QUESTS if q["key"].startswith("quest2:")):
            first = by_key["quest:" + second["key"].split(":")[1]]
            self.assertEqual((second["steps"], second.get("past_boss"), second["after"]),
                             (first["steps"], first.get("past_boss"), first["after"]), second["name"])

    def test_forger_of_wills_needs_all_three_continents(self) -> None:
        # Three NPCs, in Dilmagia, the Rebel Hideout and the Village of Kol, each move the counter
        # on by one, in any order: all three are needed, not any one.
        state = self.multiworld.state
        self.collect_by_name(["Airship", "Dirnado Unlock", "Lanzelt Unlock"])
        self.assertFalse(self.quest("Forger of Wills").can_reach(state))
        self.collect_by_name(["Zoldaad Unlock"])
        self.assertTrue(self.quest("Forger of Wills").can_reach(state))

    def test_a_step_aboard_needs_the_airship(self) -> None:
        # Last Respite is in Grandshelt, the start, but its last step is on the airship's deck.
        state = self.multiworld.state
        self.assertFalse(self.quest("Last Respite").can_reach(state))
        self.collect_by_name(["Airship"])
        self.assertTrue(self.quest("Last Respite").can_reach(state))

    def test_a_later_quest_needs_the_one_before(self) -> None:
        errand = next(q for q in SIDE_QUESTS if q["key"] == "quest:22")
        token = next(q for q in SIDE_QUESTS if q["key"] == "quest:6")
        self.assertEqual(errand["after"], ["quest:6"])
        self.assertTrue(set(token["steps"]) <= set(errand["steps"]))

    def test_rewards_go_to_the_pool_and_quest_items_do_not(self) -> None:
        pool = [i.code for i in self.multiworld.itempool if i.player == self.player]
        mercy = next(q for q in SIDE_QUESTS if q["key"] == "quest:20")
        self.assertIn(mercy["vanilla"], pool, "Iwakirimaru")
        self.assertIn(20021001, pool, "the Throne Room Key: its door tests it")
        for game_id in QUEST_ONLY_ITEMS:
            self.assertNotIn(game_id * 1000 + 1, pool, ITEMS[game_id * 1000 + 1]["name"])
            self.assertNotIn(game_id * 1000 + 1, PROGRESSION["key"])

    def test_goal_is_reachable(self) -> None:
        self.collect_all_but(())
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["include_side_quests"], 1)


class TestSideQuestsUnshuffledVisions(FFResonanceTestBase):
    """Round 78: with visions not shuffled, a vision quest holds its own vision, as a sanctum does."""
    options = {"include_side_quests": True, "shuffle_visions": False}

    def test_a_vision_quest_holds_its_vision(self) -> None:
        """Round 98: on its second reward's location; the quest's own holds a shuffled item."""
        visions = [q for q in SIDE_QUESTS if "vision" in q]
        self.assertTrue(visions and all(q["key"].startswith("quest2:") for q in visions))
        for quest in visions:
            self.assertEqual(self.multiworld.get_location(quest["name"], self.player).item.code, quest["vision"])

    def test_no_vision_in_the_pool(self) -> None:
        pool = [i for i in self.multiworld.itempool if i.player == self.player]
        self.assertFalse([i.name for i in pool if ITEMS[i.code]["category"] == "vision"])


class TestSideQuestsRealDefaults(FFResonanceTestBase, real_defaults=True):
    """Round 78: with every other default on (bosses, shinies, radar), the seed still fills."""
    options = {"include_side_quests": True, "start_with_airship": False}

    def test_every_quest_is_a_location(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertTrue({q["name"] for q in SIDE_QUESTS} <= names)


class TestNoSideQuests(FFResonanceTestBase):
    def test_no_quest_is_a_location(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse({q["name"] for q in SIDE_QUESTS} & names)


class TestRadarPartChestWithoutTreasures(FFResonanceTestBase):

    def test_no_radar_no_chest(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertNotIn("Pharm - Mt. Reizan - South Base Corner Chest", names)


class TestShinies(FFResonanceTestBase):
    options = {"include_shinies": True}

    def test_shinies_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in BASE + SHINIES})


class TestTabletShards(FFResonanceTestBase):
    options = {"include_tablet_shards": True}

    def test_shards_are_locations_and_items(self) -> None:
        self.assertEqual(len(TABLET_SHINIES), 99)
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in BASE + TABLET_SHINIES})
        shards = [i for i in self.multiworld.itempool if i.player == self.player and i.name == "Tablet Shard"]
        self.assertEqual(len(shards), len(TABLET_SHINIES))

    def test_the_palace_chests_need_their_shards(self) -> None:
        last = chest_location(self, LAST_PALACE_CHEST)
        shards = [i for i in self.multiworld.itempool if i.player == self.player and i.name == "Tablet Shard"]
        self.assertTrue(all(i.advancement for i in shards), "the last chest counts every shard")
        self.collect_all_but(["Tablet Shard"])
        self.assertFalse(last.can_reach(self.multiworld.state))
        self.collect(shards[:PALACE_SHARDS - 1])
        self.assertFalse(last.can_reach(self.multiworld.state))
        self.collect(shards[PALACE_SHARDS - 1:])
        self.assertTrue(last.can_reach(self.multiworld.state))
        first = chest_location(self, "chest:2031:0")
        self.assertEqual(first.progress_type, LocationProgressType.DEFAULT)

    def test_shards_made_like_the_tracker_makes_them_count(self) -> None:
        # Round 75: Universal Tracker makes each received item with create_item. Shards made that
        # way were "useful", so it counted none, and Oblivion Palace left its logic.
        last = chest_location(self, LAST_PALACE_CHEST)
        self.collect_all_but(["Tablet Shard"])
        for _ in range(PALACE_SHARDS):
            self.collect(self.world.create_item("Tablet Shard"))
        self.assertTrue(last.can_reach(self.multiworld.state))


class TestCrystals(FFResonanceTestBase):
    options = {"include_crystals": True}

    def test_crystals_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in BASE + CRYSTALS})

    def test_there_is_an_item_for_each(self) -> None:
        pool = [item for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(len(pool), len(BASE) + len(CRYSTALS))

    def test_a_sanctum_is_on_the_continent_of_its_door(self) -> None:
        # Round 63: the Warrior of Light's and Cloud's doors are on Lanzelt, Terra's on Kolobos
        # (the airship landing points had said Kolobos, Dirnado and Lanzelt)
        area = {c["key"]: c["area"] for c in CRYSTALS}
        self.assertEqual((area["crystal:10203"], area["crystal:10208"], area["crystal:10201"]),
                         ("Lanzelt", "Lanzelt", "Kolobos"))


class TestBosses(FFResonanceTestBase):
    options = {"include_bosses": True, "final_boss_characters": 2, "final_boss_visions": 0, "final_boss_fragments": 3}

    def boss_location(self, group):
        name = next(b["name"] for b in BOSSES if b["key"] == f"boss:{group}")
        return self.multiworld.get_location(name, self.player)

    def test_bosses_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in BASE + BOSSES + FRAGMENTS})

    def test_every_boss_holds_a_shuffled_item_and_gives_a_fragment(self) -> None:
        """Round 97 (the user): story bosses, cave masters and optional bosses alike."""
        for boss in BOSSES:
            self.assertIsNone(self.multiworld.get_location(boss["name"], self.player).item, boss["name"])
        for fragment in FRAGMENTS:
            item = self.multiworld.get_location(fragment["name"], self.player).item
            self.assertEqual((item.name, item.code, item.advancement), (FRAGMENT_NAME, FRAGMENT_ITEM, True), fragment["name"])
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertNotIn(FRAGMENT_ITEM, pool)
        self.assertEqual(len(pool), len(BASE) + len(BOSSES))

    def test_a_fragment_needs_what_its_boss_needs(self) -> None:
        boss, fragment = self.boss_location(TARTAROSAURUS), self.multiworld.get_location(
            next(f["name"] for f in FRAGMENTS if f["boss"] == TARTAROSAURUS), self.player)
        self.collect_by_name(["Pharm Unlock", "Lanzelt Unlock", "Kolobos Unlock", "Dirnado Unlock", "Olderion Unlock"])
        self.collect_by_name(["Fina", "Lid", "Nichol"])
        self.assertTrue(boss.can_reach(self.multiworld.state) and fragment.can_reach(self.multiworld.state))
        self.remove_by_name(["Nichol"])
        self.assertFalse(boss.can_reach(self.multiworld.state) or fragment.can_reach(self.multiworld.state))

    def test_a_cave_master_gives_its_magicite_to_the_pool(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        for name in ("Magicite Shard", "Magicite", "Magicite Cryst"):
            ap_id = next(i for i, info in ITEMS.items() if info["name"] == name)
            from_chests = sum(1 for c in CHESTS if c["vanilla"] == ap_id)
            from_caves = sum(1 for b in BOSSES if b["vanilla"] == ap_id)
            self.assertGreater(from_caves, 0, name)
            extra = additions(self.world).count(ap_id)
            self.assertEqual(pool.count(ap_id), from_chests + from_caves + extra, name)

    def test_the_goal_needs_the_fragments(self) -> None:
        goal = self.multiworld.get_location(GOAL_EVENT, self.player)
        fragments = [self.multiworld.get_location(f["name"], self.player).item for f in FRAGMENTS]
        # No sweep: a sweep would take the fragments from the bosses it can reach.
        state = self.multiworld.state
        for item in self.multiworld.get_items():
            if item.name not in (VICTORY, FRAGMENT_NAME):
                state.collect(item, prevent_sweep=True)
        self.assertFalse(goal.can_reach(state))
        for fragment in fragments[:2]:
            state.collect(fragment, prevent_sweep=True)
        self.assertFalse(goal.can_reach(state))
        state.collect(fragments[2], prevent_sweep=True)
        self.assertTrue(goal.can_reach(state))

    def test_cave_masters_and_optional_bosses_are_priority_but_not_sephiroth(self) -> None:
        for boss in BOSSES:
            plain = boss["kind"] == "story" or boss["key"] == SEPHIROTH
            wanted = LocationProgressType.DEFAULT if plain else LocationProgressType.PRIORITY
            self.assertEqual(self.multiworld.get_location(boss["name"], self.player).progress_type, wanted, boss["name"])
        for fragment in FRAGMENTS:
            self.assertEqual(self.multiworld.get_location(fragment["name"], self.player).progress_type,
                             LocationProgressType.DEFAULT, fragment["name"])

    def test_the_antlion_is_in_lanzelt(self) -> None:
        antlion = self.boss_location(ANTLION)
        self.assertEqual(antlion.parent_region.name, "Lanzelt")
        self.assertFalse(antlion.locked, "a shuffled item, not a Crystal Fragment")

    def test_a_late_boss_needs_a_party_and_continents(self) -> None:
        """Round 72: Tartarosaurus (level 50, tier D) needs five party members and six continents."""
        boss = self.boss_location(TARTAROSAURUS)
        self.collect_by_name(["Pharm Unlock", "Lanzelt Unlock", "Kolobos Unlock", "Dirnado Unlock", "Olderion Unlock"])
        self.collect_by_name(["Fina", "Lid", "Nichol"])
        self.assertTrue(self.multiworld.state.can_reach_region("Pharm", self.player))
        self.assertTrue(boss.can_reach(self.multiworld.state), "six continents, five members")
        self.remove_by_name(["Nichol"])
        self.assertFalse(boss.can_reach(self.multiworld.state), "four members are not enough")

    def test_an_early_boss_needs_nothing_more(self) -> None:
        self.assertTrue(self.boss_location(BELMODAR).can_reach(self.multiworld.state))

    def test_a_boss_is_on_its_continent(self) -> None:
        boss = self.boss_location(THE_HUNGER)
        self.assertFalse(boss.can_reach(self.multiworld.state))
        self.collect_by_name(["Kolobos Unlock"])
        self.assertTrue(boss.can_reach(self.multiworld.state))

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["include_bosses"], slot_data["final_boss_fragments"]), (1, 3))


class TestBossCapabilities(FFResonanceTestBase):
    """Round 73: what counts toward a boss's needs (data/game/capabilities.tsv). The party starts as
    Rain and Lasswell, on Grandshelt, with the Airship."""
    options = {"include_bosses": True, "shuffle_visions": True}

    def has(self, capability: str, level: int) -> bool:
        return has_capability(self.world, self.multiworld.state, capability, level)

    def test_a_skill_counts_from_its_level(self) -> None:
        """Fina learns her first group heal, Radiant Restoration, at level 25."""
        self.collect_by_name(["Fina"])
        self.assertTrue(self.has("heal", EARLY_LEVEL), "Cure at level 3")
        self.assertFalse(self.has("aoe_heal", FINA_GROUP_HEAL_LEVEL - 1))
        self.assertTrue(self.has("aoe_heal", FINA_GROUP_HEAL_LEVEL))

    def test_an_element_is_either_kind_of_attack(self) -> None:
        self.assertTrue(self.has("fire", EARLY_LEVEL), "Rain's Fire")
        self.assertFalse(self.has("earth", MAX_LEVEL))
        self.collect_by_name(["Lid"])
        self.assertTrue(self.has("earth", EARLY_LEVEL), "Mechabo Kick")

    def test_a_vision_awakens_with_magicite(self) -> None:
        """Leah's Esuna is at awakening 1. Round 74: awakening 1 needs two Magicite Shards (one
        for each of two Visions), not a second continent."""
        self.collect_by_name(["Leah (Vision)", "Lanzelt Unlock", "Kolobos Unlock", "Dirnado Unlock"])
        self.assertTrue(self.has("heal", EARLY_LEVEL), "Cure at awakening 0")
        self.assertFalse(self.has("cleanse", MAX_LEVEL), "continents no longer stand in for Magicite")
        self.collect(self.world.create_item("Magicite Shard"))
        self.assertFalse(self.has("cleanse", MAX_LEVEL), "one Shard")
        self.collect(self.world.create_item("Magicite Shard"))
        self.assertTrue(self.has("cleanse", MAX_LEVEL))

    def test_awakening_goes_up_one_tier_at_a_time(self) -> None:
        """A Magicite Cryst is awakening 3, which needs awakenings 1 and 2 first."""
        for name in ("Magicite Cryst", "Magicite Cryst", "Magicite", "Magicite"):
            self.collect(self.world.create_item(name))
        self.assertEqual(awakening(self.world, self.multiworld.state), 0)
        for _ in range(2):
            self.collect(self.world.create_item("Magicite Shard"))
        self.assertEqual(awakening(self.world, self.multiworld.state), 3)

    def test_shop_gear_counts_where_its_shop_is_open(self) -> None:
        """Insulated Gloves are sold in Sian, in Pharm. Gear in the item pool never counts."""
        self.assertFalse(self.has("resist_lightning", MAX_LEVEL))
        self.collect_by_name(["Pharm Unlock"])
        self.assertTrue(self.has("resist_lightning", MAX_LEVEL))

    def test_liquid_thunder_needs_earth_and_a_healer(self) -> None:
        boss = self.multiworld.get_location("Mt. Thunderclap: Liquid Thunder", self.player)
        self.collect_by_name(["Dirnado Unlock", "Lanzelt Unlock", "Lid"])
        self.assertFalse(boss.can_reach(self.multiworld.state), "no healer")
        self.collect_by_name(["Fina"])
        self.assertTrue(boss.can_reach(self.multiworld.state))


class TestBossesNotPriority(FFResonanceTestBase):
    options = {"include_bosses": True, "priority_bosses": False}

    def test_no_boss_is_priority(self) -> None:
        priority = [loc.name for loc in self.multiworld.get_locations(self.player)
                    if loc.progress_type == LocationProgressType.PRIORITY]
        self.assertFalse(priority)


class TestLabKeyCards(FFResonanceTestBase):
    """Round 97 (the user): the Research Center Ruins' key card spots are locations."""
    options = {"include_shinies": True, "shuffle_key_items": True}

    def test_each_card_is_in_the_pool_once(self) -> None:
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        for n in (1, 2, 3):
            self.assertEqual(pool.count(f"Level {n} Lab Key Card"), 1, n)

    def test_the_second_card_is_behind_the_first_door(self) -> None:
        spot = self.multiworld.get_location("Gronoa - Research Center Ruins - Level 2 Lab Key Card Shiny", self.player)
        self.collect_by_name(["Gronoa Unlock"])
        self.assertFalse(spot.can_reach(self.multiworld.state))
        self.collect_by_name(["Level 1 Lab Key Card"])
        self.assertTrue(spot.can_reach(self.multiworld.state))


class TestLabKeyCardsNotShuffled(FFResonanceTestBase):
    options = {"include_shinies": True, "shuffle_key_items": False}

    def test_each_spot_keeps_its_card(self) -> None:
        for n in (1, 2, 3):
            spot = self.multiworld.get_location(f"Gronoa - Research Center Ruins - Level {n} Lab Key Card Shiny", self.player)
            self.assertEqual(spot.item.name, f"Level {n} Lab Key Card")


class TestGifts(FFResonanceTestBase):
    """Round 97 (the user): the one-time NPC gifts are locations, always on."""
    options = {"include_radar_treasures": False}
    LUNAR_SWORD_GIFT = "Grandshelt - Colosseum - Upper East Terrace Gift"
    PHARM_CAT_GIFT = "Pharm - Town of Sian - Central Terrace Cat Gift"

    def test_the_gifts_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertTrue({g["name"] for g in GIFTS_ON} <= names)
        self.assertEqual(len(GIFTS), 7, "1403 (Zoldaad Dungeon), 1407 (Ether NPC), and 1409 (castle Mist Potion NPC) left out")
        self.assertFalse({g["flag"] for g in GIFTS} & {1403, 1407, 1409})
        self.assertNotIn("Gronoa - Gaberada - West Edge Upper Alcove Gift", names, "the radar's goes with it")

    def test_a_second_item_goes_into_the_pool(self) -> None:
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        self.assertIn("Lunar Sword", pool)
        self.assertIn("Brigandine", pool)

    def test_the_pharm_cat_needs_mysidia(self) -> None:
        cat = self.multiworld.get_location(self.PHARM_CAT_GIFT, self.player)
        self.collect_by_name(["Pharm Unlock"])
        self.assertFalse(cat.can_reach(self.multiworld.state))
        self.collect_by_name(["Mysidia Unlock"])
        self.assertTrue(cat.can_reach(self.multiworld.state))


class TestGiftsWithRadar(FFResonanceTestBase):
    options = {"include_radar_treasures": True}

    def test_the_magi_tenna_npc_is_a_location(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertIn("Gronoa - Gaberada - West Edge Upper Alcove Gift", names)
        pool = [item.name for item in self.multiworld.itempool if item.player == self.player]
        self.assertNotIn("Magi-tenna", pool, "the Progressive Radars take the parts' place")


class TestPriorityStoryBosses(FFResonanceTestBase):
    options = {"include_bosses": True, "priority_bosses": False, "priority_story_bosses": True}

    def test_only_story_bosses_are_priority(self) -> None:
        priority = {loc.name for loc in self.multiworld.get_locations(self.player)
                    if loc.progress_type == LocationProgressType.PRIORITY}
        self.assertEqual(priority, {b["name"] for b in BOSSES if b["kind"] == "story"})


class TestPriorityBossInExcludedRegion(FFResonanceTestBase, real_defaults=True):
    options = {"excluded_regions": ["Bosses"]}

    def test_excluded_wins(self) -> None:
        boss = self.multiworld.get_location(next(b["name"] for b in BOSSES if b["kind"] == "cave"), self.player)
        self.assertEqual(boss.progress_type, LocationProgressType.EXCLUDED)


class TestFragmentsWithoutBosses(FFResonanceTestBase):
    options = {"include_bosses": False, "final_boss_fragments": 4}

    def test_no_boss_no_fragment(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["final_boss_fragments"], 0)
        self.assertFalse([i for i in self.multiworld.get_items() if i.player == self.player and i.name == FRAGMENT_NAME])
        self.collect_all_but([VICTORY])
        self.assertTrue(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(self.multiworld.state))


class TestExcludedRegions(FFResonanceTestBase, real_defaults=True):
    options = {"excluded_regions": ["Crystal Tower"]}

    def test_excluded_region_locations_are_excluded(self) -> None:
        tower = [c["name"] for c in CHESTS if c["region"] == "Crystal Tower"]
        self.assertTrue(tower)
        for name in tower:
            location = self.multiworld.get_location(name, self.player)
            self.assertEqual(location.progress_type, LocationProgressType.EXCLUDED)


class TestGoalOldName(FFResonanceTestBase):
    options = {"goal": "story_checkpoint"}

    def test_the_old_name_is_the_final_boss(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["goal"], "final_boss")
        self.assertNotIn("goal_story_checkpoint", self.world.fill_slot_data())


class TestTabletShardGoal(FFResonanceTestBase):
    options = {"goal": "tablet_shards", "tablet_shards_required": 10}

    def test_the_goal_brings_in_the_shards(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in BASE + TABLET_SHINIES})
        self.assertEqual(self.world.fill_slot_data()["include_tablet_shards"], 1)

    def test_the_palace_makes_every_shard_progression(self) -> None:
        shards = [i for i in self.multiworld.itempool if i.player == self.player and i.name == "Tablet Shard"]
        self.assertEqual(len(shards), 99)
        self.assertEqual(sum(i.advancement for i in shards), PALACE_SHARDS)

    def test_the_goal_needs_the_shards(self) -> None:
        shards = [i for i in self.multiworld.itempool if i.player == self.player and i.name == "Tablet Shard" and i.advancement]
        self.collect(shards[:9])
        self.assertBeatable(False)
        self.collect(shards[9:])
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal"], "tablet_shards")
        self.assertEqual(slot_data["tablet_shards_required"], 10)


class TestPalaceWithoutShards(FFResonanceTestBase):
    def test_the_palace_chests_hold_filler_only(self) -> None:
        self.assertEqual(chest_location(self, LAST_PALACE_CHEST).progress_type, LocationProgressType.EXCLUDED)
        self.assertEqual(chest_location(self, "chest:2031:0").progress_type, LocationProgressType.EXCLUDED)


class TestFinalBossLock(FFResonanceTestBase):
    options = {"final_boss_characters": 4, "final_boss_visions": 3}

    def test_the_goal_needs_the_characters_and_visions(self) -> None:
        members = [i for i in self.multiworld.itempool if i.player == self.player and i.name in item_name_groups["Party Members"]]
        visions = [i for i in self.multiworld.itempool if i.player == self.player and i.name in item_name_groups["Visions"]]
        self.collect_all_but([VICTORY] + [i.name for i in members + visions])
        self.assertBeatable(False)
        self.collect(members[:2])            # the starting two and two more: four
        self.collect(visions[:2])
        self.assertBeatable(False)
        self.collect(visions[2:3])
        self.assertBeatable(True)

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["final_boss_characters"], slot_data["final_boss_visions"]), (4, 3))


class TestFinalBossLockWithoutShuffles(FFResonanceTestBase):
    options = {"final_boss_characters": 8, "final_boss_visions": 26, "shuffle_party_members": False, "shuffle_visions": False}

    def test_the_counts_are_lowered_to_what_the_pool_holds(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["final_boss_characters"], slot_data["final_boss_visions"]), (2, 18))


class TestFinalBossLockNotForShards(FFResonanceTestBase):
    options = {"goal": "tablet_shards", "tablet_shards_required": 10}

    def test_the_shard_goal_has_no_lock(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["final_boss_characters"], slot_data["final_boss_visions"]), (0, 0))


class TestKeyCardDoors(FFResonanceTestBase):
    def test_the_lab_rooms_need_their_cards(self) -> None:
        level_1 = chest_location(self, "chest:3220:0")
        level_2 = chest_location(self, "chest:3220:2")
        self.collect_all_but(["Level 1 Lab Key Card", "Level 2 Lab Key Card"])
        self.assertFalse(level_1.can_reach(self.multiworld.state))
        self.collect_by_name(["Level 1 Lab Key Card"])
        self.assertTrue(level_1.can_reach(self.multiworld.state))
        self.assertFalse(level_2.can_reach(self.multiworld.state))
        self.collect_by_name(["Level 2 Lab Key Card"])
        self.assertTrue(level_2.can_reach(self.multiworld.state))


class TestLocationOptionsOnByDefault(FFResonanceTestBase, real_defaults=True):
    def test_shinies_crystals_and_shards_are_locations(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["include_shinies"], slot_data["include_crystals"], slot_data["include_tablet_shards"]),
                         (1, 1, 1))


class TestKeyCardDoorsWithoutKeyItems(FFResonanceTestBase):
    options = {"shuffle_key_items": False}

    def test_the_lab_rooms_hold_filler_only(self) -> None:
        self.assertEqual(chest_location(self, "chest:3220:2").progress_type, LocationProgressType.EXCLUDED)


class TestNoArtifacts(FFResonanceTestBase):
    def test_no_artifact_is_in_the_pool_or_given_at_the_start(self) -> None:
        held = self.multiworld.itempool + self.multiworld.precollected_items[self.player]
        artifacts = [i.name for i in held if i.player == self.player and ARTIFACT_IDS[0] <= ITEMS[i.code]["game_id"] <= ARTIFACT_IDS[1]]
        self.assertEqual(artifacts, [])


class TestDefaultOptions(FFResonanceTestBase, real_defaults=True):
    def test_the_default_goal(self) -> None:
        self.assertEqual(Goal.default, Goal.option_final_boss)
        self.assertEqual(TabletShardsRequired.default, 50)

    def test_the_final_boss_needs_14_fragments_by_default(self) -> None:
        """Round 73 (the user): 14 of the 21 story bosses' Crystal Fragments."""
        self.assertEqual(FinalBossFragments.default, 14)
        self.assertEqual(self.world.fill_slot_data()["final_boss_fragments"], 14)

    def test_enemy_scaling_is_not_a_yaml_option(self) -> None:
        self.assertFalse([k for k in self.world.fill_slot_data() if k.startswith("enemy_")])


class TestCustomParty(FFResonanceTestBase):
    """A two-member start with neither of the usual two: they go in the pool, the starters do not."""
    options = {"starting_roster": 2, "starting_character_1": "Jake", "starting_character_2": "Archwitch Fina",
               "starting_continent": "kolobos"}

    def test_party_and_pool(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["starting_party"], [1007, 1006])
        names = [i.name for i in self.multiworld.itempool if i.player == self.player]
        for name in ("Rain", "Lasswell", "Fina", "Lid", "Nichol", "Sakura"):
            self.assertEqual(names.count(name), 1, name)
        self.assertNotIn("Jake", names)
        self.assertNotIn("Archwitch Fina", names)
        self.assertNotIn("Kolobos Unlock", names)
        self.assertIn("Grandshelt Unlock", names)


class TestRosterSize(FFResonanceTestBase):
    options = {"starting_roster": 1, "starting_character_1": "Sakura"}

    def test_only_the_first_slots_count(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["starting_party"], [1008])
        self.assertIn("Rain", [i.name for i in self.multiworld.itempool if i.player == self.player])


class TestRepeatedCharacter(FFResonanceTestBase):
    options = {"starting_roster": 3, "starting_character_1": "Rain", "starting_character_2": "Rain",
               "starting_character_3": "Rain"}

    def test_a_repeat_becomes_someone_else(self) -> None:
        party = self.world.fill_slot_data()["starting_party"]
        self.assertEqual(len(party), 3)
        self.assertEqual(len(set(party)), 3, party)
        self.assertEqual(party[0], 1001)
        self.assertEqual([self.world.options.starting_character_1.value,
                          self.world.options.starting_character_2.value,
                          self.world.options.starting_character_3.value], party)


class TestSmallestStart(FFResonanceTestBase):
    """The continent with the fewest chests still generates and can be finished."""
    options = {"starting_continent": "kolobos", "shuffle_party_members": True, "shuffle_visions": True,
               "shuffle_key_items": True}


class TestData(FFResonanceTestBase):
    run_default_tests = False

    def test_no_location_holds_a_key_item(self) -> None:
        # Chests and shinies with key items keep them (the mod blanks only ids below the limit).
        # Key items reach the pool as extra items instead (world 0.3.0). Round 97: but for the lab
        # key cards, whose spots are locations.
        for loc in CHESTS + SHINIES:
            info = ITEMS[loc["vanilla"]]
            if info["kind"] == "item" and info["category"] != "magicite" and not loc.get("key_item"):
                self.assertLess(info["game_id"], SHUFFLE_ID_LIMIT, loc)
        cards = sorted(ITEMS[s["vanilla"]]["name"] for s in SHINIES if s.get("key_item"))
        self.assertEqual(cards, [f"Level {n} Lab Key Card" for n in (1, 2, 3)])

    def test_chests_with_magicite_are_locations(self) -> None:
        keys = {c["key"]: ITEMS[c["vanilla"]] for c in CHESTS}
        self.assertEqual(keys["chest:3030:1"]["name"], "Magicite Shard")
        self.assertEqual(keys["chest:3010:0"]["category"], "magicite")
        self.assertNotIn("chest:2031:20", keys, "Adamantite is a key item and stays where it is")

    def test_siren_is_not_an_item(self) -> None:
        # Round 46: she is an ability both Finas start with.
        self.assertNotIn("Siren (Esper)", {i["name"] for i in ITEMS.values()})

    def test_tablet_shards_have_an_area(self) -> None:
        self.assertTrue(all(ITEMS[s["vanilla"]]["name"] == "Tablet Shard" for s in TABLET_SHINIES))
        allowed = set(CONTINENT_UNLOCKS) | {"Crystal Tower", "Open"}
        self.assertTrue({s["area"] for s in TABLET_SHINIES} <= allowed, {s["area"] for s in TABLET_SHINIES})

    def test_bosses(self) -> None:
        self.assertEqual(sum(1 for b in BOSSES if b["vanilla"] is not None), CAVE_MASTERS)
        kinds = [b["kind"] for b in BOSSES]
        self.assertEqual((kinds.count("cave"), kinds.count("story"), kinds.count("optional")),
                         (CAVE_MASTERS, STORY_BOSSES, OPTIONAL_BOSSES))
        self.assertEqual(len(FRAGMENTS), FRAGMENT_BOSSES)
        areas = {b["key"]: b["area"] for b in BOSSES}
        self.assertEqual((areas[f"boss:{MARAUDER}"], areas[f"boss:{LIQUID_THUNDER}"]), ("Lanzelt", "Dirnado"))
        self.assertFalse([b["name"] for b in BOSSES if b["kind"] == "story" and b["vanilla"] is not None])
        # a fragment sits where its boss does, with the same fights before it
        bosses = {int(b["key"].split(":")[1]): b for b in BOSSES}
        for f in FRAGMENTS:
            boss = bosses[f["boss"]]
            self.assertEqual((f["area"], f.get("after_boss"), f.get("past_boss")),
                             (boss["area"], boss.get("after_boss"), boss.get("past_boss")), f["name"])

    def test_crystals(self) -> None:
        self.assertEqual(len(CRYSTALS), 16)
        areas = {c["key"]: c["area"] for c in CRYSTALS}
        self.assertEqual(areas["crystal:10200"], "Olderion")   # round 63: its door is in Wld_05Old
        self.assertEqual(areas["crystal:10214"], "Mysidia")
        self.assertTrue(set(areas.values()) <= set(CONTINENT_UNLOCKS), set(areas.values()))

    def test_rows_with_no_box_are_not_locations(self) -> None:
        # Map 10050 (Dng_02Lan_41) has no level and no map table row: the game does not ship it.
        self.assertIn("chest:10050:0", NO_BOX)
        self.assertIn("chest:3000:0", NO_BOX)      # never seen in game, while 3000:1-6 were
        keys = {loc["key"] for loc in CHESTS + SHINIES}
        self.assertFalse(keys & set(NO_BOX))
        self.assertNotIn("Item 5", {info["name"] for info in ITEMS.values()})

    def test_shinies_come_from_the_game_files(self) -> None:
        self.assertEqual(len(SHINIES), 97)     # round 74: two with a Magicite Shard; round 97: three key cards
        self.assertIn("shiny:1000:189", {s["key"] for s in SHINIES})
        self.assertTrue(all(s["region"] == "World Map" for s in SHINIES if not s.get("key_item")))
        cards = [s for s in SHINIES if s.get("key_item")]
        self.assertEqual({(s["region"], s["area"]) for s in cards}, {("Research Center Ruins", "Gronoa")})
        unseen = sorted(int(s["key"].split(":")[2]) for s in SHINIES if not s["seen"] and not s.get("key_item"))
        self.assertEqual(unseen, [70, 71, 84, 85, 86, 87, 88, 89, 91])

    def test_mod_keys_map_to_ids(self) -> None:
        self.assertEqual(LOCATION_KEY_TO_ID["chest:2012:5"], 1_000_000_000 + 2012 * 1000 + 5)
        self.assertEqual(LOCATION_KEY_TO_ID[f"boss:{MARAUDER}"], 4_000_000_000 + MARAUDER)
        self.assertEqual(LOCATION_KEY_TO_ID[f"fragment:{MARAUDER}"], 7_000_000_000 + MARAUDER)
        self.assertEqual(len(LOCATION_KEY_TO_ID), len(CHESTS) + len(SHINIES) + len(CRYSTALS) + len(TABLET_SHINIES)
                         + len(BOSSES) + len(FRAGMENTS) + len(GIFTS) + len(RADAR) + len(RADAR_PART_CHESTS)
                         + len(SIDE_QUESTS) + len(FORGE))
        self.assertEqual(LOCATION_KEY_TO_ID["gift:1400"], 8_000_000_000 + 1400)
        self.assertEqual(LOCATION_KEY_TO_ID["forge:8"], 6_200_000_000 + 8)
        self.assertEqual(LOCATION_KEY_TO_ID["quest:13"], 6_000_000_000 + 13)


class TestNoProgression(FFResonanceTestBase):
    options = {"shuffle_party_members": False, "shuffle_visions": False, "shuffle_key_items": False}

    def test_pool_is_the_vanilla_contents_and_the_unlocks(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(len(pool), len(BASE))
        rest = [ap_id for ap_id in pool if ITEMS[ap_id]["category"] != "continent"]
        for ap_id in GIFT_EXTRAS + additions(self.world):
            rest.remove(ap_id)
        vanilla = [c["vanilla"] for c in BASE]
        for ap_id in rest:
            vanilla.remove(ap_id)
        self.assertEqual(len(pool) - len(rest) - len(GIFT_EXTRAS) - len(additions(self.world)),
                         len(CONTINENT_UNLOCKS) - 1)


class TestPoolRealDefaults(FFResonanceTestBase, real_defaults=True):
    def test_extra_magicite_is_split_over_the_tiers(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        held = self.world.vanilla_items + self.world.extra_items
        per_tier = ExtraMagicite.default // len(MAGICITE_ITEMS)
        for ap_id in MAGICITE_ITEMS:
            self.assertEqual(pool.count(ap_id), held.count(ap_id) + per_tier, ITEMS[ap_id]["name"])

    def test_every_addition_fits(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(pool.count(RIBBON), RIBBONS)
        held = self.world.vanilla_items + self.world.extra_items
        added = additions(self.world)
        for ap_id in set(added):
            self.assertEqual(pool.count(ap_id) - held.count(ap_id), added.count(ap_id), ITEMS[ap_id]["name"])


class TestNoExtraMagicite(FFResonanceTestBase, real_defaults=True):
    options = {"extra_magicite": 0, "early_healing_vision": False}

    def test_only_the_locations_magicite(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        held = self.world.vanilla_items + self.world.extra_items
        for ap_id in MAGICITE_ITEMS:
            self.assertEqual(pool.count(ap_id), held.count(ap_id), ITEMS[ap_id]["name"])

    def test_no_early_vision(self) -> None:
        self.assertFalse(self.multiworld.local_early_items[self.player])


class TestUnevenExtraMagicite(FFResonanceTestBase):
    options = {"extra_magicite": 10}

    def test_the_lower_tiers_get_the_rest(self) -> None:
        self.assertEqual([additions(self.world).count(ap_id) for ap_id in MAGICITE_ITEMS], [4, 3, 3])


class TestAdditionsShortOfFiller(FFResonanceTestBase):
    """Chests only and the most Magicite: more additions than filler. The pool takes what fits and
    keeps one filler item for each excluded location (the Oblivion Palace's chests), so the fill
    still works (the test base's own fill test)."""
    options = {"extra_magicite": ExtraMagicite.range_end}

    def test_the_excluded_locations_keep_their_filler(self) -> None:
        pool = [item for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(len(pool), len(BASE))
        excluded = [loc for loc in self.world.get_locations() if loc.progress_type == LocationProgressType.EXCLUDED]
        self.assertTrue(excluded)
        filler = [item for item in pool if ITEMS[item.code]["category"] in FILLER_CATEGORIES]
        self.assertEqual(len(filler), len(excluded))
        magicite = sum(1 for item in pool if item.code in MAGICITE_ITEMS)
        held = sum(1 for ap_id in self.world.vanilla_items + self.world.extra_items if ap_id in MAGICITE_ITEMS)
        self.assertLess(magicite - held, ExtraMagicite.range_end, "the test needs a pool short of filler")
        self.assertEqual(sum(1 for item in pool if item.code == RIBBON), RIBBONS, "gear comes before the extra Magicite")


class TestNames(FFResonanceTestBase):
    run_default_tests = False

    def test_locations_are_named_after_the_game_maps(self) -> None:
        names = {c["key"]: c["name"] for c in CHESTS}
        self.assertEqual(names["chest:2020:1"], "Lanzelt - Village of Kol - NW House Chest")
        self.assertEqual(names["chest:3000:1"], "Grandshelt - Earth Shrine - Interior Central-East Alcove Chest")   # row 0 has no box
        self.assertEqual(names["chest:3001:0"], "Grandshelt - Earth Shrine - Entrance NE Alcove West Chest")   # one place over two maps
        self.assertEqual(names["chest:2001:0"], "Grandshelt - Royal Capital - North Avenue NE Spur Chest")
        self.assertEqual(names["chest:3150:0"], "Zoldaad - Dungeon - East Wing West Cell Chest")
        self.assertTrue(all(name.isascii() for name in names.values()))
        # Round 77: world-map spots by continent, compass point and nearest door
        shiny = {s["key"]: s["name"] for s in SHINIES}
        self.assertEqual(shiny["shiny:1000:167"], "Gronoa - World Map - Shiny on Far-NW Coastal Terrace")
        self.assertEqual(NAME_OF_KEY["radar:2"], "Gronoa - World Map - Radar Treasure on Central Bay Ridge NE of Town of Duggle")
        self.assertEqual(NAME_OF_KEY["chest:3260:3"], "Pharm - Mt. Reizan - South Base Corner Chest")
        self.assertEqual(NAME_OF_KEY["shiny:3180:14"], "Mysidia - Nameless Ruins - Upper Chamber SW Alcove Tablet Shard")
        every = [loc["name"] for loc in CHESTS + SHINIES + RADAR + TABLET_SHINIES + RADAR_PART_CHESTS + BOSSES + CRYSTALS]
        self.assertEqual(len(every), len(set(every)))
        self.assertEqual({c["region"] for c in CHESTS if c["key"].startswith("chest:2020:")}, {"Lanzelt"})

    def test_progression_items(self) -> None:
        party = [ITEMS[i]["name"] for i in PROGRESSION["party"]]
        self.assertEqual(party, ["Rain", "Lasswell", "Fina", "Lid", "Nichol", "Archwitch Fina", "Jake", "Sakura"])
        self.assertEqual(ITEMS[UNIT_ITEM_BASE + 1004]["kind"], "unit")
        self.assertEqual(len(PROGRESSION["vision"]), 26)
        self.assertTrue(all(ITEMS[i]["kind"] == "vision" for i in PROGRESSION["vision"]))
        self.assertIn("Charlotte (Vision)", {ITEMS[i]["name"] for i in PROGRESSION["vision"]})
        keys = {ITEMS[i]["name"] for i in PROGRESSION["key"]}
        self.assertIn("Cabin Key", keys)
        for left_out in ("Magicite", "Tablet Shard", "Magitek Armor Key", "White Jade Stone", "Black Jade Stone",
                         "Magic Tome", "Tunnel Key"):
            self.assertNotIn(left_out, keys)
        self.assertFalse([n for n in keys if n.startswith("[TEMP]") or not n.isascii()])
        self.assertEqual(set(CLASSIFICATIONS), {i["category"] for i in ITEMS.values()})


class TestAileensForge(FFResonanceTestBase):
    """Round 105: Aileen's forge is eight locations, the nth weapon forged. Each needs Forger of
    Wills' three continents, the airship's deck and n Adamantite, and the pool has eight."""
    options = {"include_aileens_forge": True, "start_with_airship": False, "starting_continent": "grandshelt"}

    def forge(self, n):
        return self.multiworld.get_location(f"Aileen's Forge: Weapon {n}", self.player)

    def test_the_forge_is_eight_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        forge = {loc["name"] for loc in FORGE}
        self.assertEqual(len(forge), FORGE_WEAPONS)
        self.assertTrue(forge <= names)
        self.assertIn("Aileen's Forge", ExcludedRegions.valid_keys)

    def test_the_pool_has_an_adamantite_per_weapon(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(pool.count(ADAMANTITE_ITEM), FORGE_WEAPONS)
        self.assertEqual(ITEMS[ADAMANTITE_ITEM]["name"], "Adamantite")

    def test_the_nth_weapon_needs_n_adamantite(self) -> None:
        state = self.multiworld.state
        self.collect_by_name(["Airship", "Dirnado Unlock", "Lanzelt Unlock", "Zoldaad Unlock"])
        self.assertFalse(self.forge(1).can_reach(state))
        for n, item in enumerate(self.get_items_by_name("Adamantite"), 1):
            self.collect(item)
            self.assertTrue(self.forge(n).can_reach(state), n)
            if n < FORGE_WEAPONS:
                self.assertFalse(self.forge(n + 1).can_reach(state), n + 1)

    def test_the_forge_is_on_the_deck(self) -> None:
        # Bridges and ferries reach the three continents on foot; the deck needs the Airship.
        state = self.multiworld.state
        self.collect_by_name(["Dirnado Unlock", "Lanzelt Unlock", "Zoldaad Unlock"])
        self.collect(self.get_items_by_name("Adamantite"))
        self.assertFalse(self.forge(1).can_reach(state))
        self.collect_by_name(["Airship"])
        self.assertTrue(self.forge(FORGE_WEAPONS).can_reach(state))


class TestAileensForgeKeyItemsKept(FFResonanceTestBase):
    """With the key items not shuffled, the forge still puts all eight Adamantite in the pool."""
    options = {"include_aileens_forge": True, "shuffle_key_items": False}

    def test_the_pool_has_an_adamantite_per_weapon(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(pool.count(ADAMANTITE_ITEM), FORGE_WEAPONS)


class TestNoForge(FFResonanceTestBase, real_defaults=True):
    def test_the_forge_is_off_by_default(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player)}
        self.assertFalse({loc["name"] for loc in FORGE} & names)

