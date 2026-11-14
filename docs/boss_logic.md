# Boss Logic and Unshuffled Vision Placement

Logical requirements for the 41 boss checks in [data/bosses.tsv](../data/bosses.tsv), composable capability macros across party members, Visions, and shops, and location rules for unshuffled Visions (`shuffle_visions: false`) and character/Vision side-quests at `story = 8000`.

Related documents: [docs/bosses.md](bosses.md), [docs/logic.md](logic.md), [docs/open_world.md](open_world.md), and [IDEAS.md](../IDEAS.md) (idea 29).

## 1. Vanilla Strategy Guides vs. Open-World Randomizer

Strategy guides from `ffresonance.wiki`, `allthings.how`, `gmtreks.com`, and `keengamer.com` assume a linear story party, fixed Vision acquisition order, and vanilla story scripts. Five differences matter for Archipelago logic at `story = 8000`:

1. Default starters (`Rain` and `Lasswell`) have no healing, revival, or status-cleansing skills. Vanilla guides assume `Fina` (`Cure` Lv3, `Esuna` Lv5, `Pray` Lv8, `Cura` Lv17, `Raise` Lv23, `Curaga` Lv35) is always present.
2. In `DT_EquipmentItemData.json`, `Thunder God's Earrings` (`12080`, shuffled in the AP item pool) grants passive `Imbue Lightning` (`1523`), which adds Lightning to non-elemental physical attacks. It does not reduce incoming Lightning damage, and `Liquid Thunder` is immune to Lightning. Actual Lightning damage reduction comes from `Insulated Gloves` (`12034`, sold in Sian and in the AP pool), `Cape of the Raiju` (`11508`, AP pool), `Lightning (Vision)` (Awk 1 Resist Lightning, Awk 3 Lightning Immunity, MR 9 Lightning Eater), or `Cloud (Vision)` (Awk 1 Resist Lightning, Awk 3 Lightning Immunity).
3. Vanilla guides describe the first `Tellus` encounter in the Nameless Ruins (`boss:9031`) as ending automatically after a scripted attack. In [FFRArchipelago/Scripts/game.lua](../FFRArchipelago/Scripts/game.lua), `G.BossesPatch` clears `battleEventId` to `-1` on restored story bosses so they do not corrupt story state, turning `boss:9031` into a full 135,000 HP battle.
4. Only `Siren` is granted automatically to `Fina` and `Archwitch Fina` in [FFRArchipelago/Scripts/game.lua](../FFRArchipelago/Scripts/game.lua). The remaining Espers sit behind vanilla side-quests, so boss logic does not rely on Esper summons.
5. All `equipment` items in [apworld/ff_resonance/items.py](../apworld/ff_resonance/items.py) use `ItemClassification.useful`, so Archipelago's fill algorithm does not place progression weight on chest equipment unless promoted. Open-world shops in [data/game/shops.tsv](../data/game/shops.tsv), however, sell key defensive accessories and elemental weapons in infinite stock once their continent or the `Airship` is reachable, and scaled enemies allow Gil farming.

## 2. Progression Proxies for Sphere Curving and Vision Awakening

Archipelago `access_rule(state: CollectionState)` callbacks inspect which items and regions `state` currently holds; multiworld spheres are derived from those rules rather than passed into them as an integer. Without a progression proxy, starting on a late-game continent such as `Mysidia` would place `Salome` (Lv39, 200,000 HP, `Double Action`) or Awakening 3 passives (such as `Terra` Awk 3 `Ribbon`) in Sphere 1.

To curve boss readiness and Vision Awakening depth across the seed without tracking individual `Magicite Shard` (`25000`), `Magicite` (`25001`), and `Magicite Cryst` (`25002`) chests as progression items, rules use three `CollectionState` proxies:

- `ContinentsUnlocked(state)`: number of reachable continents among the 9 continent regions (`Grandshelt`, `Lanzelt`, `Kolobos`, `Dirnado`, `Olderion`, `Zoldaad`, `Mysidia`, `Gronoa`, `Pharm`).
- `PartyCount(state)`: number of available party members (starting roster plus collected character items, or `8` when `shuffle_party_members` is off).
- `HasAirship(state)`: `True` when `start_with_airship` is enabled or `state.has("Airship", player)`.

### Vision Awakening Curve

| Vision Tier | Required Progression Proxy | What It Unlocks |
|---|---|---|
| `Awk 0` | Own the Vision | Base active skills (`Cure`, `Esuna`, `Dispel`, tier-1 elemental skills) |
| `Awk 1` | `ContinentsUnlocked >= 2` | First awakening passives and skills (50% elemental resistances on `Clive`, `Charlotte`, `Bartz`, `Camille`, `Cloud`, `Lightning`, `Tidus`; `Leah` `Cura`/`Esuna`; `Firion` Instant Death immunity) |
| `Awk 2` | `ContinentsUnlocked >= 4` | Second awakening passives and skills (`Raise`, `Curaga`, `Reflect`, `Warrior of Light` 50% Dark resist, `Ayaka` Instant Death immunity) |
| `Awk 3 / MR 7-9` | `ContinentsUnlocked >= 5` and `HasAirship` | Full elemental immunities and absorbs (`Clive`, `Charlotte`, `Cloud`, `Lightning`, `Tidus`, `Warrior of Light`, `Cecil`, `Sephiroth`), `Reraise`, `Esunaga`, `Terra` `Ribbon`, `Leah` `Auto-Cure`, Finish skills |

### Boss Tier Baselines

