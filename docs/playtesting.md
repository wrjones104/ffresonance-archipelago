# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.62.2` (`2a4f7fce`), world `0.31.2` (`e0989726`). Released before them: v0.31.1 to a few testers (mod `55040fae`, world `937b4b93`, 2026-11-24); v0.31.0 public (mod `7b90595e`, world `66073f7e`, 2026-11-21). Rounds 104 to 111 were built as mod 0.63.0 and world 0.32.0.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 118: the story boss step, the airship at the start

Install: copy `FFRArchipelago/Scripts` only. The apworld did not change, so round 117's seeds and saves are fine.

- [ ] Builds: the log says `version 0.62.2 (build 2a4f7fce)`, and the client prints `world version 0.31.2 (build e0989726)`.
- [ ] Stutter on the laptop: play 5 minutes or more, towns too, and send the `perf:` lines. Is it less than in round 117? `extras: story boss` should be gone from the `steps` line, or small. The `tick` line had 2 to 24 runs over 25 ms in each 2 minutes.
- [ ] Desktop timings: a few minutes is enough. The `tick` line had 23 to 30 runs over 25 ms in each 2 minutes in round 117; it should have far fewer. The `steps` line now names `patches: ...` and `scale: ...` parts.
- [ ] A story boss still works (a seed with bosses on). On a boss map such as Kolobos Ruins, the log has its `story boss: map ...` line, the fight starts, and the win's pop-up names the Archipelago item.
- [ ] The airship at the start (a new seed with `start_with_airship` on). The log has `ok   airship's first place: landing point 9000 -> <id>`. Is the airship next to you before any map change? The `newstart: ... moved to the arrival` line says `airship CPP_MapGimmick_AirShip from ...` or `no airship on the map`. Send that line either way.
- [ ] The Archipelago page's Seed tab ends with `Start: on foot on <your continent>, next to your airship`.
- [ ] The fast travel probe, the step the log missed. Stand away from the Town of Sian, with Sian visited:
  1. `ffrap_visited 2170 unvisit`, then open the Map screen. Does Sian show grey? Does it travel there, or say "Fast Travel cannot be used to go to a place you haven't visited yet"? (Round 118's log has the `unvisit` but not what the Map screen did.)
  2. `ffrap_visited 2170 unknown`, and try again. Does Sian still show? Does it travel?
  3. `ffrap_visited 2170 restore` at the end, before you save.
