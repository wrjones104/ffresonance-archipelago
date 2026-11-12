from BaseClasses import LocationProgressType

from ..data import AIRSHIP_ITEM, BOSSES, CHESTS, CHOCOBO_ITEM, CONTINENT_UNLOCKS, CRYSTALS, FRAGMENT_ITEM, ITEMS, NO_BOX, TABLET_SHINIES, PROGRESSION, SHINIES, SHUFFLE_ID_LIMIT, UNIT_ITEM_BASE
from ..items import CLASSIFICATIONS, FILLER_CATEGORIES, FRAGMENT_NAME, item_name_groups
from ..locations import GOAL_EVENT, LOCATION_KEY_TO_ID, SEPHIROTH, VICTORY
from ..options import Goal, TabletShardsRequired
from . import FFResonanceTestBase

ARTIFACT_IDS = (30000, 30018)    # DT_ArtifactItemData's rows
LAST_PALACE_CHEST = "chest:2031:24"   # Oblivion Palace's 4-Star Chamber: all 99 shards
PALACE_SHARDS = 99
MARAUDER, LIQUID_THUNDER, ANTLION = 9079, 9083, 9060   # battle groups: a cave master, a story boss, an optional boss
CAVE_MASTERS, FRAGMENT_BOSSES = 15, 12


def chest_location(test, key):
    name = next(c["name"] for c in CHESTS if c["key"] == key)
    return test.multiworld.get_location(name, test.player)


class TestDefault(FFResonanceTestBase):
    def test_chests_are_the_only_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {c["name"] for c in CHESTS})

    def test_pool_is_the_vanilla_contents_with_progression_in_place_of_filler(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        starters = {UNIT_ITEM_BASE + 1001, UNIT_ITEM_BASE + 1002}
        unlocks = [ap_id for name, ap_id in CONTINENT_UNLOCKS.items() if name != "Grandshelt"]
        extra = [i for i in PROGRESSION["party"] if i not in starters] + PROGRESSION["vision"] + PROGRESSION["key"] + unlocks
        self.assertEqual(len(pool), len(CHESTS))
        for ap_id in extra:
            self.assertEqual(pool.count(ap_id), 1, ITEMS[ap_id]["name"])
        rest = list(pool)
        for ap_id in extra:
            rest.remove(ap_id)
        vanilla = [c["vanilla"] for c in CHESTS]
        for ap_id in rest:
            vanilla.remove(ap_id)            # every other item is some chest's vanilla content
        self.assertEqual(len(vanilla), len(extra))
        self.assertTrue(all(ITEMS[ap_id]["category"] in FILLER_CATEGORIES for ap_id in vanilla))

    def test_progression_items_are_progression(self) -> None:
        for item in self.multiworld.itempool:
            if item.player == self.player and ITEMS[item.code]["category"] in ("party", "vision", "key", "continent"):
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
        self.assertTrue(self.multiworld.get_location("Dragon's Maw Chest 1", self.player).can_reach(self.multiworld.state))
        self.assertFalse(self.multiworld.state.can_reach_region("Gronoa", self.player))

    def test_places_with_no_route_hold_only_filler(self) -> None:
        for name in ("Grandshelt Castle Chest 8", "Fina's Psyche Chest 1"):
            self.assertEqual(self.multiworld.get_location(name, self.player).progress_type, LocationProgressType.EXCLUDED)
        # Round 44 walked into the Earth Shrine's inner part and opened its chests.
        self.assertNotEqual(self.multiworld.get_location("Earth Shrine Chest 1", self.player).progress_type,
                            LocationProgressType.EXCLUDED)

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal"], "final_boss")
        self.assertEqual(slot_data["mod_protocol"], 2)
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
        self.assertEqual(len(pool), len(CHESTS))
        chocobos = [i for i in pool if i.code == CHOCOBO_ITEM]
        self.assertEqual(len(chocobos), 1)
        self.assertTrue(chocobos[0].advancement)
        self.assertEqual(ITEMS[CHOCOBO_ITEM]["game_id"], 30002, "the game's Choboco Saddle")

    def test_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["start_with_chocobo"], 0)


class TestAirshipItem(FFResonanceTestBase):
    """Round 69: on foot from Grandshelt. The bridges and the ferry need only the far side's unlock."""
    options = {"start_with_airship": False}

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

    def test_the_tower_needs_the_airship(self) -> None:
        self.collect_all_but(["Airship"])
        self.assertFalse(self.multiworld.state.can_reach_region("Crystal Tower", self.player))
        self.assertFalse(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(self.multiworld.state))


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


