"""Turns the game dump (dump/, from tools/dump_game) into tables in data/game/.

    dotnet run --project tools/dump_game -- all     # first, once per game version
    python tools/gen_from_dump.py                   # writes data/game/*.tsv
    python tools/gen_from_dump.py --check           # also compares them with data/*.tsv

The dump is the game's own data, read from its pak files, so these tables are the
reference, and tools/gen_apworld_data.py builds the world from them. data/chests.tsv
(ffrap_export) and data/shinies.tsv (shinies seen in game) are records from play;
--check lists where they differ from the dump.

Outputs (data/game/):
    items.tsv        every item in the six item tables: id, table, type, detail, name, prices
    units.tsv        every unit: playable characters, visions, summons ("Beast"), enemies, bosses
    maps.tsv         every map: id, key, English name, island, group
    chests.tsv       every treasure box row, in the columns of data/chests.tsv
    field_items.tsv  every field item placed on a map, in the columns of data/shinies.tsv
    transitions.tsv  every map exit: from map, to map and point, and its condition
    gimmicks.tsv     blockers, no-entry zones, doors, event triggers, airship landing points
    shops.tsv        every shop's stock, one row per item
"""

import argparse
import csv
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP = os.path.join(ROOT, "dump")
DATA = os.path.join(ROOT, "data")
OUT = os.path.join(DATA, "game")
TABLES = "tables/FFRS/Content/Datatable"

ITEM_TABLES = [
    ("consumable", "Item/DT_ConsumablesItemData"),
    ("seed", "Item/DT_SeedItemData"),
    ("equipment", "Item/DT_EquipmentItemData"),
    ("vision", "Item/Vision/DT_VisionItemData"),
    ("valuable", "Item/DT_ValuableItemData"),
    ("artifact", "Item/DT_ArtifactItemData"),
]

# Map actor classes that go into gimmicks.tsv (a regular expression on the class name).
GIMMICK_CLASSES = re.compile(
    r"BlockingBox|BlockingBase|NoEntry|Door|EventTrigger|InteractEventTrigger|AirShipLandingPoint|"
    r"GetOffPoint|Warp|Gate|Raft|Elevator|BlockingVolume|SavePoint")
FIELD_ITEM = re.compile(r"FieldItem")
TREASURE = re.compile(r"TreasureBox")
TRANSITION = re.compile(r"TransitionTrigger")
LAYER_SUFFIX = re.compile(r"_(GD|EV|BG|SD|LT|BG\d*)$")
MAP_PREFIX = re.compile(r"^(Town|Dng|Com|Event|Btl|Wld)_")


def load(rel):
    with open(os.path.join(DUMP, rel), encoding="utf-8") as f:
        return json.load(f)


def table_rows(rel):
    return load(f"{TABLES}/{rel}.json").get("Rows", {})


def text(value):
    """The English text of an FText, or the value itself."""
    if isinstance(value, dict):
        found = value.get("LocalizedString")
        if not found or found.startswith("<MISSING"):
            found = value.get("SourceString") or ""
        return found.strip()
    return "" if value is None else str(value).strip()


def enum(value):
    """eItemType::Valuable -> Valuable."""
    return str(value).split("::")[-1] if value is not None else ""


def clean(value):
    return str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ").strip()


def write_tsv(name, header, rows):
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, name), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([clean(v) for v in r])
    print(f"{name}: {len(rows)} rows")


def read_tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# ---------------------------------------------------------------- items, units, maps, shops

def items():
    rows = []
    for table, rel in ITEM_TABLES:
        for key, r in table_rows(rel).items():
            detail = enum(r.get("equipmentDetailType") or r.get("EquipmentType") or "")
            rows.append([r["ID"], table, enum(r.get("ItemType")), detail, text(r.get("Name")) or key,
                         r.get("buyingPrice", ""), r.get("sellingPrice", ""),
                         str(r.get("isAvailableSale", "")).lower(), key])
    rows.sort(key=lambda r: r[0])
    write_tsv("items.tsv", ["id", "table", "type", "detail", "name", "buy", "sell", "sellable", "row"], rows)
    return rows


# Round 56: Oblivion Palace (map 2031) opens its chests one by one as Tablet Shards are turned in.
# DT_TalkEvent_CollectMedal has one row per chest: the shards needed in all (Num), the side quest
# step it belongs to (progress 43) and the chest's ID in map 2031 (TreasureBoxItemId).
SHARD_CHEST_MAP = 2031


