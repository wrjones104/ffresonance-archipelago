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

## Round 35 test plan (mod 0.16.1, world 0.3.1)

Three parts. Send the `[FFRAP]` lines of `UE4SS.log`, and screenshots where asked.

**Install:**
- Copy `FFRArchipelago/Scripts` over the installed mod. The log should say `version 0.16.1 loaded`. Keep FFRRandomizer off: there should be no `FFR Randomizer is on` line. `Assets` and the apworld did not change (world 0.3.1).
- The seed must have the default goal (story 8050). The open world start reaches story 8000, so a test seed with a lower goal (such as 1130) completes at once.

**Part A: the open world start:**
1. Connect the client. Load slot 0, the Archipelago game from the first run (story 1030, at the Earth Shrine). Once you can move, run `ffrap_openstart now`. The item feed says "Open world start: saved to slot 0 (map 3280, ...), reloading", and the log has:
   - `openstart: ok   story counter -> 7090`
   - `openstart: ok   arrival: map 3280 at -2830.0, -171140.0, 3000.0`
2. Where do you land? Take a screenshot. Then run `ffrap_status`. Wait about 10 seconds: round 31 had `story 7090 -> 8000` about 8 seconds after arriving. Does a cutscene play?
3. If the spot is bad (in a wall, falling, stuck): load slot 0 again if needed, then run `ffrap_openstart at 10590 12960 600` (next to the tower's other save point, near the tower's 8000 event) and `ffrap_openstart now` again. `at` lasts until the game closes. If the story is already past 7090 by then, that is fine: `now` writes 7090 again.
4. Find the airship. The dock's exits fly back to the world map. Is the airship there? Fly out to the world map. What looks wrong: party (Rain and Lasswell at level 1), menus, a cutscene that repeats, missing features?
5. Optional, the new game path: run `ffrap_openstart on`, then New Game (Archipelago). The log should say `title: open world start is on`, then `skip: ok   story counter -> 7090` and `skip (automatic): ... open world start (story 7090, Crystal Tower)`. At the title, check the log for the reply to `ffrap_openstart on`: nothing shows on screen there without ModSettings. `ffrap_openstart off` gives the normal start again.

**Part B: the missing airship (quick, on the save from round 34):**
7. Load that save on the world map. Run `ffrap_airship` (it logs the airship's spawn condition) and `ffrap_status`. Also say which save slot round 33's airship tests used, if you remember, and whether the desktop and laptop share saves through Steam Cloud.

**Part C: no-landing boxes (world map, in the airship; use the open world save from Part A):**
8. Mysidia, without landing in between:
   - Fly over Mysidia and run `ffrap_noland here`. Each box now has a second line: `collision: actor ..., enabled ..., profile ..., channels ...`.
   - `ffrap_noland lock mysidia`, then `ffrap_noland here` again. Try to land (expect: still allowed, as in round 33).
   - `ffrap_noland refresh`, then `here`, and try to land. Is landing blocked now, without a landing in between?
   - `ffrap_noland unlock mysidia`, `refresh`, `here`, and try to land. Is it allowed again?
   - Then land and take off once, and run `here` again. Did the `collision:` line change?
9. Pharm: fly to the Pharm story box, around (-5930, -17400). `ffrap_noland show` draws it, which helps you find it. Run `ffrap_noland here`. Is it one small box? `lock pharm`, `refresh`, and try to land on that spot. Then try a spot a little away from it.
10. Spawned box: over open land, `ffrap_noland spawn`, then `here`. Compare its `collision:` line with Mysidia's. Is the shadow gone again? Then `ffrap_noland cond {progress:0}<0` and `refresh`: can you land without a landing in between?
11. `ffrap_noland off`.
12. Run `ffrap_find Landing` and `ffrap_functions CPP_MapNonLandingArea CPP_MapAirShipCanNeverLandingBox`, and send `find_Landing.txt` and `functions.txt`. They may show a function that makes the game read the conditions again.
