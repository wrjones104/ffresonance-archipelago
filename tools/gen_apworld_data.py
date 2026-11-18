"""Generates apworld/ff_resonance/data.py from the tables in data/.

    python tools/gen_apworld_data.py

Inputs, from the game's own files (tools/dump_game, then tools/gen_from_dump.py):
    data/game/items.tsv            item id -> English name
    data/game/chests.tsv           every chest table row, with the placed boxes that are its box
    data/game/field_items.tsv      every field item (shiny) placed on a map
And from play:
    data/shinies.tsv               shinies seen in game (the mod's seen.tsv): marks a shiny "seen"
And by hand, from the dump (docs/bosses.md):
    data/bosses.tsv                boss fights that are locations: battle group, win flag, map, kind
    data/quests.tsv                side quests that are locations (docs/side_quests.md): counter,
                                   the reward row's value, reward rows; with data/game/quests.tsv
                                   and data/game/quest_steps.tsv from the dump

A chest table row is a location only when a box for it is placed on some map (the boxes
column; gen_from_dump.box_matches says how a box is matched to its row). The rounds agree:
map 3000 showed boxes 1-6 in round 1 and never row 0, which has no box. Rows with no box
(for example all of map 10050, a dungeon the game does not ship) go to NO_BOX and are not
locations.

Which items move: the same kinds FFR-Randomizer moves (consumables, equipment, seeds), plus
gil. Those are told apart by id range, read off the item tables: consumables and scrolls are
below 1000, equipment is 10000-12999, visions are 13000s, and valuables, key items and
artifacts are 20000 and up. A chest or shiny holding anything else keeps its vanilla content
and is not a location. The mod's chest blanking uses the same rule (SHUFFLE_ID_LIMIT).

Ids are derived from the game's own keys, so they never change between data refreshes:
    chest location  1_000_000_000 + row mapId * 1000 + row ID
    shiny location  2_000_000_000 + map * 1000 + uid
    item            item id * 1000 + count     (e.g. Potion x3 -> 1003)
    gil             900_000_000 + amount
    boss location   4_000_000_000 + battle group
    quest location  6_000_000_000 + the quest's id in the quest log
"""

import collections
import csv
import math
import os
import pprint
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "apworld", "ff_resonance", "data.py")
FIELD_ITEMS_LUA = os.path.join(ROOT, "FFRArchipelago", "Scripts", "field_items.lua")

SHUFFLE_ID_LIMIT = 13000          # item ids at or above this never move (visions, key items)
MAGICITE_IDS = (25000, 25002)     # except these (the mod blanks them too)
CRYSTAL_LOCATION_BASE = 3_000_000_000    # + the sanctum's map id
TABLET_SHARD = 25004              # a shiny holding one is a location of its own kind (round 47)
CONSUMABLE_LIMIT = 1000

# Round 59: a boss fight is a location (data/bosses.tsv). A "story" boss holds a locked Crystal
# Fragment; a cave master or an optional boss holds a shuffled item.
BOSS_LOCATION_BASE = 4_000_000_000       # + the battle group
FRAGMENT_ITEM = 600_000_001
FRAGMENT_NAME = "Crystal Fragment"
# Round 67: the Chocobo, the game's Choboco Saddle (an artifact, 30002), which the game checks.
CHOCOBO_GAME_ID = 30002
CHOCOBO_ITEM = CHOCOBO_GAME_ID * 1000 + 1
# Round 72: the airship radar's 13 treasures (data/radar.tsv, IDEAS.md idea 32) are locations, and
# a Progressive Radar (the Magi-tenna, 27006, given again for each step) opens them by tier.
RADAR_LOCATION_BASE = 5_000_000_000      # + the treasure's number
RADAR_GAME_ID = 27006
RADAR_ITEM = RADAR_GAME_ID * 1000 + 2
RADAR_PARTS = [27006001, 27007001, 27008001]   # the three parts, which the Progressive Radar replaces
# Round 75: Mt. Reizan's chest holds the Resonance Stone. With the radar's treasures on it is a
# location, and the mod empties it; the pool gets a Potion in its place.
RADAR_PART_GAME_IDS = {ap_id // 1000 for ap_id in RADAR_PARTS}
POTION = 1
# Round 69: the airship as an item is an event flag the mod gives the airship's spawn condition.
# Its AP id is numbered like the continent unlocks, which are flags too.
AIRSHIP_FLAG = 1431

CHEST_LOCATION_BASE = 1_000_000_000
SHINY_LOCATION_BASE = 2_000_000_000
GIL_ITEM_BASE = 900_000_000

# Region codes in the chest table's row names (Dng_01Gra_40_0 = dungeon, region 01 "Gra").
REGION_NAMES = {
    "Gra": "Grandshelt",
    "Lan": "Lanzelt",           # the island column of DT_MapData (data/game/maps.tsv)
    "Kol": "Kolobos",
    "Dir": "Dirnado",
    "Old": "Olderion",
    "Zol": "Zoldaad",
    "Mys": "Mysidia",
    "Gro": "Gronoa",
    "Pha": "Pharm",
    "Cry": "Crystal Tower",
}
WORLD_MAP = 1000


def read_tsv(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))




def item_kind(item_id: int, money: int) -> str | None:
    if item_id < 0:
        return "gil" if money > 0 else None
    # Round 45: chests with Magicite are shuffled. Round 74: shinies with Magicite too (two on the
    # world map held a Magicite Shard that a tester found not shuffled).
    if MAGICITE_IDS[0] <= item_id <= MAGICITE_IDS[1]:
        return "magicite"
    if item_id == TABLET_SHARD:
        return "shard"
    if item_id < CONSUMABLE_LIMIT:
        return "consumable"
    if 10000 <= item_id < SHUFFLE_ID_LIMIT:
        return "equipment"
    return None


def ascii_name(name: str) -> str:
    """The game writes apostrophes as U+2019; names players type in hints use the plain one."""
    return name.replace("’", "'")


def chest_region(row: str) -> str:
    """'Grandshelt' from 'Dng_01Gra_40_0'."""
    code = row.split("_")[1][2:]
    return REGION_NAMES.get(code, code)


def chest_place(row: str, map_id: int, maps: dict[int, dict]) -> str:
    """
    The English map name a chest row is on: its row's mapId in DT_MapData, else the map whose
    key matches the row's table (Town_01Gra_02 -> 01Gra_02), else the region and area code.
    A name the game uses in several regions ("Dungeon") gets its region in front.
    """
    table = row.rsplit("_", 1)[0]
    key = "_".join(table.split("_")[1:3])
    name = (maps.get(map_id) or {}).get("name") or next(
        (m["name"] for m in maps.values() if m["key"] == key and m["name"]), "")
    region = chest_region(row)
    if not name:
        kind = {"Dng": "Dungeon", "Town": "Town"}.get(table.split("_")[0], table.split("_")[0])
        return f"{region} {kind} {key.split('_', 1)[-1]}"
    if name in GENERIC_PLACE_NAMES:
        name = f"{region} {name}"
    return ascii_name(name)


