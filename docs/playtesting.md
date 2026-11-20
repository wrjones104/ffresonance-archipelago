# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`ad24c957`), world `0.30.0` (`149e31ed`). Released: v0.30.0 (mod `0e1022be`, world `fbcc579c`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. The mod's fixes work on the round 99 seed; only the gift's new name needs a new seed. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 100

- [ ] Verify the client's first line says `world version 0.30.0 (build 149e31ed)`, and the mod's log says `version 0.61.0 (build ad24c957)`.
- [ ] Go back to Waterfall Way (Olderion) and open the Far-NW Chamber Chest (`chest:3100:3`, not sent yet on the round 99 seed). If the log said `chest:3100:3 reads taken (... save row false ...); never seen closed` on arrival, note whether the chest looked open or closed in the game, and what the line says after `IsOpenTreasureBox`. Verify it is sent only when you open it (`check chest:3100:3`, about 100 from the player), with its pop-up.
- [ ] Watch for `never seen closed` lines on other maps. For each, note whether that chest or shiny looks open in the game. One that looks open and can never be opened would never be sent: tell me its key.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] Finish a quest with a stat bonus or an esper (Nichol's Duty in Olderion, or another character quest). Verify the item's coloured line is gone from the stat bonus and "You can now summon..." messages.
- [ ] Talk to the Zoldaad gift: a talk point in Zoldaad Castle's Dungeon (the castle's prison, between the Underground Tunnel and the castle). Verify the pop-up and `check gift:1403`. With a new seed, the tracker names it "Zoldaad - Dungeon - X-Potion and Mist Ether Gift".
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.

## Carried over (rounds 97 to 99)

- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] In the Research Center Ruins (Gronoa), take each key card shiny. Verify the pop-up shows an Archipelago item, the log says `check shiny:3220:32` (then 33, 37), and the doors open with the cards you get from Archipelago.
- [ ] On foot from Dirnado (no Airship), verify the tracker shows Lyrical Riddles and Elven Maven out of logic until Liquid Thunder is in logic, and in logic with the Airship.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
