# Open world: design draft

How an open world seed could work. The story is skipped, the world is open, and Archipelago items decide where you can go.

**Why now (round 30, 2026-11-06).** Players on the Archipelago Discord ask mostly for open world, and few want a story mode. Open world comes first, and story mode may never come. Open world also avoids story events that undo our items, such as the story swapping the two Finas.

**Round 31 (2026-11-07): decided.**
- The start: story 7090, then the Crystal Tower (map 3280), where an event moves the story to 8000. Then the Crystal Tower is open and the airship is there. Discovered via FFRSLib developer options, replacing option A's 9000 (section 3).
- The airship is free from the start with no airship item.
- Continents are locked by landing: the airship cannot land on a continent until its unlock item arrives. The game already does this natively for Mysidia before story 5020 (section 4).

**How to use this document:** the same way as [logic.md](logic.md). Each section has what the game data shows, a *Suggestion*, and notes where the decision is yours. Facts come from the game data dump (`data/game/`, `dump/`) unless a round is named. The research scripts are short and can be run again; their results are summarised here.

Related: [logic.md](logic.md), [progression.md](progression.md), and [IDEAS.md](../IDEAS.md) ideas 3 (open world), 4 (vehicles), 16 (map blockers), 17 (airship landing limits) and 19 (a random starting party).

## 1. The idea

1. "New Game (Archipelago)" skips the whole story, not just the prologue. The save starts in the story's cleared state, with the airship.
2. Our own gates replace the story's: continent locks for the airship, blockers at choke points, and items the game already checks.
3. Enemy levels follow the party, so any continent can be first.
4. The locations are the things the cleared world still has: chests, shinies, side quests, optional bosses and NPC gifts.
5. The goal is something the cleared world can still do (section 7).

## 2. What the story counter does in the game data

The story counter is `Progress[0]`. Every story gate is a condition such as `{progress:0}>=5020`, in a table or on a map actor.

**Key values:**

| Value | What happens |
|---|---|
| 1000 to 1260 | Chapter 1. The prologue skip sets 1030 |
| 2000, 3000, ... 8000 | Each chapter starts at its thousand |
| 4250 | The airship appears on the world map (`DT_MapAirShip`, `spawnCondition`) |
| 5020 | World map exits open to Mysidia, Sunioo, the Nameless Ruins, the Tower of Mysidia, Jotunn Cave, Salome Cave and three Sanctums |
| 7090 | The world map exit to the Crystal Tower opens |
| 8050 | After the last boss (Sol). The world's goal today |
| 9000 | The ending sets this (event `C08_822_05`, before the staff roll). Chapter 9 in `DT_ChapterData` is "Epilogue". This is the cleared state |
| over 10000 | Tested in 6 places only (airship deck variants). Probably unused |

**Story blockers mostly close for good.** Of the map blockers with a story condition, most test `<` or `==`: they stand only during one story scene. For example, 42 of the 47 `BP_MapGimmick_NoEntry_C` zones with a story condition are like that. At 9000 nearly all of them are gone. The few that open later (such as `{progress:0}>=4000` in the Earth Shrine) are open at 9000 too.

**The island list follows chapters.** `DT_MapReleaseConditionData` opens one island per chapter, from Grandshelt at 2000 to the Land of the Crystals at 9000. The Colosseum's rematch list uses the same values.

**Flags.** The main story's 633 talk events turn on 91 flags (80 stay on) and turn off 22. Side events turn on 109 more. Map gimmicks set others as you play (doors, switches). A cleared save holds all of the main story's flags.

**Item checks on maps are few.** Only the Throne Room Key door in Zoldaad Castle, the Cabin Key exit on the world map, and the Chamber of Arms weapons test `{item:N}` on a map. Most item checks are inside talk events.

## 3. The starting state

