# Resolved and parked ideas

Ideas moved out of [IDEAS.md](../IDEAS.md) once implemented, superseded, or dropped. Each keeps its original number and research notes, with the commits that resolved it.

## 1. Tablet Shards

**Status:** Implemented (`189c8d9`, mod 0.30.0 / world 0.6.0; `74487bf`, mod 0.33.0 / world 0.7.0; save-id lookup in `9f98ea7`, mod 0.52.3 / world 0.19.1).

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

**Status:** Implemented (`2250a00`, mod 0.6.0; `27fb53b`, mod 0.6.1; `68f3425`, mod 0.6.2; `737e8b5`, mod 0.8.0; superseded by the open world start in `8edc30c`, mod 0.16.0; `826f5e3`, mod 0.18.0; `de0af8a`, mod 0.19.0). The opening-movie input lock was parked in round 38 (`54dc893`).

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

**The new lead (round 109):** a new game can start past the opening, so there is no lock to keep. See IDEAS.md, idea 52.

## 3. Non-story ("open world") mode

**Status:** Implemented (`3c455fb`, mod 0.13.0 / world 0.3.1; `1218481`, mod 0.14.0; `8edc30c`, mod 0.16.0; `3029a9b`, mod 0.22.0; `b3b6f17`, mod 0.25.0 / world 0.4.0; `aa63e49`, mod 0.44.0 / world 0.13.0; `0ab288d`, mod 0.45.0 / world 0.14.0; `7ad8fa2`, mod 0.48.0 / world 0.17.0). See [open_world.md](open_world.md) and [bosses.md](bosses.md).

**Idea:** jump the story to a late point once (for example after the airship), so the world is open, and gate progress with Archipelago items instead of story events. Keep boss fights as locations if possible. The full story is long for an Archipelago run.

**Round 30 (2026-11-06): this is now the main direction.** Players on the Archipelago Discord ask mostly for open world. The design draft, with what the game data says about the story counter, the airship, enemy levels and the cleared state (story 9000), is [open_world.md](open_world.md).

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

**Status:** Implemented (`4291e45`, round 5 Chocobo Saddle check; `0db4b92`, mod 0.21.0; `3029a9b`, mod 0.22.0; `b3b6f17`, mod 0.25.0 / world 0.4.0; `572eeac`, mod 0.43.0 / world 0.12.0). Airship is free from the start, continents are gated by landing boxes, and the Chocobo Saddle (`30002`) is granted on open-world saves.

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

**Status:** Implemented (`d18acdc`, world 0.3.0 / mod 0.12.0; `1b71dda`, mod 0.42.0 / world 0.11.0; `572eeac`, mod 0.43.0 / world 0.12.0). Key items are shuffled via `shuffle_key_items` and gate locations in `data/gates.tsv`.

**Known so far:** these ids are in `data/game/items.tsv`, and they match gates in [progression.md](progression.md):

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

**Status:** Implemented (`367a940`, mod 0.7.3; `737e8b5`, mod 0.8.0; `b07a3e7`, mod 0.8.1; `54cbea0`, mod 0.8.2; `71e96da`, mod 0.8.3; `b73217a`, mod 0.8.4). On-screen text moved to idea 14; skipping the opening movie outright is parked in idea 2.

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

## 13. Archipelago text in the chest pop-up

**Status:** Implemented (`7b3857b`, mod 0.11.0 / world 0.1.4; `4f995cc`, mod 0.11.1; `78ad63a`, mod 0.11.2; extended to shinies in `e7783b5`, mod 0.31.0; base64 scout lines in `9d77c4e`, mod 0.35.4 / world 0.8.1; boss reward pop-ups in `7d41b42`, mod 0.49.0 / world 0.18.0). Removing the 1 gil reward altogether is tracked in idea 15.

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

**Status:** Implemented (`26cf52c`, mod 0.9.0; `c97de0a`, mod 0.9.5; `bbbafae`, mod 0.10.0; `b1258da`, mod 0.10.1).

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

## 16. Map blockers and custom forced gates

**Status:** Implemented (`2199350`, mod 0.53.0; `91ccc24`, mod 0.53.1; `df19f59`, mod 0.54.0 / world 0.21.0). Walking crossings between continents use cart blockers built into the mod when starting without the Airship; game-owned barriers and triggers (Crystal Tower, Oblivion Palace) are toggled via collision or progress counters instead of custom key items. See [open_world.md](open_world.md), section 4.

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

## 17. Airship landing restrictions for continent gating

**Status:** Implemented (`1218481`, mod 0.14.0; `7b8f44e`, mod 0.15.0; `54dc893`, mod 0.20.0; `3029a9b`, mod 0.22.0; `c80a1b0`, mod 0.23.0; `a72e30a`, mod 0.24.0; `b3b6f17`, mod 0.25.0 / world 0.4.0). See [open_world.md](open_world.md), section 4.

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

**Found (round 32, 2026-11-07): the no-landing boxes.** The world map also has 111 `BP_MapNonLandingArea_C` actors: a box with an `m_Condition` string. While the condition holds (or when it is empty), the airship cannot land in the box. Before story 5020, one box of half-size 2400 x 6000 keeps the airship off Mysidia. So the game already gates a continent this way, and this idea is now the plan for continent locks (decided in round 31: the airship is free, continents are locked by landing). Details and rough continent positions: open_world.md, section 4. Round 32 probes it with `ffrap_noland`.
- The landing point ids start with the island's number: 1xxx Grandshelt, 2xxx Lanzelt, 3xxx Kolobos, 4xxx Dirnado, 5xxx Olderion, 6xxx Zoldaad, 7xxx Mysidia, 8xxx Gronoa, 9xxx Pharm, 10004 the Crystal Tower. 10xxx are optional caves and Legend shrines.

