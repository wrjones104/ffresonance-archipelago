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

**Round 79 (the user asked whether to probe this now).** Token Legacy showed the stand-in Potion because its check came after the game's pop-up had closed, not because of the widget. An own pop-up shown at check time would still come after a Potion pop-up. Way 1 is the one that helps every kind of check: with an empty reward row (a chest's `Money 0`, a quest's empty `ObtainItemList`) the game shows no pop-up of its own, and the mod shows its text whenever the check comes. Its test also covers quests: empty one quest's reward row and see whether the row still runs, completes the quest and moves the counter. Build 42898077 fixes the quest case without it (arms the pop-up from the counter's value before the reward). **Probe built (round 81, build 27ed563a):** `ffrap_empty chest|shiny|quest <id>|off` makes this map's closed chests, its shinies or one quest's reward rows give nothing. Chests are kept empty through chest blanking (`G.emptyRows`); the check logic does not look at the contents, so the checks still go out. **Round 81 result:** it works. An empty chest shows the game's pop-up with "0 gil", an empty shiny and an empty quest row (Rogue Rebel) show their pop-up too, and each opens or completes as normal with its check sent. Rogue Rebel gave nothing of its own and showed complete. **Built (after round 81):** chests and shinies give nothing in place of 1 gil, and quest rows lose the location's item in place of the Potion. The radar and the boss rewards keep the Potion until they are tried empty.

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

**Side quests (2026-11-17):** planned in [docs/side_quests.md](docs/side_quests.md) (idea 36). Free-talk gifts stay here.

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
- **Built (mod 0.57.0, world 0.24.0):** the 13 treasures are locations (found flags 704 to 716 as checks). Three Progressive Radars (item 27006, counted by the mod from the session's items) take the place of the three parts: one turns flag 702 on, two and three set `{progress:49}` to 40 and 50. They need the Airship. Their rewards go to the pool, and each dig row gives the pop-up's stand-in Potion. The pingers also chain: each needs the one before it found (`{progress:51}`, set by each dig row).
- **Round 75 (mod 0.59.0, world 0.28.0):** the radar works (round 74), and each Progressive Radar now opens its whole tier at once. The mod holds the found count `{progress:51}` at the top of the radar's band (13, 22, 31), the threshold of the tier's last point. Mt. Reizan's Chest 3, which holds the Resonance Stone, is a location with the treasures on (`docs/playtesting.md`, round 75).

## 33. The Mechabo upgrade quests cannot start

**Known issue in v0.28.0 (found off-line, 2026-11-16).** The three Mechabo quests from Verun cannot be reached on our start. Verun never appears at the Dwarven Forge or on the airship. This goes with the other side-quest work ([docs/side_quests.md](docs/side_quests.md), idea 36).

**Why:** the whole chain runs on one counter, `{progress:16}`. The story event `C02_219_02` ("Mechabo repair request") sets it to 10, and the skip never runs that event, so it stays at 0. Each Verun NPC is visible only while the counter is in its range (`m_VisiblFlagCondition`):

| Map | NPC | Visible when | Quest and event rows |
|---|---|---|---|
| 2050 Dwarven Forge | 7 | 16 is 10 to 19 | Arise, Mechabo! (`C02_MechaboLvUp_00`, `_01`) |
| 2050 Dwarven Forge | 0 | 16 is 20 to 70 | Mechabo Evolved (`_02` to `_06`), then `_07` |
| 20001 Airship | 28 | 16 is 75 to 99 | Mechabo Unleashed (`_08` to `_10`) |

**How the chain runs:**
- Each material step is a delivery quest on quest board 1000 (`DT_Request_QuestData`, quests 1001 to 1007), shown when the counter is 10, 30, 40, 50, 60, 80 or 90.
- The player brings 2 or 3 drops from normal enemies: Ipooh, Dhorme Chimera, Medusa, Destroyer, Sandworm, Mahadeva and Malbodoom. Delivering runs `_NN_ItemGet`, which sets flag 219.
- Talking to Verun with flag 219 on runs the next row. That row clears 219 and moves the counter on by 10.
- No other story test blocks it. "Arise, Mechabo!" needs story 2120 or later, and "Mechabo Unleashed" needs 5020 or later. Our start is 8000.
- `C02_219_02` also sets flag 13, which `OPEN_WORLD_FEATURES` already sets.

**Rewards:**
- Lid (unit 1004) learns six abilities from the rows' `AbilitySettings`: Mechabo Tackle (404110), Overclock (404130), Mecha Fat Chocobo (404070), Mecha Behemoth (404060), Overclock Zero (404140) and Mecha Mog Scan (404120).
- `_01` gives a Magicite Shard (25000), `_06` a Magicite (25001) and `_10` a Magicite Cryst (25002).

**The likely fix:** set `{progress:16}` to 10 on the open start. Also set it on load when it reads 0, so existing saves get it. `G.SetProgressValue` already does this kind of write for the radar.

**Built (round 78, mod 0.61.0):** on an open world seed's save, the mod sets `{progress:16}` to 10 whenever it reads 0. The three quests are not locations yet.

**Round 84 result:** Verun is at the forge and asks for the Ipooh drops (`C02_MechaboLvUp_00_yet`), but "Arise, Mechabo!" was not in the quest log. The quest log is fed by each event row's `RequestStateSettings` (Accept, Proceed, Complete), and the Accept of request 17 is in `C02_219_02`, which the skip never plays. **Built (build a87aac00):** `G.MechaboPatch` puts that Accept first in `_00_yet` and `_00_ItemGet`. Quests 26 and 27 are accepted by the chain's own rows (`_02`, `_07`).

**Round 85 result:** still no quest, and Ipooh kills did not count. Request 17's own row (`DT_RequestData` `C02_MechaboLvUp`) is accepted only while `AcceptCondition` holds, `{progress:16}==0&{progress:0}>=2120`, and the start has the counter at 10 already. Its first step lists quest 1001 on quest board 1000: "Ipooh" x2 (`ClearConditionList` ID 55), most likely a hunt that counts only while the quest is accepted. **Built (build b93912a5):** `G.MechaboPatch` also sets request 17's `AcceptCondition` and `Occurrence.Condition` to `{progress:16}==10`.

**To find out:**
- Whether the steps should be locations: the six abilities and three Magicite rewards, with logic for each material's enemy area. The steps also need Lid in logic if the abilities stay vanilla.

## 34. Location names a player can find

**From the user, 2026-11-17.** "World Map Shiny 167" says nothing about where to look. Players asked during the pre-release.

**What the data gives without a person (a prototype, 2026-11-17):**
- **World-map shinies (94) and radar treasures (13):** each has x and y. The world map has 99 doors with a named destination (`transitions.tsv` to `maps.tsv`) and the continent boxes (`data/continents.tsv`). Nearest door plus a compass point gives, for example, Shiny 167 "Gronoa, NW of Rugged Mountain Path", which matches the user's screenshot. The axes are +X north, +Y east. Weak spots: five or more doors are all "Sanctum of Light", and a few shinies are 3000 or more units from any door.
- **Chests (206):** the place name is there already, and a dungeon is mostly one map, so there are no floor names. The chest's vanilla item makes a name: "Wind Shrine - Armor of Gales Chest". Only 4 of 206 share an item with another chest in the same place.
- **Tablet Shards (99):** a town's map name, with the uid as the number. A position inside the town (north, plaza) needs a person or landmarks we do not have.
- **Bosses and crystals:** already readable.

**What a person should do:** read through a generated list, fix the weak ones and name the tablet shards. A TSV of `key`, current name and suggested name, with an empty column for the user's name, does it. Names come from the generator (`tools/gen_apworld_data.py`) with the user's column as an override. The first draft is `data/location_names.tsv` (469 rows; 17 duplicates and 10 shinies far from any door are marked in `note`). Nothing reads it yet.

**Built (round 77, world 0.29.0):** `tools/gen_apworld_data.py` names every chest, shiny, Tablet Shard and radar treasure this way and rewrites `data/location_names.tsv` each run, keeping the `name` column. A filled `name` wins. Repeats are numbered ("Mysidia - Shiny near Salome Cave 1" to 3). Sanctum doors name their sanctum ("near Sanctum of Onion Knight"). The `old` column keeps round 76's names, for players with old yaml lists. Tablet Shards are numbered within their place, so they still want a person.

**What it changes:** location ids stay the same, so the client, the mod and old seeds keep working. Players' yaml lists (`exclude_locations` and the like) that use the old names stop matching. Do it once, before the full release.

## 35. Keep the received-items count in the save

**From the pre-release, 2026-11-16.** After a mod update, and on a second PC, players had to `/bind` again and got every item a second time.

**Why:** the applied count (`state.applied`, `slotItems`) and the seed key live only in `ap_state.txt`, beside the mod. The install steps say to delete it on an update. A save bound by `/bind` with no count starts at 0 and gets everything.

**The likely fix:** write the count, and a short tag of the seed, into the save. Unused event flags as bits are one way: 20 flags count to a million items, and 16 more hold a hash of the seed key. The game saves them with everything else, so Steam Cloud carries them to the other PC. On load, a save whose tag matches the session is the session's, with the count it holds. `ap_state.txt` stays as a fallback for saves from before.

**Built (round 77, mod 0.60.0):** 12 count flags (1414 to 1419, 1430, 1432 to 1436) and 11 tag flags (1437 to 1439, 1442 to 1449). The tag is FNV-1a of the session key folded to 1 to 2047. On load, a save whose tag is the session's is linked with its count, before `ap_state.txt` is asked; a save stamped by another seed is not linked even when `ap_state.txt` lists its slot. The mod writes the stamp whenever the applied count changes, in the same tick as the grant, so a save the game makes holds both together. A save from before 0.60.0 has no stamp and is judged by `ap_state.txt` as before, then stamped.

## 36. Side quests as locations

**From the user, 2026-11-17.** Side-quest rewards in the pool. The plan is [docs/side_quests.md](docs/side_quests.md).

**Off-line pass (2026-11-17, before round 78):**
- The game's quest log (`DT_RequestData`) has 33 quests with English names, accept tests, completion tests and prizes. 31 become locations in the first pass; Battle at the Big Bridge and Iron Splitter go with the bosses.
- Each quest runs on its own counter. Quest-item gift rows move the counter, and the next step tests the counter, not the item. So 11 quest items in our key-item pool unlock nothing: Dew of Reprieve, Viscus Vitae, Rushroom, Pure Water, Convalescence Draught, Super Salubrious Salad Stem, Portrait of Dario, Dario's Letter, Ruby Fragment, Broken Sword Hilt and Blade (20020, 20023 to 20032). They leave the pool and stay vanilla (decided with the user).
- Every quest's start holds at story 8000 except the Mechabo quests (idea 33).

**Built (round 78, world 0.30.0, mod 0.61.0):** option `include_side_quests` (off by default for now): 28 quest locations, `quest:<id>`. The mod swaps each reward row's first item for the stand-in Potion, takes visions out, and reports a quest when its counter reaches the reward row's value. The 11 quest items left the pool. `data/quests.tsv` lists the quests by hand; `data/game/quests.tsv` and `quest_steps.tsv` come from the dump.

## 37. Open the Oblivion Palace safes with no turn-in

**From the user, 2026-11-18 (during round 79).** The turn-in is slow: every visit to the Enigmatic Princess plays her talk, then the same scene once for each chest earned. The user wants to walk in and open the safes the shards already pay for. Her last talk at 99 shards stays.

**Off-line pass (2026-11-18):**
- Each safe tests only story counter 43. Safe *n* (chest `2031:n`) has `m_OpenCondition` `{progress:43}>=11+n` in `Town_02Lan_22_01_GD`, and the Blueprint's `HaveSafeDepositBoxKey` asks `IsMeetCondition` on it. The safes never test the shards.
- The princess's chain (`DT_TalkEventData_SubEv_Chapter01`): her first talk, `SubEv_C01_Collection_01`, sets counter 43 to 10, which also lifts the palace's blocking base (`{progress:43}==0`). On each talk she takes every shard held (`TransferItemList` 25004, `Num -1`) into `{transferItem:0,25004}`. `SubEv_C01_Collection_04` then runs one step per chest earned: step *k* needs `{progress:43}==10+k-1` and enough shards turned in, plays the same scene and sets the counter to `10+k`. That loop is the repeated talk.
- `SubEv_C01_Collection_05` then gives the milestone talks, by shards turned in and flags: `_06` at 28 (flag 151), `_07` at 60 (flag 152, Steam achievement 17), `_08` at 99 (flag 153). They give no items.

**The likely fix (mod only):** hold counter 43 at `10 + chests earned`, counting shards held plus shards turned in, as the radar holds its counters (idea 32). The safes then open with no talk. The mod leaves the shards in the bag, so a talk to her still takes them and plays the milestone talks, the last one included. Her step loop finds every step already done and plays nothing. Turned in: `{transferItem:0,25004}` lives in `SaveData_TransferTargetInventory` (a map), so the mod can ask the game's `CPP_BFL_Condition:IsMeetCondition` instead of reading the map. To test in game: the call from Lua, and whether a safe in view changes when the counter changes, or only on the next visit.

**Built (for round 80, mod 0.61.0):** `G.PalaceSync` (`game.lua`), run each tick on a seed's save. It holds counter 43 at 10 plus the steps paid by the shards held and turned in, asking `IsMeetCondition("{transferItem:0,25004}>=N")` for the turned-in part. It never lowers the counter, and leaves it alone when the condition test is not found. The log line: `palace: 5 shards held, 1 steps paid, progress 43 at 11`. A save that has never met the princess goes to 10 at once, so the palace's barrier is gone from the start.

**First try (round 80, 2026-11-18):** the safe for 9 shards stayed shut. The save had 6 turned in the old way (counter 12) and 4 held. The log said `palace: 4 shards held, 1 steps paid, progress 43 at 12`, read on the world map before the player went in. So `{transferItem:0,25004}` read 0 there, and the mod did not ask again in the palace, because the held count had not changed. The save keeps turn-ins in `SaveData_TransferTargetInventoryByMap`, a map keyed by map, so the test most likely reads the current map's turn-ins only. **Fix (mod build cac73e78):** the turned-in count is read only in the palace (map 2031), as a whole number in 7 tests, and kept for the save. It is read again there when the held count changes. Elsewhere the last reading counts, or none.

**Works (round 80, build cac73e78):** with 6 turned in and 4 held, the 9-shard safe opened with no talk. Three more shards sent from Archipelago while in the palace raised the counter, but the next safe opened only after leaving and coming back.

**Why, and the likely fix (not built; the user: rare in a real run, leave it unless it is cheap):** the safe's `OnUpdateHaveItem(in_Value)` tests `m_OpenCondition` again and sets up its event (`SetupEvent`). By its name it runs when the bag changes, so the princess taking the shards refreshes the safes. An Archipelago shard changes the bag before the mod raises the counter, a tick later, so the refresh comes too early. Calling `OnUpdateHaveItem` on each live safe after the counter goes up would likely fix it. `in_Value` is an object, and whether the function reads it is not known, so it needs a probe behind a test command first.

## 38. An Archipelago page in the main menu

**From the user, 2026-11-18 (during round 82).** Our settings sit at the bottom of the game's Options screen. The user wants an entry of our own in the main menu, as FFR Bestiary has, with the settings and more: Tablet Shards and Crystal Fragments found, the seed's settings (goal and so on), and which continents are open.

**How FFR Bestiary does it (0.1.7, read 2026-11-18):**
- **The entry is a pak** (`~mods/zzz_FFRBestiary_P`). It replaces two whole tables. `DT_MainMenuScene` gets a row tagged `UI.MainMenu.Scene.Bestiary` that opens `WBP_HelpLayout`. The debug menu's tag table `DM_DT_GameplayTag_Option` gets a row that registers the tag. The tables are the game's, so its installer builds the pak on the player's PC (retoc, uasset-json, an Oodle download, one game start in between).
- **Lua puts the entry in the menu.** It adds the tag to `CPP_DA_MainMenuRoot.DisplaySceneList` before System, and names the entry per language in `CPP_MainMenuSubsystem.SceneDataMap`.
- **Lua builds the page in a borrowed screen.** When the activated `WBP_HelpLayout_C` under `WBP_MainMenuLayout` opens, it resizes the window, hides the title and puts its own boxes in the screen's `NamedSlot`. The pieces are the game's: `WBP_SystemSubhead` (headings), `WBP_Cmn_Window` (framed panels), `WBP_LeftLineButton` (framed rows), `BP_SystemTextStyle` (body text). A pre-hook on `PushLayoutWidget` stops confirm from opening a tutorial.
- It calls `SetColorAndOpacity` with a Slate colour table and does not crash. Our round 20 lesson says a Slate colour struct crashes a setter. Test it behind a probe before we use it.

**What we cannot copy:**
- **The pak.** A second pak that replaces `DT_MainMenuScene` drops the row of whichever loaded first. Bestiary logs this case.
- **The Help screen.** Bestiary takes over any activated `WBP_HelpLayout_C` under the main menu, so it would draw on our page. The menu pools one screen per class, so the System page's class is out too.

**Our way (no pak), from the off-line dump:**
- `DT_MainMenuScene` has 8 rows (Root, Item, ActionEquip, Heal, Map, Party, Journal, System). Their struct is `MainMenuSceneData`: `SceneTag`, `EntryName`, `SceneTitle`, `IconTag`, `LayoutData.LayoutWidget` (a soft class), `EnableFlagIdData` and more.
- `DA_MainMenuRoot.DisplaySceneList` lists Map, Journal, Item, Heal, ActionEquip, Party, System.
- `DefaultGameplayTags.ini` registers three scene tags that no row uses: `UI.MainMenu.Scene.Vision`, `.Equipment` and `.Action`. A registered tag needs no tag table. Our Options rows also work with tags never registered.
- So: `AddRow` a copy of System's row into `DT_MainMenuScene` from Lua, as the Options rows are added, then add the tag to the scene list. `CPP_MainMenuSubsystem` (a world subsystem) keeps its own `SceneDataMap` and `SceneEnableMap`, so it may need the row too, when it was built before the row was there.

**What the page can show:** the tower lock's counts (characters, Visions, Crystal Fragments, from `cfg finalboss`), each continent's lock (`game.ContinentOpen`), the start and vehicle settings from the `cfg` lines, and Tablet Shards from the bag. The goal and checks found of total need new `cfg` lines from the client.

**Probe built (round 82, mod build 26b6adfa):** `ffrap_apmenu`, each writing step logged before it runs:
- `info`: the table's rows, the scene list, the subsystem's maps and the view model's scenes, to `ffrap_apmenu.txt`.
- `on [own|vision|equipment|action]`: adds the entry, named Archipelago, every tick from then on. `own` is `UI.MainMenu.Scene.FFRAP`, never registered.
- `layout <system|help|tutorial|option|journal>`: the screen it opens (default: System's). It writes the soft class with `Conv_SoftClassPathToSoftClassRef`, then as a string, and reads each back.
- `screens`: every instance of those screens, activated and visible.
- `tree`: the open entry's screen, widget by widget, to `ffrap_apmenu.txt`.
- `text`: one line of text on the open entry's screen.
- `off`: stops adding it. A game restart takes it out.

**Round 82 result (build 26b6adfa):** the entry works with no pak and sits beside FFR Bestiary's. Our own unregistered tag is enough. The screen it opens can be set from Lua. Tutorial, Options and Journal all opened empty. The Tutorial screen is the host: one framed window, and no other main menu page or mod uses it. Options shares its panel with Help (FFR Bestiary's), and Journal is the Quests page's own class.

**Built (round 83, build 0c2a8b95):** `ffrap_apmenu page` fills the Tutorial screen: the title "Archipelago", the seed's state in the description, and the image box, arrows and page count hidden. The client sends `cfg goal` and `cfg checks` for it. Still to do once the page is seen: turn the entry on by default for a seed, lay the page out with the game's heading and framed-row widgets (as FFR Bestiary does), and decide what the arrows could page through (for example, the received items).

**Round 83 result (build 6a38c39e):** the page works and opens and closes again and again. Three fixes on the way:
- The page finds its widgets by walking the screen (`GetWidgetFromName` found nothing).
- The menu turns the screen off as soon as Back asks it to close, so the screen's own `FinishedClose` never ran. The page turns on the base class's default finish for a close (`CloseStateProperty.IsEnableDefaultFinisheCall`). A fallback calls `FinishedClose` on a screen off but still closing.
- `ffrap_apmenu close` is a way out: `OnRequestClose`, or the view model's `PopScene()`.

**Round 84 result (build dc66cdd9):** the page works as a normal feature. **From the user, round 84:**
- The page leaves the menu on a save not linked to the seed, and the settings go back to the game's own there (built, a87aac00; idea 39 for the rest).
- Tablet Shards held and turned in, and the safes ready to open, so a player can count without the princess's talk (built, a87aac00).
- Nicer layout: sections or framed boxes. Not built. FFR Bestiary's way is the guide: `WBP_SystemSubhead` for headings, `WBP_Cmn_Window` for framed panels, `WBP_LeftLineButton` for framed rows, all made and put in the screen from Lua. It needs a probe behind a test command first (round 20 lesson: no font or Slate colour structs to setters).

## 39. Our settings in the Archipelago page

**From the user, 2026-11-18 (round 84).** Move the settings from the bottom of Options > Gameplay into the Archipelago page. On a save not linked to the seed, the page is gone and the settings are the game's own; `/bind` brings them back. This reverses round 57, which applied the settings to every save.

**Built (round 84, build a87aac00):** the second half. `save.vanilla()` in `main.lua` is true with a seed known, a save loaded and the save not the session's. Then `settingsTick` writes `SETTING_DEFAULTS` (the game's own rates and encounters), and the page's entry leaves `DisplaySceneList` (`A.Unlist`). Scaling was already off on such a save. A mod run with no seed at all still applies the settings.

**Not built: the settings in the page.** The page is the Tutorial screen with one text box. Settings need rows the player can move between and change, as the Options screen's rows are. Two ways, both to probe first:
1. Build rows of the game's own widgets in the page (as FFR Bestiary does), with our own focus and input handling. The most work, and the most to go wrong.
2. Keep the Options rows, and have the page say what they are set to and where to change them. Cheap. The rows could also be hidden on a save not linked to the seed.

Until then the Options rows stay, and on a save not linked to the seed they change nothing.

**The user chose way 1 (2026-11-18).** A third way came out of the dump, and it may be the cheapest that still puts the settings in our entry: let the entry open the game's own Options screen, which already does rows, focus, a gamepad, saving and the description box.
- The game opens Options from `DT_GameLayoutWidget_System`'s `UI.Layout.Option` row. Its `LayoutData` gives the screen two view models, `CPP_VM_Option` and `CPP_VM_OptionKeyBind` (context name `CPP_VM_KeyBind`), and two more input contexts, `UI_Info` and `OptionMenu`.
- Main menu rows hold the same `LayoutData`. Round 82 opened Options from our entry with the screen class only, and it came up empty. Journal did too: its row has `VM_Journal`. So the missing view models are the likely cause.
- The tabs are rows of `DT_Option_Root`, one per category (`FOP_Parent_CommandCategory`: Gameplay, Graphic, KeyboardMouse, Gamepad, Sound). Each has a `Condition` string and `Object`, the row table it lists. The categories are a fixed enum, so a sixth tab of our own is not simple.
- Option rows (`DT_OP_GameSetting`) have types including `Subheader` and `Command`, and an `ItemDescription`. Section headings and read-only lines for the seed's state could be rows of those types.

**Probe (round 85, build 05f33eda):** `ffrap_apmenu options` writes the Options screen and the layout row's view models and input contexts into our row and the menu subsystem's copy (`A.WriteScreen`). `text` puts the page back. `tabs` lists `DT_Option_Root`; `tabs only` leaves out every tab but Gameplay with a condition never met (`{progress:0}<0`), and `all` puts them back.

**To find out (round 85):**
- Whether the Options screen works from our entry: rows, Back, saving.
- Whether the tab list is read again at each open, so tabs can differ between our entry and System > Options.
- Then: which rows show in our entry (only ours, with the seed's state as headings and lines), and how to keep System > Options as it is.

**Round 85 result (build 05f33eda):** the Options screen works from our entry, settings save from it and from System > Options, and Back returns to the menu. `tabs only` and `tabs all` changed the tabs at the next open, so the tab list is read at each open.

**The plan from here:**
- Our entry opens the Options screen. When the player picks it, the tables switch to "our page": the Gameplay tab alone, named Archipelago; the game's rows hidden; heading rows with the seed's state. When the menu leaves our scene, they switch back, so System > Options is the game's own again. The title screen's Options would show the game's own too.
- The moment to switch: the root entry's click calls `CPP_MainMenuSubsystem:SetScene(tag, option)` from Blueprint (`WBP_MainMenuRootEntry.BP_OnClicked`), so a pre-hook sees our tag before our screen opens.
- Hiding a row: each option row (`OP_BaseMenu_EntryInfo`) has `ShowCommandData.ShowType` (ALL 0, TitleOnly 1, GamePlayOnly 2). TitleOnly should hide it in game.
- Headings: `DT_OP_KeyboardMouseSetting` has `SubHeader` rows of the same struct to copy, with our text in `DisplayText`. The rows also have `ItemDescription`, the line shown for the focused row, which could hold more of the seed's state.

**Probe (round 86, build b93912a5):** `ffrap_apmenu mode ap` makes the switch by hand (`A.Mode`) and logs each `SetScene` from a pre-hook; `mode game` puts the tables back. To find out: whether the page looks right, whether the hook fires before the screen opens, and whether `RemoveRow` takes the heading rows out again.

**Round 86 result:** it looks right: one tab named Archipelago, our settings, the page's lines as headings, and none of the game's rows. The hook logged `SetScene UI.MainMenu.Scene.FFRAP` on the click. `mode game` put System > Options back.

**Built (round 87):** the entry opens the Options screen by default (`APMENU.screen = "options"`).
- The `SetScene` pre-hook is registered when the page starts. Our tag makes the tables our page (`A.Mode "ap"`, with the page's lines as headings, blank ones left out); any other tag puts them back.
- Each tick, once the menu's scene stack has shown our scene and then left it, the tables go back (`state.apMenuBack`). They also go back if our scene never shows within 3 s.
- Our rows are TitleOnly when made, so in game System > Options no longer has them and the title screen's Options still does. On our page they are GamePlayOnly.
- The text page stays behind `ffrap_apmenu text`.

**Two tabs (the user, 2026-11-19, built for round 87):** one tab for the settings and one for the seed's state. A sixth tab is not simple (the categories are a fixed enum), but each tab shows the row table named in its `DT_Option_Root` row's `Object`. So the page keeps the Sound tab too, names Gameplay's "Settings" and Sound's "Seed", hides the six rows of `DT_OP_SoundSetting` (the volume sliders and its Reset button), and puts the heading rows there. `ffrap_apmenu split off` gives the one tab again. To find out: whether a tab holding only headings works (nothing on it can take the cursor), and whether the game's reset key on the Seed tab touches the hidden volume rows.

**Round 87 result:** both tabs work with a keyboard and a gamepad. Three findings:
- The first open showed the game's rows on Settings, likely because the game loaded `DT_OP_GameSetting` again after the hook wrote it. Since round 88, while the page is open each tick checks the tables (`A.Written`) and writes the page again if needed.
- A gamepad cannot scroll the Seed tab: no heading takes the cursor. The round 88 probe `ffrap_apmenu seedrows command` makes the lines Command rows (`WBP_OP_Command`, whose click is empty in its Blueprint).
- The user: the settings belong only in the Archipelago entry, not at the title screen. Since round 88 our rows are in the table only while the page is open.

## 40. Abilities the story gives, which the open start skips

**Found off-line, 2026-11-18 (round 86, looking at Lid).** Story rows add abilities through their `AbilitySettings` (`AddAbilities`, `AddCommandAbilities`), as the Siren row does for both Finas. The open start never plays them, and it adds only Siren's. From `DT_TalkEventData_Chapter*` (MainEvent):

| Unit | Abilities | Rows |
|---|---|---|
| Every character (1001 to 1008) | 1471, and their own `40x300` (Rain 401300, Lasswell 402300, Fina 403300, Lid 404300, Nichol 405300, Jake 406300, Sakura 407300, Archwitch Fina 408300) | `C08_817_01` (and its `_A` to `_H`, `_Nama` copies) |
| Rain (1001) | 1475 | `C06_624_01` |
| Rain | 401130 | `C06_626_01` |
| Rain | 401240 | `C08_820_03` |
| Rain | 1259 | `C08_819_04` |
| Rain | 401030, 401040 | `C08_821_01` |
| Fina (1003) | 210190 | `C06_608_01` |
| Lid (1004) | 404030 | `Lid_LB2_Get` (chapter 4; by its name, her second Limit Burst) |
| Fina and Archwitch Fina | 6, 430980, and command ability 6 | `C01_037_01` (chapter 1) |
| Archwitch Fina (1006) | 220110, 408030, 431120; command abilities 408010, 18, 400010, 7, 400020 | `C01_001D_01`, `C01_001D_02`, `C01_001F_02`; `C03_320_01` |

**To find out:**
- What each ability is (`data/game/capabilities.tsv` or the skill table), and which of them a player would miss. 1471 and the `40x300` set come at the end of chapter 8, just before the tower.
- Whether the start should add them all, or only those a player could have before the tower.
- The character events (`CharaEvent`) and other tables may add more, such as other characters' second Limit Bursts.

## 41. Deathlink

**Idea**: when the user's party falls in battle, send out a deathlink to the multiworld. Similarly, when a deathlink is received from the multiworld, the party falls.

**Look into**
* What happens if the player is not in a battle?
  * bank until next battle? Inflict death on all party members?
  * what happens if you enter a battle with all party members in death status?
* What happens if the player is in a cutscene or shopping?