class TestShinies(FFResonanceTestBase):
    options = {"include_shinies": True}

    def test_shinies_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in CHESTS + SHINIES})


class TestTabletShards(FFResonanceTestBase):
    options = {"include_tablet_shards": True}

    def test_shards_are_locations_and_items(self) -> None:
        self.assertEqual(len(TABLET_SHINIES), 99)
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in CHESTS + TABLET_SHINIES})
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


class TestCrystals(FFResonanceTestBase):
    options = {"include_crystals": True}

    def test_crystals_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in CHESTS + CRYSTALS})

    def test_there_is_an_item_for_each(self) -> None:
        pool = [item for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(len(pool), len(CHESTS) + len(CRYSTALS))

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
        self.assertEqual(names, {loc["name"] for loc in CHESTS + BOSSES})

    def test_a_story_boss_holds_a_fragment_and_the_others_a_shuffled_item(self) -> None:
        for boss in BOSSES:
            item = self.multiworld.get_location(boss["name"], self.player).item
            if boss["fragment"]:
                self.assertEqual((item.name, item.code, item.advancement), (FRAGMENT_NAME, FRAGMENT_ITEM, True), boss["name"])
            else:
                self.assertIsNone(item, boss["name"])
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertNotIn(FRAGMENT_ITEM, pool)
        self.assertEqual(len(pool), len(CHESTS) + len(BOSSES) - FRAGMENT_BOSSES)

    def test_a_cave_master_gives_its_magicite_to_the_pool(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        for name in ("Magicite Shard", "Magicite", "Magicite Cryst"):
            ap_id = next(i for i, info in ITEMS.items() if info["name"] == name)
            from_chests = sum(1 for c in CHESTS if c["vanilla"] == ap_id)
            from_caves = sum(1 for b in BOSSES if b["vanilla"] == ap_id)
            self.assertGreater(from_caves, 0, name)
            self.assertEqual(pool.count(ap_id), from_chests + from_caves, name)

    def test_the_goal_needs_the_fragments(self) -> None:
        goal = self.multiworld.get_location(GOAL_EVENT, self.player)
        fragments = [self.multiworld.get_location(b["name"], self.player).item for b in BOSSES if b["fragment"]]
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

    def test_shuffled_bosses_are_priority_but_not_sephiroth(self) -> None:
        for boss in BOSSES:
            plain = boss["fragment"] or boss["key"] == SEPHIROTH
            wanted = LocationProgressType.DEFAULT if plain else LocationProgressType.PRIORITY
            self.assertEqual(self.multiworld.get_location(boss["name"], self.player).progress_type, wanted, boss["name"])

    def test_the_antlion_is_in_lanzelt(self) -> None:
        antlion = self.boss_location(ANTLION)
        self.assertEqual(antlion.parent_region.name, "Lanzelt")
        self.assertFalse(antlion.locked, "a shuffled item, not a Crystal Fragment")

    def test_a_boss_is_on_its_continent(self) -> None:
        boss = self.boss_location(LIQUID_THUNDER)
        self.assertFalse(boss.can_reach(self.multiworld.state))
        self.collect_by_name(["Dirnado Unlock"])
        self.assertTrue(boss.can_reach(self.multiworld.state))

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual((slot_data["include_bosses"], slot_data["final_boss_fragments"]), (1, 3))


class TestBossesNotPriority(FFResonanceTestBase):
    options = {"include_bosses": True, "priority_bosses": False}

    def test_no_boss_is_priority(self) -> None:
        priority = [loc.name for loc in self.multiworld.get_locations(self.player)
                    if loc.progress_type == LocationProgressType.PRIORITY]
        self.assertFalse(priority)


class TestPriorityBossInExcludedRegion(FFResonanceTestBase, real_defaults=True):
    options = {"excluded_regions": ["Bosses"]}

    def test_excluded_wins(self) -> None:
        boss = self.multiworld.get_location(next(b["name"] for b in BOSSES if not b["fragment"]), self.player)
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
        self.assertEqual(names, {loc["name"] for loc in CHESTS + TABLET_SHINIES})
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
        self.assertEqual((slot_data["final_boss_characters"], slot_data["final_boss_visions"]), (2, 0))


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


class TestSmallestStart(FFResonanceTestBase):
    """The continent with the fewest chests still generates and can be finished."""
    options = {"starting_continent": "kolobos", "shuffle_party_members": True, "shuffle_visions": True,
               "shuffle_key_items": True}


class TestData(FFResonanceTestBase):
    run_default_tests = False

    def test_no_location_holds_a_key_item(self) -> None:
        # Chests and shinies with key items keep them (the mod blanks only ids below the limit).
        # Key items reach the pool as extra items instead (world 0.3.0).
        for loc in CHESTS + SHINIES:
            info = ITEMS[loc["vanilla"]]
            if info["kind"] == "item" and info["category"] != "magicite":
                self.assertLess(info["game_id"], SHUFFLE_ID_LIMIT, loc)

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
        self.assertEqual(sum(1 for b in BOSSES if b["fragment"]), FRAGMENT_BOSSES)
        areas = {b["key"]: b["area"] for b in BOSSES}
        self.assertEqual((areas[f"boss:{MARAUDER}"], areas[f"boss:{LIQUID_THUNDER}"]), ("Lanzelt", "Dirnado"))
        self.assertFalse([b["name"] for b in BOSSES if b["fragment"] and b["vanilla"] is not None])

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
        self.assertEqual(len(SHINIES), 92)
        self.assertTrue(all(s["region"] == "World Map" for s in SHINIES))
        unseen = sorted(int(s["key"].split(":")[2]) for s in SHINIES if not s["seen"])
        self.assertEqual(unseen, [70, 71, 84, 85, 86, 87, 88, 89, 91])

    def test_mod_keys_map_to_ids(self) -> None:
        self.assertEqual(LOCATION_KEY_TO_ID["chest:3020:1"], 1_000_000_000 + 3020 * 1000 + 1)
        self.assertEqual(LOCATION_KEY_TO_ID[f"boss:{MARAUDER}"], 4_000_000_000 + MARAUDER)
        self.assertEqual(len(LOCATION_KEY_TO_ID), len(CHESTS) + len(SHINIES) + len(CRYSTALS) + len(TABLET_SHINIES) + len(BOSSES))


class TestNoProgression(FFResonanceTestBase):
    options = {"shuffle_party_members": False, "shuffle_visions": False, "shuffle_key_items": False}

    def test_pool_is_the_vanilla_contents_and_the_unlocks(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        self.assertEqual(len(pool), len(CHESTS))
        rest = [ap_id for ap_id in pool if ITEMS[ap_id]["category"] != "continent"]
        vanilla = [c["vanilla"] for c in CHESTS]
        for ap_id in rest:
            vanilla.remove(ap_id)
        self.assertEqual(len(pool) - len(rest), len(CONTINENT_UNLOCKS) - 1)


class TestNames(FFResonanceTestBase):
    run_default_tests = False

    def test_locations_are_named_after_the_game_maps(self) -> None:
        names = {c["key"]: c["name"] for c in CHESTS}
        self.assertEqual(names["chest:2020:1"], "Village of Kol Chest 2")
        self.assertEqual(names["chest:3000:1"], "Earth Shrine Chest 1")   # row 0 has no box
        self.assertEqual(names["chest:3001:0"], "Earth Shrine Chest 7")   # one place over two maps
        self.assertEqual(names["chest:2001:0"], "Grandshelt, the Royal Capital Chest 1")
        self.assertEqual(names["chest:3150:0"], "Zoldaad Dungeon Chest 1")
        self.assertTrue(all(name.isascii() for name in names.values()))
        self.assertEqual({c["region"] for c in CHESTS if c["key"].startswith("chest:2020:")}, {"Lanzelt"})

    def test_progression_items(self) -> None:
        party = [ITEMS[i]["name"] for i in PROGRESSION["party"]]
        self.assertEqual(party, ["Rain", "Lasswell", "Fina", "Lid", "Nichol", "Archwitch Fina", "Jake", "Sakura"])
        self.assertEqual(ITEMS[UNIT_ITEM_BASE + 1004]["kind"], "unit")
        self.assertEqual(len(PROGRESSION["vision"]), 26)
        self.assertTrue(all(ITEMS[i]["kind"] == "vision" for i in PROGRESSION["vision"]))
        self.assertIn("Charlotte (Vision)", {ITEMS[i]["name"] for i in PROGRESSION["vision"]})
        keys = {ITEMS[i]["name"] for i in PROGRESSION["key"]}
        self.assertIn("Tunnel Key", keys)
        self.assertIn("Cabin Key", keys)
        for left_out in ("Magicite", "Tablet Shard", "Magitek Armor Key"):
            self.assertNotIn(left_out, keys)
        self.assertFalse([n for n in keys if n.startswith("[TEMP]") or not n.isascii()])
        self.assertEqual(set(CLASSIFICATIONS), {i["category"] for i in ITEMS.values()})