GENERIC_PLACE_NAMES = {"Dungeon", "Shipyard", "Slums"}

# Progression items (world 0.3.0).
UNIT_ITEM_BASE = 800_000_000       # AP id of a party member: base + unit id
CONTINENT_ITEM_BASE = 700_000_000  # AP id of a continent's unlock: base + its event flag
# Maps with no route on the open world start (world 0.4.0, from data/game/transitions.tsv and the
# talk event table). Their chests held filler only, until play showed most of them open: the
# Earth Shrine's inner part (3000, round 44), Fina's Psyche (3211, 3212, behind Tellus, round 71)
# and the Imperial Residences (2113, by the Zoldaad streetcar, round 72). The burning Grandshelt
# Castle (3020) is the prologue's and cannot be entered at story 8000. Round 72: its chests are
# no locations at all, as a location no one can open only inflates the count (the user).
# Round 73: the attacked Old Town of Olderion (3090) is chapter 3's. Olderion's door to it opens
# only at story 3050 to 3085, and the user found no way in.
NO_ROUTE_MAPS = {3020, 3090}
# Round 72: single chests with no route at story 8000. Grandshelt Castle's chest row 1 (box uid 63,
# at (-30195, 8095) on map 2012) is in a room the user could not find after searching the castle:
# most likely one the story passes through and the castle closes later.
NO_ROUTE_CHESTS = {"chest:2012:1"}
# Places behind boss fights: their locations need what each of those bosses needs (the highest
# tier). Round 71 (the user): Fina's Psyche (maps 3210 to 3212) is reached past Tellus in the Tower
# of Mysidia. Round 72 (the user): Sanctissimus Shrine's chests and shards (3250) are past its first
# three fights, Archaeoaevis, Dad Bomb and Test Rider.
# Round 78 (the user): every chest in Dragon's Maw (3010) is past Intangir, airship or not. Its
# Tablet Shard and the Rogue Magitek Weapon are too.
AFTER_BOSS = {3210: [9038], 3211: [9038], 3212: [9038], 3250: [9075, 9074, 9073], 3010: [7042]}
# Single locations behind a boss fight, where the rest of their map is not. Round 73: the Crystal
# Tower's third section is past Behemoth (9051). Its door (transition 11, at story 8020) leads to
# the room at y -125400, and that room's other door to the section around (8000, -58000). These
# are the chests and shard there. The first two sections need only the way in (the user).
AFTER_BOSS_KEYS = {9051: {"chest:3280:2", "chest:3280:5", "chest:3280:6", "chest:3280:7", "chest:3280:8",
                          "shiny:3280:126"},
                   # Round 74, from positions. Tower of Mysidia Chest 3 is on the top floor (z 11247), past
                   # Tellus's trigger (z 10950); a tester found it in logic without Tellus.
                   9038: {"chest:3200:2"},
                   # Nameless Ruins Chest 4 is on the upper floor, up the stairs that Tellus's door is.
                   9031: {"chest:3180:3"},
                   # Round 77 (a pre-release player): the Nameless Ruins' south half is past both barriers,
                   # the blocking bases at y -11975 (flag 527, Iron Giant) and y -15996 (flag 526, Liquid
                   # Flame). Chest 2 and Shard 14 are at y -27000, and Tellus's door at y -25500. Chest 5,
                   # the safe by the entrance, opens from the statue puzzle, whose Abyss statue is past them.
                   **{group: {"chest:3180:1", "chest:3180:3", "chest:3180:4", "shiny:3180:14", "boss:9031"}
                      for group in (9088, 9089)},
                   # Earth Shrine Chests 4 to 6 (x 14900) are past Belmodar's triggers (x 11592 to 11767).
                   9004: {"chest:3000:4", "chest:3000:5", "chest:3000:6"}}
