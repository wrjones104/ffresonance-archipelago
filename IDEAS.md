# Ideas and to-investigate

A scratch pad for ideas that are not on the test plan yet. Each one lists what we already know, from logs, dumps and the installed mods, and what to find out.

The chapter-by-chapter progression (party, vehicles, gates, Visions, Espers) is in [docs/progression.md](docs/progression.md). The logic design built on it is in [docs/logic.md](docs/logic.md). Resolved and parked ideas (1–6, 13, 14, 16–19, 21, 23, 24, 26, 27, 29, 32–39, 42–44, 48) are archived in [docs/ideas_archive.md](docs/ideas_archive.md).

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

**From a tester (2026-11-26):** with cosmetics or music in the seed, a menu in game to roll them again or change them. The Archipelago page in the main menu (archived ideas 38 and 39) could hold it.

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
- **ModSettings Lua mod (`Mods/ModSettings`, from FFR Modding Tools):** can crash the game 1 to 2 seconds after a map change when **Hint on map load** is enabled (round 77, `ac54844`). Happens with or without `FFRArchipelago`; the workaround is disabling Hint on map load or setting `ModSettings : 0` in `Mods/mods.txt`.
- **FFRS_QoL:** writes difficulty and encounter fields (`ExpRate`, `MoneyRate`, `MRPointRate`, `ap`, encounters). Mod 0.49.0's fast tick overrides its difficulty writes, and the README advises leaving its encounter rate at 1 and disabling its multiplier and encounter overrides.
- **FFR_MapMarkers and FFRBestiary:** one crash seen about 6 hours into a run after landing the airship with both active (v0.31.0 known issues / `docs/playtesting.md`); still being isolated.
- Any mod that edits the save while we skip the prologue, or that grants items, can confuse the per-save item count.

**To find out:**
- **A start-up check:** done for FFRRandomizer in mod 0.15.2. If `Mods/FFRRandomizer/enabled.txt` exists, or `mods.txt` has `FFRRandomizer : 1`, the mod logs a warning at start and shows it once when the first save loads. Other known clashes can go in the same place.
- **Shared tables:** patch them through one place. Offer a small shared helper, or agree on an order with the other mod authors.
- **A compatibility list** in the README: done (`README.md` now has a "Mod compatibility" section covering `FFRRandomizer`, `FFRS_QoL`, and `ModSettings`, kept updated as new clashes turn up).
- The other conflicts you have seen outside this project: which mods, and what happened.

## 11. Archipelago details on the save-slot cards

**Idea:** the Load and Save screens show, on each slot's card, that it is an Archipelago save: the server (host:port) and the slot name.

**Known so far:**
- The mod already knows which slots belong to the session (`slots` in `ap_state.txt`). It does not keep that for older sessions.
- The game's slot summaries are `MuchaGameSaveDataSummary` rows in `CPP_MuchaSaveDataManager.GameSaveDataSummaryMap`. The cards are probably drawn from them.
- Saves now stamp their seed tag and applied-item count into event flags (mod 0.60.0, idea 35), so linking survives restarts and Steam Cloud, while `host:port` and slot name still need a per-slot record for the Load and Save cards.

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

**Round 79 (the user asked whether to probe this now).** Token Legacy showed the stand-in Potion because its check came after the game's pop-up had closed, not because of the widget. An own pop-up shown at check time would still come after a Potion pop-up. Way 1 is the one that helps every kind of check: with an empty reward row (a chest's `Money 0`, a quest's empty `ObtainItemList`) the game shows no pop-up of its own, and the mod shows its text whenever the check comes. Its test also covers quests: empty one quest's reward row and see whether the row still runs, completes the quest and moves the counter. Build 42898077 fixes the quest case without it (arms the pop-up from the counter's value before the reward). **Probe built (round 81, build 27ed563a):** `ffrap_empty chest|shiny|quest <id>|off` makes this map's closed chests, its shinies or one quest's reward rows give nothing. Chests are kept empty through chest blanking (`G.emptyRows`); the check logic does not look at the contents, so the checks still go out. **Round 81 result:** it works. An empty chest shows the game's pop-up with "0 gil", an empty shiny and an empty quest row (Rogue Rebel) show their pop-up too, and each opens or completes as normal with its check sent. Rogue Rebel gave nothing of its own and showed complete. **Built (after round 81, updated through v0.32.0):** chests and shinies give nothing in place of 1 gil (`24aa6c4`), though the game still shows "0 gil" underneath before the mod rewrites it. Quest reward rows left empty showed "You obtained a vision!" in round 84, so since round 88 (`8b979d5`, `d1437b9`) quest rows that would be left empty keep the stand-in Potion again (`docs/side_quests.md`, section 4). Radar treasures, boss rewards, and NPC gifts also keep the stand-in Potion, and the pop-up is still the game's rewritten `WBP_DialogBox_C` (so two checks arriving at once, such as a chest right after a boss win, can still show the game's own item on the second pop-up). In round 119, a story boss win (`boss:9012`, The Hunger) logged `chest pop-up for boss:9012: no chest pop-up on screen`, so story boss item pop-ups can still miss the rewrite while the item arrives in the feed (v0.32.0 known issue, queued for v0.33.0).

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

