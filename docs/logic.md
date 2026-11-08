# Progression logic: design draft

The design for turning the world from "chests swap items" into a real Archipelago game, where items unlock places and the multiworld depends on them.

**How to use this document:**
- Write in it freely. Bullet points are enough, and rough notes are fine.
- Each section has what is already known, and notes where a decision is yours. Suggestions are marked *Suggestion*.
- When a section has settled, the apworld code follows from it (section 9). In-game tests come from section 8.

Related: [progression.md](progression.md) (the chapter-by-chapter reference), [IDEAS.md](../IDEAS.md) ideas 3 (open world), 4 (vehicles), 5 (key items), 16 (map blockers) and 17 (airship landing limits).

## 1. Where the world stands today

- The game is currently treated as one region. Every location is reachable from the start as far as logic goes. Late-game chests are simply late.
- Progression items exist with no logic yet (world 0.3.0). One of each party member after the prologue (Fina, Lid, Nichol, Jake, Sakura, and Archwitch Fina since world 0.3.1), each of the 26 visions, and 43 key items and artifacts go into the pool in place of filler. Each has an option on by default. They are classed as progression so logic can use them later. The story still hands out vanilla copies, and chests or shinies holding them keep them so the story remains beatable. Equipment is "useful", while consumables and gil are "filler".
- There are 202 chest locations across 10 regions, plus 92 optional world-map shinies, all derived from game files (world 0.2.0). Locations are named after game maps (for example "Village of Kol Chest 1"). Chests and shinies holding items at id 13000 and up (visions, key items, valuables, Tablet Shards) keep vanilla content and are not locations, alongside the 15 chest rows with no placed map box.
- The default goal is reaching story checkpoint 8050 (`goal_story_checkpoint`).
- Supported player options include the goal, `include_shinies`, `excluded_regions`, `shuffle_party_members`, `shuffle_visions` and `shuffle_key_items`.

## 2. The experience

Questions to resolve for run pacing:
- How long should a typical seed take: a full story run or something shorter?
- Should the goal be finishing the story or alternative targets like collecting Tablet Shards (idea 1), defeating specific bosses, or collecting Espers?
- What unique game mechanics should items gate (party members, visions, vehicles, Espers)?
- What failure states must be avoided (required grinding, softlocks, or prolonged routing dead ends)?
- How early should the world start sending useful items to other multiworld players given early story linearity?

## 3. The mode: follow the story, or open world

This choice shapes everything else.

**Follow the story (story mode).** The player plays the story as normal. Story progress opens each chapter's lands, and items gate *extra* things inside them: side areas, vehicles, optional bosses, upgrades.
- *For:* works with the game as it is. The story never needs anything the mod cannot guarantee.
- *Against:* the main path is fixed, so early spheres are small, and progression items can only gate what the story does not need.

**Open world (idea 3).** Story progress is set or skipped so that lands are open, and items (vehicles, keys) decide where you can go.
- *For:* real routing, and big early spheres. This is what makes many Archipelago games fun.
- *Against:* it needs a lot of game work first: opening lands without the story, with events and NPCs in a sensible state, and a goal that does not depend on story order.

**Decided (round 30, 2026-11-06): open world first.** Players on the Archipelago Discord ask mostly for open world, and few want a story mode. The design is in [open_world.md](open_world.md). Story mode may come later, or not at all. The rest of this section is kept as earlier reference.

*Earlier suggestion:* story mode first, built so that open world can come later. The skip prologue work shows the story counter and flags can be set, so open world is not out of reach. But story mode can ship much sooner, and it teaches us which gates the game checks by item.

**Direction notes:**
- The early sketch (2026-11-04) had the first half linear and story-gated; after the airship, continents served as unlock items with the Crystal Tower as the goal.
- As refined on 2026-11-06, story mode gates itself in part. Getting the airship opens more places, but many stay locked until the story reaches them (for example, Gronoa has no entrance until the story creates one). Story mode therefore does not need continent unlock items.
- A key risk is that one or two key items open nearly everything while the player blazes through. Story mode needs custom gates so progression items remain meaningful.
- Custom gate types under consideration:
  - Map blockers (IDEAS.md, idea 16): an NPC or barrier at a choke point requiring an item or flag. Works in both modes.
  - Airship landing limits (idea 17): restricting landing on a continent until finding its unlock item. Mainly for open world.

