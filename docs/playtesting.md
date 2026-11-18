# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`b93912a5`), world `0.30.0` (`c5fec06a`). Nothing changed since round 86.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Build check (Rounds 86 & 87)

- [ ] Close the Archipelago Launcher and every client window, make sure `custom_worlds` holds one `ff_resonance.apworld` (and no `worlds/ff_resonance` folder), then start the client again. Verify the client's first line says `world version 0.30.0 (build c5fec06a)` and the mod's log says `client: world version 0.30.0 (build c5fec06a)`. If not, say which build it shows.

## Side quests (Rounds 78, 85 & 86)

- [ ] Play Mog Tag in Mysidia again (a tier not done yet). Verify the pop-up shows the Archipelago item, not "You obtained a vision!", and the log says `chest pop-up for quest:35: text set` (or 34, 36). The game also gives a Potion, the stand-in.
- [ ] Do the first step of "Mechabo Evolved" for Verun (after "Arise, Mechabo!"), with Lid in the party. Verify Lid learns Mechabo Tackle when the step ends. If you can, try another step with Lid not joined yet, then add her and check whether she has the skill.
- [ ] Complete *The Call from Beyond* (from the Imperial Residences) and *O General! My General!* inside the Phantom Train and Weapons Factory.

## Client and save session (Round 77)

- [ ] Load a stamped save on a second PC via Steam Cloud and verify it links automatically (`save is stamped with this seed`) without re-granting items.
