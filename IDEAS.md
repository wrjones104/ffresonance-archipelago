# Ideas and to-investigate

A scratch pad for ideas that are not on the test plan yet. Each one lists what we already know, from logs, dumps and the installed mods, and what to find out.

The chapter-by-chapter progression (party, vehicles, gates, Visions, Espers) is in [docs/progression.md](docs/progression.md). The logic design built on it is in [docs/logic.md](docs/logic.md). Resolved and parked ideas (1–6, 13, 14, 17–19, 23, 24, 26, 27) are archived in [docs/ideas_archive.md](docs/ideas_archive.md).

## 7. Enemy randomization

**Idea:** shuffle which enemies appear in each encounter, and maybe the bosses.

**Known so far:**
- Battles start from a table entry: FFRRandomizer's probe hooks `CPP_MapManager:Encount`, whose battle entry carries `battleGroupId`, `battleEventId` and `isEvent` (idea 3). FFRRandomizer already tells boss and event fights apart in the battle tables.
- FFRBestiary maps enemies to areas from the game data (`data.entries`, `mapArea`), so the encounter and enemy tables are readable.

**To find out:**
- Which data tables hold the encounter groups (the enemies in each `battleGroupId`) and the enemy stats.
- How to keep it fair: shuffle within a level band, or scale stats to the area.
- Story and event battles: scripted fights (Iron Giant, bosses) may expect a certain enemy and break if swapped. Start with normal encounters only.
- Whether FFRRandomizer already does some of this, and whether we should build on it or stay out of its way (idea 10).

## 8. Stat, weakness and resistance randomization

**Idea:** randomize enemy stats, elemental weaknesses and resistances, and maybe the party's growth.

**Known so far:**
- The save keeps per-enemy scan data (`unitList[n].analyzedElments{element}`), so elements are keyed per unit in the game data.
- `CPP_BFL_SaveDataUnit` has `GetBaseParameter`, `AddBaseParameter` and `IsAnayzedElement` (from `ffrap_functions`).

**To find out:**
- Which table rows hold enemy stats and element tables, and whether a row change applies at once or needs a map change. Chest rows applied at once (rounds 3 and 4), so data-table patching is a good first guess.
- The Libra / scan display: it should show the randomized weaknesses, or players learn wrong ones.

## 9. Music randomization

**Idea:** shuffle the music for each map and battle.

**Known so far:**
- The game's map data carries the BGM for each map (FFRSLib's notes on `MAP_DATA`: camera id, encounter group, battle stage, BGM, spawn points).
- The save keeps sound settings (`SaveData_Sound_BGMData`, `SaveData_Sound_SaveData`).

**To find out:**
- The BGM ids or cue names in `MAP_DATA` and the battle tables, and whether changing one changes what plays.
- Whether music can be swapped by table rows only, or needs a hook on the play call.

## 10. Conflicts with other mods

**Idea:** know where this mod can clash with others, say so to the player, and avoid the clashes we can.

