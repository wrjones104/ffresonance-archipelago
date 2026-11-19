# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`2dcd20c4`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 93)

- [ ] Verify the log says `version 0.61.0 (build 2dcd20c4)`. Type `ffrap_quest colors on`, open the Quests screen, and pick a quest that is a location. Verify the Rewards line shows "Alice's" in white and the item's name in its colour and bold, in the place and font of the game's line. Send the `quest colours:` lines either way (`seen: N reward texts: ...`, then `coloured:` or `not coloured:`). Move through a few quests and back: verify each line shows its own reward. If the game crashes, send `ap_trace.txt` and the log: the last `quest step:` line is the call that crashed.

## Side quests (Rounds 78 to 93)

- [ ] Verun's quests, one step at a time, on a seed's save. Each `mechabo:` line now says the counter, flag 219, the quest log's state of quests 17 ("Arise, Mechabo!"), 26 ("Mechabo Evolved") and 27, and Lid's Mechabo Tackle. Send every `mechabo:` line.
  - At counter 10, talk to Verun at the Dwarven Forge. Say what he says, and whether quest 17 shows in the quest log (the line should say `quest 17 open`).
  - Deliver 2 Ipooh drops and talk to him again: counter 20, quest 17 done.
  - Talk to him again: counter 30, quest 26 open.
  - Deliver 3 Dhorme Chimera drops and talk to him again: counter 40. Verify Lid has Mechabo Tackle.
