# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`c9dab8b2`), world `0.30.0` (`c5fec06a`, unchanged since round 86).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## The Archipelago page (Round 89)

- [ ] Verify the log prints `version 0.61.0 (build c9dab8b2)`, and the Seed tab shows Command rows with no console command.

## Side quests (Rounds 78 to 89)

- [ ] Open the Quests screen and pick a quest that is a location. Verify the Rewards list names its Archipelago item ("Alice's Hookshot", or the item alone for your own), in place of the vanilla item, and other rewards (gil, a second item, a stat bonus) are still listed. The log says `quests: N quest rewards show the location's item` once.
- [ ] Load a save not linked to the seed and open the Quests screen. Verify the Rewards are the game's own.
- [ ] Play a Mog Tag tier not done yet. Verify the pop-up shows the Archipelago item, and the log says `chest pop-up for quest:35 before its check: text set` (or 34, 36). The game still gives a Potion, the stand-in.
- [ ] If you have a save before the end of *The Call from Beyond*, finish it again. Verify the pop-up shows the Archipelago item, and the log says `chest pop-up for quest:25 before its check`.
- [ ] Talk to Verun at the Dwarven Forge. The log says `mechabo: progress 16 at N, flag 219 on|off, Lid ...`. Play "Mechabo Evolved" until the counter reads 40 (deliver the second set of drops, then talk to him). Verify Lid has Mechabo Tackle, in the menu and in the log line. Send the mechabo lines either way.
