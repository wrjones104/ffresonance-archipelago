# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`ac15f02e`), world `0.30.0` (`c5fec06a`, unchanged since round 86).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## The Archipelago page (Round 88)

- [ ] Verify the log prints `version 0.61.0 (build ac15f02e)`.
- [ ] Start the game, load a seed's save, and open Archipelago soon after, as in round 87. Verify the Settings tab shows our settings on the first open. If the log says `apmenu: the Options tables were loaded again with the page open`, switch to Seed and back, and say whether Settings is right then.
- [ ] Change a setting on the page, apply it, and check it takes (`settings: from the Options screen`). Close the page, open it again, and check the setting kept its value.
- [ ] Open System > Options in game, and Options on the title screen. Verify neither has our settings, and both have all of the game's own rows.
- [ ] Type `ffrap_apmenu seedrows command`, then open Archipelago and pick the Seed tab. Verify whether the cursor can move down the lines and the tab scrolls with a gamepad. Press confirm on a line and say what happens. `ffrap_apmenu seedrows heading` puts the headings back. If the game crashes, send `ap_trace.txt` and the log.

## Side quests (Rounds 78, 85 & 86)

- [ ] Play Mog Tag in Mysidia again (a tier not done yet). Verify the pop-up shows the Archipelago item, not "You obtained a vision!", and the log says `chest pop-up for quest:35: text set` (or 34, 36). The game also gives a Potion, the stand-in.
- [ ] Do the first step of "Mechabo Evolved" for Verun (after "Arise, Mechabo!"), with Lid in the party. Verify Lid learns Mechabo Tackle when the step ends. If you can, try another step with Lid not joined yet, then add her and check whether she has the skill.
- [ ] Complete *The Call from Beyond* (from the Imperial Residences) and *O General! My General!* inside the Phantom Train and Weapons Factory.

## Client and save session (Round 77)

- [ ] Load a stamped save on a second PC via Steam Cloud and verify it links automatically (`save is stamped with this seed`) without re-granting items.
