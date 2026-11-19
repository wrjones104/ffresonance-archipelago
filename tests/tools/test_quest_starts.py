"""tools/gen_apworld_data.py's reward_start: where and when a quest's reward rows run, for the
pop-up the mod writes before the quest's check (rounds 79 and 88)."""

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gen_apworld_data", REPO / "tools" / "gen_apworld_data.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

CALL_COUNTER, MOG_COUNTER = 36, 44
ZOLDAAD_TRAIN_MAP, IMPERIAL_RESIDENCES_MAP, MYSIDIA_MAP = 3121, 2100, 2130


def step(map_id, condition, chain="", at=""):
    return {"map": str(map_id), "condition": condition, "chain": chain, "at": str(at)}


# The Call from Beyond: the chain starts on the train and moves to the Imperial Residences.
assert gen.reward_start([step(ZOLDAAD_TRAIN_MAP, "{progress:36}==50", at=IMPERIAL_RESIDENCES_MAP)], CALL_COUNTER) \
    == (IMPERIAL_RESIDENCES_MAP, (50,), ())
# an old table with no `at` keeps the actor's map
assert gen.reward_start([step(ZOLDAAD_TRAIN_MAP, "{progress:36}==50")], CALL_COUNTER) == (ZOLDAAD_TRAIN_MAP, (50,), ())

# Mog Tag's first tier: each moogle's actor is visible at every tier, and its chain picks the tier
# (0 or 10). Each moogle needs its own two of 540 to 542; all three need 545, the chase.
moogles = [
    step(MYSIDIA_MAP, "{flag:545} & ({progress:44}==20|{progress:44}==30) & !{flag:540}",
         "{flag:541}&{flag:542} {progress:0}>=5040 & ({progress:44}==0|{progress:44}==10)", MYSIDIA_MAP),
    step(MYSIDIA_MAP, "{flag:545} & ({progress:44}==0|{progress:44}==10) & !{flag:541}",
         "{flag:540}&{flag:542} {progress:0}<5040 & ({progress:44}==0|{progress:44}==10)", MYSIDIA_MAP),
    step(MYSIDIA_MAP, "{flag:545} & ({progress:44}==40|{progress:44}==50) & !{flag:542}",
         "{flag:540}&{flag:541} {progress:0}>=5040 & ({progress:44}==0|{progress:44}==10)", MYSIDIA_MAP),
]
assert gen.reward_start(moogles, MOG_COUNTER) == (MYSIDIA_MAP, (0, 10), (545,)), gen.reward_start(moogles, MOG_COUNTER)

# steps that disagree on the map, or with no test of the counter, give none
assert gen.reward_start([step(1, "{progress:36}==50", at=1), step(2, "{progress:36}==50", at=2)], CALL_COUNTER) is None
assert gen.reward_start([step(1, "{flag:9}", at=1)], CALL_COUNTER) is None
print("quest starts: ok")
