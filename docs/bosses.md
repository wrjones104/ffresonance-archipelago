# Bosses: design draft

How boss fights come back into an open world seed, and how they open the Crystal Tower.

**Asked for (round 59, 2026-11-11):** bosses back in the game. Each boss gives an item reward (a "Crystal Fragment" or similar). The fragments are an objective: for example, 10 of them open the tower.

Facts here come from the game data dump (`dump/tables`, `dump/maps`, `data/game/`) unless a round is named. Related: [IDEAS.md](../IDEAS.md) ideas 24 (the tower's objectives), 25 (boss fights, the `ffrap_bossfight` test), and 29 (boss logic), [open_world.md](open_world.md), and [boss_logic.md](boss_logic.md) (capability macros, 8-element mitigation, per-boss rules, and unshuffled Vision placement).

## 1. How the game starts a boss fight

- A talk row with `encountGroupId` starts a battle group from `DT_BattleGroup`. 210 rows do this, for 173 groups that exist.
- A map actor runs the row. The actor holds a list of `Condition` and `EventId` pairs: `m_EventSettings` in the level file, `m_EventList` on the live actor (round 59). Four kinds of actor start fights:

| Actor | Used for |
|---|---|
| `BP_MapUnit_NPC_C` | An enemy you can see and touch: the cave masters |
| `CPP_MapGimmick_EventTrigger`, `BP_MapGimmick_EventTrigger_C` | A zone you walk into: Liquid Thunder, the Sanctissimus fights |
| `BP_MapGimmick_InteractEventTrigger_C` | A spot you press a button at: the Twelve Arms pedestals |
| `BP_MapTransitionTrigger_C` | A door into the boss room: most story bosses |

- The group's `battleFinishEventId` names the row to run after a win. That row turns on a flag or moves a counter. The actor's condition tests the same flag, so the boss is gone after a win.
- **A win can be seen with no change to the game:** watch the flag the win row sets.

## 2. Which fights still work at story 8000

An open world save starts at story 8000. A trigger that tests `{progress:0}==N` for an earlier N never fires again. A trigger that tests only its own flag still works. The user saw this in round 59: Liquid Thunder stands on Mt. Thunderclap and starts its fight.

### Tier 1: work now, with their own flag (27 fights)

| Fight | Level | Map | Win flag |
|---|---|---|---|
| Marauder | 15 | 10051 Marauder Cave (Lanzelt) | 146 |
| Shoggoth | 25 | 10052 Shoggoth Cave (Dirnado) | 214 |
| Rukh | 26 | 10053 Rukh Cave (Olderion) | 319 |
| Mindflayer | 28 | 10054 Mindflayer Cave (Olderion) | 320 |
| Gogmagog | 34 | 10055 Gogmagog Cave (Zoldaad) | 433 |
| Pyroviper | 37 | 10056 Pyroviper Cave (Zoldaad) | 434 |
| Salome | 39 | 10057 Salome Cave (Mysidia) | 548 |
| Jotunn | 42 | 10058 Jotunn Cave (Mysidia) | 549 |
| Malboro Varietas | 45 | 10059 Malboro Varietas Cave (Olderion) | 550 |
| Tartarosaurus | 50 | 10061 Tartarosaurus Cave (Pharm) | 551 |
| Catacumba | 54 | 10062 Catacumba Cave (Gronoa) | 552 |
| Necromonarch | 55 | 10063 Necromonarch Cave (Gronoa) | 614 |
| Humbaba | 55 | 10064 Humbaba Cave (Gronoa) | 615 |
| Titanoraidos | 60 | 10065 Titanoraidos Cave (Pharm) | 700 |
| Malboro Menace | 60 | 10066 Malboro Menace Cave (Pharm) | 701 |
| Liquid Thunder | 13 | 3050 Mt. Thunderclap | 215 |
| Sephiroth | 45 | 10218 Whirlpool Hollow | 1018 |
| Intangir | 52 | 3010 Dragon's Maw | 928 |
| Rogue Magitek Weapon | 63 | 3010 Dragon's Maw | 929 |
| Archaeoaevis | 40 | 3250 Sanctissimus Shrine | 608 |
| Dad Bomb | 40 | 3250 Sanctissimus Shrine | 609 |
| Test Rider | 40 | 3250 Sanctissimus Shrine | 610 |
| Yakhanati | 40 | 3250 Sanctissimus Shrine | 611 |
| Arch Gargoyle x2 | 40 | 3250 Sanctissimus Shrine | 612 |
| Dragon | 42 | 3250 Sanctissimus Shrine | 613 |
| Liquid Flame | 32 | 3180 Nameless Ruins | 526 |
| Iron Giant | 32 | 3180 Nameless Ruins | 527 |

The 15 cave masters also turn on flags 1231 and 1232 (shared). The 12 magic pots (flags 914 to 925) work the same way, but they are item puzzles, not bosses.

Left out: the Antlion (world map, Grandshelt, level 20). Its win turns on flag 113 only when flag 10 is on. With flag 10 off the win row sets nothing, so the fight would come back each time. Round 69: the Antlion is a location from world 0.21.1 ("Lanzelt Desert: Antlion", kind `optional`, area Lanzelt), and the mod makes every win take the branch that sets flag 113. Round 67: the Antlion's sandpit is in Lanzelt, at (10814, 13272), not Grandshelt. It is there at story 8000. The Chocobo crosses the sandpit with no fight (`!{ride}` in its trigger), so the Antlion is a gate for a start without the airship (`open_world.md`, section 4).

What a win gives in the game: a cave master gives Magicite (a Shard, a Magicite or a Cryst, by level). Sephiroth gives his vision (13113). The others give nothing. Archaeoaevis's win row writes story 6123, and the two Nameless Ruins bosses write story 5080 and 5110; the mod clears those story writes.

Round 59: the user saw the cave masters and their rewards work on the open world start.

Seen in game: each cave's entrance is open at story 8000, and the Sanctissimus fights and Dragon's Maw can be reached.

### Tier 2: behind a side quest (about 60 fights)

These test a side-quest counter (`{progress:N}`, N not 0) or an item. They may work at 8000, but each quest has steps before the fight.

| Fights | Tested by | Win seen by |
|---|---|---|
| Ramuh (Mt. Thunderclap) | `progress:12` at 0 or 10, flag 12 off | flag 92 |
| Titan (world map, Lanzelt) | item 10499, `progress:13` | flag 96 |
| Ifrit | `progress:18` | flag 94 |
| Shiva (world map, Mysidia) | `progress:20` at 20 | flag 95 |
| Odin's Shadow | `progress:17` | `progress:17` at 30 |
| Bahamut | `progress:46` at 10 | flag 98 |
| Gilgamesh, three fights | `progress:54`. The first is a trap chest in Siren's Tower | `progress:54` |
| Ultima Weapon | a chapter 9 side quest | its win row |
| Typhon, Adamandelion, Sahagin, Phantom Train, Ashasaur, Blood Dragon | each character's quest counter | the counter |
| Twelve Arms, 12 at level 50 and 12 at level 75 | the weapon in the bag, at a pedestal in the Chamber of Arms (3290) | the Victory row's flag |
| Arena, 20 fights up to Shinryu (95) and Omega (99). From mod 0.52.2 (round 63) the Brawler, Gladiator and Champion fights (groups 9705 to 9721) are scaled as bosses; the Fledgling fights use field enemies and are not | the Colosseum's ranks | the rank's proof item (29000 to 29003) |

Siren and Leviathan are story fights (tier 3). Both will give Crystal Fragments: the player starts with Siren as a summon, and the Leviathan summon comes from a side quest.

### Tier 3: story bosses, gone at 8000 (about 28 fights)

Belmodar, The Hunger, Siren, Mom Bomb, Guardian, Epimetheus, Adrastea, Aether (two), Wave Lopros, Water Dragon, Leviathan, Alluvion (two), Ignis (four), the Emperor of Zoldaad, Evan, Lazarov, Slagworm, Byblos, Malboro, Archwitch Fina, Tellus (three), Lux, Elfdrit, Lasswell (two), Gelidus, Umbra (two), Dante, Behemoth.

What they carry:
- The trigger tests one story value, for example Belmodar's `{progress:0}==1040` (condition 1001).
- The fight row is a story scene, and the win row is another. Both move the story counter. Neither can run in an open world.
- 33 groups have a scripted event inside the battle (`battleEventId`), such as tutorial text or a forced loss.
- Some have no trigger of their own. They start from the row before them (Adrastea after the train scene, Leviathan, Lazarov).

`BP_MapTransitionTrigger_C` stores its condition and event list in `mTransitionDataList` (each entry has `pointId`, `FlagCondition`, `isEventOnly` and `EventList`). For The Hunger on map 3040 (Kolobos Ruins), `pointId = 5000` runs `C01_030_01` when `FlagCondition = {progress:0}==1230`.

## 3. Bringing the story bosses back

**What is proven (round 49 to 52, `ffrap_bossfight`):**
- A fight row pointed at any battle group starts that boss on its own stage (Siren from the sword pedestal).
- A chest with `IsTrap` starts a boss in any map that has battles.
- A win row must be a Sequence row with a real sequence. `Gim_EV_Majipot_Delete_02` works and is short.
- A flag on the win row is a working check (flag 1440).

**Built for the first three tier 3 bosses (world 0.19.0, mod 0.50.0):**
- Pre-fight talk rows (`C01_008_02`, `C01_030_01`, `C02_208_01`) have their story writes and flag writes cleared and jump to the unused encounter row `SubEv_C02_SymbolEnemy_Encount`, while `G.SyncStoryBossTrigger` sets `SubEv_C02_SymbolEnemy_Encount.encountGroupId` to the current map's boss group and points that group's win event to `Gim_EV_Majipot_Delete_02`.
- Belmodar (group 9004, flag 1240, map 3000 Earth Shrine): `G.SyncStoryBossTrigger` rewrites `BP_MapGimmick_EventTrigger_C` (`m_EventList[1]` to `!{flag:1240}` / `SubEv_C02_SymbolEnemy_Encount`) and shows `BP_MapUnit_NPC_C` (unit 10003) until flag 1240 is set.
- The Hunger (group 9012, flag 1241, map 3040 Kolobos Ruins): `G.SyncStoryBossTrigger` rewrites `BP_MapTransitionTrigger_C` (`pointId = 5000`) to `FlagCondition = !{flag:1241}`, `isEventOnly = true`, and `EventList[1].EventId = SubEv_C02_SymbolEnemy_Encount`.
- Mom Bomb (group 9014, flag 1242, map 2050 Dwarven Forge): `G.SyncStoryBossTrigger` rewrites `BP_MapUnit_NPC_C` (unit 10037) to `m_VisiblFlagCondition = !{flag:1242}` and `m_EventSettings.EventList[1]` to `SubEv_C02_SymbolEnemy_Encount`, and shows the pawn with collision enabled until flag 1242 is set.
- While on one of those maps, `Gim_EV_Majipot_Delete_02.OnFlagList[1]` is set to that map's boss flag (`1240` to `1242`), and restored to `915` on other maps so the magic pot puzzles keep their own flag.
- `ffrap_bossfight trigger` runs `G.SyncStoryBossTrigger` with step-by-step pre-write logging.

**Round 62: The Hunger looped.** The door started the fight again as the party came back from it, before the win row ran, so flag 1241 never came on. The Hunger also ships with 0 EXP and in the Enemy category, so it was scaled as a plain enemy and gave nothing. Mod 0.51.0:
- Each fight's condition is `!{flag:N}&{flag:1441}`. The mod turns flag 1441 on after the field has been up for about 2 seconds on a story boss map, and off as soon as the field goes. Visibility conditions stay `!{flag:N}`.
- A unit in a boss location's battle group is scaled as a boss. While scaling is on, one with 0 EXP gets about 1350 EXP at level 14, moved along the EXP curve to its level.

Scripted fights need care one by one. The first Umbra and the Ignis and Evan duels end by script or use a fixed party. Leave those out of the first pass.

## 4. The reward and the objective

**Decided (round 59 and round 61, the user):**
- A story boss holds a locked Crystal Fragment and no shuffled item.
- A cave master holds a shuffled item. Its own Magicite goes into the pool.
- The tower's last climb needs `final_boss_fragments` fragments, beside `final_boss_characters` and `final_boss_visions`.
- Siren and Leviathan both hold Crystal Fragments as story bosses.

**Newly introduced idea:**
- Can every boss give give both a Crystal Fragment and a regular location check reward?

**Built (world 0.17.0 to 0.19.0, mod 0.48.0 to 0.50.0):**
- `data/bosses.tsv` lists 30 fights: battle group, win flag, map, kind. The kind `story` gives a fragment (12 fights: Liquid Thunder, the six Sanctissimus fights, Liquid Flame, Iron Giant, Belmodar, The Hunger and Mom Bomb). `cave` and `optional` (Sephiroth, Intangir, the Rogue Magitek Weapon) give a shuffled item.
- A location's key is `boss:<battle group>`. Its region is the continent of its map.
- The mod sends the check when the win flag is on. It empties the cave masters' and Sephiroth's reward lists, and takes story 6123 out of Archaeoaevis's win row.
- A Crystal Fragment is nothing in the game (item kind `token`). The client counts them and writes the count in the `cfg finalboss` line.

**Round 60: all of it works in game.** The cave masters, Liquid Thunder, the six Sanctissimus fights and both Dragon's Maw bosses start, end and send their checks. Sephiroth is open from the start but took no damage at party level 28, even with scaling at 1%: scaling does not write defence. Round 72 correction: the level curve does move Defence and Mind with level (`GROWTH_ORDER` in `game.lua`); only the strength percentages (HP, Attack, Intelligence) leave them alone. Sephiroth's Defence is 1.5x a normal enemy's of his level, so it does not explain the 0 damage either (`docs/boss_logic.md`, section 2).

**Changed after round 60 (world 0.18.0, mod 0.49.0):**
- A boss with a shuffled item keeps its reward pop-up. Its win row gives one Potion in place of its own reward, and the mod writes what the boss held into the pop-up, as for a chest. Not seen in game yet: whether that pop-up is the same dialog box as a chest's.
- `priority_bosses` (on by default) makes the cave masters and the two Dragon's Maw bosses priority locations. Sephiroth is left out until his fight can be won at a fair level. A boss in an excluded region stays excluded.

The two ways to count that were compared:

| | Wins counted by the mod | Crystal Fragment items |
|---|---|---|
| How | The mod counts boss flags on the save | Each boss location holds a locked "Crystal Fragment" item. The client counts fragments received, as it counts visions |
| Logic | An event item per boss | `state.has("Crystal Fragment", player, N)` |
| Seen in | Our notice at the tower | The Archipelago tracker and item feed, and the tower notice |
| Shuffled fragments | No | Possible later: put fragments in the pool, so other players find them |
| A boss's other reward | The location's shuffled item | Needs a second location per boss for a shuffled item |

A third way is fragments shuffled into the whole pool, with bosses as plain checks. Then bosses matter less: a player could reach the count without a fight.

Boss MRP is `ap` in the battle group, which the mod already scales. A large boss MRP makes bosses pay for growth (idea 25).

## 4a. The story boss survey (round 71, off-line)

Every battle group with a Boss-category unit (155), walked back from its fight row to the map actor that starts it: through talk rows, transition event lists, and earlier fights' win rows. For the story fights (groups 9000 to 9099) not yet in the mod:

| Group | Boss | Map | Starts from | Built in mod 0.55.0? |
|---|---|---|---|---|
| 9013 | Siren | 3030 Siren's Tower | door `m_EventList`, story 1230 | yes, flag 1243 |
| 9017 | Aether | 3070 Wind Shrine | door `m_EventList`, story 2130 | yes, flag 1244 |
| 9031 | Tellus | 3180 Nameless Ruins | door transition point 5000 | yes, flag 1245 |
| 9038 | Tellus | 3200 Tower of Mysidia | zone `m_EventList`, story 5290 (and an NPC) | yes, flag 1246 |
| 9039 | Lux | 3230 Rugged Mountain Path | zone `m_EventList`, story 6080 | yes, flag 1247 |
| 9040 | Elfdrit | 3240 Gronoa Shrine | native zone `m_EventList`, story 6110 | yes, flag 1248 |
| 9044 | Gelidus | 3250 Sanctissimus Shrine | automatic door `m_EventList2`, story 6160 | yes, flag 1249 |
| 9046 | Ignis | 3260 Mt. Reizan | zone `m_EventList`, story 7030 | yes, flag 1250 |
| 9048 | Tellus | 3270 and 3271 Wandering Lands | zone `m_EventList`, story 7060 and 7050 | yes, flag 1251 |
| 9051 | Behemoth | 3280 Crystal Tower | automatic door `m_EventList2`, story 8020 | yes, flag 1252 |
| 9001 | Umbra | 3020 | door, story 1110 | no: a scripted loss (win and loss run the same row) |
| 9024, 9025 | Ignis | 3130 | native zone, story 4140 | no: 9024 is a scripted loss, and 9025 follows it |
| 9016 | Adrastea | 3060 | after battle 9905, in a chain with flags 210 and 211 | not yet |
| 9021, 9023, 9028, 9029, 9045 | Leviathan, Ignis, Evan, Lazarov, Aether | | no actor found: they run inside longer story scenes | not yet |
| 9027 | Emperor of Zoldaad | 3160 | door with no condition | not yet: to look at |
| 9035 | Byblos | 3190 Arcane Library | a bookshelf (`InteractEventTrigger`), story 5108, hidden otherwise | not yet: the shelf is hidden |
| 9037 | Archwitch Fina | 10041, 10042 | native zone, story 5270 | no: event-only maps |
| 9042, 9043 | Lasswell | 3250 | door, story 6140 | not yet: a party member's duel |
| 9047 | Alluvion | 3260 | runs after a door into map 2180 | not yet: shares map 3260 with Ignis |
| 9049 | Umbra | 3272 Wandering Lands | after a door, which itself tests `{progress:0}<7090` | not yet: the door is off at 8000 |
| 9054 to 9056 | Chaotic Darkness, Sol | 3281 | the tower top's chain | no: the final battle |
| 9061 | Alluvion | 3110 Water Shrine | a door's `eventList2` and an after-arrival list | not yet |

**Built (mod 0.55.0, world 0.22.0):** the ten marked "yes". Each is a story boss with a locked Crystal Fragment (22 fragment bosses in all). The mod's new kind `list` rewrites the entry in the named event list (`m_EventList` or `m_EventList2`) on every actor of the named class, the entry that names the boss's own row, to `!{flag:N}&{flag:1441}` and the shared fight row. Nothing else on the actor changes, so a door is a door again after the win. The NPCs that showed some bosses before their fights stay hidden: the fight starts at the zone or door alone.

**Round 72:** Behemoth (9051) is out again: it sits right before the final boss, and in the story the Sworn Six weaken it first (the user's call). Elfdrit's zone and the Wandering Lands' two Tellus zones are made 4 times bigger while their boss stands (`scale` in `G.STORY_BOSSES`): the user had to hunt for Elfdrit's and never found Tellus's.

**Boss logic, first step (world 0.23.0).** Each boss has a `tier` in `data/bosses.tsv`, set from its highest unit level by the bands in `boss_logic.md`, section 2: A to 20, B 21 to 39, C 40 to 49, D 50 and up, and the optional superbosses D. The world's rule per tier (`locations.TIER_NEEDS`): A nothing more; B 3 party members and 2 continents unlocked; C 4 and 4; D 5 and 6, and the Airship when it is an item. Party counts above what the seed can give are lowered to it. Fina's Psyche takes Tellus's (9038) tier, and Sanctissimus Shrine's chests and shards take the highest of its first three fights' (Archaeoaevis, Dad Bomb, Test Rider, all C; round 72, the user). The capability rules (healing, elements, status) are the next step.

## 5. Order of work

1. **Tier 1 as checks.** Built in world 0.17.0 and mod 0.48.0 (section 4). Round 60 tests it.
2. **A probe for tier 3.** `ffrap_bossfight trigger`: rewrite the dead trigger on the current map, with a log line before each write. Try it on Belmodar (Earth Shrine, map 3000).
3. **Tier 3, a few at a time,** the plain fights first: Belmodar, Siren, Mom Bomb, Aether, Wave Lopros, Slagworm, Byblos, Lux, Elfdrit, Gelidus, Behemoth.
4. **Tier 2,** once the side-quest logic on the user's list is worked out. Espers first.

## 6. Sources outside the game data

Used to check names, levels and places. The game data wins where they differ.
- [allthings.how, bosses list](https://allthings.how/final-fantasy-resonance-bosses-list/): hand-written, 95 bosses with level, HP and weakness. Few locations.
- [KeenGamer, the 15 cave masters](https://www.keengamer.com/articles/guides/final-fantasy-resonance-all-15-cave-master-locations-weaknesses-and-rewards/): where each cave is, and that each can be fought once, at any time after the story. It puts Marauder's cave in Grandshelt's desert. `maps.tsv` has it under Lanzelt.
- [MeowDB, bosses](https://meowdb.com/db/final-fantasy-resonance/bosses): made from the game's files. Chapter tags and HP, no locations or triggers.