**Known so far:**
- **FFRRandomizer** patches the same chest table (`CDT_MapGimmickTreasureBox`) that chest blanking changes. Every test plan says to keep it disabled.
- **Round 33: FFRRandomizer was on during a test** (the first round on the user's laptop, where it was still enabled), and it explained the enemy levels that made no sense.
  - It writes its whole plan again every 3 seconds (`CHECK_INTERVAL_MS = 3000`, through `LoopAsync`). Its 1.0.1 plan had 8405 changes: chests, shops, visions, enemies and bosses.
  - Its enemy shuffle gives a swapped-in enemy the replaced enemy's level, stats, EXP, gil, drops and steals (`ENEMY_SPOT_FIELDS`). Steel Bat fought in place of Nanochu (level 47), so Steel Bat's row read level 47, HP 4800. Metal Gigantuar fought in place of Thunder Gigas (level 45), so it showed level 45.
  - 1.5 seconds after our rescale changed 357 rows, it logged `Applied 2147 field changes`: our rescale was gone.
  - From one second after the save was linked to the seed, its count went 9, 693, 9, 693... every 3 seconds. That fits our chest blanks and its item shuffle writing the same chest rows in turn.
  - How to tell: `[FFRRandomizer]` lines in `UE4SS.log`, and `Mods/FFRRandomizer/Status.txt` with `state=applied`.
- **FFRBestiary** reads the same save state (slots, timestamps, visited maps). Nothing has gone wrong running it with this mod: it is a neighbour, not a known conflict. Its notes mention a start-up crash once, in its own code.
- **FFRSLib** adds entries to the System Menu data asset and hooks its view model. A title-menu entry (idea 6) works the same way on a different asset, so both should be able to live together. Two mods writing the same list at once could still clash.
- Any mod that edits the save while we skip the prologue, or that grants items, can confuse the per-save item count.

**To find out:**
- **A start-up check:** done for FFRRandomizer in mod 0.15.2. If `Mods/FFRRandomizer/enabled.txt` exists, or `mods.txt` has `FFRRandomizer : 1`, the mod logs a warning at start and shows it once when the first save loads. Other known clashes can go in the same place.
- **Shared tables:** patch them through one place. Offer a small shared helper, or agree on an order with the other mod authors.
- **A compatibility list** in the README: tested together, works, or known problems.
- The other conflicts you have seen outside this project: which mods, and what happened.

## 11. Archipelago details on the save-slot cards

**Idea:** the Load and Save screens show, on each slot's card, that it is an Archipelago save: the server (host:port) and the slot name.

**Known so far:**
- The mod already knows which slots belong to the session (`slots` in `ap_state.txt`). It does not keep that for older sessions.
- The game's slot summaries are `MuchaGameSaveDataSummary` rows in `CPP_MuchaSaveDataManager.GameSaveDataSummaryMap`. The cards are probably drawn from them.

**What it needs:**
- **The client** writes the server address and the slot name into `ap_in.txt` (`server <host:port>`, `player <name>`), next to the `seed` line.
- **The mod** keeps a per-slot record that outlives the session: slot, seed, host:port, slot name. It is updated when a linked game saves, and cleared when another game saves over the slot.
- **The card itself:** round 17's `ffrap_layout` found it: `WBP_SaveData_Entry_C`, with `Text_ChapterName` and `Text_PlaceName` in a `VerticalBox` (`Vertical_Mid`), and `Text_PlayLevel` beside them in `Overlay_Content`. A line could go in `Vertical_Mid` under the place name, the way the feed's lines are added.

## 12. The client inside the game

**Idea:** no separate client window. The player types the server, slot name and password in the game and connects from there.

**What is realistic:**
- **UE4SS Lua has no sockets.** The mod can read and write files, start programs and call the game's functions, but cannot open a websocket. That is why the client is a Python program and the two talk through files.
- **Option A, a UE4SS C++ mod.** UE4SS also loads C++ mods (DLLs). APCpp, the C++ Archipelago client library that several PC ports use, could be built into one and called from Lua. That is a real in-game client. The cost: a C++ build against the matching UE4SS version, websocket and TLS libraries, and more to fix when the game or UE4SS updates.
- **Option B, start the existing client from the game.** An in-game connect screen writes host, slot and password to a file. The mod then starts the Archipelago client without its window, using `os.execute` or the launcher with the component's arguments. The player never touches the client, but the Archipelago install is still needed. Generating seeds needs it anyway.
- **Recommendation:** B first, because it reuses the tested client and the file bridge. Then A, if the separate install is still a sticking point. With A the connect screen from B stays, and only what is behind it changes.

**To find out:**
- For B: whether the launcher can start our client with no window and connection arguments, and how to find the install folder (a setting in the mod's config).
- For A: whether APCpp builds against UE4SS's C++ template, and how big a release that makes.

## 15. A chest pop-up of our own, and no 1 gil

**Idea (2026-11-05):** today the mod rewrites the game's own pop-up a moment after it shows, and the chest still gives 1 gil. Better: the chest gives nothing of its own, and the player sees an Archipelago pop-up from the start.

**Why it looks this way now:** chest blanking gives 1 gil because that is the shape of the game's own gil chests (`ItemId -1, Money N`). An empty chest (`Money 0`) was never tried. The pop-up is the game's, so it shows the game's reward until the mod changes it.

**Ways to get there, cheapest first:**
1. **Empty chests (one in-game test).** Blank a row to `ItemId -1, Money 0` and open that chest. If it opens with no pop-up, the mod can show its own: a line in the item feed, or a pop-up drawn the way the feed is. Then the 1 gil is gone too.

   It might instead show "obtained 0", refuse to open, or not be marked open in the save. In those cases this way is out.
2. **Change the text before it is drawn.** Hook the call that sets the pop-up's message (`RichTextBlock:SetText`, if the dialog calls it through a UFunction, the way `ExecuteEntry` is called on the title menu) and write the Archipelago text in the same frame. The gil line is collapsed in the same moment. The player never sees the game's version, but the 1 gil stays. This needs a guard so the hook does not catch the mod's own `SetText`.
3. **An "Archipelago item" in the game's item table.** Add a row to the item data table at start-up (FFRSLib adds rows to its menu tables the same way), with the logo as its icon. Every Archipelago chest then holds that item, and its name is set per chest just before the chest is opened. Then the pop-up shows it natively, which is how many Archipelago ports do it. This is the biggest piece of work:
   - the item's text and icon,
   - the item landing in the bag (it would need removing),
   - knowing which chest is about to be opened, not just opened.

**Verdict:** worth one cheap test (way 1), when there is time. If chests can be empty, the rest follows from what the feed already does. If not, way 2 is a small, safe polish, and way 3 waits until long after progression logic.

## 16. Map blockers and custom forced gates

**Idea:** Introduce "blocking" elements on the world map or in town/dungeon maps (e.g. new forced gates or barriers on a bridge or choke point until specific items, characters, or flags are collected) to control routing and enforce progression logic.

**Known so far:**
- Story gates in the game read `{progress: N}` and `{flag: N}` conditions (e.g. in `DT_MainScenario` and `VisibleCondition` for field gimmicks/shinies).
- Towns, dungeons, and the world map contain collision barriers, door gimmicks (`BP_MapGimmick_*`), and NPC actors with attached collision and interaction scripts.
- The mod and FFRSLib can read and manipulate flags, items, roster join state, and story state at runtime.

**Probe results (2026-11-06, mod 0.11.3, `ffrap_gate`):**
- **`BP_MapGimmick_*` blockers work everywhere.** Spawning cooked gimmick Blueprints with `world:SpawnActor` (loaded via `KismetSystemLibrary:LoadAsset_Blocking`) worked with full collision in towns, dungeons, and on the overworld (`map 1000`):
  - `BP_MapGimmick_BlockingBox` (invisible collision box),
  - `BP_MapGimmick_BlockingBase_Child_MagicPot` (visible sparkling Magic Pot),
  - `BP_MapGimmick_BlockingBase_Rock` (rock barrier),
  - `BP_MapGimmick_BlockObject_Gate` (gate barrier),
  - `BP_MapGimmick_BlockingBase_Wld01Gra_01` (overworld barrier).
- **Scaling works.** `SetActorScale3D` scales both the visual mesh and its collision cleanly, so a single blocker can span a wide world-map bridge or choke point.
- **Player pawn naming is inverted.** In the log, town and dungeon maps use `BP_MapUnit_Player_C` (`scale 1.00`), while the overworld (`map 1000`) uses `BP_MapUnit_Player_Field_C` (`scale 1.00`).
- **Raw NPC pawns do not work (and are not needed).** Spawning `BP_MapUnit_NPC` on the overworld placed an actor that destroyed itself on the next tick (~0.11 s later), showing nothing. Spawning `BP_MapUnit_NPC_Field` in a town (`map 2000`) crashed the game inside `SpawnActor`. `CPP_MapUnit_NPC` expects `CPP_MapManager` and `DT_MapUnitPlacementAsset` setup; `BP_MapGimmick_*` actors have no such dependency and cover all blocker needs.
- **Live conditional unlocking works.** Toggling `SetActorHiddenInGame` and `SetActorEnableCollision` hides and disables a blocker on the spot and restores it cleanly when locked again. Polling item counts (`FindInventory`) on the 500 ms tick showed `"Gate locked: need ..."` in the HUD feed on approach and removed the gate as soon as the 3rd copy was granted. Spawned actors are not written to the save and clear themselves on map change.
- **Custom key items work in `DT_ValuableItemData`, except for the display name.** Adding row `FFRAP_Key_29901` (`ID = 29901`, cloned from row `20008` Tunnel Key) via `AddRow` grew `DT_ValuableItemData` from 37 to 38 rows. `AddInventory(29901, n)` and `FindInventory(29901)` tracked the count (`0 -> 1 -> 3`) and the new item appeared live in the Valuables menu without a restart. However, the menu displayed `"Tunnel Key"` even though `r.nameSg` read back `"Bridge Crest"` in Lua, meaning the UI reads another property or localization key copied from template row `20008`.
- **Bypass behaviour.** Because gates are spawned by the mod at runtime, disabling UE4SS removes the physical barrier. Archipelago's server logic still withholds downstream progression items, and if stricter anti-bypass is ever needed the mod can check region coordinates on load or gate transitions directly.

**Still to find out:**
- **Exact item text fields:** `tools/dump_game` completed the game data dump, generating `data/game/items.tsv` across all 6 item tables. Still to check: which field controls the on-screen name of a dynamically added custom row in `DT_ValuableItemData`.
- **Save safety with custom item IDs:** check what happens if a save holding item `29901` is loaded with the mod disabled (or keep custom gate tokens in Archipelago's bridge state instead of `SaveDataInventory` if the vanilla menu dislikes unknown IDs).
- **Gate catalog:** scout exact `(mapId, X, Y, Z, Yaw, Scale)` coordinates, gimmick visuals, and unlock rules for actual world-map bridges and dungeon doors (`ffrap_gate` can scout these in game).

**From the game data dump (2026-11-06).** The maps already hold many blockers of their own. `data/game/gimmicks.tsv` lists them with their map, position and condition:
- 178 `BP_MapGimmick_BlockingBox_C` and 104 `CPP_MapGimmick_BlockingBox`. Some are switched by a condition, for example `!{flag:928}` on `Dng_01Gra_41` (uid 7).
- 43 `BP_MapGimmick_NoEntry_C`, which play an event and turn the player back. 20 have a condition, such as `{progress:0}>=4000 & {progress:3}!=10` on `Dng_01Gra_40`.
- 41 blocking bases, 12 of them magic pots.
- To find out: whether the mod can change a blocker's condition (or its flag) at run time. If it can, an item can open one of the game's own gates, and we may not need to add new blockers.

**Round 67 (mod 0.53.0): the first real use.** No door or cave joins two continents. The routes without the airship are the ferry and walking on the world map (`open_world.md`, section 4, "Routes between continents"). The ferry is gated by rewriting its menu rows. Walking crossings are this idea's blockers, placed from `crossings.txt`, which the user fills in game with `ffrap_gate mark`. Round 68: the carts are in the mod, sized and turned by the user. Mod 0.54.0 and world 0.21.0 add the start without the airship (`open_world.md`, section 4).

## 20. Trap items, banked until the next battle

**Idea:** trap items that hit the party: "Bad Breath" (random status ailments), and stat downs such as Deprotect (defence down) and Deshell (magic defence down). Status ailments end with the battle. So a trap that arrives on a map or in a menu is banked by the mod and fires at the start of the next battle.

**Known so far:**
- **The statuses, from the game's enums (`eUnitStatusCondition`):** Poison 1, Blind 2, Sleep 3, Silence 4, Paralyzation 5, Confusion 6, Stoned 7, Charme 8, Stop 9, Berserk 10, Doom 11, Slow 12, and the stat downs AttackDown 15, DeffenceDown 16, IntelligenceDown 17, MindDown 18, BreakDmgDown 19, BreakDmgTakenUp 20. There are 87 in all, buffs too (Haste 33, Regene 30).
- **Bad Breath is in the game.** It is skill `くさいいき` in `DT_SkillData` ("Bad Breath"), plus "Super Bad Breath" (`ちょ～くさいいき`). Its effect is row 1376 of `DT_SkillEffectData`: an `AddEffect` with a 50% chance that lasts 3 actions. Its `ParamList` holds 1023, 1027, 1028 and 1029, which look like the ailment effect rows it picks from.
- **A battle start can be seen.** FFRSLib hooks `/Script/mucha.CPP_MapManager:Encount` for field encounters.

**The design:**
- The apworld gets trap items and a `trap_chance` option (filler replaced by traps).
- The mod queues a trap (a new item kind `trap`) and keeps the queue in its state file, so a restart keeps it. At the next battle, once the party's battle units exist, it applies each banked trap and says so in the feed ("Bad Breath! Poison, Blind").
- Traps never fire in a story battle with a fixed party, or in a boss battle, if that can be told apart (a setting).

**Probe results (round 30, `ffrap_find` in a battle):**
- **No call adds a status directly.** `ffrap_find AddStatus` found only the class `CPP_ContFxAddStatusCondRegist`.
- **The game adds statuses through continuous effects.** `CPP_ContFxAddRandStatusCondition` adds a random status (which is what Bad Breath does), and `CPP_ContFxCureStatusCondition` cures one. `CPP_ContEffect.GetStatusCondition` reads an effect's status.
- **Units read their statuses** through `CPP_UnitParameter`: `GetStatusConditionList`, `HasStatusCondition`, `GetStatusConditionEffect`. `CPP_VM_UnitParam` has the same for the UI.
- **Battle units can be found** through `CPP_BFL_Battle`: `GetBattleUnitByUnitId`, `GetBattleUnitListByRelation`, `GetBattleUnitParameterByUnitId` and others. `GetStatusConditionList` is there too.
- There is a debug call, `CPP_DBG_BFL_Battle.DBG_ShowStatusConditionResistances`. The debug battle menu (`DT_DebugMenu_BattleUnit`, 38 entries) may have a "give status" entry to copy.

**To find out (round 31):**
- The parameters of those calls: `ffrap_functions CPP_BFL_Battle CPP_UnitParameter CPP_ContFxAddRandStatusCondition` in a battle.
- How to start a continuous effect on a unit: through a skill (Bad Breath's effect 1376), or by making a `CPP_ContFxAddRandStatusCondition` and adding it to the unit.
- Whether a status set at the very start of a battle is cleared by the battle's own setup.

## 21. NPC gifts as checks

**Idea:** many NPCs hand out an item when you talk to them, some in the story and some not. These could be Archipelago locations: the gift is blanked and reported as a check, like a chest.

**From the game data dump (round 30, 2026-11-06):** talk events carry an `ObtainItemList` (item `ID`, `Num`, and a `Condition`). About 200 talk events give items. Grouped by event table:
- **Free talk with town NPCs** (`FreeTalk/<region>/...`), about 20. For example Mage's Glasses in Mitra, Lunar Sword and Brigandine at the Colosseum, the Magi-tenna in Gaberada and the Cabin Key in Sian. Also Phoenix Down x5 and the Transporter (from Charlotte) in Grandshelt Castle.
- **Side quests** (`SubEvent/SubEv_Chapter01` to `09`), about 75. Rewards and gil from quest givers, the MogChase rewards in chapter 5, and the Aileen weapons in chapter 6.
- **Character events** (`CharaEvent`): 8 accessories from the party members' own events, and 9 vision events that give a vision plus Magicite (Amelia, Camille, Ayaka, Charlotte, Victoria, Wilhelm and more).
- **Story** (`MainEvent`): C01_014_03 gives the first two visions (Tronn and Leah), and C06_606_01 gives the White Jade Stone.
- **Others:** the Arena rank rewards and proofs, 12 Arms weapon awakenings (24), the strong enemies (15), the rope-jumping game (`Nawatobi`, 6), the summon events (7), the legend events (17) and the merchant ship (5).

**What it needs:**
- **The table as the location list.** A `tools/gen_from_dump.py` step that writes `data/game/talk_rewards.tsv`, with the event, map, items, condition and flags. Then pick which groups become locations. Free talk and side quests are the natural first set.
- **A way to see the gift.** Either a hook on the call that runs a talk event's `ObtainItemList`, or a check on the event's own done-flag (`OnFlagList`) after the event.
- **A way to blank it.** Set the row's `ObtainItemList` items to nothing, as chest blanking does for chest rows, before the event runs.

**Probe results (round 30, `ffrap_find ObtainItem`):** `TalkEventData.ObtainItemList` (the table rows), `CPP_TalkEventManager.m_ObtainItemList` (the list of the event that is running), `CPP_TalkEventSceneData.m_ExternalObtainItemList`, and the call `CPP_BFL_TalkEvent.SetExternalObtainItemList`.
- **To see a gift:** watch `CPP_TalkEventManager.m_ObtainItemList` while an event runs. When it holds items, the event is a gift, and the manager says which event it is.
- **To blank a gift:** the talk event tables are data tables, like the chest table (`CDT_TalkEventData_Prod` is a composite). Their `ObtainItemList` rows can be emptied the same way.

**To find out:** whether emptying a row's `ObtainItemList` stops the gift and leaves the event's text as it was; and, for open world, which gifts are still there at story 9000 (docs/open_world.md, section 6).

**Off-line pass (round 48):** side quests use their own counters (`{progress:15}==10`), not the main story's. 74 gift rows fall into about 20 quests. 11 of those have a start trigger in `gimmicks.tsv`, and no story test blocks any of the 11 at story 8000. This pass ignored flags and quest counters, and quests started by an NPC are not in that table. Mod 0.29.0's crystals already use `ObtainItemList:Empty()` on a talk row, so the blanking is proven.

## 22. A welcome window on an Archipelago new game

**Idea (round 37, 2026-11-08):** a dialogue window when an Archipelago new game starts: a short welcome to the mod and some tips. Not urgent.

**To find out:**
- Which of the game's own windows can show our text. The game's notices and tutorial windows are the first things to look at (idea 8's notes on `CPP_WBP_ChatNotice` and the quest notice).
- When to show it: after the reload on the world map, once per save, and not while the item feed is busy.
- What to say: how to connect the client, what the airship and continents do, and where the checks are.

## 25. Making the run more than picking up checks

**The concern (round 49, 2026-11-09):** the game feels like exploration only: go to an area, get the chests, go to the next. Battles in between are mostly grinding. The user pictures something like FF4 Free Enterprise, where bosses are the real fun and your current setup is what makes each one a puzzle. The hard part is MRP, which needs battles. The likely answer is sliders: grind as much as you like, then turn encounters off until you want more (idea 18).

**Found off-line (round 49):**
- **Fights that need no story are already in the talk tables.** 210 talk rows start a battle through `encountGroupId`: 40 Arena, 24 Twelve Arms awakenings, 19 side-quest, 15 strong enemies, and the rest story. A battle group also has `battleFinishEventId`, so a win can run an event. So a row may be able to start any boss's group from anywhere. This is the likely way to bring story bosses back as fights on the map.
- **How a fight row works.** It is a Sequence row that plays a shared sequence (`SEQ_CommonEncount`) and names a group in `DT_BattleGroup` by number. `encountGroupId` is a plain int, so it is cheap to change.
- **How a win is seen.** The group's `battleFinishEventId` names the talk row to run after a win. Strong enemies use it: `StrEne_C01_Orge_Destroy` sets flags and gives the reward. The same row with our own flag would be a check. Lose and escape have their own fields.
- **What the story bosses carry.** Almost all have a finish event that plays a story scene (for example `C01_037_01`), and 33 have a scripted event inside the battle (`battleEventId`). These must be cleared or they would run story from the middle of an open world. Only one group moves the party after a battle (9059, the opening Iron Giant).
- Chests can have `battleFinishEventId` too (`MAP_GIMMICK_TREASURE_BOX_DATA`), so a monster-in-a-box chest is a pattern the game has.
- **The test is `ffrap_bossfight <group>`** (mod 0.35.0). It borrows the first Twelve Arms fight and its Victory row, and points the sanctum crystals at it.
- **Round 49: a claimed crystal is a different event.** After a claim, the crystal stands in an inner room (for example map 10231, the Sanctum of Cecil). It runs `Int_LegendEV_Retry_Start_NN_01`, which asks whether to revisit the vision. "Yes" runs `_02`, which goes back to the scenes. Mod 0.35.0 only changed the unclaimed crystal's rows, so the user got the old revisit. Mod 0.35.1 points `_02` at the fight too, so the question becomes "fight?". A yes/no before a boss is a pattern we could keep.
- **Round 49, second try: "yes" did nothing,** and touching the crystal again asked again. 0.35.1 made `_02` a Blueprint row with no Blueprint, chained to the fight. A guess: a talk event that starts as a Blueprint row does not play a chained row's sequence. The crystal skip only ever chains Blueprint rows to Blueprint rows. Mod 0.35.2 copies the game's own shapes instead: the question's "yes" branch goes straight to the fight row (as `12Arms_..._Choice` does), and an unclaimed crystal's opening stays a Sequence row that leads to the fight. It also logs `CPP_MapManager:Encount`, to tell "no battle asked for" from "asked for, but did not start".
- **Round 49, third try: still nothing, and `Encount` was never called.** So either no battle was asked for, or event battles do not go through `CPP_MapManager:Encount`. All three tries reached the borrowed fight row (`12Arms_01Sword_1stAwake_Encount`), so the fight row itself is the likely problem when it plays outside its own Twelve Arms setting. Its sequence, `SEQ_CommonEncount`, is in the game's patch pak (`FFRS-Windows_0_P`), which `dump_game` cannot read ("Couldn't find chunk"), so its director code is unknown. Its name table shows a director Blueprint with a custom event `IsMovie`. Mod 0.35.3 adds `ffrap_bossfight watch`: it hooks the talk event and encounter classes and logs which functions run, so one play-through shows where the chain stops. Testing group 9957 (the row's own Twelve Arms fight) tells the group apart from the place.
- **Round 49, fourth try (mod 0.35.4): no fight with 9957 either,** so the borrowed row is the problem, not the group. The watcher found little that helps: `CPP_TalkEventManager` has 3 hookable functions, `CPP_BFL_TalkEvent` 6 and `CPP_MapManager` 12. Only `OnFinishFade` ran around the crystal, once per talk. `PlayEvent` never ran. The useful finding: **a normal random battle never called `CPP_MapManager:Encount`.** A battle shows only as a move to map 20001. So the "no battle was asked for" of the third try meant nothing. The game's own event and battle code runs in C++ that UFunction hooks do not see.
- **Chests can be traps.** Every chest row (`MAP_GIMMICK_TREASURE_BOX_DATA`) has `IsTrap`, `battleGroupId` and `battleFinishEventId`: a monster-in-a-box. No shipped chest sets `IsTrap` (one row in the Grandshelt Castle dungeon names group 51, which does not exist). Mod 0.36.0 drops the crystal trigger and makes the closed chests near the player traps for the group, in the table and in the live chests' copies, as chest blanking does. If the engine still acts on `IsTrap`, a boss check could simply be a chest.
- **The game's own fight trigger, as a control (mod 0.36.1).** The user asked about an NPC on the airship instead. Spawned NPC pawns destroyed themselves or crashed (idea 16), and talking to an NPC is the same talk event chain that failed. The Twelve Arms pedestals in the Chamber of Arms (map 3290) are the shipped version: an interact trigger runs `12Arms_01Sword_Check` (a Sequence row with no sequence), which needs the Ancient Greatsword (10198) and flag 901 off, then `_1stAwake_Choice` asks, then its branch runs `_1stAwake_Encount`. The test changes only that last row's `encountGroupId`. If Siren appears there, retargeting a fight row works, and the crystal failure was our chain. `ffrap_bossfight sword` gives the Greatsword.
- **Round 49, fifth try (mod 0.36.1): it works.** The pedestal started the sword fight with 9957, and **Siren with 9013**. Both wins logged `boss test: WIN seen`, so the flag on the after-win row is a working check. A loss gave the normal game over (Retry, Load, Return to Title). So a fight row can be pointed at any boss group, and the crystal failure was our chain, not the fight row. Siren fought on her own stage.
- **But both wins ended on a black screen.** The after-win row was a Blueprint row with no Blueprint. The screen is faded out after a battle, and all of the game's after-win rows are Sequence rows. Mod 0.36.2 tries two Sequence rows: the Victory row with its own scene, and `choice_cancel` (a Sequence row with no sequence) with `quiet`.
- **Round 49, sixth try (mod 0.36.2):** the pedestal with the Victory row worked end to end: Siren, a win, the sword's victory scene (it said the weapon was upgraded, though no item was given), and back in the Chamber. **A chest started Siren too** (`IsTrap` works), but with `quiet` (`choice_cancel`, a Sequence row with no sequence) the screen stayed black after the win. So an after-win row needs a real sequence. Mod 0.37.0 makes `quiet` use `Gim_EV_Majipot_Delete_02`, the magic pots' short after-win scene. The chest's own check went out, but its pop-up was missed (the battle came instead).
- **Round 51: a chest in a dungeon started the fight again** (map 3000). The user lost, so the after-win scene is still unseen.
- **Round 52: a chest boss works end to end** (map 3000, `quiet`): the fight, the win (`boss test: WIN seen`), the magic pots' short scene, and back on the field. So a boss check can be a chest in any map with battles.
- **Round 50: a chest in a town did not start the fight.** In Grandshelt (map 2000) the trapped chest opened as normal and gave its item, with the default and the `quiet` win row both. In round 49 a chest in a dungeon (map 3050) did start Siren. So a trap chest likely needs a map where battles happen. Not proven.
- **What this means for the design:** a boss check can be an interact point whose own chain asks and then fights, like the pedestals. The Chamber of Arms has 12 such pedestals, and other "challenge?" spots may too. Next: find out whether the chain can be added to an interact point that has none, or whether the checks should borrow the game's own fight spots. Chests are now a proven second option: any chest can be a boss.
- There are 176 battle groups with a boss in them: 48 story chapter bosses by name, 15 strong enemies and 113 others.
- A boss's MRP is `ap` in its battle group, which the mod already writes. Boss wins could pay for most of a character's growth, so grinding becomes a choice.

**Round 59: [docs/bosses.md](docs/bosses.md) has the design.** 25 fights that still start by themselves are locations in world 0.17.0, and story bosses give Crystal Fragments for the tower.

**Ideas, the strongest first:**
1. **Boss fights as checks.** Start with the Twelve Arms, strong enemies and Arena: about 80 fights that are already self-contained.
2. **Bosses pay for growth.** A large MRP and EXP reward from each boss, so a player who skips encounters is not behind.
3. **Bosses in a shuffled order.** Level sync makes any order fair. What you hold when you meet a boss is the puzzle.
4. **Random objectives each seed** (idea 24), so seeds ask for different things.
5. **Hints bought with gil,** at shops or the moogle, to give gil a use. Shops could be checks too (`shops.tsv`).
6. **Traps and DeathLink** for multiworld spice (idea 20).
7. **Party slots as items.** Start with one or two slots and find the others, if the party limit can be changed.

## 28. Character abilities as checks

**Idea:** party member abilities (Fire, Provoke, etc.) are locked until found in the multiworld. When characters level up and would normal get one or more abilities on that level, instead we would send checks to the server.

## 29. What a boss fight needs, in logic

**Idea (round 63, the user):** with scaling, a boss is a real gate. The right party and visions matter more than levels. So a boss location should need, in logic, the tools to win. For example, Salome could need at least one member or vision with wind skills, and one with healing magic.

**Why it matters now:**
- Round 63: on Normal, the Nameless Ruins bosses and Mom Bomb could not be won with what the seed had given by then. The user raised the party's level by hand to finish them.
- Universal Tracker showed many fights in logic that were not winnable without more members, visions or gear.
- Cave masters are priority locations (`priority_bosses`), so a progression item is likely to sit at a fight like that.

**What is known:**
- Each unit row in `DT_UnitParameter` has `ElementResistanceList` (element to resistance) and `StatusConditionResistanceList`, so weaknesses are in the off-line data. It also has an `IsBoss` field.
- The skills are under `Datatable/Skill`. Which member and which vision gives which element or healing is not tabled yet.

**What to find out:**
- A table: each member's and each vision's elements, healing and buffs, by level or by vision rank.
- A table: each boss's weaknesses and a rough tier (from its scaled level band).
- The rule shape. One choice: a boss needs N members plus visions (N by tier), at least one of them hits a weakness, and one can heal. Another: count "power" items (members, visions, weapons over some tier) in place of exact skills.
- Whether a cave master should stop being a priority location until this logic exists.

**First-pass design:** see [docs/boss_logic.md](docs/boss_logic.md) for the capability matrix, 8-element mitigation table, progression proxies, per-boss rules for all 41 bosses, and unshuffled Vision / side-quest location requirements.

## 30. Libra options

**Idea(s):** Users have expressed interest in a "Librasanity" option, which basically means there's a check in the multiworld for scanning each enemy. This would introduce a bunch of extra locations, which would need lots of filler to be populated (gil, consumables, magicite, etc.). To help this out, I would want to introduce some supporting stuff:
- start with all characters knowing Libra
- all characters can learn Libra, either naturally or via AP items

Along the same lines, I would also want an option for players to start with all enemies already scanned. If this option is enabled, it would need to disable Librasanity though, otherwise the player would send out hundreds of checks immediately - unless we could set it up where the game needed to "see" the enemy to trigger the check. That's probably more work, but probably doable. Eventually I think I would also want an Enemysanity option, very similar where you get a check for each time you defeat a unique enemy.

## 31. Shopsanity

**Round 71 (the user):** the merchant ships on the ocean, which the airship can visit, sell things such as Adamantite and the Ancient Tome. They could be locations that need the Airship. The game data has them as talk rows `GimEv_MerchantShip_01` to `_05` (`_Talk`, `_Buy_0N`, `_BuyAll`), found while looking at the ferry (round 67).


**Idea:** Each shop slot becomes an Archipelago location (see: Crystal Project, Cross-Code, ALttP, etc.) - you have to buy the item to trigger the send, afterwards that shop slot is removed (or replaced with its original vanilla item).

## 32. Radar treasures as locations

**Round 72, from the user's question.** The airship radar does not reveal any of the world-map shinies we have: those have no visibility condition and stand there from the start. It finds 13 treasures of its own instead (`docs/logic.md`, "Treasure radar").
- **In the game:** a side quest on the airship (`{progress:49}`) installs the radar (flag 702) and then the Magi-tenna (27006), Resonance Stone (27007) and High-Power Generator (27008, sold by a merchant ship). Each part opens the next tier of pinger points: 5, then 4, then 3, then the 13th.
- **The rewards:** `SubEv_C05_TreasureRadar_01_01` to `_13` give Adamantite (20016), Magicite (25001), two Magicite Crysts (25002) and nine pieces of equipment (11098, 12016, 11022, 10497, 10819, 12038, 12073, 12075, 12059).
- **At story 8000 on our start,** flag 702 is off, so no pinger works. The three parts are key items in our pool that do nothing yet.
- **To build:** the 13 treasures as locations (their found flags 704 to 715 as checks, as the bosses' win flags are), the radar on at the start (flag 702) or as an item, and the parts as a progressive item that steps `{progress:49}` to 40 and 50. They need the Airship. Their rewards go to the pool, and their win rows give nothing, as chests do.
