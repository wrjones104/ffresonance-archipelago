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
- **Scaling:** enemies in Pharm were level 45 and too strong. The log and `scale.txt` looked fine. The screenshot shows a Metal Gigantuar at level 45. It ships at level 52, and only one unit row has that name. So the table *was* rewritten, but with a band whose top is 45, as for a level 52 party (`party 3 at 80` gives 39 to 45). The low-level band (about level 3) was not in force in that battle. Not known yet: which command set it, or whether the table changed after the rescale. Mod 0.15.1 logs the band on screen, checks the table every 10 seconds on the field, and writes it again if it changed.
- Waiting for: the `[FFRAP]` lines of `UE4SS.log` and `scale.txt` from this round.

## Round 34 test plan (mod 0.15.1, world 0.3.1)

Two parts, on a save not linked to a seed (such as the 7090 + Crystal Tower save). Send the `[FFRAP]` lines of `UE4SS.log`, `scale.txt` and `noland.txt`.

**Install:** copy `FFRArchipelago/Scripts` over the installed mod. The log should say `version 0.15.1 loaded`. `Assets` and the apworld did not change (world 0.3.1).

**Before you start:** if you still have round 33's `UE4SS.log` and `scale.txt`, please send them. They show which band was in force in the Metal Gigantuar fight.

**Part A: scaling (do this first, in Pharm, with the low-level party):**
1. Load the save and run `ffrap_scale party follow`. The on-screen message now names the band: "Enemies rescaled to party level N: levels A to B". Write down N, A and B.
2. Run `ffrap_scale` with nothing after it. It says what is in force and checks the table ("table check: R rows, 0 differ").
3. Run `ffrap_scale show metal gigantuar`. The log lists the Metal Gigantuar row in every unit table the game has loaded, with its level now and the level we wanted.
4. Fight two or three battles. Note each enemy's level on the battle screen. If any is outside A to B, take a screenshot, then run `ffrap_scale` and `ffrap_scale show <that enemy's name>` straight after the battle.
5. Look in the log for `scale: the table changed under us`. If it is there, the game loaded the table again (or something wrote it), and the mod wrote our rows back.
6. Then `ffrap_scale party follow attack 70`, and `ffrap_scale party follow attack 50`. How do the fights feel?

**Part B: no-landing boxes (world map, in the airship):**
7. Mysidia, without landing in between:
   - Fly over Mysidia and run `ffrap_noland here`. Each box now has a second line: `collision: actor ..., enabled ..., profile ..., channels ...`.
   - `ffrap_noland lock mysidia`, then `ffrap_noland here` again. Try to land (expect: still allowed, as in round 33).
   - `ffrap_noland refresh`, then `here`, and try to land. Is landing blocked now, without a landing in between?
   - `ffrap_noland unlock mysidia`, `refresh`, `here`, and try to land. Is it allowed again?
   - Then land and take off once, and run `here` again. Did the `collision:` line change?
8. Pharm: fly to the Pharm story box, around (-5930, -17400). `ffrap_noland show` draws it, which helps you find it. Run `ffrap_noland here`. Is it one small box? `lock pharm`, `refresh`, and try to land on that spot. Then try a spot a little away from it.
9. Spawned box: over open land, `ffrap_noland spawn`, then `here`. Compare its `collision:` line with Mysidia's. Is the shadow gone again? Then `ffrap_noland cond {progress:0}<0` and `refresh`: can you land without a landing in between?
10. `ffrap_noland off`.
11. Run `ffrap_find Landing` and `ffrap_functions CPP_MapNonLandingArea CPP_MapAirShipCanNeverLandingBox`, and send `find_Landing.txt` and `functions.txt`. They may show a function that makes the game read the conditions again.
