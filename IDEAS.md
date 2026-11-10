# Ideas and to-investigate

A scratch pad for ideas that are not on the test plan yet. Each one lists what we already know, from logs, dumps and the installed mods, and what to find out.

The chapter-by-chapter progression (party, vehicles, gates, Visions, Espers) is in [docs/progression.md](docs/progression.md). The logic design built on it is in [docs/logic.md](docs/logic.md).

## 1. Tablet Shards

**Idea:** Tablet Shards as their own location type, and later a MacGuffin goal ("turn in N shards"). The turn-in rewards could become locations too.

**Known so far:**
- "Tablet Shard" is item 25004. Ids at 20000 and up are kept vanilla right now (`SHUFFLE_ID_LIMIT`), so shards are neither shuffled nor locations yet.
- Shards seem to be a special shiny class, `BP_MapGimmick_FieldItem_Medal_C`:
  - Map 2015, uid 4, item 25004, in `data/shinies.tsv`.
  - Medal spots 13 and 14 on map 3180 in the round 2 log.
  - Map 2020, uid 5, item 25004, found in round 5.
- They are found mostly in towns and dungeons, not on the world map. The progression overview says there are 99, across almost every town, dungeon and overworld segment.
- There is a place in the game where you turn shards in for incremental rewards.

**Round 49:** the MacGuffin goal is in, as "receive N shards" (world 0.7.0). Turning shards in at the game's own NPC is still an idea.

**From the game data dump (2026-11-06):** all 99 Tablet Shards were located in `data/game/field_items.tsv` (`BP_MapGimmick_FieldItem_Medal_C`, item 25004), confirming the exact locations and counts.

**To find out:**
- How many shards exist, and where. Visiting maps fills `seen.tsv`, and a level-file read would give the full list.
- How the turn-in works: an NPC, shop or event table. What gives the rewards, and how the game remembers which tiers are claimed (a flag, a counter, quest progress?).
- Whether a shard count can be read and set directly (`FindInventory(25004)` / `AddInventory`).
- Apworld design:
  - Shards become progression items.
  - Each turn-in tier becomes a location gated on owning N shards.
  - A new goal option: "turn in all shards" or "collect N shards".

## 2. Skip the prologue

**Idea:** start an Archipelago game after the prologue.

**Known so far:**
- The story counter is `saveData.Progress.Progress[1]`. FFRSLib's `ffrs_story_set` accepts 1020 to 8050, and 1020 is "Leave Grandshelt Castle" (chapter 1).
- Setting the counter alone does not replay what the skipped story did. FFRSLib warns that flags set by later story stay set when going backwards, so going forwards presumably leaves the prologue's flags unset.
- The tools to fill the gap exist: story flags (`SetFlag`), party (`AddUnit`), visions, items, gil, and map travel (`ffrs_travel` / `LoadMapId`).

- The prologue is a tutorial on its own maps (round 5 log: maps 10040 and 10041, story 1000 to 1010), with a temporary Lv. 55 Dark Fina. Chapter 1 begins with Rain and Lasswell in Grandshelt.
- FFRSLib notes that the level cap is 99 only while story flag 1 is on, and 15 without it. That is one example of state the skip has to get right.
- FFRSLib's travel (`ffrs_travel <map> <slot> x y z`) writes the map and arrival point into the save, saves to a slot and reloads the field from it. Its story knob (`ffrs_story_set`) says "save and reload to apply". So the skip can work the same way: change the save, save to a slot, reload.
- The game ships its own debug menu (`ffrs_debug_menu`), and its code has a debug progress editor (`CPP_BFL_DBG_FlagSaveData` `SetProgressList` / `GetProgressList`). If the menu has a chapter jump, it sets things up the way the developers expect.

**Plan (2026-11-05).** Steps 1 to 3 are yours in game; step 4 is the build.

0. **Stop-gap for testing now:** copy your base save for each seed.
   - Connect the client, load the base save, run `ffrs_save <free slot>` (FFRSLib), then type `/bind` in the client.
   - The seed now lives in the new slot, and the base save stays clean.
   - The order matters. If you bind first, the base save's slot is linked too.
1. **What the prologue changes: save snapshots.** Mod 0.5.1's `ffrap_snapshot <name>` writes every field of the loaded save to `snap_<name>.tsv`, and `tools/snapdiff.py` compares two of them.
   1. Start a new game. As soon as the console works in the first battlefield map, run `ffrap_snapshot start`.
   2. After the Iron Giant fight, at the first moment you control Rain, run `ffrap_snapshot after_giant`. This one is optional: it separates the prologue's changes from the start of chapter 1.
   3. At the point where your base save is, run `ffrap_snapshot ch1`. Then save the game to a free slot.
   4. Load your base save and run `ffrap_snapshot base`. Comparing it with `ch1` shows which differences are only noise.
   5. Send the four `snap_*.tsv` files and `UE4SS.log`. Also say which map and spot chapter 1 begins at, and whether a cutscene plays when you arrive.
2. **The game's debug menu.** Run `ffrs_debug_menu` at the title screen and in game, and take a screenshot of each page. Look for a chapter select, a story or scenario jump, a flag or progress editor, or "new game from ...".
3. **A skip by hand.** On a fresh new game, try the simple version with FFRSLib's tools, using the base save's values from `snap_base.tsv` (`live.story`, `live.map`, `live.pawn`):
   - `ffrs_story_set <story>`
   - `ffrs_travel <map> <free slot> <x> <y> <z>`. This overwrites that slot.

   Then note what is wrong: Dark Fina still in the party, Rain or Lasswell missing, a level cap of 15, a cutscene that repeats, or a tutorial that pops up.
4. **The build.** On a new game linked to an Archipelago session, the mod applies the prologue's changes from the diff: story values, flags, party, visions and items. Then it sets the arrival map and point, saves to a slot and reloads. The apworld gets a `skip_prologue` option (on by default), sent in slot data.

**Step 1 results (2026-11-05, mod 0.5.1).** Three snapshots:
- `start`: new game, map 10040, story 1005. It was taken about 30 s in, so it misses what happens between 1000 and 1005.
- `ch1`: the file is named `snap_after_giant.tsv`. Map 3001, story 1030, standing in front of the Earth Shrine. This is where "the game" begins, after about 2 minutes of Rain cutscenes and walking.
- `base`: the old base save (slot 2).

The new game autosaved to slot 0 at story 1005, and the mod linked that slot.

What the prologue changes (`start` → `ch1`), all inside the save:

| Field | start | ch1 | Notes |
|---|---|---|---|
| `Progress.Progress[0]` | 1005 | 1030 | the story counter |
| `Progress.eventFlag` | | on: 14 15 16 18 19 22 23 26 27 30 32 33 106 108 110 124 125 1164 1225 1226; off: 1 8 | 0-based. Flag 1 is probably FFRSLib's "level cap 99" flag, which the prologue's Lv. 55 Fina needs |
| `Party.partyList` | [1006] | [1001, 1002] | Dark Fina out; Rain and Lasswell in |
| `unitParameterList[0]`, `[1]` `.JoinStatus` | 1 | 0 | Rain and Lasswell join, so 0 seems to mean "in the party" |
| `unitParameterList[5]` | Lv. 55 Fina | reset | JoinStatus 0 → 2, Experience → 0, HP 200, MP 70, weapon 10600, no armor, accessories or skills |
| `unitParameterList[0].baseParameterList[5]` | 0 | 3 | not known yet |
| `inventory` | Fina's gear 10699, 11301, 12029 | 10100, 11000 ×2, 12000 ×2, 10200 | the list counts equipped gear |
| `inventoryProcedure.itemDatas` | 3 entries | 4 entries | the same items; possibly the "new item" marks |
| `unitGuest.HitPoint`, `.MagicPoint` | 0 | 9999 | a guest unit (Bahamut?) |
| `Player.WinNum` | 0 | 3 | battles won |
| `Map.mapId`, `.unitLocation`, `.unitDirection` | 10040 | 3001, (-5775, 0, -197.85), 2 | the arrival point |
| `Map.mapGimmick` | none | entries for 2014 and 3001 | contents not read by 0.5.1 |
| `Map.perMapSaveDataMap` | 10040 | 10040, 5010, 2013, 20000, 3001 | holds `bIsVisited` (FFRBestiary reads it); contents not read by 0.5.1 |
| `unitList[n].analyzedElments` | | a few elements on | Libra-style scan data; not needed |

`ch1` → `base` differs only in the player's position, eventFlag 1165 and 1228 (on), and one more scan entry. So the base save is the same point in the story.

Mod 0.5.1 wrote struct values inside maps (`mapGimmick`, `perMapSaveDataMap`, `colosseumProgress`) as memory addresses. UE4SS's Lua can't ask a map for its value type, so 0.5.2 matches each value to one of the game's save struct types by field names. The `live.saveStructs` line says how many types it had to choose from. Snapdiff now leaves out changes where only the address moved, and it prints Japanese keys.

**Step 1, second run (2026-11-05, mod 0.5.2).** Snapshots `new` (story 1000, map 10040), `ch1` and `base`.
- `new` → `ch1` matches the first run, with two corrections:
  - eventFlag 105 also turns on.
  - Flags 1 and 8 are already off at story 1000. They turn on between 1000 and 1005 and off again by 1030, so they belong to the prologue only and the skip leaves them alone.
