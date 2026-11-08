# Open world: design draft

How an open world seed could work. The story is skipped, the world is open, and Archipelago items decide where you can go.

**Why now (round 30, 2026-11-06).** Players on the Archipelago Discord ask mostly for open world, and few want a story mode. So open world comes first, and story mode may never come. Open world also avoids story events that undo our items, such as the story swapping the two Finas.

**Round 31 (2026-11-07): decided.**
- **The start:** story 7090, then the Crystal Tower (map 3280), where an event moves the story to 8000. Then the Crystal Tower is open and the airship is there. You found this with FFRSLib's developer options. It replaces option A's 9000 (section 3).
- **The airship is free** from the start. No airship item.
- **Continents are locked by landing:** the airship cannot land on a continent until its item arrives. The game already does this for Mysidia before story 5020 (section 4).

**How to use this document:** the same way as [logic.md](logic.md). Each section has what the game data shows, a *Suggestion*, and **Your call** where the decision is yours. Facts come from the game data dump (`data/game/`, `dump/`) unless a round is named. The research scripts are short and can be run again; their results are summarised here.

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
| **9000** | **The ending sets this** (event `C08_822_05`, before the staff roll). Chapter 9 in `DT_ChapterData` is "Epilogue". This is the cleared state |
| over 10000 | Tested in 6 places only (airship deck variants). Probably unused |

**Story blockers mostly close for good.** Of the map blockers with a story condition, most test `<` or `==`: they stand only during one story scene. For example, 42 of the 47 `BP_MapGimmick_NoEntry_C` zones with a story condition are like that. At 9000 nearly all of them are gone. The few that open *later* (such as `{progress:0}>=4000` in the Earth Shrine) are open at 9000 too.

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

**Your call:** A, B, or something else? And where the player starts: Grandshelt, or a random continent?

## 4. Gates: how items decide where you go

| Gate | How | State |
|---|---|---|
| **The airship** | Free from the start (decided, round 31) | No item |
| **Continents** | No landing on a continent until its item arrives (idea 17), with the game's own no-landing boxes (below) | Round 32 probe: `ffrap_noland` |
| **Ships and the Chocobo** | The Chocobo is item 30002, and the game checks the item (round 5). Ship routes are story transitions | Chocobo: works. Ships: unknown at 9000 |
| **Dungeons and choke points** | Our own blockers (idea 16), which work everywhere (mod 0.11.3). Or the game's own exits, with their condition rewritten | Blockers: work. Rewriting a live exit's condition: not tried |
| **Key items the game checks** | The Throne Room Key door; the Cabin Key exit; the radar parts for world-map treasures | Already in the pool (world 0.3.0) |

