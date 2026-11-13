from __future__ import annotations

from typing import TYPE_CHECKING

from BaseClasses import ItemClassification, Location, LocationProgressType, Region

from .data import AIRSHIP_ITEM, BOSSES, CHESTS, CONTINENT_UNLOCKS, CRYSTALS, FINAL_AREA, ITEMS, OPEN_AREA, SHINIES, TABLET_SHINIES
from .items import FRAGMENT_NAME, GAME, FFResonanceItem, create_item, progression_ids

if TYPE_CHECKING:
    from .world import FFResonanceWorld

ALL_LOCATIONS = CHESTS + SHINIES + CRYSTALS + TABLET_SHINIES + BOSSES
LOCATION_NAME_TO_ID: dict[str, int] = {loc["name"]: loc["id"] for loc in ALL_LOCATIONS}
LOCATION_KEY_TO_ID: dict[str, int] = {loc["key"]: loc["id"] for loc in ALL_LOCATIONS}

location_name_groups: dict[str, set[str]] = {}
for _loc in ALL_LOCATIONS:
    location_name_groups.setdefault(_loc["region"], set()).add(_loc["name"])
location_name_groups["Chests"] = {loc["name"] for loc in CHESTS}
location_name_groups["Shinies"] = {loc["name"] for loc in SHINIES}
location_name_groups["Crystals"] = {loc["name"] for loc in CRYSTALS}
location_name_groups["Tablet Shard Shinies"] = {loc["name"] for loc in TABLET_SHINIES}
location_name_groups["Fragment Bosses"] = {loc["name"] for loc in BOSSES if loc["fragment"]}

# Round 60: at party level 28 Sephiroth took no damage, even with enemy scaling at its lowest. So
# priority_bosses does not put a needed item on him.
SEPHIROTH = "boss:9138"

GOAL_EVENT = "Story Goal"
SHARD_GOAL_EVENT = "Tablet Shard Goal"
VICTORY = "Victory"

UNLOCK_NAMES = {continent: ITEMS[ap_id]["name"] for continent, ap_id in CONTINENT_UNLOCKS.items()}
AIRSHIP = ITEMS[AIRSHIP_ITEM]["name"]

# Round 67: the ways between continents without the airship (open_world.md, section 4). No door
# or cave joins two. Each way opens with the far continent's unlock, as the mod's gates do.
BRIDGES = [("Grandshelt", "Lanzelt"), ("Lanzelt", "Kolobos")]
FERRY_PORTS = ["Lanzelt", "Dirnado", "Olderion", "Zoldaad"]

# Round 72: what a boss needs, by its tier in data/bosses.tsv (docs/boss_logic.md, section 2): party
# members in all, continents unlocked, and the Airship. In round 71 bosses near level 20 felt out
# of reach without a full party, and beatable at level 30 with one. The capability rules per boss
# (healing, elements) in boss_logic.md are not built yet.
TIER_NEEDS = {"A": (0, 0, False), "B": (3, 2, False), "C": (4, 4, False), "D": (5, 6, True)}
BOSS_TIER = {int(b["key"].split(":")[1]): b["tier"] for b in BOSSES}


def boss_rule(world: FFResonanceWorld, tier: str):
    """The rule for a boss of `tier`, or None when it needs nothing. Party sizes above what the
    seed can give (party members not shuffled) count as the most it can."""
    members, continents, wants_airship = TIER_NEEDS[tier]
    player = world.player
    most = 8 if world.options.shuffle_party_members else len(world.starting_party)
    extra = max(0, min(members, most) - len(world.starting_party))
    airship = wants_airship and not world.options.start_with_airship
    if not (extra or continents or airship):
        return None
    return lambda state: (state.has_group("Party Members", player, extra)
                          and state.has_group("Continent Unlocks", player, continents)
                          and (not airship or state.has(AIRSHIP, player)))


class FFResonanceLocation(Location):
    game = GAME