**Option A: the cleared state (9000).**
- *For:* the world is fully open, and our gates are the only gates. Story blockers are gone. The airship is there.
- *Against:* story events and story bosses do not happen any more, so they cannot be checks. Towns and NPCs are in their after-story state.
- *Needs:* a "skip to the end": the counter at 9000, the main story's flags (from the talk event tables, in story order), the party, and the airship placed (`DT_MapAirShip` has a `gameClearLocation` for exactly this).

**Option B: the airship state (5000).** The first four chapters' lands are open and the airship flies. But chapters 5 to 8 still run as story, and their lands open only through it. This is half story mode.

**Option C: an early state with the story's gates rewritten.** Keep the counter low and rewrite every story condition to an item check. There are hundreds of conditions, and story events would still fire when you walk into them, in a strange order. Too fragile.

**Decided (round 31):** story 7090, then the Crystal Tower, which sets 8000 through its own event (see the top of this document). The open questions for that state are the same as for option A: which towns, events and bosses are still there.

*Earlier suggestion:* option A. Round 31's `ffrap_story 9000` probe (on a save not linked to a seed) shows what the cleared world looks like with only the counter set. Next, we find which flags it needs. The best reference is a real cleared save: if you or a friend has one, an `ffrap_snapshot` of it gives every flag at once.

## 4. Gates: how items decide where you go

| Gate | How | State |
|---|---|---|
| The airship | Free from the start (decided, round 31) | No item |
| Continents | No landing on a continent until its item arrives (idea 17), with the game's own no-landing boxes (below) | Round 32 probe: `ffrap_noland` |
| Ships and the Chocobo | The Chocobo is item 30002, and the game checks the item (round 5). Ship routes are story transitions | Chocobo: works. Ships: unknown at 9000 |
| Dungeons and choke points | Our own blockers (idea 16), which work everywhere (mod 0.11.3). Or the game's own exits, with their condition rewritten | Blockers: work. Rewriting a live exit's condition: not tried |
| Key items the game checks | The Throne Room Key door; the Cabin Key exit; the radar parts for world-map treasures | Already in the pool (world 0.3.0) |

**No-landing boxes (found in the game data, round 32):**
- The world map has 111 `BP_MapNonLandingArea_C` actors. Each one is a box (a `CPP_MapAirShipCanNeverLandingBox` component, with a position, a half-size and a yaw) and an `m_Condition` string. While the condition holds, or when it is empty, the airship cannot land in the box.
- Most of the 111 boxes are small (under 700 units across) and have no condition, keeping the airship off town entrances.
- Twelve boxes have conditions. Seven are side-quest steps (`{progress:24}==10` and similar), and two test flag 95 (`!{flag:95}`, in Mysidia). Three are story locks: `{progress:0}<5020` over Mysidia, `{progress:0}<6000` on Gronoa's landing spot (which also runs an event), and `{progress:0}<7020` in Pharm.
- The game locks an entire continent this way: before story 5020, one box of half-size 2400 x 6000 x 700 at (-18053, -8493) with condition `{progress:0}<5020` covers Mysidia.
- A continent lock can be implemented as one or more large boxes per continent with mod-controlled conditions.
- In round 32 testing, a box spawned at airship height (z 1500) lifted the airship over it and broke the camera while still permitting landing. Because the box collision counts as ground, boxes must sit on the terrain like native game boxes (e.g. Mysidia center height 393). The Blueprint has no script; the C++ class `CPP_MapNonLandingArea` reads the box and condition.
- Round 33 probes (mod 0.15.0): `lock mysidia` tests immediate condition evaluation on native boxes, `spawn` places new boxes at ground level, `here` lists boxes under the player, and `show` draws outlines.
- **Round 33 results:**
  - **A changed condition waits for a landing.** `lock mysidia` and `unlock mysidia` worked only after the airship landed and took off again. A spawned box blocked landing at once, but a new condition on it also waited for a landing. So the game reads a box's condition when the box starts, and again when the airship lands or takes off. For continent locks this matters only when an unlock item arrives in flight: the player would have to land somewhere first. Round 34 probes `refresh` (setting the box's collision ourselves) and looks for a function that re-reads the conditions.
  - **The Pharm story box is one landing spot, not the continent.** Half-size 473 x 304 at (-5930, -17400). Locking it cannot lock Pharm. Pharm (and Gronoa, whose story box is also on its landing spot) will need our own big boxes, like Mysidia's.
  - **A spawned box hides the airship's shadow.** It sits at the Mysidia box's height (393, 700 up and down), so its top can be above the ground where it was spawned. Round 34 compares its collision with the game's own boxes (`here` now logs it).
  - `show` draws the box outlines. Useful for placing continent boxes.

