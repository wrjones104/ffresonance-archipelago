# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.0` (`c0ed153e`), world `0.31.1` (`7c8d8ec3`). Packaged for release: v0.31.0 (mod `3245e5b1`, world `7c8d8ec3`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds` (only its version number changed, so a v0.31.0 seed still works). Close the Launcher and every client window first. The template yaml asks for world 0.31.0. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 102

- [ ] Verify the client's first line says `world version 0.31.1 (build 7c8d8ec3)`, and the mod's log says `version 0.63.0 (build c0ed153e)`.
- [ ] Open the Archipelago page. Verify three tabs: **Settings**, **Scaling test** and **Seed**. **Scaling test** should show only our six rows (Scaling preset and the five Custom sliders), with none of the game's graphics rows. If the tab is missing, looks wrong or the game crashes, run `ffrap_apmenu testtab off` and open the page again: the rows should then be at the bottom of **Settings**.
- [ ] Set **Scaling preset** to 2 and close the page. Verify the log says `settings: from the Options screen: ... preset 2` and a new `scale:` line says `preset B normal`. Restart the game and verify the slider still reads 2.
- [ ] Set the preset to 4 and move **Custom: enemy HP %** to 60. Verify the `scale:` line says `preset custom 92/60/100/103/105` and `HP 60%`. Move it with a gamepad too, and note whether a range of 100 steps is too slow to use.
- [ ] Verify the Graphics tab in **System > Options** is back to normal after the page closes (its rows are there, and ours are not).
- [ ] Win a few battles. Verify a `battle: won (N in all), S s off the field; preset ..., party level L` line after each, with N going up by one. Note whether a battle you fled from, or a boss fight, logs a line.

## Round 101

- [ ] Scaling is one step softer. On Normal, the log's `scale:` line shows separate HP and attack, and `MRP as level` at the party's level. At party level 25 or more it should read about `preset A normal: enemies centre 23 (92%), 22 to 24, HP 85%, attack 100%; bosses centre 26 (103%), power 105%`.
- [ ] Hallway fights on Normal, with the game on Normal: note how many rounds a normal fight takes. They should be short, but enemies should still hurt if you are careless. Note this for regions ahead of you too (enemies at the top of the band).
- [ ] MRP per fight: note a fight's MRP at some party level. It should be about the same as round 100 at the same level, not lower.
- [ ] Bosses on Normal at party level 30 or more: note whether they are a fair fight with what the seed has given you.
- [ ] Above party level 30, the log's `scale:` line says `counted as`, with 3/4 of the levels over 30 (level 40 counts as 37.5, 60 as 52.5). Note how levels 40 to 50 feel on Normal, and whether the final boss can be won at about level 60. If it is now too easy up there, tell me: the softer strengths and round 100's slowdown stack.
- [ ] Expert with the game on Expert: if you or a tester try it, note whether it is hard but winnable. Expert is now round 100's Normal with 10% less HP.

## Round 100

- [ ] Go back to Waterfall Way (Olderion) and open the Far-NW Chamber Chest (`chest:3100:3`, not sent yet on the round 99 seed). If the log said `chest:3100:3 reads taken (... save row false ...); never seen closed` on arrival, note whether the chest looked open or closed in the game, and what the line says after `IsOpenTreasureBox`. Verify it is sent only when you open it (`check chest:3100:3`, about 100 from the player), with its pop-up.
- [ ] Watch for `never seen closed` lines on other maps. For each, note whether that chest or shiny looks open in the game. One that looks open and can never be opened would never be sent: tell me its key.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] Finish a quest with a stat bonus or an esper (Nichol's Duty in Olderion, or another character quest). Verify the item's coloured line is gone from the stat bonus and "You can now summon..." messages.
- [ ] Start a new game from the title menu's plain New Game, with the client connected. Verify the log says `Archipelago is paused`, Rain stays at level 1 through the prologue (Fina at 55), and no `crystals:`, `bosses:`, `quests:`, `gifts:`, `mechabo:`, `antlion:` or `behemoth:` lines appear.
- [ ] Restart the game, then load one of your own saves first. Verify the same: no patch lines, no lock boxes on the world map, the airship where the save left it, and no Archipelago messages on screen.
- [ ] In one run, load the seed's save, then one of your own. Verify the second shows `Archipelago: restart the game before playing this save`. Load the seed's save again and verify it plays as before (patch lines, locks, scaling).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.

## Carried over (rounds 97 to 99)

- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] On foot from Dirnado (no Airship), verify the tracker shows Lyrical Riddles and Elven Maven out of logic until Liquid Thunder is in logic, and in logic with the Airship.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
