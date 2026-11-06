# Progression logic: design draft

The design for turning the world from "chests swap items" into a real Archipelago game, where items unlock places and the multiworld depends on them.

**How to use this document:**
- Write in it freely. Bullet points are enough, and rough notes are fine.
- Each section has what is already known, and **Your call** where a decision is yours. Where I have a suggestion, it is marked *Suggestion*. Ignore it if you have a better idea.
- When a section has settled, the apworld code follows from it (section 9). In-game tests come from section 8.

Related: [progression.md](progression.md) (the chapter-by-chapter reference), [IDEAS.md](../IDEAS.md) ideas 3 (open world), 4 (vehicles), 5 (key items), 16 (map blockers) and 17 (airship landing limits).

## 1. Where the world stands today

- **One region.** Every location is reachable from the start as far as logic goes. Late-game chests are simply late.
- **Progression items, with no logic yet (world 0.3.0).** One of each party member after the prologue (Fina, Lid, Nichol, Jake, Sakura, and Archwitch Fina since world 0.3.1), each of the 26 visions and 43 key items and artifacts go in the pool in place of filler. Each has its own option, on by default. They are classed as progression so the logic can use them later. The story still hands out its own copies, and chests and shinies that hold them keep them, so the story can always be finished. Equipment is "useful", and consumables and gil are "filler".
- **Locations:** 202 chests in 10 regions, and 92 shinies on the world map (an option, off by default), all from the game's own files (world 0.2.0). They are named after the game's maps, for example "Village of Kol Chest 1" (world 0.3.0). Chests and shinies that hold items with id 13000 and up (visions, key items, valuables, Tablet Shards) keep their vanilla content and are not locations. So are the 15 chest rows with no box placed on any map.
- **Goal:** reach a story checkpoint (`goal_story_checkpoint`, default 8050).
- **Options:** the goal, `include_shinies`, `excluded_regions`, `shuffle_party_members`, `shuffle_visions` and `shuffle_key_items`.

## 2. The experience

**Your call:** what should a good run feel like? Some questions to start with:
- **Length:** how long should a typical seed take? A full story run, or something shorter?
- **The goal:** finish the story, or something else as well? For example, a number of Tablet Shards (idea 1), beating certain bosses, or collecting Espers.
- **What feels different:** what is fun about Resonance specifically that items could play with? Party members, Visions, vehicles, Espers?
- **Limits:** what should never happen? For example, a seed that needs grinding, a story that breaks, or being stuck with nothing to do.
- **Other players:** how soon should this world start sending useful things to the rest of the multiworld? The first chapters are fairly linear.

## 3. The mode: follow the story, or open world

This choice shapes everything else.

**Follow the story (story mode).** The player plays the story as normal. Story progress opens each chapter's lands, and items gate *extra* things inside them: side areas, vehicles, optional bosses, upgrades.
- *For:* it works with the game as it is. The story never needs anything the mod cannot guarantee.
- *Against:* the main path is fixed, so early spheres are small, and progression items can only gate what the story does not need.

**Open world (idea 3).** Story progress is set or skipped so that lands are open, and items (vehicles, keys) decide where you can go.
- *For:* real routing, and big early spheres. This is what makes many Archipelago games fun.
- *Against:* it needs a lot of game work first: opening lands without the story, with events and NPCs in a sensible state, and a goal that does not depend on story order.

**Your call:** which mode first?

**Decided (round 30, 2026-11-06): open world first.** Players on the Archipelago Discord ask mostly for open world, and few want a story mode. The design is in [open_world.md](open_world.md). Story mode may come later, or not at all. The rest of this section is kept as the earlier thinking.

*Earlier suggestion:* story mode first, built so that open world can come later. The skip prologue work shows the story counter and flags can be set, so open world is not out of reach. But story mode can ship much sooner, and it teaches us which gates the game checks by item.

