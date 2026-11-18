# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`ad155ef2`), world `0.30.0` (`c5fec06a`, unchanged since round 86).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Build check (Rounds 86 & 87)

- [ ] Close the Archipelago Launcher and every client window, make sure `custom_worlds` holds one `ff_resonance.apworld` (and no `worlds/ff_resonance` folder), then start the client again. Verify the client's first line says `world version 0.30.0 (build c5fec06a)` and the mod's log says `client: world version 0.30.0 (build c5fec06a)`. If not, say which build it shows.

## The Archipelago page in the Options screen (Round 87)

Copy `Scripts`. If the game crashes, send `ap_trace.txt` and the log.

- [ ] Verify the log prints `version 0.61.0 (build ad155ef2)` and `apmenu: SetScene hook registered`.
- [ ] Open the main menu and pick Archipelago, with no console command. Verify one tab named Archipelago, with our settings and the page's lines as headings (no blank heading), none of the game's rows, and the log says `apmenu: mode ap: N game rows hidden, M heading rows` the first time. Change a setting, apply it, and check it takes (`settings: from the Options screen`).
- [ ] Press Back, then open System > Options. Verify every tab and the game's rows are back, and our settings are not there. Open Archipelago and System > Options a few more times, in either order, and check each shows its own.
- [ ] Get a check or an item, then open Archipelago again. Verify the headings show the new counts.
- [ ] On the title screen, open Options. Verify the game's rows and our settings are both under Gameplay.
- [ ] Close the main menu straight from the Archipelago page (the menu button, if there is one), then open System > Options. Verify it is the game's own.

## Side quests (Rounds 78, 85 & 86)

- [ ] Play Mog Tag in Mysidia again (a tier not done yet). Verify the pop-up shows the Archipelago item, not "You obtained a vision!", and the log says `chest pop-up for quest:35: text set` (or 34, 36). The game also gives a Potion, the stand-in.
- [ ] Do the first step of "Mechabo Evolved" for Verun (after "Arise, Mechabo!"), with Lid in the party. Verify Lid learns Mechabo Tackle when the step ends. If you can, try another step with Lid not joined yet, then add her and check whether she has the skill.
- [ ] Complete *The Call from Beyond* (from the Imperial Residences) and *O General! My General!* inside the Phantom Train and Weapons Factory.

## Client and save session (Round 77)

- [ ] Load a stamped save on a second PC via Steam Cloud and verify it links automatically (`save is stamped with this seed`) without re-granting items.
