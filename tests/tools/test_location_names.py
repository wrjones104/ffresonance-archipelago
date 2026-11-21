"""tools/gen_apworld_data.py's readable location names (round 77) and the round's data fixes.

Runs the real generator on a copy of data/, so the repo's files are never written.
"""

import csv
import importlib.util
import io
import shutil
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORK = Path(tempfile.mkdtemp(prefix="ffrap_names_"))
shutil.copytree(REPO / "data", WORK / "data")
OUT = WORK / "data.py"

spec = importlib.util.spec_from_file_location("gen_apworld_data", REPO / "tools" / "gen_apworld_data.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)
gen.DATA, gen.OUT = str(WORK / "data"), str(OUT)
gen.write_field_items_lua = lambda: None
gen.write_gifts_lua = lambda _: None
gen.write_quests_lua = lambda *_: None

NAMES = WORK / "data" / "location_names.tsv"
SHINY_167 = "shiny:1000:167"
OWN_NAME = "Gronoa - Shiny on the NW peninsula"


def run() -> dict[str, dict]:
    with redirect_stdout(io.StringIO()):
        gen.main()
    spec_out = importlib.util.spec_from_file_location("data_out", OUT)
    data = importlib.util.module_from_spec(spec_out)
    spec_out.loader.exec_module(data)
    every = data.CHESTS + data.SHINIES + data.RADAR + data.TABLET_SHINIES + data.RADAR_PART_CHESTS + data.BOSSES + data.GIFTS
    return {loc["key"]: loc for loc in every}


def rows() -> dict[str, dict]:
    with open(NAMES, encoding="utf-8") as f:
        return {r["key"]: r for r in csv.DictReader(f, delimiter="\t")}


# The user's name wins, and survives the generator rewriting the file.
table = rows()
table[SHINY_167]["name"] = OWN_NAME
for n in (85, 86, 91):
    table[f"shiny:1000:{n}"]["name"] = ""
with open(NAMES, "w", encoding="utf-8", newline="\n") as f:
    w = csv.DictWriter(f, fieldnames=gen.NAMES_COLUMNS, delimiter="\t", lineterminator="\n")
    w.writeheader()
    w.writerows(table.values())
locs = run()
assert locs[SHINY_167]["name"] == OWN_NAME, locs[SHINY_167]["name"]
assert rows()[SHINY_167]["name"] == OWN_NAME, "kept in the file"
assert rows()[SHINY_167]["suggested"] == "Gronoa - Shiny NW of Rugged Mountain Path"
assert rows()[SHINY_167]["old"] == "World Map Shiny 167"
locs = run()
assert locs[SHINY_167]["name"] == OWN_NAME, "and on the next run"
# A suggested name shared by two spots is numbered; every name is unique.
assert {locs[f"shiny:1000:{n}"]["name"] for n in (85, 86, 91)} == {
    f"Mysidia - Shiny near Salome Cave {n}" for n in (1, 2, 3)}
names = [loc["name"] for loc in locs.values()]
assert len(names) == len(set(names))
print("location names: ok")

# Round 77's data fixes.
assert locs[SHINY_167].get("airship") is True, "Gronoa's NW peninsula needs the airship"
for key in ("chest:3180:1", "chest:3180:3", "chest:3180:4", "shiny:3180:14", "boss:9031"):
    assert {9088, 9089} <= set(locs[key].get("after_boss", [])), key
assert "after_boss" not in locs["shiny:3180:13"], "Shard 13 is by the entrance"
assert locs["shiny:1000:127"]["area"] == "Grandshelt", "the land at the stone bridge's north end"
print("round 77 data: ok")

# Gift 1403 (Zoldaad Castle's dungeon) is unreachable at story 8000; remaining gifts use place names.
spec_gifts = importlib.util.spec_from_file_location("data_gifts", OUT)
generated = importlib.util.module_from_spec(spec_gifts)
spec_gifts.loader.exec_module(generated)
assert all(g["key"] != "gift:1403" for g in generated.GIFTS)
assert locs["gift:1408"]["name"] == "Kolobos - Town of Felicitas - East Bridge Gift", locs["gift:1408"]["name"]
assert locs["chest:3150:0"]["name"].startswith("Zoldaad - Dungeon - "), locs["chest:3150:0"]["name"]
print("gift names: ok")
shutil.rmtree(WORK)
