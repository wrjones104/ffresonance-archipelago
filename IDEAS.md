# Ideas and to-investigate

A scratch pad for ideas that are not on the test plan yet. Each one lists what we already know, from logs, dumps and the installed mods, and what to find out.

The chapter-by-chapter progression (party, vehicles, gates, Visions, Espers) is in [docs/progression.md](docs/progression.md).

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

## 3. Non-story ("open world") mode

**Idea:** jump the story to a late point once (for example after the airship), so the world is open, and gate progress with Archipelago items instead of story events. Keep boss fights as locations if possible. The full story is long for an Archipelago run.

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

**To find out:**
1. **Airship flag test.** On a save just before the chapter 4 ending, snapshot the flag array before and after the airship unlock. The flags that flip are the candidates. This needs a new console command that dumps the flags (or the changed ones) to a file.
2. **Where the airship is.** Even with the flag set, the airship may need placing on the world map (its map and point). The save's map data (`Map.mapId` plus a point id, per FFRSLib's travel notes) is where to look.
3. **Saddle-Bike.** Try 30011 again while riding a chocobo, and after a map change.
4. **What this means for the apworld:**
   - "Chocobo" (item 30002) becomes a progression item now. Locations become gated by it: Kolobos and Felicitas.
   - "Airship" becomes a progression item once its flag is known: Sanctums, volcanoes, ice islands and Whirlpool Hollow.
   - Radar tiers gate the world-map treasures.
   - This pairs with the open-world mode (idea 3). In story mode, if the story hands out the saddle, that vanilla grant would need blocking for the item to matter.

## 5. Key items and gates from the item table

**Known so far:** these ids are in `data/item_names.tsv`, and they match gates in [docs/progression.md](docs/progression.md):

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
- **FFRBestiary** reads the same save state (slots, timestamps, visited maps). Nothing has gone wrong running it with this mod: it is a neighbour, not a known conflict. Its notes mention a start-up crash once, in its own code.
- **FFRSLib** adds entries to the System Menu data asset and hooks its view model. A title-menu entry (idea 6) works the same way on a different asset, so both should be able to live together. Two mods writing the same list at once could still clash.
- Any mod that edits the save while we skip the prologue, or that grants items, can confuse the per-save item count.

**To find out:**
- **A start-up check:** list the other enabled mods (`Mods/mods.txt`, `enabled.txt`) and warn about known clashes in the log and on screen.
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

**To find out:**
- Which widget or view model draws the dialog (`ffrap_find Obtain`, or inspect while it is open), and whether its text can be set before it shows.
- How the client gets the text to the mod in time: scout every location at connect and write `scout <location> <item> <player>` lines to `ap_in.txt`.

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

**Still to tune, once it works:** the size, the place and the time on screen.
