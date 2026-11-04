"""Writes data/item_names.tsv from FFR-Randomizer's generated ItemNames.lua.

ItemNames.lua is part of FFR-Randomizer by LordMikoda (MIT license,
https://github.com/LordMikoda/FFR-Randomizer). It maps game item ids to English names.

    python tools/import_item_names.py <path to ItemNames.lua>
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "item_names.tsv")
ENTRY = re.compile(r'\[(\d+)\]\s*=\s*"((?:[^"\\]|\\.)*)"')


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    text = open(sys.argv[1], encoding="utf-8").read()
    rows = sorted(((int(i), n) for i, n in ENTRY.findall(text)), key=lambda r: r[0])
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("id\tname\n")
        for item_id, name in rows:
            f.write(f"{item_id}\t{name}\n")
    print(f"{len(rows)} names written to {OUT}")


if __name__ == "__main__":
    main()
