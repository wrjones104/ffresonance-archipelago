"""Every key item: the talk rows that give, take or test it, each giving row traced up to what starts
it (a map actor, another table), with the conditions on the way. Run from the repo root."""
import collections, glob, json, os, re, sys

sys.stdout.reconfigure(encoding="utf-8")
KEYS = {20005: "White Jade Stone", 20006: "Black Jade Stone", 20007: "Magic Tome", 20008: "Tunnel Key",
        20009: "Lab Key 1", 20010: "Lab Key 2", 20011: "Lab Key 3", 20016: "Adamantite", 20018: "Prison Key (jp)",
        20019: "Dungeon Key", 20020: "Dew of Reprieve", 20021: "Throne Room Key", 20023: "Viscus Vitae",
        20024: "Rushroom", 20025: "Pure Water", 20026: "Convalescence Draught", 20027: "Salad Stem",
        20028: "Portrait of Dario", 20029: "Dario's Letter", 20030: "Ruby Fragment", 20031: "Sword Hilt",
        20032: "Sword Blade", 20033: "Cabin Key", 27006: "Magi-tenna", 27007: "Resonance Stone",
        27008: "High-Power Generator", 29000: "Fledgling Proof", 29001: "Brawler Proof", 29002: "Gladiator Proof",
        29003: "Champion Proof", 29500: "Magitek Armor Key", 29510: "Archwitch's Grimoire", 29520: "Airship Passkey"}
ONLY = {int(a) for a in sys.argv[1:]} or set(KEYS)

rows = {}
for f in glob.glob("dump/tables/FFRS/Content/Datatable/Event/TalkEvent/**/*.json", recursive=True):
    d = json.load(open(f, encoding="utf-8"))
    for k, v in (d[0]["Rows"] if isinstance(d, list) else d.get("Rows", {})).items():
        if k not in rows or "CDT_" in rows[k][0]:
            rows[k] = (os.path.basename(f), v)

parents = collections.defaultdict(list)   # child -> [(parent, condition)]
for k, (_, v) in rows.items():
    for e in v.get("ContinuousEventList", []):
        parents[e["EventId"]].append((k, e.get("Condition", "")))
    for b in v.get("ChoicesBranchEventList", []):
        for e in b.get("EventList", []):
            parents[e["EventId"]].append((k, (e.get("Condition", "") + f" (choice {b.get('Index')})").strip()))

# Every other asset that names a talk row: map actors and other tables.
refs = collections.defaultdict(list)    # row -> [(file, actor, context)]
NAME = re.compile(r"^[A-Za-z0-9_]+$")
def walk(o, path, out):
    if isinstance(o, dict):
        for k, v in o.items(): walk(v, path + "/" + k, out)
    elif isinstance(o, list):
        for i, v in enumerate(o): walk(v, path + f"[{i}]", out)
    else:
        out.append((path, o))
files = [f for f in glob.glob("dump/maps/**/*.json", recursive=True)]
files += [f for f in glob.glob("dump/tables/**/*.json", recursive=True) if "TalkEvent" not in f.replace("\\", "/").split("Datatable/Event/")[-1][:9]]
wanted = set(rows)
for f in files:
    try:
        text = open(f, encoding="utf-8").read()
    except Exception:
        continue
    if not any(w in text for w in ("EventId", "EventName", "eventId", "Event")):
        continue
    try:
        d = json.loads(text)
    except Exception:
        continue
    for ob in (d if isinstance(d, list) else [d]):
        if not isinstance(ob, dict):
            continue
        flat = []
        walk(ob.get("Properties", ob.get("Rows", {})), "", flat)
        conds = [(p, v) for p, v in flat if isinstance(v, str) and ("{" in v) and re.search(r"(Condition|Visibl|Flag)", p)]
        for p, v in flat:
            if isinstance(v, str) and v in wanted and NAME.match(v):
                near = [f"{cp}={cv}" for cp, cv in conds if cp.rsplit("/", 1)[0] == p.rsplit("/", 1)[0] or "Visibl" in cp or cp.count("/") <= 1]
                refs[v].append((f.replace("\\", "/").split("FFRS/Content/")[-1], ob.get("Name", ""), p, near[:4]))

def roots(row, depth=0, seen=None):
    seen = seen or set()
    if row in seen or depth > 12:
        return []
    seen.add(row)
    out = []
    for f, actor, p, near in refs.get(row, []):
        out.append([(row, "")] + [(f"{f} :: {actor} {p}", "; ".join(near))])
    for parent, cond in parents.get(row, []):
        for chain in roots(parent, depth + 1, seen):
            out.append([(row, cond)] + chain)
    return out or [[(row, "(nothing starts it)")]]

ITEM_TEST = lambda i: re.compile(r"\{(item|transferItem):[^}]*\b" + str(i) + r"\}")
for item in sorted(ONLY):
    print("=" * 100)
    print(item, KEYS[item])
    for k, (f, v) in sorted(rows.items()):
        gives = [e for e in v.get("ObtainItemList", []) if e.get("ID") == item]
        takes = [e for e in v.get("ConsumeItemList", []) + v.get("TransferItemList", []) if e.get("ID") == item]
        if gives:
            print(f"  GIVES  {k} [{f}] {v.get('Description', '')}  flags on {v.get('OnFlagList')} progress {v.get('ProgressList')}")
            for chain in roots(k)[:6]:
                print("      <- " + "  <-  ".join(f"{r}" + (f" [{c}]" if c else "") for r, c in chain[1:]) if len(chain) > 1 else "      " + str(chain))
        if takes:
            print(f"  TAKES  {k} {v.get('Description', '')}")
    pat = ITEM_TEST(item)
    for k, (f, v) in sorted(rows.items()):
        s = json.dumps(v, ensure_ascii=False)
        for m in set(re.findall(r'"Condition": "([^"]*)"', s)):
            if pat.search(m):
                print(f"  TESTED in talk row {k}: {m}")
    for f in files:
        try:
            text = open(f, encoding="utf-8").read()
        except Exception:
            continue
        for m in set(re.findall(r'"([^"]*\{(?:item|transferItem):[^"]*)"', text)):
            if pat.search(m):
                print(f"  TESTED in {f.replace(chr(92), '/').split('FFRS/Content/')[-1]}: {m[:160]}")