# Round 74: places past a boss fight on the world map. A tester found them in logic with a party
# the boss would beat. Each entry gives the world-map doors on the boss's far side and more maps:
# every location on those maps and on the maps their doors lead to is past the boss, and so are
# the location keys given. "airship" is whether the airship can fly past the boss instead.
FAR_SIDE = {
    # Lux on the Rugged Mountain Path (map 3230) stands before its upper door (world-map door 37).
    # Past her is Gronoa's south-west plateau at z 1275 to 1710: the Town of Duggle (door 38), Gronoa
    # Shrine (39), Sanctissimus Shrine (40), Necromonarch Cave (99) and World Map Shinies 161 to 166.
    # Gaberada's side is low, at z 610 to 880. The airship cannot land on the plateau (the tester).
    9039: {"doors": {38, 39, 40, 99}, "maps": set(), "keys": {f"shiny:1000:{uid}" for uid in range(161, 167)},
           "airship": False},
    # Ignis at the top of Mt. Reizan (map 3260, z 5082) stands by its upper door (world-map door 29);
    # all its chests are below him. Past him is Pharm's plateau at z 1110 to 1350: Lake Ryusei
    # (door 30), the Wandering Lands (64) and the Forest Path (65, 66). Not known whether the airship
    # lands there, so it does not count.
    9046: {"doors": {30, 64, 65, 66}, "maps": set(), "keys": set(), "airship": False},
    # Intangir's blocking box (flag 928) in Dragon's Maw is near its south door, the one most of Pharm
    # walks to. The tester went through Dragon's Maw after beating Intangir, to World Map Shiny 149
    # by the north door. The north side is reached from the air. Dragon's Maw itself needs Intangir
    # whichever way in (AFTER_BOSS, round 78).
    7042: {"doors": set(), "maps": set(), "keys": {"shiny:1000:149"}, "airship": True},
}
# Places that on foot lie past a boss, which the airship flies over. Round 73 (the user): from
# Dilmagia, where the Dirnado start and the ferry arrive, Liquid Thunder on Mt. Thunderclap's
# summit blocks the way to the rest of Dirnado. Only Dilmagia (maps 2060 and 2061), Mt.
# Thunderclap Shard 22 and the fight itself are this side of it.
PAST_BOSS_ON_FOOT = {9083: ("Dirnado", {2060, 2061}, {"shiny:3050:22", "boss:9083"})}
# Round 73: the gear shops open at story 8000, and the town map each is in (data/game/shops.tsv).
# The game opens a shop from an actor in the town, not from a table, so this goes by the shops'
# names: a town and the chapter. Left out: the burning Grandshelt's, Zoldaad's from before its
# chapter is cleared, the airship's of chapters 5 to 7, an unused Grandport one, the Colosseum's
# (they open with its proofs) and Sanctissimus Shrine's. "ナシャト" is taken to be Felicitas, the
# only town in Kolobos. AIRSHIP_SHOP is the airship's own, from chapter 8.
AIRSHIP_SHOP = 0
SHOP_MAPS = {
    2001: 2000, 2002: 2010, 2004: 2030, 2005: 2060, 2006: 2050, 2007: 2040, 2008: 2070, 2009: 2090,
    2010: 2110, 2011: 2130, 2012: 2140, 2014: 2170, 2016: 2150, 2017: 2160, 2019: AIRSHIP_SHOP,
    2020: 2114, 2021: 2120,
    4001: 2000, 4002: 2010, 4005: 2040, 4006: 2060, 4007: 2050, 4008: 2114, 4009: 2120, 4012: AIRSHIP_SHOP,
    4013: 2150, 4014: 2160, 4017: 2030, 4018: 2070, 4019: 2090, 4020: 2110, 4021: 2130, 4022: 2140, 4023: 2170,
    6001: 2000, 6002: 2000, 6003: 2010, 6005: 2120, 6008: AIRSHIP_SHOP, 6010: 2030, 6011: 2070, 6012: 2090,
    6013: 2110, 6014: 2130, 6015: 2140, 6016: 2170,
    8002: 2030, 8003: 2070, 8004: 2090, 8005: 2110, 8008: 2040, 8009: AIRSHIP_SHOP, 8010: 2130, 8011: 2140,
    8013: 2170,
}
AIRSHIP_AREA = "Airship"
# The story counter on the open world start. A shiny whose condition is false there is not out.
OPEN_START_STORY = 8000
FINAL_AREA = "Crystal Tower"
OPEN_AREA = "Open"
# The party members (data/game/units.tsv, category Playable). Archwitch Fina (1006) is a member
# of her own: the game can have both Finas at once, though the story swaps them in and out
# (round 30). The guests (1013, 1014, 1016) never stay.
PARTY_MEMBER_IDS = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008]
# Valuables that are not key items of the US game, or not one-off items: DLC items
# (29500-29520), and the counted ones (Magicite 25000-25002, Tablet Shards 25004).
# Artifacts (DT_ArtifactItemData) are left out since round 55: the game has no screen to switch
# them, and the Bandit Cuff Links showed no effect when switched on (IDEAS.md, idea 26).
NOT_KEY_ITEMS = {25000, 25001, 25002, 25004, 29500, 29510, 29520}


def holds_at_open_start(condition: str) -> bool:
    """A map condition on the open world start: story 8000, every other counter 0, no flags."""
    if not condition:
        return True
    text = condition.replace("{progress:0}", str(OPEN_START_STORY))
    text = re.sub(r"\{progress:\d+\}", "0", text)
    text = re.sub(r"\{flag:\d+\}", "False", text)
    text = re.sub(r"\{item:\d+\}", "0", text)
    text = re.sub(r"!(?!=)", " not ", text).replace("&", " and ").replace("|", " or ")
    try:
        return bool(eval(text, {"__builtins__": {}}))     # the text is the game's own data
    except Exception:
        return True


def read_continents() -> dict[str, dict]:
    """The hand-drawn continent rectangles (data/continents.tsv), which the mod holds as well."""
    out: dict[str, dict] = {}
    for r in read_tsv("continents.tsv"):
        c = out.setdefault(r["name"].capitalize(), {"flag": int(r["flag"]), "boxes": []})
        c["boxes"].append((int(r["x0"]), int(r["y0"]), int(r["x1"]), int(r["y1"])))
    return out


def continent_at(continents: dict[str, dict], x: float, y: float) -> str | None:
    for name, c in continents.items():
        if any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in c["boxes"]):
            return name
    return None


def read_exits() -> tuple[dict[int, tuple[float, float, list[int]]], dict[int, set[int]]]:
    """The world map's doors (uid -> x, y, the maps it leads to) and the doors between other maps."""
    world_doors: dict[int, tuple[float, float, list[int]]] = {}
    edges: dict[int, set[int]] = collections.defaultdict(set)
    for r in read_tsv("game/transitions.tsv"):
        # Round 63: a door with a destination list goes to those maps, not to its toMap (the
        # sanctum doors on the world map all said 10200).
        targets = [int(m) for m in re.findall(r"(?:^|; )(\d+)", r.get("destinations") or "")]
        if not targets and r["toMap"]:
            targets = [int(r["toMap"])]
        source = int(r["map"])
        if source == WORLD_MAP and r["x"]:
            world_doors[int(r["uid"])] = (float(r["x"]), float(r["y"]), [t for t in targets if t != WORLD_MAP])
        elif source != WORLD_MAP:
            edges[source] |= {t for t in targets if t != WORLD_MAP}
    return world_doors, edges


def map_continents(continents: dict[str, dict]) -> dict[int, set[str]]:
    """The continents each map is entered from: world-map exits by position, then the exit graph."""
    reach: dict[int, set[str]] = collections.defaultdict(set)
    world_doors, edges = read_exits()
    frontier: list[int] = []
    for x, y, targets in world_doors.values():
        place = continent_at(continents, x, y)
        for target in targets if place else []:
            reach[target].add(place)
            frontier.append(target)
    while frontier:
        source = frontier.pop()
        for target in edges[source]:
            if not reach[source] <= reach[target]:
                reach[target] |= reach[source]
                frontier.append(target)
    return reach


def far_side_maps() -> dict[int, set[int]]:
    """Each FAR_SIDE boss's maps: those it lists and those its world-map doors lead to, with
    every map their doors lead to in turn."""
    world_doors, edges = read_exits()
    out: dict[int, set[int]] = {}
    for group, side in FAR_SIDE.items():
        found: set[int] = set()
        frontier = list(side["maps"]) + [t for uid in side["doors"] for t in world_doors[uid][2]]
        while frontier:
            source = frontier.pop()
            if source not in found:
                found.add(source)
                frontier += edges[source]
        out[group] = found
    return out


