"""tools/gen_from_dump.py against a small fake dump.

The fake dump has the same shapes as tools/dump_game's output: DataTable JSON with
FText names, a CompositeDataTable of chest tables, map actors and class defaults.
"""

import csv
import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gen_from_dump", REPO / "tools" / "gen_from_dump.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

T = "tables/FFRS/Content/Datatable"


def ftext(en, ja="名前"):
    return {"TableId": "/Game/x", "Key": "k", "SourceString": ja, "LocalizedString": en}


def item(id_, en, type_="Consumables", **extra):
    return {"ID": id_, "Name": ftext(en), "ItemType": f"eItemType::{type_}", "buyingPrice": 10,
            "sellingPrice": 5, "isAvailableSale": True, **extra}


def write(root, rel, data):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def ref(name):
    return {"ObjectName": f"DataTable'{name}'", "ObjectPath": f"/Game/Datatable/Map/Gimmick/TreasureBox/{name}.0"}


def make_dump(root):
    write(root, "manifest.json", {"failures": []})
    write(root, f"{T}/Item/DT_ConsumablesItemData.json", {"Rows": {
        "potion": item(1, "Potion"),
        "ether": item(3, "Ether　"),                       # a stray ideographic space
    }})
    write(root, f"{T}/Item/DT_SeedItemData.json", {"Rows": {
        "seed": item(9500, "<MISSING STRING TABLE ENTRY>"),    # falls back to the Japanese text
    }})
    write(root, f"{T}/Item/DT_EquipmentItemData.json", {"Rows": {
        "sword": item(10100, "Broadsword", "Equipment", equipmentDetailType="eEquipmentDetailType::Sword"),
    }})
    write(root, f"{T}/Item/Vision/DT_VisionItemData.json", {"Rows": {"cloud": item(13110, "Cloud", "Equipment")}})
    write(root, f"{T}/Item/DT_ValuableItemData.json", {"Rows": {"jade": item(20005, "White Jade Stone", "Valuable")}})
    write(root, f"{T}/Item/DT_ArtifactItemData.json", {"Rows": {}})
    write(root, f"{T}/Event/Data/CollectMedal/DT_TalkEvent_CollectMedal.json", {"Rows": {
        "01_02": {"Num": 6, "Condition": "{progress:43}==11", "Text": ftext("1-Star Chamber"), "TreasureBoxItemId": 1},
        "01_01": {"Num": 3, "Condition": "{progress:43}==10", "Text": ftext("1-Star Chamber"), "TreasureBoxItemId": 0},
    }})
    write(root, f"{T}/Unit/DT_UnitParameter.json", {"Rows": {
        "rain": {"ID": 1001, "Name": ftext("Rain"), "Category": "eUnitCategory::Playable", "Race": "eRace::Human", "Level": 1},
        "ifrit": {"ID": 10452, "Name": ftext("Ifrit"), "Category": "eUnitCategory::Beast", "Race": "eRace::Beast", "Level": 1},
    }})
    write(root, f"{T}/Map/MapData/DT_MapData_00Com.json", {"Rows": {
        "Wld": {"ID": 1000, "Name": ftext("Field"), "island": "eMapIslandType::None", "GroupId": -1},
    }})
    write(root, f"{T}/Map/MapData/DT_MapData_01Gra.json", {"Rows": {
        "01Gra_40": {"ID": 3000, "Name": ftext("Grandshelt Isles"), "island": "eMapIslandType::Grandshelt", "GroupId": -1},
        "01Gra_41": {"ID": 3001, "Name": ftext("Cave"), "island": "eMapIslandType::Grandshelt", "GroupId": -1},
        "01Gra_02": {"ID": 2011, "Name": ftext("Capital"), "island": "eMapIslandType::Grandshelt", "GroupId": 2011},
    }})
    write(root, f"{T}/Shop/DT_ShopList.json", {"Rows": {
        "tools": {"ShopID": 0, "ItemList": [{"ItemId": 1, "Condition": "", "MaxOrderNum": -1, "PriceRatio": 1.0}]},
    }})
    write(root, f"{T}/Map/Gimmick/TreasureBox/CDT_MapGimmickTreasureBox.json",
          {"Properties": {"ParentTables": [ref("DT_Dng_01Gra_40"), None, ref("DT_Town_01Gra_02")]}})
    write(root, f"{T}/Map/Gimmick/TreasureBox/DT_Dng_01Gra_40.json", {"Rows": {
        "Dng_01Gra_40_0": {"ID": 0, "mapId": 3000, "ItemId": 1, "ItemNum": 2, "Money": -1, "IsTrap": False, "battleGroupId": -1},
        "Dng_01Gra_40_1": {"ID": 1, "mapId": 3000, "ItemId": -1, "ItemNum": 1, "Money": 400, "IsTrap": False, "battleGroupId": -1},
        "Dng_01Gra_40_2": {"ID": 2, "mapId": 3000, "ItemId": 4, "ItemNum": 1, "Money": -1, "IsTrap": False, "battleGroupId": -1},
    }})
    # Rows of one table can sit in other maps: 2001:0 in a level named after the table, 3001:3 in
    # another level of its own map.
    write(root, f"{T}/Map/Gimmick/TreasureBox/DT_Town_01Gra_02.json", {"Rows": {
        "Town_01Gra_02_0": {"ID": 0, "mapId": 2001, "ItemId": 4, "ItemNum": 3, "Money": -1, "IsTrap": False, "battleGroupId": -1},
        "Town_01Gra_02_3": {"ID": 3, "mapId": 3001, "ItemId": -1, "ItemNum": 1, "Money": 300, "IsTrap": False, "battleGroupId": -1},
    }})
    # A medal shiny takes its item from the class default; a spot has none; m_UniqueId 0 is not stored.
    level = "FFRS/Content/Map/Dng/01Gra/01Gra_40/GD/Dng_01Gra_40_GD.json"
    world = "FFRS/Content/Map/Wld/GD/Wld_01Gra_GD.json"
    town = "FFRS/Content/Map/Town/01Gra/01Gra_02/GD/Town_01Gra_02_01_GD.json"
    house = "FFRS/Content/Map/Dng/01Gra/01Gra_41/GD/Dng_01Gra_41_GD.json"
    write(root, "maps/index.json", [{"path": level, "actors": 4}, {"path": world, "actors": 2},
                                    {"path": town, "actors": 1}, {"path": house, "actors": 1}])
    write(root, "maps/" + town, [{"Type": "BP_MapGimmick_TreasureBox_C", "Properties": {"m_Id": 0, "m_UniqueId": 4}}])
    write(root, "maps/" + house, [{"Type": "BP_MapGimmick_TreasureBox_C", "Properties": {"m_Id": 3, "m_UniqueId": 23}}])
    write(root, "maps/" + level, [
        {"Type": "BP_MapGimmick_TreasureBox_C", "Properties": {"m_Id": 0, "m_UniqueId": 4}, "RootLocation": {"X": 1.4, "Y": 2, "Z": 3}},
        {"Type": "BP_MapGimmick_TreasureBox002_C", "Properties": {"m_Id": 1, "m_UniqueId": 5}},
        {"Type": "BP_MapGimmick_TreasureBox_C", "Properties": {"m_UniqueId": 50}},     # no m_Id: a story chest (-1)
        {"Type": "BP_MapGimmick_BlockingBox_C", "Properties": {"m_UniqueId": 7, "VisibleCondition": "!{flag:928}"}},
        {"Type": "BP_MapTransitionTrigger_C", "Properties": {"m_UniqueId": 8, "m_MapId": 1000, "m_PointID": 10200,
                                                              "m_IsUseCondion": True, "m_Condition": "{progress:0}>=4000"}},
    ])
    write(root, "maps/" + world, [
        {"Type": "BP_MapGimmick_FieldItem_Medal_C", "Properties": {"m_UniqueId": 4}},
        {"Type": "BP_MapGimmick_FieldItem_C", "Properties": {"VisibleCondition": "{progress:8}==30"}},
        {"Type": "BP_MapAirShipLandingPoint_C", "Properties": {"m_Id": 10200, "m_Description": "landing"}},
    ])
    write(root, "maps/classes.json", {
        "BP_MapGimmick_FieldItem_Medal_C": {"super": "BP_MapGimmick_FieldItem_C", "defaults": {"m_ItemId": 25004}},
        "BP_MapGimmick_FieldItem_C": {"super": "CPP_MapGimmick_FieldItem", "defaults": {"m_Cycle": 1.2}},
        "CPP_MapGimmick_FieldItem": {"super": None, "defaults": None},
    })