**Continent bounds (from landing points, with island-prefixed IDs; x/y in game units):**

| Continent | x | y |
|---|---|---|
| Grandshelt | 12000 to 18000 | 20000 to 22000 |
| Lanzelt | 10000 to 13000 | 9000 to 15000 |
| Kolobos | 3500 to 15000 | 10500 to 19000 |
| Dirnado | 13000 to 21000 | -3000 to 5000 |
| Olderion | -3000 to 5500 | -5000 to 5500 |
| Zoldaad | -11000 to -1700 | 7000 to 18500 |
| Mysidia | -19500 to -16000 | -11000 to -4000 |
| Gronoa | 9000 to 16000 | -15000 to -13000 |
| Pharm and the Crystal Tower | -11000 to -3500 | -19000 to -5500 |

These bounds are approximate. Kolobos and Lanzelt overlap, requiring multiple boxes or a shared boundary. Walking, the Chocobo, ships, and caves can also cross between continents, requiring blockers (idea 16) or rewritten transition conditions.

## 5. Enemy levels

**What the data shows:**
- Enemy stats are fixed per unit in `DT_UnitParameter` (level, HP, attack). No enemy uses a level curve (`LevelParamId -1` on all 367 enemies), so scaling an enemy requires rewriting its table row.
- Nearly every enemy belongs to one region. Only 9 of 261 units in the encounter tables appear in two regions, so regional scaling remains isolated.
- Levels by region (random encounters):

| Region | Levels | Region | Levels |
|---|---|---|---|
| Grandshelt | 1 to 6 | Zoldaad | 21 to 30 |
| Kolobos | 5 to 9 | Mysidia | 31 to 38 |
| Lanzelt | 6 to 16 | Gronoa | 30 to 42 |
| Dirnado | 11 to 18 | Pharm | 40 to 52 |
| Olderion | 18 to 26 | Crystal Tower | 44 to 54 |
| | | Dragon's Maw (optional) | 45 to 70 |

Bosses run from level 4 (Belmodar) to 99 (Omega).

- Stats follow level closely. A fit over 256 normal enemies, log(stat) against level:

| Stat | Growth per level | Per 10 levels | Fit (r²) |
|---|---|---|---|
| HP | 1.108 | x2.8 | 0.65 |
| Attack | 1.046 | x1.6 | 0.86 |
| Defence | 1.047 | x1.6 | 0.74 |
| Intelligence | 1.062 | x1.8 | 0.67 |
| Mind | 1.048 | x1.6 | 0.68 |
| Agility | 1.047 | x1.6 | 0.77 |
| Break gauge | 1.045 | x1.6 | 0.43 |
| EXP | 1.136 | x3.6 | 0.82 |
| Gil | 1.109 | x2.8 | 0.80 |

MP does not correlate with level (r² 0.09) and remains unchanged.

- The damage formula reads levels directly via `DT_UnitParameterCalc` (`sameLevelDamageCalcMagnification` and `deffenceIgnoreDamageCalcLevelRate`). Level fields must change in tandem with stats.
- Party level is queryable via `CPP_BFL_Unit:GetPlayableUnitLevel`.