| Tier | Level Band | Baseline Progression Requirement |
|---|---|---|
| Tier A | Lv 4-20 | Reachable region (`ContinentsUnlocked >= 1`, any starting roster) |
| Tier B | Lv 25-39 | `PartyCount >= 3`, `ContinentsUnlocked >= 2`, `CanHeal` |
| Tier C | Lv 39-52 | `PartyCount >= 4`, `ContinentsUnlocked >= 4`, `CanAoEHealOrRevive` |
| Tier D | Lv 50-63 | `PartyCount >= 5`, `ContinentsUnlocked >= 6`, `HasAirship`, `CanAoEHealOrRevive` |

**What is built (world 0.24.2).** Only the party, continent and Airship parts of the tiers (`TIER_NEEDS` in `locations.py`). None of the capability macros (`CanHeal`, `Has<Element>`, mitigations) are built, and no per-boss rule from section 5 is.
- Round 72: Liquid Thunder (`boss:9083` in `data/bosses.tsv`; section 5 lists it as `9101`) could not be beaten at party level 3 with Lasswell and Archwitch Fina and no gear. That party fails its section 5 rule: no Earth, no healing, no cleansing, no Lightning resistance. Until the rule is built, the boss is tier B.
- On foot, Liquid Thunder also holds the rest of Dirnado: only Dilmagia, Mt. Thunderclap Shard 22 and the fight are on the near side. Every other Dirnado location needs the boss's tier, or the Airship.
- Bosses' stats against a normal enemy of the same level (median of 367 enemies, along the curve scaling uses): HP 3x to 26x, Attack 0.9x to 2.4x, Intelligence 0.5x to 2.75x, Defence and Mind 0.45x to 1.55x. Scaling keeps each ratio. So a boss's danger is in its HP, its damage and its mechanics, not its Defence. Liquid Thunder's Intelligence is the highest of all (2.75x).

## 3. Composable Capability Matrix

Boss logic uses capability macros evaluated as `OR` across party members, Visions (gated by the Awakening curve above), and reachable open-world shops.

| Capability Macro | Party Members | Visions (with Awakening Gate) | Open-World Shops & Equipment Notes |
|---|---|---|---|
| `CanHeal` | `Fina` | `Leah` (Awk0), `Ayaka` (Awk0), `Y'shtola` (Awk0), `Warrior of Light` (Awk0), `Cecil` (Awk0), `Sephiroth` (Awk2 `Curaga`) | `Tidus` has Awk0 `Cure` only (single-target backup). |
| `CanAoEHealOrRevive` | `Fina` (`Pray`, `Raise`, `Arise`, `Reraise`, `Radiant Restoration`) | `Leah` (Awk1 `Cura`, Awk2 `Raise`, Awk3 `Reraise`, Finish), `Ayaka` (Awk1 `Purify`/`Raise`, Awk3 `Reraise`), `Y'shtola` (Awk1 `Manaward`, Awk2 `Cure III`) | Consumables (`Phoenix Down`, `Phoenix Pinion`, `Mist X-Potion`) exist in shops but do not replace sustained healing on Tier C/D bosses. |
| `CanCleanse` | `Fina` (`Esuna`, `Pray`, `Light Veil`) | `Ayaka` (Awk0 `Esuna`, Awk3 `Esunaga`, Finish), `Lightning` (Awk0 `Esuna`, Awk3 `Esunaga`), `Leah` (Awk1 `Esuna`, MR9 `Auto-Cure`), `Terra` (Awk3 `Ribbon` self-immunity) | Specific status accessories in `Airship`, `Grandport` (`Lanzelt`), and `Amore` (`Olderion`) shops can substitute for individual boss ailments. |
| `CanDispel` | `Nichol`, `Sakura` (`Magicide`) | `Ayaka` (Awk0 `Dispel`), `Tronn` (Awk2 `Dispel`), `Y'shtola` (Awk3 Finish) | None in shops. |
| `CanReflect` | `Lid` (`Reflect` Lv25) | `Charlotte` (Awk2), `Cecil` (Awk2), `Squall` (Awk2), `Leah` (Awk3), `Aileen` (Awk3) | `Reflect Ring` (`12046`, AP chest pool only). |
| `CanPhysAndMag` | Any 1 physical attacker + any 1 magic attacker (true for almost any 2+ roster or starter + caster Vision) | Any physical Vision + any magic Vision | Needed for `Tellus` (`9038`, `9048`) and `Yakhanati` (`9990`). |
| `HasMagicFire` | `Rain` | `Amelia` (Awk0), `Tronn` (Awk0), `Onion Knight` (Awk0), `Terra` (Awk0), `Squall` (Awk0), `Sephiroth` (Awk1) | `Fire Scroll I/II` (limited shop stock). |
| `HasPhysicalFire` | `Rain` | `Clive` (Awk0), `Vaan` (Awk0), `Squall` (Awk1) | `Solar Pendant` (`12076`, AP pool), `Flametongue` (`10004`, AP pool). |
| `HasMagicIce` | `Lasswell` | `Tronn` (Awk0), `Victoria` (Awk0), `Terra` (Awk0), `Y'shtola` (Awk0), `Noctis` (Awk0), `Sephiroth` (Awk1) | `Ice Scroll I/II` (limited shop stock). |
| `HasPhysicalIce` | `Lasswell` | `Charlotte` (Awk0), `Aileen` (Awk0), `Lightning` (Awk0) | `Icebrand` (`10005`, `Amore` shop in `Olderion`), `Kokytos` (`10108`, `Gaberada` shop in `Gronoa`), `Snow Spirit's Scarf` (`12077`, AP pool). |
| `HasMagicWind` | `Jake` (`Cyclone Laser` Lv42) | `Victoria` (Awk0), `Onion Knight` (Awk0), `Y'shtola` (Awk0), `Zidane` (Awk1) | `Wind Scroll I/II` (limited shop stock). |
| `HasPhysicalWind` | `Jake` | `Bartz` (Awk0), `Firion` (Awk0), `Tidus` (Awk0), `Clive` (Awk0) | `Sylph's Tiara` (`12078`, AP pool), `sonic Knuckles` (`10604`, `Mysidia` shop). |
| `HasMagicEarth` | `Lid` (`Earth Split` Lv44) | `Amelia` (Awk0), `Onion Knight` (Awk0) | `Earth Scroll I/II` (limited shop stock). |
| `HasPhysicalEarth` | `Lid` | `Camille` (Awk0), `Wilhelm` (Awk0), `Aileen` (Awk0), `Warrior of Light` (Awk0), `Bartz` (Awk0), `Vaan` (Awk0) | `Golem Core` (`12079`, AP pool). |
| `HasMagicLightning` | `Sakura` | `Tronn` (Awk0), `Shantotto` (Awk0), `Noctis` (Awk0), `Sephiroth` (Awk1) | `Lightning Scroll I/II` (limited shop stock). |
| `HasPhysicalLightning` | `Jake` (`Blitzstrahl` Lv33) | `Warrior of Light` (Awk0), `Bartz` (Awk0), `Cloud` (Awk0), `Lightning` (Awk0) | `Thunder God's Earrings` (`12080`, AP pool), `Shock Whip` (`10703`, `Dilmagia` shop in `Dirnado`). |
| `HasMagicWater` | `Nichol` | `Terra` (Awk0), `Squall` (Awk0), `Zidane` (Awk0), `Shantotto` (Awk0) | `Water Scroll I/II` (limited shop stock). |
| `HasPhysicalWater` | None | `Camille` (Awk0), `Charlotte` (Awk0), `Wilhelm` (Awk0), `Cloud` (Awk0), `Tidus` (Awk0) | `Azure Amulet` (`12081`, AP pool), `Aqua Blade` (`10008`, `Olderion` shop). |
| `HasMagicLight` | `Fina`, `Sakura` (`Light Blade` Lv19) | `Leah` (Awk0) | None in shops. |
| `HasPhysicalLight` | None | `Warrior of Light` (Awk0), `Firion` (Awk0), `Cecil` (Awk0), `Noctis` (Awk1) | `Halo Ring` (`12082`, AP pool), `Lightbringer` (`10012`, AP pool). |
| `HasMagicDark` | `Archwitch Fina`, `Sakura` (`Darkness` Lv13) | `Victoria` (Awk0), `Shantotto` (Awk1) | None in shops. |
| `HasPhysicalDark` | `Archwitch Fina` | `Cecil` (Awk0), `Sephiroth` (Awk0) | `Demon's Ring` (`12083`, AP pool). |