- `ch1` → `base`: only the position, flags 1165 and 1228, and one scan entry, as before.
- `live.saveStructs` was 0, so the map contents are still unread. `FindAllOf("ScriptStruct")` returns nothing in game. The game's executable names the types (`SaveData_PerMap`, `SaveData_MapGimmick`, `SaveData_Colosseum_ProgressSaveData`, ...), so mod 0.5.3 looks each one up by path with `StaticFindObject`.

**The skip recipe so far.** Apply it on a new game at story 1000, then save and reload:

| Field | Set to |
|---|---|
| `Progress.Progress[0]` | 1030 |
| `Progress.eventFlag` | on: 14 15 16 18 19 22 23 26 27 30 32 33 105 106 108 110 124 125 1164 1225 1226 |
| `Party.partyList` | [1001, 1002] |
| `unitParameterList[0]`, `[1]` | JoinStatus 0. Also `[0].baseParameterList[5]` = 3 |
| `unitParameterList[5]` (Fina) | JoinStatus 2, Experience 0, HP 200, MP 70, weapon 10600, armor -1, no accessories, no skills |
| `inventory` | 10699 → 10100, 11301 → 11000 ×2, 12029 → 12000 ×2, add 10200 ×1 |
| `inventoryProcedure.itemDatas` | the same four items (maybe only the "new item" marks) |
| `unitGuest` | HitPoint 9999, MagicPoint 9999 |
| `Player.WinNum` | 3 (only a counter) |
| `Map` | mapId 3001, unitLocation (-5775, 0, -197.85), unitDirection 2 |
| `Map.perMapSaveDataMap` | add 5010, 2013, 20000, 3001. Contents to come from 0.5.3 |
| `Map.mapGimmick` | add 2014, 3001. Contents to come from 0.5.3 |

