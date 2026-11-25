from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType, Region

from .data import (ADAMANTITE_ITEM, AIRSHIP_AREA, AIRSHIP_ITEM, BOSSES, CHESTS, CONTINENT_UNLOCKS, FORGE, FRAGMENTS,
                   GIFTS, RADAR, RADAR_ITEM,
                   RADAR_PART_CHESTS, CRYSTALS, FINAL_AREA, ITEMS, OPEN_AREA, SHINIES, SIDE_QUESTS, TABLET_SHINIES)
from .boss_logic import boss_rule
from .items import FRAGMENT_NAME, GAME, FFResonanceItem, create_item, progression_ids

if TYPE_CHECKING:
    from .world import FFResonanceWorld

ALL_LOCATIONS = (CHESTS + SHINIES + CRYSTALS + TABLET_SHINIES + BOSSES + FRAGMENTS + GIFTS + RADAR
                 + RADAR_PART_CHESTS + SIDE_QUESTS + FORGE)
# The quests whose reward gives a vision: with visions not shuffled, the quest holds its own.
QUEST_VISIONS = [loc for loc in SIDE_QUESTS if "vision" in loc]
LOCATION_NAME_TO_ID: dict[str, int] = {loc["name"]: loc["id"] for loc in ALL_LOCATIONS}
LOCATION_KEY_TO_ID: dict[str, int] = {loc["key"]: loc["id"] for loc in ALL_LOCATIONS}

location_name_groups: dict[str, set[str]] = {}
for _loc in ALL_LOCATIONS:
    location_name_groups.setdefault(_loc["region"], set()).add(_loc["name"])
location_name_groups["Chests"] = {loc["name"] for loc in CHESTS}
location_name_groups["Shinies"] = {loc["name"] for loc in SHINIES}
location_name_groups["Crystals"] = {loc["name"] for loc in CRYSTALS}
location_name_groups["Tablet Shard Shinies"] = {loc["name"] for loc in TABLET_SHINIES}
location_name_groups["Radar Treasures"] = {loc["name"] for loc in RADAR}
location_name_groups["Side Quests"] = {loc["name"] for loc in SIDE_QUESTS}
location_name_groups["Story Bosses"] = {loc["name"] for loc in BOSSES if loc["kind"] == "story"}
location_name_groups["Cave Masters"] = {loc["name"] for loc in BOSSES if loc["kind"] == "cave"}

# Sephiroth takes negligible damage at midgame levels even at minimum scaling, so priority_bosses
# avoids placing required items on him.
SEPHIROTH = "boss:9138"
# The Crystal Tower's Behemoth, before its third section and the way up.
BEHEMOTH = 9051

GOAL_EVENT = "Story Goal"
SHARD_GOAL_EVENT = "Tablet Shard Goal"
VICTORY = "Victory"

UNLOCK_NAMES = {continent: ITEMS[ap_id]["name"] for continent, ap_id in CONTINENT_UNLOCKS.items()}
AIRSHIP = ITEMS[AIRSHIP_ITEM]["name"]
RADAR_NAME = ITEMS[RADAR_ITEM]["name"]
ADAMANTITE = ITEMS[ADAMANTITE_ITEM]["name"]

# Walking routes between continents without the airship (open_world.md, section 4). No door
# or cave joins two continents; each crossing opens with the far continent's unlock, matching the mod's gates.
BRIDGES = [("Grandshelt", "Lanzelt"), ("Lanzelt", "Kolobos")]
FERRY_PORTS = ["Lanzelt", "Dirnado", "Olderion", "Zoldaad"]
# Round 108: with the key items not shuffled, each key of data/gates.tsv comes in the place its doors
# are: the Research Center's cards from its shinies, the Throne Room Key from Zoldaad Castle's squad
# leader, the Cabin Key from the man by Sian's inn, and the Dungeon Key from the mod in the dungeon.
GIVEN_IN_PLACE = {game_id * 1000 + 1 for game_id in (20009, 20010, 20011, 20019, 20021, 20033)}

class FFResonanceLocation(Location):
    game = GAME


