"""What a boss fight needs (docs/boss_logic.md): its tier's party, continents and Airship, a
baseline of healing, and what the boss itself asks for (its weaknesses, a way through its worst
attack). The party's skills count from the level they are learned at, up to the boss's own level."""
from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from .data import AIRSHIP_AREA, AIRSHIP_ITEM, BOSSES, CAPABILITIES, ITEMS, PROGRESSION, UNIT_ITEM_BASE

if TYPE_CHECKING:
    from BaseClasses import CollectionState

    from .world import FFResonanceWorld

AIRSHIP = ITEMS[AIRSHIP_ITEM]["name"]
ELEMENTS = ("fire", "ice", "wind", "earth", "lightning", "water", "light", "dark")
PARTY_MEMBERS = [ap_id - UNIT_ITEM_BASE for ap_id in PROGRESSION["party"]]

# Round 72: party members in all, continents unlocked, and the Airship, by tier. In round 71 bosses
# near level 20 felt out of reach without a full party, and beatable at level 30 with one.
TIER_NEEDS = {"A": (0, 0, False), "B": (3, 2, False), "C": (4, 4, False), "D": (5, 6, True)}
BOSS_TIER = {int(b["key"].split(":")[1]): b["tier"] for b in BOSSES}
BOSS_LEVEL = {int(b["key"].split(":")[1]): b["level"] for b in BOSSES}

# Round 73: a Vision's awakening depends on materials no logic counts, so the continents opened
# stand in for it (docs/boss_logic.md, section 2): awakening 1 from two, 2 from four, 3 from five
# and the Airship.
AWAKENING_CONTINENTS = ((5, 3), (4, 2), (2, 1))

# Each tier's baseline: from tier B a healer, from tier C a group heal or a revive.
TIER_BASELINE: dict[str, Callable[[Callable[[str], bool]], bool]] = {
    "A": lambda has: True,
    "B": lambda has: has("heal"),
    "C": lambda has: has("aoe_heal") or has("revive"),
    "D": lambda has: has("aoe_heal") or has("revive"),
}

# Round 73: per-boss needs for tiers A and B, from docs/boss_logic.md section 5, with the
# weaknesses checked against the dump. `has` takes a capability from data/game/capabilities.tsv,
# or an element alone for either kind of attack. Bosses not listed need their tier's baseline only.
BOSS_NEEDS: dict[int, Callable[[Callable[[str], bool]], bool]] = {
    9013: lambda has: has("heal") or has("lightning"),                                      # Siren
    9079: lambda has: has("heal") or has("wind"),                                           # Marauder
    9060: lambda has: has("heal") or has("water"),                                          # Antlion
    9014: lambda has: has("water") and (has("heal") or has("resist_fire")),                 # Mom Bomb
    9017: lambda has: (has("ice") or has("resist_wind")) and has("heal"),                   # Aether
    # Round 72: a level 3 party with no Earth and no healer could not beat it.
    9083: lambda has: has("earth"),                                                         # Liquid Thunder
    # Physical attacks do nothing to it, and it poisons the party.
    9080: lambda has: (has("earth_magic") or has("water_magic")) and (has("cleanse") or has("immune_poison")),
    9084: lambda has: has("wind") and (has("dispel") or has("aoe_heal")),                   # Rukh
    9085: lambda has: has("earth") and (has("cleanse") or has("immune_paralysis")),         # Mindflayer
    9094: lambda has: has("wind") or has("light"),                                          # Gogmagog
    9093: lambda has: has("water") and (has("aoe_heal") or has("resist_fire")),             # Pyroviper
    9109: lambda has: has("wind") and (has("cleanse") or has("immune_charm")),              # Salome
    # Both counter physical attacks.
    9088: lambda has: has("ice_magic") or has("water_magic"),                               # Liquid Flame
    9089: lambda has: has("lightning_magic"),                                               # Iron Giant
    9031: lambda has: has("wind") and (has("aoe_heal") or has("resist_earth")),             # Tellus
    9038: lambda has: has("wind") and (has("aoe_heal") or has("resist_earth")),             # Tellus
}


def party_in_hand(world: FFResonanceWorld, state: CollectionState) -> set[int]:
    party = set(world.starting_party)
    if world.options.shuffle_party_members:
        party |= {unit for unit in PARTY_MEMBERS if state.has(ITEMS[UNIT_ITEM_BASE + unit]["name"], world.player)}
    return party


def has_airship(world: FFResonanceWorld, state: CollectionState) -> bool:
    return bool(world.options.start_with_airship) or state.has(AIRSHIP, world.player)


def awakening(world: FFResonanceWorld, state: CollectionState) -> int:
    continents = state.count_group("Continent Unlocks", world.player)
    for needed, level in AWAKENING_CONTINENTS:
        if continents >= needed and (level < 3 or has_airship(world, state)):
            return level
    return 0


def has_capability(world: FFResonanceWorld, state: CollectionState, capability: str, level: int) -> bool:
    """Whether the party can do `capability` in a fight at `level`: a party member who has learned
    it by then, a Vision awake enough, or shop gear someone in the party can wear."""
    if capability in ELEMENTS:
        return any(has_capability(world, state, f"{capability}_{kind}", level) for kind in ("physical", "magic"))
    sources = CAPABILITIES[capability]
    party = party_in_hand(world, state)
    if any(unit in party and learned <= level for unit, learned in sources["party"].items()):
        return True
    awake = awakening(world, state)
    if any(needed <= awake and state.has(ITEMS[ap_id]["name"], world.player) for ap_id, needed in sources["vision"].items()):
        return True
    return any(party.intersection(gear["who"]) and any(
        has_airship(world, state) if area == AIRSHIP_AREA else state.can_reach_region(area, world.player)
        for area in gear["shops"]) for gear in sources["gear"].values())


def boss_rule(world: FFResonanceWorld, group: int):
    """The rule for beating a boss. Party sizes above what the seed can give (party members not
    shuffled) count as the most it can."""
    tier, level = BOSS_TIER[group], BOSS_LEVEL[group]
    members, continents, wants_airship = TIER_NEEDS[tier]
    player = world.player
    most = len(PARTY_MEMBERS) if world.options.shuffle_party_members else len(world.starting_party)
    extra = max(0, min(members, most) - len(world.starting_party))
    airship = wants_airship and not world.options.start_with_airship
    baseline, needs = TIER_BASELINE[tier], BOSS_NEEDS.get(group, lambda has: True)

    def beat(state: CollectionState) -> bool:
        if not (state.has_group("Party Members", player, extra)
                and state.has_group("Continent Unlocks", player, continents)
                and (not airship or state.has(AIRSHIP, player))):
            return False
        has = lambda capability: has_capability(world, state, capability, level)
        return baseline(has) and needs(has)

    return beat