**Step 2 and the third run (2026-11-05, mod 0.5.3).**
- **The debug menu is empty.** The Home page lists 0 items (「0個の項目」), and the side panel only shows build, PC, input and rendering information. The `CPP_DM_*` classes (event shortcuts, the debug save manager) are not in the game at all, so the shipping build has no chapter jump.
- **The map contents can be read now.** `live.saveStructs` was 56. (The snapshot was of the base save, which matches `ch1` apart from the player's position, two flags and one scan entry.)
  - `perMapSaveDataMap{map}` holds three booleans: `bIsKnown`, `bIsVisited` and `bIsCleared`. Maps 10040, 5010, 2013, 20000 and 3001 are known and visited, and none is cleared.
  - `mapGimmick{map}` is the game's own chest record for each map: `treasureBox.treasureBoxList[]` with `ID`, `UniqueID`, `IsOpen`, `isDisableTrap` and `IsUnlock`. It also holds `gimmickState`, `switchData` and `switchSequenceData`, which are empty here.
    - Map 3001 has three chests, all closed: ID 0 (uid 23), ID 1 (uid 24) and ID -1 (uid 80). IDs 0 and 1 are our locations `chest:3001:0` and `chest:3001:1`. The game makes these rows when the map loads, so the skip does not need them.
    - Map 2014 has nine chests. Four have ID -1 (uids 5, 7, 9, 10) and are open and unlocked; the five with IDs 0, 1, 3, 4 and 5 are closed. None of map 2014's chests are in our location table. To find out: whether the story opens the four ID -1 rows, and whether map 2014 has chests we should add.
- **`ffrap_functions`** listed 236 functions from 14 classes. The ones the skip needs are below.

**The build, field by field.** Each line uses the game's own function where there is one:

| Recipe | Call |
|---|---|
| Story counter → 1030 | Write `Progress.Progress[0]` directly, as FFRSLib's `ffrs_story_set` does. There is no setter, only `CPP_BFL_DBG_FlagSaveData.SetProgressList` |
| Event flags on | `CPP_BFL_SaveDataProgress.SetFlag(index, true)` |
| Party [1001, 1002] | `CPP_BFL_SaveDataParty.SetUnitToParty(0, 1001)`, `SetUnitToParty(1, 1002)` |
| Join status | `CPP_BFL_SaveDataUnit.SetJoinStatus(1001, 0)`, `(1002, 0)`, `(1006, 2)` |
| Fina's reset | `UnEquipmentAll(1006)`, `SetEquipmentId(1006, 10600, 0)`, `SetSaveDataUnitExperience(1006, 0)`, `SetSaveDataUnitHitPoint(1006, 200)`, `SetSaveDataUnitMagicPoint(1006, 70)`. There is no call that clears her 7 active skills, so empty `activeSkillIdList` directly |
| Rain's `baseParameterList[5]` 0 → 3 | `AddBaseParameter(1001, 5, 3)`, if parameter type 5 is that index. Its meaning is unknown |
| Inventory | `CPP_BFL_SaveDataInventory.SetInventoryItem(id, n)`: 10100 ×1, 10200 ×1, 11000 ×2, 12000 ×2. Then 10699, 11301 and 12029 (Fina's old gear) to 0 |
| Guest unit | `SetGuestUnitHitPointAndMagicPoint(9999, 9999)` |
| Battles won | `CPP_BFL_SaveDataPlayer.SetWinNum(3)` |
| Visited maps | `CPP_BFL_SaveData_PerMap.AddKnownMap(m)` and `AddVisitedMap(m)` for 5010, 2013, 20000 and 3001 |
| Map 2014's open chests | `CPP_BFL_SaveDataMap.SetTreasureBox(2014, -1, uid, true)` and `UnlockTreasureBox` for uids 5, 7, 9 and 10, if the story opens them |
| Arrival | `CPP_BFL_SaveDataMap.SetMapIdAndMapUnitLocation(3001, (-5775, 0, -197.85), 2)` |
| Save and reload | `CPP_BFL_SaveData.SaveGameData(slot)` on `GetAutoSaveSlotIndex()` (slot 0, which a new game overwrites anyway), then `LoadGameData(slot)` or FFRSLib's travel reload |

Left out: `inventoryProcedure` (probably the "new item" marks) and the scan data.

**When it runs.** On a new game that the mod links to a session whose slot data has `skip_prologue` on: as soon as the save settles at story 1000 on map 10040, during the opening movie. Before that, a console command `ffrap_skip` can test the same code on any new game.

**Built: `ffrap_skip [slot]` (mod 0.6.0).** The recipe above, as a console command for testing:
- `ffrap_skip` changes the loaded save and saves nothing, so a snapshot can check it against `ch1`. It works only up to story 1005, so on a new game only.
- `ffrap_skip <slot>` also writes the save to that slot and reloads from it, with the same two calls as FFRSLib's `ffrs_travel` (`SaveGameData`, then `MapTestStartByChoiceSlotLoadSaveData`). Run after a plain `ffrap_skip` on the same save, it only saves and reloads.
- Fields are written straight into the save object, because the save object is what `SaveGameData` writes. The game's calls are used for the inventory (`SetInventoryItem`) and the visited maps (`AddKnownMap`, `AddVisitedMap`).
- Each step logs `skip: ok ...` or `skip: FAIL ...`, and a failed step does not stop the rest. One line checks whether the game's `GetFlag(14)` agrees with array element 14.
- With a linked session, the slot is linked before the reload, so the reloaded game is the session's.
- Left out on purpose: map 2014's four open chest rows, `inventoryProcedure` and the scan data.

**Step 5: test the skip in game.** Do this without the client connected, so that no seed is linked.
1. Copy `FFRArchipelago/Scripts` over the installed mod. The log should say `version 0.6.0 loaded`.
2. Start a new game. As soon as the console works (during the opening movie is fine), run `ffrap_skip`. In `UE4SS.log`, every `skip:` line should start with `ok`.
3. Run `ffrap_snapshot skip`.
4. Run `ffrap_skip 0`. This overwrites the autosave slot and reloads from it. If the reload does not start, go to the title screen and load the autosave.
5. Look around:
   - Do you stand in front of the Earth Shrine, with Rain and Lasswell in the party?
   - Do the menus open (party, equipment, items, visions, map)? Does the quest log show the Earth Shrine?
   - Walk into the shrine. Does the story carry on, and does any cutscene from the prologue play again?
   - Does Fina show up anywhere she should not?
6. Run `ffrap_snapshot skip_loaded`.
7. Send `snap_skip.tsv`, `snap_skip_loaded.tsv` and `UE4SS.log`, plus what you saw. I compare both snapshots with `ch1`.

**Step 5 results (round 8, 2026-11-05, mod 0.6.0).** Run with a seed connected, so the new game linked itself.
- Every `skip:` step logged `ok`, and the game's `GetFlag(14)` agrees with array element 14, so the numbering matches.
- The reload started on its own. After it, the story, quest log, party and inventory were all right.
- **The map was wrong:** the reload put the player back on the prologue map (10040). The opening scene kept running after the skip. At 11:42:25 (14 s after the skip, the point where a new game goes from story 1000 to 1005) the game autosaved, and an autosave writes the player's real position into the save. `snap_skip` was taken before `ffrap_skip 0` and already shows map 10040 at the new-game spawn.
- The same opening event turned flags 1 and 8 on again. Flag 1 is FFRSLib's "level cap 99" flag, so this matters too.
- `snap_skip_loaded` → `ch1` otherwise differs only in the order of the inventory, the "new item" marks, the scan data, and the chest rows that maps 2014 and 3001 create when they load.

**Fix (mod 0.6.1).** `ffrap_skip <slot>` applies the whole skip again right before it saves, which is safe because every step sets an absolute value. After saving it checks the save's map. If `SaveGameData` itself wrote the real position, it says so and does not reload. The success message names the map and flag 1 after the save.

For the automatic skip, this means it should save and reload in the same moment it applies the skip, before the opening scene gets to its first event.

**Retest (mod 0.6.1).** Same as step 5, with the seed connected or not:
1. Copy `FFRArchipelago/Scripts` over the installed mod. The log should say `version 0.6.1 loaded`.
2. Start a new game and run `ffrap_skip 0` straight away, with no plain `ffrap_skip` first. (Round 9: wait until you can move Fina. Mod 0.6.2 refuses before that.)
3. The log should show `skip:` lines, then `saved to slot 0 (map 3001, flag 1 false), reloading`.
4. Check that you stand in front of the Earth Shrine. Walk into the shrine and see whether the story carries on.
5. Run `ffrap_snapshot skip_loaded` and send it with the log.

**Round 9 results (2026-11-05, mod 0.6.1).** The arrival works. `SaveGameData` keeps the arrival point (the log said `map 3001, flag 1 false`), and the reload put the player in front of the Earth Shrine.
- **Skip during the opening movie (story 1000):** the game loaded at the shrine with no menus and no movement, so the movie's input lock outlives the reload.
- **Skip once Fina can move (story 1005, just after the game's first autosave):** everything came up right: party, movement, menus.
- Mod 0.6.2 refuses `ffrap_skip` before story 1005, with a message that says to wait until you can move.

**The automatic skip, from this.** On a linked new game with `skip_prologue` on:
1. Wait for story 1005, which is when the player first controls Fina.
2. Wait for the game's first autosave after that. The mod already sees it as the save's timestamp changing, and it shows the scene has finished saving.
3. Wait a moment more, then apply, save and reload in one go. Applying again just before saving (0.6.1) covers anything the opening scene changes in between.

Still to decide: whether to show a message first ("Skipping the prologue…"), and what to do if the player opts out.

**Second run of round 9: a new game while the session already has a game.** The session was linked to slot 0, the first run's skipped game. A second new game was paused, as designed. Its autosave then overwrote slot 0 ("slot 0 now holds another game and is no longer linked"), and the session was left with no save at all. The skip on the paused game worked, but the reloaded game stayed paused. Linking it would be right only if it also gets every item the session has handed out. That again needs the per-save item index (README, open question 5), done in mod 0.7.0. Linking the second new game is now safe, and a candidate for the automatic skip.

**Save linking, found on the way (mod 0.5.4).**
- A new game can carry the timestamp of the autosave slot it is about to overwrite. In the second run, a new game showed up as linked slot 0. A save at story 1000 or lower now always counts as a new game.
- A new game autosaves into slot 0 and overwrites whatever autosave is there. An Archipelago game that lives only in the autosave slot is lost when you start a new game, so keep it in a manual slot too.
- `/bind` keeps the applied-item count. A save bound in the middle of a seed does not get the items applied before. This is open question 5 in the README (a per-save item index). The skip makes a new save for each seed, so it should come together with that fix.

**Still to find out:**
- What the prologue changes outside the save object. The reload in step 4 rebuilds what the game derives from the save at load time, but not anything that is never saved.
- Which slot the skip should save to. It must not overwrite a save the player cares about.

**The input lock, parked (round 38, 2026-11-08):** a skip during the opening movie still leaves no menus or movement. The controller's switches, the input manager's enabled state and its mapping contexts all read the same in a locked game and a normal one, and every reset we tried did nothing (rounds 36 to 38). The cost of leaving it is about 10 seconds per new game. Come back only with a new lead.

## 3. Non-story ("open world") mode

**Idea:** jump the story to a late point once (for example after the airship), so the world is open, and gate progress with Archipelago items instead of story events. Keep boss fights as locations if possible. The full story is long for an Archipelago run.

**Round 30 (2026-11-06): this is now the main direction.** Players on the Archipelago Discord ask mostly for open world. The design draft, with what the game data says about the story counter, the airship, enemy levels and the cleared state (story 9000), is [docs/open_world.md](docs/open_world.md).

**Decided in rounds 31 and 32:**
- Starting state: setting story to 7090 and transitioning to Crystal Tower (map 3280) fires an event advancing story to 8000, spawning the airship and opening the Crystal Tower.
- The airship is free from the start; no airship item is required.
- Continents are gated by landing restrictions using native `BP_MapNonLandingArea_C` boxes.
- Enemy scaling rewrites `DT_UnitParameter` rows using calibrated curves with `attack`, `magic`, `hp`, and `follow` party tracking.

**Known so far:**
- After the airship most of the world is open, except places that need other story events.
- Continents as unlock items fit Archipelago well:
  - Grandshelt, Lan (02), Kol (03), Dirnado, Olderion, Zoldaad, Mysidia, Gronoa and Pharm.
  - The Crystal Tower is the goal.
  - Chest rows and shinies already carry their region, so location groups exist.
- Story gates read `{progress:N}` and `{flag:N}` conditions. These appear on shinies (`VisibleCondition`) and in `DT_MainScenario`.
- Bosses: FFRRandomizer's probe hooks `CPP_MapManager:Encount`, whose battle entry carries `battleGroupId`, `battleEventId` and `isEvent`. The randomizer already tells boss and event fights apart in the battle tables. So a battle can be started from a table entry, and a win could be detected.

**To find out:**
- Which story counter value and flags give an open world without breaking towns, NPCs or the airship. Which areas stay locked, and by which conditions.
- How to lock a continent when the story does not: block travel, warp the player back, or change map transition data.
- Bosses without their story event: can a boss fight be started on its own (a battle group plus a stage), and can a win be recorded as a check? Field bosses (map symbols) may be easier than cutscene bosses.
- Which story-only rewards (party members, visions, key items) must become Archipelago items so nothing is lost by skipping the story.

## 4. Vehicles: story event or separate unlock?

**Question:** are the Chocobo and the Airship unlocked by a story event, or by separate flags that could be flipped (or items that could be granted) on their own?

**Known so far:**
- The item table has unlock items that look like vehicle and upgrade gates:
  - 30002 "Choboco Saddle" (sic) and 30011 "Chocobo Saddle-Bike", both artifacts.
  - 29520 "Magitek Airship Passkey", a key item.
  - Radar upgrades 27006 Magi-tenna, 27007 Resonance Stone and 27008 High-Power Generator.
  - Colosseum proofs 29000–29003. The Gaia Hammer may be tied to the Fledgling proof.
- FFRS_QoL's item spawner leaves out key items (type 2) and artifacts (type 4). Its comment says they "unlock story features", with the chocobo saddle as the example. So owning the item may be the gate.
- The story gates we have seen read `{progress:N}` and `{flag:N}`. A vehicle could check either: the item, a flag, or the story counter.

**Round 5 results:**
- **Chocobo: item-gated.** `ffrap_grant item 30002` (Choboco Saddle) on a story-1130 save made the chocobo rideable. So "Chocobo" can be a plain Archipelago progression item: grant 30002.
- **29520 Magitek Airship Passkey is cosmetic.** It changes how the airship looks and does not unlock it. You had one already, from a pre-registration reward. So the airship unlock is still unknown, and probably a story flag or the story counter.
- **30011 Chocobo Saddle-Bike did nothing visible.** Its description says it turns a mounted chocobo into a motorcycle. It may be unused, or it may need a condition, for example granting it while riding, or after a map change.

**Open world update (round 31):** the airship is free from the start once initialized at story 7090/8000. Continents are locked against landing instead. A separate airship unlock flag or item is therefore not needed for open world.

**To find out:**
1. **Saddle-Bike.** Try 30011 again while riding a chocobo, and after a map change.
2. **What this means for the apworld:**
   - "Chocobo" (item 30002) is a progression item gating Kolobos and Felicitas.
   - Continents become gated by landing passes or region items, not an airship item.
   - Radar tiers gate world-map treasures.

## 5. Key items and gates from the item table

**Known so far:** these ids are in `data/game/items.tsv`, and they match gates in [docs/progression.md](docs/progression.md):

| Item | Id | Gate |
|---|---|---|
| White Jade Stone | 20005 | Holy, which clears the Bog of No Return (Gronoa west, Odin) |
| Level 1, 2, 3 Lab Key Cards | 20009–20011 | Research Center Ruins |
| Tunnel Key | 20008 | probably the Zoldaad tunnels |
| Dungeon Key, Throne Room Key | 20019, 20021 | Zoldaad Castle |
| Ruby Fragment | 20030 | Carbuncle (3 needed) |
| Broken Sword Hilt, Blade | 20031, 20032 | Odin (Iron Splitter) |
| Magitek Armor Key | 29500 | unknown |
| Archwitch's Grimoire | 29510 | unknown |
| Tablet Shard | 25004 | Tablet Shard turn-in (idea 1) |

**To find out:**
- Which of these does the game check by item, rather than by a story flag set at the same time?
- Each one checked by item could become an Archipelago progression item. That is the start of real logic, even with the story kept.

## 6. An Archipelago entry on the title screen

**Idea (2026-11-05):**
- **Archipelago entry:** add an "Archipelago" entry to the title menu next to New Game. Plain New Game stays vanilla, so a player can play without Archipelago and without removing mods.
- **Title branding:** show the mod's name and version, and a logo, on the title screen.
- **Automatic skip:** choosing the Archipelago entry starts a new game, links it to the seed and skips the prologue with no command.

**Known so far:**
- **FFRSLib already adds a menu entry, in the System Menu.** It appends a tag to `DA_SystemMenu.DisplayEntryList`, adds a matching `EntryPropertyMap` row with the display name, and hooks `CPP_VM_SystemMenu:ExecuteEntryEvent` to run its own action when that tag is chosen (FFRSLib `main.lua`, "System Menu entry"). The game draws the entry like its own.
- **The title menu looks built the same way.** The executable names `CPP_DA_Title` (`GetTitleDA`, `TitleEntryDisplay`, `TitleEntryProperty`, `TitleEntryBehavior`, `ETitleEntryBehavior`, `ETitleFunctionType`), `CPP_VM_Title`, `CPP_TitleController`, `CPP_TitleTaskMain`, `UI.Layout.Title` and the delegate `Delegate.Title.List.Decide`. So the plan is FFRSLib's: copy the New Game entry under our own tag, and hook the choice.
- **The new game itself is `CPP_Task_NewGame`.** If our entry runs the same behavior as New Game, the hook only needs to set an "Archipelago new game" flag first. The mod then links that game to the seed even if the session already has a save, and starts the skip.
- **Why a skip during the movie lost menus and movement (round 9):** the executable names `BeforeOpeningInputMappingContext`, `AfterOpeningInputMappingContext`, `IsOpeningProcess`, `OnOpening` and `OnOpeningEvent`. The opening most likely runs with a "before opening" control scheme and switches to the normal one when it ends. Our reload during the movie skipped that switch.

**The intro movie: skip it, or wait it out.** Two ways:
1. **Wait it out (works today).** The movie and the first scene play, the game autosaves at story 1005, and then the mod runs the skip. Rounds 9 and 10 showed this comes up clean. The cost is about 15 seconds of movie the player watches each time.
2. **Skip the movie.** Start the skip at once, and then end the opening ourselves: call whatever ends the opening process, or switch to the after-opening control scheme. If that works, the player goes from the title straight to the Earth Shrine. This needs the probes below first.

Plan: build option 1 first, because it is known to work. Then try option 2 as an improvement, and fall back to option 1 when it fails.

**The logo and text.**
- **Name and version:** a text block on the title widget is the easy part. Find the title layout (`UI.Layout.Title`) and add a `TextBlock`, or change an existing one.
- **The logo:** UE can make a texture from an image file at run time (`KismetRenderingLibrary.ImportFileAsTexture2D`). The mod can ship a PNG and show it in an `Image` widget. The Archipelago logo is free to use with credit for unpaid projects. The credit goes in the README and in DISCLOSURE.md's credits.

**Round 11 probes (mod 0.7.2, 2026-11-05):**
- **The title view model** (`VM_Title_C`, a Blueprint on `CPP_VM_Title`) has `GetDisplayEntryList`, `ExecuteEntry(InType)`, `GetTitleDA` and `IsEnableBGMovie`. Its data asset is `/Game/UI/Title/Data/DA_Title.DA_Title`. The background movie is `/Game/Movies/Event/C01/MV_Title`.
- **The data asset** (`CPP_DA_Title`) holds `EntryPropertyMap` with keys 0 to 4 and `DifficultyPropertyMap` with keys 0 to 2. It also holds `EntryDecideEvent` (`Delegate.Title.List.Decide`), `QuitGameDialog`, the title BGM (`BGM_PP_MAINTHEME_02`) and switches for the opening animation and the movie.
- **The entry types** come from the executable: `ETitleFunctionType` is Continue 0, LoadGame 1, NewGame 2, Option 3, QuitGame 4 (and Max 5). `ETitleEntryBehavior` is None, PushWidget or OpenDialog. The row structs are `TitleEntryProperty`, `TitleEntryDisplay` and `TitleEntryBehavior`.
- **`CPP_TitleController`** is an actor in the title map with `InputMenu` and nothing else of its own.
- **`ffrap_find`:**
  - It crashed the game at the title screen but worked in game.
  - `Opening` found only `UNIT_PARAMETER_CALC_DATA.openingProgressId`.
  - `NewGame` found nothing, because 0.7.2 matched function and field names only, not class names (`CPP_Task_NewGame`), and skipped Blueprint classes. The opening's names (`IsOpeningProcess`, `BeforeOpeningInputMappingContext`) are probably on a Blueprint class.
  - `InputMapping` found `CPP_InputManager.RegisterInputMappingContext`, `CPP_DA_MUCHA_INPUT.pInputMappingContextList` and `CPP_PlayerMappableKeysSubsystem.GetInputMappingContextList`: the places a control scheme gets switched.

**Round 12 (mod 0.7.3):** the entry works.
- `ffrap_title add` added row 5. It showed (as a second "New Game", at the bottom) once the menu was made again. Choosing it called `ExecuteEntry(5)`, and the hook turned that into a normal New Game.
- The row struct `TitleEntryProperty` holds `EntryName` (the label, an FText), `DisplayProperty` (`bCheckSaveData`, `bCheckPlatform`, `DisplayPlatformMap`) and `SystemActionTag` (`None` for New Game).
- `IsOpeningProcess` is a function on several widgets (finger cursor, menu titles, a combo box): their own open animation. So the before/after-opening idea above was a false lead, and skipping the movie outright is still unsolved. `CPP_Task_NewGame` is the new-game task's class.

**Built (mod 0.8.0):**
- **At start-up** (and every 3 seconds after), the mod loads `DA_Title` when it is not loaded, adds row 5 labelled "Archipelago" (`EntryName` set with `FText`), and hooks `ExecuteEntry`. Loading the asset early is how FFRSLib gets its System Menu entry into the first menu.
- **Choosing Archipelago** marks the next new game. That game links to the seed even when the seed has other saves: with per-save item counts, several saves for one seed are safe. If it autosaved before the client connected, its slot is linked when the session starts.
- **Plain New Game stays vanilla** once the entry is in place: it no longer links itself.
- **The automatic skip:** on an Archipelago game, once the story is at 1005 and the game has autosaved (so the save has a slot), it waits 2 seconds and runs the same skip as `ffrap_skip <that slot>`. It makes one try per game. If that fails, the message says to run `ffrap_skip`.
- The entry is at the bottom of the list.

**Round 13:** all of the above worked in game.

**Built (mod 0.8.1, from the round 13 screenshot):**
- **The label** is "New Game (Archipelago)".
- **The order:** the menu lists rows in the map's own order, and a map keeps the order rows were added in only when it starts empty. So the mod:
  1. Reads every row (label text, the save-data and platform checks, the platform list, the action tag).
  2. Checks that the map takes an empty row.
  3. Empties the map.
  4. Adds the rows back as Continue, Load Game, New Game, New Game (Archipelago), Options, Quit Game.
  5. Fills in each row's fields.

  If the map cannot be emptied, the spare row is taken out again and the entry stays at the bottom. The labels are written back as the text they show, so they stay in the current language, but they do not follow a language change until the next start.
- **The mod's name and version on the title:** the game's version ("1.0.1.0", bottom left) is a TextBlock. The mod writes "FFRArchipelago <version>" in front of it on a line of its own, so it shows above the version if the block grows upwards. The title widget is made again each time the title shows, so this is checked every 3 seconds while not in a game.
- **The logo** is saved as `FFRArchipelago/Assets/archipelago_logo.png` (from the Archipelago community; free with credit for unpaid projects). Showing it needs an `Image` widget made at run time, with the texture loaded from the file (`KismetRenderingLibrary.ImportFileAsTexture2D`). That is the next step after the text.

**Round 14:** the order and the version line worked. The version block is right-justified, so "1.0.1.0" moved right under our longer line. 0.8.2 sets it to left-justified and logs the block's layout (its slot, parent panel and that panel's children) once per run.

**Where the logo goes:** small, about two text lines high, just above "FFRArchipelago <version>" in the bottom-left corner. To its left there is not enough room: the corner text starts about 47 px from the screen's edge.
- It sits next to the text it belongs to and stays clear of the game's artwork and the menu (which the game makes again).
- **Round 15's layout line:** the version text is in an `Overlay` (`Overlay_UI`, in `WBP_TitleLayout_C`).
- **How 0.8.3's `ffrap_logo` places it:**
  1. It makes an `Image` in the title layout's widget tree (`StaticConstructObject`, with a fresh name each time).
  2. It loads the PNG with `KismetRenderingLibrary.ImportFileAsTexture2D` and sets it with `SetBrushFromTexture` and `SetDesiredSizeOverride` (39 x 40).
  3. It adds the image with `Overlay_UI:AddChildToOverlay`, gives it the version text's alignment, and adds the text's height plus 6 px to the bottom padding, so it sits above the text.
- **Round 16:** it worked, above the text (padding 60,0,50,97, two lines 43.2 px high).
- **0.8.4:** it is one line high, at the end of the first line ("FFRArchipelago <version>"). The block's width is that line's width, and the logo is centred on that line. It runs by itself at the title, one check after the version line, so the block has been laid out with both lines.

**Still open:**
- **Skipping the movie outright:** find what the opening holds the player's input with. `CPP_Task_NewGame` is the place to start (`ffrap_inspect` while a new game is starting).
  - Round 35: the user wants New Game (Archipelago) to go from the opening movie straight to the open world, with no Fina segment. The recording has the movie (with Skip), the opening event (with Skip), a Move/Sprint tutorial pop-up, then about 3 s of Fina before the skip.
  - Round 36 probes (mod 0.17.0): `ffrap_skip 0 force` makes the lock on purpose. `ffrap_input` logs the player controller's input switches in the movie, the locked game and a normal game, and `ffrap_input fix` tries the engine's resets. `ffrap_inspect CPP_InputManager <label>` and `ffrap_inspect CPP_Task_NewGame movie` keep each state in its own file.
  - Round 36: the controller's move and look switches were false in the movie, the locked game and a normal game, so the lock is not there. `CPP_InputManager` is a world subsystem, made new on each map, with `IsEnableInput`, `EnableInput`, `DisableInput`, `GetCurrentInputModeDebugString`, `GetAllIMCStackList` and `ReregistrationCurrentMappingContext`. `CPP_Task_NewGame` had no live instance during the movie. Mod 0.18.0's `ffrap_input` reads the manager, and `fix` calls its `EnableInput` and `ReregistrationCurrentMappingContext` (round 37).
- **Our own on-screen text:** messages go through ModSettings' Toast panel, so without that mod a player sees nothing. Two ways:
  - **Use one of the game's own notices.** The executable names `CPP_VM_QuestNotice` and `CPP_DA_QuestNotice` (quest pop-ups), `CPP_WBP_ChatNotice` (`UI.Layout.Chat.Notice`) and `CPP_VM_BattleResult_Notification`. If one of them takes plain text, our messages look like the game's.
  - **Make our own widget:** a `TextBlock` (and later the logo) on a widget we create. This is the same work as the logo.

  Round 14 probes:
  - `CPP_VM_QuestNotice` (the "new quest" banner, `WBP_QuestNotice` in the field layout) holds `NoticeData.NoticeTitle` (a text), `NoticeQuestData` (a quest's name, subtitle and so on) and `bDisplayNotice`. It has `ExecuteNotics(bool)`, `PlayNoticeSound` and `CloseNotice`. 0.8.2's `ffrap_notice <text>` sets the title and the quest name, then calls `ExecuteNotics(true)`.
  - `CPP_BFL_Chat.Notice` is a call in the chat library (`CPP_ChatSubsystem` keeps the notice widget, and the save keeps a `NoticeQueue`). Its parameters come with round 15's `ffrap_functions`.
  - If neither takes our text, we make our own widget (as for the logo).
  - **Round 16:** `ffrap_notice` showed nothing, so the quest banner is out. The plan is our own item feed (idea 14).

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

## 13. Archipelago text in the chest pop-up

**Idea:** a chest that is an Archipelago location gives 1 gil, so the game's pop-up says "You obtained the following: 1" with a gil icon (round 15 recording). It should say what was found, and for whom: "Found Rod of Focus for Jones".

**Known so far:**
- The client knows the item and the player once the server answers the check. `LocationInfo` scouting can tell it before the chest is opened.
- The pop-up is the game's item-get dialog. It shows the chest row's item and count, which blanking set to gil 1.

**Plan (2026-11-05, next after the item feed):**
1. **The client** scouts the slot's locations once at connect (`LocationScouts`, `create_as_hint` 0, so no hints are made), and writes one line per location to `ap_in.txt`: `scout <location key> <item name> <player name> <flags>`. The flags give progression, useful or trap.
2. **The mod** keeps those by location key. While a chest's pop-up is up, it rewrites the pop-up's text. Your own item reads "Rod of Focus"; another player's reads "Ether for Alice". The gil icon and the "1" are hidden or replaced.
3. Received items still come to the feed as now, so a batch never means a pile of pop-ups.

**To find out:**
- Which widget draws the pop-up, and which of its texts and images hold the item. 0.10.0 logs the panels around the "obtained" text by itself, the first time a chest check is reported.
  - **Round 24:** nothing was found. The item line, "(gil icon) 1", is text with an icon in it, which is a `RichTextBlock`, and only TextBlocks were searched.
  - **0.10.1** searches both, and tries on each chest (15 s) until it has found it once in a run.
  - **Round 25 found it.** The chest pop-up is the game's general dialog box, `WBP_DialogBox_C`, shown in the dialog layer (`WBP_DialogLayout_C` in `WBP_OverAllLayout_C`). Inside its window:
    - `VerticalBox_0` holds `Text_Message`, a `CommonRichTextBlock` with "You obtained the following:", and `Overlay_Custom`, the dialog's custom content. The "(gil icon) 1" item line is most likely drawn in `Overlay_Custom`.
    - The chain up from the text: `VerticalBox_0`, `SizeBox_2`, `Overlay_141`, `Window_Content` (a NamedSlot of `WBP_Cmn_Window_C`), then `WBP_DialogBox_C`.
  - **Still to find:** what is inside `Overlay_Custom`, the item line's widgets. A probe that lists its children, with their text, finds it. Then either:
    - write the Archipelago item into the item line's text and hide the gil icon, or
    - write it into `Text_Message` ("You found Rod of Focus for Jones") and hide `Overlay_Custom`.

**Built (mod 0.11.0, world 0.1.4):**
- **The client** sends `LocationScouts` for the slot's locations once per session (`create_as_hint` 0, so no hints are made). From the `LocationInfo` answer it writes `scout <location key> <item> <player> <flags> <own>` lines to `ap_in.txt`. A reconnect to the same session finds them in the file and does not ask again.
- **The mod** keeps the scouts by location key. When it reports a scouted chest's check, it looks over a few ticks for an on-screen rich text holding "obtained" (the pop-up's `Text_Message`). It sets the text with `SetText`:
  - your own item: "You obtained the following:" plus the item's name;
  - another player's: "You found the following for <player>:" plus the item's name.

  It collapses the `Overlay_Custom` beside it (the gil line). The dialog box is shared with other pop-ups, so the line's visibility is put back once the message is off screen.
- **Limits:**
  - The pop-up is found by the English word "obtained".
  - The text can change a moment after the pop-up appears, because chests are scanned every second.
  - The chest still gives its 1 gil.
  - Progression, useful and trap items look the same; the flags are in the scout line for later, for colours.

**Round 26:** it worked in a 4-player multiworld, but the text changed 0.5 to 1.5 s after the pop-up came up.

**0.11.1, the fast check:**
- The dialog box is made once and used again, so the mod keeps its message widget once found.
- Ten times a second, a cheap check asks only that widget whether a chest pop-up has just come up. When one has, the chests in the map are scanned at once and the pop-up is rewritten in the same pass, within about 0.1 s.
- The first pop-up of a session still takes the slower path (a search of all rich text), because the widget is not known yet.
- **Round 27:** fast, and no stutter. But chests opened again after reloading an older save kept "1 gil": only a chest's first report asked for the pop-up text. Other Archipelago games show the item at pickup whether or not the server already has the check, and that is the rule here too.
- **0.11.2:** each map visit keeps the chests it has seen closed. One of those that is later seen open was opened in front of the player, so its pop-up is rewritten, whether its check is new or not. A first report still asks too, for a chest opened before the map's first scan.
- **If 0.1 s is still visible:** hook the call that sets the message text (`RichTextBlock:SetText`, if the dialog calls it through a UFunction, as `ExecuteEntry` is called) and rewrite it in the same frame. That would need a guard against the hook seeing our own `SetText`.
- Whether the text can be changed while the pop-up is up (the feed showed that field writes before a widget is drawn are safe; this is a widget already drawn, so `SetText` it is).

## 14. An item feed on the HUD

**Idea (2026-11-05):** show items sent and received in a small list at the side of the screen, the way TUNIC and Hollow Knight do: the last 5 or so, each fading out after a few seconds. The player should see what arrives from other worlds without watching the Archipelago client, which in a full-screen game they won't.

**Weighed against the other ways (your notes):**
- **The chest pop-up for every received item:** too jarring while exploring. Twenty items after logging in would mean twenty pop-ups. Keep the pop-up text (idea 13) for your own chests only.
- **The quest banner:** round 16 showed it cannot be given our text.
- **The Archipelago client:** it always shows everything, so it stays the backup. But players won't watch it in a full-screen game.
- **ModSettings' Toast:** this is what shows "Received ..." today. Until the feed exists, the README says the messages need it.

**Plan:**
- **The widget:** a vertical box of text lines, added to the field HUD the same way the logo was added to the title: made in the HUD layout's widget tree and added to one of its panels. `ffrap_layout` (0.8.4) finds which panel, from the quest tracker or the minimap.
- **Lines:**
  - "Received Potion from Bob" (or "Found Potion" for your own).
  - "Sent Ether to Alice".
  - Each line stays about 5 seconds, then fades. Five lines at most. When more arrive at once: "and 15 more".
- **Sent items:** the client sees them in the server's `PrintJSON` messages (`ItemSend`, where we are the sender). It writes `feed <text>` lines to `ap_in.txt` for those, alongside the item lines the mod already turns into "Received ...".
- **Fallback:** if the feed cannot be made (a game update moves the HUD), messages go to ModSettings' Toast as now, or only to the log.

**Round 17:** `ffrap_layout` found the field HUD's overlay: `WBP_FieldLayout_C`'s `Overlay_66`, holding `WBP_MiniMapLayout`, `WBP_FieldFuncList2` (the key list), `WBP_FieldQuestLayout` (the quest tracker) and `WBP_FieldName`. In the fullest HUDs (an enlarged minimap, a long quest list, the key list with Mount Chocobo and Active Time Chat) the bottom right stays empty.

**Built (mod 0.9.0):**
- **Where:** a `VerticalBox` added to that overlay (found through the key list's parent), aligned right and bottom with 48 px right and 96 px bottom padding. It is made in the field layout's widget tree, the way the title logo is.
- **Lines:** a `TextBlock` per line, in the key guide's font (`WBP_KeyGuide_C.Text_Name.Font`) at size 20, white with a dark shadow, right-justified. Five at most, each shown 6 seconds and then faded over 1.5 seconds.
- **When the HUD is made again** (a load or a map change), a new box is made in the new overlay.
- **What goes there:** every message while in a game. Received items get a line each ("Received Potion from Bob"). The client already labels other players' items "from <sender>" and writes "Sent <item> to <player>".
- **Waiting:** messages that come while the HUD is not there (loading, a battle) wait in a queue of up to 20. More than five show as the last four and "and N more".
- **Off the field, or with `ffrap_feed off`:** ModSettings' Toast, as before.

**Round 18:** 0.9.0 crashed the game on Continue, Load Game and New Game, each time just after the first message following the load ("Archipelago is paused"). That was the feed's first box on the field HUD. The title logo is made the same way and works, so the difference is one of these:
- the field HUD (made while the map loads) versus the title layout,
- the `VerticalBox` and `TextBlock` classes versus `Image`,
- the styling (the key guide's `CommonTextBlock` font struct passed to `SetFont`, the `FSlateColor` from a Lua table).

**0.9.1:** the feed is off by default. `ffrap_feed test` logs each step before it runs, and `test plain` leaves out the styling, so round 19 can tell which call it is.

**Round 19:** 0.9.1 still crashed, because the feed was still on: 0.9.0 had saved `feed 1` by itself, and 0.9.1 read it as on. The items that arrived during the opening movie waited for the HUD and were shown at story 1005, and the game crashed then. 0.9.2 uses a new key (`itemfeed`, written only by `ffrap_feed on|off`) and logs the feed's steps every time.

**Round 20:** the plain test worked; the styled one crashed twice at `style: copy the key guide's font`, which is `tb:SetFont(guide.Text_Name.Font)`. Passing an `FSlateFontInfo` (or an `FSlateColor`) from Lua to a function loses the struct's engine-only parts. A lesson for all UI work here: write a widget's fields before it goes on screen; never hand a font or Slate colour struct to a setter. 0.9.3 does that: the font object, typeface, size, shadow colour and justification are field writes on the new line, before it is added to the box. The text keeps the default white.

**Round 21:** no crash, but no lines showed, though every step reported `line done`. There were two causes:
- **Alignment:** the alignment enum is Fill 0, Left/Top 1, Center 2, Right/Bottom 3, and 0.9.0 to 0.9.3 used 2 for right (centre).
- **Font:** the key guide's `CommonTextBlock` may carry no font object of its own (its style supplies one when it is drawn), and an empty font object draws nothing.

The "Back" prompt that menus and the chest pop-up show at the bottom right also needs room.

**0.9.4:**
- Right is 3.
- The font object is copied only when the key guide has one (the step logs its name).
- The feed sits 140 px up.
- `ffrap_feed check` logs the engine's view of the box and lines.

**Round 22:** `ffrap_feed check` showed the overlay the feed used was `0x0, visible false`.
- **The cause:** `FindFirstOf` had found a copy of the key list that is never drawn (a widget Blueprint's template), so the feed and its lines lived in a HUD nobody sees. The key guide font came back empty for the same reason.
- **A lesson for all UI work here:** pick the instance that is on screen (`IsVisible()`), not the first one found.

**0.9.5:**
- The feed takes the first key list and key guide that are on screen, and only counts an overlay that is on screen.
- Messages that wait 10 seconds for a HUD on screen go to ModSettings' Toast, so none are lost from the screen.

**Round 23: it works.**
- Lines show at the bottom right in the game's `SystemText` font.
- A chest's line waits until its pop-up is closed, so it never meets the "Back" prompt.
- You prefer lines that fade (unlike TUNIC and Hollow Knight, which keep the last few on screen), but a bit longer and with more space between them.

**0.10.0:**
- On by default.
- Each line is shown 10 seconds, then fades over 2.
- 6 px under each line.
- The `feed step:` logging only runs during `ffrap_feed test`.

**Round 24:** feels right. A pop-up held 10 s sent its items to the Toast, so in 0.10.1 the Toast fallback only applies until the feed has shown its first line in a run. After that, messages wait for the HUD however long a pop-up or menu is up.

**Still to tune:** the size, the place, colours (Archipelago's item colours for progression, useful and trap items need the item flags from the client), and whether the time on screen feels right.

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

## 17. Airship landing restrictions for continent gating

**Idea:** Change or restrict where the airship can land to gate continents and regions in open-world mode. Currently in-game, if a spot is unlandable, the airship's shadow turns red. Could use or hook this check to prevent landing on specific continents until their respective items/passes are acquired.

**Known so far:**
- The airship already performs a continuous landing validity check beneath its position; hovering over invalid terrain (water, steep mountains, dense forest, or restricted zones) turns the shadow red and disables the landing action.
- Open-world mode (Idea 3) and vehicles (Idea 4) rely on continents as unlockable items (e.g. Grandshelt, Dirnado, Olderion, etc.), but an unrestricted airship would normally bypass continental borders.
- Vehicle physics/controllers and map data (`MAP_DATA`, world map collision/sub-levels) handle the movement and landing raycast/trace.

**To find out:**
- Which function or component performs the landing trace/check (e.g. in the airship actor/pawn, vehicle movement component, or map manager).
- Can that landing query be hooked via UE4SS to force a landing refusal (shadow turns red, landing button disabled) if the player is over a continent or region whose corresponding Archipelago item has not yet been unlocked?
- How continental boundaries or regions are defined on the world map (coordinate bounding boxes, surface/material tags, or distinct sub-levels/volumes).

**From the game data dump (2026-11-06).** The world map has 81 `BP_MapAirShipLandingPoint_C` actors, in `data/game/gimmicks.tsv`. Each has an `m_Id` (a map or point id, such as 2002 for Grandport) and a Japanese description. None has a condition of its own, so the game decides elsewhere which ones are open.

**Found (round 32, 2026-11-07): the no-landing boxes.** The world map also has 111 `BP_MapNonLandingArea_C` actors: a box with an `m_Condition` string. While the condition holds (or when it is empty), the airship cannot land in the box. Before story 5020, one box of half-size 2400 x 6000 keeps the airship off Mysidia. So the game already gates a continent this way, and this idea is now the plan for continent locks (decided in round 31: the airship is free, continents are locked by landing). Details and rough continent positions: docs/open_world.md, section 4. Round 32 probes it with `ffrap_noland`.
- The landing point ids start with the island's number: 1xxx Grandshelt, 2xxx Lanzelt, 3xxx Kolobos, 4xxx Dirnado, 5xxx Olderion, 6xxx Zoldaad, 7xxx Mysidia, 8xxx Gronoa, 9xxx Pharm, 10004 the Crystal Tower. 10xxx are optional caves and Legend shrines.

**Round 37 (2026-11-08):** the shadow is placed by a sphere trace, and the airship keeps a list of actors for that trace to ignore (`CPP_MapUnit_AirShip.m_ShadowDecalSphareTraceActorsToIgnore`). Changing the box's channels 3 and 4 did not obviously bring the shadow back. Round 38 adds our boxes to the list. The hoped-for result is the shadow on the ground, red, with landing still blocked.

**Round 38 (2026-11-08): that is what happened.** The game lists its 111 boxes the same way. A box on the list looks and works like one of the game's own, and destroying it restores landing at once. So a continent lock needs no change to the game's landing check: a box per continent, listed for the shadow, destroyed when the item arrives. Still to learn (round 39): whether the listing lasts through boarding, and whether the box lasts through a map change.

**Round 40 (2026-11-08):** the listing lasts through boarding, and the box does not last through a map change. Mod 0.22.0 builds the locks on that (`ffrap_lock`, `docs/open_world.md`, section 4).

**Round 33 (2026-11-08):** changing a box's condition works, but only after the airship lands and takes off again. A new box reads its condition when it starts. The game's Pharm story box is one landing spot (about 950 x 600 units), so locking it does not lock Pharm. A spawned box hides the airship's shadow. Details: docs/open_world.md, section 4. Round 34 looks for a way to apply a change at once.

**Round 32 (2026-11-07):** a box spawned at the airship's height, 3000 up and down, lifted the airship over it and broke the camera, and the airship could still land on it. So the box's collision counts as ground for the airship. The game's own boxes sit on the ground (the Mysidia box: centre height 393, 700 up and down). The Blueprint has no script; the C++ class `CPP_MapNonLandingArea` reads the box and the condition. Mod 0.15.0 puts boxes at the ground height and adds `ffrap_noland lock mysidia`, which tests a changed condition on the game's own box.

## 18. In-game menu for on-the-fly settings and modifiers

**Idea:** Introduce our own in-game menu option with on-the-fly customizable settings, such as EXP, Gil (GP), and MRP (Magic/Resonance Points) modifiers, encounter rate adjustments (e.g. 0x / 0.5x / 1x / 2x / 4x), and Archipelago client status.

**Known so far:**
- FFRSLib successfully adds custom menu options to the System Menu by appending tags to `DA_SystemMenu.DisplayEntryList`, registering rows in `EntryPropertyMap`, and hooking `CPP_VM_SystemMenu:ExecuteEntryEvent`.
- We successfully added a custom entry to the Title Menu (`DA_Title`, `VM_Title_C`, `ExecuteEntry`) in mod 0.8.0.
- Encounter checks and battle reward calculations route through distinct engine functions/classes (e.g. `CPP_MapManager:Encount`, battle calculation / reward distribution functions).

**To find out:**
- How best to display the configuration UI: whether to build a custom widget layout (similar to the item feed / dialog overlay) or reuse the game's existing Option/Settings UI widgets (sliders, toggles, list pickers).
- Where battle rewards (EXP, Gil, MRP/AP) are tallied and awarded at battle end, and whether a multiplier hook can safely scale rewards without breaking progression caps or desyncing saves.
- Where the field encounter step counter or rate calculation lives (e.g. in `CPP_MapManager` or player pawn state) and how to cleanly scale or suppress encounters on the fly.

**Round 49: this is where enemy scaling goes.** The user moved it out of the yaml. The menu should have sliders for the scaling (level percent, range, HP, attack, magic, bosses), the EXP, gil and MRP rates, and the encounter rate. The default until then is in `SEED_SCALE` in `main.lua`. 75% is a baseline only: low-level enemies need it, but it may be too easy later. A slider lets a player change it as the game goes on.

**Found off-line (round 49):**
- `DT_GameDifficultyParam` has one row per difficulty, with `ExpRate`, `MoneyRate` and `MRPointRate`, and also `EnemyHpRate`, `EnemyBreakRate`, `EnemyAgilityRate`, `DamageTakenRate` and `DamageGivenRate`. Writing the row in use may give EXP, gil and MRP sliders with no hook on the rewards. To find out: whether the game reads the row at each battle, and whether a rate over 1.5 works.
- Encounter gear already exists: 12102 prevents encounters, 12066 halves them, 12067 raises them, 12001 doubles EXP and 12059 doubles MRP. A player can already turn encounters off, if they find the item.
- **FFRS_QoL already has most of these sliders** (round 49, read from the user's install). Its moghub menu has encounters on/off (`doMovementEncount` in the map tables, walking encounters only), an encounter rate, and EXP, gil and MRP multipliers. The multipliers write `ExpRate`, `MoneyRate` and `MRPointRate` in `DT_GameDifficultyParam`, and its defaults are EXP x2 and gil x2. So our menu may only need the scaling sliders, and can leave the rest to FFRS_QoL, or read its settings.
- **The game's Options screen is data-driven (round 49).** `DT_Option_Root` lists the tabs (Gameplay, Graphics, Keyboard, Gamepad, Sound), each pointing at a table of rows such as `DT_OP_GameSetting`. A row has a `Type` (`Slider`, `RadioButton`, `ComboBox`, `ResetButton`), a `DisplayText` and an `EntryTag` (`Delegate.UI.System.Option.Root.GameSetting.Difficulty`). Camera sensitivity and the sound volumes are sliders. So our settings could be rows on the Gameplay tab, in the game's own style, if the screen draws a row with a new tag and its value can be read or hooked. To find out with a probe first.
- **Round 50 decisions (user):** our mod owns EXP, gil and MRP rates and the encounter settings, and the conflict with FFRS_QoL is documented. Scaling is on or off only, with the numbers we tune together; sliders for it would let a player undo bosses as a gate. Mod 0.38.0 has the settings behind `ffrap_set` (in `settings.txt`, written only when the player sets one) and `ffrap_menu probe` for the Options screen.
- **Round 50: the probe's two rows showed at the end of the Gameplay tab,** labelled as ours, with no crash. Next is values. Found off-line: the game saves each row's value as a float under its `EntryTag`, in `CPP_MuchaOptionSaveData.m_EntrySaveDataList` (`OPTION_SAVEDATA_SETTING { Value, IsDisplay, Type }`). A slider has `SliderInfo { MinValue, MaxValue, DefaultValue }`; a switch is a radio-button index into `DT_OP_RadioButton_OnOff` (On 0, Off 1). So mod 0.39.0's `ffrap_menu add` puts six rows in (EXP, gil and MRP rates 1 to 10, encounters on or off, encounter rate 1 to 5, scaling on or off), each with a tag of its own, and reads their values back from that map. The tags are not registered gameplay tags; whether the screen and the save accept them is what round 51 shows.
- **Round 51: our rows showed and could be changed and applied, but the values never reached us** (no `settings: from the Options screen` line; EXP at 10 gave normal EXP). So the option save has no entry under our tags, or the mod reads a different object. Mod 0.39.1's `ffrap_menu dump` lists every `CPP_MuchaOptionSaveData` and its entries, and the open screen's pending changes (`CPP_VM_Option.ChangingOptionSetting`).
- **Round 52: the dump showed where the values went.** While Options was open, `CPP_VM_Option.ChangingOptionSetting` held our six tags with the values set (`FFRAP_Exp=10.0`, `FFRAP_EncounterRate=2.0`). After Apply it was empty, and the option save (one object, 97 entries) had none of ours. So the game updates only the entries the save already has, and drops a pending change with no entry. Mod 0.39.2 adds an entry per tag to the option save when the rows go in, seeded from the current settings. The game writes its option save to disk, so the entries should stay.
- **Round 53: the menu works.** With the entries seeded, the rows open with the current settings, a change applies at once (`settings: from the Options screen: ... exp 10.0`), and the values were kept across sessions. Mod 0.40.0 adds the rows by itself on each save load.
- **ModSettings (the toolkit's F10 panel) is a cooked Blueprint** with fixed contents, so another mod cannot add options to it from Lua. MogHub (which FFRS_QoL has a page for) is not installed.
- **FFRS_QoL also writes `ap` in `DT_BattleGroup`** (its `APMultiplier`), the field our MRP scaling writes. It writes when its settings change or the table loads again. Our rescale then takes its value as the original, so nothing breaks, but our MRP scaling is gone until the party's level next changes. Idea 10 is about such conflicts.

## 19. A random starting party

**Idea:** a yaml option for the starting party: 1 to 4 members, picked at random from the party members (Rain, Lasswell, Fina, Lid, Nichol, Jake, Sakura). It must not break story mode. The members not in the starting party become Archipelago items.

**From the game data dump (round 30, 2026-11-06):**
- **The story's conditions never test the party.** Every condition string in the game's tables is one of `{flag:}` (2043), `{progress:}` (1419), `{item:}` (295), `{colosseum:}` (130), `{transferItem:}` (64), `{unitLevel:}` (48) or `{colosseum_ClearCount:}` (4). None is about who has joined.
- **The story sets the roster itself, in talk events.** Each talk event row has a `ChangeUnitJoinStatusList` (unit id, `eUnitJoinStatus`) and an `OverwriteBattleParty` (a fixed party for one battle). The status values are 0 Join, 1 NotJoin, 2 Leave, 3 TemporalLeave and 4 Lost. The events that use them:

| Event | Change |
|---|---|
| C01_002_01 (end of the prologue) | Rain and Lasswell join, Archwitch Fina (1006) NotJoin |
| C01_022_01 | Fina (1003) joins |
| C02_204_01 | Lid (1004) joins |
| C03_306_01 | Nichol (1005) joins |
| C03_312_01, C03_314_B_01 | Lasswell and Nichol join (again) |
| C03_320_01 | Fina leaves, Archwitch Fina joins |
| C03_328_03 | Archwitch Fina leaves, Fina joins |
| C04_416_01 | Jake (1007) joins |
| C04_421_01, C04_422_02 | Lasswell leaves for a while (TemporalLeave), then joins again |
| C04_435_01 | a battle with Lid alone (`OverwriteBattleParty` [1004]) |
| C05_504_01 | Sakura (1008) joins |
| C05_513 to C05_540 | Fina and Archwitch Fina swap again |
| C06_607_01, C06_608_01 | Fina joins |
| C06_623_01, C06_624_01, C08_819_04 | battles with Rain alone (`OverwriteBattleParty` [1001]) |

**What that means:**
- A member who joined early simply "joins" again at their story event. That is harmless (round 30 tests it with the party-member items).
- Nothing after the prologue makes Rain join. A starting party without Rain would have him only as an Archipelago item. Lasswell joins again in chapter 3.
- The story still makes members leave (Fina in chapters 3 and 5, Lasswell in chapter 4) and fights some battles with one fixed member. What `OverwriteBattleParty` does when that member has not joined is unknown. Rain alone is the risky case, so Rain may have to stay in every starting party for now.

**Open world fits this better (round 30).** In open world the story no longer runs, so nothing makes members leave or fights with a fixed party. A random starting party is then simple.

**The build:** the prologue skip already writes the party (`Party.partyList`) and each unit's `JoinStatus`. A `starting_party_size` option (1 to 4) and a seed-chosen list in slot data would make the skip write those members instead of Rain and Lasswell. The apworld would then put the other party members in the pool.

**To find out:**
- What level and gear a member has when they join before the story's own join (round 30 shows this with Fina, Lid, Nichol, Jake and Sakura).
- What a story battle with `OverwriteBattleParty` does when that member has not joined.
- Whether the party menu lets you swap in a member who joined the roster but not the active party.

**Round 32 (2026-11-07):** members given by `ffrap_grant unit` work: they go into the active party when there is room, and into the roster when it is full, and you can swap them in. They join at their own story levels: Lid 11, Nichol 19, Archwitch Fina 3, Fina 6, next to a level 3 Rain. For open world, a member should probably join at the party's level (or its average). This also matters for enemy scaling, because the band follows the party's average level: Lid and Nichol joining moved it from 2 to 7.

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

## 23. Shinies and vision crystals as real checks

**Asked for (round 45, 2026-11-09): the next priority once the broken things are fixed.**

**Shinies:** mod 0.29.0 blanks the reward on the actor (`m_ItemId`, `m_ItemNum`, `m_Money`), as chests are blanked. The 99 Tablet Shards became locations in world 0.6.0, at the user's request (`include_tablet_shards`). 6 shinies stay vanilla: 2 Magicite Shards and 4 key items.

**Vision crystals:** the user wants to skip the summoning scene and the questions. Mod 0.29.0 does this for the 16 sanctum crystals (`include_crystals`), and round 47 confirmed it works. The other 10 visions come from sidequests and one boss.

**Story bosses as map encounters:** Siren's fight is a story event, so she is an item for now. Story bosses could be fights on the map later.

## 24. The Crystal Tower as the goal, behind objectives

**Asked for (round 49, 2026-11-09):** block the Crystal Tower, and open it with objectives such as "defeat X espers", "defeat X bosses" or "collect X visions". The AP goal is then to beat the final boss. The Tablet Shard goal is a stopgap until this works.

**To find out:**
- Whether the final boss can still be fought from an open world start, and whether a win can be seen.
- How to block the tower. It has a landing point and an exit, so it needs a lock like the continents.
- How to show the objectives in game. The item feed could count them, as it counts shards.

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

**Ideas, the strongest first:**
1. **Boss fights as checks.** Start with the Twelve Arms, strong enemies and Arena: about 80 fights that are already self-contained.
2. **Bosses pay for growth.** A large MRP and EXP reward from each boss, so a player who skips encounters is not behind.
3. **Bosses in a shuffled order.** Level sync makes any order fair. What you hold when you meet a boss is the puzzle.
4. **Random objectives each seed** (idea 24), so seeds ask for different things.
5. **Hints bought with gil,** at shops or the moogle, to give gil a use. Shops could be checks too (`shops.tsv`).
6. **Traps and DeathLink** for multiworld spice (idea 20).
7. **Party slots as items.** Start with one or two slots and find the others, if the party limit can be changed.

## 26. Artifacts from Archipelago

**Asked (round 49, the user's scratchpad):** artifacts arrive from Archipelago but do not seem to work. Do they need turning on, and are they a working feature in the vanilla game?

**Found off-line (round 49):**
- They are a vanilla feature. `DT_ArtifactItemData` has 19 rows (items 30000 to 30018), each with an effect (`EffectValueList`) and `isInitialActive`. Only a few start active, such as the Chocobo Saddle. Exodus (30001, "Escape always succeeds") and the Tome of Sages (30000, +20% EXP) start inactive.
- The main menu has an on/off switch per artifact (`WBP_ArtifactToggle`, `WBP_ArtifactToggleEntry`, under `UI/MainMenu/Artifact`), and the item screen's data names some artifacts by tag. The watcher saw `CPP_MapManager:OnOpenMainMenu_CheckArtifactCondition` and `OnArtifactActiveUpdate` run when the menu opened.
- So an artifact most likely has to be switched on in the menu after it arrives. Not yet seen in play. If there is no switch in the menu, the next step is to look for a feature flag (`EnableFlagIdData`) for the artifact screen, like the ones the open world start sets for the other menus.
- **The user has no artifact option in the menu.** No main menu scene is an artifact screen: the switch is part of the Items screen (`WBP_SelectItemEntry.SyncArtifactActivation`, `WBP_ItemLayout` asks `IsActivateArtifact`), and `DA_ItemCategory` has an Artifacts tab (`UI.Common.Item.Category.Artifact`). No feature flag gates it. **The likely cause is the save:** artifacts live in `artifactList` (`CPP_MuchaGameSaveData`, id -> `SaveData_Artifact { IsActive }`), apart from the bag, and our grant used `AddInventory`, which only fills the bag (round 48's log: "item 30001 x1: ok (held 0 -> 1)"). Mod 0.37.1 adds every artifact in the bag to `artifactList` after each grant and on each save load, so a save that already holds some is fixed too.
- **Round 50: there is no artifact screen, and the bag already holds some on a new game.** On a new game, before any item, the sync found 30000 (Tome of Sages), 30004 (Sorcerer's Cape), 30010 (Bandit Cuff Links), 30013 and 30018 in the bag: bonus items, which is why the user had two Cuff Links. The Items screen's tabs (`WBP_InventoryCategoryTab`: All, Consumables, Weapons, Armor, Accessories, Valuables) have no Artifacts tab, though its text exists (`ST_UI_ItemMenu.CategoryArtifact`, `ST_UI_MainMenu.MainMenuTitleArtifactContents`). Only two artifacts have an on/off behaviour in `DA_UI_ItemLayout`: 29520 (airship skin) and 29500 (saddle-bike). So the artifact screen looks unfinished or cut. Mod 0.39.0 adds `ffrap_artifact <id> on|off`, to find out whether the list's `IsActive` drives an effect. If it does, the switches can go in our Options rows.
- **Round 51: the game's own artifact switches are on two DLC key items.** The user found the Magitek Airship Passkey (29520) in the key items tab with an OFF/ON switch. `DA_UI_ItemLayout.ItemBehaviorMap` (item id -> `UIItemBehavior`) gives it `StateOnOff` (`EUIItemBehavior` 3) with `ExecuteEvent` `Artifact.AirshipSkin`; the Magitek Armor Key (29500) has the same for `Artifact.ChocoboSaddleBike`. `DA_MapManager.ArtifactIdTable` maps only those two tags to ids (29520, 29500). No other artifact has an entry, so none has a switch, and artifacts show only in the Items screen's All tab. **Turning the Cuff Links on in the save list worked, but off did not take the chest icons away, even after a map change.** The mini-map keeps its own `ArtifactActiveMap`, so the state likely has to change through the switch. Mod 0.39.1's `ffrap_artifact menu` adds a `StateOnOff` entry for every artifact, keyed by its own id with its own tag. If the switch shows and works in the All tab, that is the fix; if not, the user's idea is next: key items like the passkey, one per artifact.
- **Round 52: no switch showed.** The entries went in (19), but the artifacts in the All tab stayed greyed out, while the passkey shows its switch in the All tab too. So the switch depends on the item being a key item (valuable), not only on the behaviour entry. Next, two checks with no new code: where the game stores the passkey's switch (switch it, then `ffrap_artifact`), and whether reloading a save after `ffrap_artifact 30010 off` clears the chest icons. Then a key item per artifact, a copy of the passkey's row with the artifact's own name and text.
- **Round 53: the passkey's switch writes the artifact list.** Switching it on and off in the Items screen gave `29520 on`, then `29520 off`: the entry under the id `DA_MapManager.ArtifactIdTable` gives `Artifact.AirshipSkin`. That table has only that tag and `Artifact.ChocoboSaddleBike` (29500). **The Cuff Links test was not a real one:** `ffrap_artifact 30010 off` and then a load with no save between brings back the save's own list, with the Cuff Links on. And the user's `Paks/~mods` has `zzz_TreasureMinimap_P`, a pak mod that likely shows chests on the mini-map by itself. So whether the Cuff Links do anything is still open. Mod 0.40.0 adds `ffrap_artifact table`: every artifact's tag into `ArtifactIdTable`, in case the game finds an artifact's state through it.
- **The Bandit Cuff Links (30010) show chests on the mini-map.** The user wants players to start with it, as FFRS_QoL's chest markers are the main reason to keep that mod. World 0.9.0 adds `start_with_bandit_cuff_links` (on by default), and mod 0.38.0 switches it on when it arrives. It shows chests only, not shinies.