Generic `Has<Element>` macros expand to `HasMagic<Element> OR HasPhysical<Element>`. Bosses with physical immunity or physical counter passives (`Shoggoth`, `Liquid Flame`, `Iron Giant`, `Intangir`) require `HasMagic<Element>` specifically, while `Necromonarch` (which counters magic of its Fire and Light weaknesses) uses `HasPhysicalFire OR HasPhysicalLight`.

## 4. Eight-Element Mitigation and Status Immunity Table

Data extracted from `DT_VisionAwakeningMasteryData.json`, `DT_EquipmentItemData.json`, and [data/game/shops.tsv](../data/game/shops.tsv).

### Elemental Mitigation (`Has<Element>Mitigation`)

| Element | Visions (with Awakening/MR Gate) | Open-World Shops (Infinite Stock) | AP Chest Pool Gear (`useful`) |
|---|---|---|---|
| Fire | `Clive` (Awk1 Half, Awk3 Immune, MR9 Absorb) | `Fire Sprite Earrings` (`12030`, Sian in `Pharm`) | `Fire Sprite Earrings` (`12030`) |
| Ice | `Charlotte` (Awk1 Half, Awk3 Immune, MR9 Absorb) | `Tiara of Frost` (`12031`, `Mysidia`, Sniw in `Mysidia`, Sian in `Pharm`) | None |
| Wind | `Bartz` (Awk1 Half) | `Fujin's Fuda` (`12032`, Sian in `Pharm`), `Tsukiyo no Tachi` (`10205`, `Airship` Katana) | `Tsukiyo no Tachi` (`10205`) |
| Earth | `Camille` (Awk1 Half) | `Mole Doll` (`12033`, Sian in `Pharm`), `Gaia Gear` (`11412`, `Airship` Robe, grants Earth Immunity) | None |
| Lightning | `Cloud` (Awk1 Half, Awk3 Immune), `Lightning` (Awk1 Half, Awk3 Immune, MR9 Absorb) | `Insulated Gloves` (`12034`, Sian in `Pharm`) | `Insulated Gloves` (`12034`), `Cape of the Raiju` (`11508`, Robe) |
| Water | `Tidus` (Awk1 Half, Awk3 Immune, MR9 Absorb) | `Aquatic Veil` (`12035`, Sian in `Pharm`) | `Aquatic Veil` (`12035`) |
| Light | None | `Scintillating Ring` (`12036`, Sian in `Pharm`) | None |
| Dark | `Warrior of Light` (Awk2 Half, Awk3 Immune), `Cecil` (MR9 Immune), `Sephiroth` (MR9 Absorb) | `Silver Key` (`12037`, Sian in `Pharm`) | `Silver Key` (`12037`) |

Light has no Vision mitigation passive; `Scintillating Ring` in Sian (`Pharm`) is the only dedicated Light resistance item. Because Sian (`Pharm`) sells all 8 half-damage accessories and the Chapter 8 `Airship` sells `Gaia Gear` and `Tsukiyo no Tachi`, reaching `Pharm` or `HasAirship` satisfies elemental mitigation checks without promoting chest accessories to `progression`.