def shard_chests():
    rows = [[SHARD_CHEST_MAP, r["TreasureBoxItemId"], r["Num"], r["Condition"], text(r.get("Text")), key]
            for key, r in table_rows("Event/Data/CollectMedal/DT_TalkEvent_CollectMedal").items()]
    rows.sort(key=lambda r: r[1])
    write_tsv("shard_chests.tsv", ["map", "chest", "shards", "condition", "room", "row"], rows)


def units():
    rows = []
    for key, r in table_rows("Unit/DT_UnitParameter").items():
        rows.append([r["ID"], enum(r.get("Category")), enum(r.get("Race")), text(r.get("Name")) or key,
                     r.get("Level", ""), key])
    rows.sort(key=lambda r: r[0])
    write_tsv("units.tsv", ["id", "category", "race", "name", "level", "row"], rows)


def maps():
    rows, by_key = [], {}
    for path in sorted(glob.glob(os.path.join(DUMP, TABLES, "Map/MapData/DT_MapData_*.json"))):
        for key, r in load(os.path.relpath(path, DUMP))["Rows"].items():
            rows.append([r["ID"], key, text(r.get("Name")), enum(r.get("island")), r.get("GroupId", ""),
                         os.path.basename(path)[:-5]])
            by_key[key] = r["ID"]
    rows.sort(key=lambda r: r[0])
    write_tsv("maps.tsv", ["id", "key", "name", "island", "group", "table"], rows)
    return by_key


def shops():
    rows = []
    for key, r in table_rows("Shop/DT_ShopList").items():
        for i in r.get("ItemList") or []:
            rows.append([r["ShopID"], key, i.get("ItemId"), i.get("Condition", ""), i.get("MaxOrderNum", ""),
                         i.get("PriceRatio", "")])
    write_tsv("shops.tsv", ["shop", "row", "item", "condition", "max", "price_ratio"], rows)


# ---------------------------------------------------------------- chests

CHEST_COLUMNS = ["row", "mapId", "ID", "ItemId", "ItemNum", "Money", "IsTrap", "battleGroupId"]


def box_matches(row, box):
    """Whether a placed box (a treasure_actors row) is this chest table row's box.

    The box's m_Id is the row's ID, and either the box's level is the row's map, or the
    level's name starts with the row's table name. Both are needed: row 2001:0 is in level
    Town_01Gra_02_01 (map 2011), and row Town_01Gra_02_3 (map 2015) in level Town_01Gra_04_01.
    Round 3 confirmed both in game. A box with no m_Id (-1) is a story chest with no row.
    """
    if str(box[1]) != str(row[2]):
        return False
    table = row[0].rsplit("_", 1)[0]
    return str(box[0]) == str(row[1]) or box[5] == table or box[5].startswith(table + "_")


def chests(box_rows):
    """Every row of the treasure box tables, in CDT_MapGimmickTreasureBox's parent order,
    with the placed boxes that are its box (level:uid). A row with none is not a location."""
    composite = load(f"{TABLES}/Map/Gimmick/TreasureBox/CDT_MapGimmickTreasureBox.json")
    rows = []
    for parent in composite["Properties"]["ParentTables"]:
        if not parent:
            continue
        name = parent["ObjectPath"].split("/")[-1].split(".")[0]
        for key, r in table_rows(f"Map/Gimmick/TreasureBox/{name}").items():
            rows.append([key, r["mapId"], r["ID"], r["ItemId"], r["ItemNum"], r["Money"],
                         str(r["IsTrap"]).lower(), r["battleGroupId"]])
    for row in rows:
        row.append(" ".join(f"{b[5]}:{b[2]}" for b in box_rows if box_matches(row, b)))
    write_tsv("chests.tsv", CHEST_COLUMNS + ["boxes"], rows)
    return rows


# ---------------------------------------------------------------- map actors

class Classes:
    """Class defaults from dump/maps/classes.json, merged down the parent chain."""

    def __init__(self):
        self.raw = load("maps/classes.json")
        self.cache = {}

    def defaults(self, cls):
        if cls in self.cache:
            return self.cache[cls]
        entry = self.raw.get(cls) or {}
        merged = dict(self.defaults(entry["super"])) if entry.get("super") else {}
        if isinstance(entry.get("defaults"), dict):
            merged.update(entry["defaults"])
        self.cache[cls] = merged
        return merged


