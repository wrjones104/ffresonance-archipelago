# Playtesting archive

Completed in-game test rounds and results moved out of [docs/playtesting.md](playtesting.md). Open checks that still need to be tested live in [docs/playtesting.md](playtesting.md); automated suite tests are in [tests/README.md](../tests/README.md).

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

**Round 50 (mod 0.38.0, world 0.9.0, 2026-11-10): settings work; the Options screen draws our rows.**
- **Settings by console worked:** EXP, MRP, encounters off and on, and the encounter rate all did what they say. The log shows 3 rate rows and 64 to 84 map rows in 13 tables written.
- **The Options probe worked:** "Archipelago test switch" and "Archipelago test slider" showed at the end of the Gameplay tab, in the game's style. No crash.
- **Artifacts:** the sync ran (`artifacts: added to the artifact list: 30000, 30001, ...`), but there is still no Artifacts tab, and the Cuff Links in the bag (x2) cannot be used. On a new game the bag already holds five artifacts before any item: bonus items, so the second Cuff Links came from the seed. The Items screen has no Artifacts tab in its tab list at all (IDEAS.md, idea 26).
- **A trapped chest in a town did not start a fight**, with either win row. Round 49's worked in a dungeon (IDEAS.md, idea 25).
- **The ramp shows in the log:** party level 31 gave "enemies centre 28 (90%), power 100%"; level 7 gave 81% and 78%. The user will judge the feel over a longer game.

**Round 51 (mod 0.39.0, world 0.9.0, 2026-11-10): rows show, values do not arrive; the Cuff Links can be turned on.**
- **Options rows:** `ffrap_menu add` put the six rows in, and they could be changed and applied. But EXP, gil and MRP at 10 gave normal rewards, and the log has no `settings: from the Options screen` line. So the values never reached the mod (IDEAS.md, idea 18).
- **Artifacts:** `ffrap_artifact 30010 on` showed chests on the mini-map. `off` did not take them away, even after a map change. The user found the game's own switch: the Magitek Airship Passkey, a key item with OFF/ON in the Items screen. Artifacts have no icon and show only in the All tab. The Chocobo Saddle-Bike looks unused in the main game (IDEAS.md, idea 26).
- **A trapped chest in a dungeon** (map 3000) started Siren. The user lost, so the after-win scene is still unseen.

**Round 52 (mod 0.39.1, world 0.9.0, 2026-11-10): a chest boss works end to end.**
- **Chest boss:** in a dungeon (map 3000), `ffrap_bossfight 9013 quiet` and a closed chest gave Siren, a win (`boss test: WIN seen`), and the field again.
- **Menu values:** `ffrap_menu dump` showed our six values pending while Options was open, then none after Apply, and none in the option save (97 entries). The game only updates entries it already has (IDEAS.md, idea 18).
- **Artifact switches:** 19 behaviour entries went in, but no switch showed; the artifacts stay greyed out in the All tab. The passkey shows its switch there too, so being a key item seems to be what matters (IDEAS.md, idea 26).

**Round 53 (mod 0.39.2, world 0.9.0, 2026-11-10): the settings menu works.**
- **Menu:** `ffrap_menu add` seeded 6 entries. The rows opened with the current settings; setting EXP, gil and MRP to 10 and the rate to 2 applied at once (`settings: from the Options screen: ...`), and the values were there in the next session (`0 option save entries added`).
- **Passkey:** switching it in the Items screen wrote `29520 on`, then `29520 off`, in the artifact list.
- **Cuff Links:** off, then a load, left the chest icons up. But there was no save between the two, so the load brought the Cuff Links back on. And `zzz_TreasureMinimap_P` in `Paks/~mods` may draw the icons by itself (IDEAS.md, idea 26).

**Round 54 (mod 0.40.0, world 0.9.0, 2026-11-10): the menu goes in by itself; the Cuff Links do nothing so far.**
- **Menu:** with no command, the AP rows were in Options with the values set earlier (`menu: rows added to the Options screen; ... 6 option save entries added`, then `settings: from the Options screen: ... exp 10.0`).
- **Cuff Links:** with `zzz_TreasureMinimap_P` moved out of `Paks/~mods`, the chest icons went away and did not come back with the Cuff Links on, nor after `ffrap_artifact table` and map changes. So the icons were the pak mod's (IDEAS.md, idea 26).
- **Passkey:** switching it on changes the airship as soon as the menu closes.

**Round 55 (mod 0.40.1, world 0.9.0, 2026-11-11): artifacts are parked.**
- **Mini-map:** one mini-map view model, its artifact map empty before and after the passkey switch. `ThiefCuffs` set on in it showed no chest icons, also after a map change.
- **TreasureMinimap:** off-line, the pak changes three mini-map and world-map data assets only, to show chest, exit and "check" icons the game hides (IDEAS.md, ideas 26 and 27).
- **Decided:** artifacts are left out for now, the passkey too. World 0.10.0 and mod 0.41.0 take them out.

**Round 56 (mod 0.42.0, world 0.11.0, 2026-11-11): the palace logic and the shard goal work.**
- **Oblivion Palace:** with 4 shards from Archipelago, one chest opened in game, and Universal Tracker showed chest 1 in logic. At 6 shards the tracker showed the second, and it opened.
- **Shard goal:** reached, the first time it was played to the end.
- **Research Center Ruins (map 3220):** the level 1 card is shiny 32, the level 2 card (33) is behind the level 1 door, and the level 3 card (37) is behind the level 2 door. The level 3 door leads to the White Jade Stone area, with a boss in vanilla.
- **Scaling strength:** the row works, and the difference shows.
- **Menu:** the AP rows did not stay; the user typed `ffrap_menu add` every time. With the rows always there, the user wants the settings on any save again.
- **From the log** (sent after the round):
  - The rows went in at each save load (`menu: rows added ... 7 option save entries added`), and 50 seconds later `ffrap_menu add` found the table with 15 rows again: the game had loaded it again. That is what mod 0.43.0's check every tick is for.
  - The palace turn-in takes the shards you hold: at the first chest the bag went from 4 shards to 0 (the next shard was `held 0 -> 1`). Each step counts the shards turned in so far, so the logic's count of shards received matches.
  - Research Center Ruins, in the order played: card 1 (shiny 32), shard 34, chests 0 and 1, shard 36, chest 3, card 2 (33), chests 5 and 2, shard 35, chest 4, card 3 (37). That is `data/gates.tsv` exactly.
  - The key card pickups are already reported as checks (`check shiny:3220:32`); they are not locations yet.
  - At the goal, the server sent the rest of the player's items (about 350) in 37 seconds, with no trouble. The shard count reads past the goal, such as `Tablet Shard (99/20)`.
  - The airship's shadow list gains 14 null entries each time the player lands on the world map and boards again (`126 -> 210, 84 null` over six landings). No crash or slowdown seen. To look at (open_world.md, section 4).

**Round 57 (mod 0.44.0, world 0.13.0, 2026-11-11): the lock works; the goal came too early.**
- **Menu:** the AP rows were there every time, at the title too.
- **Chocobo:** given on the new seed (`chocobo: saddle given (ok, held 0 -> 1)`), and it works.
- **Chest icons:** shown and kept after map changes (`chest icons on: 3 fields written`). The user asks for more: hide an icon once its chest is open, and mark shinies and shards, as FFRS_QoL does (IDEAS.md, idea 27). The old pak mods moved out of `~mods` were probably overwritten by FFRS_QoL anyway.
- **Research Center Ruins:** not tested; next round.
- **Final boss lock:** `sealed (characters 2/4, visions 0/8)`, the notice showed near the climb, and the prompt stayed away. After the counts came in, `open (characters 6/4, visions 10/8)` and the climb worked.
- **Goal:** sent at story 8050, which is after the first Sol fight and before the last floor. More fights and scenes come after it. The story went 8050 -> 9000 at the "Fin" screen, then 9000 -> 8040 (the staff roll's row sets it back). The user would rather have the win over Sol (Rain alone) as the goal, or 9000.
- **From the log:**
  - `final boss lock: the last climb's trigger was not found (nearest trigger 57538 away)` alternated with `sealed` all through the tower: the trigger is loaded only near the climb. It was sealed again each time it came back.
  - `menu: rows added` came every few seconds to a minute: the game loads the Options table again all the time. The rows were always back in time.
  - The airship's shadow list gained 23 nulls per landing this time (`134 -> 249, 115 null` over five landings).
- **Scratchpad:** Mobliz Shipyard (maps 3060 to 3062): two of three elevators do not work, so chests 1 and 3 and shards 71 and 79 cannot be reached, with a boss there too, it seems. Mt. Thunderclap: the Liquid Thunder symbol on the map starts a boss battle when touched, a model for boss checks (screenshot in `.reference`).

**Round 58 (mod 0.46.0, world 0.15.0, 2026-11-11): the final win is the goal; map markers are left to other mods.**
- **Goal:** `the last battle is won (battle group 9056, flag 40 off)`, then `Goal complete!` right after Rain beat Sol, before the ending's scenes. Story 8050 alone did not send it.
- **Final boss lock:** sealed at visions 8 to 11 of 12, open at 12 of 12.
- **Research Center Ruins:** the logic matches the game.
- **Chest Radar:** the icons showed only on maps loaded after it arrived; a map already drawn kept none until the next map change. Opened chests kept their icons, and there are no shiny or shard markers as FFRS_QoL has. The user chose to leave map markers to other mods, so world 0.16.0 and mod 0.47.0 take the feature out.
- **Quieter log:** `menu: rows added` showed once, and the tower's "trigger was not found" once per visit.
- **Mobliz Shipyard:** `ffrap_inspect` showed elevator 75 with `m_GimmickCondition 1` (deactivated). Off-line, the level (`Dng_04Dir_41_02_GD`) has four elevators: 72 and 74 active, 73 and 75 deactivated. A five-lever puzzle (the right lever is D) turns 73 on in chapter 2; its levers start deactivated too. Nothing in the level turns 75 on. A wrong lever starts a fight (`C02_Moburizu_Switch_Fail_Encount`), maybe the boss the user expected there.

**Round 59 (mod 0.47.0, world 0.16.0, 2026-11-11): one elevator still cannot be reached; bosses come next.**
- **Mobliz Shipyard:** the log has `shipyard: 2 stopped elevators turned on`. The middle elevator works once a keypad to its right is touched. That may have worked before the mod's change. The right elevator is on too (a switch above it, reached with the middle elevator), but it stands at the bottom and nothing at the top calls it. So the chests and shards past it are still out of reach. A lead from `ffrap_inspect`: the elevator's Blueprint has `CallSwitch(InArg, Direction)` and `m_IsCallSwitch`. Next: read that Blueprint's code off-line.
- **FFRS_QoL's map markers:** FFRS_QoL alone showed none. With the TreasureMinimap paks beside it they work: the paks draw the markers, and FFRS_QoL takes a marker away once its chest is found. Both run fine with this mod. Rounds 54 to 58 looked at each one alone, which is why neither seemed to do the whole job.
- **Cave masters:** all there on the open world start. The fights and their own rewards work.
- **Liquid Thunder** stands on Mt. Thunderclap and starts its fight (the scratchpad).
- **A live trigger's events can be read.** `ffrap_inspect CPP_MapGimmick_EventTrigger` on Mt. Thunderclap gave Ramuh's trigger: `m_EventList[0].Condition` is `{progress:12}==0&!{flag:12}|{progress:12}==10&!{flag:12}` and `EventId` is `Summon620_Ramuh_02`. The class has `SetEventList`, `SetEvent`, `GetEventList`, `PlayEvent` and `FindMatchEventByEventList`. This is what bringing the story bosses back needs (docs/bosses.md).
- **The user's choices for bosses:** a story boss gives a locked Crystal Fragment and no shuffled item. A cave master gives a shuffled item. Espers are open: fragments, their own kind of fragment, or left as they are. The user will ask players.
- **From the log:** `client: world version 0.15.0`. The 0.16.0 apworld was not the one in use.
- **Found off-line: the generation tests had not been running.** `python -m unittest worlds.ff_resonance.test` loads only the package, so `run_all.py` ran 6 empty tests and printed ok. 12 tests had gone stale since the location options became on by default. The runner now names `test_generation`, and the tests are fixed.

**Round 60 (mod 0.48.0, world 0.17.0, 2026-11-11): the bosses work as locations.**
- **Cave masters:** Shoggoth's fight starts and ends well, and the win sends the check (`check boss:9080`, then the item). No pop-up comes up, as the win row has no reward left. The user wants the reward pop-up back, saying what the boss held, as a chest's does.
- **Liquid Thunder:** `check boss:9083`, then `Received Crystal Fragment (1/1)`.
- **Sanctissimus Shrine:** all six fights are there and each gives its fragment (2 to 7). No `story` line with 6123 after Archaeoaevis.
- **Dragon's Maw:** Intangir and the Rogue Magitek Weapon are there, and both send their checks.
- **Whirlpool Hollow:** open from the start with only the airship. Sephiroth could not be beaten at party level 28: every hit did 0 damage, even with `ffrap_scale` at 1% HP, attack and magic. Scaling writes level, HP, attack and magic, not defence. So his check and his row without the vision are still not seen.
- **The tower's notice** was not tried.
- **The chest pop-up's text is slower than it was:** a second or two at times. From the log: the first pop-up on each map takes 0.5 s after the check, the later ones none. Round 49 made a map load forget the cached message widget, and the fast check needs that widget.
- **"A few shinies gave no Archipelago item."** The log has five checks with no item after them. Four are in `KEPT_VANILLA` (`chest:3230:2`, `chest:3260:3`, `shiny:1000:4`, `shiny:1000:189`): they keep the game's own item and are not locations. `shiny:3260:1` is in no table (`field_items.tsv` has only 7 and 8 on map 3260). The two shinies hold a Magicite Shard in `field_items.tsv`, which looks wrong for a kept spot: to look at.
- **FFRS_QoL's rates won over ours.** Its code writes the three difficulty rows every 3 seconds. Ours wrote them every 5 seconds, so its values were in use most of the time. It writes the map tables' encounter fields when its config changes, and ours wrote them only on a map change.
- **The user asks for:** the encounter slider from 0.5 to 3 in steps of 0.5, and a yaml option, on by default, that makes the bosses with shuffled items priority locations.
- **Also in the log:** `menu: DT_OP_GameSetting could not be loaded`, twice, in battles on map 10218. It came back by itself.

**Round 61 (mod 0.49.0, world 0.18.0, 2026-11-11): passed.**
- Cave master reward pop-up worked with the 1-Potion stand-in and showed the Archipelago item text.
- Chest pop-up speed is back to immediate on map changes.
- Rates won over FFRS_QoL.
- The encounter rate slider (0.5x to 3x in 0.5 steps) worked as intended.
- Cave masters and Dragon's Maw bosses held priority items (`priority_bosses`).
- Crystal Tower notice ("Crystal Fragments x/y") was deferred to the next round.

**Round 62 (mod 0.50.0, world 0.19.0, 2026-11-11): first report, The Hunger.**
- The Hunger's door in Kolobos Ruins (map 3040) starts the fight.
- **The fight was easy.** The game files put The Hunger (unit 113) and the cave masters in the Enemy category, not Boss. So the mod scaled them as plain enemies: the enemies' band, below the party's level, at 75% power. `scale.txt` had it at level 6 with 1236 HP. It ships at level 9 with about 2500 HP.
- **The win gave no EXP.** The Hunger ships with 0 EXP (`scale.txt`: `113 The Hunger ... EXP 0`). Scaling keeps a 0 at 0.
- **The fight started again after each win, with no way out but loading a save.** Every `story boss` line says `won false`, so flag 1241 never came on. The log has no `story boss` line from 21:23:25 to the reload at 21:25:06, so the field did not come back between the fights. The door's trigger fired again as the party came back from the battle, before the win row could run.
- **Two items came out of a battle at x 0:** Ruby Fragment (20030) and Hoodwink Garb (11024) were in the bag, each at x 0. The user thinks they came from another player during a battle. The log was lost to a restart. The mod gave items whenever a save was loaded, battles included. The likely cause: the battle keeps its own copy of the bag and writes it back as it ends, so the count went back to 0 and only the entry stayed.
- The rest of the round 62 plan was not tried yet. It is in the round 63 plan.

**Changed after round 62 (mod 0.51.0 to 0.52.0, world unchanged):**
- 0.52.0: the user found scaling too easy all round. Each strength moved up one step, and a harder one was added. Casual is the old Normal, Normal (the default) the old Expert, and Expert a step past it. The names were Easy, Standard and Hard on a 1 to 3 slider, as every radio button table in the game is in use. The slider's label ran past its box, so 0.52.1 has the copied Difficulty row back, with the game's names.
- 0.52.1: bosses on Normal still melted. On Normal and Expert their level and power ramp from 10 points over 0.52.0's at party level 5 to 20 points over at 25. Numbers in docs/open_world.md, section 5.
- 0.51.1: received items go in only while the field is on screen. In a battle, a scene or a menu they wait, and the status says `waiting: not on the field`.
- A unit in a boss location's battle group (`G.BOSSES`) is scaled as a boss, whatever its category. That is the boss band at 100% power. This moves the cave masters to the boss band too.
- While scaling is on, a boss unit with 0 EXP gets a story boss's EXP for its level. Mom Bomb (level 14) and Liquid Thunder (level 13) both ship with about 1350, so The Hunger gets about 500 at level 6.
- The three story boss fights (Belmodar, The Hunger, Mom Bomb) also need flag 1441. The mod turns it on after the field has been up for about 2 seconds on a story boss map, and off as soon as the field goes (a battle, a scene, a menu). So the party coming back from the fight cannot set it off again before the win row runs.
- Scaling "off" now puts boss rows back too. Before, the seed's own "off" left them scaled.

**Round 63 (mod 0.52.1 to 0.52.2, world 0.19.0, 2026-11-12): passed, with three bugs and two crashes.**
- During the round, mod 0.52.2: Belmodar with a low-level Rain and Lasswell felt good on the game's Normal with our Normal, and on Expert with Expert. A level 8 party on Normal met level 5 enemies, "like fighting air". The enemies' band was 2 under and 2 over a centre of 7. It is now 1 under the centre, and 1, 3 or 5 over it on Casual, Normal and Expert. The bosses' band is unchanged. The Arena's Brawler, Gladiator and Champion fights are scaled as bosses.
- **Scaling (0.52.2) feels better.** It pushes the player to need the right members and visions for a boss, which is the natural gate the user wants. Bosses need logic of their own now (IDEAS.md, idea 29).
- The Hunger worked. Cave masters worked, and their scaling feels good.
- Nameless Ruins (Liquid Flame, Iron Giant) and Mom Bomb worked, but were too hard for the party and gear the seed had given. The user raised the party's level by hand to finish them. Belmodar worked and felt good.
- The Crystal Tower notice worked. Items received in a battle came after it, with the right counts.
- **Universal Tracker showed fights in logic that could not be won** without more members, visions or gear. Cave masters are priority locations, so progression can sit behind them. IDEAS.md, idea 29.
- **Town of Felicitas Shards 8 and 9 did not send when picked up.** The log has `check shiny:2040:1` on the first visit, which is no location: the live shard read id 1, not the level's 8 or 9. `seen.tsv` has Felicitas medals with ids 0 and 1, and so have the Research Center Ruins and map 3260. On the next visit both `shiny:2040:8` and `shiny:2040:9` came at once, 3 seconds in: the save had them as taken under their real ids. Why the live ids differ is not known.
- **The Research Center Ruins' Tablet Shards (34 to 36) never sent.** Same cause: the log has `check shiny:3220:1`, and 34 to 36 never came.
- **Town of Mitra Chest 3 (`chest:2000:2`) may be out of reach.** The box is at (-657, 13160), far from the town's other four. It is near the same-map doors 9 and 17 (ground floor) and 6 and 21 (upper floors). Those are the exits of an inside room with 3 floors. By the door points, its ground floor door in town is door 22 at (345, 2412) or door 8 at (800, 2462). This is a guess from door ids. It is not seen in game.
- **The Warrior of Light's, Cloud's and Tidus's sanctums were in logic on the wrong continents.** The world took a sanctum's continent from the airship landing point with the sanctum's id, and those ids do not match the sanctums. The door on the world map has the real destinations in `mTransitionDataList`. By the doors: the Warrior of Light (10203) and Cloud (10208) are on Lanzelt, Tidus (10200) on Olderion, Terra (10201) on Kolobos, Noctis (10202) and Zidane (10206) on Dirnado. The log agrees: with only Dirnado newly open, the user entered 10207, 10202 and 10206 within two minutes, and 10201 just after Felicitas.
- **Two crashes, both about 1 h 48 min into a session.** Both are an access violation in UE4SS's handling of a UObject from Lua: an object the engine had already freed.
  - Fast travel to Gaberada with the Iron Splitter quest on (`UECC-...7BC458BB`, 10:08). The Lua ran from a game-thread timer (`LoopInGameThreadWithDelay`), three `pcall`s deep. Our tick (`tick`, `pcall(locksTick)`, `Alive`) has that shape, and so do FFRS_QoL's ticks. The log ends 7 seconds after the world map came back up. Not known which mod it was.
  - Going to the airship's deck (`UECC-...D8B3077E`, 11:57). This Lua ran from an `ExecuteInGameThread` callback, one `pcall` deep, 1 to 2 seconds after map 20002 loaded. This mod does not use `ExecuteInGameThread`. ModSettings does: on each new `WBP_ModSettingsHint`, it queues callbacks at 50, 200, 800 and 2000 ms that call `hint:IsValid()` in a `pcall`. A map load in that time frees the hint, and `IsValid` on a freed object crashes (this mod's round 49 lesson). So the deck crash is most likely ModSettings.

**Changed after round 63 (mod 0.52.3, world 0.19.1):**
- A scouted shiny on the current map is also asked of the save by its own id, each scan. So a pick-up sends its check even when the live actor reads another id. The pop-up may not show for those, as the check comes from the save.
- `gen_from_dump.py` writes each door's destination list in a new `destinations` column of `transitions.tsv`. The world uses it for the continents of maps behind the world map, and a sanctum takes the continent of its door. Six sanctums moved: Tidus to Olderion, Terra to Kolobos, Noctis and Zidane to Dirnado, the Warrior of Light and Cloud to Lanzelt. Sephiroth's boss (Whirlpool Hollow) moved from "Open" to Lanzelt, as its door is in the Lanzelt box.

**Round 64 (mod 0.52.3, world 0.19.1, 2026-11-12): passed, with one bug.**
- The Felicitas shards sent on a new seed. The round 63 save was not tried again.
- Sanctum logic in Universal Tracker is right now.
- Mitra Chest 3 is in reach. It was where the plan said.
- The Arena's Brawler fights feel good as bosses.
- No crashes.
- **Four Earth Shrine chests were sent with nothing opened.** On the first visit to map 3000, `chest:3000:1`, `3`, `4` and `6` were sent together, 3 seconds after the map loaded. That is when its chests came into view. No pop-up showed. The user then opened them, and nothing was sent, because they were sent already. Universal Tracker no longer listed them, so they looked like they were not in the world. They are: the world has all 8 Earth Shrine chests, and the pool always has one item per location, filled up with filler (`items.create_all_items`). The ninth row, `Dng_01Gra_40_0`, has no box in the level.
  - The trigger was most likely the mod asking the save (`IsOpenTreasureBox(3000, m_UniqueId)`). The game itself saw the chests as closed, as the user could open them.
  - All four are `BP_MapGimmick_TreasureBox_C`. The two sent normally (2 and 5) are `TreasureBox002_C`.
  - Each of the four has the uniqueId (4, 5, 6, 9) of a shiny picked up earlier in the seed, on other maps. Round 63 had one case of the same kind: `chest:3050:3` (uid 26) after shinies 26 on maps 3210 and 1000.
  - The dump shows how the game's own Blueprints save these things. A chest calls `OpenTreasureBox(GetSameMapId(), GetId(), GetUniqueId())`. A shiny calls `OpenTreasureBoxWithoutId(GetSameMapId(), GetUniqueId())`, and asks `IsOpenTreasureBox` the same way. The mod uses the `m_UniqueId` field, not `GetUniqueId()`. Whether the two differ is not known yet. They may, and that would also explain Felicitas's live ids (round 63).
- **Starting party.** The user rolls slots 1 and 2 at random and keeps getting Lasswell with Archwitch Fina, or Jake with Sakura, and has never seen Lid or Nichol. The world takes each choice as Archipelago rolls it, and changes only a repeat. 3000 seeds rolled the way `Generate.py` rolls them gave each member between 719 and 793 times out of 6000. So the roll is fair when the yaml says `random`. Not known yet: the user's yaml lines for these options.

**Changed after round 64 (mod 0.52.4):**
- A loaded chest is sent only when the chest itself says open. When the save says open and the chest says closed, the log says `<key>: the save says open, the chest says closed; not sent`, with the save's answer under each key, once per visit. `ffrap_sync` still asks the save.
- The first time a chest or shiny is seen on a visit, the mod asks it for `GetUniqueId()`. If that differs from `m_UniqueId`, the log says `chest <map>:<uid>: GetUniqueId says <id>` (or `shiny`).