### Status & Instant-Death Mitigation

| Status Threat | Visions (with Awakening/MR Gate) | Open-World Shops (Infinite Stock unless noted) |
|---|---|---|
| Instant Death (`HasDeathMitigation`) | `Firion` (Awk1), `Ayaka` (Awk2) | `Safety Bit` (`12029`, `Airship` shop `6008`/`8009` and `Mysidia` shop `6014`/`8010`) |
| Petrify + Paralysis (`HasParalyzeMitigation`) | `Lightning` (Awk1 Paralysis), `Warrior of Light` (Awk1 Petrify), `Terra` (Awk3 `Ribbon`), `Leah` (MR9 `Auto-Cure`) | `Jeweled Ring` (`12023`, `Airship` and `Amore` in `Olderion`) |
| Charm (`HasCharmMitigation`) | `Ayaka` (Awk1), `Terra` (Awk3 `Ribbon`) | `Monk's Prayer Beads` (`12025`, `Airship`, `Amore` in `Olderion`, `Grandport` in `Lanzelt` [stock 2]) |
| Confuse + Berserk (`HasConfuseMitigation`) | `Cecil` (Awk1 Confuse), `Terra` (Awk3 `Ribbon`), `Leah` (MR9 `Auto-Cure`) | `Calm Armlet` (`12027`, `Airship` and `Amore` in `Olderion`) |
| Poison / Blind / Sleep / Silence | `Terra` (Awk3 `Ribbon`), `Leah` (MR9 `Auto-Cure`) | `Star Pendant` (`12018`), `Silver-Rimmed Glasses` (`12019`), `Headband` (`12020`), `White Cape` (`12021`) on `Airship` |

## 5. First-Pass Logical Requirements for All 41 Bosses

Stats, weaknesses, resistances, and passive traits come from `DT_BattleGroup.json`, `DT_UnitParameter.json`, and [data/bosses.tsv](../data/bosses.tsv). Each boss inherits its Tier baseline from Section 2 in addition to the boss-specific rule below.

### Tier A: Early Story Bosses and Low-Level Cave Masters (Lv 4-20)