def map_id(path, by_key):
    """FFRS/Content/Map/Dng/01Gra/01Gra_40/GD/Dng_01Gra_40_GD.json -> 3000."""
    stem = LAYER_SUFFIX.sub("", os.path.basename(path)[:-5])
    if stem.startswith("Wld_"):
        return by_key.get("Wld", ""), stem
    key = MAP_PREFIX.sub("", stem)
    while key:
        if key in by_key:
            return by_key[key], stem
        if "_" not in key:
            break
        key = key.rsplit("_", 1)[0]
    return "", stem


def condition(props):
    for name in ("VisibleCondition", "m_FlagCondition", "m_Condition"):
        if props.get(name):
            return props[name]
    return ""


def events(props):
    out = []
    for name in ("m_EventList", "m_EventList2", "m_AfterTransitionEventList"):
        for e in props.get(name) or []:
            if isinstance(e, dict) and e.get("EventId") not in (None, "None", "FieldItem"):
                out.append(f"{e['EventId']}" + (f"[{e['Condition']}]" if e.get("Condition") else ""))
    return " ".join(out)


def location(actor):
    loc = actor.get("RootLocation") or {}
    if not isinstance(loc, dict):
        return ["", "", ""]
    return [round(loc.get(a, 0)) for a in "XYZ"]


def actors(by_key):
    classes = Classes()
    fields, transitions, gimmicks, boxes = [], [], [], []
    for entry in load("maps/index.json"):
        path = entry["path"]
        mid, stem = map_id(path, by_key)
        for a in load("maps/" + path):
            cls = a["Type"]
            props = dict(classes.defaults(cls))
            props.update(a.get("Properties") or {})
            uid = props.get("m_UniqueId", 0)   # zero values are not stored
            where = location(a)
            if FIELD_ITEM.search(cls):
                item = props.get("m_ItemId", -1)
                kind = "shiny" if item not in (-1, None) else "spot"
                fields.append([kind, mid, uid, cls, item, props.get("m_ItemNum", 1), props.get("m_Money", -1),
                               condition(props), events(props), stem] + where)
            elif TREASURE.search(cls):
                # m_Id is the box's chest table row ID. A box that does not store one has the native
                # default, -1: round 3 saw those live (m_Id -1) as open story chests with no row.
                # m_TreasureBoxData is an editor copy and is often empty, so it is only reported.
                data = props.get("m_TreasureBoxData") or {}
                boxes.append([mid, props.get("m_Id", -1), uid, cls, condition(props), stem] + where
                             + [f"{data.get('mapId', 0)}:{data.get('ID', 0)}"])
            elif TRANSITION.search(cls):
                transitions.append([mid, stem, uid, props.get("m_MapId", ""), props.get("m_PointID", ""),
                                    str(props.get("m_IsAutoTransition", "")).lower(),
                                    enum(props.get("m_TransitionMovementType", "")),
                                    condition(props) if props.get("m_IsUseCondion") or props.get("m_Condition") else "",
                                    events(props)] + where)
            elif GIMMICK_CLASSES.search(cls):
                gimmicks.append([mid, stem, uid, cls, props.get("m_Id", ""), props.get("m_Description", ""),
                                 condition(props), events(props)] + where)
    xyz = ["x", "y", "z"]
    sort = lambda r: (str(r[1]), str(r[2]), str(r[3]))
    write_tsv("field_items.tsv", ["kind", "map", "uid", "row", "item", "count", "money", "visible", "events", "level"] + xyz,
              sorted(fields, key=lambda r: (str(r[1]), int(r[2]) if str(r[2]).isdigit() else 0)))
    write_tsv("treasure_actors.tsv", ["map", "ID", "uid", "class", "visible", "level"] + xyz + ["editorData"],
              sorted(boxes, key=lambda r: (str(r[0]), r[1], r[5])))
    write_tsv("transitions.tsv", ["map", "level", "uid", "toMap", "toPoint", "auto", "movement", "condition", "events"] + xyz,
              sorted(transitions, key=sort))
    write_tsv("gimmicks.tsv", ["map", "level", "uid", "class", "id", "description", "condition", "events"] + xyz,
              sorted(gimmicks, key=sort))
    return fields, boxes


# ---------------------------------------------------------------- comparison with data/*.tsv

