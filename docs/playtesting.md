# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`f04c0650`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 95)

- [ ] Verify the log says `version 0.61.0 (build f04c0650)`. Type `ffrap_quest colors on`, open the Quests screen, and pick a quest that is a location. Verify the Rewards line shows "Alice's" in white and the item's name in its colour and bold, and stays. The log should say `coloured: ... (in a NamedSlot, in its place)`. Move through a few quests and back: verify each line shows its own reward, and no line goes blank. Send the `quest colours:` lines.

## Side quests (Rounds 78 to 95)

- [ ] Load the save where "Arise, Mechabo!" is open. Verify the log says `mechabo: board quests 1001 ordered, so their kills count`, then a `mechabo:` line with `board quest 1001 ordered`. Defeat Ipoohs outside the Dwarven Forge: verify the tracker counts them (1/2, 2/2) and the `mechabo:` line's kills go up (`55 x1`, `55 x2`).
- [ ] Then carry on with Verun: deliver to him (counter 20), talk to him again for "Mechabo Evolved" (counter 30, a `board quests 1002 ordered` line), defeat three dhorme chimerae northeast of Grandport, deliver, and talk to him again (counter 40). Verify Lid has Mechabo Tackle. Send every `mechabo:` line.