**No-landing boxes (found in the game data, round 32).**
- The world map has 111 `BP_MapNonLandingArea_C` actors. Each one is a box (a `CPP_MapAirShipCanNeverLandingBox` component, with a position, a half-size and a yaw) and an `m_Condition` string. While the condition holds, or when it is empty, the airship cannot land in the box.
- There are 111 boxes. Most are small (under 700 units across) and have no condition. They keep the airship off town entrances and the like.
- 12 have a condition. 7 are side-quest steps (`{progress:24}==10` and similar), and 2 test flag 95 (`!{flag:95}`, in Mysidia). 3 are story locks: `{progress:0}<5020` over Mysidia, `{progress:0}<6000` on Gronoa's landing spot (which also runs an event), and `{progress:0}<7020` in Pharm.
- **The game locks a whole continent this way:** before story 5020, one box of half-size 2400 x 6000 x 700 at (-18053, -8493), condition `{progress:0}<5020`, covers Mysidia.
- So a continent lock can be one or more big boxes per continent, with a condition the mod controls. To find out (round 32): whether a box we spawn or move works, and whether the game reads a changed condition at once or only when the map loads.
- **Round 32 results:** `list` found the 111 boxes. A box spawned at the airship's height (z 1500, 3000 up and down) lifted the airship over it and broke the camera, and the airship could still land on it. So the box's collision counts as ground for the airship, and a box must sit on the ground, as the game's own do (the Mysidia box: centre height 393, 700 up and down). The Blueprint has no script: the C++ class `CPP_MapNonLandingArea` reads the box and the condition.
- **Round 33 probes (mod 0.15.0):** `lock mysidia` (the game's own box, with a condition that always holds) tests whether a changed condition works at once. `spawn` now puts a new box at the ground height. `here` lists the boxes under the player, and `show` tries to draw them.
- **Where the continents are** (from the landing points, whose ids start with the island: 1xxx Grandshelt, 2xxx Lanzelt, and so on; x and y in game units):

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

  These are rough. Kolobos and Lanzelt overlap, so they need more than one box each, or a shared one. `ffrap_noland list` and a few positions from the game will make them exact.
- **Other ways across:** walking, the Chocobo, ships and caves can still cross between some continents. Those crossings need our blockers (idea 16) or their exits' conditions rewritten.

*Earlier suggestion for a first set:* "Airship" plus one pass per continent group: Grandshelt, Lanzelt and Kolobos as the starting group (the map data lists them as neighbouring islands), then Dirnado, Olderion, Zoldaad, Mysidia, Gronoa, Pharm and the Crystal Tower. That is 8 progression items with clear meaning, and a big first sphere.

**Your call:** which gates, and how many.

## 5. Enemy levels

**What the data shows:**
- **Enemy stats are fixed per unit** in `DT_UnitParameter`: a level, HP, attack and so on. No enemy has a level curve (`LevelParamId` -1 for all 367 enemies). So scaling an enemy means rewriting its row, the way chest blanking rewrites chest rows.
- **Nearly every enemy belongs to one region.** Only 9 of the 261 units in the encounter tables appear in two regions, so a region's enemies can be scaled on their own.
- **Levels by region** (random encounters):

| Region | Levels | Region | Levels |
|---|---|---|---|
| Grandshelt | 1 to 6 | Zoldaad | 21 to 30 |
| Kolobos | 5 to 9 | Mysidia | 31 to 38 |
| Lanzelt | 6 to 16 | Gronoa | 30 to 42 |
| Dirnado | 11 to 18 | Pharm | 40 to 52 |
| Olderion | 18 to 26 | Crystal Tower | 44 to 54 |
| | | Dragon's Maw (optional) | 45 to 70 |

  Bosses run from level 4 (Belmodar) to 99 (Omega).
- **Stats follow level closely.** A fit over the 256 normal enemies, log(stat) against level:

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

  MP does not follow level (r² 0.09), so it stays as it is.
- **The damage formula reads levels too.** `DT_UnitParameterCalc` has `sameLevelDamageCalcMagnification` and `deffenceIgnoreDamageCalcLevelRate`. So the level field must change along with the stats.
- **The party's level** can be read with `CPP_BFL_Unit:GetPlayableUnitLevel` (FFRSLib uses it).

**The design.** A scaled enemy keeps its own stats and moves them by the growth rates: stat × growth^(new level − own level). EXP and gil move the same way, so levelling up still pays. Modes:
- **`enemy_scaling: clamp`, `enemy_level_range: 5`** (your "+/- 5" idea): each enemy keeps its own level, but it is pulled into the party's average level ± 5. A level 40 Gronoa enemy meets a level 10 party at level 15. Grandshelt stays easy, Gronoa stays the harder place, and nothing is out of reach.
- **Range 0:** every enemy is at the party's level.
- **`off`:** the shipped levels.
- **Bosses:** the same rule, with their own switch, because a boss pulled to the party's level may be too easy or too hard.
- **When:** the rows are rewritten on the field, never in a battle, whenever the party's average level changes.

**The other way: scale by sphere.** The apworld gives each region a level from the sphere where logic expects you to reach it, and the mod writes those levels once. That is fixed and fair, but it depends on the logic being good, and it does not help a player who goes off the expected route. *Suggestion:* the party clamp first; sphere scaling later as an option, if players want it.

**Round 31 results.** Battles read the rewritten rows at once. But the enemies were too hard at both ends: a level 1 party against Mysidia's enemies at levels 1 to 3, and a level 52 party against Grandshelt's enemies at levels 51 to 53.

**Why (round 32, off-line):**
- **The growth rate was wrong at the ends.** Real enemies do not grow by a fixed rate per level. For example, attack grows about x5 from level 1 to 30, where a rate of 1.046 per level gives x3.5. So a level 30 enemy pulled to level 2 kept too much attack.
- **The new curve:** log(stat) = a + b log(level) + c level, a fit over the same enemies (r² 0.88 for attack, 0.70 for HP). Only the ratio between two levels is used, so a drops out. Levels above 70, the last in the data, count as 70.

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

- **The party is normally far ahead of the enemies.** Party members' stats grow by a fixed amount per level (Rain: about +70 HP and +5 attack). Required EXP is a running total (level 50 needs 98006), and late regions give a lot of it: a Pharm battle gives about 10200. Even if EXP is shared four ways, a party reaches about level 31 to 38 in Olderion (enemies 23), 37 to 45 in Zoldaad (27), and 40 or more in Mysidia (35). So in the shipped game the enemies are 10 or more levels below the party from mid-game on, and enemies at the party's own level are much harder than normal.
- **Not the cause:** enemy skills and group sizes. The median skill power is 12 to 24 in every region, and groups average 2 to 3 enemies everywhere.
- **Gear** is not in the party's base stats, and it adds a lot later on. Shipped level 50 enemies have about twice the base attack of a level 50 party member.

**Mod 0.14.0** has the new curve and three knobs to try in game:
- `at`: the centre of the band, as a share of the party's level. `at 80` with a level 50 party puts enemies at about 40.
- `hp` and `power`: enemy HP, and enemy Attack and Intelligence, as percentages.
- `follow`: the band moves when the party's level changes, on the field only.

**Round 32 results.**
- `party 2 at 80` "feels much better" with a level 3 party. Mod 0.15.0 makes range 2 and `at 80` the defaults.
- `follow` works: the band moved when the party levelled up, once back on the field.
- **Physical hits are much stronger than spells:** a Hydra's Crush hit for almost 200, its Thundara for about 40. Crush is weaker on paper (power 18, one hit, against 22 times two hits), but the stats are not even. The curve keeps an enemy's own balance, and at low levels attack falls much less than intelligence (attack's b is 0.32, intelligence's 0.56). The Hydra (level 48: attack 505, intelligence 330) pulled to level 4 has attack 62 and intelligence 19.
- Shipped low-level enemies are like that too: about 2.3 times more attack than intelligence at levels 1 to 10. But they only have plain attacks (power 12), and late enemies keep their strong skills when they are pulled down. If damage grows faster than attack (attack²/defence, as in many FF games), the gap grows.
- **Party members join at their own levels** (Lid 11, Nichol 19), and the band follows the party's average. With a level 3 Rain, Lid and Nichol joining moved the band from 2 to 7.

**Mod 0.15.0:** `attack` and `magic` knobs apart (`power` still sets both), and `scale.txt` with each enemy's new stats after every rescale.

**Your call (after round 33):** the defaults for `attack` and `magic`; whether the party level is the average or the highest member; whether new members join at the party's level; and whether bosses scale by default.

## 6. Locations in the cleared world

| Kind | Count | At 9000 |
|---|---|---|
| Chests | 202 | All there: the save keeps which are open, not the story |
| Shinies | 92 (world map) | There; a few show only under a story condition |
| NPC gifts and side quests | about 200 talk events (idea 21) | Chapter side quests with `==` story conditions are gone. Free-talk gifts and later quests should be there. Needs a survey of their conditions |
| Optional bosses | Espers, strong enemies (15), Dragon's Maw, superbosses (Omega, Shinryu) | To find out: which still start |
| Vision Sanctums and vision quests | most of the 26 visions | To find out |
| Story bosses | | Probably gone: their events test story values below 9000 |

## 7. The goal

The ending cannot be the goal, because the save starts past it. Some candidates:
- **Tablet Shards:** turn in N of the 99 (idea 1).
- **Espers:** gather the nine. Bahamut's trial already asks for the other eight, but it is a story event, so it needs checking at 9000.
- **A boss:** Omega (level 99) or Shinryu (95), if they can be fought at 9000.
- **"Crystals":** N Archipelago-only items spread through the multiworld, then a final boss.

**Your call.**

## 8. What the story used to give, now items

The story hands out the party, the first visions, the airship and the main key items. In open world each of these must be an Archipelago item, or be in the starting state:
- **Party:** 8 members (world 0.3.1 has 6 in the pool, plus Rain and Lasswell at the start). A random starting party (idea 19) fits open world well, since the story no longer swaps anyone.
- **Visions:** all 26 are in the pool already.
- **The airship:** a new item (section 4).
- **Key items:** in the pool already (43).

## 9. Order of work

1. **Round 31 probes:** `ffrap_scale`, `ffrap_airship` and `ffrap_story 9000`. Done: scaling works but was too hard.
2. **Round 32 probes:** the new scaling curve and knobs, and the no-landing boxes (`ffrap_noland`). Done: `at 80` is much better; physical hits too strong; a box must sit on the ground.
3. **Round 33 probes:** `attack` and `magic` knobs, and `ffrap_noland lock`, `spawn` at the ground height, `here` and `show`.
4. **The skip to the open world:** story 7090 and the Crystal Tower's event, done by the mod for a new Archipelago game.
5. **Enemy scaling:** the defaults from rounds 32 and 33, as options in the apworld, applied by the mod with `follow`.
6. **Gates:** continent locks with no-landing boxes, plus blockers for the crossings that do not need the airship.
7. **The goal,** and regions and rules in the apworld (logic.md section 9).