**Round 65 (mod 0.52.4, world 0.19.1, 2026-11-12): passed. The snapshot explains round 64.**
- **The save's rows (`snap_es.tsv`, round 64 save).** Each map's `Map.mapGimmick{map}.treasureBox.treasureBoxList` holds only that map's own chests (`ID` 0 and up) and shinies (`ID` -1). No shiny went into another map's list. 13 maps had rows.
  - Map 3000 has its six chests. The four sent early (uids 4, 5, 9, 6) are its first four rows. The two `TreasureBox002_C` chests (14, 15) came after.
  - Other maps had rows with those uids. Open rows had 4, 5, 6 and 9: shinies on the world map (4, 5), Dilmagia 2060 (5, 6), Felicitas 2040 (8, 9, and chests 4 to 7), Gaberada 2150 (9, and chest 4). For 14 and 15, Kolobos Ruins 3040 had closed rows, and the Shipyard 2061 had open ones.
  - **So `IsOpenTreasureBox(map, uid)` answers from another map's row when the map has no row for that uid yet.** That fits all six. 4, 5, 6 and 9 found an open row. 14 and 15 found 3040's closed rows first. Round 63's `chest:3050:3` (uid 26) fits too: map 3050 has no rows in this save, and shinies 26 were open on maps 3210 and 1000. Before round 64, the mod sent a chest the moment this answered true.
  - Kolobos Ruins (3040) has all six of its rows closed, though `chest:3040:0`, `3040:1` and `shiny:3040:15` were sent in round 64's first session. Not known why: an older save loaded, or the game reset the dungeon.
