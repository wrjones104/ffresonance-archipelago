"""The template yaml (apworld/Final Fantasy Resonance.yaml) lists every option a player can see,
each at its default. Round 73: it had fallen behind since round 58. From v0.28.0 it is Archipelago's
own generated template (the Launcher's "Generate Template Options"): it also has Archipelago's
common options, and each option is a table of weights in which only the default has weight."""

import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

AP = str(paths.APTEST)
paths.install_world()
sys.path.insert(0, AP)
os.chdir(AP)

from Options import Visibility  # noqa: E402
from worlds.ff_resonance.options import FFResonanceOptions  # noqa: E402

TEMPLATE = paths.REPO / "apworld" / "Final Fantasy Resonance.yaml"
COMMON = {"progression_balancing", "accessibility", "local_items", "non_local_items", "start_inventory",
          "start_hints", "start_location_hints", "exclude_locations", "priority_locations",
          "item_links", "plando_items", "start_inventory_from_pool"}

failures = 0


def check(name, cond):
    global failures
    print(("ok  " if cond else "FAIL") + " " + name)
    failures += 0 if cond else 1


template = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8-sig"))["Final Fantasy Resonance"]


def chosen(value):
    """A weighted option's one choice: the only key with weight. A plain value is its own choice."""
    if not isinstance(value, dict):
        return value
    weighted = [key for key, weight in value.items() if weight]
    return weighted[0] if len(weighted) == 1 else None

options = FFResonanceOptions.type_hints
visible = {name for name, option in options.items() if name not in COMMON and option.visibility != Visibility.none}
check("every visible option is in the template: " + ", ".join(sorted(visible - set(template))),
      not visible - set(template))
check("no hidden or unknown option in the template: " + ", ".join(sorted(set(template) - visible - COMMON)),
      not set(template) - visible - COMMON)
for name in sorted(visible & set(template)):
    option, value = options[name], chosen(template[name])
    check(f"{name} is its default", value is not None and option.from_any(value).value == option.from_any(option.default).value)

print("failures:", failures)
sys.exit(1 if failures else 0)
