# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`ec671324`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 91)

- [ ] Verify the log says `version 0.61.0 (build ec671324)`. With no command, receive or send an item: verify the feed shows the item's name in its colour and in bold, and the rest of the line white and not bold.
- [ ] Type `ffrap_popup colors on`, then open a chest that is a location. Verify the pop-up shows "You found ...:" and, under it, the item's name in its colour and bold, centred, in the message's font and size. The log has `popup step:` lines and `chest pop-up for ...: text set, item line hidden, the name in its colour`. Close the pop-up and open another chest: verify the old name is gone. If the game crashes, send `ap_trace.txt` and the log: the last `popup step:` line is the call that crashed.
- [ ] Type `ffrap_quest colors on`, then open the Quests screen and pick a quest that is a location. Verify the Rewards line shows "Alice's" in white and the item's name in its colour and bold, in the same place and font as the game's line. The log says `quest colours: coloured: ... (in a ...)`, and the `quest step:` lines. Move through a few quests and back: verify each line shows its own reward, with no name left over from another quest. If it says `not coloured`, send that line.

## Side quests (Rounds 78 to 90)

- [ ] If you have a save before the end of *The Call from Beyond*, finish it again (a replay now gets its pop-up too). Verify the pop-up shows the Archipelago item, and the log says `chest pop-up for quest:25 before its check`.
- [ ] Mechabo Tackle, step by step. Watch the `mechabo:` lines. At counter 20, talk to Verun at the Dwarven Forge: "Mechabo Evolved" starts and the counter reads 30. Deliver 3 Dhorme Chimera drops (the quest board's "Mechabo Evolved"), then talk to Verun again: the counter reads 40. Verify Lid has Mechabo Tackle, in the menu and in the log line. Send the `mechabo:` lines either way.
