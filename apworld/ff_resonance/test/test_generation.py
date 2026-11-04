from BaseClasses import LocationProgressType

from ..data import CHESTS, ITEMS, SHINIES, SHUFFLE_ID_LIMIT
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

    def test_mod_keys_map_to_ids(self) -> None:
        self.assertEqual(LOCATION_KEY_TO_ID["chest:3020:1"], 1_000_000_000 + 3020 * 1000 + 1)
        self.assertEqual(len(LOCATION_KEY_TO_ID), len(CHESTS) + len(SHINIES))
