# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`c2d4d794`), world `0.30.0` (`88874051`, unchanged since round 90).

Install: copy `FFRArchipelago/Scripts`. The apworld is unchanged. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Item colours (Round 96)

- [ ] Verify the log says `version 0.61.0 (build c2d4d794)`. With no command, open the Quests screen and pick a quest that is a location: verify the name shows in its colour (about a second late, as in round 95). The log says one `quest colours: coloured: ...` line, not one per quest.
- [ ] Type `ffrap_quest instant on`, then open the Quests screen. Verify the log says `quest colours: SetText hook registered`. Move through quests: verify each scouted name shows in its colour at once, and lines for other rewards are the game's own. The log has `quest colours (instant): coloured: ...` lines and `quest step:` lines for the first one. If the game crashes, send `ap_trace.txt` and the log: the last `quest step:` line is the call that crashed.
