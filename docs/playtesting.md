# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.0` (`5f911663`), world `0.32.0` (`4649c0ed`). Released before them: v0.31.0 (mod `7b90595e`, world `66073f7e`, 2026-11-21).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Generate a new seed with `include_aileens_forge: true` (side quests on or off): the round 105 save holds two of each early item. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 106: items given twice, the pop-up's two names, the Cabin Key

- [ ] Builds: the log says `version 0.63.0 (build 5f911663)`, and the client prints `world version 0.32.0 (build 4649c0ed)`.
- [ ] Before the prologue skip, get an item (the starting continent's unlock comes then). The feed shows it once. After the skip's reload, the log has no `items: an Archipelago new game: 0 applied`, and the feed does not show it again.
- [ ] Pick up a few items, then reload the autosave (or lose a battle and continue). The bag holds one of each, not two. The log has no `0 applied (was N)` line.
- [ ] A quest with two rewards (or a boss with two): the two names in the pop-up have space between them.
- [ ] The spoiler log, or the tracker, puts "Pharm - Abandoned Cabin - NW Corner Chest" after the Cabin Key.

## Round 105, still open: Aileen's forge and Lid's airship line

- [ ] Board the airship on the new seed. Lid does not say "We already found Mysidia...". The log has `radar: step 49 set to 10 (Lid's Mysidia line skipped)`.
- [ ] Finish Forger of Wills (if it is not done yet), then talk to Aileen on the deck with an Adamantite. Forge any weapon. You get the weapon, the pop-up names the Archipelago item, and the log has `check forge:1`.
- [ ] Forge Rain's weapon (Save the Vermillion) before the last one. Aileen still offers the other weapons afterwards. In the base game, Rain's weapon ends the forge.
- [ ] Get two Adamantite before forging (find them, or `/send` them). Tell me what the bag shows: 1 or 2. If 1, the log has `forge: an Adamantite given back` after the first forge, and you can forge again.
- [ ] Equip a forged weapon and wait a few seconds. The `forge: N weapons forged` line in the log does not go down.
- [ ] Tell me how the pop-up and the choice list looked. Every weapon you have not forged shows; the ones you hold do not.

## Carried over (rounds 97 to 101), for the user and the v0.31.0 testers

- [ ] Expert with the game on Expert: if you or a tester try it, note whether it is hard but winnable. Expert is now round 100's Normal with 10% less HP.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
