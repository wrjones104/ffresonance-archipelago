# Progression logic: design draft

The design for turning the world from "chests swap items" into a real Archipelago game, where items unlock places and the multiworld depends on them.

**How to use this document:**
- Write in it freely. Bullet points are enough, and rough notes are fine.
- Each section has what is already known, and notes where a decision is yours. Suggestions are marked *Suggestion*.
- When a section has settled, the apworld code follows from it (section 9). In-game tests come from section 8.

Related: [progression.md](progression.md) (the chapter-by-chapter reference), [IDEAS.md](../IDEAS.md) ideas 3 (open world), 4 (vehicles), 5 (key items), 16 (map blockers) and 17 (airship landing limits).

## 1. Where the world stands today

**World 0.4.0:** a seed starts with one continent (`starting_continent`). The others need their Unlock item. There is one logic region per continent, and the Crystal Tower and the goal need every unlock. Everything on a continent counts as reachable once it opens, which round 44 starts to test. The starting party comes from the yaml (`starting_roster`, `starting_character_1` to `_4`). The notes below are from before this.

- Before world 0.4.0, the game was treated as one region. Every location was reachable from the start as far as logic went. Late-game chests were simply late.
- Progression items exist with no logic yet (world 0.3.0). One of each party member after the prologue (Fina, Lid, Nichol, Jake, Sakura, and Archwitch Fina since world 0.3.1), each of the 26 visions, and 43 key items and artifacts go into the pool in place of filler (29 key items since world 0.10.0, which leaves artifacts out: IDEAS.md, idea 26). Each has an option on by default. They are classed as progression so logic can use them later. The story still hands out vanilla copies, and chests or shinies holding them keep them so the story remains beatable. Equipment is "useful", while consumables and gil are "filler".
- There are 202 chest locations across 10 regions, plus 92 optional world-map shinies, all derived from game files (world 0.2.0). Locations are named after game maps (for example "Village of Kol Chest 1"). Chests and shinies holding items at id 13000 and up (visions, key items, valuables, Tablet Shards) keep vanilla content and are not locations, alongside the 15 chest rows with no placed map box.
- The goals are `final_boss` (the default from world 0.15.0): win the last battle, Rain against Sol (world 0.14.0; before that, story checkpoint 8050), and `tablet_shards`.
- Supported player options include the goal, `excluded_regions`, `shuffle_party_members`, `shuffle_visions` and `shuffle_key_items`. From world 0.15.0, `include_shinies`, `include_crystals` and `include_tablet_shards` are on by default and hidden from the template; a yaml can still turn them off for a test seed.

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

**Decided (round 30, 2026-11-06): open world first.** Players on the Archipelago Discord ask mostly for open world, and few want a story mode. The design is in [open_world.md](open_world.md). Story mode may come later, or not at all.

**Rounds 31 and 32 implementation decisions:**
- Starting state initializes at story 7090 and transitions to the Crystal Tower (map 3280), triggering story 8000 with the airship spawned and Crystal Tower open.
- The airship is free from the start with no separate airship progression item.
- Continents are gated by airship landing restrictions via native `BP_MapNonLandingArea_C` boxes.
- Enemy stats dynamically scale via `DT_UnitParameter` curve rewriting with `follow` party tracking.

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
| Party members | `CPP_VM_Party:AddUnit`, and `JoinStatus` 0 when the party is full (mod 0.12.0) | yes: verified in rounds 30 and 32. Units join active party or roster when full and are swappable |
| Story flags | `SetFlag` | yes (the skip prologue sets 21) |
| Vehicles | the Chocobo by item 30002; airship free in open world | yes: Chocobo saddle alone enables riding (round 5). Airship is free from start in open world (round 31); continents gated by landing boxes |

A gate only works as an Archipelago item if the game checks for the *item*, not for a story flag set at the same time. That is the main thing to test for each candidate (section 8).

## 5. Progression item candidates

Filled from progression.md and IDEAS.md idea 5.

