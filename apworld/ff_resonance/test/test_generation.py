from BaseClasses import LocationProgressType

from ..data import CHESTS, ITEMS, NO_BOX, SHINIES, SHUFFLE_ID_LIMIT
from ..locations import GOAL_EVENT, LOCATION_KEY_TO_ID
from . import FFResonanceTestBase


class TestDefault(FFResonanceTestBase):
    def test_chests_are_the_only_locations(self) -> None:
        names = {loc.name for loc in self.multiworld.get_locations(self.player) if loc.address is not None}
        self.assertEqual(names, {c["name"] for c in CHESTS})

    def test_pool_is_the_vanilla_contents(self) -> None:
        pool = sorted(item.code for item in self.multiworld.itempool if item.player == self.player)
        self.assertEqual(pool, sorted(c["vanilla"] for c in CHESTS))

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

    def test_no_key_items_move(self) -> None:
        for info in ITEMS.values():
            if info["kind"] == "item":
                self.assertLess(info["game_id"], SHUFFLE_ID_LIMIT, info)

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