- No chest sent early in round 65 (mod 0.52.4 judges a loaded chest by the chest).
- **No `GetUniqueId` lines.** Mod 0.52.4 logged only a difference, and logged nothing when the call failed. So it is not known whether the call works.
- **Starting party (9 seeds from the user's yaml, all 8 members at weight 50 in slots 1 and 2).** The spoilers' rolls: Rain+Rain, Fina+Rain, Rain+Jake, Lasswell+Lasswell (twice), Jake+Jake, Nichol+Rain, Sakura+Lid, Lid+Nichol. The real party is the two members the spoiler never places. The four repeats became Rain+Fina, Lasswell+Lid, Lasswell+Rain and Jake+Nichol. So the swap can pick Fina and Lid, the defaults of slots 3 and 4: with a roster of 2, only slots 1 and 2 are kept out. 8000 rolls of the yaml's weights through `Generate.get_choice` gave a repeat 12.1% of the time (1 in 8 is 12.5%). Four repeats in nine seeds is luck, about 3 in 100. Not a bug.

**Changed after round 65 (mod 0.52.5):**
- The mod reads the save's rows for a map itself (`game.SaveOpenRows`), and a uid with no row is not open. Shinies, the round 63 scouted-shiny check and `ffrap_sync` use the rows. `IsOpenTreasureBox` is only logged.
- A loaded chest still goes by its own state. When the save disagrees, the log says `the save says open (row <row>, IsOpenTreasureBox <answer>), the chest says closed; not sent`.
- The first `GetUniqueId` answer of each session is logged, and so is a failure: `chest <map>:<uid>: GetUniqueId says <id> (first of the session)`, or `failed: <why>`.

**Round 66 (mod 0.52.5, world 0.19.1, 2026-11-12): passed.**
- The user reports that everything worked as expected: the shards sent on pick-up, and nothing was sent early. No log was sent, so the `GetUniqueId` answer and the `/resync` count are not recorded.
- The chest and shiny work of rounds 63 to 66 is closed. Next: the story bosses, map blockers at the crossings between continents, and options to start without the airship or the Chocobo.

**Changed after round 66 (mod 0.53.0, world 0.20.0):**
- **Routes between continents, off-line.** No door or cave joins two continents. The ways across without the airship are the ferry and walking on the world map (`open_world.md`, section 4).
- **The ferry is gated.** Grandport Harbor (Lanzelt), Dirnado, Olderion and Zoldaad each offer the other three ports. Choosing a port on a locked continent now ends the talk, as "no" does. Open ports work as before.
- **Walking crossings, marked in game.** `ffrap_gate mark <a> <b> [scale] [dist]` puts a world-map blocker ahead of you between continents `a` and `b`, and saves it in `crossings.txt`. It holds while either continent is locked, and comes back after each map change. Near a closed one, the feed says which unlock is needed. `ffrap_gate unmark` removes the nearest, `ffrap_gate crossings` lists them.
- **`start_with_chocobo`** (on by default). Off: the save gets no Chocobo at the start, and "Chocobo" (the game's Choboco Saddle) is an item in the pool. No logic needs it yet.

**Round 67 (mod 0.53.0, world 0.20.0, 2026-11-12): passed.**
- **The ferry works.** With Dirnado locked, the ferry at Grandport would not sail there, and it did once Dirnado opened. The log has `ferry: 24 port choices written` at the start, then 6 each time a port's continent opened or closed.
- **Two walking crossings, and only two:** Grandshelt to Lanzelt over the stone bridge, and Lanzelt to Kolobos over the rope bridge. Both blockers work. They block the way, last through a town visit and a landing, go within a second of `ffrap_lock open lanzelt` (`crossings: 0 placed, 1 opened`), and come back on a close. The feed said "The way is closed. Archipelago needs Lanzelt Unlock" (and "... and Kolobos Unlock" at the second). `crossings.txt`:
  - `grandshelt lanzelt 13684 16599 87 180.0 3.00`
  - `lanzelt kolobos 7889 13983 61 180.0 3.00`
- **Every mark faced north.** On foot the pawn's rotation reads 0 whichever way the player faces, so every cart went 150 units to +x (north on screen) with yaw 180. Both bridges run east to west, so each cart lies along its bridge, not across it. At scale 3 the carts look too big, and the crates float above them (screenshots). The game's own cart (uid 129, Grandshelt, story under 5000) has scale 1.
- **No door or cave joins two continents.** The user knew of none either. The ferry and the two bridges are all the ways across without the airship.
- **`start_with_chocobo: false` works.** No Chocobo at the start, and the item gave one.
- **The Chocobo and the Antlion.** In Lanzelt a sandpit holds the Antlion. Walking in starts the fight. The Chocobo crosses it with no fight, and after a win you walk across. The Antlion is there at story 8000 (the user first thought not, then saw it). The game data agrees: trigger uid 131 on the world map at (10814, 13272), `C01_ArijigokuEncount[!{ride}&!{flag:113}]`. Its win sets flag 113 only when story flag 10 is on (`bosses.md`), which is not checked at story 8000. The Chocobo blocks nothing else.

**Changed after round 67 (mod 0.53.1):**
- **The two crossings are in the mod** (`G.CROSSINGS`), so every install has them. `crossings.txt`, when there is one, is used in their place: delete it to go back to the mod's own list.
- **A mark goes the way you last walked.** The mod follows the player's position about once a second on the world map. `mark` puts the cart 150 ahead in that direction, turned to face you, so it lies across the path. The default scale is 2.
- **The nearest crossing can be changed where it stands:** `ffrap_gate move <dx> <dy> [dz]` (+x is north), `ffrap_gate turn [degrees]` (90 by default) and `ffrap_gate size <scale>`. Each one writes `crossings.txt` and puts the cart back at once.

**Round 68 (mod 0.53.1, world 0.20.0, 2026-11-12): passed.**
- **Both carts sit across their bridges** (screenshots). The user turned, sized and moved them. `crossings.txt`:
  - `grandshelt lanzelt 13684 16599 87 90.0 1.50`
  - `lanzelt kolobos 7834 13928 61 90.0 1.50`
  - Scale 1.5 closes both bridges. Yaw 90 lies across both, though one bridge runs east to west and the other south-west to north-east on screen. Which way +y moves on screen was not reported.
- **The airship can be hidden.** With `ffrap_airship {flag:1431}`, the airship was gone after a visit to a town. `ffrap_grant flag 1431` brought it back at the next map change. It did not go away again, as the flag stayed on (`ffrap_grant` only turns flags on). The condition is not saved: the log shows it written again after each reload.

**Changed after round 68 (mod 0.54.0, world 0.21.0):**
- **The two carts are in the mod** at the round 68 places. Delete `crossings.txt` to use them.
- **`start_with_airship`** (on by default). Off:
  - The new game starts on foot on the starting continent, at the airship landing point beside its main town: the Royal Capital, Village of Kol, Felicitas, Dilmagia, Olderion, Zoldaad, Mysidia, Gaberada or Sian (`G.FOOT_STARTS`). The airship is parked there and hidden.
  - "Airship" is an item. It turns on flag 1431, which is the airship's spawn condition for that seed. The mod writes the condition about once a second from the moment the client sends `cfg airship 0`, before the game loads a map.
  - When the item comes, the mod parks the airship where you stand on the world map (or as soon as you are back on it) and says so. It lands there at your next map change.
  - Logic: a continent other than the starting one needs its unlock and the Airship, or a way on foot. The ways on foot are the two bridges and the ferry, each opened by the far continent's unlock. Mysidia, Gronoa, Pharm and the Crystal Tower need the Airship. The Antlion's sandpit is not in logic yet (part 4).

**Round 69 (mod 0.54.0, world 0.21.0, 2026-11-12): passed, with one bug.**
- **The start on foot works.** The new game arrived by Kol on foot (`arrival: map 1000 at 12470.0, 14980.0, 65.0, on foot, the airship parked there`), with no airship through town visits and a reload. The condition went in at the title screen, before any map loaded (`airship: spawn condition {flag:1431}`).
- **The gates hold on foot.** The stone bridge said "Archipelago needs Grandshelt Unlock", and the ferry only sailed to open ports.
- **The Airship received on the world map** landed where the player stood after the next map change (`parked at (12672, 15192, 39)`).
- **Bug: the Airship received in a town landed in Olderion.** It came in Grandport (map 2030). The mod parked it 14 seconds later at `(498, -777, 502)`, as the map changed to 1000. Those are Grandport's own coordinates: the world map's id was already in, but the pawn was still the town's. Read on the world map, (498, -777) is Olderion. Fast travel could not reach it, as fast travel needs a visit inside the airship first.
- **The Antlion's sandpit is between Kol and Grandport Harbor** (screenshot). A win does not end it: "We managed to fight it off, but it probably won't be long until it attacks us again", and walking in starts the fight again, with or without the Chocobo first. In the user's own cleared save it is gone. The game data says why: the win row `C01_ArijigokuWin` runs `_Win_02` (sets flag 113, "We should be able to cross without riding chocobos now") only when story flag 10 is on, and `_Win_01` (sets nothing) otherwise. Flag 10 is off at the open world start.
  - The user's concern: from the west, the fight puts you on the east side, and with no Chocobo you cannot get back. With a Lanzelt start and no Chocobo or Airship, that leaves about 6 checks for a long time. The user wants a win to clear the sandpit.

**Changed after round 69 (mod 0.54.1, world 0.21.1):**
- **Where the Airship lands.** Received on the world map, it lands where you stand, read only from the world map's own pawn. Received anywhere else, it waits at the seed's start point, which you can always walk back to. `ffrap_airship home` parks it at the start by hand, for a save where it went astray.
- **One win clears the Antlion's sandpit.** On every open world seed, both branches of the win row go to `_Win_02`, which sets flag 113 (`G.AntlionPatch`, logged as `antlion: 2 win choices set to clear the sandpit`).
- **The Antlion is a boss location:** "Lanzelt Desert: Antlion" (battle group 9060, flag 113), with a shuffled item, in Lanzelt. Like the other bosses in the mod's list, it is scaled as a boss.

**Round 70 (mod 0.54.1, world 0.21.1, 2026-11-12): passed.**
- **One win clears the Antlion's sandpit.** The log has `antlion: 2 win choices set to clear the sandpit` on each new game, and `check boss:9060` after the win. The fight did not come back.
- **"Lanzelt Desert: Antlion" is a location.** On the new world 0.21.1 seed the win sent it, and its item (Pharm Unlock) came a second later. It has no reward pop-up of its own (`chest pop-up for boss:9060: no chest pop-up on screen`): its win row gives nothing, so only the feed shows the item.
- **The Airship received in a town waited at the start.** It came in Kol (map 2020): `airship: parked at the start (received off the world map), (12470, 14980, 65)`, and it was there on the way out.
- The round 69 save with the stray airship was an autosave, since overwritten, so `ffrap_airship home` was not tried.
- Not checked yet: how the Antlion feels with scaling on. The user scaled enemies down by hand to test. A bigger play test comes later.
- The airship and Chocobo work of rounds 67 to 70 is done. Next on the user's list: the story bosses.

**Changed after round 70 (mod 0.55.0, world 0.22.0):**
- **Ten more story bosses** (`bosses.md`, section 4a): Siren (Siren's Tower), Aether (Wind Shrine), Tellus (Nameless Ruins, Tower of Mysidia and Wandering Lands), Lux (Rugged Mountain Path), Elfdrit (Gronoa Shrine), Gelidus (Sanctissimus Shrine), Ignis (Mt. Reizan) and Behemoth (Crystal Tower). Each starts where its story fight did, at a zone or a door, and holds a Crystal Fragment. There are now 22 fragment bosses.
- None of them is seen yet: each trigger is a little different, and each may be gone or moved at story 8000.

**Round 71 (mod 0.55.0, world 0.22.0, 2026-11-13): passed for most bosses, with bugs and two crashes.** A long solo seed on the game's Normal with our Normal (`.reference/2026-11-13_playtest ue4ss logs.txt`).
- **Most of the ten story bosses work**: their triggers were found (`1 triggers`), the fights started, and the wins sent their checks.
- **Tellus in the Wandering Lands did not start.** The trigger was found on map 3270 (`1 triggers`), but the user could not find the spot. Its zone is at (235, 102590), past where the way from map 3272 comes in.
- **Elfdrit started only on one square**: the zone is small.
- **Behemoth:** in the story the Sworn Six weaken it first. It sits right before the final boss, and a player should not have to go there before they are ready. The user's call: leave it to the game.
- **Fast travel offered Grandshelt Castle and the Earth Shrine** on a start without the airship. The prologue skip marks maps 2013 and 3001 as visited, so they are fast travel points from the first minute, past the continent locks.
- **Zoldaad Castle Shard 10 was sent with nothing picked up.** The log: `check shiny:3160:11` with its pop-up at 12:02:31, then a trip to map 5100 (an event copy of the castle) and back, then `check shiny:3160:10` at 12:03:46 with `no chest pop-up on screen`. So the shard taken as 11 most likely came back on the next visit reading 10, already taken (the round 63 Felicitas pattern).
- **Grandshelt Castle Chest 2 not found.** The game data: map 2012, box uid 63 at (-30195, 8095, 92). The hall by the castle's west exit to the town (around x -32600) has two doors facing each other, at (-29980, -6000) and (-29980, 6000). The chest is about 2,100 past the second, and much lower (z 92, the doors at 832). The doors are plain doors with no condition.
- **Bosses felt too hard on Normal.** Near level 20 without a full party, some felt unbeatable. At level 30 with a full party, tough but beatable, "a tad too tough for normal". Party size matters more than thought.
- **Two crashes, with no other mods in.** Both in a mod tick, one Lua `pcall` deep, reading a field on a freed object (`UECC-...0E0874F5`: `FFieldClassVariant::GetFName`, reading 0xffffffffffffffff; `UECC-...F767683F`: `FName::ToString`, reading 0x100). Both about a second after leaving the world map: into Mitra (12:53:09) and into a cave (14:44:57). Round 63's two crashes were also near 1 h 50 into a session.
- **Logic, from the user:** Zoldaad Dungeon Chests 1 to 4 and Dungeon Shards 2 and 3 need the Dungeon Key. All of Fina's Psyche is behind Tellus in the Tower of Mysidia. These are only reachable by the airship: World Map Shiny 68, 104 and 105, the Sanctum of Light (Clive), and Malboro Varietas Cave. The user offers to find the rest.
- **Ideas from the user:** merchant ships on the ocean that the airship can visit (`GimEv_MerchantShip_*`, IDEAS.md idea 31), shuffled in, needing the Airship.

**Changed after round 71 (mod 0.56.0, world 0.23.0):**
- **The crash.** The mod kept some game objects from one tick to the next: the map and save managers (`Live`), the chest pop-up's widgets and the item feed's. A kept object can be freed by the garbage collector with no map load the mod sees, and then even `IsValid` on it reads freed memory, which `pcall` cannot catch. The tick that crashed calls `game.InGame()` with no `pcall`, and the only one on the stack was `Alive`'s own. So these are now kept as the object's path, and found again each time with `StaticFindObject`, which looks in the engine's own table and never touches a freed object.
- **Shinies are known by where they stand.** `Scripts/field_items.lua` (generated from the level data) holds every shiny's id and place. A live shiny takes the id of the level's shiny within 150 of it, and the log says so when that differs.
- **Bosses:** Behemoth is out (21 fragment bosses). Elfdrit's zone and both Wandering Lands zones are made 4 times bigger while their boss stands.
- **Fast travel:** an open start marks only the battlefield (5010) as visited, and the airship's deck (20000) when it starts in the airship. Saves already made keep their marks.
- **Boss strength:** Normal's bosses come in to 110 to 115% of the party's level and 115 to 120% power (from 115 to 125% and 125 to 135%). Expert's take Normal's old numbers. Plain enemies are unchanged.
- **Boss logic (first step of `docs/boss_logic.md`).** Each boss has a tier in `data/bosses.tsv`, from its level: A (to 20) needs nothing more, B (21 to 39) 3 party members and 2 continents, C (40 to 49) 4 and 4, D (50 and up, and the optional superbosses) 5 and 6 and the Airship. Party counts above what the seed can give are lowered to it. The per-boss capability rules are not built yet.
- **Logic from the user's notes:** the Dungeon Key for Zoldaad's dungeon (`data/gates.tsv`); Fina's Psyche in logic, behind Tellus's tier; `data/airship_only.tsv` for places only the airship reaches.
- **The user's own changes, reviewed:** unshuffled visions (Tronn and Leah at the start, each sanctum and Sephiroth holding its own vision) work and have a test now. `docs/boss_logic.md` is the plan for boss logic. Its battle group numbers differ from `data/bosses.tsv` in places (Marauder 9969 there, 9079 here; the Antlion 9015 there, 9060 here), so the tiers were set by boss name and level.

**Round 72, before play (world 0.23.0): Universal Tracker showed 0 locations in logic.** The seed started on foot in Mysidia, with Fina and Jake. The world had no tracker support, so Universal Tracker built it again from the yaml and rolled the starting continent and party itself. With the airship off, a tracker world that started elsewhere had nothing in reach.

**Changed (world 0.23.1):** the world takes the seed's own continent, party and options from its slot data when Universal Tracker builds it (`interpret_slot_data`, `ut_can_gen_without_yaml`). The slot data now also sends `shuffle_party_members`, `shuffle_visions` and `shuffle_key_items`. A seed made with 0.23.0 lacks those three, so the tracker takes their defaults (all on).

**Also before play:** Universal Tracker showed Grandshelt Castle Chests 8 to 16 grayed out. Those are excluded locations, on map 3020: the castle burning in the prologue, which has no way in at story 8000. The user: they should not count at all. And the Imperial Residences (2113), on the same no-route list, are reachable: the user went there in the round 71 seed, by the Zoldaad streetcar.

**Changed (world 0.23.2):** map 3020's nine chests are no locations (`NO_ROUTE` in `data.py`), so a seed has 9 fewer. The Imperial Residences' chest and shard are in logic, in Zoldaad. The no-route list now holds map 3020 only.

**And (world 0.23.3):** Grandshelt Castle Chest 2 (`chest:2012:1`) is no location either. The user searched the whole castle and could not find its room; it is most likely one the story passes through and the castle closes later. The castle's other chests are numbered again: Chests 1 to 6 now.

**And (world 0.23.4):** eight more places only the airship reaches, from the user: World Map Shiny 27 (in Pharm by our continent map, not Dirnado), 88 and 89 (Mysidia), 94 and 169 (Lanzelt), Quarry Cave Chest 1 (Zoldaad), Tartarosaurus Cave (Pharm) and Jotunn Cave (Mysidia). Shiny 68 was in already. Shiva's fight (Mysidia, an esper side quest) is airship-only too, but is no location yet.

**And (mod 0.57.0, world 0.24.0): the radar's 13 treasures** (IDEAS.md idea 32, `data/radar.tsv`).
- `include_radar_treasures` (on by default) makes "Radar Treasure 1" to "13" locations. They lie at sea, so they need the Airship.
- Three "Progressive Radar" items take the place of the radar's three parts (Magi-tenna, Resonance Stone, High-Power Generator). In logic, 1 radar opens treasures 1 to 5, 2 open 6 to 9, and 3 open 10 to 13.
- In game, the mod counts the Progressive Radars applied to the save. With 1 it turns the radar on (flag 702); with 2 and 3 it sets the radar quest's step (`{progress:49}`) to 40 and 50, which the later pingers test. It never lowers that step.
- The treasures come in order in the game, as in vanilla: each pinger also needs the one before it found. The logic needs nothing more for that, as the tiers only rise along the chain.
- A treasure's check is its found flag (704 to 716). Its dig row gives one Potion in place of its reward, so the pop-up shows and says what it held.

**And (world 0.24.1):** Sanctissimus Shrine's chests and shards (Chests 1 and 2, Shards 82 and 84) are past its first three fights, Archaeoaevis, Dad Bomb and Test Rider (the user). They need what those bosses need, tier C: four party members and four continents. A place behind bosses (`AFTER_BOSS` in `tools/gen_apworld_data.py`) can now name several, and takes the highest tier.

**And (mod 0.57.1):** an Airship received on foot inside Gronoa was parked where the user stood, in a part of Gronoa the airship cannot take off from, so it was stuck there. The Airship now always waits at the seed's start point, wherever it comes.

**Round 72, in play (mod 0.57.1, world 0.24.1): Liquid Thunder held all of Dirnado.** A new seed on foot from Dirnado, with Lasswell and Archwitch Fina. Universal Tracker showed most of Dirnado in logic, Liquid Thunder too.
- Liquid Thunder stands on Mt. Thunderclap's summit, between Dilmagia and the rest of Dirnado. On foot, only Dilmagia (maps 2060 and 2061, the town and its shipyard), Mt. Thunderclap Shard 22 and the fight are this side of it. The ferry's port is on this side too: the story's chapter 2 lands there.
- At party level 3, on the game's Normal with our Normal, with no gear or Visions, Liquid Thunder could not be beaten. It was tier A, which needs nothing.
- Its stats against a normal enemy of its level: HP 10x, Intelligence 2.75x (its `Gigavolt` is magic, an AoE with Paralysis), Defence 0.9x. Scaling keeps those ratios. The party had no Earth damage, healing, cleansing or Lightning resistance. That is what `docs/boss_logic.md` asks for this fight, but those per-boss rules are not built yet.

**Changed (world 0.24.2):**
- Liquid Thunder is tier B: three party members and a second continent.
- On foot, the rest of Dirnado is past it: 38 locations (Dwarven Forge, Mt. Thunderclap's other chests and shards, Mobliz Shipyard, the Wind Shrine, the world map's shinies, Mom Bomb, Aether, Shoggoth Cave and three sanctums). They need what Liquid Thunder needs, or the Airship to fly over it. With `start_with_airship` on, nothing changes. `PAST_BOSS_ON_FOOT` in `tools/gen_apworld_data.py` holds this; it marks the locations `past_boss`.

**Round 73, before play (world 0.25.0): boss logic by what the party can do.** The user's calls: a character's skill counts from the level it is learned at, up to the boss's own level; shop gear counts where a reachable shop sells it; gear from the item pool never counts, so no gear becomes progression. The Discord playtest starts with this world.
- `data/game/capabilities.tsv` (from `tools/gen_from_dump.py`) has what every party member's skills (by level), Vision's (by awakening) and gear's passives do: element attacks, heals, group heals, revives, cleanses, dispels, Reflect, element resistances and status immunities. 368 rows.
- `apworld/ff_resonance/boss_logic.py` checks them. From tier B a boss needs a healer, from tier C a group heal or a revive. The tier A and B bosses have their own needs too: their weaknesses and a way through their worst attack (`docs/boss_logic.md`, section 2). Liquid Thunder needs Earth and a healer.
- A Vision's awakening counts by continents opened: 1 from two, 2 from four, 3 from five and the Airship.
- `SHOP_MAPS` in `tools/gen_apworld_data.py`: the 55 gear shops open at story 8000, by their names. The only shop gear that counts in logic is resistance and status accessories and armour; no open shop sells an elemental weapon.
- Off-line, 54 seeds (every starting continent, with and without the Airship, 3 seeds each, the real defaults) filled and could be finished.

**Round 73, in play (world 0.25.2): Old Town, Olderion Chests 1 to 3 are no locations.** The user could not reach them. They are on map 3090, the Old Town that monsters attack in chapter 3. Olderion's door to it opens only at story 3050 to 3085 (`transitions.tsv`), and the open start is at 8000. Map 3090 is on the no-route list now, as map 3020 is, so a seed has 3 fewer locations.

**And (world 0.25.3):** World Map Shinies 36, 39 and 145 (Olderion) are airship-only (the user), in `data/airship_only.tsv`. Shiny 68, also in Olderion, was in the table already from round 71.

**And (mod 0.58.0, world 0.26.0): the Crystal Tower in sections.** The user: the first two sections should be in logic as soon as the Airship is, and Behemoth, between sections 2 and 3, can be a tier B boss. The fight between sections 1 and 2 is a plain enemy formation and gates nothing.
- **Logic.** The tower needs only the Airship now (nothing when the seed starts with it), not every continent. Sections 1 and 2 hold Chests 1, 2, 4, 5, 10 and 11 and Shards 124 and 125. Chests 3 and 6 to 9 and Shard 126 are past Behemoth: they need a tier B party (3 members, 2 continents, a healer) with Wind or Light, its weaknesses (`docs/boss_logic.md`). The goal still needs every continent, and Behemoth too.
- **Which section is which,** from the level (map 3280's transition points, dumped off-line): Behemoth's door (transition 11, story 8020) leads to a room at y -125400, and that room's other door to the third section, around (8000, -58000). The user named Chests 7 and 9 as maybe in the first two; the level puts them in the third, with Chest 8 and Shard 126.
- **Behemoth** is level 52 in the game. It is not in `data/bosses.tsv`, which must match the mod's boss list, so its tier is in `boss_logic.py` (`GATE_BOSSES`), with its skills counted to level 39, the top of tier B.
- **The scripted hits.** In the fight, the Sworn Six's ally (unit 1014, Water Flower's Alluvion) uses three skills with fixed damage: 501940 (Water, 2000), 501950 (Light, 2000) and 501960 (Light, 3000, with a defence and magic defence break). The battle's text names three Water support hits, three Light ones and a last one. With Behemoth scaled to a low party, those alone killed it. Mod 0.58.0 sets the three skills' damage (`magnification` in `DT_SkillData`) to 1, on each new save and on each way into the tower. No other unit uses them. The ally's own attack, Ruin (500100), is a common skill and is unchanged.

**And (world 0.27.0):** `final_boss_fragments` defaults to 14 (from 4), and the template yaml (`apworld/Final Fantasy Resonance.yaml`) lists it. When the final boss lock asks for party members or visions, each one received shows its count in the item feed as the fragments do, such as "Jake (3/6)" or "Ifrit (5/12)". The starting party counts, and past the need only the count shows.

**Round 74, a Discord tester's seed (mod 0.58.0, world 0.27.0, 2026-11-15).** The release v0.27.0, on the game's Normal with our Normal, with Lid and Sakura. The feedback is in `.reference/user_feedback_2026-11-15.txt`.
- **The airship radar did nothing.** The mod set flag 702, but the radar works only while `DT_MapPingerData`'s condition holds: the radar's step `{progress:49}` must be 20 or 30 while the found count `{progress:51}` is 13 or less, 40 while it is 14 to 22, and 50 while it is 23 to 31. The game's install row (`SubEv_C05_TreasureRadar_04`) sets the step to 20. The mod left it at 0, and it would have set 40 and 50 without looking at the found count.
- **Places past bosses were in logic.** The boss fights were gated right: off-line, with two members and every continent and Vision, only the seven tier A bosses were in logic. But only Fina's Psyche, Sanctissimus Shrine, the Crystal Tower's third section and Dirnado on foot had a rule for what lies past a boss. The tester had Tower of Mysidia Chest 3 (past Tellus), all of Dragon's Maw and the world map past it (past Intangir), and Gronoa past Lux in logic.
- **Nameless Ruins Chest 4 could not be reached.** The stairs past Tellus had no loading zone. The mod made Tellus's door (`mTransitionDataList[1]`, to point 5000) "event only while flag 1245 is off". After the win the game took the door's second entry, which goes to map -1: nowhere. The Hunger's door has the same rewrite, but its second entry leads on.
- **A Magicite Shard on the world map was not shuffled.** World Map Shinies 4 (Dirnado) and 189 (Pharm) hold one. Magicite was shuffled only from chests, a rule from round 45, before a shiny's reward could be replaced.
- **No Magicite Shard came for hours, and bosses were in logic with 0-star Visions.** The pool had 12 Shards, 12 Magicite and 13 Crysts, and logic counted continents in place of Magicite.
- **Two members could not beat the bosses that act twice a turn** (Lux, Intangir, the Sworn Six): "getting one shot on opening". The tester thinks four members for Pharm and Gronoa's bosses would be fair. Normal's bosses also felt too strong: Siren at level 44 and the Marauder at 42 beat a two-member party.
- **Abandoned Cabin Chest 1 opened without the Cabin Key.** At story 8000 the cabin's door does not test the key (`{item:20033}` picks only the destination). Not changed: a note for when the key is shuffled for its own sake.
- Known and not changed: the Research Center Ruins' key cards and the Zoldaad Throne Key are not locations yet.

**Round 74, before play (mod 0.59.0, world 0.28.0): the fixes.**
- **Versions.** From this round, the versions change once per release (the user's call): mod 0.59.0 and world 0.28.0 stay until the next one. A build tells test installs apart. The mod logs `version 0.59.0 (build <hash of its scripts>)`. `tools/build_apworld.py` stamps the apworld with a hash of its files. The client logs its build, writes it to the mod, and warns when a seed was made with another build (`world_build` in slot data).
- **The radar (mod).** The mod sets the step from the radar level and the found count together (`game.RADAR_BANDS`). With too low a level for the band, it leaves the step alone, so the radar is off there, as in the game.
- **Tellus's door (mod).** Once Tellus is won, the Nameless Ruins door is a plain door again, to the upper floor (`reopen` in `G.STORY_BOSSES`). Nameless Ruins Chest 4 is past Tellus in logic.
- **Places past bosses (world), from the maps' positions.** `AFTER_BOSS` now covers every kind of location on its maps, bosses and sanctums too. New in `tools/gen_apworld_data.py`:
  - Tower of Mysidia Chest 3 is past Tellus. It is on the top floor (z 11247), and the trigger is at z 10950.
  - Earth Shrine Chests 4 to 6 (x 14900) are past Belmodar's triggers (x 11592 to 11767).
  - `FAR_SIDE`: Lux holds Gronoa's south-west plateau, at z 1275 to 1710. That is the Town of Duggle, Gronoa Shrine, Sanctissimus Shrine, Necromonarch Cave and World Map Shinies 161 to 166. The airship does not help there. Gaberada's side is low, at z 610 to 880.
  - Ignis, at the top of Mt. Reizan, holds Pharm's plateau (Lake Ryusei, the Forest Path, the Wandering Lands). All of the mountain's chests are below him.
  - Intangir's blocking box (flag 928) is near Dragon's Maw's south door. On foot, Dragon's Maw and World Map Shiny 149 by its north door need Intangir or the Airship. Intangir is tier D, which wants the Airship anyway.
  - Gear sold in a shop past a boss does not count in logic.
  - 56 locations changed rule.
- **Magicite (world and mod).** Shinies holding Magicite are locations, and the mod blanks them. Magicite is progression (skipping balancing, like the Tablet Shards). A Vision's awakening level N costs one item of tier N (`DT_VisionUpgradeItemData`): Shard, Magicite, Cryst. Logic counts awakening N once there are two of each tier up to N. Two, because a fight's needs often come from two Visions.
- **Small parties (world).** The bosses that act twice a turn need one member more than their tier, up to five. In tier B these are Pyroviper, Salome, Tellus (Tower of Mysidia) and Behemoth. In tier C they are Jotunn, Malboro Varietas, Dad Bomb, Test Rider, Dragon, Gelidus, Lux, Elfdrit and Tellus (Wandering Lands).
- **Normal's bosses (mod).** Their level went from 110-115% of the party's to 105-110%, and their power from 115-120% to 105-110%. Casual and Expert are unchanged.
- Off-line: in the tester's case (two members, every continent and Vision, no Magicite), only the seven tier A bosses are in logic. Five seeds of the real defaults filled.

## Round 72 test plan (mod 0.57.1, world 0.24.1)

**World 0.24.2 (during the round):** copy `dist/ff_resonance.apworld` and generate a new seed for the Liquid Thunder gate. The mod is unchanged.

**Install:** copy `FFRArchipelago/Scripts` (it has a new file, `field_items.lua`) and `dist/ff_resonance.apworld` (0.24.1). A new seed is needed for the logic and fast travel changes. The crash fix, the shard fix and the boss changes also work on the round 71 save.

**1. Play long.** The crash came about 2 hours in, on leaving the world map. **Does it still happen?** If it does, send the crash folder.

**2. Elfdrit and the Wandering Lands' Tellus.** On a save where they are not beaten, walk up to where the story fought them. **Do they start more easily now?** The Wandering Lands' zone is past where the way from map 3272 comes in.

**3. Behemoth** should not start at the Crystal Tower door any more. **Does it?**

**4. Shards and shinies.** Pick up some shards and shinies, especially in Zoldaad Castle and Felicitas, then leave and come back. **Is anything sent that you did not pick up?** Any line `the live one reads id ...` in the log tells us more about the ids.

**5. Fast travel on a new seed** (`start_with_airship: false`). **Are Grandshelt Castle and the Earth Shrine gone from the list?**

**6. Bosses on Normal.** **Do they feel fairer now?** Universal Tracker should keep tier B bosses out of logic until you have 3 party members, and so on.

**7. Airship-only places.** If you find more places only the airship reaches, list them with their names as Universal Tracker shows them: they go in `data/airship_only.tsv`.

**8. The radar treasures.** When a Progressive Radar comes, the log says `radar: level N (flag 702 true, progress 49 ...)`. To try treasures 1 to 5 early, `ffrap_grant flag 702` turns the radar on by hand (a granted item 27006 is not counted: only Archipelago's are).
- Fly the airship over the sea. **Does the radar ping, and can you dig Radar Treasure 1?** The pop-up should say what it held, and the log `check radar:1`.
- **Do they come in order, 1 to 13, with the later ones only after the second and third radar?**
- **Does any scene play** after treasures 5, 9 or 13 (the game's own radar quest lines)?

Send the `[FFRAP]` lines of the log and any crash folder.

## Round 73 test plan (world 0.25.0, mod 0.57.2)

**Install:** copy `dist/ff_resonance.apworld` (0.25.0) into `custom_worlds` and generate a new seed, and copy `FFRArchipelago/Scripts`. Mod 0.57.2 has the user's shorter chest pop-up text ("You found:" and "You found <player>'s:") and a clearer note when the Airship arrives. Round 72's open items (long play, the radar, shards) carry over.

**1. Bosses in logic.** Universal Tracker should show a boss only once your party can hit its weakness and heal. **Was a boss in logic that you could not beat?** Note your party (members and levels), Visions and gear. **Was one out of logic that you beat easily?** Note the same.

**2. The early bosses.** Siren, Marauder, Antlion, Mom Bomb, Aether, Liquid Thunder and the tier B cave masters have their own rules now. **Did any feel wrong for what logic asked?**

**3. Shops.** The logic counts these accessories where they are sold. **Do these shops sell them at story 8000?**
- Jeweled Ring (Paralysis, Petrify) and Calm Armlet (Confuse, Berserk) in Olderion or Amore.
- Monk's Prayer Beads (Charm) in Grandport, Olderion or Amore.
- Star Pendant (Poison) in a Lanzelt shop (Kol or Grandport) or Felicitas.
- The element resistance accessories (Resist Fire, Lightning and the rest) in Sian.
- Safety Bit (Instant Death) in Mysidia.

Also, **is Felicitas's shop the one the data calls "ナシャト"?** If a town's shop sells something else, a screenshot of its list helps.

**4. The Crystal Tower's Behemoth (mod 0.58.0, world 0.26.0, during the round).** Install: copy `FFRArchipelago/Scripts` and `dist/ff_resonance.apworld`, and generate a new seed. On entering the tower the log should say `behemoth: 3 assist hits set to 1 damage`. **In the fight, do the Water and Light support hits now deal 1 or 2 damage, and does the fight end only when your party wins it?** Note any other hit from the allies that still takes a big part of its HP. **Was Behemoth fair for a tier B party,** and was anything past it out of logic that you could reach without the fight?

**5. Goal counters (world 0.27.0).** Install: copy `dist/ff_resonance.apworld` and generate a new seed; the mod is unchanged. **Does each party member and vision received show its count in the item feed, like the Crystal Fragments?**

**Round 75, in play (mod 0.59.0 on a world 0.26.0 seed, 2026-11-16).** The user's own seed.
- **The radar works.** Treasures 1 to 9 were dug, and the step moved from 30 to 40 at treasure 5 as planned. But they came one at a time, in order, as in the game. The user wants each Progressive Radar to open its whole tier.
- **The Resonance Stone came from a chest.** Mt. Reizan's Chest 3 (`chest:3260:3`) holds it in the game, and it was kept as vanilla (a key item, not shuffled). The pool itself has no radar parts with the radar's treasures on.
- **Tellus in the Tower of Mysidia: stuck walking.** From the zone's east or west side, the character walked toward the fight and stopped at a stairway, for good. The zone's event entry (`C05_540_Retry`) walks the player to a target point first (`MoveInfo.MoveTargetPoint`, `CPP_MoveTargetPoint_2`). It hangs on the zone, 250 units east of its middle.
- **Tellus in the Wandering Lands: never found.** The log shows 13 minutes in the Forest Path (map 3271) with the zone patched. The zone is a thin line across the path: its box, the actor's root, has the level scale 14.1 x 0.44 x 3. Round 73's "4 times bigger" was `SetActorScale3D(4, 4, 4)`, which replaces that scale: the line became a 256-unit box, a third as wide, that the player can walk past. Elfdrit's zone (2 x 25 x 2) and the Wandering Lands' (3270, 1 x 6.25 x 1) shrank the same way.
- **Universal Tracker dropped Oblivion Palace from logic** though the user had plenty of shards. Tablet Shards were "useful" by category, and only the pool's copies were marked progression. Universal Tracker makes each received item with `create_item`, so it counted none.

**Round 75, before play (mod 0.59.0, world 0.28.0, same versions): the fixes.**
- **Radar tiers (mod).** Each pinger needs the found count `{progress:51}` at a threshold (point 2 at 10, 3 at 11, up to 13 at 31), and each dig sets it to its own number (10, 11 ... 32). The top of each band (13, 22, 31) is also the threshold of its tier's last point. The mod now holds the count at the top of the player's band, so every treasure of the tier shows at once. After a dig the next tick puts it back. The game's own part steps (`DT_MapAirShip`, which test the count at 14 and 23) never match now.
- **The Resonance Stone chest (world and mod).** With the radar's treasures on, it is a location, "Mt. Reizan Resonance Stone Chest" (`RADAR_PART_CHESTS`), with a Potion in the pool for it. The mod empties it like any shuffled chest (`game.blankRadarParts`). The other two parts come from events of the radar's side quest, not from chests.
- **Story boss zones (mod).** `size` in `G.STORY_BOSSES` is the zone's new scale, set from the level's own shape: the Forest Path 20 x 6 x 4, the Wandering Lands 6 x 10 x 4, Elfdrit 6 x 30 x 4.
- **Tellus in the Tower of Mysidia (mod).** `nowalk` clears the entry's walk target, as most zones have none. The log line ends with `walk off` when it took, or `walk kept`.
- **Tablet Shards (world).** The category is progression (skipping balancing), so every shard counts, in Universal Tracker too. In a seed nothing changes: all 99 were marked already.

**Round 75, in play (mod 0.59.0 build 2dc8cf35, world 0.28.0 build ea6ac2e8, 2026-11-16).** A new seed of the user's.
- **Radar:** with two radars the log said `step 40, found 22`, and Radar Treasure 4 was dug. Works.
- **The Resonance Stone chest** sent its check (`chest:3260:3`), with a Tablet Shard from the pool. Works.
- **Tellus in the Tower of Mysidia:** `walk off`, and the fight started with no walk. Works.
- **Tablet Shards:** Oblivion Palace's chests came into logic in Universal Tracker. Works.
- **Tellus in the Forest Path, and Elfdrit: nothing on the first pass.** Tellus started only on a later visit, near the save point. Elfdrit started on the way back, and then every time after a reload. The same was true of Tellus in Mysidia: three shinies were taken between the first pass and the fight. The base class `CPP_MapGimmick` has a state, `m_GimmickCondition` (Active 0, Deactive 1). The game judges it at the map's load from the zone's rows as they are then: `{progress:0}==7050` is false at story 8000, so the zone is off. The mod writes its rows about 2 seconds later. The game looks again only when a flag changes in its own way, such as a shiny taken. Lux and Ignis worked the same way; their players took a shiny or a chest first.
- **The Forest Path's fight sent "Wandering Lands: Tellus".** The two zones share group 9048 and flag 1251, and the location took map 3270's name.

**Round 76, before play (mod 0.59.0, world 0.28.0, same versions):**
- **Zones on the first pass (mod).** For a boss zone (an `EventTrigger` class) not yet won, the mod sets `m_GimmickCondition` to 0 with `SetGimmickCondition` when it is not 0. The log's story boss line ends with `1 zones turned on` when it did. Doors are left alone.
- **Tellus's place (world and mod).** The fight is the Forest Path's: the location is "Forest Path: Tellus" (map 3271 in `data/bosses.tsv`), with the same id and rules. The Wandering Lands zone (3270) is left to the story, which never runs it at story 8000.

**Round 77, public pre-release feedback (v0.28.0: mod 0.59.0 build 1c03b1ed, world 0.28.0 build 6df97dd3, 2026-11-16).** Several Discord players. Mostly positive: the run works end to end. The notes are in `.reference/2026-11-16_feedback/`. What each report points to, from a first look at the data:

| Report | First look |
|---|---|
| A player climbs an invisible ladder in Mt. Thunderclap (3050). In the story Lid's paid shortcut puts a ladder there; unpaid, you let it down from the top. | The user wants the ladder there but up, to let down from the top; if not, gone. `gimmicks.tsv` shows no ladder gimmick on 3050, so it is probably a mesh or a gimmick in another class. Find the ladder's actor and what the payment sets. |
| After a mod update, and on a second PC, the save needs `/bind` again, and every item already received comes again. | The applied count lives only in `ap_state.txt` (per PC), and the install steps say to delete it on an update. A newly bound save starts at 0. Fix: keep the count and a seed tag in the save itself (IDEAS 35). |
| What happens in the final 1-v-1 with Sol when Rain is not in the party? | Not tested. Rain (1001) is the default first party member but can be left out or be a pool item. Test with `ffrap_story` at the tower top; if it breaks, give Rain to the party with fixed gear for that fight. |
| Nameless Ruins: Tellus's zone fired only after walking past and back. | Round 76's first-pass fix covers `EventTrigger` zones. The Nameless Ruins fight is on a door (`reopen`, round 74), which that fix leaves alone. Needs the log. |
| A player landed on the island between Grandshelt and Lanzelt without Grandshelt Unlock. | Every landing point is in a continent box, but the boxes leave a gap at x 18200 to 20600 below y 17500 (Lanzelt ends at x 18200, Grandshelt starts at y 17500). Likely the island. Needs its position. |
| Late bosses have far too much HP (Siren, level 57: 2,434,404 HP). | `stat * growth^(levels)` compounds. Cap the boss HP growth above level 20 or so. |
| Physical skills fall behind magic. | Scale enemy Defence less steeply. |
| Small parties are wiped by opening attacks. | Cut boss power by a set % for each empty party slot. |
| Wind Shrine Chest 1 (vanilla Mist Hi-Potion) and Waterfall Way Chest 5 (Aquatic Veil) in logic but out of reach. | One report each. Find each chest's position and what stands in front of it. |
| World Map Shiny 167 in logic on a Gronoa start with no airship. | At x 19347, y -19766, the Gronoa NW peninsula. Add it to `data/airship_only.tsv` after a check of the walk. |
| Nameless Ruins Chests 2 and 5 (Magicite, Tyr's Armor) and Shard 14 need both Liquid Flame (9088) and Iron Giant (9089). | Add `after_boss` for both. |

**Round 77, before play (mod 0.60.0 build 8ef015af, world 0.29.0 build e63e4438):** the first cycle after v0.28.0, so both versions moved.
- **Save stamp (mod).** The save keeps its seed's tag and the applied count in event flags 1414 to 1449 (IDEAS 35). A save loaded on another PC, or after `ap_state.txt` is deleted, links itself and gets only what it lacks. Log lines: `save is stamped with this seed: it holds N items`, and `stamp: N items (k flags)` when it is written.
- **Grandshelt island (mod and world).** The Grandshelt/Lanzelt line moves from y 17500 to y 16700 for x 12700 to 15400, from Grandshelt's landscape tiles (`docs/open_world.md`). World Map Shiny 127 is on Grandshelt now.
- **Scaling (mod).** Bosses take HP from a curve fitted to the game's own bosses (Siren at 57: about 320,000, was 2,434,404). Defence grows by the curve's factor to the power 0.75. Bosses lose 12% power per empty party slot of four (`docs/open_world.md`).
- **Logic (world).** World Map Shiny 167 needs the airship. Nameless Ruins Chests 2, 4 and 5, Shard 14 and Tellus need Liquid Flame and Iron Giant: the blocking bases at y -11975 (flag 527) and y -15996 (flag 526) stand before them.
- **Readable names (world).** Every chest, shiny, Tablet Shard and radar treasure has a new name (IDEAS 34). `data/location_names.tsv` has the old and new names. Ids are unchanged, so a seed generated on 0.28.0 keeps working with the new client.
- **Found off-line, for the probes below:**
  - The invisible ladder in Mt. Thunderclap is `BP_MapGimmick_StringLadder_C_2` (uid 20) in `Dng_04Dir_40_01_GD`. Its `VisibleCondition` and `m_FlagCondition` are both `{flag:205}`, the flag Lid's paid shortcut sets. Hidden, its ladder part (`BP_MapGimmickLadder_C_2`) is still climbable. Uids 18 and 19 are rope ladders with no condition and `interactType` Check: the kind you let down from the top. Uid 20 may behave the same with its `VisibleCondition` cleared.
  - Wind Shrine Chest 1 (now "Wind Shrine - Mist Hi-Potion Chest") is at z 5270 by the lift at (13600, 37000); Waterfall Way Chest 5 ("Waterfall Way - Aquatic Veil Chest") is at (310, -16290) by in-map warp 9. Nothing in the data closes either.

## Round 74 test plan (mod 0.59.0 build d8e6e426, world 0.28.0 build ddd8aeb4)

**Install:** copy `FFRArchipelago/Scripts` and `dist/ff_resonance.apworld` into `custom_worlds`, and generate a new seed. The radar and door fixes also work on an older save.

**0. The builds.** The log should say `version 0.59.0 (build d8e6e426)` on load, and `client: world version 0.28.0 (build ddd8aeb4)` once the client connects. The client says the same on start. **Do they match?** If not, an older copy is installed.

**1. The radar.** Receive a Progressive Radar. The log says `radar: level 1 (flag 702 true, step 20, found 0)`. Fly over the sea.
- **Does it ping, and can you dig Radar Treasure 1?**
- After treasure 5 the radar should go quiet until a second radar comes (step 40). After treasure 9 it should go quiet until the third (step 50).
- If all three radars come before any dig, the step should still start at 20.

**2. The Nameless Ruins stairs.** Beat Tellus there, or go back on a save where he is beaten. **Do the stairs lead to the upper floor now, and is Chest 4 there?** Then **can you reach Odin's place** (the tester thought the stairs were the way)?

**3. Places past bosses.** In Universal Tracker:
- Tower of Mysidia Chest 3 should wait for Tellus's needs.
- Duggle, Gronoa Shrine and Sanctissimus Shrine should wait for Lux's (five members, four continents, a group heal or a revive).
- Lake Ryusei, the Forest Path and the Wandering Lands should wait for Ignis's.

Some of these came from positions only. **Please check them in game:**
- Is Dragon's Maw's south door the way in from most of Pharm, and do all seven chests and Shard 4 lie past Intangir's box?
- What does the Rogue Magitek Weapon's box block?
- Can the airship land on Pharm's plateau, by Lake Ryusei? If it can, the plateau needs Ignis or the Airship, as Dirnado does.
- Are Earth Shrine Chests 4 to 6 past Belmodar?
- Is Catacumba Cave (west Gronoa, low ground) on Gaberada's side?

**4. Magicite.** **Do World Map Shinies 4 (Dirnado) and 189 (Pharm) send a check** and give the pop-up's item, not a Magicite Shard? **Do bosses stay out of logic until Magicite comes?**

**5. Bosses on Normal.** **Do they feel fairer?** The double-action bosses now need one more member in logic, and Normal's bosses are a little lower and weaker. Note your party's size and levels for a fight that felt wrong either way.

Send the `[FFRAP]` lines of the log and any crash folder.

## Round 75 test plan (mod 0.59.0 build 2dc8cf35, world 0.28.0 build ea6ac2e8)

**Install:** copy `FFRArchipelago/Scripts`. For the Resonance Stone chest and the Tablet Shard fix, also copy `dist/ff_resonance.apworld` into `custom_worlds` and generate a new seed. The radar and boss zone fixes work on the old seed too.

**0. The builds.** The log should say `version 0.59.0 (build 2dc8cf35)` on load, and with the new apworld `client: world version 0.28.0 (build ea6ac2e8)`.

**1. The radar tiers.** With one Progressive Radar the log says `radar: level 1 (flag 702 true, step 20, found 13)`.
- **Do treasures 1 to 5 all ping at once?** Dig one out of order, such as 3. The log shows found go to 12 and back to 13. **Do the rest still ping?**
- With the second radar, found 22 and step 40: **do 6 to 9 ping too?** With the third, found 31 and step 50: **10 to 13?**

**2. The Resonance Stone chest (new seed).** Open Mt. Reizan's Chest 3. **Does it send a check and show the pop-up, with no Resonance Stone?**

**3. Tellus in the Tower of Mysidia.** Walk into the zone from the east or west side. The log line for map 3200 should end with `walk off`. **Does the fight start, with no walking?** If it says `walk kept`, the game did not take the change; tell me.

**4. Tellus in the Forest Path (map 3271).** The zone is a line across the path near the north end, about 30 m west of the north exit (the door at 2215, 39680 that leads to the world map). The other one is in the Wandering Lands (map 3270), at the far north end (y 102590), next to where you come in from the second Wandering Lands map (3272). Either one is the fight, and winning it once counts. **Does walking through the Forest Path's north end start it now?** If not, `ffrap_status` near the spot, and the log, will help.

**5. Elfdrit in Gronoa Shrine.** The zone is longer and deeper now. **Does it still start the fight where it did before?**

**6. Oblivion Palace in Universal Tracker (new seed).** **Do the Palace's chests come into logic as shards come in, up to the 99-shard chest?**

Send the `[FFRAP]` lines of the log and any crash folder.

## Round 76 test plan (mod 0.59.0 build 1c03b1ed, world 0.28.0 build 6df97dd3)

**Install:** copy `FFRArchipelago/Scripts`. For the Tellus name, also copy `dist/ff_resonance.apworld` into `custom_worlds` and generate a new seed. The zone fix works on the current seed.

**0. The builds.** The log should say `version 0.59.0 (build 1c03b1ed)`, and with the new apworld `client: world version 0.28.0 (build 6df97dd3)`.

**1. Boss zones on the first pass.** Go to a boss you have not fought, with no shiny or chest on the way: Tellus in the Forest Path, Elfdrit, Lux or Ignis. The story boss line should end with `1 zones turned on`. **Does the fight start the first time you walk into the zone?**

**2. Tellus's name (new seed).** **Does the Forest Path's fight send "Forest Path: Tellus"?**

Send the `[FFRAP]` lines of the log and any crash folder.

**Round 77, first try (mod 0.60.0 build 8ef015af, world 0.29.0 build e63e4438, 2026-11-17).** The user's own new seed.
- **The Archipelago new game started in chapter 1, at the Earth Cave.** The log said `open world start is off`. The user had deleted `ap_in.txt` for the new seed while the client was open and connected. The client writes the seed line once, on connecting, so the mod never heard of the new seed. It took the old seed from `ap_state.txt`, with no settings, and ran the plain prologue skip.
- The old save read "not linked to the seed": right, as it is the old seed's. Steam Cloud upload errors at the same time were IPv6 connections failing on Steam's side (`Steam/logs/cloud_log.txt`, "failed to issue"), not the save.

**Round 77, second build (mod 0.60.0 build a659ff7d, world 0.29.0 build 08eba742):**
- **The skip waits for the client (mod).** The automatic prologue skip runs only once a seed line has come in this run (or with `ffrap_openstart on`). Until then it says once: "connect the client to this seed. The prologue skip waits for it". The story holds at 1005, so connecting late works. The title notice says the same when no client has written yet.
- **A deleted `ap_in.txt` is written again (client).** While connected, the client checks that the file exists and, if not, writes the seed, the settings, every item from index 0 and the scouts again. The mod already rereads a new file from the top and applies items by index, so nothing is granted twice.

**Round 77, a crash (mod 0.60.0 build a659ff7d, 2026-11-17 10:30).** On a new seed (Zoldaad start), about a second after walking from Zoldaad Castle's courtyard (2111) into the castle (3160).
- `UECC-...D8790B61`: an access violation in UE4SS's `FName::ToString`, reading 0x100, from a UObject handle's `__index` in a game-thread Lua loop (`process_simple_actions`), one Lua `pcall` deep. The same signature as round 71's second crash.
- The last mod lines are the map change and `chest blanking: 0 rows`. Nothing else ran that logs.
- **The stack does not say which mod's loop it was.** FFRS_QoL was on too (MapMarkers 1), with eight game-thread loops (`gameLoop`), and its HUD keeps widgets from tick to tick and asks them `IsValid()` (`hudWidget`); its own comment says they "may be garbage collected" after a map change. That is the pattern that crashed this mod in round 71. Round 71's crashes had no other mods in, so this mod is not cleared either.

**Round 77, third build (mod 0.60.0 build 08cabc86):** for 12 ticks (6 s) after each map load, `ap_trace.txt` gets a line before each step of the mod's two loops (`map load`, `tick`, `items`, `loot`, ..., `tick done`). After a crash, a last line without its `done` names this mod's step; a `done` as the last line means the crash was in another mod's loop.

**Round 77, a second crash (mod 0.60.0 build 08cabc86, 2026-11-17 13:07), with FFRS_QoL off.** Going from the world map (1000) into the dungeon 3050, within a second or two of the load.
- `UECC-...E3BA7FB5`: the same stack as the first, `FName::ToString` reading 0x100 from a UObject handle's `__index`, in `process_simple_actions`, one Lua `pcall` deep.
- `ap_trace.txt` ends `map load`, `fast tick`, `fast tick done`. This mod's loops were not running when the game crashed.
- The log's last lines are BPModLoaderMod spawning the level's mod actors, ModSettings' last.
- **The likely cause is ModSettings' Lua (`Mods/ModSettings/Scripts/main.lua`), as round 63 suspected.** On each new hint strip (`WBP_ModSettingsHint`, shown at every level load), `NameBothKeys` queues callbacks at 50, 200, 800 and 2000 ms. Each runs `pcall(function() if not hint:IsValid() ...)` from `ExecuteInGameThread`: one `pcall` deep, as on the stack. When the hint is freed before a callback runs, `hint:IsValid()` reads freed memory. Round 63's deck crash and round 71's two crashes had the same shape and timing, and ModSettings was in `mods.txt` then too.
- The fix is in ModSettings: keep the hint's path (`hint:GetFullName()`) and find it again with `StaticFindObject` in each callback, as this mod does since round 72.
- **From the ModSettings Blueprints (dumped off-line with its pak beside the game's):** `ModActor`'s BeginPlay creates the hint when the panel's **Hint on map load** toggle (`HintOnLoad`, on by default) is on, adds it to the viewport, and removes it after a `Delay`. The actor keeps it in its ubergraph frame, so that hint may not be freed in the 2 s. A second cause fits as well: the ModSettings Lua runs its `ExecuteWithDelay` callbacks on UE4SS's async thread, and they call `ExecuteInGameThread` in the same Lua state that the game thread runs. That is the race that crashed this mod at random in round 29. `BP_ModSettings.Toast` also removes every hint on screen and makes a new one, held only by the viewport.
- **This mod cannot patch it.** Each UE4SS Lua mod has its own Lua state, so this mod cannot reach ModSettings' callbacks. The only lever is to turn off ModSettings' `HintOnLoad` toggle, which is the player's choice in another mod, is saved, and leaves the thread race in place. The user's call: list it as a known conflict. The README and the playtester guide say to turn off **Hint on map load** (F10), or to set `ModSettings : 0` in `mods.txt`.

## Round 77 test plan (mod 0.60.0 build 08cabc86, world 0.29.0 build 08eba742)

**Install:** copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the client before deleting anything in the mod folder (it now writes `ap_in.txt` again if you do not), and start it again after. Generate a new seed for the names and logic. The mod parts also work on a 0.28.0 seed. Keep `ap_state.txt` this time.

**0. The builds.** The log should say `version 0.60.0 (build 08cabc86)`, and the client `world version 0.29.0 (build 08eba742)`.

**1. The save stamp.**
1. Load your linked save from round 76 with the new mod. The log should say `stamp: N items` once, N the items you have. Save the game.
2. Close the game, rename `ap_state.txt` to `ap_state.old.txt`, start the game and connect. Load the same save. **Does it link by itself (`save is stamped with this seed`) and grant nothing again?**
3. If you have a second PC with Steam Cloud, load the save there. **Same question.**
4. Put `ap_state.old.txt` back afterwards if you like; it is no longer needed for stamped saves.

**2. Grandshelt island.** With Lanzelt open and Grandshelt locked, fly over the land at the north end of the stone bridge (around World Map Shiny 127). **Is the shadow red there?** Then check that landing on Lanzelt's coast south of the bridge still works.

**3. Boss scaling.** Fight a boss you know well, and note the party size. The scale line in the log ends with `(n in the party)`; **is n the number in your battle party?** (If it counts reserve members too, the cut never applies.) Change the party size on the field; the log should show a new scale line. **Do bosses feel right on HP? Do physical skills keep up with magic?** Libra on a late boss gives the HP to compare with Siren's 2,434,404.

**4. Readable names.** **Are the new names in the client and Universal Tracker easy to find in game?** Note any that send you to the wrong place. `data/location_names.tsv` has a `name` column for your own names.

**5. Probes for next round (when you pass by):**
- **Mt. Thunderclap ladder:** stand by Lid's shortcut ladder (the invisible one) and run `ffrap_inspect BP_MapGimmick_StringLadder001_C`. Then the same at the top of the climb. Send the log lines.
- **Wind Shrine Chest 1 and Waterfall Way Chest 5:** if you go there, a screenshot of what stops you.
- **Nameless Ruins Tellus:** if the fight starts only on a second pass, send the log from entering the map to the fight.
- **The final duel without Rain:** if you reach the tower top without Rain, say what happens in the 1-v-1.

**6. If the game crashes:** send `Mods/FFRArchipelago/ap_trace.txt` with the crash folder and the log, before starting the game again (the next map load rewrites it). To test the ModSettings finding, turn off **Hint on map load** in the F10 panel, or set `ModSettings : 0` in `Mods/mods.txt` (this turns off only its Lua key binding; the Blueprint panel and its Toast stay), then go in and out of maps for a while.

Send the `[FFRAP]` lines of the log and any crash folder.

**Round 77 results (mod 0.60.0 build 08cabc86, world 0.29.0, 2026-11-17).** The user's own seed, levels 1 to 30, and a level 1 cheat-scaled run to the end.
- **Save stamp:** it seems to work. Steam Cloud's servers had trouble that day, so the second-PC test waits.
- **Grandshelt island:** not tried. Next round, with the players' feedback.
- **Boss scaling:** much better. The party size cut works. Only levels 1 to 30 were played.
- **Readable names:** the user set their own names in `data/location_names.tsv`. They are final for now.
- **Mt. Thunderclap ladder:** no one climbs an invisible ladder. At the top of the cliff an Examine prompt lets the ladder down, as in the base game, and the player can then climb it. Only the ladder's mesh is missing. `ffrap_inspect BP_MapGimmick_StringLadder001_C` gave the first ladder of the class, uid 18 (`BP_MapGimmick_StringLadder_C_0`, lowered, no condition), not uid 20. Uid 20's `VisibleCondition` is `{flag:205}`, the flag Lid's payment sets (event `C02_205`, story 2040). On an open start flag 205 is off, so the mesh stays hidden. Setting flag 205 would also lower the shortcut from the start, so it is not done. A cosmetic issue, left for later.
- **Wind Shrine Chest 1 and Waterfall Way Chest 5:** reachable. The players missed them.
- **Nameless Ruins Tellus:** the fight starts on the first pass now.
- **The final duel without Rain:** it worked, and the goal was sent. This was on a level 1 run with cheat scaling, so a normal levelled save is still to be tried.
- **Crashes:** two, both in the ModSettings Lua mod (see above). It is a known conflict in the README and the playtester guide.

## Round 78 test plan (mod 0.61.0 build d9576a0a, world 0.30.0 build 33c2ffa5)

Side quests as locations (`docs/side_quests.md`) and the Mechabo start (IDEAS.md idea 33).

**Install:** copy `FFRArchipelago/Scripts` (it has a new file, `quests.lua`), and copy `dist/ff_resonance.apworld` into `custom_worlds`. Generate a new seed with `include_side_quests: true` in the yaml (it is off by default). Keep `shuffle_visions` on.

**0. The builds.** The log should say `version 0.61.0 (build d9576a0a)`, and the client `world version 0.30.0 (build 33c2ffa5)`. On the first load of the seed's save the log should say `quests: N reward rows set to the pop-up's stand-in`. There are 43 rows, and N may be twice that, as the game holds the rows in two tables.

**1. Rear Support, Ahoy! (Grandport Harbor, Lanzelt; short).** Talk to Zile, deliver the 4 Turbo Ethers at the quest board, and finish the quest.
- **Does the reward pop-up show the Archipelago item?** The log should say `check quest:13`.
- **Do you still get the 500 gil, and no Magicite Shard?**

**2. A vision quest.** Any of The Shield of the Weak (Charlotte, Grandshelt), Victoria Revivified (Mysidia) or Errand's End (Amelia, after Token Legacy). At the end: **does the pop-up show the Archipelago item, with no vision and no Magicite from the quest?** The vision should come only when its Archipelago item arrives.

**3. Secrets Unearthed (Chloe, Felicitas), if you pass by.** At the end: **is the pop-up the Archipelago item, and does the Magicite Shard still come with it?**

**4. Mechabo (Dwarven Forge, Dirnado).** The log should say `mechabo: progress 16 set to 10` once on the seed's save. **Is Verun at the forge?** Does talking to him play his first meeting, or go straight to the repair request? **Does "Arise, Mechabo!" show in the quest log?** These three quests are not locations yet.

**5. Probes, when you pass by:**
- **The Phantom Train and the Weapons Factory** (Zoldaad): can you get in on our start? The Call from Beyond (from the Imperial Residences) and O General! My General! need them.
- **Mog Tag (Mysidia):** one catch gives a check (`quest:34`); the next two tiers give `quest:35` and `quest:36`.
- **Any quest:** note any whose reward came out wrong: the vanilla item, two pop-ups, or none.

**6. If the game crashes** in a quest's reward scene, send the crash folder, the log and `Mods/FFRArchipelago/ap_trace.txt`. The vision quests' rows are rebuilt from an empty list, the step most likely to go wrong.

Send the `[FFRAP]` lines of the log.

**Round 78 results (mod 0.61.0 build d9576a0a, world 0.30.0 build 33c2ffa5, 2026-11-17).** The user's seed with `include_side_quests` on, started on foot in Olderion with the airship parked. Also the log of FieryBlizzard, a pre-release player on v0.29.0 (mod 0.60.0 build 08cabc86). The notes are in `.reference/2026-11-17/`. The user did not get to every quest yet.
- **Side quests work.** Six quests sent their checks: Medicinal Mission (29), Nichol's Duty (4), The Tide from the Sky (21), Last Respite (5), A New Leaf (0) and the vision quest The Shield of the Weak (28). The vision came only from its Archipelago item. On the normal quests the pop-up showed only the Archipelago item, and the logic held. Log: `quests: 86 reward rows set to the pop-up's stand-in` (43 rows in two tables).
- **Quests with a stat bonus or an esper showed the stand-in Potion.** On Nichol's Duty, Last Respite and A New Leaf the pop-up said Potion, and the Archipelago item came in the feed after it. These are character quests, and the counter moves at the start of a long reward scene. The mod waited 30 s for the pop-up and gave up (`no chest pop-up on screen` for quests 0 and 5). On quest 4 it wrote into the stat bonus dialog, which also says "obtained" but has no item line (`text set (no item line found to hide)`), and the item pop-up after it kept the Potion. The Potion itself comes on every quest: it is the stand-in the game's pop-up needs.
- **Mechabo:** `mechabo: progress 16 set to 10` once, as planned. Verun and the quest log not checked yet.
- **Checks sent with nothing picked up.**
  - The user: Colosseum Shard 2 (`shiny:2016:2`) 3 s after entering the Colosseum for the first time. No pop-up came (`no chest pop-up on screen`).
  - FieryBlizzard: after the Sanctum of Cecil (10211), groups of world-map shinies were sent each time they boarded the airship: 49, 57, 58, then 5, 24, 25, 100 and 102, which are on other continents, and later 1, 3, 4, 7, 21, 22, 82, 99, 104, 105, 127, 128, 130 and 150. Each group came with `locks: 6 boxes on the airship's shadow list (0 -> 6)`, the airship being made again. Their map marker mod's "looted" count did not move for them, and three pick-ups later had no check line: those shinies were still in the game, and the player picked them up after their checks were out. Three Wind Shrine chests (`chest:2130:1`, `:3`, `:4`) were also sent 3 s after a first arrival.
  - What read them as taken is not known. A shiny is sent when the live actor's `m_IsOpen` is true or the save's own row for its map says open, and a scouted shiny on the map also on the save's row alone. The log did not say which. The chests go by `m_IsOpen` alone, so for them it was the live actor.
- **Dragon's Maw was in logic at the start, Intangir was not.** With the airship, the world let the airship stand in for Intangir for all of Dragon's Maw (round 74's rule for its north door). The user: every chest there is past Intangir. FieryBlizzard's run agrees: from the south door they met Intangir before any chest, then Chests 7 and 6, then the Rogue Magitek Weapon, then Shard 4 and Chests 5, 3, 4 and 2, out of the north door, and Chest 1 by the north door on the way back in.

## Round 79 test plan (mod 0.61.0 build 5f81a706, world 0.30.0 build a1ccfcdb)

**The fixes:**
- **Mod: a chest or shiny is sent only with the player near it.** One read as taken farther than 1500 units from the pawn waits until the player walks up to it. Each one held is logged once a visit: `shiny:1000:100 reads taken (live open, save row true), 21345 from the player; not sent until the player is near it`. Each check line now says what read it as taken: `check shiny:1000:47 (live open, save row true, 120 from the player)`. Chests carry their place now (`x`, `y` in `game.LiveChests`).
- **Mod: a quest's pop-up waits through the reward scene.** It counts down only while the field is on screen, and it writes only into a dialog with the item line, so the stat bonus dialog is left alone.
- **World: every location in Dragon's Maw needs Intangir** (`AFTER_BOSS` in `tools/gen_apworld_data.py`): its seven chests, Shard 4 and the Rogue Magitek Weapon. World Map Shiny 149 by the north door still needs Intangir or the airship.

**Install:** copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Generate a new seed for the Dragon's Maw logic; the mod parts also work on the round 78 seed.

**0. The builds.** The log should say `version 0.61.0 (build 5f81a706)`, and the client `world version 0.30.0 (build a1ccfcdb)`.

**1. Early checks.** Play as usual, and board the airship often. Look for `reads taken` lines in the log.
- **When one shows, is the shiny or chest still there?** If it is, pick it up: the check should go out then, with a pop-up. Note which signal the line names (`live open`, `save row true` or `save row only`).
- **Does any check go out with nothing picked up?** The check line says how far the player was.
- A shiny you picked up should still be sent at once, with its pop-up, as before.

**2. Quests with a stat bonus or an esper.** Nichol's Duty, Last Respite or A New Leaf (on a new seed), or any other character quest. **Does the last pop-up show the Archipelago item now?** The log should say `chest pop-up for quest:N: text set, item line hidden`. The stand-in Potion still comes, as on every quest.

**3. Dragon's Maw.** In Universal Tracker, Dragon's Maw should be out of logic until Intangir is. **From the north door, can you reach any chest before a fight?** If you can, those chests need the airship only, and the logic is stricter than the game.

**4. The quests from round 78's plan** that were not done yet: Rear Support, Ahoy!, Secrets Unearthed, Mechabo (is Verun at the forge, does "Arise, Mechabo!" show), the Phantom Train and the Weapons Factory, and Mog Tag.

Send the `[FFRAP]` lines of the log.

## Round 80 changes so far (mod 0.61.0 build cac73e78, world 0.30.0 build a1ccfcdb)

Built during round 79, before its results. The plan gets the round 79 fixes too.

**The change:**
- **Mod: the Oblivion Palace safes open with no talk to the princess** (IDEAS.md idea 37). Safe *n* opens at story counter 43 >= 11 + *n*. The mod holds that counter at 10 plus the steps the shards pay for, held plus turned in. The shards stay in the bag. A talk to her still takes them and plays her talks at 28, 60 and 99 turned in.

**Install:** copy `FFRArchipelago/Scripts`. No new seed needed: the apworld is unchanged.

**To test:**
- **First try (build 7c4eba1d, 2026-11-18):** the user's save had 6 shards turned in (counter 12) and 4 held, so the 9-shard safe should open. It did not: the mod read the turn-ins on the world map, where the game says 0, and not again in the palace (`palace: 4 shards held, 1 steps paid, progress 43 at 12`). Fixed in build cac73e78: turn-ins are read in the palace only (IDEAS.md idea 37).
- **0.** The log says `version 0.61.0 (build cac73e78)`. In the palace: `palace: N shards held, T turned in, K steps paid, progress 43 at X`, with X = 10 + K. Before the first visit, `not read yet turned in`.
- **1. Walk in with no talk.** Holding shards, enter the palace without talking to her. **Can you open each safe your shards pay for (3 shards for the first, 6 for the second, and so on), and no more?** Each should send its check.
- **2. A safe in view.** Stand in the palace and receive a shard that pays for a new safe. **Does that safe open at once, or only after you leave and come back?**
- **3. The princess.** Talk to her once. **Does she take the shards and skip the "earned a chest" scenes?** The `palace:` line should then read 0 shards held, with the same steps paid. If you reach 28 turned in, does her milestone talk play?
- **4. A save from before.** On a save where you already turned in shards the old way, the counter should stay where it was or go up, never down.

**Results so far (build cac73e78, 2026-11-18):**
- **Walk in with no talk: works.** On the user's save (6 turned in, 4 held), the 9-shard safe opened.
- **A safe in view: only after a new visit.** Three shards sent from Archipelago while in the palace opened the next safe only after leaving and coming back. Then it opened at once. Left as it is (IDEAS.md idea 37 has the likely fix).
- **The princess and an old save:** not tried yet.

**Round 79 results (mod 0.61.0 build cac73e78, world 0.30.0 build a1ccfcdb, 2026-11-18).** The user's seed, on foot, no airship yet.
- **Early checks:** none so far. No airship yet, so the boarding case is untested.
- **Token Legacy (quest 6) still showed the stand-in Potion.** The order on screen: the reward pop-up (Potion), then the stat bonus box, then the Archipelago item in the client. So the reward pop-up comes first, not last. The log has `check quest:6` at 11:19:12 and no pop-up line at all: the check came after both pop-ups had closed, and a shiny's pop-up replaced the waiting one later.
  - **Why:** the reward row `ChrEv_0070_006_01` gives the item, completes the request and sets counter 7 to 60, all in one row. The game applies the counter after the row's pop-ups. Secrets Unearthed (quest 16) set its counter before its pop-up, which is why it worked.
  - **Fix (build 42898077):** `quests.lua` now has each quest's reward `map` and the counter's value `before` the reward row, from `quest_steps.tsv` (Mog Tag has several and gets none). While a quest's counter reads `before` on its map, an item pop-up in an event there is that quest's: the mod writes it before the check (`chest pop-up for quest:6 before its check: ...`) and the check later writes nothing.
- **The Weight of Mercy (quest 20)** went out 17 s after Secrets Unearthed, in the same town, and its pop-up was never found (`no chest pop-up on screen`). Not asked about yet.
- **Dragon's Maw:** not in logic yet.
- **Quests:** Rear Support, Ahoy! and Secrets Unearthed worked. The Phantom Train and the Weapons Factory are open; not done yet. Mog Tag not reached.

**Round 80, a crash (build cac73e78, 2026-11-18 11:20:03).** On the world map, about 5 s after walking out of Zoldaad (2102). FFRS_QoL (MapMarkers 1) and FFRBestiary were on; ModSettings is gone.
- `UECC-...B474475`: an access violation in `RC::LuaType::push_intproperty`, reading 0x230440020. A Lua loop read an int field (`obj.Field`) of a freed object. The C frames show the loop's callback, then two Lua `pcall`s, then the read.
- `ap_trace.txt` ends `tick 3840 tick done` at 11:20:03. That was the 12th tick after the load, the last one the trace covered, so it cannot say whose loop it was.
- **The shape fits this mod's loops** (`every` → `pcall(tick)` → `pcall(step)`) **and FFRS_QoL's world-map loop** (`guarded` → `pcall(fastWorldMap)` → `wldMapId` → `pcall(function() return s.WldMapId end)`, an int field). The minidump holds no Lua state, so it cannot tell them apart.
- **Build 42898077 traces all the time:** one file handle, unbuffered, started again at each map load and every 4000 lines (about 90 s). The fast tick has two more steps (`fast: pop-up`, `fast: scans`).

## Round 81 test plan (mod 0.61.0 build 27ed563a, world 0.30.0 build a1ccfcdb)

**Install:** copy `FFRArchipelago/Scripts`. No new seed: the apworld is unchanged.

**0. The build.** The log should say `version 0.61.0 (build 27ed563a)`. Build 27ed563a is 42898077 plus the `ffrap_empty` probe (step 4).

**1. A character quest's pop-up.** Token Legacy is done, so try another with a stat bonus: Nichol's Duty, Last Respite, A New Leaf, or any character quest. **Does the first pop-up (the reward) show the Archipelago item?** The log should say `chest pop-up for quest:N before its check: text set, item line hidden`, then `check quest:N`.

**2. Normal quests still work.** On The Weight of Mercy or any town quest: one pop-up with the Archipelago item, and one `chest pop-up for quest:N` line.

**3. The round 79 and 80 items still open:** early checks once you have the airship, Dragon's Maw, the Phantom Train and the Weapons Factory, Mog Tag, the princess talk, and an old save's counter.

**4. Probe: empty rewards (IDEAS.md idea 15, way 1), on a save you can reload.** Save first. `ffrap_empty` makes rewards give nothing, in place of 1 gil or the Potion. A game restart undoes it. Each case asks: **does it open, is there a game pop-up (and what does it say), does the check go out, and is it still taken after you leave and come back?**
- **A chest:** in a dungeon with a closed chest that is a location, run `ffrap_empty chest`. The log lists the chests marked and `empty: N chest rows emptied`. Open one.
- **A shiny:** where a shiny is still there, run `ffrap_empty shiny`, then pick it up.
- **A quest:** before the last step of a quest, run `ffrap_empty quest <id>`, with the id from the check line (`quest:20` is 20). Finish it. **Does the quest still complete in the quest log?** The Weight of Mercy (20) or any town quest will do.
- `ffrap_empty off` puts chests back to 1 gil.
- If it works, the mod can drop the 1 gil and the Potion and show its own text when a check goes out. If an empty chest will not open or is not saved as taken, the idea is out.

**5. If the game crashes:** send `Mods/FFRArchipelago/ap_trace.txt` with the crash folder and the log, before starting the game again. A last line without its `done` names this mod's step. A `done` last means another mod's loop. If the crashes keep coming on the world map, try a session with FFRS_QoL off (`enabled.txt` out of its folder).

Send the `[FFRAP]` lines of the log.

**Round 81 results so far (build 27ed563a, 2026-11-18).**
- **Empty chest (step 4):** `ffrap_empty chest` in map 3140 marked 5 chests (`15 chest rows emptied`: 5 rows in 3 tables). Chest 3 opened, its check went out, and **the game still showed its own "obtained" pop-up, with the item line**. The mod wrote the Archipelago text into it and hid the line, as with 1 gil. The user: it worked.
- **Empty shiny:** `ffrap_empty shiny` emptied shinies 10 and 11. Shiny 10 opened and showed the game's pop-up, which the mod rewrote. No new check: the save had been loaded from before a later save (`82 applied (was 83)`), and shiny 10 had been sent already. The mod shows the pop-up again for a known check, and sends nothing.
- **What this means for idea 15:** way 1 does not take the game's pop-up away. It takes away the 1 gil and keeps the pop-up for the mod to write into. The remaining questions: what the hidden item line said (blank, or "0"), and whether an empty chest is still taken after leaving and coming back.
- **The 0 gil:** the user saw "0 gil" on the empty chest's item line before the mod hid it. So an empty chest shows a "0 gil" pop-up, not a blank one.
- **Empty quest (Rogue Rebel, quest 30):** `ffrap_empty quest 30` emptied its reward row (`2 reward rows`, the row in two tables). The game still showed an "obtained" pop-up with an item line, and the check went out 3 s later. What the line said was not seen: the mod wrote it first.
- **The quest pop-up fix works in game.** Rogue Rebel also sets its counter after its pop-up: `chest pop-up for quest:30 before its check` at 12:03:22, `check quest:30` at 12:03:25. Without build 42898077's fix, this quest would have shown the Potion.
- **No Magicite and no Rose Circlet came, and the quest log shows Rogue Rebel complete.** So the pop-up was the empty row's own, as with chests, and the quest log's prize list gives nothing by itself.
- **Way 1 works for chests, shinies and quests:** an empty reward opens or completes as normal, the check goes out, and the game still shows its pop-up for the mod to write into. The 1 gil and the stand-in Potion are not needed. Not tried: the radar treasures and the boss rewards, which use the Potion too.

**Built after these results (mod 0.61.0 build 1d6caf0a, world 0.30.0 build dbf83717):** chests and shinies are blanked to nothing (`ItemId -1, ItemNum 0, Money 0`) in place of 1 gil, and each quest reward row loses the location's item (`item` in `quests.lua`) in place of the stand-in Potion. Gil and a second item in a quest row stay, as before. The radar treasures and the boss rewards keep the Potion: they were not tried empty. The `ffrap_empty` probe is gone. The apworld changed only in its game page (no more 1 gil).

## Round 82 test plan (mod 0.61.0 build 26b6adfa, world 0.30.0 build dbf83717)

**Install:** copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds` (only its game page changed; the round 79 seed still works).

**0. The builds.** The log should say `version 0.61.0 (build 26b6adfa)` and `chest blanking on for this save: N rows changed`; the client `world version 0.30.0 (build dbf83717)`. `quests: N reward rows without the location's item`.

**1. Chests and shinies.** Open a few chests and pick up a few shinies. **Does each show the Archipelago item, with no gil line?** A chest without a scout would show "0 gil".

**2. Quests.** Finish any quest. **One pop-up with the Archipelago item, the quest complete in the log, and no vanilla item?** A quest with gil (Rear Support, Ahoy!, The Weight of Mercy) should still pay its gil.

**3. Leave and come back.** After opening chests in a dungeon, leave and come back. **Are they still open?**

**4. The round 81 plan's steps 1 to 3 and 5** still stand (character quest pop-ups, the open items from rounds 79 and 80, the crash trace).

**5. Probe: an Archipelago entry in the main menu (IDEAS.md idea 38).** Build 26b6adfa is 1d6caf0a plus `ffrap_apmenu`. It needs no pak. FFR Bestiary can stay installed: its entry should stay too. Each step that writes logs an `apmenu:` line before it runs, so if the game crashes, the last `apmenu:` line names the step. A game restart undoes all of it. In game, on the field:
1. `ffrap_apmenu info`. Send `Mods/FFRArchipelago/ffrap_apmenu.txt`.
2. `ffrap_apmenu on`. Open the main menu. **Is there an Archipelago entry above System? Does it show its name, or "???" with a lock?** Pick it: **does the System page open?** That is expected for now.
3. If the entry is missing or shows "???", walk into a town or out to the world map so the menu is built again, and look again. If it is still wrong, restart the game and try `ffrap_apmenu on vision`, which uses a tag the game registers.
4. `ffrap_apmenu info` again (the file is written again). Send it with the log.
5. `ffrap_apmenu layout tutorial`, then open the entry again. **What opens?** Then try `layout option` and `layout journal`. With each one open, run `ffrap_apmenu tree` and send `ffrap_apmenu.txt` (each run writes over the last). `ffrap_apmenu screens` logs which screens exist and which is activated.
6. With the entry's screen open, `ffrap_apmenu text`. **Does "Archipelago test page" show anywhere on it?**
7. After each layout, open System, Quests and Bestiary. **Do they still look and work as before?**

Send the `[FFRAP]` lines of the log.

**Round 82 results, step 5 (the main menu probe, build 26b6adfa, 2026-11-18).** Steps 1 to 4 were not reported yet. The files and screenshots are in `.reference/2026-11-18/`.
- **The entry works with no pak.** `ffrap_apmenu on` (our own tag, never registered) added the row, put it before System and added it to the menu subsystem's maps in one tick. The scene list went from 8 to 9: FFR Bestiary's entry was there already, and both stayed. The user: "the menu looks good so far".
- **The screen can be changed from Lua.** `layout` wrote the soft class with `Conv_SoftClassPathToSoftClassRef` into both the table row and the subsystem's copy, and read it back. Tutorial, Options and Journal each opened from the entry.
- **Each screen opens empty**, as its Blueprint's defaults, since our row has no view model:
  - Tutorial: one framed window with "TITLE", a white image box, "TEXT", two arrows and "1/1" (`WBP_Tutorial`: `Text_Title`, `SizeBox_2` with the image, `SizeBox_1` with `Text_Description`, `Overlay_ButtonNext`, `Overlay_ButtonPreview`, `HorizontalBox_215` with the page count).
  - Options: the whole Options window with its tabs and empty rows. It is built on `WBP_TitlePanelLayout` (`Text_Title`, `Spacer_101`, `NamedSlot_93`), the same panel FFR Bestiary takes over in Help.
  - Journal: the Quests page's two columns with "Goal", "Summary" and "Text" lines. It is the Quests page's own class, so the pool may hand our changes to the real Quests page.
- **Text can be added.** `text` put a TextBlock into the Journal screen's root Overlay, at its top left.
- In the trees, visibility 3 is HitTestInvisible and 4 is SelfHitTestInvisible.
- **The choice: the Tutorial screen.** It is one window, it is not a main menu page of its own, and FFR Bestiary does not use it.

**Built after these results (mod 0.61.0 build 0c2a8b95, world 0.30.0 build 109145bc):**
- `ffrap_apmenu page`: the entry opens the Tutorial screen. The mod sets its title to "Archipelago", hides the image box, the arrows and the page count, and puts the seed's state in the description. Each tick it writes what differs from the screen, so if the game fills the screen again, the page comes back.
- The page lists the goal, the tower lock (party members, Visions, Crystal Fragments), checks done of the total, items received, Tablet Shards held, the continents open and locked, the kinds of locations, and the start.
- The client sends two new lines when they change: `cfg goal <kind> <shards> <shards needed>` and `cfg checks <done> <total>`.

## Round 83 test plan (mod 0.61.0 build 6a38c39e, world 0.30.0 build 91d7b935)

**Install:** copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Only the client changed, so the round 79 seed still plays. The client will warn that the seed's build is not its own; that warning is expected this time.

**0. The builds.** The log should say `version 0.61.0 (build 6a38c39e)`; the client `world version 0.30.0 (build 91d7b935)`.

**First try (build 0c2a8b95, apworld 109145bc, 2026-11-18).** The entry opened the Tutorial screen, but it stayed blank: "TITLE", the white box, "TEXT". The page lines in the log were right (goal, tower 2/6, 7/12, 2/10, checks 113 of 497, 117 items, 16 shards, 5 continents open). The log said `apmenu: page: no Text_Title or Text_Description on the screen`: `GetWidgetFromName` found neither, on the layout or on `WBP_Tutorial`. The round 82 `tree` walk did reach them (it follows `GetChildAt` and each user widget's `WidgetTree.RootWidget`). **Fix (build afd59819):** the page finds its parts with that same walk. A miss now logs how many widgets the walk saw.

**Second try (build afd59819, apworld 91d7b935, 2026-11-18).**
- **The page works** (screenshot). One window titled Archipelago, the image box, arrows and page count gone, all 10 lines shown. Long lines wrap: the text box is narrower than the window.
- **The second open was blank and stuck.** The user opened the page (13:10:17), closed it, opened a chest (`check chest:3001:0`, a Tablet Shard came in, 118 items), and opened the page again. The log says `apmenu: page written` at 13:10:57, so the screen was there and activated and got the new text. But only the main menu's background showed, and Back did nothing. Only Alt+F4 got out.
- **Likely cause:** the menu pools one screen per row (`PushSettings.bUsePooling`, copied from System's row). The Tutorial screen is a pop-up the game makes for each tutorial, and the second time the menu handed back the same one. Its closing animation most likely left it faded out, with its input still bound. Not proven: the log has no opacity line.
- **Changes (build 64aeef0d):**
  - Our row's screen is not pooled: `layout` (and `page`) set `bUsePooling` false in the row and the subsystem's copy, and log it (`pooling false`).
  - The page logs and undoes a faded-out window (`apmenu: page WBP_Tutorial render opacity 0 -> 1`).
  - `ffrap_apmenu state` logs the screens (activated, visible, visibility, opacity) and the menu's scene stack.
  - `ffrap_apmenu close` deactivates our open screen: a way out without Alt+F4, if the console still opens.

**Third try (build 64aeef0d, 2026-11-18).**
- The page opened, closed, and opened again, and showed the new numbers (checks 115, 119 items, party 3/6). The second time, Back did nothing.
- `bUsePooling` false changed nothing: the second open was the same screen (no new `page title` lines). The menu's screen container keeps the widget anyway.
- The log confirmed the fade: `page layout render opacity 0.0 -> 1` on the second open. Setting it to 1 made the page show, but it still would not close.
- `ffrap_apmenu state`: our screen activated, visible, opacity 1, and the menu's scene stack `Root, FFRAP`. So the menu still had our page open.
- `ffrap_apmenu close` (DeactivateWidget) took the screen away but left the menu on its empty background with the stack unchanged. Only Alt+F4 got out.

**What the Blueprint does (dump with `DUMP_BYTECODE=1`, `WBP_TutorialLayout`):** it is an EnhancedUI activatable (`CPP_EU_WBP_Activatable`). `OnRequestOpen` plays `A_Open`, and the end of `A_Open` calls `FinishedOpen`. `OnRequestClose` plays `A_Close`, and the end of `A_Close` calls `FinishedClose`. Its `OpenStateProperty` and `CloseStateProperty` have `IsEnableDefaultFinisheCall` false, so the screen itself must call the finish. On the second open the screen sat at opacity 0, the end of `A_Close`: the menu activated it again but never asked it to open. Most likely its open/close state still said closed, so Back's close request was dropped and `FinishedClose`, which the menu waits for, never came.

**Changes (build da0d250c):**
- When the page finds our screen activated at opacity below 1, it calls the screen's own `OnRequestOpen`, once per opening, and logs its state first: `apmenu: page screen at opacity 0 (IsOpeningProcess ..., IsClosingProcess ..., IsCanInput ..., bIsCanceling ...); OnRequestOpen`.
- `ffrap_apmenu close` calls `OnRequestClose`, the way Back does, instead of `DeactivateWidget`.
- `ffrap_apmenu state` adds those four flags.
- The `bUsePooling` write is gone.

**Fourth try (build da0d250c, 2026-11-18).** No change for the player: the second open still would not close. The flags told why.
- On the second open: `IsOpeningProcess false, IsClosingProcess true`. **The first close never finished.** Back asked the screen to close (`A_Close`, then `FinishedClose` at its end), but the menu turned the screen off at once, so `FinishedClose` never ran and the screen stayed "closing". With `IsEnableInProcessingStateChange` false, the next open was refused (opacity 0), and so was the next close.
- Our `OnRequestOpen` call played the open, but the state stayed "closing".
- `ffrap_apmenu close` (`OnRequestClose`) did finish a close: 2 s later the screen was off and `IsClosingProcess false`. But the menu's scene stack still ended with our scene, so the menu stayed on its empty background. It does not wait for a late `FinishedClose`.
- `inspect_WBP_TutorialLayout_C.tsv`: the class chain is `WBP_TutorialLayout_C < CPP_WBP_Tutorial < CPP_WBP_MuchaActivatable < CPP_EU_WBP_Activatable < CommonActivatableWidget`. `FinishedOpen`, `FinishedClose`, `OnRequestOpen` and `OnRequestClose` are callable. Both `OpenStateProperty` and `CloseStateProperty` have every switch false.
- The game's exe names `PushScene`, `PopScene`, `RequestScene` and `OnFinishedSceneOpen`, most likely on `CPP_VM_MainMenu`, which holds `SceneDataStack`.

**`inspect_CPP_VM_MainMenu.tsv` (a run still on build da0d250c, 2026-11-18):** the view model has `PopScene()` (no arguments), `CloseMenu()`, `SetScene(tag, option)`, `TurnScene(advance)`, `OnFinishedSceneOpen()` and `GetCurrentScene()`. `AllSceneDataList` holds our row (10 scenes with FFR Bestiary's). Bestiary's row uses the Journal view model and `CPP_JournalSceneOption`; ours is System's copy (no view model, `IsFillScreen` true). The run showed the same stuck second open, as expected for that build.

**Changes (build 6a38c39e):**
- The page sets our screen's `CloseStateProperty.IsEnableDefaultFinisheCall` to true, so the base class finishes a close itself, the moment Back asks. The next open should then start from "closed", and the menu's own open should play.
- A fallback: a screen that is off but still "closing" for 1.5 s gets `FinishedClose`, logged as `apmenu: screen off but still closing (...); FinishedClose`.
- The page asks `OnRequestOpen` only when no open is under way.
- `ffrap_apmenu close`: with our screen open, `OnRequestClose`. With it already off but the menu still on our scene, `CPP_VM_MainMenu:PopScene`.
- `ffrap_apmenu state` adds `close finish`.

**Fifth try (build 6a38c39e, 2026-11-18): works.** The page opens and closes again and again, and Back works each time. The log was not sent, so it is not known whether the default finish was enough on its own, or the `FinishedClose` fallback also acted. The fallback logs `apmenu: screen off but still closing` when it does.

**1. The page.** In game, run `ffrap_apmenu page`. The log lists the page's lines (`apmenu: page line: ...`). Open the main menu and pick Archipelago. **Does one window show, titled Archipelago, with the lines and no white box, arrows or "1/1"?** Send a screenshot. **Do all the lines fit, or is the text cut off?**

**2. The numbers.** **Do the goal, the tower counts, the checks and the continents match the client and the game?** Open a chest or receive an item, then open the page again. **Do the checks and items received go up?** **Open and close the page three or four times: does it show each time, and does Back always work?** On the second open the log should say `page screen at opacity 0 (...); OnRequestOpen`, and the window should fade in. The log should say `page CloseStateProperty.IsEnableDefaultFinisheCall true` on the first open. On the second open it should say nothing about opacity. If Back does nothing, open the console, run `ffrap_apmenu state`, then `ffrap_inspect CPP_VM_MainMenu` (it writes `inspect_CPP_VM_MainMenu.tsv`), then `ffrap_apmenu close` (once, and again if the screen goes but the empty background stays). Send the log and the file.

**3. Nothing else changed.** After the page, open System, Quests, Bestiary and System > Help, and look at a tutorial from Help. **Do they look and work as before?** A tutorial from Help should still show its own picture and text.

**4. The round 82 plan's steps 1 to 4**, if not done yet.

**5. A new game before the client.** With a new seed, start an Archipelago new game first and connect the client while the game waits on the prologue. Open the first chest. **Does the client send the check without a restart?** This is the 2026-11-18 fault below.

Send the `[FFRAP]` lines of the log.

**Found on 2026-11-18, the first play of a new seed (`.reference/2026-11-18/UE4SS_first play - client did not receive item.log`).** The client did not send a chest check until it was restarted. The game was right: it reported the check. The client dropped it.
- The user had cleared `ap_in.txt` and `ap_out.txt` for the new seed, but `ap_state.txt` still named the old seed. So the game started, wrote `hello` and `seed 92996...` to `ap_out.txt`, and linked the new game to the old seed (09:17:25, "this new game is linked to the seed"). The story then went 1000 -> 1005, so `ap_out.txt` was 4 short lines.
- The client connected and wrote the new seed to `ap_in.txt`. Before the mod saw it, the client read the old 4-line file to its end.
- At 09:17:43 the mod logged `new session 41007...:0:1 (was 92996...:0:1)`. It emptied `ap_out.txt` and wrote `hello`, `seed 41007...` and, in the same tick, `applied 0 ok flag 1421 = true` (item 0, 09:17:43.477). The new file was 80 bytes, the old one 72.
- The client noticed a new file only when it was shorter than what it had read. This one was longer, so the client read on from byte 72, past the new `seed` line. It kept the old seed as the scope and dropped every line after it: `story 8000` and `check chest:2020:0` (09:18:06). A restart read the file from the top, which is why it fixed it. `/resync` would also have.
- **Fix (client, world build 91d7b935):** the client keeps the start of `ap_out.txt` through its first `seed` line (`out_file_head`). When that start changes, the mod started the file over, and the client reads it from the top. A game restart appends `hello` and `seed` to the same file, so its start stays the same and nothing is read twice. `tests/client/test_out_file.py` plays the log's files; the old client fails it.

## Round 84 build notes (mod 0.61.0 build dc66cdd9, world 0.30.0 build 91d7b935)

**Built after round 83 (the page works):** the Archipelago page is a normal feature now.
- The entry is added with no command, whenever the mod runs. Its steps are logged until it is first in the menu; putting it back after the game loads its table again is quiet.
- The row opens the Tutorial screen as soon as it is added. The extra tags and screens of the probe are gone, and so are `info`, `layout`, `screens`, `text` and `page`.
- The page's text box is 1180 wide (it was 750), so the long lines should no longer wrap.
- The page's text is made only while the page is open.
- `ffrap_apmenu off | on | state | close | tree` stay, for when something goes wrong.

**Round 84 results (mod 0.61.0 build dc66cdd9, world 0.30.0 build 91d7b935, 2026-11-18).** The log is the user's paste of the `[FFRAP]` lines.
- **Build check:** passed. The log shows both builds, and `apmenu: AddRow FFRAP_Archipelago ...; scene list 7 -> 8, before System` at the title screen, before any save.
- **The Archipelago page:** works. It appears above System beside Bestiary, the lines fit, it opens and closes again and again with the counts going up, and it is still there after going back to the title. System, Quests, Bestiary and Help work as before. It also showed on a save not linked to the seed (slot 1).
- **A new game before the client (round 83 step 5):** passed with the client fix (world build 91d7b935).
- **Empty rewards (rounds 81 and 82):** passed. Chests and shinies show the Archipelago item with no gil, dungeon chests stay open, town and character quests show one pop-up and complete (`quest:13`, `quest:4` with `before its check`).
- **Distance guard (round 79):** passed. `chest:3080:3 reads taken (live open), 66886 from the player; not sent until the player is near it`, and the check came at the chest (`101 from the player`).
- **Oblivion Palace (round 80):** passed. 6 shards held were turned in at one talk (`palace: 0 shards held, 6 turned in, 2 steps paid`), and the two safes paid for opened (`chest:2031:0`, `chest:2031:1`).
- **Mog Tag (round 78):** the checks came (`quest:34`, `quest:35`) with the right items. But the pop-up said "You obtained a vision!", and the log says `chest pop-up for quest:34: no chest pop-up on screen`. Why: each Mog Tag reward row holds only the location's item (`33:1`, `25001:1`, `25002:1`), so the patch left it empty. An empty row shows a vision pop-up, which the mod does not find. The character quests are empty too, but their pop-up is written before their check, while the game's own item pop-up is up. **Fix (build a87aac00):** a quest with no `before` keeps the stand-in Potion in a row that would be left empty, so the game shows its item pop-up and the mod writes into it.
- **Verun (round 78):** Verun was at the Dwarven Forge and asked for the Ipooh drops, but "Arise, Mechabo!" was not in the quest log. Why: the quest log is fed by each event row's `RequestStateSettings` (Accept, Proceed, Complete). The story row the skip never plays, `C02_219_02`, holds the Accept of request 17. Setting counter 16 to 10 brought Verun, but nothing accepted the quest. **Fix (build a87aac00):** `G.MechaboPatch` puts an Accept of request 17 first in Verun's `C02_MechaboLvUp_00_yet` (he asks for the drops) and `C02_MechaboLvUp_00_ItemGet` (the drops delivered). The rest of the chain is the game's own: it accepts quests 26 and 27 itself.
- **Logic and scaling (rounds 77 and 79):** passed. Dragon's Maw, the stone bridge shadow, and the boss balance above level 30.
- `menu: DT_OP_GameSetting could not be loaded` came twice in a seed's save, minutes apart (14:01:58, 14:46:24). The Options rows were there each time the user looked. Not looked at yet.

**From the user, with round 84:**
- A save not linked to the seed should play as the game made it, with our settings off and the Archipelago page gone, and come back on `/bind` (this reverses round 57). **Built (a87aac00):** on such a save the mod writes the game's own rates and encounters (`settings: the game's own, for a save not linked to the seed`), scaling was already off there, and the page leaves the menu (`apmenu: taken out of the menu`). A linked save, or `/bind`, brings both back. The Options rows stay on the Options screen for now (idea 39).
- A player asked for a way to count shards without the princess's long talk. **Built (a87aac00):** the page says `Tablet Shards: N held, M turned in` (turned in once the palace has been read in this run) and `Oblivion Palace safes: R ready to open, O opened; the next needs S shards in all`, from counter 43 and the safes' checks.
- Fast travel from dungeons. `DA_WldMapParameter`'s `FastTravelProperty.ConditionBehaviorList` has three conditions: the map type (dungeons refuse, `CommonDialog_034`), an event under way, and a place not visited. **Built (a87aac00):** on a seed's save the map type condition travels, with the usual confirm dialog (`fast travel: allowed from dungeons`). The other two stay. Other saves get the game's rule back.
- The Airship item should make the airship a fast travel place. **Built (a87aac00):** with flag 1431 on, the mod marks maps 20001 (the airship) and 20002 (its deck) known and visited (`airship: maps 20001, 20002 marked visited, for fast travel`). Which map the Map screen lists for the airship is not known yet.
- Wording: "Archipelago needs ..." is now "You need ..." in the continent and tower notices. The client's `Told the game what N location(s) hold` line is gone; it was still in the client.

**Round 85 results (mod 0.61.0 builds a87aac00 and 05f33eda, world 0.30.0 build 84e053e7, 2026-11-18).**
- **Build check:** the client first reported world build 91d7b935 (the new apworld was not installed yet), then 84e053e7.
- **A save not linked to the seed:** the page left the menu and the settings went back to the game's own (`settings: the game's own, for a save not linked to the seed`). Loading the linked save, and `/bind`, brought both back. Two things were still on there:
  - The continent locks: `locks: boxes placed for grandshelt, lanzelt, ...` on the vanilla slot, and `ferry: 6 port choices written` from its unlock flags, which are all off.
  - An `ffrap_scale 1` set on the linked save: the seed's own scaling goes off on such a save (`scale: off`), but a hand-set scale did not.
  - **Fix (build b93912a5):** on such a save `locksOn()` is false, so the map load places no boxes. The boxes placed before the save was known, the crossings and the ferry's closed ports come off once per save (`locks: off for a save not linked to the seed (N ferry choices put back)`, `G.FerrySync(true)`). An `ffrap_scale` goes off there too (`scale: ffrap_scale is off for a save not linked to the seed`).
- **Shards on the page:** the numbers were right, but the wording was confusing. The user asked for two lines only: the shards collected, and the Oblivion Palace chests ready to open, with "Safe" renamed "Chest" in the location names too. **Built (b93912a5, world c5fec06a):** `Tablet Shards: N collected` (the shards the seed has sent, or held plus turned in when that is more) and `Oblivion Palace Chests: R ready to open`. The 23 palace locations are now "... N-Shard Chest (...)".
- **Fast travel:** works from dungeons, including one with a boss. Receiving the Airship marked 20001 visited (`airship: maps 20001 marked visited`; 20002 was visited already), and the airship can be fast travelled to.
- **Verun:** "Arise, Mechabo!" still did not start, and three Ipooh kills did not count; Verun still asked for two. The rows were patched (`mechabo: 4 rows of Verun's first step accept its quest`: two tables). Why: request 17's own row in `DT_RequestData` has `AcceptCondition` `{progress:16}==0&{progress:0}>=2120`, and the start had set the counter to 10, so the Accept was refused. Its quest-board step, quest 1001 on board 1000, is "Ipooh" x2 (`ClearConditionList` ID 55), which most likely counts kills only while the quest is accepted. **Fix (b93912a5):** `G.MechaboPatch` also sets request 17's `AcceptCondition` and `Occurrence.Condition` to `{progress:16}==10`.
- **Wording:** `The way is closed. You need ...` shows.
- **Oblivion Palace on an older save (round 80):** no old Archipelago save to test. A vanilla save worked the vanilla way.
- **Options screen probe (build 05f33eda):** every command worked. `ffrap_apmenu options` opened the full Options screen from our entry; changing a setting worked there and in System > Options; Back returned to the menu. `tabs only` left out the other tabs and `tabs all` put them back, so the tab list is read at each open. `text` brought the page back.
- **The log on a late bind:** binding a save near the end of a seed wrote about 80 `reads taken` lines, one `sync: check` line for each of 225 checks, and two lines for each of 280 items. **Built (b93912a5):** the far-away reads of one scan share a line, the first five by name; `sync from save: N new checks` stands alone; with more than 10 items waiting, the feed says `Receiving N items from Archipelago` and `Received N items` in place of a line each, and the stamp is logged once at the end. The per-item `item N ...: ok` lines stay.
- After the bind, `chest pop-up for boss:9014: no chest pop-up on screen`: a pop-up was armed for a check that came from the save. Harmless; not looked at yet.

**Round 86 probe (build b93912a5):** `ffrap_apmenu mode ap|game`, the Options screen as our page (idea 39).

**Round 86 results (mod 0.61.0 build b93912a5, 2026-11-18).**
- **Build check:** the apworld the client loaded was not `c5fec06a`, though the new one was copied. `tools/build_apworld.py` still makes `c5fec06a` from this commit, and the client reports the build of the package it loaded (`version.py`, from its `archipelago.json`). So an older copy was loaded: most likely a Launcher or client that was not restarted, or a second `ff_resonance` world elsewhere (another `.apworld` in `custom_worlds`, or a `worlds/ff_resonance` folder).
- **A save not linked to the seed:** passed. The locks came off (crossings and ferry too) and `ffrap_scale` went off there; the linked save got its locks and the seed's scaling back.
- **Palace names:** passed. A new seed has "... N-Shard Chest (...)" in the client and Universal Tracker.
- **Palace chests on the page:** it said `0 ready to open`, Universal Tracker showed none in logic, and the chests from III on were closed in the save. Not a bug in play. The nearly-finished save bound at 15:58 (round 85) sent `chest:2031:0` to `2031:19` as checks from its own opened chests, so for this seed those locations are done. The page counts chests paid for whose checks are not sent, as the tracker does. The two screens said 61 and 67 collected: the text page was made before a palace visit in that run (turned in not known yet), the Options headings after it (61 held + 6 turned in).
- **Options page probe:** passed. `mode ap` gave one tab named Archipelago with our settings and the page's lines as headings, and none of the game's rows (screenshot). System > Options showed the same while it was on. `mode game` and `text` put everything back.
- **Late bind log:** passed. One feed line for the backlog, one line per scan for far-away pick-ups, no `sync: check` lines.
- **Verun:** passed. "Arise, Mechabo!" showed in the quest log, two Ipooh kills finished it, and the reward was the vanilla Magicite Shard (the quest is not a location). Lid had no new skill, even after `!getitem` added her. That is the game's own: the quest's rows (`C02_MechaboLvUp_00` to `_01`) give no ability. Lid's first Mechabo skill, Mechabo Tackle (404110), comes from `C02_MechaboLvUp_03`, the second step of "Mechabo Evolved". Whether a step's ability reaches Lid while she has not joined is not known.
- **Found looking at Lid:** the open start never runs the story's ability rows. Each character's `C08_817_01` ability, Rain's chapter 6 and 8 abilities and Lid's `Lid_LB2_Get` are missing (IDEAS.md idea 40).

**Round 87 build (mod 0.61.0 build 5acddc01):** the Archipelago entry is the Options screen made our page, switched by a `SetScene` pre-hook and back by the tick, with our rows out of in-game System > Options (IDEAS.md idea 39). Before the round was played, the user asked for two tabs: the page now has Settings (the Gameplay tab) and Seed (the Sound tab, its rows hidden, holding the headings). The first build of the round, ad155ef2, had one tab.

### Round 87 (mod 0.61.0 build 5acddc01, apworld 0.30.0 build c5fec06a)

- **Build check:** passed. After a full restart the client and the mod both showed apworld build c5fec06a, so last round's mismatch was a client still running the old world.
- **Two tabs:** passed, with one fault. Both tabs showed and the player could switch between them, and the Seed tab looked right. On the first open the Settings tab showed the game's rows and not ours; on the next open it showed ours. The log shows the hook wrote the right rows (`mode ap: 21 game rows hidden, 10 heading rows on the Seed tab`) 6 s after the save loaded. Later in the run, `menu: DT_OP_GameSetting could not be loaded` showed that the table was gone for a time. The likely cause: the game loaded the table again after the hook wrote it, and a fresh copy has the game's rows and no changes of ours.
- **Tabs with keyboard and gamepad:** passed, except that a gamepad cannot scroll the Seed tab. No heading row takes the cursor, and the list scrolls with the cursor.
- **System > Options after the page:** passed, every time and in either order.
- **New counts:** passed.
- **Title screen Options:** passed (our rows and the game's under Gameplay). **From the user:** having the settings at the title screen but not in game System > Options could confuse; keep them only in the Archipelago entry.
- **Closing the menu from the page:** passed.

**Round 88 build (mod 0.61.0 build ac15f02e):**
- Our setting rows are in `DT_OP_GameSetting` only while the page is open. They are added when it opens (into whichever copy of the table the game has then) and removed when it closes, so the title screen's Options and System > Options never show them. The tick no longer puts them back.
- While the page is open, each tick checks that the tables still hold the page (`APMENU.Written`) and writes it again if not, logging it once.
- `ffrap_apmenu seedrows command` probe: the seed's lines as Command rows, which may take the cursor.

### Round 88 (mod 0.61.0 build ac15f02e, apworld 0.30.0 build c5fec06a)

- **Build:** passed.
- **First open soon after a load:** passed. Settings showed our settings on the first open. The log once said `apmenu: the Options tables were loaded again with the page open; mode ap: already so`, just after `ffrap_apmenu seedrows command`: the probe command had put the tables back while the page was open, and the page wrote itself again.
- **A setting kept after close and open:** passed.
- **Neither Options screen has our settings:** passed, in game and on the title screen.
- **Seed lines as Command rows:** passed. The cursor moves down the lines and a gamepad scrolls the tab. **From the user:** the Command rows look and feel better than the headings; keep them.
- **Mog Tag:** failed again, now explained. The game's pop-up ("You obtained: Potion", the stand-in) comes first, then the screen fades and the quest completes. The check (`check quest:34`) came after the pop-up, and 30 s later the mod found no pop-up (`no chest pop-up on screen`). Mog Tag had no early pop-up: each tier's reward runs at two counter values (0 or 10 for the first), so the generator gave it no `before`.
- **The Call from Beyond:** showed "You obtained a vision!", and the real reward was the scouted Phoenix Pinion. Its early pop-up waited for map 3121, where the chain starts, but `ChrEv_0410_007_01` moves the player to map 2100 (`TransitionLocation`), and the reward row `_007_02` runs there. The log shows `map 3121 -> 2100`, then `check quest:25`.
- **O General! My General!:** passed.
- **Mechabo Tackle:** failed in both tries (Lid in the party, and Lid added after). Not yet clear: Mechabo Tackle comes from `C02_MechaboLvUp_03`, which runs at counter 16 = 30 with flag 219, the second delivery of "Mechabo Evolved". The round 88 checklist asked for "the first step", which is `_02` and gives no ability. The log did not show the counter.
- **Steam Cloud:** passed. A stamped save on a second PC linked by itself (`save is stamped with this seed`) with no items given twice.

**Round 89 build (mod 0.61.0 build c9dab8b2):**
- The seed's lines are Command rows by default.
- `quest_steps.tsv` has a new column, `at`: the map each row runs on, following any row on the way that moves the player. The early pop-up uses it (The Call from Beyond: 2100).
- A quest's `before` can be several values, with `flags` that must be on too: Mog Tag's tiers are `{ 0, 10 }`, `{ 20, 30 }` and `{ 40, 50 }`, with flag 545 (the chase). The early pop-up is written once per quest.
- A reward row left empty keeps the stand-in Potion, for quests with an early pop-up too.
- The Quests screen's Rewards name the scouted item: the location's entry in `DT_RequestData`'s `Prize` becomes a text entry (ID 0), as "Attribute Bonus: Fina" is.
- The log shows Verun's counter, flag 219 and whether Lid has Mechabo Tackle, each time one changes.

### Round 89 (mod 0.61.0 build c9dab8b2, apworld 0.30.0 build c5fec06a)

- **Build and Seed tab:** passed. The log showed `version 0.61.0 (build c9dab8b2)` and `command row` lines with no console command.
- **Quest rewards:** passed. The Rewards list named the Archipelago item, the other rewards stayed, and the log said `quests: 28 quest rewards show the location's item` once.
- **Save not linked:** passed. `quests: 28 quest rewards back to the game's own`, and the screen showed the game's rewards.
- **Mog Tag:** passed. `chest pop-up for quest:35 before its check: text set, item line hidden`, then `check quest:35`.
- **The Call from Beyond, played again:** the game's Potion pop-up showed. The quest's check had been sent in round 88, and the early pop-up left out quests whose check was sent. The log shows `map 3121 -> 2100` and no pop-up line, so the map fix itself was not tested.
- **Mechabo Tackle:** not reached. The log shows counter 16 at 10, then flag 219 on (the Ipooh drops delivered), then 20 ("Arise, Mechabo!" done), and never 30. Mechabo Tackle comes at 40: talk to Verun at 20 to start "Mechabo Evolved" (30), deliver 3 Dhorme Chimera drops (quest 1002), and talk to him again.
- **Steam Cloud:** passed in round 88 (moved here from the open list).

**From the user, round 89:** item names in Archipelago's colours (light blue filler, dark blue useful, purple progression, red trap), in the item feed, the chest and reward pop-ups and the Quests screen; the name only.

**Round 90 build (mod 0.61.0 build 87f4d742, apworld 0.30.0 build 88874051):**
- The early quest pop-up is written for a quest played again from an older save, its check sent already: once per loaded save.
- The client sends each item's flags and name with its item line, and with each "Sent" message.
- `ffrap_feed colors on` (probe, off at each start): a feed line becomes a row of three TextBlocks, with the item's name in its colour, written into the block's fields before it is on screen.
- `ffrap_popup probe` and `ffrap_popup colors on [attr]` (probe): the chest pop-up's colours (IDEAS.md idea 42).

### Round 90 (mod 0.61.0 build 87f4d742, apworld 0.30.0 build 88874051)

- **Builds:** passed, both in the client and in the mod's log.
- **Feed colours:** passed. `ffrap_feed colors on` showed the four test lines with each name in its colour (`feed colours test: ok, ok, ok, ok`), and real received and sent lines coloured only the name. **From the user:** bold the name too; the colours alone can be hard to read at a glance.
- **Pop-up probe:** the message (`Text_Message`) has no decorators: `DecoratorClasses: 0`, `InstanceDecorators: 0`. `RTBD_TextStyle` is not used there.
- **Pop-up colours:** the name changed colour, but to black. With no decorator, `<text color="...">` is a run whose style the block has no row for, drawn in a fallback style. The colour table also had no rows: `AddRow` with a Lua table added none (`0 colour rows`).
- **Quests screen:** no colours, as expected; it was not built.
- The side quests wait until the colours are done (the user).

**Round 91 build (mod 0.61.0 build ec671324, apworld unchanged, build 88874051):**
- Feed colours are on by default, and the item's name is bold (the SystemText font's Bold typeface).
- `ffrap_popup colors on` (probe): the message keeps the lines without the name ("You found Alice's:"), and the name's line goes into a row of our own TextBlocks under it in the dialog's VerticalBox, centred and styled as the message (size 18, letter spacing 4). The row is removed when the pop-up closes. The markup and colour table code is gone.
- `ffrap_quest colors on` (probe): each Rewards line showing a scouted item gets our row beside its text block (`AddChild` on the block's parent panel), and the block is collapsed. A line the list reuses for another reward gets its own text back.

### Round 91 (mod 0.61.0 build ec671324, apworld 0.30.0 build 88874051)

- **Feed colours with bold names:** passed, with no command.
- **Pop-up colours:** passed. The log showed each `popup step:` and `text set, item line hidden, the name in its colour` for two chests in a row; the old name was gone from the second.
- **Quests screen colours:** not working. "Dream of an Idealist" showed its scouted item ("Blessed Pendant", our text line: no icon, no count) in white, and the log had no `quest colours:` line at all. The search found no line to colour and logged nothing when it found none, so it is not known whether it saw the reward lines, their text block, or the text.

**Round 92 build (mod 0.61.0 build 5d85e80c, apworld unchanged, build 88874051):**
- Pop-up colours are on by default (`ffrap_popup colors off`).
- The Quests screen probe logs what it sees each time that changes: `quest colours: seen: N reward lines, M on screen: "text" (scouted), ...`. It takes a line's block by its name or by its text (the first text block under the line that shows a scouted label).

### Round 92 (mod 0.61.0 build 5d85e80c, apworld 0.30.0 build 88874051)

- **Pop-up colours by default:** passed, on every chest and shiny of the run.
- **Quests screen colours:** not yet. The probe found the reward lines (`seen: 7 reward lines, 2 on screen`), but under each line on screen it found `no text block`. The text block sits in the entry panel's named slot, which the walk down from the line did not reach.
- **The Call from Beyond, played again:** passed. `chest pop-up for quest:25 before its check: text set, item line hidden, the name in its colour`, then `check quest:25` (the user: good now).
- **Mechabo:** Verun showed only "..." and no quest marker, and "Arise, Mechabo!" was not active. This run was a new seed's save with counter 16 at 10, so the step there is "Arise, Mechabo!" (2 Ipooh drops), not "Mechabo Evolved". The log does not say whether the quest log holds request 17.

**Round 93 build (mod 0.61.0 build 2dcd20c4, apworld unchanged, build 88874051):**
- The Quests screen probe finds the reward texts as CommonTextBlocks whose path is in a reward line. In a one-child slot our row takes the block's place (`SetContent`), and the block goes back when the line shows another reward; in a panel it goes beside the hidden block (`AddChild`).
- The `mechabo:` line also gives the quest log's state of quests 17, 26 and 27 (open, done, not started, not in the log), from the save's `request.DataMap`.

### Round 93 (mod 0.61.0 build 2dcd20c4, apworld 0.30.0 build 88874051)

- **Quests screen colours:** not yet. The probe logged `seen: 0 reward texts` when it was turned on and never changed, so no CommonTextBlock whose path is in a reward line was found while the screen was open. Off-line since: the line's own `SetText` writes `CommonTextBlock_194` (a variable of the line), and the entry panel (`WBP_IconEntryLayoutPanel`) holds it in its named slot `Slot_33_Content`.
- **Verun:** `quest 17 open` from the load, so "Arise, Mechabo!" is accepted, but Ipooh kills did not count (the user). Request 17's first step is "Defeat two Ipoohs near the Dwarven Forge": board quest 1001, a hunt of unit 55 (`DeliveryQuantity` 2). Its progress is in the save's `questBoardList` (`State`, `KilledCount`), which the log did not show.

**Round 94 build (mod 0.61.0 build 8aafe048, apworld unchanged, build 88874051):**
- The Quests screen probe takes each line's block from the line's `CommonTextBlock_194` property, or else from the entry panel's `GetContentForSlot("Slot_33_Content")`, and logs which (`by property`, `by slot`, `no text block`).
- The `mechabo:` line also gives board quest 1001's state (none, ordered, met, done, failed) and its kills.

### Round 94 (mod 0.61.0 build 8aafe048, apworld 0.30.0 build 88874051)

- **Quests screen colours:** found but not shown. The blocks were found by the line's property (`"Blessed Pendant" (scouted) by property`), and the log said `coloured: Blessed Pendant (in a NamedSlot)`. On screen the name showed white, then went. The block's parent is a NamedSlot, which holds one child: `AddChild` failed, but UE4SS gave back a null object, which Lua takes as true. So the block was hidden and our row went nowhere.
- **Verun:** the hunt was never ordered. The line read `quest 17 open, ... board quest 1001 none, kills 55 x0`, and three Ipooh kills right outside the Dwarven Forge's back exit did not count. The story event that accepts request 17 (`C02_219_02`) holds only the Accept, so the order is not in the event's data; a save that had played the story had it ordered (round 86).

**Round 95 build (mod 0.61.0 build f04c0650, apworld unchanged, build 88874051):**
- A slot from `AddChild` or `SetContent` counts only when `IsValid()`. In a NamedSlot our row takes the block's place (`SetContent`).
- On a seed's save, for each of Verun's open quests, the board quests of its current step (`DT_RequestData` `ProgressList[step].QuestList`) that read none are set to ordered in the save's `questBoardList`, and the log says `mechabo: board quests N ordered, so their kills count`.

### Round 95 (mod 0.61.0 build f04c0650, apworld 0.30.0 build 88874051)

- **Quests screen colours:** passed. Each scouted line showed the name in its colour and bold (`coloured: Blessed Pendant (in a NamedSlot, in its place)`), and switching quests put the game's lines back. **From the user:** the colour comes a second late each time; can it be at once?
- **Verun, "Arise, Mechabo!":** passed. At load the mod ordered board quest 1001 (`mechabo: board quests 1001 ordered, so their kills count`); two Ipooh kills counted (`kills 55 x2`, `met`), the delivery set flag 219, and the counter went to 20 (quest 17 done).
- **Verun, "Mechabo Evolved":** passed. Talking to him again gave counter 30 and quest 26 open; the dhorme chimera hunt (1002) was ordered by the game itself (no `ordered` line for it); after the delivery the counter went to 40 and Lid had Mechabo Tackle.
- **From the user:** "Arise, Mechabo!" gives no skill; it repairs Mechabo and starts the gather quests. "Mechabo Evolved" gives the first skill, Mechabo Tackle. Round 88's "no Tackle" came from a checklist that asked for the wrong step: the counter never passed 20. The one real fault was the first hunt (1001), never ordered on the open start (round 94); the game orders the later hunts itself.

**Round 96 build (mod 0.61.0 build c2d4d794, apworld unchanged, build 88874051):**
- Quests screen colours are on by default, and quiet in the log: the first line coloured, and any line not coloured. `ffrap_quest colors on` logs every line again.
- `ffrap_quest instant on` (probe): a hook on the reward line's own `SetText` (a Blueprint function, so the hook runs after the text is written) colours each line as the game writes it.

### Round 96 (mod 0.61.0 build c2d4d794, apworld 0.30.0 build 88874051)

- **Quests screen colours by default:** passed, with one log line.
- **Instant colouring (`ffrap_quest instant on`):** passed. The hook registered, and each scouted name showed in its colour at once.

**From the user, before the next release:**
- The Research Center Ruins' key card spots become locations.
- The NPCs who give one-time rewards (the old man with the Lunar Sword and the Brigandine) become locations. Always on, no option.
- Every boss and cave master gives an Archipelago item and a Crystal Fragment, with a pop-up where the fight had none. Options: cave masters priority locations (exists, `priority_bosses`) and story bosses priority locations (new). Decided with the user: all 40 bosses give a fragment; a two-item gift is one location, both items in the pool; the Magi-tenna's NPC is a location; story bosses priority off by default.

**Round 97 build (mod 0.61.0 build 26e942ac, apworld 0.30.0 build 5daa523d):**
- **Bosses:** all 40 hold a shuffled item, story bosses included, and each gives a Crystal Fragment on a location of its own (`fragment:<group>`, AP id 7,000,000,000 + group), sent with the fight's check. `final_boss_fragments` goes up to 40 (default 14). Finish rows with no reward get the stand-in Potion, so every win shows a pop-up: the six Nameless Ruins rows, Liquid Thunder's, the two barrier fights', Intangir's, Rogue Magitek Weapon's and the Antlion's; the story bosses' shared row (`Gim_EV_Majipot_Delete_02`, also the game's Majipot row) only on their maps. New option `priority_story_bosses` (off); `priority_bosses` reads "Priority Cave Masters".
- **Lab key cards:** shinies 3220:32, 33 and 37 are locations ("Gronoa - Research Center Ruins - Level N Lab Key Card Shiny"). Each card is in the pool once; the level 2 spot needs the level 1 card, the level 3 spot both; without key item shuffle each spot keeps its card. The mod blanks them.
- **NPC gifts:** 10 one-time gifts (flags 1400 to 1413, `data/game/gifts.tsv`) are locations (`gift:<flag>`, AP id 8,000,000,000 + flag). Each row gives the stand-in; the check is the gift's flag, set before the pop-up shows, so the pop-up is written as for a cave master. A second item goes into the pool in place of a filler. The Pharm cat's gift needs Mysidia (its cat first). The Magi-tenna's NPC is a location with the radar treasures, like the radar part chests.
- Quests screen colours are instant by default (`ffrap_quest instant off`).

### Round 97 (mod 0.61.0 build 26e942ac, apworld 0.30.0 build 5daa523d), first part

The user is still playing this seed; the rest of the round's checks stay open.

- **Builds and options:** passed. Both builds in the logs; the template shows `priority_bosses` (Priority Cave Masters), `priority_story_bosses` and `final_boss_fragments` up to 40; a seed with `priority_story_bosses: true` put progression on story bosses.
- **A story boss the mod brings back:** passed. Its pop-up showed the item, both checks were sent and the fragment came; Majipots gave nothing extra.
- **Quests screen colours by default:** passed, at once.
- **From the user (logic):** Lyrical Riddles and Elven Maven were in logic from the start, but both end in the Dwarven Forge, past Liquid Thunder. A quest's steps were tested by continent only, and Dilmagia is in Dirnado, so the boss went unseen. Fixed: a step on a map past Liquid Thunder gives the quest the chests' rule (Liquid Thunder's needs, or the Airship). It also caught Beyond the Blue, The Admirable Apprentice and "Reunion".
- **From the user:** can a quest with two rewards give both as Archipelago items? Leave out the stat bonuses, unless they can be items too.

**Round 98 build (mod 0.61.0 build 22b9afbc, apworld 0.30.0 build 91355310):**
- **The Forge quests' logic**, as above (`past_boss` on the quest, from `PAST_BOSS_ON_FOOT`).
- **Second rewards:** 17 quests give a second reward, and each is a location of its own (`quest2:<id>`, AP id 6,100,000,000 + quest, "Quest: <name> - Second Reward"), with the quest's logic. 8 give gil, 2 a second item (Secrets Unearthed, Rogue Rebel) and 7 a vision. The patch takes the second reward out of the row too (a row left empty keeps the stand-in); the check sends both; the pop-up names both, one line each, each in its colour; the Quests screen names both. A vision quest's own location now holds its Magicite, which with `shuffle_visions` off used to be lost; the vision sits on the second location. The stat bonuses are not items (left as they are). The client sends `cfg quest2` from slot data `quest_second_rewards`; a seed without it keeps the old behaviour.

### Round 98 (mod 0.61.0 build 22b9afbc, apworld 0.30.0 build 91355310)

- **Builds:** passed (mod 22b9afbc, client 91355310); at load `quests: 86 reward rows without the location's item` and `quests: 45 quest rewards show the location's item`.
- **Bosses (round 97 checks):** a cave master and a boss whose fight gave nothing before both passed: item pop-up, `check boss:` and `check fragment:`, the fragment in the feed.
- **Quests screen with two rewards:** passed, both names in their colours.
- **NPC gifts:** found and checked: 1400, 1401, 1405 (with radar treasures), 1406, 1408, 1411, 1413. **Failed:** every gift showed the game's Potion. The log shows why: gift 1400's check came and no pop-up was on screen for the next 30 s; gifts 1411 and 1405 wrote into the next chest's pop-up (chest:2000:0 then had none). The check is seen only after the gift's scene has ended.
- **Not found:** the Mist Potion gift in Grandshelt Castle (1409) and the Ether gift in the Commercial District (1407), after talking to every NPC there.
- **From the user (names):** "Magiapolis - West Hall NE Alcove Chest" is in Sakura's house; the Weapons Factory "SE Jump-Stone Platform" is a conveyor platform. World Map Shiny 91 (Mysidia, between Sunioo and Salome Cave) needs the Airship.
- **From the user (colours):** items the server sends (the starting continent's unlock, `!getitem`) showed light blue, as filler. The server sends them with no classification (flags 0).

**Round 99 build (mod 0.61.0 build 0e1022be, apworld 0.30.0 build fbcc579c):**
- **Gift pop-ups:** written early: in an event on a gift's map, with its check not sent yet, an item pop-up is the gift of the nearest gift NPC within 500 units. `gifts.tsv` gains the NPC's `x` and `y`. The check writes no second pop-up.
- **Gifts 1407 and 1409** are no longer locations (`GIFTS_NOT_FOUND`); their NPCs give their own items. 8 gifts are locations.
- **Names:** "Mysidia - Magiapolis - Sakura's House Chest", "Zoldaad - Weapons Factory - SE Conveyor Platform Chest". World Map Shiny 91 is in `airship_only.tsv`.
- **Server items' colour:** an item with no location (start inventory, `!getitem`) is classed by its category in the client (`CLASSIFICATIONS`), so a continent unlock shows purple.

### Round 99 (mod 0.61.0 build 0e1022be, apworld 0.30.0 build fbcc579c)

The user played one seed on one save over two sessions: on a laptop on 2026-11-19 (with FFRS QoL), then on the desktop on 2026-11-20 (without it), about 6 h, which ended in a crash. Not every check was reached.

- **Builds:** passed.
- **Gift pop-ups:** passed, for the gifts the user could reach. A chest near a gift NPC kept its own item.
- **Server items' colour:** passed. The continent unlock showed purple and a `!getitem` filler light blue.
- **A quest that pays gil:** passed. Both rewards were named, each in its colour, and no gil was paid.
- **The Zoldaad gift (1403) was not found.** The user looked in the Slums: an NPC there had a "..." bubble but no talk prompt. Gift 1403 is a talk point in Zoldaad Castle's Dungeon (map 3150, `Dng_06Zol_43_01`, at 515, -37240), not in the Slums. Its name, "Zoldaad - Zoldaad, the Imperial Capital - ...", came from the map's group, because the map's own name is only "Dungeon". The map's chests are named "Zoldaad - Dungeon - ...". The Slums NPC is not a location.
- **Nichol's Duty (quest 4), a stat bonus and an esper:** the first pop-up showed the Archipelago item. The stat bonus and "You can now summon..." came next, and both still had the item's coloured line at the bottom. The game showed them in the same dialog without closing it. The mod removed its coloured rows only when the dialog closed.
- **Checks sent with nothing opened (the laptop, Waterfall Way 3100 and the Town of Amore 2090).** On the first scan after arrival, `chest:3100:0`, `chest:3100:4`, `chest:2090:0` and `chest:2090:2` read `m_IsOpen` true, thousands of units away. Round 79's guard held them only until the player came within 1500: they went out at 1326, 765, 1285 and 933, seconds later. 3100:0 and 2090:0 had no pop-up on screen. On a second visit, `chest:3100:3` read open the same way. None of the five had been seen closed on that visit. All five are `TreasureBox002_C`, but 18 others of that class behaved, so the class is not the cause. FFR_MapMarkers judges looted chests with `IsOpenTreasureBox`, so its "looted" count is not separate evidence. Not known yet: whether the game itself shows these chests open. Round 65 found that `IsOpenTreasureBox(map, uid)` answers from another map's row when the map has no row of its own for that uid, and a chest may take `m_IsOpen` from it when it loads.
- **Repeats from the other computer (the desktop).** The desktop's save held the laptop's openings. Each such chest or shiny read open on arrival, and the mod sent it again: 13 of them, 594 to 1412 units away, each with `no chest pop-up on screen`. The server already had them, so nothing was lost. But each one asked for a pop-up. On the first map, six repeats in the Oblivion Palace (2031) asked for one, then the player opened `chest:2031:6`: its pop-up showed `chest:2031:3`'s item, and 2031:6's own request found no pop-up.
- **The crash (`UECC-Windows-2640C6364148041C9DF9A1AF94216C1B_0000`), about 6 h in, 4 s after the airship landed on the world map (map 20001 -> 1000).** An access violation in `FFieldClassVariant::GetFName` (reading 0x600000001), inside a Lua call to a UFunction, four Lua frames deep, under a game-thread callback. `ap_trace.txt` ends with `tick done`, so by round 77's rule it was not this mod's loop. Two other Lua mods were on: FFR_MapMarkers (four game-thread loops, one for the world map's markers) and FFRBestiary (a 50 ms tick). Round 63's crashes also came about a second after leaving the world map.

**Round 99, ticked later:** the Research Center Ruins key card shinies passed (pop-ups, `check shiny:3220:32`, 33 and 37, and the doors open with the cards from Archipelago).

**v0.30.0 released** (2026-11-19, apworld 0.30.0 build fbcc579c, mod 0.61.0 build 0e1022be, from commit 81bd70a).

**Scaling late in a run (the user's notes on the round 99 seed).** On Normal strength with the game on Normal, the run became a slog at about party level 40. By 50 the user had to set both to Casual. At 60, on Casual and Casual, they could not beat the final boss (Chaotic Darkness, group 9055): its HP was high and it hit hard. Better ailment resistance would have helped, but not enough. The dump shows why it got worse with each level. From level 40 to 60 a player's Attack grows x1.4 and HP x1.5 (`DT_UnitLevelParameter*`), but the enemy curve grows Attack x2.05, Intelligence x2.4 and HP x6.9. Enemies held at the party's level pull further ahead with each level. Chaotic Darkness is level 55 in the game. Scaling put it at 60 on Casual and at 66 on Normal.

**A new game of the game's own (the user, 2026-11-20).** A plain New Game, with the client connected, started Rain at level 55. `G.SyncSlotLevel` keeps an unjoined Rain at the party's level, for the save slot's level, and it asked only `seedCfg.openworld`, which comes back from the last `ap_in.txt` at every start. The prologue's party is Fina at level 55. An audit found more writes that asked only the seed's config, not whether the save is the seed's:
- the table patches run once per save: the vision shop guard, crystals, bosses, radar, quests, gifts, Mechabo, the Antlion and Behemoth;
- the Vision Enhancement screen's hook;
- the airship's spawn condition (`{flag:1431}` in place of the game's), written on the title screen too;
- the lock boxes placed during a map load, before the save is judged (taken off a moment later, round 85);
- with no session at all, every save counted as the seed's (for `fake_ap.py` testing).

**Round 100 build (mod 0.62.0 build 31c0fe10, apworld 0.31.0 build 149e31ed):**
- **A save that is not the seed's gets none of the seed's writes.** Rain's level, the table patches, the vision screen's hook and messages from the client wait for the seed's save (`sessionSave()`). The vision shop's rows are put back. The airship's condition and the map load's lock boxes follow `save.seedExpected()`: the loaded save's verdict, or between loads the last save's, kept in `ap_state.txt` as `lastok`. With no session, only a new game from the Archipelago entry is the seed's; `fake_ap.py` writes a fake seed line and has a `bind` command.
- **The table patches cannot be taken back in a run.** A save of the game's own loaded after the seed's save in the same run says `Archipelago: restart the game before playing this save`. Scaling, chest blanking, the settings, the locks and the vision shop are put back there, as before.
- **Versions bumped for the next cycle:** world 0.31.0 (and the template yaml), mod 0.62.0.
- **Scaling past party level 30 slows down.** The level bands come from a counted level that grows 3/4 of a level for each party level above 30 (`slowFrom` and `slowRate` in `SEED_RAMP`). Level 40 counts as 37.5, 50 as 45, 60 as 52.5. At 60 on Normal, enemies are 52 to 56 and bosses 56 to 60 (were 59 to 63 and 64 to 68). On Casual, bosses are 51 to 55, a little under the final boss's own level. Power percentages are unchanged. The log's `scale:` line says `counted as`. No yaml cap: strength is already an in-game setting, and the curve should be right without one.
- **A chest or shiny never seen closed on this visit is sent only when the map's own save row says taken.** The game writes the row when the player opens one. A held one is logged once per visit, a scan's together: `chest:3100:0 reads taken (live open, save row false, IsOpenTreasureBox true); never seen closed, and the map's save row does not say taken; not sent until it does`. The `IsOpenTreasureBox` answer tells whether the chest took another map's row. One seen closed and then open is sent as before.
- **Such a one gets the pop-up only with the player within 300 units.** A repeat from another computer is still sent, with no pop-up, so the next chest's pop-up keeps its own text.
- **Pop-up rows:** the coloured names go as soon as the dialog's message is no longer the mod's. The item line stays hidden until the dialog closes, as before.
- **Gift 1403 is "Zoldaad - Dungeon - X-Potion and Mist Ether Gift"**, as the map's chests are named.

### Rounds 101 and 102 (no play yet)

**Round 101 build (mod 0.62.0 build 3245e5b1, apworld 0.31.0 build 7c8d8ec3):** every scaling strength one step softer, enemy HP cut more than Attack, and battle MRP paid at the party's level (docs/open_world.md, round 101). v0.31.0 was packaged from it (2026-11-21) but not posted. Round 102 goes into v0.31.0 too, which is packaged again after the user's pre-release testing.

**Round 102 build (mod 0.62.0 build 80d9d5af, apworld 0.31.0 build 7c8d8ec3):**
- **No version bump:** a first build bumped to mod 0.63.0 and world 0.31.1, but v0.31.0 had not been posted, so this goes into it.
- **Scaling test presets** on a third tab of the Archipelago page: a preset slider (A, B, C, Custom) and five Custom sliders. `ffrap_set preset a|b|c|custom` and `ffrap_set elevel|ehp|eatk|blevel|bpower <percent>` set the same. `ffrap_apmenu testtab off` puts the rows under Settings.
- **A `battle: won` line per battle won**, with the time off the field, the preset and the party's level.

### Round 102 and older open items (mod 0.62.0 build 80d9d5af, apworld 0.31.0 build 7c8d8ec3)

The user tested before v0.31.0 goes out (2026-11-21).

- **Builds:** passed.
- **The Scaling test tab:** it showed, and the sliders worked. Preset 2 gave `preset B normal` and stayed 2 after a restart. Custom with enemy HP 60 gave `preset custom 92/60/100/103/105`. The Graphics tab in System > Options was normal after the page closed. Problems:
  - **The page's rows came in a different order at each open.** Our rows are removed when the page closes and added again when it opens. The row map reuses freed slots last-freed-first, so rows removed in order came back reversed, and back again at the next open. The Seed lines move the same way.
  - The help text at the bottom of the screen was cut off at about 140 characters (the preset row's).
  - The user asked for the preset to move the Custom sliders, and a Custom slider to move the preset to 4. Moot: see below.
- **The `battle: won` line worked**, but the first battle said 4 in all. The prologue skip sets the save's battles-won counter to 3, the prologue's own wins.
- **Round 101 scaling (preset A, Normal):** passed. The scale line, short hallway fights, MRP per fight and bosses past level 30 ("much better"), and levels 40 to 60 with the final boss. Expert is not tried yet.
- **Round 100:** `chest:3100:3` was sent only when opened, with its pop-up; `never seen closed` lines matched what the game showed; the stat bonus and esper messages had no coloured line; a plain New Game and the user's own saves got none of the seed's writes; the seed's save then an own save asked for a restart. The second computer and the crash test are still open.
- **Rounds 97 to 99:** the Dirnado quests' logic passed in the tracker.

**The user's decisions after it:**
- Keep preset A and take the Scaling test tab out: letting every tester set their own curve would add more noise than help.
- The Seed tab gets the Graphics tab's monitor icon in place of Sound's speaker.
- White Jade Stone, Black Jade Stone, Magic Tome and Tunnel Key leave the pool: they open nothing.
- A yaml option to show `???` in white for every quest reward.

**Round 103 build (mod 0.62.0 build 7b90595e, apworld 0.31.0 build 66073f7e), still for v0.31.0:**
- The Scaling test tab, presets B and C, Custom and their settings are gone. The `battle: won` line stays, and says `save's win count N`.
- The Seed tab is the Graphics tab (`SEED_CATEGORY` 1, `DT_OP_GraphicSetting`).
- The page's rows are removed last first, so they come back in the same order (`removeRows`).
- `NOT_KEY_ITEMS` gains 20005 to 20008.
- `hide_quest_rewards` (off by default): the client sends `cfg hidequests 1`, and the Quests screen's Rewards read `???` with no colour span. The completion pop-up still names the item.

### Round 103 (mod 0.62.0 build 7b90595e, apworld 0.31.0 build 66073f7e)

The user's pre-release test (2026-11-21): every round 103 check passed. The builds; two tabs, Settings on the gear and Seed on the monitor; the same row order at each open; System > Options' own tabs normal after the page closed; the `battle: won` line with the save's win count; `hide_quest_rewards` on (`???` in white, the completion pop-up still naming the item) and off (coloured names); and no White Jade Stone, Black Jade Stone, Magic Tome or Tunnel Key in the spoiler or the tracker.

**v0.31.0 packaged** from these builds (2026-11-21). The open items carried over in `docs/playtesting.md` go to the user and the v0.31.0 testers.

### A tester's full seed on v0.31.0 (2026-11-22)

The first full seed by a tester to the goal (Normal scaling, progression balancing 65). Their `UE4SS.log`: about 7.5 hours from the start to `Goal complete!`, the last battle at party level 30, 107 battles won (median 36 s off the field, 90% under 3 minutes), 286 checks (121 chests, 120 shinies, 14 bosses with their 14 fragments, 12 crystals, 3 gifts, 2 radar), side quests off. No errors.

What they said: fun and well-rounded; early and mid game fast, late game fine; status effects hard with no Ribbon and few cures; Magicite tight but fair; they took level scaling for a gate at first; their partner's items felt late. They asked for a save folder per seed and a PopTracker pack (IDEAS.md, ideas 11 and 47). The pool findings are idea 48.

**Round 104 build (mod 0.63.0 build c02e6de5, apworld 0.32.0 build 94562703):** the first change after v0.31.0, so both versions move. The pool gains 2 Ribbons and 13 enemy-only accessories (`data/pool_additions.tsv`), 9 extra Magicite (`extra_magicite`), and an early healing vision (`early_healing_vision`). The additions take the cheapest filler, and the pool keeps one filler item per excluded location (IDEAS.md, idea 48). The mod changes only its version.

### Round 104 (mod 0.63.0 build c02e6de5, apworld 0.32.0 build 94562703)

The user tested (2026-11-23). Every check passed:
- Builds.
- The spoiler log had the 2 Ribbons, the enemy-only accessories and 3 more of each Magicite tier.
- A healing vision was in sphere 1 of the player's own world.
- A Ribbon and an imbue charm received from Archipelago went into the bag under accessories and could be equipped.
- `extra_magicite: 0` with `early_healing_vision: false` gave the old Magicite count and no early vision.

**Round 105 build (mod 0.63.0 build 395095c2, apworld 0.32.0 build e38986f1):** no version bump, as v0.32.0 is not out yet.
- **Aileen's forge** (`include_aileens_forge`, off by default; docs/side_quests.md section 7). Eight locations, the nth weapon forged, each needing Forger of Wills' continents, the airship deck and n Adamantite. The pool has eight Adamantite. The forge still gives the chosen weapon: the weapons in the bag are how the mod counts forges, so the count is in the save. The forge's flag (1236) comes on before each forge's pop-up, and the mod turns it off again. The row after a forge ends the forge only with all eight weapons held, not as soon as Rain's is. While the Adamantite received outnumber the weapons forged, an empty bag gets one back, in case the game keeps only one.
- **Lid's airship line:** a seed's save sets the radar's step (progress 49) from 0 to 10, which is what the line itself does. Every other test of the step reads 0 and 10 alike.

### Round 105 (mod 0.63.0 build 395095c2, apworld 0.32.0 build e38986f1)

The user played (2026-11-23). Passed: the builds, the spoiler's eight forge locations and eight Adamantite, and the forge patch's log line (2 rows). The forge itself and Lid's line were not reached yet; they stay open.
- **Every early item came twice.** At 14:10 a load of slot 0 (in Malboro Menace Cave) logged `items: an Archipelago new game: 0 applied (was 13)`, and all 13 items were given again (the Tablet Shards went 3 to 6). Not the forge. Since mod 0.8.0, a load of the slot the Archipelago new game was skipped into counted as that new game, which holds nothing. The skip's own reload did the same at 14:02 (`0 applied (was 1)`), so Pharm Unlock came twice in the feed: the user's "two identical pop-ups" at the start.
- **The two names in a two-reward pop-up touched** (the user).
- **Abandoned Cabin - NW Corner Chest was in logic from a Pharm start, but needs the Cabin Key** (the user). The world-map door runs `C07_Wld_09Pha_Cabin_01` ("the cabin is locked") without the key. Round 74's note that the chest opened without the key was wrong.

**Round 106 build (mod 0.63.0 build 5f911663, apworld 0.32.0 build 4649c0ed):**
- A load of the Archipelago new game's slot takes its count from the save's stamp (or the slot's count), not 0. Only the unsaved new game starts at 0. This fixes both the doubled items and the doubled feed line at the start.
- The second name in a pop-up has 10 px of space above it (`G.POPUP_COLORS.GAP`).
- `data/gates.tsv`: the cabin's chest needs the Cabin Key.

**More round 105 notes (the user, 2026-11-23):**
- **Zoldaad Castle still gave the Throne Room Key** in a story scene with Shera and Ignis, so it could be had out of logic.
- **Grandport Harbor had no vision Moogle**, so a Lanzelt start could not upgrade with Magicite.
- **Zoldaad - Castle - Throne Room West Bushes Chest and Upper Tower SW Alcove Chest need the Throne Room Key**, and were in logic without it.

**Round 107 build (mod 0.63.0 build 52a08832, apworld 0.32.0 build 1a267523), on top of round 106:**
- **The Throne Room Key (found off-line):** the scene is `SubEv_Dng_06Zol_44_GimEv_03` ("questions with the squad leader"), from a walk-in trigger on map 3160 (uid 6, `{item:20021}==0`). Its two answers both give the key: `_03_B` by talking and `_03_A` after battle group 9087. With the key items in the pool (`cfg keyitems`, from `shuffle_key_items`), the mod turns the trigger off each time the map makes it (collision off, `SetGimmickCondition 1`, its condition never true), and both rows give the stand-in Potion in place of the key. With the key items not shuffled, the game's own key stays.
- **Grandport's vision Moogle (found off-line):** NPC 720 on map 2030 shows only with flag 144 (`m_VisiblFlagCondition`). Its chapter 1 scene (`SubEv_C01_Moogle_01`, story 1240) sets it, and the open start skips that scene. Every other town's Moogle has no flag condition. A seed's save gets flag 144, once, so saves already made get it too.
- `data/gates.tsv`: chests 3160:0 and 3160:2 need the Throne Room Key.

**Round 108 notes (the user, 2026-11-24, from testers):**
- **Two shinies on Zoldaad's south-west tip are reached only by the airship**, but were in logic on foot (screenshot of the peninsula). By their names, World Map Shiny 57 (SW Peninsula Tip) and 58 (South Peninsula West Cove).
- **A tester fast travelled to Grandport and walked around Lanzelt before it was unlocked.** Found off-line: "The Tide from the Sky" (Olderion, request 21) runs its fight scene, then `SubEv_C03_Mercedes_02_02` loads Grandport Harbor (map 2030) and `SubEv_C03_Mercedes_03` takes the player back to Olderion (world map point 5012). That visit made Grandport a fast travel place.
- The user asked to build every fix from the round 107 key item audit (docs/logic.md, section 8b).

**Round 108 build (mod 0.63.0 build 4e6c553b, apworld 0.32.0 build 937b4b93):**
- **The Cabin Key, key items shuffled:** the man in front of Sian's inn (NPC 22, map 2170) has three entries: before the cabin, "flag 1410 and no key" (gives the key), and "flag 1410 and the key". On map 2170 the mod points the middle entry at his first line (`FEV_Town_09Pha_01_1044_01`). A stand-in item would have given a Potion at every talk.
- **The Dungeon Key, key items not shuffled:** the mod gives it on map 3150 while it is not held (its soldier's trigger needs story 4180).
- **Logic, key items not shuffled:** every key in `data/gates.tsv` comes in the place of its doors (the cards from the Research Center's shinies, the squad leader's Throne Room Key, the Cabin Key man, the mod's Dungeon Key). Those locations need only their place now, and are no longer filler only (`GIVEN_IN_PLACE` in `locations.py`).
- **The Proofs of Victory are out of the pool.** The Colosseum gives each at its rank clear, and no location needs one.
- **The High-Power Generator: no change.** The merchant ship shows it only with the found count at 23 or more. With the radar treasures on, the mod holds that count at 13 or 22 until the third Progressive Radar, which opens tier 3 anyway. The upgrade's own test needs step 40 or 41 with the count at exactly 23.
- **Fast travel into a locked continent:** on a seed's save, every map of a locked continent (by `maps.tsv`'s island, `G.CONTINENT_MAPS`) is marked not visited (`Map.perMapSaveDataMap`, `bIsVisited`), but the map the player is on. Fast travel refuses a place not visited. It stays known.
- `data/airship_only.tsv`: shinies 1000:57 and 1000:58.
- **The radar goes quiet when there is nothing left to find** (a player: in the game it stops until the next part). The mod held the found count at the top of the band, so it kept pinging. Once every treasure of the level's tiers is found, the count goes 2 past the band's top (15, 24, 33): out of every band of `DT_MapPingerData`'s condition, and off 14 and 23, the counts the game's own part upgrades test. The next Progressive Radar puts it back at its band's top. At 24 and 33 the merchant ship offers the Generator, as the game does at 23; without a count of exactly 23 it upgrades nothing.

**Round 109 notes (a tester, 2026-11-23, v0.31.0: mod 0.62.0 build 7b90595e, apworld 0.31.0 build 66073f7e):**
- **Their starting Rain was level 55, and the Earth Shrine boss fight came back over and over.** Two seeds did the same. They had other mods on (FFRSLib, DevKnobs, QoLTweaks, CheatManagerEnabler and more), "mainly cosmetic".
- **Their `UE4SS.log`:** New Game (Archipelago) linked the new game to the seed, with the open start on. Story 1005 came at 17:28:25, but the game never saved: there is no `saved to slot` line in the seven minutes of the log. The automatic prologue skip waits for the first autosave (it needs a slot to save into and reload from), and it waited without a word. So the seed's save played the prologue (maps 10040 and 10041) and chapter 1 (5010, Grandport, the Earth Shrine), story 1005 to 1040, with every seed patch on.
- **Level 55:** in the prologue the party is Archwitch Fina at level 55. `G.SyncSlotLevel` keeps an unjoined Rain at the party's level. On the seed's save every guard held (open world, `sessionSave()`, on the field), so Rain went to 55 before she joined. Round 100's fix covered only saves that are not the seed's.
- **The boss loop:** `BossesPatch` sends Belmodar's win (group 9004) to `Gim_EV_Majipot_Delete_02`, which sets flag 1240 and writes no story. At story 1040 the game's own story trigger for the fight still holds, and the win no longer moves the story past it. The log ends at story 1040 with a map load every 30 to 40 seconds.
- **Why the game never saved: most likely autosave is off** in the game's Options (`オートセーブ設定`, a row of the Options screen). The user is asking the tester. Other players will turn it off too, and the user does not want to make them turn it on.

**Found off-line for a start with no prologue (round 109):**
- **The new game's first map is a setting:** `DefaultProject.ini` has `[/Script/mucha.CPP_GameSettings] GameStartSettings=(TransitionMapId=10040)`. `CPP_Task_NewGame` is a transition task with a `TransitionMapData` (a `MAP_DATA` row).
- **The new save is built from a table:** `DT_InitGameSaveData`, row `NewGame` (struct `SaveData_InitGameData`): money, party (`[1006]`), inventory, each unit's level, gear, skills and join status (Archwitch Fina joined at 55, the rest `NotJoin`), `OnFlagList` (1160 to 1163, 1182), `Progress` (`{0: 1000}`) and difficulty. There is no map or position in it. A second row, `Setup`, looks like a debug start.
- **The opening is map 10040's startup event:** `{progress:0}==1000 -> C01_001_01` (the movie, the "bygone era" event and the Move tutorial). Map 10040 has a second one, `!{flag:553} & {progress:0}>=5270 -> C05_536_02`, a scene that sets flag 553. Neither the world map (1000) nor the tower's dock (3280) has a startup event at story 8000.
- **The executable names `CPP_MapManager:MapTestStartByLoadSaveData`** and `MapTestStart`, beside `MapTestStartByChoiceSlotLoadSaveData` (the slot reload the prologue skip uses). Their parameters are not known yet.

**Round 109 build (mod 0.63.0 build 6a25a245, apworld 0.32.0 build 937b4b93, unchanged):**
- **The new start (idea 52), behind `ffrap_newstart on`, off by default.** In the title entry's pre-hook, the mod writes the arrival's map into `GameStartSettings.TransitionMapId` and changes the `NewGame` row: the arrival's story, the seed's party joined at level 1, everyone else not joined at level 1, Archwitch Fina with her own weapon and first ability, and the flags the prologue skip writes (plus the air start's 31, and 553). Each write is logged before it runs. Once the new game is in and linked, the mod puts both back, then writes the rest of the skip into the save in place (`SkipPrologue` with the open start) and sets the bag: each starter's gear up to what the party wears, Archwitch Fina's prologue gear out. Two seconds later it calls `MapTestStartByLoadSaveData` if that takes no parameters, to load the map again from the save in memory (the exact arrival, in the airship too). If it takes parameters, it moves the player on foot to the arrival when they are more than 300 away. A reloaded save is the new game only if it carries the seed's stamp.
- **Rain's level sync waits for the open start's story** (8000), so a prologue that still plays (autosave off, the new start off) leaves her at level 1.

**Round 109 results (the user, 2026-11-24, mod 0.63.0 build 6a25a245):**
- **Builds right, and the new start off works as before:** the first run (a Zoldaad seed on foot) autosaved to slot 0 at story 1005 and the prologue skip reloaded into the open start.
- **The new start works up to the arrival.** With `ffrap_newstart on` and an airship seed: `start map 10040 -> 1000`, the `NewGame` row at story 8000 with Rain and Lasswell joined, no opening and no Archwitch Fina. The game read both at New Game, not at start-up. The new game stood on the world map at (17214, 20957), on foot in Grandshelt just south of the Earth Shrine: where the world map puts a new game. The put-back and the skip's writes were all `ok`.
- **The party, menus, Map screen and fast travel worked.** The bag held each starter's gear once (`10100 1, 10200 1, 11000 2, 12000 2`, before and after: the game puts a joined unit's gear in the bag, as guessed). **But Rain's Leather Armor and Earrings of Health were in the bag, not on him.** Lasswell, with the same two pieces, wore his.
- **`MapTestStartByLoadSaveData()` takes no parameters, and it is not a reload from memory: it loaded the save in slot 0.** In the first try that was the earlier Zoldaad seed's autosave: the user landed by Zoldaad on foot with the airship beside them, and liked it, but it was another game. The mod saw no seed stamp and paused it, so the save made by hand after it was not linked. Later the user started a plain New Game, which autosaved into slot 0 on the battlefield. Every new start after it, through a restart and a new seed, loaded that save: Archwitch Fina on the battlefield, `story 8000 -> 1005`. In two of those runs the mod took the battlefield save as the seed's: the map manager stayed up through the load, so the game never left "in game", and the mod wrote the seed's stamp into the loaded data before it judged the load.
- **The plain New Game after the new start was vanilla** (the opening and Archwitch Fina): the put-back works.
- **The user's choice for the start:** on foot by the starting continent's town with the airship parked beside them, for airship seeds too, in place of the air start by the tower.
- Not tested: an on-foot seed, autosave off.

**Round 110 build (mod 0.63.0 build d0634fd8, apworld 0.32.0 build 937b4b93, unchanged):**
- **No more `MapTestStartByLoadSaveData`.** About two seconds after the new game is in, the mod moves the airship (if it is on the map) and the player to the arrival with `K2_SetActorLocation`. The arrival's island may not be loaded at the move, so four ticks later a player found more than 300 below the arrival, or still far from it, is moved again, once. Each move and the place after it are logged.
- **The new start's arrival is the starting continent's town on foot for every seed** (`FOOT_STARTS`), with the airship parked there. On an airship seed the airship is there at once; on an on-foot seed it stays hidden until its item.
- **The starters wear what the `NewGame` row gives them:** weapon, armor and accessories, written into the save when they differ, with a `gear:` line saying what changed.

**Round 110 results (the user, 2026-11-24, mod 0.63.0 build d0634fd8): every check passed.**
- The new start put the player on foot by the starting continent's town (Zoldaad), with the airship beside them on an airship seed and hidden on an on-foot seed. The first time, the user never saw the Earth Shrine: the move came before the screen faded in. After a plain New Game in the same run, Grandshelt showed for a moment, then Zoldaad.
- Rain wore his Leather Armor and Earrings of Health. The airship flew and landed as usual.
- A save made by hand linked when loaded from the title, with no item twice.
- A plain New Game, then New Game (Archipelago): the opening for the first, the town for the second.
- With autosave off in the game's Options: the same.
- **One nit:** the Active Time Chat "Thoughtful Resolve" (ATC11) played when the map loaded. Found off-line: ATC11 is released by no story row or table. The game's own new save already holds it released and waiting (the new-game snapshot that `tests/mod/test_skip.py` copies has it in `NoticeQueue`), and it plays once Lasswell, its `RequiredUnitList`, is in the party: in chapter 1 in the game, at once in a new start. The prologue skip cleared it before its reload; the new start clears it two seconds after the map is up, too late.

**Round 111 build (mod 0.63.0 build 2a01167a, apworld 0.32.0 build 937b4b93, unchanged):**
- **The chats wait.** In the title's pre-hook, every Active Time Chat row of `CDT_ChatEventData` (and its parent tables) gets the first unit not in the starting party as its `RequiredUnitList`. `NewStartFinish` puts them back after it has marked every chat played and emptied the queue.
- **The new start is on by default.** `ffrap_newstart off` goes back to the prologue skip, which also still runs when no seed has been heard this run (round 77).

**v0.31.1 sent to a few testers** (apworld 0.31.1 build 937b4b93, mod 0.62.1 build 55040fae, 2026-11-24): a tester build between public releases, a patch release (CLAUDE.md, "Tester builds and public releases").

### Round 112 (v0.31.1: mod 0.62.1 build 55040fae, apworld 0.31.1 build 937b4b93)

**The user's run (2026-11-24, `UE4SS.log`):** a Dirnado seed on foot, 2 hours 25 minutes from New Game (Archipelago) to the Crystal Tower's top. The new start went as in round 110: `chats wait for unit 1002: 112 rows`, the put-back with `112 chat rows`, the move to Dilmagia, and no chat logged. The Airship came at 21:18 near Dilmagia and was parked at the start, then flown. 8 bosses with their fragments, 11 visions, 5 of 6 party members. At story 8040 the final boss lock sealed the last climb (`characters 5/6, visions 11/12, Crystal Fragments 8/20`) and said so. No crash.

**From the user and testers (2026-11-24; some are the user's own, some testers', as the user said in round 113):**
- "Dirnado - World Map - Shiny on Far-SW Headland West of Sanctum of Onion Knight" (shiny 1000:4) needs the airship.
- "My airship spawned in Zoldaad when I received it, but I started in Dirnado." This was the user's own run, the log above (round 113).
- After the first talk with any vision Moogle, a scene plays: Grandport's, with the player left out of bounds on any other map.
- "Impossible to get to the top of Mysidia Tower", with a screenshot: chapter 8, "Go to the top of the tower". Round 112 took it for the Crystal Tower's final boss lock. Wrong: it is the Tower of Mysidia's lift (round 113), and the chapter 8 objective is the story's own, shown all the time at story 8000.
- Token Legacy needs the Throne Room Key.
- Beyond the Blue needs a party of 4.

**Found off-line:**
- **The Moogle scene:** every Moogle's shop row (`VisionUpgrade`, `VisionUpgrade_Main` in `CDT_TalkEventData_Prod`) goes on to `SubEv_C01_Moogle_02` (or its `_fade`) while `!{flag:145}&{flag:144}`. That scene, staged in Grandport, only sets flag 145. Round 107 set 144 alone, so the first Moogle anywhere played it.
- **Token Legacy:** its last step (`ChrEv_0070_006_01`, value 60) is NPC 14 on map 3160, past the Throne Room Key's door. Errand's End starts after it and has a step at the same NPC.
- **The airship:** the park writes only the save (round 72: one received inside Gronoa stood where the player was). An airship the game shows before a map load stands where the game puts it.

**Round 112 build (mod 0.62.2 build 5d54d782, apworld 0.31.2 build 177b8160):** the first change after v0.31.1, so both patch numbers move.
- **The Moogle:** a seed's save gets flags 144 and 145, so no Moogle plays Grandport's scene. A v0.31.1 save that has 144 gets 145.
- **The airship:** after it comes, the first time an airship is on the world map, one more than 1000 from the start is moved there (`game.MoveAirships`, which the new start uses too), with an `airship: on the world map ...` line.
- **Logic:** shiny 1000:4 needs the Airship (`data/airship_only.tsv`). Token Legacy needs the Throne Room Key (`data/gates.tsv`), and a quest that starts after another takes its keys too (Errand's End and its second reward). Beyond the Blue needs a party of 4 (`party` in `data/quests.tsv`): the starting party counts, and with party members not shuffled and fewer than 4 at the start it is filler only.

### Round 113 (the user, on round 112's reports; mod 0.62.2 build 3b66f1dc, apworld 0.31.2 build 177b8160)

**From the user (2026-11-25):**
- The round 112 reports were partly the user's and partly testers'. The airship one was the user's, with the log of round 112.
- **The airship:** at the start it showed greyed out on the map in Dirnado, where it should be. When the item came, it stood near Zoldaad, where the user had not been. Fast travel to it worked. Not what the feed said.
- **The Tower of Mysidia (map 3200), reproduced by the user:** a lift takes the player to the top, where Fina's Psyche and Tellus are. Take it up, fast travel out, and the lift stays at the top: the top can never be reached again. "Go to the top of the tower" is the story's objective at story 8000, always shown.
- Could the same happen in Siren's Tower, Mobliz Shipyard, the Wind Shrine and other places? And the Shipyard's last lift is still to do (to IDEAS.md, idea 53).

**Found in the log:** at 21:18 the Airship came on the world map and the save was parked at Dilmagia (`airship: parked at the start (received), (13190, 3210, -12)`). So the actor the game spawned stood elsewhere, and leaving the world map (21:20, into Dilmagia) wrote its place back into the save. Round 112's build already moves the actor to the start the first time it is on the world map after it came.

**Found off-line (`tools/lift_audit.py`, `data/game/lifts.tsv`):**
- A lift with `m_IsSave` keeps its stop (the spline point index, `SetGimmickState(m_CurrentSplineKeyIndex)`) in the save, and at a map load starts there, or at `m_InitStepIndex` on a first visit. A "ride" lift (`BP_MapGimmick_Floor_Elevator_Interact2`) moves only when ridden or called; nothing brings it back. Its `m_TransitionDataList` puts it at a stop when the player arrives at a given point; an arrival with no rule keeps the saved stop.
- **The Tower of Mysidia:** lift 13 (z 4586 to 6586) is the way up; a warp at its top puts the player at point 1, by lift 32's top (z 10765). Lift 32 is the way down, and the warp at its bottom puts the player at point 2, by lift 13's bottom. Lift 13 goes to its bottom on arrival at point 2 or at the bottom save point (10000), but not at the door from the world map (point 0). In the game a player always leaves by the way down, which puts it back. Fast travel out from the top, then the door, left it at its top.
- The same gap is in four more dungeons: the Wind Shrine (lifts 71, 72 and 74 have no rules at all, 41 none for the save points), the Water Shrine, the Gronoa Shrine (lift 24 has none) and the Sanctissimus Shrine (six lifts, rules only for two inner points). In all five the only way in from another map is the door a first visit uses (point 0).
- Not changed: the step-on lifts (`BP_MapGimmick_Floor_Elevator`, in Siren's Tower, the Arcane Library and a Gronoa dungeon) have an entry box that calls them to the player. The keypad lifts (`..._Interact`, Mobliz Shipyard, Dilmagia) have call switches. Mobliz Shipyard also has a second door in (point 2).

**Round 113 build (mod 0.62.2 build 3b66f1dc, apworld 0.31.2 build 177b8160, the apworld unchanged):**
- **Lifts:** while the player is on another map, each ride lift of those five dungeons is put back at its first-visit stop in the save (`G.LIFT_RESETS`, from `data/game/lifts.tsv`), once per map change. The game's own arrival rules then run on top, as on a first visit. The log has `lifts: back at their first-visit stops: 3200:13 1 -> 0`, and on a lift map `lifts on map 3200: 13 at 0, 32 at 0` each time a lift's live stop changes. Not seen in game: that the save row's `Value` is the stop. The second line tells.
- **The airship:** when the actor is moved to the start, the save is parked there again too, and the line says what the save had (`the save had placed true, riding false, ... at (x, y, z)`).

### Round 114 (round 113's build tried: mod 0.62.2 build 3b66f1dc, apworld 0.31.2 build 177b8160)

**From the user (2026-11-25):**
- **Ticked on the checklist (round 112's and 113's checks):** the builds; no scene at a first vision Moogle outside Grandport, and a v0.31.1 save the same; the Airship received away from the start stood at the start and stayed there after a town; the spoiler log or tracker put the Far-SW Headland shiny after the Airship, Token Legacy and Errand's End after the Throne Room Key, and Beyond the Blue after 4 party members. From round 111: Active Time Chats stayed quiet for the whole run.
- **The Tower of Mysidia's lift now resets** when the player leaves and comes back. So the save row's `Value` is the lift's stop, as round 113 guessed.
- The other lift dungeons are for the user's next round.
- **A player: the boats in Cave of Waters and the Water Shrine** do the same: they stay where they were left.

**Found off-line:**
- The rafts' logic is native (`CPP_MapGimmick_Object_Raft`, `CPP_MapGimmick_RaftVisibleChange`), so the Blueprints show nothing. The save keeps one row per map, `Map.lastRideRaftMap{map}.UniqueID`: the last raft ridden there. Each crossing has a raft at both ends, and the "visible change" boxes by the docks show one or the other by that row. A first visit has no row, so the row is what keeps a raft on the far side. Cave of Waters (3080) has 9 rafts and the Water Shrine (3110) 7. The only way in to both from another map is point 0.
- **A survey of everything else that keeps its place in the save** (every gimmick Blueprint that calls `SetGimmickState`, `SaveState` or `SetSwitch`, counted over all 159 levels):
  - Lifts: round 113.
  - Rafts: Cave of Waters and the Water Shrine. Fixed in this round.
  - Floors moved by a switch (`BP_MapGimmick_Floor_MoveBySwitch`): Cave of Waters 3, the Water Shrine 3, the Weapons Factory 6. Turning bridges (`..._SequentialRotationBridge`): the Weapons Factory 6. Their state is the switch's (`switchData`), so a reset would undo the puzzle. To check in game whether one can leave the way back closed.
  - Push boxes (`BP_MapGimmick_PushObject_WoodenBox`, a fall box, and 2 blockers that a box clears): the Water Shrine. A pushed box stays; that only keeps a puzzle solved.
  - A falling floor (`BP_MapGimmick_Floor_ShakeAndFalling`): Kolobos Ruins, 1. Once fallen it stays fallen. To check whether it is the way on.
  - Doors, string ladders (Mt. Thunderclap 3, Cave of Waters, the Weapons Factory, the Underground Tunnel, the Research Center Ruins) and breakable objects stay open, down or broken: they only help.
  - The Crystal Tower's 114 see-through floors do not save.

**Round 114 build (mod 0.62.2 build 901ca04e, apworld 0.31.2 build 177b8160, the apworld unchanged):**
- **Rafts:** while the player is on another map, the last raft row of Cave of Waters and the Water Shrine is taken out (`G.RAFT_MAPS`), so the rafts stand as on a first visit. `G.ResetLifts` is now `G.ResetRides`, for both. The log lines are `rides: back as on a first visit: 3080 raft 47 -> none, 3200:13 1 -> 0` and, on the map, `rides on map 3080: last raft 47` (with `lifts ...` on a lift map) each time it changes. Not seen in game: that a first visit has no row, and that the rafts then stand at the near docks.

### Round 115 (mod 0.62.2 build 901ca04e, apworld 0.31.2 build 177b8160)

**From the user (2026-11-26):**
- **Round 111's full run finished with no issues.**
- **Ticked from rounds 106 and 107:** an item that came before the start shows once in the feed and is not given again; a reload gives one of each item, not two; the two names of a two-reward pop-up have space between them. The log's `items: an Archipelago new game: 0 applied (was 1)` came from a second new game after a quit to the title, which is right: the first game had applied 1.
- **The player stuck at the start.** The user walked on the world map while the new start moved Rain from the Earth Shrine to the Town of Sian (Pharm), and Rain could not move after. They quit to the title and started a new game, which went through.
- The user asked: can the start load while something else is on screen, such as the welcome window of idea 22? Can a new game be refused when the client is not connected?

**What the log shows (the first game):**
- 24.26: the save is in, with Rain at point 0 (the Earth Shrine, 17214, 20957). 25.39: the first move, to the arrival (-3920, -17480, 90).
- 27.49: Rain stood 359 from the arrival at z 73, so the user was walking. The check moves the player again when farther than 300 (`G.NEW_START.near`), so it moved a walking player back. That check was meant for a player who fell through an island that was not loaded yet.
- 29.65: Rain stood at exactly -3920, -17480, 90, and the user quit 18 s later. The ground there is at about z 72 (both games read 72 to 73 after a walk), so Rain had not dropped to the ground: the pawn was not moving at all after the second move.
- The second game: the user walked 147 after the first move, under 300, so there was no second move, and it played on.
- So the freeze came with the second move of a walking pawn. Why the pawn stopped is not known. `ffrap_input` reads the controller's and the game's input locks; it was not run.

**Found off-line:**
- **Where a new game stands.** `GameStartSettings` holds only `TransitionMapId`, and the NewGame row (`SaveData_InitGameData`) has no place. The new game uses point 0 of the map, and point 0 of the world map is the Earth Shrine's arrival: a `BP_MapTransitionPoint_C` in `Wld_GD` with `m_PointID 0`. There are 113 points there.
- **The game's dialog windows** are rows of `DialogBoxInfo` in `CDT_DialogBox` (`DT_DialogBox_System` and 12 more): a `DialogTag`, a `Message`, a `ChoiceTag` (such as `UI.Dialog.Choice.YesNo`), and sounds. The title's Quit Game uses `UI.Dialog.Box.QuitGame.Title`. The executable names the calls `OpenDialog`, `RequestOpenDialog`, `IsDialogActive`, `IsOpenDialog`, `CloseDialog`, `BindToDialogClosed` and `GetDialogManager`, on `CPP_BFL_Dialog` and `CPP_DialogManager`. Their parameters need `ffrap_functions` in game.
- **The client is not known to be connected.** At start-up the mod reads the last `ap_in.txt`, which holds the last session's `seed` line, so `seedCfg.heard` is true with no client running. A new game from the Archipelago entry then starts on the last seed's continent and party.
- **The title entry cannot be refused as it is.** `ExecuteEntry`'s pre-hook can change the entry type but not stop the call. The types are Continue 0 to QuitGame 4. What the game does with an unknown type is not known.

### Round 116 (mod 0.62.2 build 517a874b, apworld 0.31.2 build e0989726)

**From Discord (2026-11-26):**
- A player finished a multiworld with very few issues: a Moogle cutscene glitch (likely the vision Moogle's scene that round 112 took out), and some lag in Dragon's Maw.
- Another player had a constant stutter, "like a heartbeat". A third had none. The user feels it on their laptop and not on their desktop.
- An idea for later: a menu to roll cosmetics or music again after the seed is made (idea 9).

**Why a heartbeat stutter fits the mod.** The mod's main loop runs every 0.5 s on the game thread, and each run does its work in one go. UE4SS's `FindAllOf` and `FindFirstOf` go through every object in the game to find a class's instances, so a run with several of them can take a frame or more on a slower CPU. The shiny scan (`G.LiveFieldItems`, every second in game) searched every `CPP_MapGimmick`, hundreds on the world map, and read each one's class in Lua to keep the field items.

**Built:**
- **The start (idea 54, way 1).** The new start moves the player a second time only when they are below the arrival (fell through an island not loaded yet). A player who walked away is left alone. From the save's arrival until the player stands at the arrival, the controller's move input is held (`SetIgnoreMoveInput`, `G.HoldMove`), and it is given back after that, or after 10 s (`G.NEW_START.holdTicks`). The log has `newstart: move input held: ignored true`, then `newstart: move input given back (at the arrival): ignored false; <ffrap_input's line>`.
- **The client's heartbeat (way 2).** While connected to its slot, the client writes `ap_alive.txt` (the Unix time and the session) every 2 s, and deletes it on a disconnect and on exit. The mod reads it at the title (`bridge.readAlive`); one older than 10 s does not count. With no live client, the title entry is labelled "New Game (Archipelago: connect the client)" (the menu shows a new label only when it is made again), and choosing it becomes Load Game, with a notice. `ffrap_title refuse <type>` tries another type in its place; `ffrap_title refuse off` lets the entry start with no client. `tools/fake_ap.py` writes the heartbeat too.
- **The shiny scan** searches only `CPP_MapGimmick_FieldItem`, the native class of all four field item Blueprints (FieldItem, `_Child`, `_Medal`, `_08Gro_40`; their parents read from the dump).
- **Timings.** Each loop run, each step the loops mark and each `FindAllOf` and `FindFirstOf` call is timed with `os.clock`. Every 2 minutes the log has `perf:` lines: each loop's runs, average, maximum and count over 25 ms, then the six steps and the six searches that took the most time. A run over 25 ms is logged at once with its steps over 2 ms (`perf: a tick took 41 ms (ms by step: loot 30, ...)`), at most once per 10 s. `ffrap_perf` logs the summary now.
- **Probe for the welcome window (way 3):** `ffrap_functions CPP_BFL_Dialog CPP_DialogManager` (an existing command) writes the dialog calls' parameters to `functions.txt`.
- **Probe for no move at all (way 4):** `ffrap_point0 on` (not kept), then the Archipelago entry. From the choice until the save is in, the mod looks for the world map's point 0 (`BP_MapTransitionPoint_C`, `m_PointID 0`, in `Wld_GD`) at each tick and map load, moves it to the arrival once found, and logs each try with where the pawn stands. It is put back once the save is in, as the Earth Shrine's door leads to it. `ffrap_point0` alone logs where point 0 stands.

Not seen in game: whether the move lock stops the game's own walking (it uses the engine's `AddMovementInput` check, if the game's pawn goes through it), what Load Game in place of the entry looks like, whether a new label shows without a restart, and the timings themselves.