def check(item_rows, chest_rows, field_rows, box_rows):
    problems = 0
    unmapped = sorted({r[9] for r in field_rows if r[1] == ""} | {r[5] for r in box_rows if r[0] == ""})
    if unmapped:
        print(f"\nlevels with field items or chests but no map id: {' '.join(unmapped)}")

    # data/item_names.tsv (from FFR-Randomizer) was retired once the dump replaced it;
    # an old copy is still compared if one is there.
    names_path = os.path.join(DATA, "item_names.tsv")
    if os.path.exists(names_path):
        names = {int(r["id"]): r["name"] for r in read_tsv(names_path)}
        game = {int(r[0]): r[4] for r in item_rows}
        missing = sorted(set(game) - set(names))
        extra = sorted(set(names) - set(game))
        renamed = sorted(i for i in set(game) & set(names) if game[i] != names[i])
        print(f"\nitem_names.tsv: {len(names)} ids, game: {len(game)} ids")
        for i in missing:
            print(f"  missing from item_names.tsv: {i} {game[i]}")
        for i in extra:
            print(f"  not in the game tables: {i} {names[i]}")
        for i in renamed:
            print(f"  name differs: {i} item_names.tsv={names[i]!r} game={game[i]!r}")
        problems += len(missing) + len(extra) + len(renamed)

    ours = {(r["mapId"], r["ID"]): r for r in read_tsv(os.path.join(DATA, "chests.tsv"))}
    cols = CHEST_COLUMNS
    dumped = {(str(r[1]), str(r[2])): dict(zip(cols, map(str, r))) for r in chest_rows}
    print(f"\nchests.tsv: {len(ours)} rows, game: {len(dumped)} rows")
    for k in sorted(set(dumped) - set(ours)):
        print(f"  missing from chests.tsv: {dumped[k]['row']}")
    for k in sorted(set(ours) - set(dumped)):
        print(f"  not in the game tables: {ours[k]['row']}")
    for k in sorted(set(ours) & set(dumped)):
        diff = [c for c in cols if ours[k][c] != dumped[k][c]]
        if diff:
            print(f"  differs: {ours[k]['row']}: " + ", ".join(f"{c} {ours[k][c]} -> {dumped[k][c]}" for c in diff))
            problems += 1
    problems += len(set(dumped) ^ set(ours))

    # Placed boxes against table rows (box_matches). tools/gen_apworld_data.py reads the
    # boxes column: a row with no box is not a location.
    boxes_by_row = {r[0]: [b for b in box_rows if box_matches(r, b)] for r in chest_rows}
    matched = {id(b) for bs in boxes_by_row.values() for b in bs}
    print(f"\ntreasure box actors: {len(box_rows)}, table rows with a box: "
          f"{sum(1 for bs in boxes_by_row.values() if bs)} of {len(chest_rows)}")
    for r in chest_rows:
        if not boxes_by_row[r[0]]:
            print(f"  table row with no box on any map: {r[0]} (map {r[1]}, item {r[3]}, gil {r[5]})")
    for b in box_rows:
        if id(b) not in matched:
            print(f"  box with no table row: map {b[0]} ID {b[1]} uid {b[2]} on {b[5]} ({b[3]})")
    for row, bs in sorted(boxes_by_row.items()):
        if len(bs) > 1:
            print(f"  one row, {len(bs)} boxes: {row} on " + ", ".join(f"{b[5]} uid {b[2]}" for b in bs))

    seen = {(r["map"], r["uid"]): r for r in read_tsv(os.path.join(DATA, "shinies.tsv"))}
    placed = {(str(r[1]), str(r[2])): r for r in field_rows}
    print(f"\nshinies.tsv: {len(seen)} seen in game, dump: {len(placed)} placed field items "
          f"({sum(1 for r in field_rows if r[0] == 'shiny')} with an item)")
    for k in sorted(set(seen) - set(placed)):
        print(f"  seen in game but not placed on a map: map {k[0]} uid {k[1]} ({seen[k]['row']})")
        problems += 1
    for k in sorted(set(seen) & set(placed)):
        s, p = seen[k], placed[k]
        if s["item"] != str(p[4]) or s["row"] != p[3]:
            print(f"  differs: map {k[0]} uid {k[1]}: seen {s['row']} item {s['item']}, placed {p[3]} item {p[4]}")
            problems += 1
    print(f"  not seen in game yet: {len(set(placed) - set(seen))}")
    return problems


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="compare with data/*.tsv")
    args = parser.parse_args()
    if not os.path.exists(os.path.join(DUMP, "manifest.json")):
        sys.exit("No dump/ yet. Run: dotnet run --project tools/dump_game -- all")
    item_rows = items()
    units()
    shard_chests()
    by_key = maps()
    shops()
    field_rows, box_rows = actors(by_key)
    chest_rows = chests(box_rows)
    if args.check:
        problems = check(item_rows, chest_rows, field_rows, box_rows)
        print(f"\n{problems} differences")


if __name__ == "__main__":
    main()
