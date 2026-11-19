# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`5d85e80c`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 92)

- [ ] Verify the log says `version 0.61.0 (build 5d85e80c)`. With no command, open a chest that is a location: verify the pop-up shows the name in its colour and bold.
- [ ] Type `ffrap_quest colors on`, open the Quests screen, and pick a quest that is a location. Send the `quest colours:` lines whatever the screen shows: each `seen:` line says how many reward lines the mod found, how many are on screen, and the text in each. If the name shows in its colour, move through a few quests and back and check each line shows its own reward.

## Side quests (Rounds 78 to 90)

- [ ] If you have a save before the end of *The Call from Beyond*, finish it again (a replay now gets its pop-up too). Verify the pop-up shows the Archipelago item, and the log says `chest pop-up for quest:25 before its check`.
- [ ] Mechabo Tackle, step by step. Watch the `mechabo:` lines. At counter 20, talk to Verun at the Dwarven Forge: "Mechabo Evolved" starts and the counter reads 30. Deliver 3 Dhorme Chimera drops (the quest board's "Mechabo Evolved"), then talk to Verun again: the counter reads 40. Verify Lid has Mechabo Tackle, in the menu and in the log line. Send the `mechabo:` lines either way.