| Group | Boss | Area (Map) | Lv | HP / Brk | Weak / Resist | Key Mechanics | First-Pass Logic Rule |
|---|---|---|---|---|---|---|---|
| `9004` | Belmodar | Grandshelt (`3000` Earth Shrine) | 4 | 2,000 / 350 | Weak: Water | Single-target lightning | Reachable (no extra requirements) |
| `9012` | The Hunger | Kolobos (`3040` Kolobos Ruins) | 9 | 2,500 / 450 | Weak: Ice | Low break gauge | Reachable (no extra requirements) |
| `9013` | Siren | Lanzelt (`3030` Siren's Tower) | 11 | 20,000 / 700 | Weak: Lightning; Half: Water, Wind | Inflicts Charm and Sleep | `CanHeal OR HasLightning` |
| `9969` | Marauder | Lanzelt (`10051` Marauder Cave) | 15 | 30,000 / 700 | Weak: Wind | Physical cleave | `CanHeal OR HasWind` |
| `9015` | Antlion | Lanzelt (`1000` Lanzelt Desert) | 20 | 20,000 / 600 | Weak: Water; Half: Earth | `Physical Counter` | `CanHeal OR HasWater` |
| `9101` | Liquid Thunder | Dirnado (`3050` Mt. Thunderclap) | 13 | 10,000 / 350 | Weak: Earth; Invalid: Lightning | `Gigavolt` AoE Lightning + Paralysis | `(HasEarth AND (CanHeal OR HasLightningMitigation OR CanCleanse)) OR Lightning (Vision)` |
| `9014` | Mom Bomb | Dirnado (`2050` Dwarven Forge) | 14 | 21,000 / 750 | Weak: Water; Half: Fire | +2 Bombs; `Explode` self-destruct at low HP | `HasWater AND (CanHeal OR HasFireMitigation)` |
| `9017` | Aether | Dirnado (`3070` Wind Shrine) | 18 | 34,000 / 700 | Weak: Ice; Invalid: Wind | Summons `Zu` minions | `(HasIce OR HasWindMitigation) AND CanHeal` |

### Tier B: Mid-Game Mechanics Gates (Lv 25-39)

Baseline: `PartyCount >= 3`, `ContinentsUnlocked >= 2`, `CanHeal`.

| Group | Boss | Area (Map) | Lv | HP / Brk | Weak / Resist | Key Mechanics | First-Pass Logic Rule |
|---|---|---|---|---|---|---|---|
| `9970` | Shoggoth | Dirnado (`10052` Shoggoth Cave) | 25 | 45,500 / 750 | Weak: Earth, Water | Physical Immunity (DEF 255), AoE Poison | `(HasMagicEarth OR HasMagicWater) AND (CanCleanse OR HasAirship)` |
| `9971` | Rukh | Olderion (`10053` Rukh Cave) | 26 | 46,800 / 900 | Weak: Wind; Invalid: Earth | Evasion buff and `Mighty Guard` | `HasWind AND (CanDispel OR CanAoEHealOrRevive)` |
| `9972` | Mindflayer | Olderion (`10054` Mindflayer Cave) | 28 | 52,000 / 800 | Weak: Earth; Adds weak: Fire, Invalid: Ice | +2 Mind Elementals (counter KO with `Blizzaga`); Paralysis, Poison, Silence | `HasEarth AND (CanCleanse OR HasParalyzeMitigation)` |
| `9973` | Gogmagog | Zoldaad (`10055` Gogmagog Cave) | 34 | 78,000 / 900 | Weak: Wind, Light | High single-target ATK (680) | `HasWind OR HasLight` |
| `9974` | Pyroviper | Zoldaad (`10056` Pyroviper Cave) | 37 | 89,700 / 900 | Weak: Water; Invalid: Fire | `Double Action`, heavy Fire/physical hits | `HasWater AND (CanAoEHealOrRevive OR HasFireMitigation)` |
| `9032` | Liquid Flame | Mysidia (`3180` Nameless Ruins) | 34 | 78,000 / 1,100 | Weak: Ice, Water; Absorb: Fire | `Physical Defense +60%`, `Physical Counter`, casts `Reflect` on party | `HasMagicIce OR HasMagicWater` |
| `9034` | Iron Giant | Mysidia (`3180` Nameless Ruins) | 34 | 85,000 / 1,000 | Weak: Lightning | `Physical Defense +60%`, `Physical Counter` | `HasMagicLightning` |
| `9031` | Tellus (1st) | Mysidia (`3180` Nameless Ruins) | 39 | 135,000 / 1,200 | Weak: Wind; Half: Earth | Endures at 20% HP (`HP20%で耐える`) | `HasWind AND (CanAoEHealOrRevive OR HasEarthMitigation)` |
| `9038` | Tellus (2nd) | Mysidia (`3200` Tower of Mysidia) | 39 | 135,000 / 1,200 | Weak: Wind; Half: Earth | `Double Action`, punishes breaking alternating Physical/Magic stance rules | `CanPhysAndMag AND HasWind` |

### Tier C: Chapter 5-6 Cave Masters, Sanctissimus Gauntlet, and Story Bosses (Lv 39-52)

Baseline: `PartyCount >= 4`, `ContinentsUnlocked >= 4`, `CanAoEHealOrRevive`.

| Group | Boss | Area (Map) | Lv | HP / Brk | Weak / Resist | Key Mechanics | First-Pass Logic Rule |
|---|---|---|---|---|---|---|---|
| `9975` | Salome | Mysidia (`10057` Salome Cave) | 39 | 200,000 / 1,000 | Weak: Wind; Half: Earth | `Double Action`, Charm + Poison | `HasWind AND (CanCleanse OR HasCharmMitigation)` |
| `9976` | Jotunn | Mysidia (`10058` Jotunn Cave) | 42 | 240,000 / 1,100 | Weak: Fire, Dark; Invalid: Ice | `Double Action`, rapid-stagger and low-HP escalation | `(HasFire OR HasDark) AND (HasIceMitigation OR CanDispel OR PartyCount >= 5)` |
| `9977` | Malboro Varietas | Olderion (`10059` Malboro Varietas Cave) | 45 | 270,000 / 900 | Weak: Fire | `Double Action`, multi-ailment breath, reacts to Fire hits | `HasFire AND CanCleanse` |
| `9987` | Archaeoaevis | Gronoa (`3250` Sanctissimus Shrine) | 40 | 130,000 / 1,200 | Weak: Wind (initial) | `Barrier Shift` rotates elemental weaknesses | `HasWind AND (PartyCount >= 4)` |
| `9988` | Dad Bomb | Gronoa (`3250` Sanctissimus Shrine) | 40 | 140,000 / 1,200 | Weak: Fire; Half: Ice | `Double Action`, self-destructs at low HP | `HasFire` |
| `9989` | Test Rider | Gronoa (`3250` Sanctissimus Shrine) | 40 | 150,000 / 1,100 | Weak: Earth, Light | `Double Action`, shifts between calm and enraged stances | `HasEarth OR HasLight` |
| `9990` | Yakhanati | Gronoa (`3250` Sanctissimus Shrine) | 40 | 145,000 / 1,100 | Weak: Wind, Dark | Alternates Physical-null and Magic-null barriers; Paralysis | `CanPhysAndMag AND (HasWind OR HasDark) AND (CanCleanse OR HasParalyzeMitigation)` |
| `9991` | Arch Gargoyles | Gronoa (`3250` Sanctissimus Shrine) | 40 | 2x 55,000 / 700 | Weak: Wind, Light | Two targets; living partner resurrects defeated partner | `HasWind OR HasLight` |
| `9992` | Dragon | Gronoa (`3250` Sanctissimus Shrine) | 42 | 175,000 / 1,400 | Weak: Lightning | `Double Action`, countdown breath (`Flame Breath` / `Windstorm`) | `HasLightning AND (HasFireMitigation OR HasWindMitigation OR CanHeal)` |
| `9044` | Gelidus | Gronoa (`3250` Sanctissimus Shrine) | 43 | 200,000 / 1,350 | Weak: Fire; Half: Ice | `Double Action`, `Deprotega` + physical spike when DEF is lowered | `HasFire AND (HasIceMitigation OR CanCleanse)` |
| `9039` | Lux | Gronoa (`3230` Rugged Mountain Path) | 41 | 125,000 / 1,100 | Weak: Dark; Half: Light | `Double Action`, Blind, buff dispel, healing passives | `HasDark OR HasLightMitigation` |
| `9040` | Elfdrit | Gronoa (`3240` Gronoa Shrine) | 42 | 120,000 / 1,200 | Weak: Fire, Light; Half: Dark | `Double Action`, restores break gauge, Poison/Sleep/Paralysis | `(HasFire OR HasLight) AND (CanCleanse OR HasDarkMitigation OR HasAirship)` |
| `9046` | Ignis | Pharm (`3260` Mt. Reizan) | 47 | 205,000 / 1,300 | Weak: Water; Half: Fire | `First Strike`, escalates on Water hits | `HasWater AND (HasFireMitigation OR PartyCount >= 5)` |
| `9048` | Tellus (3rd) | Pharm (`3270` Wandering Lands) | 49 | 220,000 / 1,400 | Weak: Wind; Half: Earth | `Double Action`, alternating Physical/Magic stance rules | `CanPhysAndMag AND HasWind` |
| `9051` | Behemoth | Grandshelt (`3280` Crystal Tower) | 52 | 320,000 / 1,500 | Weak: Wind, Light | `Double Action`, high DEF (400) and MDEF (400) | `HasWind OR HasLight` |

Sanctissimus Shrine (`3250`) is a sequential gauntlet (`Archaeoaevis` -> `Dad Bomb` -> `Test Rider` -> `Yakhanati` -> `Arch Gargoyles` -> `Dragon` -> `Gelidus`), so each boss in the chain inherits the requirements of the bosses before it.

### Tier D: Endgame Cave Masters and Optional Superbosses (Lv 50-63)

Baseline: `PartyCount >= 5`, `ContinentsUnlocked >= 6`, `HasAirship`, `CanAoEHealOrRevive`.

| Group | Boss | Area (Map) | Lv | HP / Brk | Weak / Resist | Key Mechanics | First-Pass Logic Rule |
|---|---|---|---|---|---|---|---|
| `9978` | Tartarosaurus | Pharm (`10061` Tartarosaurus Cave) | 50 | 350,000 / 1,100 | Weak: Ice; Half: Earth | `Double Action`, `Meteor` escalation at low HP | `HasIce` |
| `9979` | Catacumba | Gronoa (`10062` Catacumba Cave) | 54 | 380,000 / 1,100 | Weak: Fire, Light | `Double Action`, Instant Death attacks | `(HasFire OR HasLight) AND HasDeathMitigation` |
| `9980` | Necromonarch | Gronoa (`10063` Necromonarch Cave) | 55 | 444,400 / 1,200 | Weak: Fire, Light; Half: Earth | Counters Fire/Light weakness magic; high DEF (520); Paralysis | `(HasPhysicalFire OR HasPhysicalLight) AND (CanCleanse OR HasParalyzeMitigation)` |
| `9981` | Humbaba | Gronoa (`10064` Humbaba Cave) | 55 | 450,000 / 1,200 | Weak: Wind | `Double Action`, ATK 800, Paralysis, Blind, Confuse, Berserk | `HasWind AND (CanCleanse OR (HasParalyzeMitigation AND HasConfuseMitigation))` |
| `9982` | Titanoraidos | Pharm (`10065` Titanoraidos Cave) | 60 | 800,000 / 1,400 | Weak: Ice | `Double Action`, ATK 900, removes party members from battle | `HasIce AND (Fina OR Leah OR Ayaka)` |
| `9983` | Malboro Menace | Pharm (`10066` Malboro Menace Cave) | 60 | 700,000 / 1,400 | Weak: Fire | `Double Action`, `Putrid Breath` all ailments, counters weakness hits | `HasFire AND CanCleanse AND (Terra OR Leah OR Ayaka)` |
| `9136` | Intangir | Grandshelt (`3010` Dragon's Maw) | 52 | 300,000 / 1,300 | Weak: Earth, Light, Dark; Absorb: F/I/Wi/Th/Wa | `Physical Counter`, counters waking from Sleep, casts `Meteor` on defeat | `HasMagicEarth OR HasMagicLight OR HasMagicDark` |
| `9137` | Rogue Magitek Weapon | Grandshelt (`3010` Dragon's Maw) | 63 | 573,000 / 1,400 | Weak: Lightning, Water; Invalid: Dark; Half: F/I/Wi/E | `Haywire` (3 actions/turn), `Ultima`, `Blaster` (Instant Death) | `(HasLightning OR HasWater) AND HasDeathMitigation` |
| `9138` | Sephiroth | Lanzelt (`10218` Whirlpool Hollow) | 45 | 250,000 / 1,200 | Weak: Light (Phase 3) | `Double Action`, `Magic Defense +60%`, 3 phases, physical parry stance, Phase 3 DPS check | `HasPhysicalLight AND (PartyCount >= 5)` |

## 6. Unshuffled Visions (`shuffle_visions = False`) and Side-Quest Locations

When `shuffle_visions` is disabled in [apworld/ff_resonance/options.py](../apworld/ff_resonance/options.py), Visions remain in the MultiWorld state for logic and `final_boss_visions` counting rather than being omitted:

1. Starter Visions (`Tronn (Vision)` `13024001` and `Leah (Vision)` `13045001`, normally granted during the skipped Mitra story event `C01_014_03`) are precollected via `push_precollected` in [apworld/ff_resonance/items.py](../apworld/ff_resonance/items.py).
2. `generate_early()` in [apworld/ff_resonance/world.py](../apworld/ff_resonance/world.py) forces `include_crystals.value = 1` so all 16 Sanctum of Light locations exist, and clamps `final_boss_visions` against `len(STARTER_VISIONS) + len(CRYSTALS)` (`18`).
3. `create_all_locations()` in [apworld/ff_resonance/locations.py](../apworld/ff_resonance/locations.py) locks each of the 16 Sanctum Visions onto its corresponding `Sanctum of Light (...)` location (`place_locked_item`) and locks `Sephiroth (Vision)` (`13113001`) onto `Whirlpool Hollow: Sephiroth` (`boss:9138`) when `include_bosses` is enabled.
4. Because locked items at checked locations are sent by the Archipelago server just like shuffled items, the client and Lua mod (`G.CrystalsPatch` and `BOSS_ROWS_NO_REWARD` in [FFRArchipelago/Scripts/game.lua](../FFRArchipelago/Scripts/game.lua)) require no special-case branching: touching the Sanctum crystal or defeating Sephiroth checks the location and grants its own Vision from the server.

### Unshuffled Vision Locations by Continent

| Vision | AP Item ID | Unshuffled Source | Continent / Region |
|---|---|---|---|
| `Tronn` | `13024001` | Precollected at start (`C01_014_03` skipped) | Starting Inventory |
| `Leah` | `13045001` | Precollected at start (`C01_014_03` skipped) | Starting Inventory |
| `Clive` | `13114001` | `Sanctum of Light (Clive)` (`10216`) | `Grandshelt` |
| `Warrior of Light` | `13054001` | `Sanctum of Light (Warrior of Light)` (`10203`) | `Lanzelt` |
| `Cloud` | `13099001` | `Sanctum of Light (Cloud)` (`10208`) | `Lanzelt` |
| `Sephiroth` | `13113001` | `Whirlpool Hollow: Sephiroth` (`boss:9138`, map `10218`) | `Lanzelt` |
| `Terra` | `13091001` | `Sanctum of Light (Terra)` (`10201`) | `Kolobos` |
| `Noctis` | `13112001` | `Sanctum of Light (Noctis)` (`10202`) | `Dirnado` |
| `Zidane` | `13103001` | `Sanctum of Light (Zidane)` (`10206`) | `Dirnado` |
| `Onion Knight` | `13085001` | `Sanctum of Light (Onion Knight)` (`10207`) | `Dirnado` |
| `Tidus` | `13105001` | `Sanctum of Light (Tidus)` (`10200`) | `Olderion` |
| `Firion` | `13083001` | `Sanctum of Light (Firion)` (`10205`) | `Olderion` |
| `Squall` | `13101001` | `Sanctum of Light (Squall)` (`10209`) | `Olderion` |
| `Shantotto` | `13107001` | `Sanctum of Light (Shantotto)` (`10210`) | `Zoldaad` |
| `Cecil` | `13087001` | `Sanctum of Light (Cecil)` (`10211`) | `Zoldaad` |
| `Y'shtola` | `13110001` | `Sanctum of Light (Y'shtola)` (`10212`) | `Zoldaad` |
| `Bartz` | `13089001` | `Sanctum of Light (Bartz)` (`10213`) | `Mysidia` |
| `Lightning` | `13109001` | `Sanctum of Light (Lightning)` (`10214`) | `Mysidia` |
| `Vaan` | `13108001` | `Sanctum of Light (Vaan)` (`10215`) | `Mysidia` |

### Vision Side-Quests (`DT_RequestData.json` & `DT_TalkEventData_VisionCharaEvent.json`)

The remaining 7 Visions come from multi-step character events (`CharaEvent`). At `story = 8000`, all `AcceptCondition` checks on `{progress:0}` are satisfied without checking whether a specific party member is in the active roster, but two quests test another quest's completion counter (`{progress:7}` and `{progress:36}`), and several quests span multiple continents.

| Quest ID | Quest Name | Vision & Extra Reward | Reward Event Row (`Comp`) | Prerequisite at `story = 8000` | Start Map | Step Maps & Boss Fights | Required Continents in Logic |
|---|---|---|---|---|---|---|---|
| `Q22` (`ChrEv_0340`) | Errand's End | `Amelia` (`13017`) + `Magicite` (`25001`) | `ChrEv_0340_005_01` (`{progress:37}>=50`) | `{progress:7}>=60` (`Q06` Token Legacy complete) | `2110` Zoldaad Capital (bulletin board) | `3160` Zoldaad Castle, `2110-2114` Zoldaad -> `2070` Olderion -> `3100` Waterfall Way -> `2110` Zoldaad | `Zoldaad` + `Olderion` |
| `Q23` (`ChrEv_2810`) | Forger of Wills | `Aileen` (`13080`) + `Magicite` (`25001`) | `ChrEv_2810_007_03_03` (`{progress:38}>=40`) | None (`{progress:0}>=5010`) | `2060` Dilmagia (`Dirnado`) | `2061` Shipyard, `2060` Dilmagia (`Dirnado`), `2120` Rebel Hideout (`Zoldaad`), `2020` Village of Kol (`Lanzelt`) -> `2060` Dilmagia | `Dirnado` + `Zoldaad` + `Lanzelt` |
| `Q24` (`ChrEv_2280`) | Victoria Revivified | `Victoria` (`13027`) + `Magicite` (`25001`) | `ChrEv_2280_005_01` (`{progress:39}>=50`) | None (`{progress:0}>=5060`) | `2130` Mysidia (`Mysidia`) | `2130` Mysidia -> `3213` Victoria's Shrine (`Mysidia`) -> `1000` Mysidia field -> `2130` Mysidia (battle `9107`) | `Mysidia` |
| `Q25` (`ChrEv_0410`) | The Call from Beyond | `Camille` (`13033`) + `Magicite` (`25001`) | `ChrEv_0410_007_02` (`{progress:36}>=60`) | None (`{progress:0}>=5000`) | `2113` Imperial Residences (`Zoldaad`) | `1000` Zoldaad field (`ChrEv_0410_002_01`) -> `3121` Phantom Train (`Zoldaad`, battle `9095`) | `Zoldaad` |
| `Q28` (`ChrEv_0470`) | The Shield of the Weak | `Charlotte` (`13060`) + `Magicite Cryst` (`25002`) | `ChrEv_0470_006_01` (`{progress:40}==50`) | None (`{progress:0}>=7000`) | `2030` Grandport Harbor (`Lanzelt`) | `2012`/`2017` Grandshelt -> `3040` Kolobos Ruins (battle `9104`) -> `3031` Cavern of Swords (`Lanzelt`, battle `9105`) -> `2017` Grandshelt | `Lanzelt` + `Grandshelt` + `Kolobos` |
| `Q31` (`ChrEv_2630`) | O General! My General! | `Wilhelm` (`13062`) + `Magicite Cryst` (`25002`) | `ChrEv_2630_005_01` (`{progress:48}==50`) | `{progress:36}==60` (`Q25` Camille quest complete) | `2111` Zoldaad Castle Plaza (`Zoldaad`) | `1000` Zoldaad field (`!{flag:443}`, `!{flag:444}`) -> `2110-2114` Zoldaad -> `3130`/`3131` Weapons Factory -> `2110-2114` Zoldaad | `Zoldaad` |
| `Q32` (`ChrEv_0420`) | The Admirable Apprentice | `Ayaka` (`13051`) + `Magicite Cryst` (`25002`) | `ChrEv_0420_005_01` (`{progress:47}==50`) | None (`{progress:0}>=7020`) | `2170` Town of Sian (`Pharm`) | `3100` Waterfall Way (`Olderion`) -> `10030` Infernal Hollow (`Zoldaad`, battle `9134`) -> `3050` Mt. Thunderclap (`Dirnado`) -> `2170` Sian (`Pharm`) | `Pharm` + `Olderion` + `Zoldaad` + `Dirnado` |

Note on `2113: Imperial Residences` (`Q25` Camille start): [tools/gen_apworld_data.py](../tools/gen_apworld_data.py) lists `2113` in `NO_OPEN_WORLD_ROUTE` because `transitions.tsv` has no walk-trigger door into `2113`. In-game, `2113` is reached from `2110: Zoldaad, the Imperial Capital` via the Zoldaad streetcar talk event (`C04_06Zol_01_Choice`).

### Party Member Character Quests (`Q00-Q07` in `DT_RequestData.json`)

For future side-quest location checks (and `Q06`, which gates `Amelia` `Q22`), these are the map and continent requirements of the 8 party member quests at `story = 8000`:

| Quest ID | Quest Name | Character & Accessory Reward | Reward Event Row (`Comp`) | Start Map | Step Maps & Boss Fights | Required Continents in Logic |
|---|---|---|---|---|---|---|
| `Q00` (`ChrEv_0010`) | A New Leaf | Rain (`12050` Knight's Medallion) | `ChrEv_0010_010_01` (`{progress:1}>=90`) | `20002` Airship Deck | `2012`/`2017`/`2000` Grandshelt -> `3100` Waterfall Way (`Olderion`, battle `9091`) -> `20002` Airship Deck | `HasAirship` + `Grandshelt` + `Olderion` |
| `Q01` (`ChrEv_0020`) | The Twin Titleholders | Lasswell (`12051` Crest of Criticality) | `ChrEv_0020_007_02` (`{progress:2}>=70`) | `2150` Gaberada (`Gronoa`) | `2150` Gaberada -> `10001` Lost Cave (`Grandshelt`, battle `9092`) -> `2150` Gaberada | `Gronoa` + `Grandshelt` |
| `Q02` (`ChrEv_0030`) | Shimmering Reflections | Fina (`12052` Blessed Pendant) | `ChrEv_0030_007_01` (`{progress:3}>=50`) | `2130` Mysidia (`Mysidia`) | `3000`/`3001` Earth Shrine (`Grandshelt`) -> `3030` Siren's Tower (`Lanzelt`) -> `2070` Olderion & `2080` Lake Dorr (`Olderion`) | `Mysidia` + `Grandshelt` + `Lanzelt` + `Olderion` |
| `Q03` (`ChrEv_0040`) | Beyond the Blue | Lid (`12053` Chocobo Nitro) | `ChrEv_0040_006_01` (`{progress:4}>=50`) | `2061` Shipyard (`Dirnado`) | `3060` Mobliz Shipyard & `2060` Dilmagia (`Dirnado`, battle `9093`) -> `20001` Airship | `Dirnado` + `HasAirship` |
| `Q04` (`ChrEv_0050`) | Nichol's Duty | Nichol (`12054` Enchanted Ring + Leviathan) | `ChrEv_0050_007_01` (`{progress:5}>=60`) | `2070` Olderion (`Olderion`) | `2080` Lake Dorr & `3080` Cave of Waters (`Olderion`, battle `9094`) -> `2070` Olderion | `Olderion` |
| `Q05` (`ChrEv_0060`) | Last Respite | Archwitch Fina (`12056` Moonlight Ring) | `ChrEv_0060_008_01` (`{progress:6}>=70`) | `2017` Grandshelt Capital (`Grandshelt`) | `2015`/`2016`/`2012` Grandshelt -> `20002` Airship Deck | `Grandshelt` + `HasAirship` |
| `Q06` (`ChrEv_0070`) | Token Legacy | Jake (`12047` Trick Coin) | `ChrEv_0070_008_01` (`{progress:7}>=60`) | `2110` Zoldaad Capital (`Zoldaad`) | `2110-2114` Zoldaad Capital, `2101`/`2102` Downtown Zoldaad, `3160` Zoldaad Castle (battle `9096`) | `Zoldaad` |
| `Q07` (`ChrEv_0080`) | Mysidia, Ever Blooming | Sakura (`12055` Amulet of Magic Absorption) | `ChrEv_0080_006_01` (`{progress:8}>=60`) | `2130` Mysidia (`Mysidia`) | `2130` Mysidia, `3190` Arcane Library, `3200` Tower of Mysidia (battle `9097`) | `Mysidia` |