def create_regions_and_locations(world: FFResonanceWorld) -> None:
    """
    One region per continent, each behind its unlock item. The Crystal Tower and the goal need
    every unlock: the tower is open from the start in game, but it is the end of the road, and
    this keeps what the player needs out of it until the continents are done. Everything on a
    continent counts as reachable once it opens.
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

    # Round 69: with the Airship an item, the airship lands only once it comes. Until then the
    # player walks from the starting continent, over the bridges and by the ferry.
    on_foot = not world.options.start_with_airship
    for continent, unlock in UNLOCK_NAMES.items():
        if on_foot and continent != world.starting_continent:
            add_region(continent, lambda state, unlock=unlock: state.has_all((unlock, AIRSHIP), player))
        else:
            add_region(continent, lambda state, unlock=unlock: state.has(unlock, player))
    every_unlock = list(UNLOCK_NAMES.values()) + ([AIRSHIP] if on_foot else [])
    add_region(FINAL_AREA, lambda state: state.has_all(every_unlock, player))
    if on_foot:
        ways = BRIDGES + [(a, b) for i, a in enumerate(FERRY_PORTS) for b in FERRY_PORTS[i + 1:]]
        for a, b in ways:
            for here, there in ((a, b), (b, a)):
                regions[here].connect(regions[there], f"{here} to {there} on foot",
                                      lambda state, unlock=UNLOCK_NAMES[there]: state.has(unlock, player))

    chosen = list(CHESTS)
    if world.options.include_shinies:
        chosen += SHINIES
    if world.options.include_crystals:
        chosen += CRYSTALS
    if world.options.include_tablet_shards:
        chosen += TABLET_SHINIES
    if world.options.include_bosses:
        chosen += BOSSES
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
        # Doors that test a key item (data/gates.tsv). With the item not in the pool, logic
        # cannot count the copy the game hands out: filler only.
        if "needs" in loc:
            if in_pool.issuperset(loc["needs"]):
                names = [ITEMS[ap_id]["name"] for ap_id in loc["needs"]]
                rules.append(lambda state, names=names: state.has_all(names, player))
            else:
                location.progress_type = LocationProgressType.EXCLUDED
        # Round 72: a boss, or a place behind one (Fina's Psyche, behind Tellus), needs what the
        # boss's tier needs. A place only the airship reaches (data/airship_only.tsv) needs it.
        tier = loc.get("tier") or BOSS_TIER.get(loc.get("after_boss"))
        tier_rule = boss_rule(world, tier) if tier else None
        if tier_rule:
            rules.append(tier_rule)
        if loc.get("airship") and on_foot:
            rules.append(lambda state: state.has(AIRSHIP, player))
        if rules:
            location.access_rule = lambda state, rules=rules: all(rule(state) for rule in rules)
        if (world.options.priority_bosses and loc.get("fragment") is False and loc["key"] != SEPHIROTH
                and location.progress_type == LocationProgressType.DEFAULT):
            location.progress_type = LocationProgressType.PRIORITY
        region.locations.append(location)
        # Round 59: a story boss gives a Crystal Fragment, always its own.
        if loc.get("fragment"):
            location.place_locked_item(create_item(world, FRAGMENT_NAME))
        elif "vision" in loc and not world.options.shuffle_visions:
            location.place_locked_item(create_item(world, ITEMS[loc["vision"]]["name"]))
        if loc["vanilla"] is not None:
            world.vanilla_items.append(loc["vanilla"])

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
        goal.access_rule = lambda state: (state.has_group("Party Members", player, members) and
                                          state.has_group("Visions", player, visions) and
                                          state.has(FRAGMENT_NAME, player, fragments))
    goal.place_locked_item(FFResonanceItem(VICTORY, ItemClassification.progression, None, player))
    goal_region.locations.append(goal)
    world.multiworld.completion_condition[player] = lambda state: state.has(VICTORY, player)
