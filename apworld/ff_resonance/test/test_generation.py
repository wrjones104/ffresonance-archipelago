from BaseClasses import LocationProgressType

from ..data import CHESTS, ITEMS, NO_BOX, PROGRESSION, SHINIES, SHUFFLE_ID_LIMIT, UNIT_ITEM_BASE
from ..items import CLASSIFICATIONS, FILLER_CATEGORIES
from ..locations import GOAL_EVENT, LOCATION_KEY_TO_ID
from . import FFResonanceTestBase


class TestDefault(FFResonanceTestBase):
    def test_chests_are_the_only_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {c["name"] for c in CHESTS})

    def test_pool_is_the_vanilla_contents_with_progression_in_place_of_filler(self) -> None:
        pool = [item.code for item in self.multiworld.itempool if item.player == self.player]
        extra = PROGRESSION["party"] + PROGRESSION["vision"] + PROGRESSION["key"]
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
            if item.player == self.player and ITEMS[item.code]["category"] in ("party", "vision", "key"):
                self.assertTrue(item.advancement, item.name)

    def test_goal_is_reachable(self) -> None:
        self.assertBeatable(True)
        self.assertTrue(self.multiworld.get_location(GOAL_EVENT, self.player).can_reach(self.multiworld.state))

    def test_slot_data(self) -> None:
        slot_data = self.world.fill_slot_data()
        self.assertEqual(slot_data["goal_story_checkpoint"], 8050)
        self.assertEqual(slot_data["mod_protocol"], 1)


class TestShinies(FFResonanceTestBase):
    options = {"include_shinies": True}

    def test_shinies_are_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {loc["name"] for loc in CHESTS + SHINIES})


class TestExcludedRegions(FFResonanceTestBase):
    options = {"excluded_regions": ["Crystal Tower"]}

    def test_excluded_region_locations_are_excluded(self) -> None:
        tower = [c["name"] for c in CHESTS if c["region"] == "Crystal Tower"]
        self.assertTrue(tower)
        for name in tower:
            location = self.multiworld.get_location(name, self.player)
            self.assertEqual(location.progress_type, LocationProgressType.EXCLUDED)


class TestGoalOption(FFResonanceTestBase):
    options = {"goal_story_checkpoint": 1130}

    def test_goal_in_slot_data(self) -> None:
        self.assertEqual(self.world.fill_slot_data()["goal_story_checkpoint"], 1130)


class TestData(FFResonanceTestBase):
    run_default_tests = False

    def test_no_location_holds_a_key_item(self) -> None:
        # Chests and shinies with key items keep them (the mod blanks only ids below the limit).
        # Key items reach the pool as extra items instead (world 0.3.0).
        for loc in CHESTS + SHINIES:
            info = ITEMS[loc["vanilla"]]
            if info["kind"] == "item":
                self.assertLess(info["game_id"], SHUFFLE_ID_LIMIT, loc)

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
        self.assertEqual(len(LOCATION_KEY_TO_ID), len(CHESTS) + len(SHINIES))


class TestNoProgression(FFResonanceTestBase):
    options = {"shuffle_party_members": False, "shuffle_visions": False, "shuffle_key_items": False}

    def test_pool_is_the_vanilla_contents(self) -> None:
        pool = sorted(item.code for item in self.multiworld.itempool if item.player == self.player)
        self.assertEqual(pool, sorted(c["vanilla"] for c in CHESTS))


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
        self.assertEqual(party, ["Fina", "Lid", "Nichol", "Jake", "Sakura"])
        self.assertEqual(ITEMS[UNIT_ITEM_BASE + 1004]["kind"], "unit")
        self.assertEqual(len(PROGRESSION["vision"]), 26)
        self.assertTrue(all(ITEMS[i]["kind"] == "vision" for i in PROGRESSION["vision"]))
        self.assertIn("Charlotte (Vision)", {ITEMS[i]["name"] for i in PROGRESSION["vision"]})
        keys = {ITEMS[i]["name"] for i in PROGRESSION["key"]}
        self.assertIn("Tunnel Key", keys)
        self.assertIn("Transporter", keys)
        for left_out in ("Magicite", "Tablet Shard", "Magitek Armor Key"):
            self.assertNotIn(left_out, keys)
        self.assertFalse([n for n in keys if n.startswith("[TEMP]") or not n.isascii()])
        self.assertEqual(set(CLASSIFICATIONS), {i["category"] for i in ITEMS.values()})