**Scaling design.** A scaled enemy keeps base stats adjusted by growth rates: `stat * growth^(new level - own level)`. EXP and gil scale proportionally so leveling remains worthwhile.
- Clamp mode (`enemy_scaling: clamp`, `enemy_level_range: 5`): enemy levels pull into the party average ± 5. A level 40 Gronoa enemy meets a level 10 party at level 15. Grandshelt remains easy while later continents remain appropriately challenging.
- Range 0: all enemies match the party's level.
- Off: original shipped levels.
- Bosses: separate toggle to avoid trivializing or over-buffing boss encounters.
- Updates: rows rewrite on the field whenever the party's average level changes, never during battle.

**Round 31 & 32 findings:**
- The simple exponential growth rate produced excessive attack at low levels. Real enemies follow `log(stat) = a + b log(level) + c level` (r² 0.88 for attack, 0.70 for HP). Using relative level ratios eliminates constant `a`.

| Stat | b | c | Fit (r²) |
|---|---|---|---|
| HP | 0.3675 | 0.08917 | 0.70 |
| Break gauge | -0.1249 | 0.05094 | 0.48 |
| Attack | 0.3207 | 0.02946 | 0.88 |
| Defence | 0.7752 | 0.00867 | 0.83 |
| Intelligence | 0.5644 | 0.03269 | 0.71 |
| Mind | 0.7289 | 0.01236 | 0.75 |
| Agility | 0.7853 | 0.00899 | 0.86 |
| EXP | -0.0647 | 0.12967 | 0.84 |
| Gil | 0.0934 | 0.09910 | 0.82 |

- In the shipped game, parties normally out-level enemies by 10 or more levels from mid-game onward. Late-game enemies placed at exact party levels hit much harder than expected.
- Mod 0.14.0 introduced `at` (band center percentage), `hp`/`power` multipliers, and dynamic `follow` tracking. Mod 0.15.0 splits `attack` and `magic` controls and exports `scale.txt` after each rescale.
- **Round 33: something else wrote enemy rows. It was the FFR Randomizer mod, not the game** (found off-line before round 34; IDEAS.md, idea 10).
  - A Metal Gigantuar in Pharm showed level 45 while our band was 0 to 4. The dump has it at 52. A rescale also read Steel Bat (ID 2, level 1 and HP 68 in the dump) as level 47, HP 4800, attack 422, EXP 1760.
  - FFRRandomizer was enabled. Its enemy shuffle gives a swapped-in enemy the stats of the enemy it replaces. In that seed, Steel Bat fought in place of Nanochu (level 47), and Metal Gigantuar in place of Thunder Gigas (level 45). Both match the levels seen.
  - It writes its rows again every 3 seconds. It undid our rescale 1.5 seconds after we wrote it.
  - So there is no sign yet that the game itself changes `DT_UnitParameter`. Round 34 checks this with the randomizer off: after a save load, the table check should find nothing to write again.
  - Mod 0.15.1's table check (every 10 seconds on the field) and its "originals are the latest values" rule stay. They are cheap and make the rescale hold against anything else that writes the table. Mod 0.15.2 warns when FFRRandomizer is on.

## 6. Locations in the cleared world

| Kind | Count | At 9000 |
|---|---|---|
| Chests | 202 | All present: save state tracks looted flags independently of story progress |
| Shinies | 92 (world map) | Present; some depend on story conditions |
| NPC gifts and side quests | ~200 talk events (idea 21) | Main chapter quests with strict equality story checks expire, but free-talk gifts and post-game quests remain |
| Optional bosses | Espers, 15 strong enemies, Dragon's Maw, superbosses (Omega, Shinryu) | Availability to be verified |
| Vision Sanctums | Most of 26 visions | Availability to be verified |
| Story bosses | - | Defeated: their events check story progress values below 9000 |

## 7. The goal

