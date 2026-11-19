# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`8aafe048`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 94)

- [ ] Verify the log says `version 0.61.0 (build 8aafe048)`. Type `ffrap_quest colors on`, open the Quests screen, and pick a quest that is a location. Verify the Rewards line shows "Alice's" in white and the item's name in its colour and bold. Send the `quest colours:` lines either way: `seen: N reward lines on screen: "..." by property` (or `by slot`, or `no text block`), then `coloured:` or `not coloured:`. Move through a few quests and back: verify each line shows its own reward. If the game crashes, send `ap_trace.txt` and the log: the last `quest step:` line is the call that crashed.

## Side quests (Rounds 78 to 94)

- [ ] Verun's quests on a seed's save. The `mechabo:` line now also says `board quest 1001 ...`: the hunt's state (none, ordered, met, done) and its kills (`55 xN` is Ipooh). Send every `mechabo:` line.
  - Load the save where "Arise, Mechabo!" is open and note the `board quest 1001` part.
  - Talk to Verun at the Dwarven Forge, and note it again.
  - Defeat Ipoohs near the Dwarven Forge, and note it after each battle. Say where the Ipoohs were (the map).