**Your direction so far.**
- **Early sketch (2026-11-04):** the first half linear, gated by the story; after the airship, continents as unlock items; the Crystal Tower as the goal.
- **Refined (2026-11-06): story mode gates itself, in part.** Getting the airship opens more places, but many stay locked, wholly or in part, until the story reaches them. For example, Gronoa has no way in until the story makes an entrance. So story mode does not need continent unlock items.
- **The risk:** a story run where one or two key items open nearly everything, and the player blazes through. Story mode needs some **artificial gates** of our own, so that progression items matter along the way.
- **Gates we make:**
  - **Map blockers** (IDEAS.md, idea 16): an NPC or barrier at a choke point that lets you through only with an item or flag. It works in both modes.
  - **Airship landing limits** (idea 17): no landing on a continent until its item is found. Mainly for open world, where these give the continent locks.

**Still to decide:**
- Which choke points get blockers, and with which items.
- How many gates a run should have, so it feels routed without feeling padded.
- Whether blockers can be added at all (idea 16's to-find-out list). The first in-game probe of a door gimmick or an NPC's collision answers that.

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

**What the game checks.** A gate only works as an Archipelago item if the game checks for the *item*, not for a story flag set at the same time. That is the main thing to test for each candidate (section 8).

## 5. Progression item candidates

Filled from progression.md and IDEAS.md idea 5. **Your call:** which ones go in, and are there others?

| Candidate | Item id | Gates | Game checks | Tested | In v1? |
|---|---|---|---|---|---|
| Chocobo (Choboco Saddle) | 30002 | Kolobos Island, the Felicitas region | the item | yes (round 5) | |
| Airship | unknown | world-map flight: Sanctums, volcanoes, ice islands, Whirlpool Hollow | unknown (29520 is cosmetic) | no: needs the flag test (idea 4) | |
| Radar: Magi-tenna | 27006 | tier 1 world-map treasures | unknown | no | |
| Radar: Resonance Stone | 27007 | tier 2 world-map treasures | unknown | no | |
| Radar: High-Power Generator | 27008 | tier 3 world-map treasures | unknown | no | |
| Gaia Hammer (field skill) | unknown | the sealing stone in Grandshelt Desert, to Titan | unknown (from Colosseum, proofs 29000–29003) | no | |
| White Jade Stone | 20005 | Holy, which clears the Bog of No Return: western Gronoa, Odin | unknown | no | |
| Lab Key Cards 1–3 | 20009–20011 | Research Center Ruins | unknown | no | |
| Tunnel Key | 20008 | probably the Zoldaad tunnels | unknown | no | |
| Dungeon Key, Throne Room Key | 20019, 20021 | Zoldaad Castle | unknown | no | |
| Ruby Fragment (×3) | 20030 | Carbuncle | unknown | no | |
| Broken Sword Hilt, Blade | 20031, 20032 | Odin (Iron Splitter) | unknown | no | |
| Tablet Shards | 25004 | the Tablet Shard turn-in (idea 1) | unknown | no | |
| Party members | units 1001–1008 (guests: 1013 Ignis, 1014 Alluvion, 1016 Charlotte) | battle strength; maybe story events | the story expects them | no | |
| Blocker passes (our own) | new | the choke points we block (idea 16) | the mod, since the gate is ours | no: needs idea 16 first | |
| Visions (26), summons (10 units; Bahamut has two) | 13017–13130; units 10451–10460 | battle strength | — | no | |

**Things to weigh:**
- **Story items in story mode.** A key item the story itself needs (a key on the main path) cannot be taken out of its place, or the story can stall until another player sends it. That may be fine, or it may be miserable. *Suggestion:* in v1, only shuffle gates on optional content, and keep main-path keys where they are.
- **Party members** would be the most Resonance-feeling progression, but the story scripts them joining. The story's conditions never test the party, though: only flags, the story counter, items, the Colosseum and unit levels (IDEAS.md, idea 19). So a member who joins early may be harmless. Round 30 tests it.
- **Upgrades as progressive items.** The three radar parts could be one "Progressive Radar" item, received three times.

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

**What the game data dump gives this section (2026-11-06).** `data/game/` (README, "The game data dump") is read from the game's own files:
- **The map graph.** `transitions.tsv` has 640 map exits on 143 maps, with the map and point each leads to. 18 of them have a condition (`{progress:N}` or `{flag:N}`). Logic regions can be built from it, not by hand.
- **The game's own blockers.** `gimmicks.tsv` has 282 blocking boxes, 43 no-entry zones and 41 blocking bases. Many have a condition such as `!{flag:928}`. These show where the game already gates the map, and which flag opens each gate (idea 16).
- **Airship landing points.** 81 on the world map, each with a destination id (idea 17).
- **Field items.** 197 field items hold an item: 94 on the world map and 103 elsewhere. Today the world has 83 world-map shinies, from what was seen in game. All 95 rows in `data/shinies.tsv` match the dump.
- **Chests.** The 238 chest table rows match `data/chests.tsv` exactly. A box is matched to its row by `m_Id`, and by its map or by its level's name (`gen_from_dump.box_matches`; round 3 confirmed both ways). 15 rows have no placed box on any map, and since world 0.2.0 they are not locations (`NO_BOX` in `data.py`). Among them is all of map 10050 (`02Lan_41`), which ships only a background level and has no map table row; its items 5 and 6 are not in any item table. Boxes with no `m_Id` (the native default, -1) are the open story chests that round 3 saw in map 2002.

**Your call, and facts to fill in:**
- When does **Kolobos** (Felicitas, Kolobos Ruins) open? The dump shows the Village of Kol is in Lanzelt (`02Lan_20`), not in Kolobos (round 30).
- Which regions can be **revisited** later, and from when (the airship)? Anything you cannot go back to belongs in `excluded_regions` by default, or needs logic that says "before chapter N".
- The **sub-areas** inside a region that need an item. For example, the Kolobos part of Grandshelt needs the Chocobo. Those become their own logic regions.

**How story progress fits the logic (story mode).** Story progress is not an item, so each chapter is an *event* in logic: "Chapter 2 open" is reached once chapter 1's region is. Locations in a chapter's lands need that event, plus any items for their sub-area. That gives the fill a sphere structure that follows the story.

## 7. Options

**Your call:** what should players be able to change? Some candidates:
- **The goal** (exists), plus other goals if section 2 adds them.
- **Shinies** (exists).
- **Which gates are shuffled:** for example, vehicles yes/no, key items yes/no, party members yes/no.
- **Excluded regions** (exists).
- **Starting items:** for example, start with the Chocobo, to open more early.
- **The skip prologue** is always on with "New Game (Archipelago)", and needs no option.

## 8. Tests needed before the logic can rely on them

Each is an in-game check. Most can be done with `ffrap_grant` on a save, and a look at whether the gate opens.

1. **For each key item in section 5:** does the gate open with the item alone (granted on a save before the story hands it out)? And does the story still work when the item is already in the bag before the story would hand it out?
2. **The airship:** which flag or item lets it fly (idea 4). That needs a flag diff around the point the story hands it out, with `ffrap_snapshot`.
3. **Party members:** does `AddUnit`, or setting `JoinStatus`, give a working member before the story would? And what does the story do when that member is already there?
4. **Revisiting:** which regions can be reached again after their chapter.
5. **Kolobos:** when it opens.
6. **The goal:** does the ending reach story 8050?

## 9. How this becomes code (for reference)

Once the sections above are settled:
- **`items.py`:** the chosen gates become `progression` items in the pool. Where an item is shuffled, its vanilla chest becomes a location, if it is not one already (ids at or above 13000 are kept vanilla today).
- **New `regions.py` and `rules.py`:**
  - a region per land (and per item-gated sub-area);
  - chapter events;
  - `set_rule` per location or entrance (`state.has("Chocobo", player)`, and so on).
- **The mod:** granting a progression item is already `AddInventory`, `AddUnit` or `SetFlag`. In story mode, the story's own hand-out of a shuffled item must be stopped, or the item ends up given twice. That is new mod work, per item.
- **Tests:** Archipelago's world tests (`test/`) check that every seed can be beaten. Unit tests check each rule.