Because a cleared save starts past the story ending, candidate goals include:
- Tablet Shards: turn in N of the 99 shards (idea 1).
- Espers: defeat and collect the nine Espers.
- Superbosses: defeat Omega (level 99) or Shinryu (level 95) if accessible.
- Multiworld artifacts: collect N custom items distributed across players to open the final area.

## 8. What the story used to give, now items

The story natively awards party members, starter visions, the airship, and key items. In open world, these become Archipelago items or starting loadout:
- Party: 8 playable characters (world 0.3.1 places 6 in the pool with Rain and Lasswell starting).
- Visions: all 26 are randomized in the pool.
- Airship: unlock mechanism detailed in section 4.
- Key items: 43 items in the pool.

## 9. Order of work

1. Round 31 probes (`ffrap_scale`, `ffrap_airship`, `ffrap_story 9000`): confirmed scaling works and exposed difficulty spikes.
2. Round 32 probes: validated `at 80` scaling curve and grounded no-landing boxes (`ffrap_noland`).
3. Round 33 probes: test separate `attack`/`magic` multipliers, box locking, ground-height spawning, and box queries. Results: locks apply after a landing; the Pharm story box is one spot; the scaling band in force was not the expected one (the FFR Randomizer mod rewrote it).
4. Round 34 probes: the table check and `ffrap_scale show`. Results: the game does not write enemy rows; `attack 50` felt best at party level 3 in Pharm. The box probes wait for round 35 (no airship on that save).
5. Skip to open world: mod 0.16's `ffrap_openstart` writes story 7090 and an arrival at the Crystal Tower's dock, on a new game or on a skipped save (`now`). Round 35: it works; two tower events set story 8000 and the airship waits at the dock. Round 36: the events write only story 8000, so mod 0.18.0 writes 8000 itself and arrives at the dock (`dock`) or on the world map in the airship (`air`), with no events. Round 37: the user chose `air`, so mod 0.19.0 makes it the default and keeps a choice over a restart. Next: an apworld option sent in slot data, so a seed decides it with no console command.
   - Active Time Chats: an open world start marks all 56 as released and played (`chat.DataMap`) and empties the notice queue (round 37, mod 0.19.0).
   - Vision items waited for good on this start, because the story's first visions never come. Round 38 read the synchro keys, and mod 0.20.0 writes them itself. Round 39: granted visions had no menu, because the Equip screen needs event flag 24, which the story sets at Mitra. Mod 0.21.0 turns on flags 21 and 24.
   - Round 39: the airship vanished after a visit to a town. Mod 0.21.0 sets the save's `IsAlreadySpawnAirship` for the `air` arrival. The `dock` and `event` arrivals do not set it, as they are no longer the default.
   - Fast travel needs event flag 34, which is off on this start. Decide with the continent locks: fast travel could cross a lock.
   - A cleared `ap_state.txt` starts with the switch off, which sends a new game to the Earth Shrine (round 38), so the seed should decide.
   - Locks: round 35 showed `lock` + `refresh` (the box's collision) works on Mysidia without landing. Round 36: the Pharm story box is not buried (its top is at z 371, the ground beside it at 34 to 201); it covers one spot. A spawned box blocks landing on Pharm at once, so continent locks can be our own boxes. Over a box the airship's shadow is gone. Round 37: the channel changes did not obviously bring it back. The airship has a list of actors the shadow's trace ignores (`m_ShadowDecalSphareTraceActorsToIgnore`), and round 38 tested adding our boxes to it (`ffrap_noland shadow`). **It works: the shadow is red over the box, landing is blocked, and removing the box gives the black shadow and landing back at once.** The game lists all 111 of its own boxes the same way. Round 39: the box and its listing last through boarding. Round 40 finds out whether the box lasts through a map change, which decides what the real continent locks must redo.
6. Enemy scaling integration: package tested curves into apworld options applied via `follow`.
7. Gates: continent locks using landing exclusion zones and choke-point blockers for overland crossings.
8. Goal and logic rules: define regions, events, and completion conditions in apworld.