**Still to decide:**
- Which choke points get blockers, and with which items.
- How many gates a run should have, balancing routing against padding.
- Technical feasibility of adding blockers in-game (idea 16).

## 4. What the mod can do in game

What a progression item can be depends on what the mod can grant and what the game checks.

| Grant | How | Tested |
|---|---|---|
| Bag items (consumables, equipment, key items, artifacts) | `AddInventory` | yes, every round since round 1 |
| Gil | `SetCurrentMoney` | yes (round 5) |
| Visions | `visionList` plus `AddInventory`, the FFRSLib way | yes in round 1; an Archipelago item since world 0.3.0. One received before the save owns a vision waits (mod 0.12.0). Round 30 tests it |
| Party members | `CPP_VM_Party:AddUnit`, and `JoinStatus` 0 when the party is full (mod 0.12.0) | an Archipelago item since world 0.3.0. The story sets `JoinStatus` itself, in talk events (IDEAS.md, idea 19). Round 30 tests it |
| Story flags | `SetFlag` | yes (the skip prologue sets 21) |
| Vehicles | the Chocobo by item 30002 | yes: the saddle alone lets you ride (round 5). The airship is unknown: 29520 only changes how it looks |

A gate only works as an Archipelago item if the game checks for the *item*, not for a story flag set at the same time. That is the main thing to test for each candidate (section 8).

## 5. Progression item candidates

Filled from progression.md and IDEAS.md idea 5.

| Candidate | Item id | Gates | Game checks | Tested | In v1? |
|---|---|---|---|---|---|
| Chocobo (Choboco Saddle) | 30002 | Kolobos Island, the Felicitas region | the item | yes (round 5) | |
| Airship | unknown | world-map flight: Sanctums, volcanoes, ice islands, Whirlpool Hollow | unknown (29520 is cosmetic) | no: needs the flag test (idea 4) | |
| Radar: Magi-tenna | 27006 | tier 1 world-map treasures | unknown | no | |
| Radar: Resonance Stone | 27007 | tier 2 world-map treasures | unknown | no | |
| Radar: High-Power Generator | 27008 | tier 3 world-map treasures | unknown | no | |
| Gaia Hammer (field skill) | unknown | the sealing stone in Grandshelt Desert, to Titan | unknown (from Colosseum, proofs 29000-29003) | no | |
| White Jade Stone | 20005 | Holy, which clears the Bog of No Return: western Gronoa, Odin | unknown | no | |
| Lab Key Cards 1-3 | 20009-20011 | Research Center Ruins | unknown | no | |
| Tunnel Key | 20008 | probably the Zoldaad tunnels | unknown | no | |
| Dungeon Key, Throne Room Key | 20019, 20021 | Zoldaad Castle | unknown | no | |
| Ruby Fragment (x3) | 20030 | Carbuncle | unknown | no | |
| Broken Sword Hilt, Blade | 20031, 20032 | Odin (Iron Splitter) | unknown | no | |
| Tablet Shards | 25004 | the Tablet Shard turn-in (idea 1) | unknown | no | |
| Party members | units 1001-1008 (guests: 1013 Ignis, 1014 Alluvion, 1016 Charlotte) | battle strength; maybe story events | the story expects them | no | |
| Blocker passes (our own) | new | the choke points we block (idea 16) | the mod, since the gate is ours | no: needs idea 16 first | |
| Visions (26), summons (10 units; Bahamut has two) | 13017-13130; units 10451-10460 | battle strength | - | no | |

**Trade-offs to consider:**
- A key item the story itself needs on the main path cannot easily be randomized without risking softlocks while waiting for other players. In v1, only shuffle gates on optional content while keeping main-path keys vanilla.
- Party members provide high thematic flavor, but the story scripts their joins. Story conditions check flags, counters, items, and levels rather than party lists (IDEAS.md, idea 19), so early joins appear viable (tested in round 30).
- The three radar components could be combined into a "Progressive Radar" item received three times.

## 6. Regions and access

The location regions today, with where each opens in the story:

| Region | Chests | Opens (story) | Needs, beyond the story | Can you go back later? |
|---|---|---|---|---|
| Grandshelt | 40 | chapter 1 | | |
| Lanzelt | 28: Village of Kol, Grandport Harbor, Siren's Tower, Oblivion Palace | chapter 1 (Village of Kol) | Chocobo? | |
| Kolobos | 8: Town of Felicitas, Kolobos Ruins | ? | | |
| Dirnado | 19 | chapter 2 | | |
| Olderion | 23 | chapter 3 | | |
| Zoldaad | 21 | chapter 4 | keys inside (Tunnel, Dungeon, Throne Room)? | |
| Mysidia | 25 | chapter 5 | Radar Pulse (story) | |
| Gronoa | 17 | chapter 6 | Holy for the west | |
| Pharm | 11 | chapter 7 | | |
| Crystal Tower | 10 | chapter 8 | | |
| World Map (shinies) | 92 | varies | airship, radar tiers | |

**Reference data from game dump (2026-11-06):**
- In `transitions.tsv`, there are 640 map exits across 143 maps with target coordinates, 18 of which have explicit progress or flag conditions. Logic regions can be generated directly from these exits.
- The game already has 282 blocking boxes, 43 no-entry zones, and 41 blocking bases documented in `gimmicks.tsv`, many with conditions like `!{flag:928}`. These show existing native gates and the flags that clear them (idea 16).
- There are 81 airship landing points on the world map, each with a destination id (idea 17).
- Of 197 field items holding items (94 on the world map and 103 elsewhere), the world currently tracks 83 world-map shinies based on in-game discovery. All 95 rows in `data/shinies.tsv` match the dump.
- All 238 chest table rows match `data/chests.tsv` exactly. Boxes match by `m_Id` and map or level name (`gen_from_dump.box_matches`). The 15 chest rows without a placed box on any map are excluded from location generation (`NO_BOX` in `data.py`), including unused map 10050 (`02Lan_41`). Boxes with default `m_Id` (-1) are open story chests from map 2002.

**Open routing questions:**
- When does Kolobos (Felicitas, Kolobos Ruins) open? The dump shows Village of Kol is in Lanzelt (`02Lan_20`), not Kolobos (round 30).
- Which regions can be revisited later, and from what point (e.g. after acquiring the airship)? Irreversible areas belong in `excluded_regions` by default or require temporal logic rules.
- Identify sub-areas inside regions that require specific items (such as the Kolobos section of Grandshelt requiring the Chocobo) to define child regions.

**How story progress fits the logic (story mode).** Story progress is not an item, so each chapter is an *event* in logic: "Chapter 2 open" is reached once chapter 1's region is. Locations in a chapter's lands need that event, plus any items for their sub-area. That gives the fill a sphere structure that follows the story.

## 7. Options

Candidates for player customization:
- The goal condition (exists), plus secondary objectives if added.
- Inclusion of field shinies (exists).
- Shuffle toggles for specific gate categories (vehicles, key items, party members).
- Region exclusions (exists).
- Starting inventory adjustments (such as starting with the Chocobo).
- Prologue skip remains automatically active on Archipelago new games without requiring a toggle.

## 8. Tests needed before the logic can rely on them

1. For each key item in section 5: verify whether the gate opens with the item alone before story grant, and ensure the story functions normally if the item already exists in inventory.
2. Airship: identify which flag or item enables flight (idea 4) via snapshot diff around story unlock.
3. Party members: confirm whether `AddUnit` or setting `JoinStatus` grants fully functional party members early, and verify engine behavior during subsequent scripted joins.
4. Revisiting: catalog which regions remain accessible after chapter completion.
5. Kolobos: determine exact story unlock timing.
6. Goal: verify whether story progression reliably reaches 8050 at game completion.

## 9. How this becomes code (for reference)

Once requirements are finalized:
- `items.py`: selected gates become `progression` items in the pool. When an item is shuffled, its vanilla chest becomes an active location.
- New `regions.py` and `rules.py`:
  - Create regions per land and item-gated sub-area.
  - Define chapter progression events.
  - Set access rules per location or entrance (`state.has("Chocobo", player)`).
- Mod scripts: item grants use existing `AddInventory`, `AddUnit`, or `SetFlag`. In story mode, native story item rewards must be suppressed to avoid duplicate grants.
- Tests: Archipelago generation tests (`test/`) confirm beatability, with dedicated unit tests validating specific rule evaluations.