# Round 77: names a player can find (IDEAS.md idea 34). data/location_names.tsv lists every
# location: the old name, the generated one, and a `name` column for the user, which wins when it
# is filled in. The generator rewrites the file and keeps that column. Ids do not change.
NAMES_FILE = "location_names.tsv"
NAMES_COLUMNS = ["key", "old", "suggested", "name", "note"]
# A world-map spot is "near" a door within this many units, else a compass point from it.
NEAR_DOOR = 600
FAR_FROM_DOORS = 2500
COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def compass(dx: float, dy: float) -> str:
    """The world map's +X is north and +Y east (World Map Shiny 167 sits on Gronoa's NW peninsula)."""
    return COMPASS[int((math.degrees(math.atan2(dy, dx)) % 360 + 22.5) // 45) % 8]


def world_spot(x: float, y: float, doors: list[tuple[str, float, float]],
               continents: dict[str, dict]) -> tuple[str, str, float]:
    """The continent, a place by the nearest door ("NW of Rugged Mountain Path") and its distance."""
    land = continent_at(continents, x, y) or "Sea"
    dist, name, dx, dy = min((math.dist((x, y), (mx, my)), n, x - mx, y - my) for n, mx, my in doors)
    if name == "Sanctum of Light":
        name = f"{continent_at(continents, x - dx, y - dy) or 'Sea'} Sanctum"
    return land, (f"near {name}" if dist <= NEAR_DOOR else f"{compass(dx, dy)} of {name}"), dist


def readable_names(chests: list[dict], radar_part_chests: list[dict], shinies: list[dict],
                   tablet_shinies: list[dict], radar: list[dict], items: dict[int, dict],
                   maps: dict[int, dict], continents: dict[str, dict]) -> None:
    """Gives each chest, shiny, Tablet Shard and radar treasure its readable name, in place."""
    doors = []
    for x, y, targets in read_exits()[0].values():
        named = [ascii_name(maps[t]["name"]) for t in targets if t in maps and maps[t]["name"] not in ("", "Field")]
        if named:
            doors.append((named[0], x, y))
    spots = {f"shiny:{r['map']}:{r['uid']}": (float(r["x"]), float(r["y"]))
             for r in read_tsv("game/field_items.tsv") if r["kind"] == "shiny" and r["x"]}
    spots.update({f"radar:{r['n']}": (float(r["x"]), float(r["y"])) for r in read_tsv("radar.tsv")})

    suggested: dict[str, tuple[str, str]] = {}    # key -> (name, note)
    for entry in chests:
        place = entry["name"].rsplit(" Chest ", 1)[0]
        suggested[entry["key"]] = (f"{place} - {items[entry['vanilla']]['name']} Chest", "")
    places = {ascii_name(m["name"]) for m in maps.values()}
    for entry in radar_part_chests:
        # "Mt. Reizan Resonance Stone Chest": the longest map name it starts with is the place.
        words = entry["name"].removesuffix(" Chest")
        place = max((p for p in places if words.startswith(p + " ")), key=len)
        item = words[len(place) + 1:]
        suggested[entry["key"]] = (f"{place} - {item} Chest", "")
    for entry in shinies + radar:
        kind = "Shiny" if entry in shinies else "Radar Treasure"
        land, where, dist = world_spot(*spots[entry["key"]], doors, continents)
        note = f"nearest door {dist:.0f} units away" if dist > FAR_FROM_DOORS else ""
        suggested[entry["key"]] = (f"{land} - {kind} {where}", note)
    by_place: dict[str, list[dict]] = collections.defaultdict(list)
    for entry in sorted(tablet_shinies, key=lambda e: e["id"]):
        by_place[entry["name"].rsplit(" Shard ", 1)[0]].append(entry)
    for place, entries in by_place.items():
        for n, entry in enumerate(entries, start=1):
            number = f" {n}" if len(entries) > 1 else ""
            suggested[entry["key"]] = (f"{place} - Tablet Shard{number}", "where in the place: needs a person")

    # Names that come out the same are numbered, in id order.
    everything = sorted(chests + radar_part_chests + shinies + tablet_shinies + radar, key=lambda e: e["id"])
    counts = collections.Counter(suggested[e["key"]][0] for e in everything)
    seen: collections.Counter = collections.Counter()
    for entry in everything:
        name, note = suggested[entry["key"]]
        if counts[name] > 1:
            seen[name] += 1
            suggested[entry["key"]] = (f"{name} {seen[name]}", (note + "; " if note else "") + "same place as another")

    path = os.path.join(DATA, NAMES_FILE)
    chosen = {r["key"]: r["name"].strip() for r in read_tsv(NAMES_FILE)} if os.path.exists(path) else {}
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(NAMES_COLUMNS) + "\n")
        for entry in everything:
            name, note = suggested[entry["key"]]
            own = chosen.get(entry["key"], "")
            f.write("\t".join([entry["key"], entry["name"], name, own, note]) + "\n")
            entry["name"] = own or name


# Round 78: side quests (docs/side_quests.md). data/quests.tsv, by hand, lists the quest-log
# quests that are locations: the quest's counter, the value its reward row writes (the check)
# and the reward rows the mod blanks. data/game/quest_steps.tsv gives each step's map.
QUEST_LOCATION_BASE = 6_000_000_000      # + the quest's id in the game's quest log
QUESTS_LUA = os.path.join(ROOT, "FFRArchipelago", "Scripts", "quests.lua")
AIRSHIP_MAPS = {20001, 20002}            # the airship's cabin and deck
# Quest items the game never tests: each gift row moves the quest's counter, and the next step
# tests the counter (side_quests.md, section 2). They stay vanilla and out of the pool.
QUEST_ONLY_ITEMS = {20020, 20023, 20024, 20025, 20026, 20027, 20028, 20029, 20030, 20031, 20032}


def quest_name(name: str) -> str:
    return "Quest: " + ascii_name(name).replace("“", '"').replace("”", '"')


def quest_gifts(text: str) -> list[tuple[int, int]]:
    """'25000:1 -1:500' -> [(25000, 1), (-1, 500)]."""
    return [(int(i), int(n)) for i, n in (g.split(":") for g in text.split())]


def write_quests_lua(quests: list[dict]) -> None:
    with open(QUESTS_LUA, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Generated by tools/gen_apworld_data.py from data/quests.tsv. Do not edit by hand.\n")
        f.write("-- Side quests that are locations: the check is the quest's counter at or past `value`;\n")
        f.write("-- `rows` are the reward rows whose items the mod swaps for the pop-up's stand-in.\n")
        f.write("return {\n")
        for q in quests:
            rows = ", ".join(f'"{r}"' for r in q["rows"])
            f.write(f'    {{ key = "{q["key"]}", counter = {q["counter"]}, value = {q["value"]}, rows = {{ {rows} }} }},\n')
        f.write("}\n")


def is_japanese(name: str) -> bool:
    return any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in name)


def write_field_items_lua() -> None:
    """Round 72: every shiny's level id and place, for the mod. A live shiny can report another id
    (rounds 63 and 71), so the mod takes the id of the level's shiny that stands where it does."""
    by_map: dict[int, list[str]] = collections.defaultdict(list)
    for r in read_tsv("game/field_items.tsv"):
        if r["kind"] == "shiny" and r["map"] and r["x"]:
            by_map[int(r["map"])].append(f"{{ {int(r['uid'])}, {float(r['x']):.0f}, {float(r['y']):.0f} }}")
    with open(FIELD_ITEMS_LUA, "w", encoding="utf-8", newline="\n") as f:
        f.write("-- Generated by tools/gen_apworld_data.py from data/game/field_items.tsv. Do not edit by hand.\n")
        f.write("-- Each map's shinies as placed in the level: { uid, x, y }.\n")
        f.write("return {\n")
        for map_id in sorted(by_map):
            f.write(f"    [{map_id}] = {{ {', '.join(by_map[map_id])} }},\n")
        f.write("}\n")


def main() -> None:
    item_rows = read_tsv("game/items.tsv")
    names = {int(r["id"]): ascii_name(r["name"]) for r in item_rows}
    maps = {int(r["id"]): r for r in read_tsv("game/maps.tsv")}
    units = {int(r["id"]): r for r in read_tsv("game/units.tsv")}
    seen_shinies = {(r["map"], r["uid"]) for r in read_tsv("shinies.tsv")}
    items: dict[int, dict] = {}      # AP item id -> item info
    continents = read_continents()
    reach = map_continents(continents)

    def chest_area(map_id: int, row: str) -> str:
        """
        The continent a chest is on. Position decides where the exits say so: Dragon's Maw is in
        the Grandshelt table but opens on Pharm. A row's map id can be an alias with no exits
        (2001 for the capital), so the map named by the row counts too. Otherwise, its table.
        """
        region = chest_region(row)
        if region == FINAL_AREA:
            return region
        key = "_".join(row.rsplit("_", 1)[0].split("_")[1:3])
        for candidate in [map_id] + [i for i, m in maps.items() if m["key"] == key]:
            found = reach.get(candidate, set())
            if len(found) == 1:
                return next(iter(found))
        return region

    def item_for(item_id: int, count: int, money: int) -> int | None:
        kind = item_kind(item_id, money)
        if kind is None:
            return None
        if kind == "gil":
            ap_id = GIL_ITEM_BASE + money
            items.setdefault(ap_id, {"name": f"{money} Gil", "kind": "gil", "game_id": 0, "count": money,
                                     "category": "gil"})
            return ap_id
        count = max(count, 1)
        ap_id = item_id * 1000 + count
        base = names.get(item_id, f"Item {item_id}")
        items.setdefault(ap_id, {"name": base if count == 1 else f"{base} x{count}", "kind": "item",
                                 "game_id": item_id, "count": count, "category": kind})
        return ap_id

    shards_for = {(int(r["map"]), int(r["chest"])): int(r["shards"]) for r in read_tsv("game/shard_chests.tsv")}
    chests, kept_chests, radar_part_chests, no_box, no_route = [], [], [], [], []
    for r in read_tsv("game/chests.tsv"):
        map_id, chest_id = int(r["mapId"]), int(r["ID"])
        if not r["boxes"]:
            no_box.append(f"chest:{map_id}:{chest_id}")
            continue
        if map_id in NO_ROUTE_MAPS or f"chest:{map_id}:{chest_id}" in NO_ROUTE_CHESTS:
            no_route.append(f"chest:{map_id}:{chest_id}")
            continue
        item_id, count, money = int(r["ItemId"]), int(r["ItemNum"]), int(r["Money"])
        ap_item = item_for(item_id, count, money)
        entry = {"key": f"chest:{map_id}:{chest_id}", "place": chest_place(r["row"], map_id, maps),
                 "region": chest_region(r["row"]), "area": chest_area(map_id, r["row"]),
                 "open_world": True, "row": r["row"],
                 "id": CHEST_LOCATION_BASE + map_id * 1000 + chest_id, "vanilla": ap_item}
        if (map_id, chest_id) in shards_for:
            entry["shards"] = shards_for[(map_id, chest_id)]
        if item_id in RADAR_PART_GAME_IDS:
            entry["vanilla"] = item_for(POTION, 1, -1)
            entry["name"] = f"{entry.pop('place')} {ascii_name(names[item_id])} Chest"
            radar_part_chests.append(entry)
            continue
        (chests if ap_item is not None else kept_chests).append(entry)

    # Chests are numbered from 1 within each place name, in the order of their AP ids (map id,
    # then row ID). A place can span maps (the Earth Shrine is maps 3000 and 3001).
    numbered: dict[str, int] = {}
    for entry in sorted(chests, key=lambda e: e["id"]):
        numbered[entry["place"]] = numbered.get(entry["place"], 0) + 1
        entry["name"] = f"{entry['place']} Chest {numbered[entry['place']]}"
    for entry in chests + kept_chests:
        entry.pop("place")

    def map_area(map_id: int) -> str:
        """The continent a map is on: by its exits where they say so, else by its code (01Gra_02)."""
        found = reach.get(map_id, set())
        if len(found) == 1:
            return next(iter(found))
        key = (maps.get(map_id) or {}).get("key") or ""
        code = key.split("_")[0][2:]
        return REGION_NAMES.get(code, OPEN_AREA)

    shinies, kept_shinies, tablet_shinies = [], [], []
    for r in read_tsv("game/field_items.tsv"):
        if r["kind"] != "shiny" or not r["map"]:
            continue
        map_id, uid = int(r["map"]), int(r["uid"])
        ap_item = item_for(int(r["item"]), int(r["count"]), int(r["money"]))
        place = "World Map" if map_id == WORLD_MAP else f"Map {map_id}"
        area = OPEN_AREA
        if map_id == WORLD_MAP and r["x"]:
            area = continent_at(continents, float(r["x"]), float(r["y"])) or OPEN_AREA
        entry = {"key": f"shiny:{map_id}:{uid}", "name": f"{place} Shiny {uid}", "region": place, "area": area,
                 "open_world": holds_at_open_start(r.get("visible") or ""),
                 "id": SHINY_LOCATION_BASE + map_id * 1000 + uid, "vanilla": ap_item,
                 "condition": r.get("visible") or "", "seen": (r["map"], r["uid"]) in seen_shinies}
        if ap_item is not None and int(r["item"]) == TABLET_SHARD:
            place = ascii_name((maps.get(map_id) or {}).get("name") or f"Map {map_id}")
            entry.update({"name": f"{place} Shard {uid}", "region": "Tablet Shards", "area": map_area(map_id),
                          "open_world": map_id not in NO_ROUTE_MAPS and holds_at_open_start(r.get("visible") or "")})
            tablet_shinies.append(entry)
            continue
        (shinies if ap_item is not None else kept_shinies).append(entry)

    # Progression items: party members, visions and key items, one of each.
    progression: dict[str, list[int]] = {"party": [], "vision": [], "key": []}
    for unit_id in PARTY_MEMBER_IDS:
        ap_id = UNIT_ITEM_BASE + unit_id
        items[ap_id] = {"name": units[unit_id]["name"], "kind": "unit", "game_id": unit_id, "count": 1,
                        "category": "party"}
        progression["party"].append(ap_id)
    # The sanctum crystals (data/crystals.tsv): a location each, with no vanilla item of their own
    # to add, since their visions are already in the pool. The door into the sanctum decides the
    # continent. Round 63: the airship landing points did before, and their ids do not match the
    # sanctums (the Warrior of Light's and Cloud's are on Lanzelt, not Kolobos and Dirnado).
    landing = {r["id"]: r for r in read_tsv("game/gimmicks.tsv") if r["class"] == "BP_MapAirShipLandingPoint_C"}
    island_names = {"MagiNationMysidia": "Mysidia"}
    crystals = []
    for r in read_tsv("crystals.tsv"):
        map_id = int(r["map"])
        point = landing.get(r["map"])
        doors = reach.get(map_id, set())
        area = next(iter(doors)) if len(doors) == 1 else None
        if area is None and point:
            area = continent_at(continents, float(point["x"]), float(point["y"]))
        if area is None:
            island = maps[map_id]["island"]
            area = island_names.get(island, island)
        crystals.append({"key": f"crystal:{map_id}", "name": f"Sanctum of Light ({names[int(r['vision'])]})",
                         "region": "Sanctums", "area": area, "open_world": True,
                         "id": CRYSTAL_LOCATION_BASE + map_id, "vanilla": None,
                         "vision": int(r["vision"]) * 1000 + 1})
    crystals.sort(key=lambda e: e["id"])
    # Boss fights (data/bosses.tsv). A cave master's own reward (Magicite) goes into the pool.
    bosses, boss_maps = [], {}
    for r in read_tsv("bosses.tsv"):
        group, map_id = int(r["group"]), int(r["map"])
        boss_maps[f"boss:{group}"] = map_id
        # Round 69: a boss on the world map (the Antlion) names its place and continent itself.
        place = "Lanzelt Desert" if map_id == WORLD_MAP else ascii_name(maps[map_id]["name"])
        name = place if r["kind"] == "cave" else f"{place}: {r['name']}"
        reward = int(r["reward"]) if r["reward"] else 0
        vanilla = item_for(reward, 1, 0) if r["kind"] == "cave" else None
        entry = {"key": f"boss:{group}", "name": name, "region": "Bosses", "area": r.get("area") or map_area(map_id),
                 "open_world": True, "id": BOSS_LOCATION_BASE + group, "vanilla": vanilla,
                 "fragment": r["kind"] == "story", "tier": r["tier"], "level": int(r["level"])}
        if r["kind"] != "cave" and reward >= SHUFFLE_ID_LIMIT:
            entry["vision"] = reward * 1000 + 1
        bosses.append(entry)
    bosses.sort(key=lambda e: e["id"])

    # Round 73: what each party member (by level), Vision (by awakening) and piece of shop gear
    # does in a boss fight (data/game/capabilities.tsv, docs/boss_logic.md). Gear counts only
    # where an open shop sells it, never from the item pool (the user's call).
    shop_areas: dict[int, set[str]] = collections.defaultdict(set)
    # Gear sold past a boss does not count: it could not help with that boss, and the rule would
    # need itself.
    far_side = far_side_maps()
    past_a_boss = set(AFTER_BOSS).union(*far_side.values())
    for r in read_tsv("game/shops.tsv"):
        town = SHOP_MAPS.get(int(r["shop"]))
        if town is not None and town not in past_a_boss and int(r["item"]) > 0:
            shop_areas[int(r["item"])].add(AIRSHIP_AREA if town == AIRSHIP_SHOP else map_area(town))
    capabilities: dict[str, dict] = {}
    for r in read_tsv("game/capabilities.tsv"):
        cap = capabilities.setdefault(r["capability"], {"party": {}, "vision": {}, "gear": {}})
        owner, level = int(r["id"]), int(r["level"])
        if r["source"] == "party":
            cap["party"][owner] = min(level, cap["party"].get(owner, level))
        elif r["source"] == "vision":
            ap_id = owner * 1000 + 1
            cap["vision"][ap_id] = min(level, cap["vision"].get(ap_id, level))
        elif owner in shop_areas:
            cap["gear"][owner] = {"who": [int(u) for u in r["who"].split(",")], "shops": sorted(shop_areas[owner])}
    items[FRAGMENT_ITEM] = {"name": FRAGMENT_NAME, "kind": "token", "game_id": 0, "count": 1, "category": "fragment"}
    items[CHOCOBO_ITEM] = {"name": "Chocobo", "kind": "item", "game_id": CHOCOBO_GAME_ID, "count": 1, "category": "vehicle"}
    items[CONTINENT_ITEM_BASE + AIRSHIP_FLAG] = {"name": "Airship", "kind": "flag", "game_id": AIRSHIP_FLAG, "count": 1,
                                                 "category": "vehicle"}
    items[RADAR_ITEM] = {"name": "Progressive Radar", "kind": "item", "game_id": RADAR_GAME_ID, "count": 1,
                         "category": "radar"}
    # Round 72: the radar's treasures lie at sea, dug from the airship. In the game each pinger
    # needs the one before it found ({progress:51}); round 75: the mod holds that count at the
    # top of the radar's tier, so a tier opens at once. Their rewards join the pool.
    radar = []
    for r in read_tsv("radar.tsv"):
        n = int(r["n"])
        radar.append({"key": f"radar:{n}", "name": f"Radar Treasure {n}", "region": "Radar Treasures",
                      "area": OPEN_AREA, "open_world": True, "id": RADAR_LOCATION_BASE + n,
                      "vanilla": item_for(int(r["reward"]), 1, 0), "radar_tier": int(r["tier"]),
                      "flag": int(r["found_flag"]), "row": r["row"], "airship": True})
    # Round 78: side quests. A quest needs, for each value its counter passes on the way to the
    # reward, one of the continents where a step writes that value. A world-map step's continent
    # comes from its position, an airship step needs the Airship. A quest that starts after
    # another needs that one's steps too.
    log = {int(r["id"]): r for r in read_tsv("game/quests.tsv")}
    quest_steps = read_tsv("game/quest_steps.tsv")
    vision_ids = {int(r["id"]) for r in item_rows if r["table"] == "vision"}

    def step_area(r: dict) -> str | None:
        if not r["map"]:
            return None          # no map actor leads to it (a quest board's delivery)
        map_id = int(r["map"])
        if map_id in AIRSHIP_MAPS:
            return AIRSHIP_AREA
        if map_id == WORLD_MAP:
            return continent_at(continents, float(r["x"]), float(r["y"])) if r["x"] else None
        return map_area(map_id)

    def quest_needs(counter: int, value: int) -> set[tuple[str, ...]]:
        """
        Groups of places, one of each group needed. Where one event starts a step in several
        places (an inn's rest), any of them does. Where different events start it (Forger of
        Wills: three NPCs, each moving the counter on by one, in any order), all of them are needed.
        """
        by_value: dict[int, set[tuple[str, str]]] = collections.defaultdict(set)
        for r in quest_steps:
            if int(r["counter"]) == counter and 0 < int(r["value"]) <= value:
                area = step_area(r)
                if area is not None:
                    by_value[int(r["value"])].add((r["start"], area))
        groups: set[tuple[str, ...]] = set()
        for found in by_value.values():
            areas = {area for _, area in found}
            if len({start for start, _ in found}) == 1:
                groups.add(tuple(sorted(areas)))
            else:
                groups |= {(area,) for area in areas}
        # A group with a place open from the start needs nothing.
        return {g for g in groups if OPEN_AREA not in g}

    side_quests, quest_rows = [], read_tsv("quests.tsv")
    groups_of = {int(r["quest"]): quest_needs(int(r["counter"]), int(r["value"])) for r in quest_rows}
    for r in quest_rows:
        quest, counter, value = int(r["quest"]), int(r["counter"]), int(r["value"])
        rows = r["rows"].split(",")
        for row in rows:
            found = [s for s in quest_steps if s["row"] == row]
            assert found and all((int(s["counter"]), int(s["value"])) == (counter, value) for s in found), \
                f"quests.tsv: {row} does not write progress {counter} = {value}"
        needs = [int(n) for n in r["needs"].split(",") if n]
        groups = set(groups_of[quest]).union(*(groups_of[n] for n in needs))
        gifts_of = next(s["gifts"] for s in quest_steps if s["row"] == rows[0])
        entry = {"key": f"quest:{quest}", "name": quest_name(log[quest]["name"]), "region": "Side Quests",
                 "area": OPEN_AREA, "open_world": True, "id": QUEST_LOCATION_BASE + quest, "vanilla": None,
                 "counter": counter, "value": value, "rows": rows, "steps": sorted(groups),
                 "after": [f"quest:{n}" for n in needs]}
        for item_id, count in quest_gifts(gifts_of):
            if item_id in vision_ids:
                entry["vision"] = item_id * 1000 + 1
            elif item_id >= 0 and entry["vanilla"] is None:
                entry["vanilla"] = item_for(item_id, count, -1)
        assert entry["vanilla"] is not None, f"quests.tsv: quest {quest} gives no item that can move"
        side_quests.append(entry)
    side_quests.sort(key=lambda e: e["id"])

    # A continent's unlock turns on its event flag; Ardra has no locations, so it has no unlock.
    # One name can cover two maps (the Earth Shrine), so a repeat gets its map id.
    counts = collections.Counter(e["name"] for e in tablet_shinies)
    for entry in tablet_shinies:
        if counts[entry["name"]] > 1:
            entry["name"] = f"{entry['name']} (Map {entry['key'].split(':')[1]})"
    tablet_shinies.sort(key=lambda e: e["id"])
    used_areas = {e["area"] for e in chests + radar_part_chests + shinies + crystals + tablet_shinies + bosses}
    unlocks: dict[str, int] = {}
    for name, continent in continents.items():
        if name in used_areas:
            ap_id = CONTINENT_ITEM_BASE + continent["flag"]
            items[ap_id] = {"name": f"{name} Unlock", "kind": "flag", "game_id": continent["flag"], "count": 1,
                            "category": "continent"}
            unlocks[name] = ap_id
    for r in item_rows:
        item_id, name = int(r["id"]), names[int(r["id"])]
        if r["table"] == "vision":
            category, kind = "vision", "vision"
        elif r["table"] == "valuable":
            if item_id in NOT_KEY_ITEMS or name.startswith("[TEMP]") or is_japanese(name):
                continue
            category, kind = "key", "item"
        else:
            continue
        ap_id = item_id * 1000 + 1
        items[ap_id] = {"name": name, "kind": kind, "game_id": item_id, "count": 1, "category": category}
        if item_id not in QUEST_ONLY_ITEMS:
            progression[category].append(ap_id)

    # Item names must be unique: two ids with one English name get the id appended. A vision
    # shares its name with a party member or a unit (Charlotte): it gets "Vision" after it.
    for ap_id, info in items.items():
        if info["category"] == "vision":
            info["name"] = f"{info['name']} (Vision)"
    seen: dict[str, int] = {}
    for ap_id in sorted(items):
        name = items[ap_id]["name"]
        if name in seen:
            items[ap_id]["name"] = f"{name} ({items[ap_id]['game_id']})"
        seen[items[ap_id]["name"]] = ap_id

    chests.sort(key=lambda e: e["id"])
    shinies.sort(key=lambda e: e["id"])
    # Round 57: data/gates.tsv, by hand from play: the items a location needs (game item ids).
    by_key = {e["key"]: e for e in chests + radar_part_chests + shinies + tablet_shinies}
    for r in read_tsv("gates.tsv"):
        assert r["location"] in by_key, f"gates.tsv: no location {r['location']}"
        by_key[r["location"]]["needs"] = [int(i) * 1000 + 1 for i in r["needs"].split(",")]
    # Round 71: data/airship_only.tsv, by hand from play: places only the airship can reach.
    by_key.update({e["key"]: e for e in crystals + bosses})
    for r in read_tsv("airship_only.tsv"):
        assert r["location"] in by_key, f"airship_only.tsv: no location {r['location']}"
        by_key[r["location"]]["airship"] = True
    def location_map(key: str) -> int:
        return boss_maps[key] if key.startswith("boss:") else int(key.split(":")[1])

    # A map's gate fights (Sanctissimus Shrine's first three) are not past each other.
    for key, entry in by_key.items():
        groups = AFTER_BOSS.get(location_map(key), [])
        if groups and key not in {f"boss:{g}" for g in groups}:
            entry["after_boss"] = list(groups)
    for group, keys in AFTER_BOSS_KEYS.items():
        for key in keys:
            assert key in by_key, f"AFTER_BOSS_KEYS: no location {key}"
            by_key[key].setdefault("after_boss", []).append(group)
    for group, side in FAR_SIDE.items():
        for key in side["keys"]:
            assert key in by_key, f"FAR_SIDE: no location {key}"
        for key, entry in by_key.items():
            if key == f"boss:{group}" or not (location_map(key) in far_side[group] or key in side["keys"]):
                continue
            if side["airship"]:
                assert "past_boss" not in entry, f"{key} is past two bosses on foot"
                entry["past_boss"] = group
            else:
                entry.setdefault("after_boss", []).append(group)
    for group, (area, near_maps, near_keys) in PAST_BOSS_ON_FOOT.items():
        for key, entry in by_key.items():
            kind, place = key.split(":")[:2]
            near = key in near_keys or (kind in ("chest", "shiny") and int(place) in near_maps)
            if entry["area"] == area and not near:
                entry["past_boss"] = group
    readable_names(chests, radar_part_chests, shinies, tablet_shinies, radar, items, maps, continents)
    location_names = [e["name"] for e in chests + radar_part_chests + shinies + crystals + tablet_shinies + bosses
                      + radar + side_quests]
    assert len(location_names) == len(set(location_names)), "duplicate location names"

    write_field_items_lua()
    write_quests_lua(side_quests)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write('"""Generated by tools/gen_apworld_data.py from data/*.tsv. Do not edit by hand."""\n\n')
        f.write(f"SHUFFLE_ID_LIMIT = {SHUFFLE_ID_LIMIT}\n\n")
        f.write("# AP item id -> name, kind (item | gil), game item id, count, category\n")
        f.write("ITEMS = " + pprint.pformat(items, width=110, sort_dicts=True) + "\n\n")
        f.write("# Chest locations: key (as the mod reports it), name, region, row, AP id, vanilla AP item\n")
        f.write("CHESTS = " + pprint.pformat(chests, width=110, sort_dicts=True) + "\n\n")
        f.write("# Shiny locations (data/game/field_items.tsv); condition is the spot's VisibleCondition,\n"
                "# seen is whether it was seen in game (data/shinies.tsv)\n")
        f.write("SHINIES = " + pprint.pformat(shinies, width=110, sort_dicts=True) + "\n\n")
        f.write("# Shinies holding a Tablet Shard (round 47)\n")
        f.write("TABLET_SHINIES = " + pprint.pformat(tablet_shinies, width=110, sort_dicts=True) + "\n\n")
        f.write("# The sanctum crystals; vanilla is None, as their visions are in the pool already\n")
        f.write("CRYSTALS = " + pprint.pformat(crystals, width=110, sort_dicts=True) + "\n\n")
        f.write("# Boss fights (data/bosses.tsv); fragment marks the ones that hold a locked Crystal Fragment\n")
        f.write("BOSSES = " + pprint.pformat(bosses, width=110, sort_dicts=True) + "\n\n")
        f.write("# What helps in a boss fight (data/game/capabilities.tsv): party members by unit id and the\n"
                "# level they learn it, Visions by AP id and awakening, shop gear by item id with who can\n"
                "# wear it and the areas whose shops sell it\n")
        f.write("CAPABILITIES = " + pprint.pformat(capabilities, width=110, sort_dicts=True) + "\n\n")
        f.write(f"AIRSHIP_AREA = {AIRSHIP_AREA!r}\n\n")
        f.write(f"FRAGMENT_ITEM = {FRAGMENT_ITEM}\n\n")
        f.write(f"CHOCOBO_ITEM = {CHOCOBO_ITEM}\n\n")
        f.write("# The airship radar's treasures (data/radar.tsv): tier is how many Progressive Radars they need\n")
        f.write("RADAR = " + pprint.pformat(radar, width=110, sort_dicts=True) + "\n\n")
        f.write(f"RADAR_ITEM = {RADAR_ITEM}\n")
        f.write(f"RADAR_PARTS = {RADAR_PARTS}\n\n")
        f.write("# Chests holding a radar part: locations with the radar's treasures, a Potion in the pool\n")
        f.write("RADAR_PART_CHESTS = " + pprint.pformat(radar_part_chests, width=110, sort_dicts=True) + "\n\n")
        f.write(f"AIRSHIP_ITEM = {CONTINENT_ITEM_BASE + AIRSHIP_FLAG}\n\n")
        f.write("# Side quests (data/quests.tsv): the check is progress `counter` at or past `value`; steps are\n"
                "# the places it needs, one continent of each group; vision is a vision the reward gives\n")
        f.write("SIDE_QUESTS = " + pprint.pformat(side_quests, width=110, sort_dicts=True) + "\n\n")
        f.write("# Chests and shinies that keep vanilla key items or valuables: not locations\n")
        f.write("KEPT_VANILLA = " + pprint.pformat(sorted(e["key"] for e in kept_chests + kept_shinies), width=110) + "\n\n")
        f.write("# Chest table rows with no box placed on any map: not locations\n")
        f.write("NO_BOX = " + pprint.pformat(sorted(no_box), width=110) + "\n\n")
        f.write("# Chest rows with no route at story 8000 (the burning castle, one castle room): not locations\n")
        f.write("NO_ROUTE = " + pprint.pformat(sorted(no_route), width=110) + "\n\n")
        f.write("# Progression items by group (AP ids): party members, visions, key items. One of each goes\n"
                "# in the pool when its option is on, except the party members a player starts with.\n")
        f.write("PROGRESSION = " + pprint.pformat(progression, width=110, sort_dicts=True) + "\n\n")
        f.write("# Continent name -> the AP id of its unlock item\n")
        f.write("CONTINENT_UNLOCKS = " + pprint.pformat(unlocks, width=110, sort_dicts=False) + "\n\n")
        f.write(f"UNIT_ITEM_BASE = {UNIT_ITEM_BASE}\n")
        f.write(f"FINAL_AREA = {FINAL_AREA!r}\n")
        f.write(f"OPEN_AREA = {OPEN_AREA!r}\n")
    print(f"{len(chests)} chest locations ({len(kept_chests)} kept vanilla, {len(no_box)} with no box), "
          f"{len(shinies)} shiny locations ({len(kept_shinies)} kept vanilla), {len(items)} items "
          f"({len(progression['party'])} party members, {len(progression['vision'])} visions, "
          f"{len(progression['key'])} key items) -> {OUT}")


if __name__ == "__main__":
    main()
