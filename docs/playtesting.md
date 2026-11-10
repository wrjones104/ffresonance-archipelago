# Playtesting log and test plans

In-game test rounds and current test plans for the Final Fantasy Resonance Archipelago mod and apworld.

Automated suite tests are documented in [tests/README.md](file:///c:/Projects/ffresonance-archipelago/tests/README.md).

## Test results so far

**Round 1 (0.1.0, 2026-11-04): passed.**
- Bag items, vision unlock (with all 8 synchro keys), party add and duplicate guards worked. Party add refused a unit when the party was full.
- Story counter reported live (5062 -> 5064).
- Chest checks reported live (`chest:3180:0`, `chest:3180:2`).
- The dump showed:
  - The chest table has 238 rows. Each row's `mapId` and `ID` match the live chest's `m_TreasureBoxData`, so `chest:<mapId>:<ID>` from the table is the location key. Row names do not encode the map.
  - Gil chests have `ItemId = -1` and a `Money` value. `IsTrap` and `battleGroupId` are on every row.
  - `IsOpenTreasureBox` answered `false` for two chests opened moments before. Live checks use the chest's own `m_IsOpen`, so they work. A reconnect re-sync needs the save, so round 2 finds out when the save catches up.

**Round 2 (0.2.0, 2026-11-04): mostly passed, and it found three bugs.**
- Chest export: 238 rows, 56 maps, no duplicate `mapId:ID` keys, 9 gil chests and no trap rows. Row `3020:0` has `battleGroupId 51`, indicating a guarded chest. The export is in `data/chests.tsv`.
- Shinies:
  - The reward is on the actor: `m_ItemId`, `m_ItemNum`, `m_Money` on `CPP_MapGimmick_ItemObjectBase`.
  - `CPP_MapGimmick_FieldItem.m_IsOpen` is the picked-up flag.
  - The save (`IsOpenTreasureBox(map, m_UniqueId)`) answers true the moment one is picked up.
  - Classes seen: `BP_MapGimmick_FieldItem_C`, `_Child_C` and `_Medal_C`.
  - The world map (1000) has 93 field items. 8 of them have no item and no money, only a `VisibleCondition`: they are story or quest points, not pick-ups.
- Save timing: shinies are in the save at once. Chests never were under `m_Id`, even after leaving the map and saving, indicating the save does not key chests by `m_Id`.
- Bug 1, wrong current map: the save's `Map.mapId` lagged minutes behind the real map. Two chests from map 3180 were reported as `chest:1000:0` and `chest:1000:2`. Fixed: the current map is now `CPP_MapManager:GetSameMapId()`, and chests are keyed by their own table row.
- Bug 2, actors lingering after a map change: a map's actors outlive the map change for a moment. Fixed: nothing is evaluated until the map id has held for 3 scans.
- Bug 3, blanking restore: after `ffrap_blank off`, chests in the current map still gave 1 gil. They had spawned while blanking was on, so their original snapshot was already blank. Fixed: originals are keyed by the row's `mapId:ID`, and a spawned chest restores from those.
- Rowless chests: four chests had `m_Id -1` (one in 2010, three already open in 3020).
- Switching saves: reported checks are per install, which fits Archipelago since a location checked once stays checked.

**Round 3 (0.3.0, 2026-11-04): passed the steps that were run; the chest save key is found.**
- Map ids: `GetSameMapId()` was correct on every change (2002, 2001, 2015, 5200, 1000, 3001). The save's `Map.mapId` reported 3020 while in 2002 and 2001.
- Chest save key is `IsOpenTreasureBox(current map, m_UniqueId)`. `TypeData.ID` is the same number.
  - It returned true for every opened chest: 3020:1, 3020:3 to 3020:6, 3001:0, 3001:1 and rowless chests.
  - It returned false for closed chests.
  - `m_Id` matched nothing. Its single match was a collision: `m_Id 7` of chest 3020:7 was the `m_UniqueId` of opened chest 3020:1.
- Rows and maps do not line up: rows `3020:*` sit in map 2002, and rows `2001:*` in map 2001. The row key remains the location key, with `seen.tsv` recording each chest's save key.
- Rowless chests: the three in 2002 (`u50`, `u52`, `u54`) had no item and no money and were already open. They represent story chests whose contents come from an event.
- Shinies: live pickups (`shiny:1000:137`, `shiny:1000:3`) and looted ones (`100`, `150`) were reported. One field shiny (map 3001, uid 80, item 20001) is story-gated: `{progress:31}==20`. Map 2015 has a Medal shiny (item 25004).
- Story counter: jumps made via Modding Tools (1130 -> 5010 -> 1130) reported as `story 5010`. The client treats story reports as "reached at least N".
- Clean start: deleting `ap_state.txt` while keeping `ap_in.txt` re-granted items 0 to 6. A complete clean start deletes all three `ap_*.txt` files and restarts the server.

**Round 5 (mod 0.4.0 with MVP apworld and client, 2026-11-05): passed.**
First connected Archipelago session: new game, local MultiServer, 0.6.7 Launcher, goal 1130.
- Checks and items: 20 chests in 5 maps each sent a check before the goal. Each gave 1 gil, and the real item arrived from the server with a message within 1 second.
- Reconnect: client closed overnight and reconnected. The mod kept the session (17 items applied) and granted nothing twice.
- Goal: story 1130 triggered the goal. Server auto-release sent the remaining 196 items. The mod applied them 5 at a time, every half second, with one message per batch. All 216 were applied, including gil items (9930 -> 13930 gil).
- Blanking restore: after `ffrap_blank off`, chest 2020:1 gave its real item. After `ffrap_blank on`, chest 2020:0 gave 1 gil.
- Sync: `ffrap_sync` reported "0 new checks from 137 known locations".
- Shinies: shinies were disabled, so checks (`shiny:1000:150`, `1000:137`, `2015:4`, `1000:127`) were reported and ignored by the client. Tablet Shard found at map 2020, uid 5.
- Vehicles ([IDEAS.md](file:///c:/Projects/ffresonance-archipelago/IDEAS.md), idea 4):
  - `ffrap_grant item 30002` (Choboco Saddle) enabled riding immediately. Chocobo is gated by item alone.
  - 29520 (Magitek Airship Passkey) is a cosmetic reskin and does not unlock the airship.
  - 30011 (Chocobo Saddle-Bike) produced no visible effect.
- Bug 1, seed name: 0.6.7 client did not store the room's seed name, leading to session key `unknown:0:1`. Fixed by reading seed name directly from `RoomInfo`.
- Bug 2, checks from another save: session started while old save (story 1095) was loaded, reporting `shiny:1000:150` into the new session. Addressed in 0.5.0 via save linking.
- Item names: items 5 and 6 showed as "Item 5" and "Item 6" because they belong to unreleased map 10050. Dropped in world 0.2.0.

Rounds 6 to 9 (2026-11-05) researched and tested the prologue skip; details are in [IDEAS.md](file:///c:/Projects/ffresonance-archipelago/IDEAS.md), idea 2.

**Round 10 (mod 0.7.0, 2026-11-05): per-save item count passed.**
- New game linked automatically. `ffrap_skip 0` ran after the first autosave, linking slot 0 with 0 items.
- Per-save count: saved to slot 3 (`3=0`), then two chests in map 3001 granted Briar Edge and Nodachi. Reloading slot 3 logged `slot 3 holds: 0 applied (was 2)` and granted both again. Saving to slot 4 recorded `4=2`, and loading slot 4 granted nothing.
- Pausing: an older save (slot 1) and a second new game paused as intended.

**Round 11 (mod 0.7.2, world 0.1.3, 2026-11-05): passed.**
Session key included seed number, `/bind` linked an older save, and that save received all items. Title-screen probes ran (see [IDEAS.md](file:///c:/Projects/ffresonance-archipelago/IDEAS.md), idea 6).

**Round 12 (mod 0.7.3, 2026-11-05): title entry works.**
`ffrap_title add` added row 5. Selecting row 5 logged `entry 5` and started a new game.

**Round 13 (mod 0.8.0, 2026-11-05): passed.**
Archipelago entry appeared on the main title menu. Plain New Game paused with a notification pointing to the Archipelago entry. New Game (Archipelago) linked to the seed, autosaved to slot 0 after story 1005, skipped the prologue automatically, and landed at the Earth Shrine.

**Round 14 (mod 0.8.1, 2026-11-05): passed.**
Title menu ordered: Continue, Load Game, New Game, New Game (Archipelago), Options, Quit Game. Version line displayed above 1.0.1.0. Automatic skip executed cleanly.

**Round 15 (mod 0.8.2, 2026-11-05): passed.**
Version text left-justified. HUD layout inspection completed.

**Round 16 (mod 0.8.3, 2026-11-05):**
`ffrap_logo` placed logo on title screen. `ffrap_notice` showed nothing; quest banner dropped in favor of a HUD item feed.

**Round 17 (mod 0.8.4, 2026-11-05): passed.**
Logo integrated cleanly at the end of the version line. HUD layout determined bottom right was clear for the item feed.

**Round 18 (mod 0.9.0, 2026-11-05): crash during initial item feed creation.**
Game crashed on battle result screen with an access violation on the game thread.

**Round 19 (mod 0.9.1, 2026-11-05): crash investigation.**
Feed was still reading legacy configuration. Step logging added.

**Round 20 (mod 0.9.2, 2026-11-05): crash cause identified.**
`tb:SetFont(guide.Text_Name.Font)` crashed due to passing engine-internal `FSlateFontInfo` struct across the Lua boundary. Resolved in 0.9.3 by configuring font object and size explicitly without struct copying.

**Round 21 (mod 0.9.3, 2026-11-05): alignment and visibility debugging.**
Steps ran without crashing, but lines were invisible due to wrong Slate alignment indexing and empty font objects.

**Round 22 (mod 0.9.4, 2026-11-05): root cause of invisible feed.**
`FindFirstOf("WBP_FieldFuncList2_C")` returned an off-screen template widget rather than the active UI instance.

**Round 23 (mod 0.9.5, 2026-11-05): item feed verified.**
Item feed displayed notifications in the bottom right using native `SystemText` font with shadows. Chest items queued during popups and displayed upon dismissal.

**Round 24 (mod 0.10.0, 2026-11-05):**
Item feed enabled by default with adjusted spacing and timing.

**Round 25 (mod 0.10.1, 2026-11-05): passed.**
Silenced unnecessary startup messages. Popup dismissal queue verified.

**Round 26 (mod 0.11.0, world 0.1.4, 2026-11-05): 4-player multiworld passed.**
Tested with Rat1, Rat2, Rat3. Chest popups reflected real contents and sender/receiver names. Gil line hidden. Incoming items queued during menus.

**Round 27 (mod 0.11.1, 2026-11-05):**
Fast checks eliminated popup delay. Identified that reloading older saves previously defaulted to vanilla gil text for scouted checks.

**Round 29, first run (mod 0.11.3, world 0.2.0, 2026-11-06): stopped by idle crash.**
New game skip and 432 chest blanks functioned. Game crashed after idling in menus for 20 minutes with `EXCEPTION_ACCESS_VIOLATION` in `process_simple_actions`.

**Round 29, second run (mod 0.11.3, world 0.2.0, 2026-11-06): root cause identified.**
World-map shinies verified as locations. Multiple crashes observed across different subsystems (`get_string`, `luaH_getshortstr`, `IsA`). Identified memory corruption caused by `LoopAsync` executing Lua callbacks across multiple threads concurrently. Fixed in 0.11.4 by switching all mod timers to `LoopInGameThreadWithDelay`.

**Round 30 (mod 0.11.4, then mod 0.12.0 and world 0.3.0, 2026-11-06): passed.**
- Crash fix confirmed: zero crashes under sustained play across menus, battles, and maps.
- Progression items verified: location names updated; visions granted before Mitra queued safely until story unlocked the menu; key items placed in bag; Archwitch Fina identified as a separate playable unit (1006).
- Probes: trap and NPC gift probes executed ([IDEAS.md](file:///c:/Projects/ffresonance-archipelago/IDEAS.md), ideas 20 and 21).

**Round 31 (mod 0.13.0, 2026-11-07): open world start and scaling evaluation.**
- Starting point established: setting story to 7090 then transitioning to Crystal Tower (map 3280) sets story to 8000, opens the tower, and spawns the airship.
- Airship decided as free from the start; continent gates will use landing restrictions.
- Enemy scaling functioned via `DT_UnitParameter` row patching, but raw exponential curves were overtuned at both ends.

**Round 32 (mod 0.14.0, 2026-11-07): scaling calibration and no-landing box probe.**
- Scaling at `at 80` was significantly improved. Physical attacks hit disproportionately harder than spells due to defense scaling formulas and base stat distributions. Mod 0.15.0 splits knobs into `attack` and `magic` and outputs `scale.txt`.
- Party member additions (`ffrap_grant unit`) worked: units join active party when space permits or roster when full, joining at their native levels (Lid 11, Nichol 19, Archwitch Fina 3, Fina 6).
- No-landing boxes: spawning boxes at flight altitude lifted the airship and broke the camera. Game's native boxes sit on the terrain (Mysidia center z 393). Mod 0.15.0 places boxes at ground level and adds `lock`/`unlock` controls for native continent boxes.

**Round 33 (mod 0.15.0, 2026-11-08): box outlines work; changed conditions need a landing; Pharm lock did nothing; scaling gave the wrong levels.**
- **Outlines:** `ffrap_noland show` draws the boxes. `hide` hides them.
- **Mysidia:** `lock mysidia` and `unlock mysidia` both work, but only after the airship lands and takes off again. The condition is written at once (the log reads it back), so the game reads a box's condition only at some moments: when the box starts, and when the airship lands or takes off.
- **Pharm:** `lock pharm` did not stop landing. The log looks fine. Unlock could not be judged. The likely reason (found off-line): the game's Pharm story box is small. Round 32's box list has it at (-5930, -17400), half-size 473 x 304: about 950 x 600 units, over one spot. It is not a continent lock, so most of Pharm stays open.
- **`spawn`:**
  - The airship kept its normal height (round 32's box lifted it).
  - Landing was blocked at once, with no landing needed. A new box reads its condition when it starts, and the condition was empty.
  - The airship's shadow was gone over the box.
  - `cond {progress:0}<0` (never holds) took effect only after a landing and take-off, as on Mysidia.
- **What the log shows for the boxes:**
  - `show` drew 87 boxes, not the 111 that `list` found in round 32. Some boxes may have no box component, or sit in parts of the map that were not loaded. Not important for now.
  - There is one Pharm story box: `BP_MapNonLandingArea_C_1` at (-5930, -17400), half-size 473 x 304 x 130. That confirms it covers one spot.
  - The spawned box was at (152, 904), on Olderion.
- **Scaling:** enemies in Pharm were level 45 and too strong. The screenshot shows a Metal Gigantuar at level 45. The data dump has it at level 52, and only one unit row has that name. The log explains most of it:
  - `ffrap_scale party follow` worked: party level 3, band 0 to 4, 357 rows changed.
  - **Something else writes enemy rows** (first read as the game; it was the FFR Randomizer mod, see "Off-line, before round 34" below). The first rescale of the run read Steel Bat (ID 2) as level 47, HP 4800, attack 422, EXP 1760. The dump has it at level 1, HP 68. IDs are unique in the dump. So by then the game had already put other values in that row (this save is at story 8000).
  - **A save load undoes our rescale** (wrong too: the randomizer's 3-second rewrite undid it, not the load). After each save load (20:33:05 and 20:33:46), the same `party follow` command had to change 214 rows again. Without a change in between, it would have changed none. `follow` did not notice, because the party level stayed 3.
  - So the level 45 Metal Gigantuar was not our value. Our band (0 to 4) cannot give 45.
  - Afterwards, on the level 52 save (slot 1), follow moved the band to 40 to 44, then `off` restored the rows.
- **Fixed in 0.15.1:**
  - The table check (every 10 seconds on the field) writes our rows back after a load, and logs `scale: the table changed under us`.
  - Our "original" for a row is now the table's latest values, not the first values we read. A row that something else changed since our last write gives a new original, and the log says how many (`something else had changed N rows`, from 0.15.2). So `off` gives back what was there.

**Off-line, before round 34 (2026-11-07): the FFR Randomizer mod wrote the enemy rows, not the game.**
- The dump tool could not run on the laptop (no .NET SDK, no `Mappings.usmap`). The answer came from the installed mods and the full `UE4SS.log` instead.
- Round 33 was the first round on the user's laptop, and the randomizer was still on there: `Mods/FFRRandomizer/enabled.txt` exists, so UE4SS ran FFRRandomizer 1.0.1. Its settings had `enemies=on`, `bosses=on` and `gil_rate=0.25`. At 20:20:54 it logged `Enemies: 225 in random encounters, 222 swapped` and `Applied 6180 field changes`.
- Its enemy shuffle gives a swapped-in enemy the replaced enemy's level, stats, EXP, gil, drops and steals. Its spoiler log for seed 21625644487 has:
  - "Steel Bat (unit 2) fights in place of Nanochu (unit 254)". Nanochu is level 47 in the dump. That is Steel Bat's level 47.
  - "Metal Gigantuar (unit 298) fights in place of Thunder Gigas (unit 186)". Thunder Gigas is level 45. That is the level 45 Metal Gigantuar.
- It writes its whole plan again every 3 seconds. Our rescale at 20:32:26 changed 357 rows. At 20:32:28 it logged `Applied 2147 field changes`: most of our rescale was gone 1.5 seconds later. The 214 rows after each load were its rows, not a reload.
- The chests too: from 20:21:42, one second after the save was linked to the seed, its count went 9, 693, 9, 693... every 3 seconds. That fits our chest blanks and its item shuffle writing the same chest rows in turn. Which value a chest held when it was opened is a matter of timing.
- So there is no sign yet that the game itself changes `DT_UnitParameter`. Rounds 1 to 32 ran on the desktop without the randomizer, so their results stand, round 31 and 32's scaling included. Only round 33's scaling and chest results are affected.
- Fixed in 0.15.2: the mod warns in the log at start, and once on screen when a save loads, if FFRRandomizer is enabled (`enabled.txt`, or `FFRRandomizer : 1` in `mods.txt`). The log text `the game had changed N rows` is now `something else had changed N rows`. IDEAS.md, idea 10 has the details.

**Round 34 (mod 0.15.1, world 0.3.1, 2026-11-07, laptop): scaling holds without the randomizer; Part B not run (no airship).**
- 0.15.2 was not installed yet (the log says 0.15.1). FFRRandomizer was off: no `[FFRRandomizer]` lines.
- **The game does not write enemy rows.** Before any rescale, Steel Bat was level 1, HP 68 and Metal Gigantuar level 52, as in the dump. After a rescale, many save loads and battles, the table check read `367 rows, 0 differ`, and there was not one `table changed under us` line all session. Round 33's rewrites were the randomizer's.
- The level 52 save (slot 1) had Steel Bat at level 1 too. The game's values do not depend on the save.
- `follow` moved the band each time a load changed the party level (3, 1, 3, 4, 3, 53, 8, 3), and the on-screen message named the band ("levels 1 to 4").
- **Feel, in Pharm at party level 3 and band 1 to 4:** `attack 50` felt best. Two caveats from the user:
  - It is not known yet how 50 holds up at higher levels.
  - The bear enemies' skills may be strong on their own. Nearly everything else only cast magic, and that did very little damage.
- **Part B was not run: the airship was gone** on the save used for it. Not explained yet:
  - Round 33's airship tests ran on the same laptop, also without FFRSLib, so FFRSLib's absence alone does not explain it.
  - FFRRandomizer does not touch the airship (nothing in its code does).
  - The user also tried `ffrap_story 8000` on a new Archipelago game (slot 0). The counter changed, but that alone is not the open world start: round 31 went to the Crystal Tower at 7090, and an event there set 8000.
- **Added in 0.16.0: the open world start on an Archipelago new game.** `ffrap_openstart on` makes the prologue skip write story 7090 and an arrival in the Crystal Tower (map 3280) in place of story 1030 and the Earth Shrine. It is the same save, save to slot, reload as the skip. FFRSLib's `ffrs_story_set` and `ffrs_travel` do the same writes, so the mod does not need FFRSLib for it. The arrival is the tower's airship dock, near save point 139. Round 31's arrival point was not recorded, so this spot is a guess from the dump.

**Round 35, first run (mod 0.16.0, world 0.3.1, 2026-11-07, laptop): the open world start did not run, because the switch was off.**
- New Game (Archipelago) skipped the prologue as before: `story counter -> 1030`, `arrival: map 3001`, saved to slot 0 and reloaded at the Earth Shrine.
- The switch was off. `ap_state.txt` reads `openstart 0`, and the log has no line from `ffrap_openstart` at all: the command never reached the mod. The command always logs, so it was not run, or it was typed where the console does not pass it on.
- Nothing on screen tells you either way at the title. This laptop has no ModSettings (`LogicMods` is empty), and the mod's title-screen messages go to ModSettings' Toast. On the field they go to the item feed.
- Fixed in 0.16.1:
  - `ffrap_openstart now` writes the open world start into the loaded save, saves it to its slot and reloads. This needs no new game and no title-screen step. It is what round 31 did by hand: the skip first, then story 7090 and the travel.
  - Choosing New Game (Archipelago) now logs `title: open world start is on` (or `off`).

**Round 35 (mod 0.16.1, world 0.3.1, 2026-11-07, laptop): the open world start works both ways; Mysidia locks and unlocks without landing; the Pharm box was never under the airship.**
- **`ffrap_openstart now`** (slot 0, story 1030, at the Earth Shrine): `story counter -> 7090`, `arrival: map 3280`, saved and reloaded. `story 7090 -> 8000` came 8 to 11 seconds after arriving, after two short cutscenes. Then the player stands at the tower's dock with the airship just below and can board it. It matches round 31's start by hand with FFRSLib.
- **`ffrap_openstart on`, then New Game (Archipelago):** the log said `title: open world start is on`, and the automatic skip wrote story 7090 and map 3280 directly (`story 1005 -> 7090`). The same two cutscenes and `story 7090 -> 8000` followed.
- **The recording (41 s, from the title to the world map):**

| Time | What happens |
|---|---|
| 0 to 2 s | Title, New Game (Archipelago) |
| 3 to 11 s | Opening movie ("A great legend..."), with a Skip button |
| 12 to 19 s | Opening event ("In a bygone era..."), with Auto, Log and Skip |
| 20 to 21 s | Move/Sprint tutorial pop-up |
| 22 to 24 s | Fina on the Battlefield (map 10040, story 1005), autosave; the skip reloads 2 s later |
| 27 to 32 s | Two Crystal Tower events, both skippable; story 7090 -> 8000 |
| 33 s | Control at the dock; "Crystal Tower, recommended level 55" |
| 38 s | World map, in the airship next to the tower: the player boarded (`map 3280 -> 1000` in the log) |

- **What the user wants next:** New Game (Archipelago), watch or skip the opening movie, then the Crystal Tower dock with no Fina segment and no tower cutscenes.
  - The tower cutscenes are story events. What they write should show in a save diff, as the prologue's did (round 6). Then the start can write story 8000 and the rest itself, so the events have nothing to play.
  - The Fina segment is harder. A reload before story 1005 leaves the game with no menus and no movement (round 9), and what holds that lock is still unknown (IDEAS.md, idea 6). Round 36 makes the lock on purpose and probes it.
- **The airship on the old save (slot 3):** `ffrap_airship` read the shipped condition `{progress:0}>=4250`, and the save is at story 8000 on map 1000. The open world start gives a fresh save with the airship, so this save no longer matters.
- **No-landing boxes:**
  - **Mysidia works without landing:** `lock mysidia` + `refresh` blocked landing at once, and `unlock mysidia` + `refresh` allowed it again. `refresh` switches the box's collision on (3) or off (0). The box's collision is what the game's landing check uses. At story 8000 the shipped Mysidia box has its collision off (enabled 0), because its condition `{progress:0}<5020` no longer holds.
  - **Pharm:** `lock pharm` + `refresh` switched the Pharm story box's collision on (3). The landing was tried at (-4968, -17559). The box spans x -6403 to -5457 and y -17704 to -17096, so that spot is about 500 units east of it, and `here` said "under 0 boxes". The box was never under the airship.
  - The Pharm box was not seen, although `show` drew it. It sits at z 110 to 370. If the ground there is higher, the box is buried. That fits the user's note that part of Pharm is too high for the airship. Mod 0.17.0's `here` measures the ground.
  - `show` drew 111 boxes this time, as `list` found in round 32 (87 in round 33).
  - `ffrap_functions CPP_MapNonLandingArea CPP_MapAirShipCanNeverLandingBox`: 0 functions on either class. `find_Landing.txt` names `CPP_MapManager.m_MapNonLandingAreaStorage`, `CPP_MapNonLandingAreaStorage.m_NonLandingAreaList` and `CPP_MapUnit_AirShip.m_NonLandingEvent`. Not needed while the collision switch works.
  - Step 10 (the spawned box) was not run.
- **Added in 0.17.0:**
  - `ffrap_noland here` traces straight down and logs each no-landing box it meets (collision on) and the ground's height.
  - `ffrap_noland spawn [half] [top]`: the box's top can be set (default 1093, the Mysidia box's top). The box stays 1400 tall.
  - `ffrap_skip <slot> force` skips before story 1005, to make the opening's input lock on purpose.
  - `ffrap_input [fix]` logs the player controller's input switches. `fix` runs the engine's resets (`ResetIgnoreInputFlags`, `EnableInput`, `SetInputMode_GameOnly`), logging each step before it runs.
  - `ffrap_inspect <class> [label]` writes `inspect_<class>_<label>.tsv`, so two states of one object can be compared.

**Round 36 (mod 0.17.0, world 0.3.1, 2026-11-07, laptop): the tower events write only the story counter; the Pharm box is not buried; a spawned box blocks landing on Pharm.**
- **Part A, the tower events (snapshots `ow_before`, `ow_dock`, `ow_world`; `tools/snapdiff.py`):**
  - Before (story 1030, Earth Shrine) to the dock after both events: story 1030 -> 8000 (we wrote 7090, the events wrote 8000), map 3280, the player at (-2704.8, -171166.7, 3002.2), and the first visit's bookkeeping for map 3280 (its 14 chests, known and visited). **No event flag changed.** So the events only move the story to 8000.
  - Dock to the world map (the player boarded the airship): map 1000, the player and `Map.airShipLocation` at (-5935, -8305, 2075), `airShipDirection` 2, `IsRidingAirShip` true, event flag 31 on, three chat notices (ATC11, ATC34, ATC55), and the world map's first-visit bookkeeping.
  - So the start can write story 8000 itself and put the player at the dock: the events, which need 7090, do not play. Or it can put the player on the world map in the airship, as boarding did.
- **Part B, the opening's input lock:**
  - `ffrap_input` in the movie, in the locked game (after `ffrap_skip 0 force` at story 1000) and in a normal game: the player controller's move and look switches were false every time. So the lock is not in the engine's controller switches. `ffrap_input fix` ran its three resets; whether movement or menus came back was not reported.
  - `CPP_InputManager` is a world subsystem, made new on each map (the objects were in maps 10040, 3001 and 1000). Its fields hold no state, but it has the functions that matter: `IsEnableInput`, `EnableInput`, `DisableInput`, `GetCurrentInputModeDebugString`, `GetAllIMCStackList`, `ReregistrationCurrentMappingContext` and `RegisterInputMappingContext`.
  - `ffrap_inspect CPP_Task_NewGame` found only the class's default object: there is no live new-game task to read during the movie.
  - `ffrap_find Opening`: the same 6 matches as round 12, nothing new.
- **Part C, ground and boxes (on a chapter 6 save):**
  - Ground heights from the trace: Mysidia 60; Pharm near the story box 34 to 38, rising to 178 and 201 just south of it; Pharm high ground 1031 at (-7717, -16239). Many points read -280 (likely the sea floor), and some hit nothing.
  - Over the Pharm story box, at (-5626, -17203) and (-6114, -17189), the trace hit `BoxComponent` at z 371: the box's top. Its collision was on (3), as its condition `{progress:0}<7020` holds on a chapter 6 save. So **the box is not buried**: it stands 170 to 340 above the ground beside it, over one spot. The user thinks it is where an NPC blocks the path earlier in the game.
  - The trace returns the component, not the actor, so 0.17.0 did not know it as a box and called it "ground at z 371". Fixed in 0.18.0: the box is known by its owner.
  - A box the game has switched on shows profile `AirShipCanNeverLanding`; the switched-off Mysidia box showed `Custom`. A spawned box shows `AirShipCanNeverLanding` too. Our `refresh` only switches the collision, and that was enough on Mysidia in round 35.
  - **A spawned box blocks landing on Pharm at once:** at (-4199, -17190), ground z 34, the log shows half-size 200. The airship's shadow was gone over it, as in round 33.
- **Added in 0.18.0:**
  - **The open world start without the tower events.** `ffrap_openstart` now has three arrivals: `dock` (the default: story 8000 at the dock), `air` (story 8000 on the world map, riding the airship beside the tower, flag 31 on) and `event` (story 7090 at the dock, so the events play, as before).
  - `ffrap_input` also logs the game's input manager: `IsEnableInput`, its input mode and its stack of mapping contexts. `fix` first calls the manager's `EnableInput` and `ReregistrationCurrentMappingContext`, then the engine's resets.
  - `ffrap_noland here` knows a no-landing box by the hit component's owner.
  - `ffrap_noland channel <n> <0|1|2>` sets the spawned boxes' response to one collision channel: a probe for the missing shadow.

**Round 37 (mod 0.18.0, 2026-11-08): the air start is the choice; the input lock survives every reset; the broken title rows are our bug.**
- **Part A, the start with no events:**
  - `dock` and `air` both worked. Story 8000, no cutscenes, "Chapter 8 - Beyond Hope" at the dock.
  - **The user prefers `air`.** Mod 0.19.0 makes it the default.
  - The arrival was not kept over a restart. `air` was set at 12:40, the game restarted at 12:44, and the next start came up at the dock. Fixed in 0.19.0.
  - The user wants a welcome window on a new game, later (IDEAS.md, idea 22).
- **Part B, the opening's input lock:** a forced skip reached the airship, but no `ffrap_input fix` step helped, and the user had to quit with Alt+F4.
  - In the movie: pawn `BP_MapUnit_Player_C`, input manager enabled, 2 mapping contexts.
  - In the locked game: pawn `BP_MapUnitAirShip_C`, input manager enabled, 1 mapping context, move and look not ignored. The fix's five steps ran without an error and changed nothing.
  - The contexts logged as `LocalUnrealParam: 00000000713B9288`, so their names were lost. The elements are wrapped and need `:get()`. Fixed in 0.19.0.
  - Slot 3 was loaded afterwards, but `ffrap_input` was not run there, so there is no normal game to compare.
  - So the lock is not in the engine's switches or the manager's `EnableInput`. The cost of leaving it: the player waits for story 1005 or skips the movie by hand, about 10 seconds. Not worth many more rounds.
- **Part C, the shadow:**
  - `spawn 2000` at (-3927, -17437), then `channel 3 0`, then `channel 4 0`. The user went on to channel 4, so channel 3 most likely did not bring the shadow back. The log cannot show the shadow, and the result was not reported.
  - `here` at (-5857, -17263): the trace now passes the spawned box and hits `Landscape_1` at z 115. The trace is on channel 3, so the channel change worked. The shadow does not depend on that channel alone.
  - The plan's step 13 could not work. At story 8000 the Pharm story box's condition `{progress:0}<7020` is false, so its collision is off (enabled 0), and a trace passes it. The step needs a save before story 7020.
- **Off-line after the round:**
  - **The shadow has its own ignore list.** `CPP_MapUnit_AirShip` has `m_ShadowDecalSphareTraceActorsToIgnore`: a sphere trace places the shadow decal, and this list holds the actors it passes through. A sphere trace can test object types, which response channels do not change. Mod 0.19.0 adds `ffrap_noland shadow`.
  - The custom channels, from `DefaultEngine.ini`: 14 Env_Train, 15 NPC, 16 Minimap, 17 DitherObject, 18 PingerPoint, 19 Pinger, 20 MinimapRecive. Channels 3 and 4 are Visibility and Camera. The profile `AirShipCanNeverLanding` ignores Pawn, Env_Train, PingerPoint and Pinger.
- **Other notes from the user:**
  - **Broken title rows:** at random and rarely, every row but ours read `<MISSING STRING TABLE ENTRY>` until a restart. **Cause, from the code:** `OrderTitleEntries` reads each label as text and writes it back as plain text. A label read before its string table has loaded gives the placeholder, and we then saved the placeholder as the label. The first check runs about half a second after the mod loads, so it was a race. Fixed in 0.19.0: the order waits until every label has its text, with the map untouched.
  - **Active Time Chats should all be marked complete.** The save has `chat.DataMap` (one row per chat, with `IsReleased` and `IsAlreadyPlayed`), `chat.NoticeQueue` and `chat.LatestNotice`. Mod 0.19.0 marks all 56 on an open world start.
- **Seen in the log:**
  - **Vision items wait for good on an open world start.** `item 8 vision 13017 x1: waits (the save owns no vision yet to copy synchro keys from)`. The story gives the first visions in Mitra, and the open world start skips that. `ffrap_visions` (0.19.0) logs the keys on a save that has visions, so the mod can write them with no entry to copy.
  - `client: world version 0.3.0` and an `ap_in.txt` dated 2026-11-06: the client was not running. The 25 items came from the old bridge file. This does not affect the results.
- **Tools added:** `dump_game structs <regex>` prints the fields of any class or struct from the usmap. `dump_game raw <path>` writes files such as the game's ini files to `dump/raw`.

**Round 38 (mod 0.19.0, 2026-11-08): the chats stay done; the shadow's ignore list gives the red shadow; the input manager looks the same in a locked game.**
- **Part A, the air start and the chats:**
  - The start worked, and none of the chats fired. `active time chats: 56 of 56 released and played (56 rows added)`, then `56 rows, 56 released, 56 played; notices [], latest None`.
  - In the chat list some entries are greyed out, because the party members they need are not in the party. That is the game's own `RequiredUnitList` and is fine.
  - The first New Game of the session went to the Earth Shrine: `ap_state.txt` had been cleared, so `openstart` was off. A fresh install does the same, so the seed should decide this.
  - Step 6 (the arrival kept over a restart) did not run: the log has one mod start. The test suite covers it.
- **Part B, the shadow: solved.** Over a spawned box the shadow was gone. `ffrap_noland shadow` brought it back, red. Landing stayed blocked. After `off` the shadow went black and landing worked.
  - The game fills the list itself: 114 entries, which are the airship, 111 no-landing boxes, `CPP_MuchaWorldSetting` and `StaticMeshActor_2`. So a box that is on the list looks exactly like one of the game's own.
- **Part C:**
  - `ffrap_visions` on a chapter 6 save: 21 visions, keys `[1001, 1002, 1003, 1006, 1004, 1005, 1007, 1008]`. These are the eight party members. Mod 0.20.0 writes them itself, so a first vision no longer waits.
  - `ffrap_input` shows `MUCHA_INPUT_MAPPING_CONTEXT_DATA`, 1 context, input enabled, in a normal game and in the locked game alike. (The name printed is the context's type, so two different contexts could still look the same.) So nothing we can read tells a locked game from a normal one. **Parked:** the cost is about 10 seconds per new game (IDEAS.md, idea 2).
- **The title rows** were fine. The race is rare and did not happen in this log (`rebuilt` on the first try), so this is not proof yet. Watch for the `has no text yet` line.
- **Seen in the log:** loading slot 1 with no session logged about 90 `check` lines. This is by design: with no seed every save counts (fake_ap.py testing). The client drops any `ap_out.txt` line that has no matching `seed` line, so nothing reaches a server.
- **Added in 0.20.0:** `UnlockVision` writes the eight keys and no longer needs an owned vision. `ffrap_noland spawn` lists its box for the shadow by itself. `shadow` adds only boxes not listed yet and logs only the entries that are not the game's own boxes.

**Round 39 (mod 0.20.0, 2026-11-08): visions were in the save but not usable; the red shadow lasts through boarding; the airship vanished after a town.**
- **Part A, the first vision:**
  - `vision 13017: ok (visionList 0 -> 1, synchro keys 8, HasVision true)`, and the same for 13128. So the grant works with no vision to copy from.
  - No vision could be equipped, and no menu showed them. Leaving the Equip screen still warned about party members with no vision. Saving and reloading did not change this.
  - In the log, `visionList 0 -> 1` a second time at 13:23:57 is from loading slot 0, the save written before the first grants. It is not a bug. The later save was slot 4.
  - **Cause, off-line:** the Equip screen shows visions only with **event flag 24** on (`DA_ActionEquipment.VisionEnableFlagIdData`). The story turns on flags 21 and 24 at Mitra (`C01_014_04`, story 1090). The warning comes from a separate check that only counts owned visions, which is why it fired.
  - The menu's other gates, from the same assets: 14 Equipment, 16 World Map, 18 Recovery, 19 Party, 26 the main menu (all already on), and **34 fast travel (off on our start)**.
- **Part B, the box over time:**
  - The shadow was red at once with no `shadow` command, and landing was blocked. Landing elsewhere and boarding again kept the red shadow and the block. So the listing lasts through boarding.
  - **Going into a town made the airship disappear** (`map 1000 -> 2170 -> 1000`). So steps 9 and 10 could not finish, and whether a spawned box lasts through a map change is still unknown.
  - **Cause, most likely, off-line:** the save has `Map.IsAlreadySpawnAirship`, and our start never set it. While the airship was being ridden it did not matter. After a map change the game has to place the airship again. `DT_MapAirShip` names `initSpawnPointId` 9000 for a first placement, and no map or landing table has a point 9000. This also fits round 34's unexplained missing airship.
  - **No key item is involved:** the airship's only condition is `{progress:0}>=4250`, and no item in the data unlocks it.
- `GameSaveData*.sav` files begin with `SVHD` and hold no readable field names, so saves can be compared only through `ffrap_snapshot`.
- **Added in 0.21.0:** the open world start turns on flags 21 and 24 and, for the `air` arrival, sets `IsAlreadySpawnAirship`. `ffrap_airship state` logs the airship's save fields.

**Round 40 (mod 0.21.0, 2026-11-08 and 09): visions work; the airship stays; a box does not last through a map change.**
- **Part A, equipping visions:** all worked, with no issues. Both visions could be equipped, battles were fine, and the equipment survived a save and reload. So flags 21 and 24 were what the Equip screen needed.
- **Part B, the airship:** `IsAlreadySpawnAirship` was the cause. The airship stayed in every case: towns (2070, 2090) and a save and reload. `ffrap_airship state` after landing read `placed true, riding false, at (-4109, -17108, 77), direction 4, island 9`, and later `island 5` over Olderion. So the game keeps the island by itself.
- **A spawned box is gone after a map change.** It had to be spawned again after each town. When spawned again it worked (red shadow, no landing). So the locks must place their boxes on every world-map load.
- **Also in the log:** `ffrap_scale` with `follow` on two saves moved the band with the party level (1 to 3 and back).
- **Off-line after the round:**
  - Each continent has its own landscape level (`Wld_<code>_landscape_BG`). Plotting the landscape tiles with every landing point and exit gave a clear map.
  - Landing point ids are not a safe guide to a continent: some are dungeon map ids (3111 is in Olderion, 2190 in Pharm), and `maps.tsv`'s island column is wrong for sanctums. Position is the safe guide.
  - The 21 rectangles in `G.CONTINENTS` place every landing point and exit in exactly one continent, except the Crystal Tower's exit (in none).
  - Event flags 1414 to 1449 are used nowhere in the game's data.
- **Added in 0.22.0: the continent locks.** `ffrap_lock on` keeps a set of boxes on the world map for every locked continent, placed again after each map change, and listed on the airship for the red shadow. A continent's lock is an event flag in the save (1420 to 1429, on means open), so an unlock stays with its save. `ffrap_lock open|close <continent|all>` writes the flag.

**Round 41 (mod 0.22.0, 2026-11-09): the locks hold everywhere; boarding after a map change crashed the game.**
- **Part A, all locked:** the shadow was red everywhere and no landing worked. `show` drew 132 boxes (111 of the game's and our 21), and the screenshots show them where they should be. No problem was reported over high mountains.
- **Part B, opening one:** `open pharm` worked within a second. Sian, the boxes coming back for the other nine and the rest worked. Then, boarding the airship to run step 9, the game crashed.
- **Part C, on foot in a lock:** closing Pharm on foot worked, and walking and battles were normal. Boarding the airship crashed the game, with the boxes visible.
- **Part D:** `ffrap_lock off` removed the locks at once.
- **The two boarding crashes are one bug** (`tools/crashstack.py`). Both read address `0x18` in a UE4SS `UObject` member call, under three Lua `pcall`s from our tick. `0x18` is an object's name field, so a null object was asked for its name. The only objects `ContinentSync` names that are not already checked are the entries of the airship's shadow list. So that list held a null entry the first time we read it on a newly boarded airship. An access violation goes straight through `pcall`. Fixed in 0.23.0: `ObjText` asks `IsValid` first. Each listing now logs how many entries are null, to confirm this.
- **The third crash, on load (07:59:03), is not from the locks.** The stack is `RemoteUnrealParam::construct` in UE4SS's `InitGameState` hook. Our mod has no such hook; among the enabled mods only FFRSLib registers one, and FFRSLib also runs `LoopAsync` timers. Round 29 showed that this kind of thread race crashes at random. It did not come back on the next start. It is not proof, but nothing from the crash on boarding could carry over: the mod keeps its boxes only in memory.
- **Boxes placed twice on the way back from a town** (07:53:20 and 07:53:23): the first set went in while the world map was still arriving. Boxes now wait for three syncs (about 3 seconds) with one controller.
- **Added in 0.23.0:** the null check, the wait, `locks: N boxes on the airship's shadow list (a -> b, k null)` in the log, and the list is taken again if its length changes.

**Round 42 (mod 0.23.0, 2026-11-09): no crashes; a save loaded in the air can land in the first seconds.**
- Every crash path ran with no crash: boarding after a town, closing a continent on foot and boarding, and save and reload.
- **The null entries are confirmed.** The first listing on a new airship often found an empty list (`0 -> 18`). A later one read `162 -> 162, 27 null` and `156 -> 156, 24 null`. So the game fills the list after the airship appears, and it holds nulls. Round 41's crash was one of those being asked for its name.
- `opened pharm` and `boxes placed for pharm` each worked within a second.
- **A gap on load:** after loading a save made in the air over a locked continent, the user could land in the first second or two. The boxes came about 2.5 seconds after the save was seen (08:14:02.6 to 08:14:05.2): the field HUD has to appear, then the sync waits to settle. A player could use this to cross any lock.
- **Added in 0.24.0:** the boxes go in from the engine's `LoadMap` post hook. That runs before the first frame of the new map, so there is no moment without them. The one-second sync stays, to repair anything that differs and to fill the airship's shadow list.

**Round 43 (mod 0.24.0, 2026-11-09): the continent locks are done on the mod side.** The user reports no issues at all with the plan's steps, including landing straight after loading a save in the air. The locks go in during the map load, from the `LoadMap` post hook.

**Added for round 44 (mod 0.25.0, world 0.4.0): a real seed.** Written off-line, and tested by the suite and ten real generations (each starting continent, shinies on and off).
- **Continent logic.** A seed starts with one continent's Unlock item. The others are in the pool and open their continents. The logic has one region per continent. Which continent a chest is on comes from position where the map exits say so (Dragon's Maw opens on Pharm, not Grandshelt), and otherwise from its table. The Crystal Tower and the goal need every unlock.
- **Places with no open world route hold filler only:** the Earth Shrine's inner part (3000), the burning castle (3020), the Imperial Residences (2113) and Fina's Psyche (3211, 3212). Found from the exits and the talk event table, not from play.
- **A starting party from the yaml.** `starting_roster`, then `starting_character_1` to `_4`, each a weighted choice. A repeat becomes someone not chosen. Everyone else is in the pool, Rain and Lasswell included.
- **What makes a non-standard start safe, from the data:** the party, join status and starter gear are all set by the skip. Rain and Lasswell are named by story events only (`OverwriteBattleParty`, chats), which this start skips. Archwitch Fina is reset by the skip and gets her first ability back when she is a starter.
- **Round 44, first look (mod 0.26.0):** the custom party started fine, but Jake was level 27. Everyone now starts at level 1 with HP and MP filled, through the game's own `SetPlayableUnitExperience`, and a member received later joins at the party's average level.
- **The seed now decides the start.** The client writes `cfg openworld 1` and `cfg party ...`. So no console commands are needed, but the client must be connected before New Game (Archipelago). `ffrap_lock off` in the same run still wins over the seed, for testing; an `off` saved from an earlier run does not.

**Round 44 (mods 0.25.0 and 0.26.0, world 0.4.0, 2026-11-09): the first real seed. Continent logic, the custom party and level 1 starts work; story state still gets in the way.**
- **Worked:** Jake and Archwitch Fina as the party, level 1 starts with sensible HP, Grandshelt open and the rest locked, an Unlock opening Gronoa, visions, chests, and `follow` scaling.
- **The Earth Shrine would not let the party leave.** `C01_Dng01Gra43_NoEntry_01` holds while flag 102 is off. Flag 102 comes from the event `C01_010_02`. Fixed in 0.27.0.
- **Other story no-entry zones that are active on this start (from `gimmicks.tsv`, not yet seen in play):** Nameless Ruins (3180, flag 520, a barrier sidequest), Sanctissimus Shrine (3250, flags 617 to 620), Olderion city (2070, story 3130 and up). Round 45 can look at them if the player reaches them.
- **Fast travel did not work.** `Tutorial_FastTravel` sets flags 1180, 13 and 34, and 34 is what the Map screen checks. Fixed in 0.27.0.
- **Crash entering the airship interior** (map 20001, during the sidequest Last Respite). The stack is one `pcall` deep under UE4SS's `process_simple_actions`, reading a stale object. Our mod uses timers from `LoopInGameThreadWithDelay`, not `ExecuteInGameThread`, so this is another mod's callback. FFRSLib's `RegisterLoadMapPostHook` is the best fit: it keeps the world and uses it 1.5 seconds later, under one `pcall`, and the crash came about 2 seconds after the map change. A quest that changes map twice would leave it a dead world. Not proven: round 45 tries the same thing with FFRSLib off.
- **Rain, received from the pool, got no EXP, and gear on her did not count as equipped.** `AddUnit` adds a unit to the party list and leaves `JoinStatus` at NotJoin. The starters go through the skip, which sets it. Fixed in 0.27.0: every join sets `JoinStatus` 0, `IsUsable`, and puts the unit's own gear in the bag. Saves from this round keep the problem.
- **The save slot showed level 1.** The slot's `PlayLevel` appears to be Rain's level (the user's reading; party was level 10). While she has not joined, 0.27.0 keeps her level at the party's.
- **Walking between continents crosses a lock:** Grandshelt to Lanzelt on foot. Not urgent. The user suggests a gate, or removing the bridges if that is possible.
- The Earth Shrine's inner part (3000) was opened in play, so world 0.4.1 takes it off the filler-only list.
- Enemy scaling with `follow` still works in a seed.

**Round 45 (mod 0.27.0, world 0.4.1, 2026-11-09): new seeds; the fixes held, and more story state turned up.**
- Rain and Fina, received from the pool, joined and levelled up with the party (the log shows `1002:6 1001:6`). The airship interior did not crash in three visits. Last Respite was not tried again.
- **The moogle's Vision Enhancement screen has no way out with no vision owned** (the game was restarted). It opens from three talk events, all `BP_VisionUpgradeEntry`. Mod 0.28.0 makes those rows do nothing until the first vision arrives.
- **Tutorials:** the user wants them all off. Every `Tutorial_` row turns on one "seen" flag, in 1160 to 1199 and 1217 to 1229, and tutorials in battles and on maps test that flag. Mod 0.28.0 turns them all on. A few are chained from story events with no test, but those events do not run on this start.
- **Staggering did not work.** Flag 25 is set in `C01_008_02`, the Earth Shrine boss, where the story teaches it. The game's `Setup` start row has it on. Fixed in 0.28.0.
- **Fina could not summon.** `C01_037_01_Choice_After`, after Siren, sets flags 28 and 90. Flag 28 is the summoning, set in 0.28.0. Flag 90 is Siren herself: the other espers have 91 to 98, set when you earn them. Her fight is a story event, so world 0.4.2 makes "Siren (Esper)" an item. A fight on the map is for later, with the other story bosses.
- **Chests with Magicite were not locations.** 17 of the 21 kept chests hold it. World 0.4.2 shuffles those, and the mod blanks them. Resonance Stone and Adamantite stay.
- Twice `chest pop-up ...: no chest pop-up on screen` was logged (chests 2020:0 and 2020:1), so those two kept the game's own text. Nothing else went wrong with them.

**Next, as the user asked:** replace what shinies give, and make the vision crystals into checks that skip the summoning scene (IDEAS.md, idea 23).

**Round 46 (mod 0.28.0, world 0.4.2, 2026-11-09): tutorials, staggering, the moogle and Magicite chests work; Siren did not appear.**
- **Worked:** no tutorials except the opening's, before the first autosave. Staggering works. The moogle's menu stays shut with no vision and opens with one. The Siren's Tower Magicite chest worked as a check.
- **Spare gear on join:** a member who joins keeps their gear on and also got a copy in the bag. The bag copy came from 0.27.0's `FinishJoin`; the earlier equip problem was `JoinStatus`. Removed in 0.29.0.
- **Siren:** received as an item, flag 90 on, and not in the summon menu; Ifrit, earned in play, was. Found off-line: an esper is an ability. The event rows' `AbilitySettings` add it to both Finas (`AddAbilities [6, 430980]`, `AddCommandAbilities [6]` for units 1003 and 1006, in `C01_037_01`). 6 is the summon command and 430980 is Siren. As the user suggested, 0.29.0 gives her to both Finas on an open world start, and the item is gone (world 0.5.0).
- **Added in 0.29.0, world 0.5.0, not yet played:**
  - **Shinies:** a shiny that is a location now gives 1 gil, like a blanked chest. Its `m_ItemId`, `m_ItemNum` and `m_Money` are rewritten on the actor, before the map settles. Only with `include_shinies` (cfg `shinies`).
  - **Crystals:** the 16 sanctum crystals are locations with `include_crystals` (cfg `crystals`). Each opening row (`Int_LegendEV_NN_01`, `_01_Short`) jumps to `_07`, and `_07` keeps its flags and gives nothing. All three are set to Blueprint rows with no Blueprint, which should play nothing. The flag is the check. Not proven: that an empty Blueprint row still applies its `OnFlagList`.
  - The other 10 visions come from sidequests and one boss (`Str_LegendEV_07_Boss`), and still hand out their own.
- **Added in 0.30.0, world 0.6.0, not yet played:** the 99 shinies holding a Tablet Shard are locations with `include_tablet_shards` (cfg `shards`), and the shards are in the pool. Their continent comes from the map's exits, else from its code (`01Gra_02`). Airship and common maps count as open from the start.

**Round 47 (mod 0.29.0, world 0.5.0, 2026-11-09): crystals, shinies, Siren and joins all worked.**
- **Crystals worked as designed:** the scene was skipped, the flag set, and the check went out (`check crystal:10202`). So a Blueprint row with no Blueprint is a no-op that still applies its `OnFlagList`.
- **Shinies** gave 1 gil. **Siren** was in the menu for both Finas. **New members** kept their gear with no copy.
- **Asked for:** shinies should show the Archipelago item in the pop-up, as chests do. Added in 0.31.0: a shiny is scanned when a pop-up opens, and rewrites it the same way. Off-line, `DT_DialogBox_Item` shows the two "You obtained" messages are rows of the same dialog table, so a shiny should use the box the chest code knows. Not yet seen in play. If the game marks a shiny as taken only after its box closes, the text will not change, and step 1 below will show it.
- **MRP was not scaled.** A later continent gave far more. It is not on the enemy: it is `ap` in `DT_BattleGroup`, one value per battle. Mod 0.31.0 scales it from the battle's enemies' average level, on a curve fitted to the shipped groups (459 groups without a boss, r2 0.70). A level 45 battle at party level 3 gives about 6% of its usual MRP.

**Round 48 (mod 0.31.0, world 0.6.0, 2026-11-09): a clean multiworld session. One trap left, at the moogle.**
- **No crashes or other issues** in a 40-minute session over 3 continents, in a multiworld with an automated second slot. Three seeds were started in the log.
- **Shiny pop-ups work.** World-map, town and dungeon shinies logged `chest pop-up for shiny:...: text set, item line hidden`. One check had no pop-up line (`shiny:1000:189`). The timing question from round 47 is closed: the game marks a shiny as taken while its box is up.
- **MRP scaling runs** (`MRP changed in 470 battle groups` at party level 1). The user reported no problem with it.
- **Crystals, Unlock items, party starts and the reload** all behaved. Loading slot 2 rolled the applied items back from 36 to 34 and gave items 34 and 35 again, as designed.
- **The moogle's Vision Enhancement screen would not close** with 2 visions and no usable Magicite. It closed once the player held a Magicite Shard. The user asked if a story tutorial is behind it.
  - **Found off-line:** `WBP_VisionUpgradeLayout:IsClosable` and the list layout's `IsClosable` return false unless the native `CPP_BFL_VisionUpgrade:IsVisionUpgrade` returns true. The layout's `Handle_SyncActionGuide` calls it too. The function's body is native, so what it tests is not known. Play suggests "can the player enhance a vision now", or a tutorial lock of that kind.
  - **Upgrade costs:** `DT_VisionUpgradeItemData` needs item 25000 (Magicite Shard) for level 1, 25001 (Magicite) for level 2, 25002 (Magicite Cryst) for level 3. So a new vision cannot use a Cryst. The two seeds played in the log each gave a Cryst and no Shard.
  - **Fix, mod 0.32.0:** a post hook on `IsVisionUpgrade` answers true in a seed. Not yet seen in play. The hook logs the game's own answer whenever it changes, so round 49 also shows what the function really tests.
- **Noted, not a problem yet:** the airship's shadow list grows while the player picks up world-map shinies (`130 -> 154 -> 178 ...`), and the new entries are null. A map change resets it. The mod's list code asks `IsValid` first, so nulls are safe for it.
- **Tool added:** `DUMP_BYTECODE=1 dotnet run --project tools/dump_game -- assets <path>` also writes each Blueprint function's code, which is how `IsClosable` was read.

**Before round 49 was played (2026-11-09):** the user moved enemy scaling out of the yaml, as it suits in-game sliders better (IDEAS.md, idea 18). The default for a seed is now party sync with follow, HP and power at 75%, bosses too.

**Round 49, first try (mod 0.35.0, world 0.8.0, 2026-11-09): the boss test ran the old revisit.**
- **The seed's scaling started by itself:** `clamp -1 3, hp 75%, attack 75%, magic 75%, with bosses`, with `MRP changed in 598 battle groups`, and it followed the party to level 3.
- **The shard counter works:** `Received Tablet Shard (1/50) from Rat`.
- **The boss test armed without errors:** group 9013's own events were read (start -1, win `C01_037_01`), and 64 crystal rows, 2 fight rows, 2 win rows and the group were written. Two of each because the composite table and its parent table both hold the rows.
- **But touching the crystal asked to revisit the vision.** The player was in map 10231, the Sanctum of Cecil: the inner room of a crystal already claimed (10211). A claimed crystal runs `Int_LegendEV_Retry_Start_04_01`, which the test did not change. Mod 0.35.1 changes its "yes" row too.

**Round 49, second try (mod 0.35.1, 2026-11-09): "yes" did nothing.** The test armed (96 crystal rows), the vanilla revisit no longer played, but no fight started, and touching the crystal again asked again. The guess, and the change in mod 0.35.2, are in IDEAS.md (idea 25). Also found while looking: FFRS_QoL is installed, and it writes the same MRP field as our scaling (idea 18).

**Round 49, third try (mod 0.35.2, 2026-11-09): still no fight.** The log shows the test armed and the `Encount` hook in place, but no `the game asked for a battle` line. So the chain stops before any battle is asked for, or event battles start some other way. Mod 0.35.3 adds a watcher to find out (IDEAS.md, idea 25).

**Round 49, fourth try (mod 0.35.4, world 0.8.1, 2026-11-10): no fight, even with the row's own group.** Group 9957 (the Twelve Arms fight the test borrows) failed like 9013, so the problem is the borrowed row, not the boss. The watcher hooked 29 functions with no crash. A normal random battle showed only as a move to map 20001; it never called `CPP_MapManager:Encount`. Around the crystal only `CPP_TalkEventManager:OnFinishFade` ran. So hooks do not see the game's event and battle code. Mod 0.36.0 tries chests as the trigger instead (IDEAS.md, idea 25). Also seen: the shard counter, the seed's scaling and the shiny pop-ups all still work on world 0.8.1.

**Round 49, fifth try (mod 0.36.1, world 0.8.1, 2026-11-10): the pedestal started Siren.**
- **The sword pedestal works as a boss trigger.** With 9957 it was the sword fight, and with 9013 it was **Siren**, on her own stage. Both wins logged `boss test: WIN seen`. A loss gave the normal game over: Retry, Load or Return to Title.
- **Both wins ended on a black screen**, and the game had to be closed. The after-win row was a Blueprint row with no Blueprint; the game's own after-win rows are all Sequence rows. Mod 0.36.2 changes that (IDEAS.md, idea 25).
- **`ffrap_scale` by hand still wins over the seed:** the user set `hp 200 power 200` to lose a fight on purpose.
- **A crash, on an older mod (0.35.x), leaving the Rugged Mountain cave in Gronoa to the west.** `tools/crashstack.py` shows an access violation in UE4SS's `FName::ToString`, called from a Lua game-thread tick (`process_simple_actions`) through a UObject handle's metamethod. So a tick asked an object for its name after the object was freed. A map load frees the old map's objects, and `G.Live` caches the map manager, which is asked every tick. Mod 0.36.2 forgets cached objects in the `LoadMap` post hook. Not proven to be the cause; if it happens again, send `UE4SS.log` too, so the last lines show what the tick was doing.

**Round 49, sixth try (mod 0.36.2, world 0.8.1, 2026-11-10): a boss from the pedestal works end to end, and a chest starts one.**
- **Pedestal, default win row:** Siren, a win, the sword fight's victory scene (it says the weapon was upgraded, though no item was given), and back in the Chamber. `boss test: WIN seen`.
- **Chest, `quiet`:** a closed chest in map 3050 started Siren. The chest's check went out (`check chest:3050:2`), but its pop-up was missed, as the battle came instead. After the win the screen stayed black. `quiet` used `choice_cancel`, a Sequence row with no sequence. So an after-win row needs a real sequence. Mod 0.37.0 makes `quiet` use the magic pots' short after-win scene.
- **Other answers:** the shard counter counts up in the item feed (no seed finished yet). The moogle's Vision Enhancement screen shows its close button; not yet seen with no Magicite Shard at all.
- **Scaling:** 75% felt good early, but enemies got far too easy from about party level 20, and bosses were too easy all along. The user wants bosses on their own setting, at 100% by default, and to be a real gate. Mod 0.37.0 ramps enemies and gives bosses their own band (docs/open_world.md, section 5).

## Round 50 test plan (mod 0.37.0, world 0.8.1)

Seeds can now be finished, and a seed scales its enemies by itself. Send the `[FFRAP]` lines of `UE4SS.log`.

**Install:** copy `FFRArchipelago/Scripts` over the installed mod. If you have not installed world 0.8.0 yet, copy `dist/ff_resonance.apworld` into `custom_worlds` and **generate a new seed**. Connect the client first, then New Game (Archipelago). Do not type `ffrap_scale`.

For a short test, add this to your yaml. The default is 50. Shards turn on by themselves with this goal, so `include_tablet_shards` is no longer needed.

```yaml
  tablet_shards_required: 10
```

1. After the start, the log should say `scale: the seed's scaling is on`, with `hp 75%, attack 75%, magic 75%, with bosses`. **Is that a fair baseline?** Note how it feels early, and again later if you can.
2. Receive a Tablet Shard. **Does the item feed say `Tablet Shard (1/10)`?**
3. Receive the last one you need. **Does the game say `Goal complete!`, and does the server show your slot as finished?**
4. The moogle: have a vision and no Magicite Shard (a Cryst alone is a good test). Open Vision Enhancement and press Cancel. **Does the screen close?** Then get a Shard and enhance a vision. Does the screen still work and close after?
5. Send the `vision screen:` lines of the log. They show what the game's own check answered.

**Install:** copy `FFRArchipelago/Scripts`. Your seed still works.

**1. Scaling.** No command needed. After a load, the log shows a line like `scale: party level 29 (...): enemies centre 26 (90%), power 100%; bosses centre 29, power 100%`. Play as usual. **How do normal enemies feel now, at your level?** And if you fight a boss, how does it feel at 100%?

**2. A quiet boss from a chest.** Save in a spare slot. Next to a closed chest, `ffrap_bossfight 9013 quiet`, then open the chest. **After the win, does a short scene play and bring you back to the field?** If it is black again, wait 10 seconds, then close the game. Send the `boss test:` lines. `ffrap_bossfight off` when done.
