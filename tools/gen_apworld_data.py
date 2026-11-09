"""Generates apworld/ff_resonance/data.py from the tables in data/.

    python tools/gen_apworld_data.py

Inputs, from the game's own files (tools/dump_game, then tools/gen_from_dump.py):
    data/game/items.tsv            item id -> English name
    data/game/chests.tsv           every chest table row, with the placed boxes that are its box
    data/game/field_items.tsv      every field item (shiny) placed on a map
And from play:
    data/shinies.tsv               shinies seen in game (the mod's seen.tsv): marks a shiny "seen"

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
"""

import collections
import csv
import os
import pprint
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(ROOT, "apworld", "ff_resonance", "data.py")

SHUFFLE_ID_LIMIT = 13000          # item ids at or above this never move (visions, key items)
CONSUMABLE_LIMIT = 1000

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
# Maps with no route on the open world start, so their chests may only hold filler (world 0.4.0).
# Each is entered only from a story event, or lies behind a map that is: the Earth Shrine's inner
# part (3000), the burning Grandshelt Castle (3020), the Imperial Residences (2113) and Fina's
# Psyche (3211, 3212). From data/game/transitions.tsv and the talk event table, not from play.
NO_OPEN_WORLD_ROUTE = {3000, 3020, 2113, 3211, 3212}
# The story counter on the open world start. A shiny whose condition is false there is not out.
OPEN_START_STORY = 8000
FINAL_AREA = "Crystal Tower"
OPEN_AREA = "Open"
# The party members (data/game/units.tsv, category Playable). Archwitch Fina (1006) is a member
# of her own: the game can have both Finas at once, though the story swaps them in and out
# (round 30). The guests (1013, 1014, 1016) never stay.
PARTY_MEMBER_IDS = [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008]
# Valuables and artifacts that are not key items of the US game, or not one-off items:
# DLC items (29500-29520), and the counted ones (Magicite 25000-25002, Tablet Shards 25004).
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


def map_continents(continents: dict[str, dict]) -> dict[int, set[str]]:
    """The continents each map is entered from: world-map exits by position, then the exit graph."""
    reach: dict[int, set[str]] = collections.defaultdict(set)
    edges: dict[int, set[int]] = collections.defaultdict(set)
    frontier: list[int] = []
    for r in read_tsv("game/transitions.tsv"):
        if not r["toMap"]:
            continue
        source, target = int(r["map"]), int(r["toMap"])
        if source == WORLD_MAP and target != WORLD_MAP and r["x"]:
            place = continent_at(continents, float(r["x"]), float(r["y"]))
            if place:
                reach[target].add(place)
                frontier.append(target)
        elif source != WORLD_MAP and target != WORLD_MAP:
            edges[source].add(target)
    while frontier:
        source = frontier.pop()
        for target in edges[source]:
            if not reach[source] <= reach[target]:
                reach[target] |= reach[source]
                frontier.append(target)
    return reach


def is_japanese(name: str) -> bool:
    return any("぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" for ch in name)


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

    chests, kept_chests, no_box = [], [], []
    for r in read_tsv("game/chests.tsv"):
        map_id, chest_id = int(r["mapId"]), int(r["ID"])
        if not r["boxes"]:
            no_box.append(f"chest:{map_id}:{chest_id}")
            continue
        item_id, count, money = int(r["ItemId"]), int(r["ItemNum"]), int(r["Money"])
        ap_item = item_for(item_id, count, money)
        entry = {"key": f"chest:{map_id}:{chest_id}", "place": chest_place(r["row"], map_id, maps),
                 "region": chest_region(r["row"]), "area": chest_area(map_id, r["row"]),
                 "open_world": map_id not in NO_OPEN_WORLD_ROUTE, "row": r["row"],
                 "id": CHEST_LOCATION_BASE + map_id * 1000 + chest_id, "vanilla": ap_item}
        (chests if ap_item is not None else kept_chests).append(entry)

    # Chests are numbered from 1 within each place name, in the order of their AP ids (map id,
    # then row ID). A place can span maps (the Earth Shrine is maps 3000 and 3001).
    numbered: dict[str, int] = {}
    for entry in sorted(chests, key=lambda e: e["id"]):
        numbered[entry["place"]] = numbered.get(entry["place"], 0) + 1
        entry["name"] = f"{entry['place']} Chest {numbered[entry['place']]}"
    for entry in chests + kept_chests:
        entry.pop("place")

    shinies, kept_shinies = [], []
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
        (shinies if ap_item is not None else kept_shinies).append(entry)

    # Progression items: party members, visions and key items, one of each.
    progression: dict[str, list[int]] = {"party": [], "vision": [], "key": []}
    for unit_id in PARTY_MEMBER_IDS:
        ap_id = UNIT_ITEM_BASE + unit_id
        items[ap_id] = {"name": units[unit_id]["name"], "kind": "unit", "game_id": unit_id, "count": 1,
                        "category": "party"}
        progression["party"].append(ap_id)
    # A continent's unlock turns on its event flag; Ardra has no locations, so it has no unlock.
    used_areas = {e["area"] for e in chests + shinies}
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
        elif r["table"] in ("valuable", "artifact"):
            if item_id in NOT_KEY_ITEMS or name.startswith("[TEMP]") or is_japanese(name):
                continue
            category, kind = "key", "item"
        else:
            continue
        ap_id = item_id * 1000 + 1
        items[ap_id] = {"name": name, "kind": kind, "game_id": item_id, "count": 1, "category": category}
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
    location_names = [e["name"] for e in chests + shinies]
    assert len(location_names) == len(set(location_names)), "duplicate location names"

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
        f.write("# Chests and shinies that keep vanilla key items or valuables: not locations\n")
        f.write("KEPT_VANILLA = " + pprint.pformat(sorted(e["key"] for e in kept_chests + kept_shinies), width=110) + "\n\n")
        f.write("# Chest table rows with no box placed on any map: not locations\n")
        f.write("NO_BOX = " + pprint.pformat(sorted(no_box), width=110) + "\n\n")
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
