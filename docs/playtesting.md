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

## Round 33 test plan (mod 0.15.0, world 0.3.1)

Two parts, both executed on an unbound save (such as the 7090 + Crystal Tower save).

**Installation:**
Copy `FFRArchipelago/Scripts` over the installed mod directory. Log should verify `version 0.15.0 loaded`. Apworld is unchanged (0.3.1).

**Part A: no-landing boxes (world map, in airship):**
1. Outlines: run `ffrap_noland show` to check if debug collision wireframes render. Run `ffrap_noland hide` to remove.
2. Lock Mysidia:
   - Fly over Mysidia and run `ffrap_noland here`. Log should show `BP_MapNonLandingArea_C_42` with condition `{progress:0}<5020`.
   - Verify landing is permitted, then take off.
   - Run `ffrap_noland lock mysidia`. Check if the landing shadow turns red and landing is blocked.
   - Run `ffrap_noland unlock mysidia` and verify landing is restored.
3. Pharm: test `ffrap_noland lock pharm` and `unlock pharm` on the Pharm landing box.
4. Custom ground box: fly over open land and run `ffrap_noland spawn`.
   - Confirm the airship maintains normal flight elevation.
   - Verify `ffrap_noland here` reports the spawned box and landing is blocked.
   - Run `ffrap_noland cond {progress:0}<0` to ensure landing is re-enabled.
5. Run `ffrap_noland off` to clean up all test boxes.

**Part B: scaling:**
6. Low level (Rain and Lasswell at low level in Pharm): test `ffrap_scale party follow`. Evaluate combat feel, then test `attack 70` and `attack 50`.
7. High level (level 52 save): compare `ffrap_scale party` against `ffrap_scale party at 70`.
8. Damage inspection: when encountering severe spikes, note the enemy and value. Compare against exported rows in `scale.txt`.