**Round 37 (2026-11-08):** the shadow is placed by a sphere trace, and the airship keeps a list of actors for that trace to ignore (`CPP_MapUnit_AirShip.m_ShadowDecalSphareTraceActorsToIgnore`). Changing the box's channels 3 and 4 did not obviously bring the shadow back. Round 38 adds our boxes to the list. The hoped-for result is the shadow on the ground, red, with landing still blocked.

**Round 38 (2026-11-08): that is what happened.** The game lists its 111 boxes the same way. A box on the list looks and works like one of the game's own, and destroying it restores landing at once. So a continent lock needs no change to the game's landing check: a box per continent, listed for the shadow, destroyed when the item arrives. Still to learn (round 39): whether the listing lasts through boarding, and whether the box lasts through a map change.

**Round 40 (2026-11-08):** the listing lasts through boarding, and the box does not last through a map change. Mod 0.22.0 builds the locks on that (`ffrap_lock`, `open_world.md`, section 4).

**Round 33 (2026-11-08):** changing a box's condition works, but only after the airship lands and takes off again. A new box reads its condition when it starts. The game's Pharm story box is one landing spot (about 950 x 600 units), so locking it does not lock Pharm. A spawned box hides the airship's shadow. Details: open_world.md, section 4. Round 34 looks for a way to apply a change at once.

**Round 32 (2026-11-07):** a box spawned at the airship's height, 3000 up and down, lifted the airship over it and broke the camera, and the airship could still land on it. So the box's collision counts as ground for the airship. The game's own boxes sit on the ground (the Mysidia box: centre height 393, 700 up and down). The Blueprint has no script; the C++ class `CPP_MapNonLandingArea` reads the box and the condition. Mod 0.15.0 puts boxes at the ground height and adds `ffrap_noland lock mysidia`, which tests a changed condition on the game's own box.

## 18. In-game menu for on-the-fly settings and modifiers

