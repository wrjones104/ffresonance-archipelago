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

# Party size, continents unlocked, and Airship requirement per tier (docs/boss_logic.md).
TIER_NEEDS = {"A": (0, 0, False), "B": (3, 2, False), "C": (4, 4, False), "D": (5, 6, True)}
# Fights that gate places but are no locations, so they are not in data/bosses.tsv (which must match
# the mod's G.BOSSES): battle group -> (tier, level). Round 73 (the user): Behemoth, level 52 in the
# game, is tier B once the Sworn Six's assist hits deal 1 damage (game.BehemothPatch). Its skills
# count to level 39, the top of tier B.
GATE_BOSSES = {9051: ("B", 39)}
BOSS_TIER = {int(b["key"].split(":")[1]): b["tier"] for b in BOSSES} | {g: t for g, (t, _) in GATE_BOSSES.items()}
BOSS_LEVEL = {int(b["key"].split(":")[1]): b["level"] for b in BOSSES} | {g: lv for g, (_, lv) in GATE_BOSSES.items()}

# Round 74: awakening level N costs one item of tier N (DT_VisionUpgradeItemData): a Magicite
# Shard, a Magicite, a Magicite Cryst. A level counts once there are AWAKENING_COPIES of each tier
# up to it, since a fight's needs often come from two Visions (a heal and an element). Until round
# 73, unlocked continents stood in for it, and a tester met tier B bosses in logic with no Shard.
AWAKENING_ITEMS = ("Magicite Shard", "Magicite", "Magicite Cryst")
AWAKENING_COPIES = 2

# Round 74 (a tester): a boss that acts twice a turn kills a small party before it can act. These
# need one party member more than their tier, up to tier D's five (docs/boss_logic.md, section 5:
# Double Action). Tier D's bosses are at five already.
# Tier B: Pyroviper, Salome, Tellus (Tower of Mysidia), Behemoth. Tier C: Jotunn, Malboro Varietas,
# Dad Bomb, Test Rider, Dragon, Gelidus, Lux, Elfdrit, Tellus (Wandering Lands). Round 121 (the dump's
# passive 1003, Double Action): Archaeoaevis and Yakhanati too.
MULTI_ACTION = {9093, 9109, 9038, 9051, 9110, 9111, 9074, 9073, 9076, 9044, 9039, 9040, 9048, 9075, 9072}
MULTI_ACTION_MOST = TIER_NEEDS["D"][0]

# Each tier's baseline: from tier B a healer, from tier C a group heal or a revive.
TIER_BASELINE: dict[str, Callable[[Callable[[str], bool]], bool]] = {
    "A": lambda has: True,
    "B": lambda has: has("heal"),
    "C": lambda has: has("aoe_heal") or has("revive"),
    "D": lambda has: has("aoe_heal") or has("revive"),
}



def any_magic(has: Callable[[str], bool]) -> bool:
    """Magic damage of any element, for bosses that shut out physical attacks for a while."""
    return any(has(f"{element}_magic") for element in ELEMENTS)


# Per-boss needs (docs/boss_logic.md, section 5), checked against the game dump: each boss unit's
# weaknesses, passives and traits in DT_UnitParameter (round 121 for tiers C and D).
# `has` takes a capability from data/game/capabilities.tsv, or an element for either attack type.
# Bosses not listed need their tier's baseline only.
BOSS_NEEDS: dict[int, Callable[[Callable[[str], bool]], bool]] = {
    9013: lambda has: has("heal") or has("lightning"),                                      # Siren
    9016: lambda has: has("heal") or has("lightning") or has("water"),                      # Adrastea
    9079: lambda has: has("heal") or has("wind"),                                           # Marauder
    9060: lambda has: has("heal") or has("water"),                                          # Antlion
    9014: lambda has: has("water") and (has("heal") or has("resist_fire")),                 # Mom Bomb
    9017: lambda has: (has("ice") or has("resist_wind")) and has("heal"),                   # Aether
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
    9051: lambda has: has("wind") or has("light"),                                          # Behemoth
    # Tier C. The baseline is a group heal or a revive.
    9110: lambda has: has("fire") or has("dark"),                                           # Jotunn
    # Several ailments in one breath.
    9111: lambda has: has("fire") and has("cleanse"),                                       # Malboro Varietas
    # Its weakness changes during the fight; wind is the first.
    9075: lambda has: has("wind"),                                                          # Archaeoaevis
    9074: lambda has: has("fire"),                                                          # Dad Bomb
    9073: lambda has: has("earth") or has("light"),                                         # Test Rider
    # It shifts between shutting out physical and magic attacks.
    9072: lambda has: (has("wind") or has("dark")) and any_magic(has),                      # Yakhanati
    9071: lambda has: has("wind") or has("light"),                                          # Arch Gargoyles
    9076: lambda has: has("lightning"),                                                     # Dragon
    # Deprotega on the party, then a strong physical attack.
    9044: lambda has: has("fire") and (has("resist_ice") or has("cleanse")),                # Gelidus
    9039: lambda has: has("dark") or has("resist_light"),                                   # Lux
    # Poison, Sleep and Paralysis.
    9040: lambda has: (has("fire") or has("light")) and (has("cleanse") or has("immune_poison")),  # Elfdrit
    9046: lambda has: has("water") and (has("resist_fire") or has("aoe_heal")),             # Ignis
    # Counters when its rules of engagement (physical or magic turns) are broken.
    9048: lambda has: has("wind") and any_magic(has),                                       # Tellus
    # Tier D. The baseline is a group heal or a revive.
    9112: lambda has: has("ice"),                                                           # Tartarosaurus
    # Instant Death attacks.
    9113: lambda has: (has("fire") or has("light")) and (has("immune_death") or has("revive")),  # Catacumba
    # Counters magic of its weakness, so its weakness hits must be physical.
    9114: lambda has: has("fire_physical") or has("light_physical"),                        # Necromonarch
    # Paralysis, Blind, Confuse and Berserk.
    9115: lambda has: has("wind") and has("cleanse"),                                       # Humbaba
    # Removes party members from battle; a revive is in the baseline.
    9116: lambda has: has("ice"),                                                           # Titanoraidos
    9117: lambda has: has("fire") and has("cleanse"),                                       # Malboro Menace
    # Counters physical attacks (passive 1082) and absorbs five elements.
    7042: lambda has: has("earth_magic") or has("light_magic") or has("dark_magic"),        # Intangir
    # Three actions a turn when enraged; Dark does nothing.
    7057: lambda has: has("lightning") or has("water"),                                     # Rogue Magitek Weapon
    # Phase 1 has Magic Defense +60%; phase 3 (unit 2520) acts three times a turn, is weak to light
    # and absorbs dark. The phases between rotate fire, ice, earth and water weaknesses.
    9138: lambda has: has("light"),                                                         # Sephiroth
}


def party_in_hand(world: FFResonanceWorld, state: CollectionState) -> set[int]:
    party = set(world.starting_party)
    if world.options.shuffle_party_members:
        party |= {unit for unit in PARTY_MEMBERS if state.has(ITEMS[UNIT_ITEM_BASE + unit]["name"], world.player)}
    return party


def has_airship(world: FFResonanceWorld, state: CollectionState) -> bool:
    return bool(world.options.start_with_airship) or state.has(AIRSHIP, world.player)


def awakening(world: FFResonanceWorld, state: CollectionState) -> int:
    level = 0
    for name in AWAKENING_ITEMS:
        if not state.has(name, world.player, AWAKENING_COPIES):
            break
        level += 1
    return level


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
    if group in MULTI_ACTION:
        members = min(members + 1, MULTI_ACTION_MOST)
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
