# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.0` (`2a1d876c`), world `0.32.0` (`e0989726`), packaged as v0.32.0 (public) on 2026-11-27. Released before them: v0.31.1 to a few testers (mod `55040fae`, world `937b4b93`, 2026-11-24); v0.31.0 public (mod `7b90595e`, world `66073f7e`, 2026-11-21). Rounds 104 to 111 were built as mod 0.63.0 and world 0.32.0.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Open from rounds 118 and 119

- [ ] Stutter on the laptop: play 5 minutes or more, towns too, and send the `perf:` lines. Is it less than in round 117? In round 119's desktop log the `tick` line had 5 runs over 25 ms in 2 minutes, and `patches: quest colours` should now be small too.
- [ ] A story boss's pop-up: on a win, what did the item pop-up say? Round 119's log has `chest pop-up for boss:9012: no chest pop-up on screen`, so the mod did not write it. The item still came in the feed.
- [ ] The fast travel probe. Stand away from the Town of Sian, with Sian visited:
  1. `ffrap_visited 2170 unvisit`, then open the Map screen. Does Sian show grey? Does it travel there, or say "Fast Travel cannot be used to go to a place you haven't visited yet"?
  2. `ffrap_visited 2170 unknown`, and try again. Does Sian still show? Does it travel?
  3. `ffrap_visited 2170 restore` at the end, before you save.