def make_data(root):
    data = Path(root) / "data"
    data.mkdir()
    (data / "item_names.tsv").write_text(
        "id\tname\n1\tPotion\n3\tEther\n9500\t名前\n10100\tBroadsword\n13110\tCloud\n20005\tWhite Jade\n99\tGone\n",
        encoding="utf-8")
    (data / "chests.tsv").write_text(
        "row\tmapId\tID\tItemId\tItemNum\tMoney\tIsTrap\tbattleGroupId\n"
        "Dng_01Gra_40_0\t3000\t0\t1\t3\t-1\tfalse\t-1\n"
        "Dng_01Gra_40_1\t3000\t1\t-1\t1\t400\tfalse\t-1\n", encoding="utf-8")
    (data / "shinies.tsv").write_text(
        "kind\tmap\tuid\trow\titem\tcount\tmoney\tvisible\n"
        "shiny\t1000\t4\tBP_MapGimmick_FieldItem_Medal_C\t25004\t1\t-1\t\n"
        "shiny\t2015\t4\tBP_MapGimmick_FieldItem_Medal_C\t25004\t1\t-1\t\n", encoding="utf-8")
    return data


def tsv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        make_dump(os.path.join(tmp, "dump"))
        data = make_data(tmp)
        gen.DUMP, gen.DATA, gen.OUT = os.path.join(tmp, "dump"), str(data), str(data / "game")
        sys.argv = ["gen_from_dump.py", "--check"]
        out = io.StringIO()
        with redirect_stdout(out):
            gen.main()
        log = out.getvalue()
        game = data / "game"

        items = {r["id"]: r for r in tsv(game / "items.tsv")}
        assert list(items) == ["1", "3", "9500", "10100", "13110", "20005"], list(items)
        assert items["3"]["name"] == "Ether", items["3"]              # stripped
        assert items["9500"]["name"] == "名前", items["9500"]          # missing English -> Japanese
        assert items["10100"]["detail"] == "Sword" and items["10100"]["table"] == "equipment"
        assert items["20005"]["type"] == "Valuable"

        units = {r["id"]: r for r in tsv(game / "units.tsv")}
        assert units["1001"]["category"] == "Playable" and units["10452"]["name"] == "Ifrit"

        maps = {r["key"]: r["id"] for r in tsv(game / "maps.tsv")}
        assert maps == {"Wld": "1000", "01Gra_40": "3000", "01Gra_41": "3001", "01Gra_02": "2011"}, maps
        assert tsv(game / "shops.tsv")[0]["item"] == "1"
        # Round 56: Oblivion Palace's chests, in chest order, with the shards each needs in all
        shard_rows = tsv(game / "shard_chests.tsv")
        assert [(r["map"], r["chest"], r["shards"]) for r in shard_rows] == [("2031", "0", "3"), ("2031", "1", "6")], shard_rows
        assert shard_rows[0]["room"] == "1-Star Chamber" and shard_rows[0]["condition"] == "{progress:43}==10"

        chests = tsv(game / "chests.tsv")
        assert [c["row"] for c in chests] == ["Dng_01Gra_40_0", "Dng_01Gra_40_1", "Dng_01Gra_40_2",
                                              "Town_01Gra_02_0", "Town_01Gra_02_3"]
        assert chests[1]["Money"] == "400" and chests[0]["IsTrap"] == "false"
        boxes_of = {c["row"]: c["boxes"] for c in chests}
        assert boxes_of["Dng_01Gra_40_0"] == "Dng_01Gra_40:4", boxes_of
        assert boxes_of["Dng_01Gra_40_2"] == "", boxes_of                       # no box: not a location
        assert boxes_of["Town_01Gra_02_0"] == "Town_01Gra_02_01:4", boxes_of    # by table name
        assert boxes_of["Town_01Gra_02_3"] == "Dng_01Gra_41:23", boxes_of       # by map

        boxes = tsv(game / "treasure_actors.tsv")
        assert [(b["map"], b["ID"], b["uid"]) for b in boxes] == [
            ("2011", "0", "4"), ("3000", "-1", "50"), ("3000", "0", "4"), ("3000", "1", "5"), ("3001", "3", "23")], boxes
        assert boxes[2]["x"] == "1", boxes[2]

        fields = {(r["map"], r["uid"]): r for r in tsv(game / "field_items.tsv")}
        assert fields[("1000", "4")]["item"] == "25004" and fields[("1000", "4")]["kind"] == "shiny"
        assert fields[("1000", "0")]["kind"] == "spot" and fields[("1000", "0")]["visible"] == "{progress:8}==30"

        trans = tsv(game / "transitions.tsv")
        assert trans[0]["map"] == "3000" and trans[0]["toMap"] == "1000" and trans[0]["condition"] == "{progress:0}>=4000"

        gimmicks = {r["class"]: r for r in tsv(game / "gimmicks.tsv")}
        assert gimmicks["BP_MapGimmick_BlockingBox_C"]["condition"] == "!{flag:928}"
        assert gimmicks["BP_MapAirShipLandingPoint_C"]["id"] == "10200"

        # The comparison with data/*.tsv.
        assert "missing from item_names.tsv" not in log, log
        assert "not in the game tables: 99 Gone" in log, log
        assert "name differs: 20005" in log, log
        assert "differs: Dng_01Gra_40_0: ItemNum 3 -> 2" in log, log
        assert "seen in game but not placed on a map: map 2015 uid 4" in log, log
        assert "table row with no box on any map: Dng_01Gra_40_2" in log, log
        assert "box with no table row: map 3000 ID -1 uid 50" in log, log
        assert "not seen in game yet: 1" in log, log
    print("ok")


if __name__ == "__main__":
    main()