def create_regions_and_locations(world: FFResonanceWorld) -> None:
    """
    One region per continent, each behind its unlock item. Everything on a continent counts as
    reachable once it opens. The Crystal Tower needs only the Airship: its third section is past
    Behemoth (`after_boss`). The goal needs every unlock and Behemoth too.
    """
    player = world.player
    menu = Region("Menu", player, world.multiworld)
    world.multiworld.regions.append(menu)
    regions = {OPEN_AREA: menu}

    def add_region(name: str, rule) -> None:
        region = Region(name, player, world.multiworld)
        world.multiworld.regions.append(region)
        menu.connect(region, f"To {name}", rule)
        regions[name] = region

    # When Airship is an item, walk from the starting continent via bridges and ferries until unlocked.
    on_foot = not world.options.start_with_airship
    for continent, unlock in UNLOCK_NAMES.items():
        if on_foot and continent != world.starting_continent:
            add_region(continent, lambda state, unlock=unlock: state.has_all((unlock, AIRSHIP), player))
        else:
            add_region(continent, lambda state, unlock=unlock: state.has(unlock, player))
    every_unlock = list(UNLOCK_NAMES.values()) + ([AIRSHIP] if on_foot else [])
    add_region(FINAL_AREA, lambda state: not on_foot or state.has(AIRSHIP, player))
    if on_foot:
        ways = BRIDGES + [(a, b) for i, a in enumerate(FERRY_PORTS) for b in FERRY_PORTS[i + 1:]]
        for a, b in ways:
            for here, there in ((a, b), (b, a)):
                regions[here].connect(regions[there], f"{here} to {there} on foot",
                                      lambda state, unlock=UNLOCK_NAMES[there]: state.has(unlock, player))

    # The NPC gifts are always on (round 97); the Magi-tenna's goes with the radar treasures.
    chosen = list(CHESTS) + [g for g in GIFTS if world.options.include_radar_treasures or not g.get("radar_part")]
    if world.options.include_shinies:
        chosen += SHINIES
    if world.options.include_crystals:
        chosen += CRYSTALS
    if world.options.include_tablet_shards:
        chosen += TABLET_SHINIES
    if world.options.include_bosses:
        chosen += BOSSES + FRAGMENTS
    # Round 75: with the radar's treasures on, a chest that held a radar part is a location too.
    if world.options.include_radar_treasures:
        chosen += RADAR + RADAR_PART_CHESTS
    if world.options.include_side_quests:
        chosen += SIDE_QUESTS
    if world.options.include_aileens_forge:
        chosen += FORGE
    excluded = world.options.excluded_regions.value
    in_pool = set(progression_ids(world))

    for loc in chosen:
        region = regions[loc["area"]]
        location = FFResonanceLocation(player, loc["name"], loc["id"], region)
        rules = []
        # A place with no route on the open world start may only hold filler.
        if loc["region"] in excluded or not loc["open_world"]:
            location.progress_type = LocationProgressType.EXCLUDED
        # Oblivion Palace's chests open as Tablet Shards are turned in (3 for the first, 99 for
        # the last). With the shards not in the pool, logic cannot count them: filler only.
        if "shards" in loc:
            if world.options.include_tablet_shards:
                rules.append(lambda state, n=loc["shards"]: state.has("Tablet Shard", player, n))
            else:
                location.progress_type = LocationProgressType.EXCLUDED
        # Doors that test a key item (data/gates.tsv). With the item not in the pool, the game's
        # own copy opens them, in the same place (GIVEN_IN_PLACE); any other key: filler only.
        if "needs" in loc:
            if in_pool.issuperset(loc["needs"]):
                names = [ITEMS[ap_id]["name"] for ap_id in loc["needs"]]
                rules.append(lambda state, names=names: state.has_all(names, player))
            elif not GIVEN_IN_PLACE.issuperset(loc["needs"]):
                location.progress_type = LocationProgressType.EXCLUDED
        # Bosses and post-boss regions (Fina's Psyche, Sanctissimus Shrine) require those bosses'
        # combat needs (boss_logic.py). Places only the airship reaches (data/airship_only.tsv) require it.
        fights = list(loc.get("after_boss", []))
        if loc["key"].startswith("boss:"):
            fights.append(int(loc["key"].split(":")[1]))
        if "boss" in loc:
            fights.append(loc["boss"])
        rules += [boss_rule(world, group) for group in fights]
        if loc.get("airship") and on_foot:
            rules.append(lambda state: state.has(AIRSHIP, player))
        # On foot, regions past a boss (Dirnado past Liquid Thunder) need that boss's needs or the Airship.
        if "past_boss" in loc and on_foot:
            beat = boss_rule(world, loc["past_boss"])
            rules.append(lambda state, beat=beat: state.has(AIRSHIP, player) or beat(state))
        # A radar treasure requires as many Progressive Radars as its tier. The mod opens a whole tier at once.
        # A gift that needs a place first (the Pharm cat's: the Mysidia cat talked to).
        if "needs_area" in loc:
            rules.append(lambda state, area=loc["needs_area"]: state.can_reach_region(area, player))
        if "radar_tier" in loc:
            rules.append(lambda state, n=loc["radar_tier"]: state.has(RADAR_NAME, player, n))
        # A quest that needs a party of n (Beyond the Blue: 4, round 112). The starting party counts;
        # with party members not shuffled, nobody else ever joins.
        if "party" in loc:
            members = loc["party"] - len(world.starting_party)
            if members > 0 and world.options.shuffle_party_members:
                rules.append(lambda state, n=members: state.has_group("Party Members", player, n))
            elif members > 0:
                location.progress_type = LocationProgressType.EXCLUDED
        # The nth weapon forged costs n Adamantite in all.
        if "adamantite" in loc:
            rules.append(lambda state, n=loc["adamantite"]: state.has(ADAMANTITE, player, n))
        # A side quest's steps: one place of each group (side_quests.md, section 5). The airship's
        # own rooms need the Airship when the player starts on foot.
        for group in loc.get("steps", []):
            places = [area for area in group if area != AIRSHIP_AREA]
            if AIRSHIP_AREA in group and not on_foot:
                continue
            if AIRSHIP_AREA in group:
                rules.append(lambda state, places=places: state.has(AIRSHIP, player) or
                             any(state.can_reach_region(p, player) for p in places))
            else:
                rules.append(lambda state, places=places: any(state.can_reach_region(p, player) for p in places))
        if rules:
            location.access_rule = lambda state, rules=rules: all(rule(state) for rule in rules)
        kind = loc.get("kind")
        priority = ((world.options.priority_bosses and kind in ("cave", "optional") and loc["key"] != SEPHIROTH)
                    or (world.options.priority_story_bosses and kind == "story"))
        if priority and location.progress_type == LocationProgressType.DEFAULT:
            location.progress_type = LocationProgressType.PRIORITY
        region.locations.append(location)
        # Every boss awards its own Crystal Fragment, on a location of its own (round 97).
        if "boss" in loc:
            location.place_locked_item(create_item(world, FRAGMENT_NAME))
        elif "vision" in loc and not world.options.shuffle_visions:
            location.place_locked_item(create_item(world, ITEMS[loc["vision"]]["name"]))
        # A key item's own spot keeps it when key items are not shuffled (round 97).
        elif loc.get("key_item") and not world.options.shuffle_key_items:
            location.place_locked_item(create_item(world, ITEMS[loc["vanilla"]]["name"]))
        # A location that holds its own item adds nothing to the pool.
        if loc["vanilla"] is not None and location.item is None:
            world.vanilla_items.append(loc["vanilla"])
        # A gift's second item goes into the pool in place of a filler.
        world.extra_items += loc.get("extra", [])

    if world.options.goal.value == world.options.goal.option_tablet_shards:
        goal_region = menu
        needed = world.options.tablet_shards_required.value
        goal = FFResonanceLocation(player, SHARD_GOAL_EVENT, None, goal_region)
        goal.access_rule = lambda state: state.has("Tablet Shard", player, needed)
    else:
        goal_region = regions[FINAL_AREA]
        goal = FFResonanceLocation(player, GOAL_EVENT, None, goal_region)
        # The final boss lock: the starting party counts, so only the members beyond it are items.
        members = max(0, world.final_boss_characters - len(world.starting_party))
        visions = world.final_boss_visions
        fragments = world.final_boss_fragments
        behemoth = boss_rule(world, BEHEMOTH)
        goal.access_rule = lambda state: (state.has_all(every_unlock, player) and behemoth(state) and
                                          state.has_group("Party Members", player, members) and
                                          state.has_group("Visions", player, visions) and
                                          state.has(FRAGMENT_NAME, player, fragments))
    goal.place_locked_item(FFResonanceItem(VICTORY, ItemClassification.progression, None, player))
    goal_region.locations.append(goal)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY, player)
