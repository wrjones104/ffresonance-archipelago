"""Compares two save snapshots from the mod's ffrap_snapshot command.

    python tools/snapdiff.py snap_start.tsv snap_ch1.tsv [--all]

Prints every path whose value changed, was added or was removed, grouped by its top-level
field (save.Progress, save.unitParameterList, ...). Fields that change all the time (play time,
dates, the live.* lines) are left out unless --all is given.

Boolean array elements that turned on or off are listed as index lists, so a flag array of
thousands of entries reads as a few lines ("save.Progress.eventFlag: on 1, 7, 141").
"""

from __future__ import annotations

import re
import sys
from collections import OrderedDict, defaultdict

NOISY = re.compile(r"(^live\.|PlayTime|playTime|DateTime|Ticks|Date\b|Time$|Timer)", re.IGNORECASE)
ELEMENT = re.compile(r"^(.*)\[(\d+)\]$")


def load(path: str) -> "OrderedDict[str, str]":
    values: OrderedDict[str, str] = OrderedDict()
    with open(path, encoding="utf-8") as f:
        for line in f:
            key, _, value = line.rstrip("\n").partition("\t")
            if key:
                values[key] = value
    return values


def group_of(path: str) -> str:
    parts = re.split(r"[.\[{]", path)
    return ".".join(parts[:2]) if len(parts) > 1 else path


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    show_all = "--all" in argv
    if len(args) != 2:
        print(__doc__)
        return 2
    a, b = load(args[0]), load(args[1])

    flags_on: dict[str, list[int]] = defaultdict(list)
    flags_off: dict[str, list[int]] = defaultdict(list)
    groups: dict[str, list[str]] = defaultdict(list)

    for key in list(a.keys()) + [k for k in b.keys() if k not in a]:
        old, new = a.get(key), b.get(key)
        if old == new or (not show_all and NOISY.search(key)):
            continue
        m = ELEMENT.match(key)
        if m and {old, new} <= {"true", "false", None} and (old == "true" or new == "true"):
            (flags_on if new == "true" else flags_off)[m.group(1)].append(int(m.group(2)))
            continue
        if old is None:
            groups[group_of(key)].append(f"  + {key} = {new}")
        elif new is None:
            groups[group_of(key)].append(f"  - {key} (was {old})")
        else:
            groups[group_of(key)].append(f"    {key}: {old} -> {new}")

    for array in sorted(set(flags_on) | set(flags_off)):
        lines = groups[group_of(array)]
        if flags_on.get(array):
            lines.append(f"    {array}: on {', '.join(map(str, sorted(flags_on[array])))}")
        if flags_off.get(array):
            lines.append(f"    {array}: off {', '.join(map(str, sorted(flags_off[array])))}")

    if not groups:
        print("No differences" + ("" if show_all else " (noisy fields left out; --all shows them)"))
        return 0
    for group in sorted(groups):
        print(f"{group}: {len(groups[group])} change(s)")
        for line in groups[group]:
            print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
