# Bosses: design draft

How boss fights come back into an open world seed, and how they open the Crystal Tower.

**Asked for (round 59, 2026-11-11):** bosses back in the game. Each boss gives an item reward (a "Crystal Fragment" or similar). The fragments are an objective: for example, 10 of them open the tower.

Facts here come from the game data dump (`dump/tables`, `dump/maps`, `data/game/`) unless a round is named. Related: [IDEAS.md](../IDEAS.md) ideas 24 (the tower's objectives) and 25 (boss fights, the `ffrap_bossfight` test), and [open_world.md](open_world.md).

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

### Tier 1: work now, with their own flag (25 fights)

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

The 15 cave masters also turn on flags 1231 and 1232 (shared). The 12 magic pots (flags 914 to 925) work the same way, but they are item puzzles, not bosses.

Left out: the Antlion (world map, Grandshelt, level 20). Its win turns on flag 113 only when flag 10 is on. With flag 10 off the win row sets nothing, so the fight would come back each time.

What a win gives in the game: a cave master gives Magicite (a Shard, a Magicite or a Cryst, by level). Sephiroth gives his vision (13113). The others give nothing. Archaeoaevis's win row also writes story 6123.

Round 59: the user saw the cave masters and their rewards work on the open world start.

Not yet seen in game: whether each cave's entrance is open at story 8000, and whether the Sanctissimus fights and Dragon's Maw can be reached.

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
| Arena, 20 fights up to Shinryu (95) and Omega (99) | the Colosseum's ranks | the rank's proof item (29000 to 29003) |

Siren and Leviathan are story fights (tier 3). Their espers are Archipelago items today.

### Tier 3: story bosses, gone at 8000 (about 30 fights)

Belmodar, The Hunger, Siren, Mom Bomb, Guardian, Epimetheus, Adrastea, Aether (two), Wave Lopros, Water Dragon, Leviathan, Alluvion (two), Ignis (four), the Emperor of Zoldaad, Evan, Lazarov, Slagworm, Byblos, Malboro, Archwitch Fina, Tellus (three), Liquid Flame, Iron Giant, Lux, Elfdrit, Lasswell (two), Gelidus, Umbra (two), Dante, Behemoth.

What they carry:
- The trigger tests one story value, for example Belmodar's `{progress:0}==1040`.
- The fight row is a story scene, and the win row is another. Both move the story counter. Neither can run in an open world.
- 33 groups have a scripted event inside the battle (`battleEventId`), such as tutorial text or a forced loss.
- Some have no trigger of their own. They start from the row before them (Adrastea after the train scene, Leviathan, Lazarov).

Three triggers showed no condition in the off-line pass: The Hunger (Kolobos Ruins), the Emperor (Zoldaad Castle) and Sol. Sol is the tower's own. The other two need a look in game.

## 3. Bringing the story bosses back

**What is proven (round 49 to 52, `ffrap_bossfight`):**
- A fight row pointed at any battle group starts that boss on its own stage (Siren from the sword pedestal).
- A chest with `IsTrap` starts a boss in any map that has battles.
- A win row must be a Sequence row with a real sequence. `Gim_EV_Majipot_Delete_02` works and is short.
- A flag on the win row is a working check (flag 1440).

**Suggestion: put each boss back on its own dead trigger.** On the boss's map, the mod finds the story trigger and writes:
1. The trigger's condition: our own flag for that boss, off.
2. The trigger's event: one fight row of ours (a borrowed row with no story scene), with `encountGroupId` set to the boss for this map.
3. The group: `battleEventId` cleared, `battleFinishEventId` set to the short win row.
4. After the win, the mod sees flag 1440, turns it off, turns on the boss's own flag and sends the check.

Flags 1430 to 1449 are free in the game's data. Thirty bosses need more room, so the range needs a new search of the dump.

**Round 59:** a live trigger's list can be read from Lua (`m_EventList[0].Condition` and `.EventId`, on Ramuh's trigger). The class has `SetEventList`, `SetEvent`, `GetEventList`, `PlayEvent` and `FindMatchEventByEventList`.

**Not proven:** writing the list on a live actor, and whether a transition trigger can run a fight row without its move to the boss room. Both need a probe behind a test command.

**The fallback is proven:** a trap chest near the boss room. The cost is that the chest's own check and the boss share one spot.

Scripted fights need care one by one. The first Umbra and the Ignis and Evan duels end by script or use a fixed party. Leave those out of the first pass.

## 4. The reward and the objective

**Decided (round 59, the user):**
- A story boss holds a locked Crystal Fragment and no shuffled item.
- A cave master holds a shuffled item. Its own Magicite goes into the pool.
- The tower's last climb needs `final_boss_fragments` fragments, beside `final_boss_characters` and `final_boss_visions`.
- Espers are open: Crystal Fragments, a fragment kind of their own, or left as they are (the esper is an item). The user will ask players.

**Built (world 0.17.0, mod 0.48.0):**
- `data/bosses.tsv` lists the fights: battle group, win flag, map, kind. The kind `story` gives a fragment (Liquid Thunder and the six Sanctissimus fights: 7). `cave` and `optional` (Sephiroth, Intangir, the Rogue Magitek Weapon) give a shuffled item.
- A location's key is `boss:<battle group>`. Its region is the continent of its map.
- The mod sends the check when the win flag is on. It empties the cave masters' and Sephiroth's reward lists, and takes story 6123 out of Archaeoaevis's win row.
- A Crystal Fragment is nothing in the game (item kind `token`). The client counts them and writes the count in the `cfg finalboss` line.

**Round 60: all of it works in game.** The cave masters, Liquid Thunder, the six Sanctissimus fights and both Dragon's Maw bosses start, end and send their checks. Sephiroth is open from the start but took no damage at party level 28, even with scaling at 1%: scaling does not write defence.

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
