# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.0` (`c02e6de5`), world `0.32.0` (`94562703`). Released before them: v0.31.0 (mod `7b90595e`, world `66073f7e`, 2026-11-21).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Generate a new seed: the pool has new items and there are two new options. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 104: the item pool pass

- [ ] Builds: the log says `version 0.63.0 (build c02e6de5)`, and the client prints `world version 0.32.0 (build 94562703)`.
- [ ] Generate a seed with the template's defaults. The spoiler log has 2 Ribbons, one each of Angel Ring, Gale Hairpin, Solar Pendant, Azure Amulet, Golem Core and Halo Ring (among others), and 3 more of each Magicite tier than before.
- [ ] The spoiler's playthrough has one of Leah, Ayaka, Warrior of Light, Cecil, Tidus, Y'shtola or Lightning in your own world in sphere 1.
- [ ] Receive a Ribbon (find it, or `/send` it from the server console). It is in the bag under accessories, with its name, and a party member can equip it.
- [ ] Receive one of the imbue charms (Solar Pendant, Azure Amulet, Golem Core, Halo Ring) the same way, and equip it.
- [ ] Generate with `extra_magicite: 0` and `early_healing_vision: false`. The seed has the old Magicite count and no early vision.

## Carried over (rounds 97 to 101), for the user and the v0.31.0 testers

- [ ] Expert with the game on Expert: if you or a tester try it, note whether it is hard but winnable. Expert is now round 100's Normal with 10% less HP.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