**Status:** Implemented (`ecb4a65`, mod 0.38.0 / world 0.9.0; `4ce226f`, mod 0.39.0; `64dc113`, mod 0.39.2; `cd26283`, mod 0.40.0; `1b71dda`, mod 0.42.0 / world 0.11.0; `572eeac`, mod 0.43.0 / world 0.12.0; `7d41b42`, mod 0.49.0 / world 0.18.0; `7c08659`, mod 0.52.1).

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
- **Round 56: settings apply to the seed's save only.** The user found the EXP, gil and MRP rates on a regular save, where the AP rows may not be there to change them. Mod 0.42.0 writes the game's own values on any save not linked to the seed, and the player's again on the linked save.
- **Round 57: the rows did not stay, so the settings go back to every save.** The user had to type `ffrap_menu add` each time. The rows went in once per save load, so the game's table, loaded again, lost them; and the title screen's Options never had them. Mod 0.43.0 checks the table every tick (at the title too) and puts the rows back when missing. With the rows always there, the user wants the settings on any save, where they can be changed, so round 56's limit is gone.
- **Round 56: a scaling strength row.** "AP: Scaling strength" is a copy of the game's Difficulty row with our own tag, so it has the same three choices: Casual, Normal (the default) and Expert. It picks the scaling curve (open_world.md, section 5). The game's own difficulty still applies on top.
- **Round 63: a slider for our own strength names was tried and dropped** (mod 0.52.0 to 0.52.1). The user wanted names apart from the game's. A choice row's labels come from the table its `DT_RadioButton` points to, and the dump shows all eight `DT_OP_RadioButton_*` tables in use (the three-choice ones are Difficulty and DashType). So 0.52.0 made the row a 1 to 3 slider with the names in its label. The label ran past its box, and the user chose the copied Difficulty row back. A radio table made at run time would give real labels; that is not tried.
- **Round 60: the encounter slider counts in halves** (mod 0.49.0). The user wants 0.5 to 3 in steps of 0.5. The row's `SliderInfo` has only a minimum, a maximum and a default, and the slider moves in whole steps. So the row goes from 1 to 6 and each step is 0.5; its label says "(x0.5)". A step size on the slider widget itself is not looked at yet.
- **Round 60: ours win over FFRS_QoL.** FFRS_QoL writes the difficulty rows every 3 seconds. The fast tick writes ours back within 0.1 s, and the encounter fields are written at every settings pass.
- **ModSettings (the toolkit's F10 panel) is a cooked Blueprint** with fixed contents, so another mod cannot add options to it from Lua. MogHub (which FFRS_QoL has a page for) is not installed.
- **FFRS_QoL also writes `ap` in `DT_BattleGroup`** (its `APMultiplier`), the field our MRP scaling writes. It writes when its settings change or the table loads again. Our rescale then takes its value as the original, so nothing breaks, but our MRP scaling is gone until the party's level next changes. Idea 10 is about such conflicts.

## 19. A random starting party

**Status:** Implemented (`b3b6f17`, mod 0.25.0 / world 0.4.0; `ff90e17`, mod 0.26.0). Options: `starting_roster`, `starting_character_1..4` (which accept `random` in YAML), and `shuffle_party_members`.

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

## 21. NPC gifts as checks

**Status:** Implemented / superseded (side quests, character events, and vision events in idea 36; one-time free-talk NPC gifts in idea 43; strong enemies in [bosses.md](bosses.md); sanctum legend events in idea 23). Remaining untouched talk-reward groups (Arena, Twelve Arms, non-Siren Espers, `Nawatobi`) are tracked in [side_quests.md](side_quests.md) and [bosses.md](bosses.md); merchant ships are in idea 31.

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

**Side quests (2026-11-17):** planned in [side_quests.md](side_quests.md) (idea 36). Free-talk gifts stay here.

**To find out:** whether emptying a row's `ObtainItemList` stops the gift and leaves the event's text as it was; and, for open world, which gifts are still there at story 9000 (open_world.md, section 6).

**Off-line pass (round 48):** side quests use their own counters (`{progress:15}==10`), not the main story's. 74 gift rows fall into about 20 quests. 11 of those have a start trigger in `gimmicks.tsv`, and no story test blocks any of the 11 at story 8000. This pass ignored flags and quest counters, and quests started by an NPC are not in that table. Mod 0.29.0's crystals already use `ObtainItemList:Empty()` on a talk row, so the blanking is proven.

## 23. Shinies and vision crystals as real checks

**Status:** Implemented (`a623de5`, mod 0.29.0 / world 0.5.0; `189c8d9`, mod 0.30.0 / world 0.6.0; `e7783b5`, mod 0.31.0; `9f98ea7`, mod 0.52.3 / world 0.19.1).

**Asked for (round 45, 2026-11-09): the next priority once the broken things are fixed.**

**Shinies:** mod 0.29.0 blanks the reward on the actor (`m_ItemId`, `m_ItemNum`, `m_Money`), as chests are blanked. The 99 Tablet Shards became locations in world 0.6.0, at the user's request (`include_tablet_shards`). 6 shinies stay vanilla: 2 Magicite Shards and 4 key items.

**Vision crystals:** the user wants to skip the summoning scene and the questions. Mod 0.29.0 does this for the 16 sanctum crystals (`include_crystals`), and round 47 confirmed it works. The other 10 visions come from sidequests and one boss.

**Story bosses as map encounters:** Siren's fight is a story event, so she is an item for now. Story bosses could be fights on the map later.

## 24. The Crystal Tower as the goal, behind objectives

**Status:** Implemented (`aa63e49`, mod 0.44.0 / world 0.13.0; `0ab288d`, mod 0.45.0 / world 0.14.0; `6787ade`, mod 0.46.0 / world 0.15.0; `7ad8fa2`, mod 0.48.0 / world 0.17.0).

**Asked for (round 49, 2026-11-09):** block the Crystal Tower, and open it with objectives such as "defeat X espers", "defeat X bosses" or "collect X visions". The AP goal is then to beat the final boss. The Tablet Shard goal is a stopgap until this works.

**To find out:**
- Whether the final boss can still be fought from an open world start, and whether a win can be seen.
- How to block the tower. It has a landing point and an exit, so it needs a lock like the continents.
- How to show the objectives in game. The item feed could count them, as it counts shards.

**Round 58: the first objectives, characters and visions (the user's choice, in the style of Worlds Collide).** World 0.13.0 adds `final_boss_characters` (default 6 of 8, the starting party counts) and `final_boss_visions` (default 12 of 26), for the `story_checkpoint` goal only. A count the pool cannot meet is lowered (party members or visions not shuffled). The goal's logic needs them. The client counts what it has received and writes a `cfg finalboss` line each time that changes. Mod 0.44.0 seals the tower's point of no return until both are met:
- The climb to the top floor (map 3281) starts at an interact trigger on map 3280, gimmick 133, event `C08_Dng_10Cry_41_CanNotRetrun_01`. The lock goes there, before the point of no return, so a player without the counts is never stuck upstairs.
- The trigger's collision goes off, so its prompt cannot come; on again once the counts are met. Spawned blockers (idea 16) would also work, but this leaves nothing in the world.
- Walking near it says what is missing: "The way to the top is sealed. Archipelago needs characters 4/6, visions 9/12".
- From 3281 an exit leads to an event map (5191), likely the last fight. The tower's own story triggers: `C08_802_01` at story 8000 by the entrance and `C08_811_02` at 8030 near the point of no return.
- Next objective kinds: continents unlocked, Tablet Shards, bosses or espers defeated; later "N of these", as Worlds Collide has.

**Round 57: the lock works.** With characters 2/4 and visions 0/8 the prompt stayed away and the notice showed; with the counts met it came back. The trigger is loaded only near the climb (from about 38,000 units away the nearest trigger was another one), so mod 0.45.0 logs its absence once per visit. The goal fired at 8050, which is before the last floor: world 0.14.0's `final_boss` goal is the win over Sol in battle group 9056 (open_world.md has the order of the last fights).

## 26. Artifacts from Archipelago

**Status:** Parked (`74cf68e`, mod 0.37.1; probes preserved at `351a4fd`, mod 0.40.1; removed in `c8e09fe`, mod 0.41.0 / world 0.10.0).

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
- **Round 54: the Cuff Links do nothing so far.** With `zzz_TreasureMinimap_P` moved out of `Paks/~mods`, the chest icons went away, and they did not come back with the Cuff Links on (`30010 on` in the artifact list, and the tag in `ArtifactIdTable`), even after map changes. So the icons the user saw were the pak mod's. The passkey switch changes the airship as soon as the menu closes, so a switch acts through a live update. The mini-map view model (`CPP_VM_MiniMap`) keeps its own `ArtifactActiveMap` (tag -> on) and listens for `Delegate.Artifact.Active.Update` (`DA_MiniMapLayout.ArtifactUpdateTag`). `DA_MapIconBinding.ArtifactIconTagMap` is empty everywhere, and it is for world-map icons anyway. Mod 0.40.1 adds `ffrap_artifact minimap`, to list and set that map. The other lead is the TreasureMinimap pak itself: what it changes may be a data change the mod can make at run time.
- **The Bandit Cuff Links (30010) show chests on the mini-map.** The user wants players to start with it, as FFRS_QoL's chest markers are the main reason to keep that mod. World 0.9.0 adds `start_with_bandit_cuff_links` (on by default), and mod 0.38.0 switches it on when it arrives. It shows chests only, not shinies. (Round 54: it did not. The icons were the pak mod's.)
- **Round 55: no change on the mini-map.** `ffrap_artifact minimap` found one mini-map view model with an empty `ArtifactActiveMap`, before and after the passkey was switched. Setting `ThiefCuffs` on in it gave no chest icons, also after a map change.
- **Round 55: what the TreasureMinimap pak changes.** It replaces three data assets and nothing else: `DA_MiniMapEntryProperty`, `DA_MapIconBinding` and `DA_WM_EntryProperty`. In the game's own `DA_MiniMapEntryProperty`, the interact types `Field.Object.Interact.Type.Treasure`, `.Transition` and `.Check` are hidden (`bOverrideDefaultDisplay` true, `bDefaultDisplay` false), and `DA_MapIconBinding` gives Treasure and Transition the icon `UI.Map.Icon.Null`. The pak shows them, with the icons `UI.Map.Icon.TreasureBox`, `.Transition` and `.Check` at the low zoom state, and adds Treasure and Check to the world map's `DA_WM_EntryProperty`. So the chest icons have nothing to do with the Cuff Links. They are data our mod could write at run time (idea 27).
- **Parked (round 55).** The game has no screen to switch artifacts, and the Cuff Links show no effect when on. Perhaps the feature comes in a later patch. The user's call: leave all artifacts out for now, the passkey too (pre-order players get it anyway, and it is cosmetic). World 0.10.0 takes them out of the pool and drops `start_with_bandit_cuff_links`; mod 0.41.0 drops the artifact list sync and the `ffrap_artifact` probes. The probes are in git history (mod 0.40.1, commit 351a4fd) if the feature comes back.

## 27. Chest and exit icons on the mini-map

**Status:** Implemented then dropped (`572eeac`, mod 0.43.0 / world 0.12.0; `6787ade`, mod 0.46.0 / world 0.15.0; dropped in `282ae50`, mod 0.47.0 / world 0.16.0 in favor of dedicated map-marker mods such as FFRS_QoL).

**Idea (round 55):** the game hides chests, map exits and "check" spots on the mini-map, by data (idea 26 has the three assets and fields). The TreasureMinimap pak mod shows them. Our mod could make the same change at run time, so players would not need the pak.

**As an Archipelago item:** a "Treasure Radar" that shows chest icons once it arrives, or a yaml option to start with the icons on. It could pair with the progressive radars on the user's list.

**To find out:** whether writing `bDefaultDisplay` and the icon tags in the loaded assets is enough (the entries hold a nested `StatePropertyMap`, which is harder to write from Lua than a flat field), and whether the mini-map reads the assets once or on each map load. FFRS_QoL's chest markers may do the same thing.

**Round 57: the icons show and stay.** The user asks for more, as FFRS_QoL does: hide a chest's icon once it is opened, and mark shinies and Tablet Shards too. To look at in FFRS_QoL's code.

**Round 58: dropped (world 0.16.0, mod 0.47.0).** The Chest Radar worked only in part: the mini-map reads the assets when a map loads, so a map drawn before the radar arrived kept no icons until the next map. Opened chests kept their icons, and shinies and shards had no markers, which FFRS_QoL has. The user chose to leave map markers to other mods. The option, the item, the `cfg chesticons` line and `ShowChestIcons` are gone.

**Round 58: the Chest Radar (world 0.15.0, mod 0.46.0), at the user's request.** `minimap_chest_icons` is now `start_with` (the default, as before), `item` or `off`. With `item`, a Chest Radar takes the place of one filler item in the pool (classed useful). It is a flag item: it turns on event flag 1430, which nothing in the game uses (1430 to 1449 are free; the boss test uses 1440). The mod shows the icons once the flag is on, so it stays with the save. The name keeps it apart from the airship's Treasure Radar quest.

**Round 57: built as a yaml option.** `minimap_chest_icons` (on by default) goes to the mod in slot data. On the seed's save, mod 0.43.0 writes the Treasure entry as the pak has it (shown, the `TreasureBox` icon, also at the low zoom state) and the icon binding; on any other save it puts back what the assets held. Chests only: the pak also shows `Check` spots and map exits, which may be shinies and doors. Not seen in game yet.

## 29. What a boss fight needs, in logic

**Status:** Implemented (`640712a`, world 0.25.0: `data/game/capabilities.tsv`, `apworld/ff_resonance/boss_logic.py`, and per-boss capability rules; `862f260`, world 0.28.0: Magicite awakening logic and double-action party rules). See [boss_logic.md](boss_logic.md).

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

**First-pass design:** see [boss_logic.md](boss_logic.md) for the capability matrix, 8-element mitigation table, progression proxies, per-boss rules for all 41 bosses, and unshuffled Vision / side-quest location requirements.

## 32. Radar treasures as locations

**Status:** Implemented (`77170cb`, mod 0.57.0 / world 0.24.0; `862f260`, `d4ab143`, mod 0.59.0 / world 0.28.0; Magi-tenna NPC in `c725c2f`, mod 0.61.0 / world 0.30.0).

**Round 72, from the user's question.** The airship radar does not reveal any of the world-map shinies we have: those have no visibility condition and stand there from the start. It finds 13 treasures of its own instead (`docs/logic.md`, "Treasure radar").
- **In the game:** a side quest on the airship (`{progress:49}`) installs the radar (flag 702) and then the Magi-tenna (27006), Resonance Stone (27007) and High-Power Generator (27008, sold by a merchant ship). Each part opens the next tier of pinger points: 5, then 4, then 3, then the 13th.
- **The rewards:** `SubEv_C05_TreasureRadar_01_01` to `_13` give Adamantite (20016), Magicite (25001), two Magicite Crysts (25002) and nine pieces of equipment (11098, 12016, 11022, 10497, 10819, 12038, 12073, 12075, 12059).
- **At story 8000 on our start,** flag 702 is off, so no pinger works. The three parts are key items in our pool that do nothing yet.
- **Built (mod 0.57.0, world 0.24.0):** the 13 treasures are locations (found flags 704 to 716 as checks). Three Progressive Radars (item 27006, counted by the mod from the session's items) take the place of the three parts: one turns flag 702 on, two and three set `{progress:49}` to 40 and 50. They need the Airship. Their rewards go to the pool, and each dig row gives the pop-up's stand-in Potion. The pingers also chain: each needs the one before it found (`{progress:51}`, set by each dig row).
- **Round 75 (mod 0.59.0, world 0.28.0):** the radar works (round 74), and each Progressive Radar now opens its whole tier at once. The mod holds the found count `{progress:51}` at the top of the radar's band (13, 22, 31), the threshold of the tier's last point. Mt. Reizan's Chest 3, which holds the Resonance Stone, is a location with the treasures on (`docs/playtesting.md`, round 75).

## 33. The Mechabo upgrade quests cannot start

**Status:** Implemented (`6bf4953`, `8b979d5`, `04dba04`, `98a0a1c`, verified in `c35c301`, mod 0.61.0). Turning the three Mechabo quests into locations remains a future item in [side_quests.md](side_quests.md).

**Known issue in v0.28.0 (found off-line, 2026-11-16).** The three Mechabo quests from Verun cannot be reached on our start. Verun never appears at the Dwarven Forge or on the airship. This goes with the other side-quest work ([side_quests.md](side_quests.md), idea 36).

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

**Round 92 (a new seed's save, counter 10):** Verun showed only "..." and no quest. Since round 93 the `mechabo:` line gives the quest log's state of quests 17, 26 and 27 from the save (`request.DataMap`).

**Round 93 result:** quest 17 open, but Ipooh kills did not count. Its first step is board quest 1001, a hunt of unit 55, whose state and kills are in the save's `questBoardList` (EQuest_State: None, AfterOrder, ConditionAchievement, QuestSuccessful, QuestFailure). Since round 94 the `mechabo:` line gives them.

**Round 94 result:** `board quest 1001 none`: never ordered, so kills did not count. **Built (round 95):** for each of Verun's open quests the mod orders the current step's board quests that read none.

**Round 95 result:** the whole chain to Mechabo Tackle works. Only the first hunt (1001) needed the order; the game ordered 1002 itself. "Arise, Mechabo!" gives no skill (the user): it repairs Mechabo and starts the gather quests, and "Mechabo Evolved" gives Mechabo Tackle at counter 40.

**To find out:**
- Whether the steps should be locations: the six abilities and three Magicite rewards, with logic for each material's enemy area. The steps also need Lid in logic if the abilities stay vanilla.

## 34. Location names a player can find

**Status:** Implemented (`55082fb`, world 0.29.0; hand-written overrides for chests, shinies, Tablet Shards, and radar treasures in `b8838ae`; NPC gift renames in `168240c`, `4f38161`, `98f3604`, world 0.31.0).

**From the user, 2026-11-17.** "World Map Shiny 167" says nothing about where to look. Players asked during the pre-release.

**What the data gives without a person (a prototype, 2026-11-17):**
- **World-map shinies (94) and radar treasures (13):** each has x and y. The world map has 99 doors with a named destination (`transitions.tsv` to `maps.tsv`) and the continent boxes (`data/continents.tsv`). Nearest door plus a compass point gives, for example, Shiny 167 "Gronoa, NW of Rugged Mountain Path", which matches the user's screenshot. The axes are +X north, +Y east. Weak spots: five or more doors are all "Sanctum of Light", and a few shinies are 3000 or more units from any door.
- **Chests (206):** the place name is there already, and a dungeon is mostly one map, so there are no floor names. The chest's vanilla item makes a name: "Wind Shrine - Armor of Gales Chest". Only 4 of 206 share an item with another chest in the same place.
- **Tablet Shards (99):** a town's map name, with the uid as the number. A position inside the town (north, plaza) needs a person or landmarks we do not have.
- **Bosses and crystals:** already readable.

**What a person should do:** read through a generated list, fix the weak ones and name the tablet shards. A TSV of `key`, current name and suggested name, with an empty column for the user's name, does it. Names come from the generator (`tools/gen_apworld_data.py`) with the user's column as an override. The first draft is `data/location_names.tsv` (469 rows; 17 duplicates and 10 shinies far from any door are marked in `note`). Nothing reads it yet.

**Built (round 77, world 0.29.0):** `tools/gen_apworld_data.py` names every chest, shiny, Tablet Shard and radar treasure this way and rewrites `data/location_names.tsv` each run, keeping the `name` column. A filled `name` wins. Repeats are numbered ("Mysidia - Shiny near Salome Cave 1" to 3). Sanctum doors name their sanctum ("near Sanctum of Onion Knight"). The `old` column keeps round 76's names, for players with old yaml lists. Tablet Shards are numbered within their place, so they still want a person.

**What it changes:** location ids stay the same, so the client, the mod and old seeds keep working. Players' yaml lists (`exclude_locations` and the like) that use the old names stop matching. Do it once, before the full release.

**Follow-up (`b8838ae`, `168240c`, `4f38161`, `98f3604`):** hand-written names were filled across `data/location_names.tsv` (including Tablet Shards), and NPC gift locations were renamed by where each NPC stands.

## 35. Keep the received-items count in the save

**Status:** Implemented (`55082fb`, mod 0.60.0).

**From the pre-release, 2026-11-16.** After a mod update, and on a second PC, players had to `/bind` again and got every item a second time.

**Why:** the applied count (`state.applied`, `slotItems`) and the seed key live only in `ap_state.txt`, beside the mod. The install steps say to delete it on an update. A save bound by `/bind` with no count starts at 0 and gets everything.

**The likely fix:** write the count, and a short tag of the seed, into the save. Unused event flags as bits are one way: 20 flags count to a million items, and 16 more hold a hash of the seed key. The game saves them with everything else, so Steam Cloud carries them to the other PC. On load, a save whose tag matches the session is the session's, with the count it holds. `ap_state.txt` stays as a fallback for saves from before.

**Built (round 77, mod 0.60.0):** 12 count flags (1414 to 1419, 1430, 1432 to 1436) and 11 tag flags (1437 to 1439, 1442 to 1449). The tag is FNV-1a of the session key folded to 1 to 2047. On load, a save whose tag is the session's is linked with its count, before `ap_state.txt` is asked; a save stamped by another seed is not linked even when `ap_state.txt` lists its slot. The mod writes the stamp whenever the applied count changes, in the same tick as the grant, so a save the game makes holds both together. A save from before 0.60.0 has no stamp and is judged by `ap_state.txt` as before, then stamped.

## 36. Side quests as locations

**Status:** Implemented (`6bf4953`, `d1437b9`, `0662c63`, mod 0.61.0 / world 0.30.0; `19a087b`, mod 0.62.0 / world 0.31.0, adding `hide_quest_rewards` and removing unused key items). See [side_quests.md](side_quests.md) for future additions (Mechabo quests, Aileen's weapons, non-quest-log rewards); character-quest stat bonuses remain in idea 45.

**From the user, 2026-11-17.** Side-quest rewards in the pool. The plan is [side_quests.md](side_quests.md).

**Off-line pass (2026-11-17, before round 78):**
- The game's quest log (`DT_RequestData`) has 33 quests with English names, accept tests, completion tests and prizes. 31 become locations in the first pass; Battle at the Big Bridge and Iron Splitter go with the bosses.
- Each quest runs on its own counter. Quest-item gift rows move the counter, and the next step tests the counter, not the item. So 11 quest items in our key-item pool unlock nothing: Dew of Reprieve, Viscus Vitae, Rushroom, Pure Water, Convalescence Draught, Super Salubrious Salad Stem, Portrait of Dario, Dario's Letter, Ruby Fragment, Broken Sword Hilt and Blade (20020, 20023 to 20032). They leave the pool and stay vanilla (decided with the user).
- Every quest's start holds at story 8000 except the Mechabo quests (idea 33).

**Built (round 78, world 0.30.0, mod 0.61.0):** option `include_side_quests` (off by default for now): 28 quest locations, `quest:<id>`. The mod swaps each reward row's first item for the stand-in Potion, takes visions out, and reports a quest when its counter reaches the reward row's value. The 11 quest items left the pool. `data/quests.tsv` lists the quests by hand; `data/game/quests.tsv` and `quest_steps.tsv` come from the dump.

**Round 88 results and fixes (build c9dab8b2):**
- Mog Tag's pop-up comes before its counter moves, and each tier runs at two counter values, so it had no early pop-up. The generator now allows several values, gated by the flags every step needs (545, the chase).
- The Call from Beyond's reward runs on map 2100, after a row moves the player there. `quest_steps.tsv`'s new `at` column follows those moves.
- The user asked for the scouted item in the Quests screen. Its Rewards list is `DT_RequestData`'s `Prize`, where an entry with ID 0 shows its own text; the location's entry becomes that.

**Round 98 (`0662c63`) and round 103 (`19a087b`):** steps on maps past Liquid Thunder use the chests' rule in logic, quest second rewards are locations (`quest2:<id>`), `hide_quest_rewards` shows `???` on the Quests screen when enabled, and White Jade Stone, Black Jade Stone, Magic Tome, and Tunnel Key left the key-item pool.

## 37. Open the Oblivion Palace safes with no turn-in

**Status:** Implemented (`acfbd9f`, `a121d5e`, `5b4f492`, mod 0.61.0). The live-refresh edge case when shards arrive while standing inside the palace is parked.

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

**Status:** Implemented (`a4fd9e1`, `60fba4c`, `8b979d5`, mod 0.61.0; evolved into the two-tab Settings/Seed page hosted on the Options screen in idea 39).

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

**Status:** Implemented (`8b979d5`, `a18f8b0`, `4366822`, `aaef171`, `d1437b9`, mod 0.61.0; `7108c46`, `19a087b`, mod 0.62.0).

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

**Rounds 89 to 103 (`d1437b9`, `7108c46`, `19a087b`):** Seed tab Command rows became default, saves not linked to the seed receive none of the seed's writes, and in v0.31.0 the Seed tab moved to the Graphics tab for its monitor icon while rows are removed in reverse order so they keep their order on reopen.

## 42. Item names in Archipelago's colours

**Status:** Implemented (`973554f`, `2f76f9b`, `c35c301`, `c725c2f`, `168240c`, mod 0.61.0 / world 0.30.0; `4f38161`, `19a087b`, mod 0.62.0 / world 0.31.0).

**From the user, 2026-11-19 (round 89).** Show item names in the colours Archipelago's clients use: light blue (cyan) for filler, dark blue (slateblue) for useful, purple (plum) for progression, red (salmon) for traps. In the item feed, the chest and reward pop-ups, and the Quests screen's Rewards. The name only, not the rest of the text.

**Found off-line (round 89):**
- The client now sends each item's flags (1 progression, 2 useful, 4 trap) and its name with its item line, and with each "Sent" message. A location's scout already had its flags.
- **The feed** is our own VerticalBox of TextBlocks. A line can be a HorizontalBox of three TextBlocks, the middle one coloured by writing `ColorAndOpacity.SpecifiedColor` before it is on screen. No colour struct goes to a setter (round 20).
- **The chest pop-up's message** (`Text_Message` in `WBP_DialogBox`) is a CommonRichTextBlock. The game's text decorator, `CPP_RTBD_Text` (`RTBD_TextStyle`), handles `<text style="italic">` and `"bold"` in the game's strings, and has a `ColorSet` and a `SizeSet`: DataTables of `RTB_Text_Color` (`FontColor`) and `RTB_Text_Size` rows. The game ships neither table, and the decorator's default has none. Its attribute names are not readable in the executable. So colour there needs a probe: make the table, give it to the decorator, and try `<text color="progression">`.
- **The Quests screen's Rewards** line (`WBP_Quest_Reward_Text`) is one CommonTextBlock with the game's text style (`BP_SystemTextStyle`). It cannot colour part of its text, and a line already on screen takes a colour only through a setter that needs a colour struct. Not built. Ways to look at later: a style class the game does not use, given by `SetStyle` (it takes a class); or making the line a rich text block.

**Probes (round 90, build 87f4d742):** `ffrap_feed colors on` (four test lines, then real ones); `ffrap_popup probe` (the message's decorators and their tables); `ffrap_popup colors on [attr]` (the table, then markup in the next pop-ups). All are off at each start.

**Round 90 result:** the feed colours work; the user asked for the name in bold too. The pop-up's message has no decorators, so the markup drew the name black, and `AddRow` with a Lua table made no rows. Markup is out for the pop-up.

**Built (round 91, build ec671324):** feed colours on by default, with the name bold. The pop-up and the Quests screen use the feed's way: a row of our own TextBlocks, styled before it is on screen. The pop-up's row goes under the message, the Rewards line's beside its hidden text block. Both are probes (`ffrap_popup colors on`, `ffrap_quest colors on`).

**Round 91 result:** the feed and the pop-up work, and the pop-up's colours are on by default since round 92. The Quests screen showed no colour and logged nothing. Since round 92 the probe logs what it sees (`seen:` lines) and takes a line's block by its name or by its text.

**Round 92 result:** the lines were found, but no text block under them: it sits in the entry panel's named slot. Since round 93 the probe finds the reward texts as CommonTextBlocks whose path is in a reward line, and in a one-child slot puts our row in the block's place (`SetContent`).

**Round 93 result:** no such CommonTextBlock was found. The line's `SetText` writes `CommonTextBlock_194`, a variable of the line, held in the entry panel's `Slot_33_Content`. Since round 94 the probe takes the block from the line's property, or from `GetContentForSlot`.

**Round 94 result:** the blocks were found, but the name went blank: the NamedSlot's `AddChild` failed and gave back a null object, which Lua takes as true. Since round 95 a slot counts only when `IsValid()`, and in a NamedSlot our row takes the block's place.

**Round 95 result:** the Quests screen works. The user: the colour comes a second late. Since round 96 the screen's colours are on by default; `ffrap_quest instant on` (a probe) hooks the reward line's `SetText` to colour each line as it is written.

**Rounds 97 to 103 (`c725c2f`, `168240c`, `4f38161`, `19a087b`):** instant quest colouring is on by default, server-sent items are coloured by their own category, pop-up coloured rows clear when the dialog's message changes, and `hide_quest_rewards` shows `???` uncoloured.

## 43. NPC gifts as locations

**Status:** Implemented (`c725c2f`, `168240c`, mod 0.61.0 / world 0.30.0; `4f38161`, `98f3604`, mod 0.62.0 / world 0.31.0). Seven reachable one-time gifts are active locations; three unreachable or missing at story 8000 (`1403`, `1407`, `1409`) are left out.

**From the user, 2026-11-19 (round 96).** The NPCs who give one-time rewards (the old man with the Lunar Sword and the Brigandine) are locations, always on.

**Found off-line:** each one-time gift row sets its own flag in 1400 to 1413 and gives items; `tools/gen_from_dump.py` writes them to `data/game/gifts.tsv` with the map actor leading to each. There are 10, all reachable on the open start; the Pharm cat's (1413) needs flag 1412, from the Mysidia cat. The Cabin Key's row sets no flag and is left out.

**Built (round 97, build 26e942ac):** each gift is a location, `gift:<flag>`, checked by its flag. The row gives the stand-in Potion. One location per NPC: the first item is the location's, a second goes into the pool in place of a filler. The Magi-tenna's NPC goes with the radar treasures.

**Round 98 (the user):** every gift showed the Potion. The check came only after the scene had ended (gift 1400: 30 s with no pop-up on screen), or wrote the next chest's pop-up (1411, 1405). Now the pop-up is written early, as for Token Legacy: in an event on a gift's map, with its check not sent yet, a pop-up is the gift of the nearest gift NPC within 500 units (`gifts.tsv` has where each stands). Two gifts were not found at story 8000 and are left out: the Ether NPC in the Commercial District (1407, standing far from the rest of the map) and the Mist Potion NPC in Grandshelt Castle (1409, map 3020). **To find out:** whether either shows at an earlier story value.

**v0.31.0 (`4f38161`, `98f3604`):** the Zoldaad Dungeon gift (`1403`) was also removed because it cannot be reached from the open world start, and the remaining 7 gifts were renamed for where each NPC stands.

## 44. The Research Center Ruins' key card spots

**Status:** Implemented (`9edc8ae`, mod 0.61.0 / world 0.30.0).

**From the user, 2026-11-19 (round 96).** The three lab key card spots are locations.

**Built (round 97, build 26e942ac):** shinies 3220:32, 33 and 37 are locations (`SHUFFLED_KEY_ITEMS` in the generator). Each card is in the pool once (a progression item a chosen location holds is not added again); the level 2 spot is behind the level 1 door, the level 3 spot behind the level 2 door (`data/gates.tsv`); without key item shuffle each spot keeps its card.

## 48. Item pool pass: drop-only gear, more Magicite, an early healer

**From a tester, 2026-11-22 (v0.31.0, a full seed to the goal at party level 30).** Status effects were hard: no Ribbon, few cures. Magicite was tight but fair; they liked choosing. They hinted for a Ribbon and it was not in the pool. The user wants more status gear and Magicite in the pool, and an option to put a support vision early.

**Why Ribbon is missing:** the pool is each location's own vanilla item, with progression items in place of random filler (`items.create_all_items`). Ribbon (12065) is in no chest, shiny, quest or gift. It drops from Archwitch Fina's story fight (gone on our start) and is a rare steal from Messalina (level 52). `DT_UnitParameter` has `DropNormalItem`, `DropRareItem`, `StealNormalItem` and `StealRareItem` per unit.

**Accessories with no location, from the dump (2026-11-22):**

| Source | Accessories |
|---|---|
| Enemies only (drop or steal) | Ribbon, Angel Ring (Regen), Aeolian Misanga, Iron Sandals, Gale Hairpin, Poison Charm, Ring of Rage, Arcane Pendant, Vampire Charm, Adamantine Beads, and the four imbue charms (Solar Pendant, Azure Amulet, Golem Core, Halo Ring; three of them drop from story bosses) |
| Shops only | Star Pendant (Poison), Silver-Rimmed Glasses (Blind), Safety Bit (Death), Alarm Earrings, Precognizant Beads, Tiara of Frost, Scintillating Ring, Heart Anklet, Life Charm, Hairband. The Arena shop: Reflect, Protect and Barrier Rings, Warding Bell, Foe Attractor, Circlet of Enlightenment |
| Not-yet locations (Arena ranks, Twelve Arms, rope jumping, chapter 9 quests, DLC) | Super Ribbon, Dragon Seal, Omega Badge, Gold Hairpin(+), Genji Gloves, Ultima Reactor, Swift Badge, Hairpin of Grace, Mastery Ring. These come with those locations (roadmap milestone 4), not now |

The single-status accessories are mostly in shops already, and Headband, Jeweled Ring and Calm Armlet are in chests too. So the gap is Ribbon, and early access before a shop's continent is open.

**The pool today (5 seeds each, world 0.31.0):**

| | Locations | Consumables | Gil | Equipment | Magicite (Shard / Magicite / Cryst) |
|---|---|---|---|---|---|
| Defaults | 519 | 151 | 7 | 131 | 37 (12 / 12 / 13) |
| Side quests on | 564 | 162 | 12 | 143 | 54 (18 / 19 / 17) |

Awakening a vision fully costs one of each tier, so 26 visions need 78. A default seed has enough for about 12. The Arena shop sells all three tiers, behind the Arena's medals.

**Healing visions** (`capabilities.tsv`, Cure or Esuna at awakening 0): Leah, Ayaka (both), Warrior of Light, Cecil, Tidus, Y'shtola, Lightning (Esuna). Fina is the only party member with Cure (level 3), and the start is Rain and Lasswell.

**The user's choices (2026-11-22):** two Ribbons and one of each enemy-only accessory; 9 extra Magicite by default, as a yaml option; the early healer on by default.

**Built (round 104, world 0.32.0 build 94562703):**
- `data/pool_additions.tsv` lists the gear: 2 Ribbons and 13 enemy-only accessories, 15 items. `tools/gen_apworld_data.py` writes them to `POOL_ADDITIONS`, with `MAGICITE_ITEMS` and `FILLER_VALUE` (a filler item's shop price times its count; gil by its amount).
- `extra_magicite` (0 to 30, default 9) adds Magicite split over the three tiers, the lower tiers first when it does not split evenly.
- Progression items still take filler at random. Then each addition takes the cheapest filler left, so a Megalixir is never lost to a Ribbon. Gear comes before the extra Magicite.
- The pool keeps one filler item for each excluded location (the Oblivion Palace's chests, `excluded_regions`, the yaml's `exclude_locations`), as those take filler only. The first test run found this: chests-only test pools failed to fill. If there is not room, additions are left out from the end, with a warning.
- `early_healing_vision` (on by default, with `shuffle_visions`): one of the seven healing visions goes in `multiworld.local_early_items`.
- No mod change: the mod's item path gives any item id.

**The pool now (10 full fills, real defaults):** equipment 131 to 146, Magicite 37 to 46, consumables 151 to 133, gil 7 to 1 (the small gil amounts are the cheapest filler). The healer was in sphere 0 in all 10.

**Round 104 result (the user, 2026-11-23): passed.** The spoiler had the gear and the extra Magicite, a healer was in sphere 1, a received Ribbon and an imbue charm went into the bag and could be equipped, and `extra_magicite: 0` with `early_healing_vision: false` gave the old pool. Whether the tester's status problem is gone needs their next seed.
