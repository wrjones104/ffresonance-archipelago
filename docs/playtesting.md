# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.62.0` (`af5305a4`), world `0.31.0` (`7c8d8ec3`). Released: v0.30.0 (mod `0e1022be`, world `fbcc579c`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. The mod's fixes work on the round 99 seed; only the gift changes need a new seed. The template yaml now asks for world 0.31.0. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 100

- [ ] Verify the client's first line says `world version 0.31.0 (build 7c8d8ec3)`, and the mod's log says `version 0.62.0 (build af5305a4)`.
- [ ] Go back to Waterfall Way (Olderion) and open the Far-NW Chamber Chest (`chest:3100:3`, not sent yet on the round 99 seed). If the log said `chest:3100:3 reads taken (... save row false ...); never seen closed` on arrival, note whether the chest looked open or closed in the game, and what the line says after `IsOpenTreasureBox`. Verify it is sent only when you open it (`check chest:3100:3`, about 100 from the player), with its pop-up.
- [ ] Watch for `never seen closed` lines on other maps. For each, note whether that chest or shiny looks open in the game. One that looks open and can never be opened would never be sent: tell me its key.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] Finish a quest with a stat bonus or an esper (Nichol's Duty in Olderion, or another character quest). Verify the item's coloured line is gone from the stat bonus and "You can now summon..." messages.
- [ ] Scaling above party level 30: the log's `scale:` line says `counted as`, with 3/4 of the levels over 30 (level 40 counts as 37.5, 60 as 52.5). Note how levels 40 to 50 feel on Normal strength with the game on Normal, and whether the final boss can be won at about level 60.
- [ ] Start a new game from the title menu's plain New Game, with the client connected. Verify the log says `Archipelago is paused`, Rain stays at level 1 through the prologue (Fina at 55), and no `crystals:`, `bosses:`, `quests:`, `gifts:`, `mechabo:`, `antlion:` or `behemoth:` lines appear.
- [ ] Restart the game, then load one of your own saves first. Verify the same: no patch lines, no lock boxes on the world map, the airship where the save left it, and no Archipelago messages on screen.
- [ ] In one run, load the seed's save, then one of your own. Verify the second shows `Archipelago: restart the game before playing this save`. Load the seed's save again and verify it plays as before (patch lines, locks, scaling).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.

## Carried over (rounds 97 to 99)

- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] On foot from Dirnado (no Airship), verify the tracker shows Lyrical Riddles and Elven Maven out of logic until Liquid Thunder is in logic, and in logic with the Airship.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
