# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.1` (`3f446645`), world `0.32.1` (`e0989726`), for round 120. Last release: v0.32.0 (public), mod `0.63.0` (`2a1d876c`), world `0.32.0` (`e0989726`), 2026-11-27.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. The apworld's build is unchanged, so a v0.32.0 seed still works; no new seed is needed. Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Open from round 120

- [ ] The builds: the log shows `version 0.63.1 (build 3f446645)`.
- [ ] Stutter on the laptop: play 5 minutes or more on the world map and in towns, and send the `perf:` lines. Is it less than in round 120? In round 120's log the `tick` line averaged 8 to 15 ms, with a slow run every 5 s. `patches: quest colours` should now be about 0.5 ms a run with the Quests screen never opened.
- [ ] Quest colours still work: open the Quests screen. Are the reward names coloured? The log should have `quest colours: SetText hook registered` once.
- [ ] A story boss win: fight one the mod brings back (Kolobos Ruins, or another). Before the fight, what does the log's `story boss: map ...` line say in `(N with the stand-in)`? After the win, did any pop-up show? If so, what did it say: a Potion, the Archipelago item, or something else?
- [ ] Lid's radar line: with a Progressive Radar, dig its treasures. Lid should say "the radar seems to have stopped picking up treasure" only after the last one the radar can find, not before. The log has `radar: N of Lid's "stopped picking up treasure" lines set` when it changes.
- [ ] The title label: on the title screen with the client closed, the entry reads "New Game (Archipelago: connect the client)". Start the client and connect while the title stays up. Within about 3 s, does it read "New Game (Archipelago)"? Close the client: does it go back?
- [ ] The Mobliz Shipyard lift probe (map 3060). Stand at the top, where lift 75 should come up to (past the middle lift, by the switch above the right lift):
  1. `ffrap_lift`, and send the `lift:` lines (each lift's stop, points and place).
  2. `ffrap_lift 75 call 1 up`. Does lift 75 come up?
  3. If not: `ffrap_lift 75 exec 1`, then `ffrap_lift 75 call 0 down`. Does either move it?