## 22. A welcome window on an Archipelago new game

**Idea (round 37, 2026-11-08):** a dialogue window when an Archipelago new game starts: a short welcome to the mod and some tips. Planned for v0.33.0 ([docs/roadmap.md](docs/roadmap.md), milestone 1).

**Round 115:** the game's own dialog windows can likely show our text: rows of `DialogBoxInfo` in `CDT_DialogBox`, opened by tag through `CPP_BFL_Dialog` (idea 54). The user wants the window to cover the start's move.

**Round 117 (the dialog probe):** `CPP_BFL_Dialog.OpenDialog(InTag, InParent)` opens a row by its tag, with `IsDialogActive()`, `CloseDialog(InIsImmediately)` and `BindToDialogClose(InDialogTag, InDel)`. A GameplayTag cannot be made up, so the window is an existing row with its `Message` written first and put back after. `Map_FastTravel_CanNot` (`UI.Dialog.Box.Map.FastTravel.Prohibited`, an OK button, no message of its own) is the first to try. Since round 116 the start holds move input, so the window is not needed to cover the move.

**To find out:**
- Which of the game's own windows can show our text. The game's dialog rows are the first to try (idea 54), then the notices and tutorial windows (idea 8's notes on `CPP_WBP_ChatNotice` and the quest notice).
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

**v0.30.0 to v0.32.0:** all 40 bosses (story bosses, cave masters, and optional bosses) are now locations giving both a shuffled item and a Crystal Fragment (`9edc8ae`), boss capability logic is in place (idea 29, `640712a`, `862f260`), enemy/boss scaling plus MRP retention were tuned in v0.31.0 (`a336275`, `1734ad6`, `19a087b`), and v0.32.0 shipped the item pool pass (2 Ribbons, 13 enemy-only accessories, `extra_magicite`, `early_healing_vision`) and `include_aileens_forge`.

**Ideas, the strongest first:**
1. **Boss fights as checks.** 40 story, cave master, and optional bosses are done; Twelve Arms, Arena, and non-Siren Espers remain untouched.
2. **Bosses pay for growth.** Enemy and boss scaling and MRP retention are in (v0.31.0); dedicated bonus boss EXP and MRP payouts remain open.
3. **Bosses in a shuffled order.** Level sync makes any order fair. What you hold when you meet a boss is the puzzle. (Open.)
4. **Random objectives each seed.** Configurable static objectives (characters, visions, Crystal Fragments) are in (idea 24); random per-seed objective rolls remain open.
5. **Hints bought with gil,** at shops or the moogle, to give gil a use. Shops could be checks too (`shops.tsv`, idea 31). (Open.)
6. **Traps and DeathLink** for multiworld spice (ideas 20 and 41). (Open.)
7. **Party slots as items.** Start with one or two slots and find the others, if the party limit can be changed. (Open.)

## 28. Character abilities as checks

**Idea:** party member abilities (Fire, Provoke, etc.) are locked until found in the multiworld. When characters level up and would normal get one or more abilities on that level, instead we would send checks to the server.

## 30. Libra options

**Idea(s):** Users have expressed interest in a "Librasanity" option, which basically means there's a check in the multiworld for scanning each enemy. This would introduce a bunch of extra locations, which would need lots of filler to be populated (gil, consumables, magicite, etc.). To help this out, I would want to introduce some supporting stuff:
- start with all characters knowing Libra
- all characters can learn Libra, either naturally or via AP items

Along the same lines, I would also want an option for players to start with all enemies already scanned. If this option is enabled, it would need to disable Librasanity though, otherwise the player would send out hundreds of checks immediately - unless we could set it up where the game needed to "see" the enemy to trigger the check. That's probably more work, but probably doable. Eventually I think I would also want an Enemysanity option, very similar where you get a check for each time you defeat a unique enemy.

## 31. Shopsanity

**Round 71 (the user):** the merchant ships on the ocean, which the airship can visit, sell things such as Adamantite and the Ancient Tome. They could be locations that need the Airship. The game data has them as talk rows `GimEv_MerchantShip_01` to `_05` (`_Talk`, `_Buy_0N`, `_BuyAll`), found while looking at the ferry (round 67).


**Idea:** Each shop slot becomes an Archipelago location (see: Crystal Project, Cross-Code, ALttP, etc.) - you have to buy the item to trigger the send, afterwards that shop slot is removed (or replaced with its original vanilla item).

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

## 45. Quest second rewards, and stat bonuses as items

**From the user, 2026-11-19 (round 97).** A quest with two rewards gives both as Archipelago items, to make quests worth doing. Leave out the stat bonuses, unless they can be items too.

**Built (round 98, build 22b9afbc, v0.30.0 `0662c63`):** 17 quests give a second reward (8 gil, 2 an item, 7 a vision), and each is a location of its own, `quest2:<id>` (docs/side_quests.md, section 6).

**Round 106 (mod build 5f911663, shipped in v0.32.0 `c2e8b3a`):** the pop-up's two names touched (the user). The second now has 10 px of space above it.

**To find out (stat bonuses only; second rewards and pop-up spacing shipped):** what writes a character quest's stat bonus ("Attribute Bonus: Fina" in the Rewards list, an ID 0 entry). If it is a field of the reward row, a stat bonus could be an item the mod applies when it comes in. Not looked at yet.

## 46. Supporting custom vision mods

**Idea:** Many users have asked for the ability to use custom visions in the AP mod. I haven't looked into how custom visions are done in-game and what sorts of data tables they manipulate, so I don't know how feasible this is technically. We'd also need to think through how this could work functionally in the game. Without having dynamic custom locations, I'm not sure that we could support more than the base number of visions that FFRS has. I do think (and users have suggested) that we could possibly just take the user's full list of available visions (base + mods) and put them into the pool, either with amount caps (pool of 50 total visions gets truncated to 26 for the final available pool), or possibly sacrifice some filler for others. I lean towards truncating to 26, but open to exploring other options.

**Research:** I believe most custom visions are created with https://github.com/FFBE-JP-Translation/FFR-Vision-Studio, though I'm sure there are other methods. An example of a custom vision mod: https://www.nexusmods.com/finalfantasyresonance/mods/321
## 47. A PopTracker pack

**From the user and a tester, 2026-11-22.** [PopTracker](http://poptracker.github.io/) is a map-based tracker with Archipelago auto-tracking. Players like it for the overview a map gives. On the list, not a priority ([docs/roadmap.md](docs/roadmap.md), milestone 4).

**Known so far (PopTracker's PACKS.md and AUTOTRACKING.md):**
- A pack is a folder or zip: `manifest.json`, `scripts/init.lua`, JSON for items, locations, maps and layouts, and the images.
- Logic is rule strings in the locations' JSON: comma-separated codes are AND, array entries are OR, `item:3` is a count, `$func|arg` calls the pack's Lua, `@location/section` reuses another location's rule.
- Map pins are `map_locations` with x and y in the map image's pixels.
- Auto-tracking: the variant's `ap` flag, then `Archipelago:AddClearHandler` (gets slot data), `AddItemHandler` and `AddLocationHandler`. The pack maps Archipelago's ids to its own codes itself.
- Universal Tracker already rebuilds our logic from slot data (round 72), so players have a logic tracker today, without a map.

**To find out:**
- Map images: the world map, and one picture per town or dungeon, or one pin per place with its checks as sections.
- Pin positions: `data/game` has x and y for chests, shinies and radar treasures. A script can turn them into image pixels, as the location names (idea 34) use them.
- Generating the pack's locations and rules from `data.py` and the apworld's rules, so the pack does not drift from the logic. Boss rules (`boss_logic.py`) are the hard part: they count party, visions and Magicite, which suits `$func` rules.
- The options that change the location list (`include_side_quests` and the like), read from slot data in the clear handler.

**Order:** after idea 40, side quests on by default, and the last location renames, so the pack is not rebuilt each round. `data/location_names.tsv` names are filled apart from the 3 Research Center Ruins lab key card shinies (`shiny:3220:32`, `33`, `37`), which still fall back to `suggested`.

## 49. Standard or custom scaling on the Settings page

**From the user, 2026-11-22.** Bring back the custom scaling sliders of round 102, but on the Settings page next to the strength, not on a tab of their own. A toggle picks Standard or Custom. Standard shows the presets and hides the sliders. Custom shows the sliders and hides the presets. Standard is the default. Roadmap milestone 1 (v0.33.0).

**Decided (2026-11-27):** ideas 49 and 56 build together on the Settings tab. In `Standard` mode (`Custom scaling` off), Enemies and Bosses get separate On/Off switches and separate `Casual`, `Normal`, and `Expert` presets. Turning `Custom scaling` on hides the presets and shows the five enemy/boss sliders (`elevel`, `ehp`, `eatk`, `blevel`, `bpower`), seeded from the active presets.

**Known so far:**
- Round 102 (`891e70d`) had a preset slider (A, B, C, Custom) and five Custom sliders on a third tab: enemy level, enemy HP, enemy Attack, boss level, boss power. `ffrap_set elevel|ehp|eatk|blevel|bpower <percent>` set the same. The sliders worked. Round 103 (`19a087b`) took the tab out, as a curve of each tester's own would make reports hard to compare. The `battle: won` line names the preset, so a report shows when Custom was on.
- An on/off row works on the page (the encounters and scaling switches). Every radio button table in the game is in use (round 52), so the toggle is a switch row ("Custom scaling"), not a two-choice row.
- Our rows are taken off the page when it closes and added again when it opens, in reverse order so they keep their order (round 103). The page also checks the tables at each tick while it is open (round 88).
- A Custom curve is flat: one percent per slider. Standard ramps each value from party level 5 to 25 (`SEED_SCALES` in `main.lua`). The sliders could set the level-25 end, with the ramp kept.

**To find out:**
- Whether rows can be added or taken off while the page is open, so the page changes the moment the toggle flips. If not, hide the rows (`ESlateVisibility` Collapsed) or show the change at the next open, with a help line that says so.
- Whether the game's row list keeps a hidden row's focus slot, so a gamepad does not stop on a row it cannot see (idea 39 has the gamepad scroll problem).
- Where the sliders start when Custom is first turned on: the current strength's numbers.

## 50. The field character follows the party leader

**From the user and a tester, 2026-11-22. The user had this idea before, but it was not written down.** On the field the player is always Rain. With `shuffle_party_members` the starting party can be anyone, so the field character could be the party's leader.

**Known so far (from [Change field Leader](https://www.nexusmods.com/finalfantasyresonance/mods/124) on Nexus, version 1.1, read 2026-11-22):**
- It is a UE4SS Lua mod (`ChangeLeader`), with a pak (`000_FFRS_AnimTiming_P`) that fixes diagonal walk animations. F6 or holding L3 changes the field character. It is based on YeOldeTreeStump's FinaLeader script.
- It changes the field look only. Rain comes back for cutscenes and story events it detects, and the chosen character returns after them and after map changes. It has a 2-second cooldown between changes.
- A "Party Members Only (Experimental)" version cycles only the current party and follows party changes. The page says this version may still crash now and then.
- Known gaps: some characters have no ladder climb animation, and some have diagonal movement glitches.
- **Its permissions:** use of its files, changes to them, forks, and changes made with generative AI all need the author's permission first. So we may not take its code. We can find the method ourselves with our own probes, or ask the author.

**Ways to do it:**
1. Compatibility only: test our mod with its Party Members Only version and list it in the README (idea 10). In an Archipelago seed that version already follows our party. Cheap.
2. Our own: the field character is the party's leader, and the swap happens on its own (no key). This needs our own probes: what the field pawn is made from, and how the game plays as Fina in her own story parts.

**To find out:**
- Whether their mod and ours conflict. Our mod checks the pawn's class (`BP_MapUnit_Player_Field_C` on the world map) before it trusts a world-map position (round 69). If the swap changes that class, the airship position and the gate crossings could break.
- Off-line, before a probe: the player pawn Blueprints and any data table that ties a unit to a field mesh and animation set (`dump_game structs` and `assets`).
- How cutscenes find Rain. A scene that looks for Rain's actor may break if the field pawn is someone else. Their mod puts Rain back for scenes, so this risk is real.

## 51. Key items the game still gives, or never gives, at the open start

**From the user, 2026-11-23 (after round 107's Throne Room Key fix).** With `shuffle_key_items` off there is the opposite problem: no way to get the Dungeon Key, so Zoldaad Dungeon's cells never open. Look at every key item and the story triggers that give it.

**Found off-line (round 107 audit, `tools/key_audit.py`; the table is in docs/logic.md, section 8b):**
- The Dungeon Key is only a drop from the soldier in battle group 9096, whose trigger needs story 4180. With key items off, its six locations can never be checked.
- The Cabin Key is given free by the man in front of Sian's inn once the cabin door is tried. With key items on, the cabin chest opens out of logic.
- The merchant ship sells the High-Power Generator once 23 radar treasures are found. With radar treasures on, this may open tier 3 early (to check).
- The Proofs of Victory gate no location: they only open Colosseum shop stock.
- With key items off, the Throne Room Key and Cabin Key chests could be in logic behind the game's own givers, not filler only.

**Built in round 108 (mod build 4e6c553b, apworld build 937b4b93):** all of them (docs/logic.md, section 8b). The Generator needed no change. To test in game: the Cabin Key man, the Dungeon Key given in the dungeon, and the spoiler log with key items off.

**Found with it (a tester, round 108):** a quest scene ("The Tide from the Sky") visits Grandport, which made it a fast travel place with Lanzelt locked. The mod now marks every map of a locked continent not visited. Other scenes that move the player to another continent would be caught the same way.

**Round 112 (testers, v0.31.1):** Token Legacy's last step is past the Throne Room Key's door, and Errand's End follows it. Both need the key now; a quest that starts after another takes its keys. Beyond the Blue needs a party of 4. Grandport's vision Moogle flag (144, round 107) made every Moogle play Grandport's scene: its flag 145 is set too (mod build 5d54d782).

**Round 118 (the user, shipped in v0.32.0):** the key-item fixes (`1dc94ca`, `dc2aaaf`, `01982db`) shipped in v0.32.0: with key items off, the Dungeon Key is given in Zoldaad Dungeon and the cells open, and the radar goes quiet once every reachable treasure is dug. Left of this idea for v0.33.0: the two radar findings below.

**Round 117 (the user, round 108's radar check):** the radar goes quiet when its treasures are dug, but Lid says the radar stopped finding treasure while some are still to find, likely when the last treasure in the game's order is dug. And a Progressive Radar received while flying turns the radar on at once, but its treasures can be dug only after a map change. Both to look at for v0.33.0: Lid's line is likely a chat or talk row with a radar counter condition.

**Also round 108 (a player):** in the game the radar goes quiet once every treasure it can find is dug, until the next part. The mod kept it pinging, as it held the found count in the band. Now the count goes 2 past the band once the level's tiers are all found (docs/playtesting_archive.md, round 108).

## 52. A new game with no prologue (the new start)

**From a tester, round 109.** With autosave off in the game's Options, the prologue skip never ran: it waits for the first autosave, to have a slot to save into and reload from. The seed's save played the prologue and chapter 1, with Rain at level 55 and the Earth Shrine boss fight coming back over and over (docs/playtesting_archive.md, round 109). The user does not want to make players turn autosave on, and wants the Archwitch Fina part gone too.

**Found off-line:** the new game's first map is `CPP_GameSettings`'s `GameStartSettings.TransitionMapId` (10040 in `DefaultProject.ini`), and the new save is built from `DT_InitGameSaveData`'s `NewGame` row (party, units, flags, story). The opening is map 10040's startup event at story 1000. This is the new lead that archived idea 2 (the opening's input lock) waited for: with no opening, there is no lock to keep.

**Built in round 109 (mod build 6a25a245), behind `ffrap_newstart on`:** the title entry points both at the arrival before the new game begins, and puts them back once the new game is in. The rest of the skip goes into the save in place. Then the mod tries `MapTestStartByLoadSaveData` to load the map again from the save in memory, or moves the player to the arrival on foot.

**Round 109's test (the user):** the game reads both at New Game. No opening, the party and menus work, and a plain New Game after it is vanilla. The new game stands where the world map puts one (south of the Earth Shrine). `MapTestStartByLoadSaveData` loads slot 0, another game, so it is gone. Rain's armor and accessory were in the bag, not on him. The user wants the start on foot by the starting continent's town for every seed, with the airship parked there.

**Built in round 110 (mod build d0634fd8):** the player and the airship are moved to the arrival in place, and moved again once if the player is found below it. The starters wear the `NewGame` row's gear.

**Round 110's test (the user): every check passed**, with autosave off too. One nit: the Active Time Chat "Thoughtful Resolve" (ATC11) played at the start. The game's new save holds it waiting for Lasswell, who is in a new start's party from the first frame.

**Built in round 111 (mod build 2a01167a):** the chats wait for a unit not in the party until the start has marked them all played. The new start is on by default.

**Round 111's full run (the user, v0.31.1):** the start, the chats and the run to the Crystal Tower's top went through, with no crash. The user's airship came up near Zoldaad on a Dirnado start: the game spawned the actor elsewhere and wrote that place over the park when the player left the world map. Round 112 (mod build 5d54d782) moves it to the start the first time it is on the world map after it came, and round 113 parks the save there again.

**Round 118 (the user):** a seed that starts with the airship had none at the start until a map change. The game places the airship at the first map load, before the mod parks it in the save. Every start on foot is an airship landing point, so the start now points `DT_MapAirShip`'s `initSpawnPointId` (9000, no point) at the start's landing point for that first load (mod build 2a4f7fce). It works (round 119): the game placed its airship by the landing point at the first load, and the move put it at the arrival.

**Shipped in v0.32.0 (`c9588fc`):** the direct open start is live. Left: take out the old autosave prologue skip fallback (still present with `ffrap_newstart off` or before a seed is heard) once v0.32.0 playtesting settles.

## 53. Lifts and rafts after fast travel, and Mobliz Shipyard's last lift

**From the user, 2026-11-25 (round 113).** In the Tower of Mysidia, a ride up and a fast travel out left the lift at the top for good. Could it happen elsewhere? And Mobliz Shipyard's third lift still does not work.

**Built in round 113 (mod build 3b66f1dc):** a lift that keeps its stop in the save is put back at its first-visit stop while the player is on another map, in the five dungeons where that is always safe: the Tower of Mysidia, the Wind Shrine, the Water Shrine, the Gronoa Shrine and the Sanctissimus Shrine (`G.LIFT_RESETS`). `tools/lift_audit.py` reads every lift's stops and arrival rules from the levels and writes `data/game/lifts.tsv`. The tower works (round 114). To test in game: the other four after a fast travel out (docs/playtesting.md).

**Rafts (a player, round 114):** the boats in Cave of Waters and the Water Shrine stayed where they were left too. The save keeps the last raft ridden per map (`Map.lastRideRaftMap`); the mod takes that row out while the player is elsewhere (mod build 901ca04e). A survey of the rest of what keeps its place (round 114 in docs/playtesting_archive.md): switch floors and turning bridges (Cave of Waters, the Water Shrine, the Weapons Factory) and one falling floor (Kolobos Ruins) are left alone for now, as a reset would undo their puzzles. They are on the checklist.

**Kolobos Ruins' floor (the user, round 117):** the floor falls under the player in a scene (flag 111), and Rain puts it back from the far side (flag 112, "elbow grease"). A fast travel out from the far side left the way in blocked. Off the ruins' map, the mod now sets flag 112 when 111 is on, as Rain's scene does (mod build afd9cf66). The switch floors and turning bridges still pass the checklist.

**Round 118 (the user, shipped in v0.32.0):** the floor comes back, and the Water Shrine, Gronoa Shrine and Sanctissimus Shrine lifts and the switch floors and bridges all pass after a fast travel out. Lifts and rafts shipped in v0.32.0 (`c9588fc`); what is left of this idea for v0.33.0 is Mobliz Shipyard's last lift (elevator 75 on map 3060).

**Known so far about the Shipyard (rounds 58 and 59, docs/playtesting_archive.md):**
- Map 3060 has keypad lifts (`BP_MapGimmick_Floor_Elevator_Interact_002_C`) 72 to 75. 73 and 75 start switched off (`m_GimmickCondition 1`). The mod turns them on (`G.WakeShipyardElevators`).
- 73 then works with a keypad beside it. 75 is on too, but it stands at the bottom and nothing at the top calls it, so chests 1 and 3 and shards 71 and 79 stay out of reach.
- The lift's Blueprint has `CallSwitch(InArg, Direction)` and `m_IsCallSwitch`. In the level, 75's stops are not in the dump (no spline points read by the audit).
- In the story, a scene with Lid asks for switch 16 (5 + 8 + 3 = 16, docs/progression.md), and a lift goes from off to on. That scene still plays.

**The user's lead:** see what the switch 16 scene does to its lift (which rows and calls switch it on, and whether it calls the lift too), and do the same for 75.

**To find out:**
- Off-line: the switch 16 scene's talk rows (`C02_Moburizu_Switch_*`) and the switch actors in `Dng_04Dir_41_0*_GD` that target lifts (`switchData` in the save, `gimmickStateByTarget`). Which target list holds 75, if any.
- In game: `ffrap_inspect` on 75 at the top, and `ffrap_snapshot` before and after the switch 16 scene (`tools/snapdiff.py`), to see which save rows change.
- Whether a `CallSwitch` on 75 from Lua, with the player at the top, brings it up.

## 54. A start that cannot go wrong

**From the user, 2026-11-26 (round 115).** Rain froze at the start: the user walked while the new start moved him to the Town of Sian, and had to start again. Can the start load while a window is up (idea 22)? Can a new game be refused while the client is not connected? Make the opening hard to break.

**Known so far (docs/playtesting_archive.md, round 115):**
- The freeze came with the mod's second move, which moved a walking player back to the arrival. That check was for a player who fell through an island not loaded yet, but it also fires once the player walks 300 away.
- A new game stands at point 0 of the map: on the world map that is the Earth Shrine. `GameStartSettings` has only the map id.
- The game's dialogs are table rows opened by tag (`CDT_DialogBox`, `CPP_BFL_Dialog`). The mod's Lua runs on the game thread's tick, and that tick goes on while a window is open: the chest pop-up is written while the game's own pop-up is on screen. The world goes on loading too. A dialog takes the input, so the player cannot walk while it is open.
- With no client running, the mod still holds the last session's seed from the old `ap_in.txt`. The Archipelago entry then starts the last seed's start.

**Ways to do it, cheapest first:**
1. **No second move for a walking player, and no walking during the move.** Move again only when the player is below the arrival (the case it was for). Hold move input (`SetIgnoreMoveInput`, the engine's own) from the save's arrival until the player stands at the arrival on the ground, and let it go after that, on a time limit, and on leaving the game. No probe needed. If a freeze still comes, `ffrap_input` and `ffrap_input fix` tell what holds it.
2. **The client's heartbeat.** The client writes `ap_alive.txt` (one line: the time and the session) every few seconds while it is connected to the slot. The mod reads it at the title. With no live client, the entry reads "Archipelago (connect the client)", and choosing it starts no seed's start. This also ends the stale seed above. What the pre-hook turns the choice into needs a test: an unknown type, or the game's dialog (way 3) with a "connect the client" line.
3. **The welcome window over the move.** One probe for the dialog calls' parameters (`ffrap_functions CPP_BFL_Dialog CPP_DialogManager`). Then reuse a row with an OK-only choice: write our text into its `Message` while it is open and put it back after, as the Options rows are kept. GameplayTags cannot be made up, so the tag is an existing one. The window opens when the save is in, the move runs under it, and the player closes it. Way 1 stays as the guard.
4. **No move at all.** Move the world map's point 0 (`BP_MapTransitionPoint_C`, `m_PointID 0`, in `Wld_GD`) to the arrival before the game puts the player there, so the game loads the right island and places the player itself. To test: whether the game reads the point's place at that moment, and whether the mod can reach the point first (a map load hook or the first tick). Behind a test command, with the move as the fallback.

**Order:** 1 and 2 first (no probe for 1, a small client change for 2). The probes for 3 and 4 in the same round.

**Round 116 (mod build 517a874b, world build e0989726):** ways 1 and 2 are built. The second move is only for a player below the arrival, and move input is held until the player stands at the arrival (10 s at most). The client writes `ap_alive.txt` every 2 s while connected; without it the entry is labelled "New Game (Archipelago: connect the client)" and becomes Load Game. The probes are `ffrap_functions CPP_BFL_Dialog CPP_DialogManager` (way 3) and `ffrap_point0 on` (way 4). To test in game (docs/playtesting.md).

**Round 117 (the user tried round 116's build, shipped in v0.32.0):** ways 1 and 2 work and shipped in v0.32.0 (`c9588fc`). Rain could not walk until he stood at the town; one move each time. The entry read "connect the client" and opened Load Game with the client closed, and started the seed with it connected. The label changes only when the title screen is made again. Way 4 does not work: point 0 moved to the arrival before the pawn came, but the game still put Rain at the Earth Shrine, so it places a new game from its own data. The probe is taken out. Way 3's calls are known (idea 22); the window is no longer needed for the move. What is left of this idea for v0.33.0: live refresh of the label while the title screen stays open.

## 55. A stutter like a heartbeat

**From testers, 2026-11-26 (round 116).** One player had a constant stutter "like a heartbeat"; another had none. The user feels it on their laptop and not on their desktop. A player also had lag in Dragon's Maw.

**Known so far (docs/playtesting_archive.md, round 116):**
- The mod's loop runs every 0.5 s on the game thread, and the chest pop-up check every 0.1 s. A run's work all lands in one frame.
- `FindAllOf` and `FindFirstOf` go through every object in the game. The shiny scan searched every map gimmick each second; since round 116 it searches only the field items.
- Since round 116 the log has timings every 2 minutes (`perf:` lines) and each run over 25 ms; `ffrap_perf` logs them now.

**To find out:**
- Which steps and searches the timings name on a slower PC, and whether the stutter goes when they are fixed.
- What else could do it: the trace file (`ap_trace.txt`, a line per step, unbuffered), a `FindFirstOf` for an object that is not there (it goes through everything each call), or other mods.
- Whether Dragon's Maw is slow without the mod too.

**Ways to fix, once the timings say where:** keep found objects by path (as `Live` does) so searches happen only after a map load; spread the per-second work over the ticks between; run the slow scans less often away from chests.

**Round 117 (the user's desktop, 50 minutes of timings):** the main loop averaged 8 to 13 ms, and one run in four to one in ten went over 25 ms. The slow runs were the even ticks, where every step that runs one tick in two came together: the seed's extras and the continent locks (9 to 40 ms), the table patches (8 ms), the loot scan (7 ms), and every 5 s scale and settings (5 to 28 ms). The object searches were small (the busiest, `WBP_FieldFuncList2_C`, about 2 ms a second). So the time is in the steps, not the searches. **Built (mod build afd9cf66):** the extras and the patches run on odd ticks, and the extras are timed in eight parts, the locks and the level sync apart. To test: the laptop, and the next `perf:` lines to name the slow part of the extras.

**Round 118 (the user's laptop and desktop):** "better, but still noticeable, especially in towns" on the laptop; nothing felt on the desktop. The slow runs moved to the odd ticks, and the largest step on both computers was the story boss step: 7 to 26 ms on every odd tick, from a walk of every talk row to find two rows. The patches added 6 to 14 ms on the same ticks. **Built (mod build 2a4f7fce):** the story boss step finds its rows by `FindRow` and writes its battle group at a map's first pass and every 10 passes after. The patches and scale steps are timed in parts. To test: both computers' `perf:` lines.

**Round 119 (the user's desktop, shipped in v0.32.0):** 5 runs over 25 ms in 2 minutes, from 23 to 30, and the story boss step is gone from the timings. The largest step left was the quest colours' hook, tried every odd tick (about 7 ms each) until the Quests screen is first opened; it now waits for its class to load (`StaticFindObject` check, `805720b`, shipped in v0.32.0). Open in v0.32.0 playtesting (`docs/playtesting.md`): laptop and slower-PC `perf:` timings.

## 56. Separate boss scaling options

**From tester feedback, paired with idea 49 for v0.33.0 (2026-11-27):**
- Separate On/Off switches for Enemy scaling and Boss scaling on the Settings tab.
- Separate `Casual`, `Normal`, and `Expert` preset rows for Enemies and Bosses (copied from `Difficulty`) in `Standard` mode, swapping to the 5 percentage sliders (`elevel`, `ehp`, `eatk`, `blevel`, `bpower`) when `Custom scaling` is turned on.
- `game.lua` already tells boss battle groups (`G.BOSSES` and Arena `9705` to `9721`) apart from regular field enemies, so no new engine probes are needed.

## 57. Fast travel to a place a scene took the player to

**From the user, 2026-11-27 (round 117).** After The Tide from the Sky, fast travel went to Grandport with Lanzelt still locked. The airship showed grey on the Map screen, but fast travel went there. Zoldaad's capital could be travelled to after the Ayaka quest's scene, with no visit on foot.

**Known so far (docs/playtesting_archive.md, round 117):**
- Since round 108 the mod marks each map of a locked continent not visited (`bIsVisited` in `Map.perMapSaveDataMap`). The log shows Grandport marked not visited, then a fast travel to it two minutes later. So that mark is not what the Map screen's refusal reads ("a place you haven't visited yet", condition `bCheckLockedMap` in `DA_WldMapParameter`).
- The grey on the Map screen does follow the visited mark: the airship was grey because a seed that starts with it never marked it visited (fixed in round 117).
- Zoldaad Unlock had come before any Zoldaad map in the log. With the continent open, a visit made by a scene counts as in the game.

**The user's answer (round 117):** a place waits for a visit on foot, on an open continent too.

**Built (round 117, mod builds afd9cf66 and b295fb0e, shipped in v0.32.0 `ed5c027`):** maps of a locked continent are marked unknown as well as not visited, and `ffrap_visited <map> [unvisit|unknown|restore]` logs or writes a map's marks. The mod keeps the places the player stood in with the field up for two passes (about 2 s), per session, in `ap_state.txt` (`walked`). Every other place of a continent is marked unknown and not visited, as a locked continent's are; the map the player is on is left alone. A session's first pass takes the places the save has visited already, so a save from before keeps its fast travel places (a scene's visit before this build counts). The log has `fast travel: map <id> walked in`, and `fast travel: maps ... not walked in or on locked continents, marked never seen`.

**Round 118 (the user):** the walk-in rule works: `fast travel: map <id> walked in` for each new place, and existing saves kept their places. The probe ran `unvisit` but not `unknown` (the log has the usage line in its place), and what the Map screen did is not recorded.

**To find out (`docs/playtesting.md`):** with `ffrap_visited` on an open continent's town, whether the Map screen still travels there when it is only not visited, and when it is unknown. If neither stops it, the next probe is `ffrap_find Visited` and `ffrap_find Known` for the list it reads.


## 58. Universal Tracker in the client

**From the user, 2026-11-27.** Embed Universal Tracker directly inside **Final Fantasy Resonance Client** when the player has `tracker.apworld` installed, as other Archipelago custom clients do, so players get the **Tracker** tab and UT commands in one window instead of connecting two separate clients to the same slot. Planned for v0.33.0 ([docs/roadmap.md](docs/roadmap.md), milestone 1).

**Known so far (from `apworld/ff_resonance/world.py` and `client.py`):**
- `FFResonanceWorld` already supports Universal Tracker without a YAML (`ut_can_gen_without_yaml = True`, `interpret_slot_data`, `re_gen_passthrough`, and `take_slot_data`, built in round 72).
- Custom clients integrate UT by importing `TrackerGameContext` (and `TrackerCommandProcessor`, if UT commands are wanted) from `worlds.tracker.TrackerClient` inside a `try / except ImportError`, falling back to `CommonContext` and `ClientCommandProcessor` when `tracker.apworld` is not installed.
- In `apworld/ff_resonance/client.py`, `FFResonanceContext.on_package` currently does not call `super().on_package(cmd, args)` (`CommonContext.on_package` is empty, while `TrackerGameContext.on_package` drives UT's world rebuild and location updates), and `make_gui` sets `ui.base_title` on `super().make_gui()`.

**To find out:**
- The exact `worlds.tracker.TrackerClient` hooks in the current UT release (`TrackerGameContext`, `make_gui`, `run_generator` or startup tasks, and `server_auth` / `on_package` call order) against an installed `tracker.apworld`.
- Making sure `client.py` runs cleanly both with `tracker.apworld` installed (showing the **Tracker** tab and updating reachable locations live) and without it (plain `CommonContext`, no import error).
- Optional later tie-in: once `FFResonanceContext` holds UT's live `locations_available` list, the client could also write the in-logic check count to `ap_in.txt` for the in-game **Seed** tab.