| Candidate | Item id | Gates | Game checks | Tested | In v1? |
|---|---|---|---|---|---|
| Chocobo (Choboco Saddle) | 30002 | Kolobos Island, the Felicitas region | the item | yes (round 5) | |
| Airship | free in open world | world-map flight: Sanctums, volcanoes, ice islands, Whirlpool Hollow | native at story 8000 | yes (round 31): free from start; landing boxes gate continents | no |
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
| Tablet Shards | 25004 | the Tablet Shard turn-in (idea 1) | unknown | 99 confirmed in data dump | |
| Party members | units 1001-1008 (guests: 1013 Ignis, 1014 Alluvion, 1016 Charlotte) | battle strength; maybe story events | the story expects them | yes (rounds 30 & 32) | |
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
2. Airship: resolved for open world (free from start at story 8000; landing restriction boxes gate continents).
3. Party members: confirmed in rounds 30 and 32; `AddUnit` grants playable units to party or roster, and roster units can be swapped into the active party.
4. Revisiting: catalog which regions remain accessible after chapter completion.
5. Kolobos: determine exact story unlock timing.
6. Goal: round 57 reached 8050 before the last floor, so world 0.14.0 uses the last battle's win instead (open_world.md, section on the goal).

## 8a. Gates the game already checks (round 56, off-line)

Round 58: Mobliz Shipyard (map 3060) is not a gate but a stuck switch. Two of its four elevators (uids 73 and 75) start deactivated; in chapter 2 a lever puzzle turns 73 on, and a story scene likely turns 75 on. The open world start skips both, so chests 1 and 3 and shards 71 and 79 could not be reached. Mod 0.47.0 turns both on at each visit on a seed's save, so the logic stays as it is.

From the game data dump. Each still needs a test in game: does the gate open with an item from Archipelago, on the open world start?

| Gate | What the game checks | Logic | State |
|---|---|---|---|
| Oblivion Palace (map 2031, Lanzelt): 25 chests | A Tablet Shard turn-in: `DT_TalkEvent_CollectMedal` opens chest *n* at 3, 6, 9, 12, 16, 20, ... 99 shards. Each step is `{progress:43}==k&{transferItem:0,25004}>=N`. A blocking base stands while `{progress:43}==0` (quest not started) | World 0.11.0: each palace chest needs its shards. All 99 shards are progression then. Without `include_tablet_shards` the chests are filler only | Works (round 56): with 4 shards from Archipelago one chest opened in game, and Universal Tracker showed chest 1; at 6, the second. The turn-in takes the shards held and counts those turned in so far |
| Treasure radar (Magi-tenna 27006, Resonance Stone 27007, High-Power Generator 27008) | A side quest on the airship (`DT_MapAirShip`): boarding with a part runs the next step, `{progress:49}==30 & {progress:51}==14 & {item:27007}>=1` and so on, 15 steps in all | Not yet. The 94 world-map shinies have no visibility condition, so what each tier reveals is not in our tables | Probe in game first |
| Research Center Ruins (map 3220, Gronoa) | Doors 41, 42 and 43 run `Gim_EV_HaveKeyItemLV1` to `LV3`, so the door tests the card. The cards are shinies on the same map (32: level 1, 33: level 2, 37: level 3), with 3 Tablet Shards (34 to 36) | World 0.12.0 (`data/gates.tsv`): chests 0, 1 and 3 and shards 34 and 36 need the level 1 card; chests 2, 4 and 5 and shard 35 need levels 1 and 2. With `shuffle_key_items` off: filler only | Rooms confirmed (round 56): the user found the level 2 card behind the level 1 door, the level 3 card behind the level 2 door, and the level 3 door leads to the White Jade Stone area (a boss in vanilla). Next: the cards' shinies as locations (the user's list) |
| Zoldaad Castle throne room (map 3160) | The door's events test `{item:20021}` (Throne Room Key) with flags 407 and 422 | Not yet | The only plain item check found. Tunnel and Dungeon Keys are not in any condition |

## 9. How this becomes code (for reference)

Once requirements are finalized:
- `items.py`: selected gates become `progression` items in the pool. When an item is shuffled, its vanilla chest becomes an active location.
- New `regions.py` and `rules.py`:
  - Create regions per land and item-gated sub-area.
  - Define chapter progression events.
  - Set access rules per location or entrance (`state.has("Chocobo", player)`).
- Mod scripts: item grants use existing `AddInventory`, `AddUnit`, or `SetFlag`. In story mode, native story item rewards must be suppressed to avoid duplicate grants.
- Tests: Archipelago generation tests (`test/`) confirm beatability, with dedicated unit tests validating specific rule evaluations.
