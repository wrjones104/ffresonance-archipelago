"""Lifts whose stop the save keeps, and where the game puts them when the player arrives.

Reads full level dumps (dump/assets/FFRS/Content/Map/.../*_GD.json) and the lift Blueprints
(dump/assets/FFRS/Content/BP/Map/Gimmick/...). Make them first:

    dotnet run --project tools/dump_game -- assets FFRS/Content/Map/Dng/07Mys/07Mys_43/GD/Dng_07Mys_43_01_GD
    dotnet run --project tools/dump_game -- assets FFRS/Content/BP/Map/Gimmick/BP_MapGimmick_Floor

A lift with m_IsSave keeps its stop (the spline point index) in the save. When a map loads it
starts at the saved stop, or at m_InitStepIndex on a first visit. Its m_TransitionDataList moves
it to a stop when the player arrives at a given point. An arrival with no rule keeps the saved
stop. Round 113: the Tower of Mysidia's lift up stayed at its top after a fast travel out.

Prints each level's lifts and writes data/game/lifts.tsv (one row per lift: stops as z heights,
rules as point:stop). The mod's G.LIFT_RESETS is taken from it (tests/mod/test_game.py).

    python tools/lift_audit.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "dump" / "assets" / "FFRS" / "Content"
GAME = ROOT / "data" / "game"
SAVE_POINT_BASE = 10000   # m_PointID of the arrival at a save point (load or fast travel)


def read_tsv(name):
    with open(GAME / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def export_index(ref):
    return int(ref["ObjectPath"].rsplit(".", 1)[1])


def class_defaults():
    """Each lift Blueprint class's defaults, with its parents' filled in."""
    own, parent = {}, {}
    for path in (ASSETS / "BP" / "Map" / "Gimmick").rglob("*.json"):
        exports = json.loads(path.read_text(encoding="utf-8"))
        for e in exports:
            if e.get("Type") == "BlueprintGeneratedClass":
                parent[e["Name"]] = (e.get("Super") or e.get("SuperStruct") or {}).get("ObjectName", "").split("'")[1:2]
            elif e.get("Name", "").startswith("Default__"):
                own[e["Name"][len("Default__"):]] = e.get("Properties", {})
    merged = {}
    for name in own:
        chain, at = [], name
        while at in own:
            chain.append(own[at])
            up = parent.get(at) or []
            at = up[0] if up else None
        props = {}
        for p in reversed(chain):
            props.update(p)
        merged[name] = props
    return merged


def level_lifts(level_path, defaults):
    exports = json.loads(level_path.read_text(encoding="utf-8"))

    def location(i):
        root = exports[i].get("Properties", {}).get("RootComponent")
        loc = exports[export_index(root)].get("Properties", {}).get("RelativeLocation") if root else None
        return (loc or {}).get("X", 0.0), (loc or {}).get("Y", 0.0), (loc or {}).get("Z", 0.0)

    points = {}
    for i, e in enumerate(exports):
        if e.get("Type") == "BP_MapTransitionPoint_C":
            points[e["Name"]] = (e.get("Properties", {}).get("m_PointID"), location(i))
    lifts = []
    for i, e in enumerate(exports):
        kind = e.get("Type", "")
        if "Elevator" not in kind or "Wall" in kind:
            continue
        props = dict(defaults.get(kind, {}))
        props.update(e.get("Properties", {}))
        base = location(i)
        stops = []
        for c in exports:
            if c.get("Type") == "SplineComponent" and c.get("Outer") and export_index(c["Outer"]) == i:
                for p in c.get("Properties", {}).get("SplineCurves", {}).get("Position", {}).get("Points", []):
                    v = p["OutVal"]
                    stops.append((base[0] + v["X"], base[1] + v["Y"], base[2] + v["Z"]))
        rules = {}
        for t in props.get("m_TransitionDataList", []):
            name = t["pTransitionPoint"]["ObjectName"].split(".")[-1].rstrip("'")
            if t.get("bOverride_ValueInt"):
                rules[points.get(name, (name,))[0]] = t.get("IntValue")
        lifts.append({
            "uid": props.get("m_UniqueId"), "class": kind, "saved": props.get("m_IsSave", False),
            "init": props.get("m_InitStepIndex", 0), "call": props.get("m_IsCallSwitch", False),
            "special": str(props.get("m_SpecialBehavior", "")).split("::")[-1],
            "stops": stops, "rules": rules,
        })
    return lifts, {pid: loc for pid, loc in points.values()}


def main():
    table = []
    level_map = {}
    for r in read_tsv("gimmicks.tsv"):
        level_map.setdefault(r["level"], r["map"])
    defaults = class_defaults()
    for level_path in sorted((ASSETS / "Map").rglob("*_GD.json")):
        level = level_path.stem[:-len("_GD")]
        lifts, points = level_lifts(level_path, defaults)
        if not lifts:
            continue
        map_id = level_map.get(level, "?")
        print(f"\n{map_id} {level}: arrival points " + ", ".join(
            f"{pid} (z {loc[2]:.0f})" for pid, loc in sorted(points.items(), key=lambda kv: kv[0] or 0)))
        for lift in lifts:
            stops = ", ".join(f"{n}: z {s[2]:.0f}" for n, s in enumerate(lift["stops"]))
            rules = ", ".join(f"at {pid} -> {n}" for pid, n in sorted(lift["rules"].items(), key=lambda kv: kv[0] or 0))
            unruled = sorted(pid for pid in points if pid is not None and pid not in lift["rules"])
            print(f"  lift {lift['uid']} {lift['class']}: saved {lift['saved']}, init {lift['init']}, "
                  f"call {lift['call']}, {lift['special']}; stops {stops or '-'}; rules {rules or 'none'}; "
                  f"keeps its saved stop on arrival at {unruled or 'none'}")
            table.append([map_id, level, lift["uid"], lift["class"], str(lift["saved"]).lower(), lift["init"],
                          ",".join(f"{s[2]:.0f}" for s in lift["stops"]),
                          ",".join(f"{pid}:{n}" for pid, n in sorted(lift["rules"].items(), key=lambda kv: kv[0] or 0))])
    table.sort(key=lambda r: (int(r[0]) if r[0].isdigit() else 0, r[1], r[2]))
    with open(GAME / "lifts.tsv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter="\t", lineterminator="\n")
        writer.writerow(["map", "level", "uid", "class", "saved", "init", "stops", "rules"])
        writer.writerows(table)
    print(f"{len(table)} lifts written to data/game/lifts.tsv")


if __name__ == "__main__":
    main()
