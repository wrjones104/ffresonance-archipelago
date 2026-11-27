# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.62.2` (`afd9cf66`), world `0.31.2` (`e0989726`). Released before them: v0.31.1 to a few testers (mod `55040fae`, world `937b4b93`, 2026-11-24); v0.31.0 public (mod `7b90595e`, world `66073f7e`, 2026-11-21). Rounds 104 to 111 were built as mod 0.63.0 and world 0.32.0.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 117: the stutter spread out, fast travel, the airship, Kolobos Ruins' floor

Install: copy `FFRArchipelago/Scripts` only. The apworld did not change, so round 116's seed and save are fine.

- [ ] Builds: the log says `version 0.62.2 (build afd9cf66)`, and the client prints `world version 0.31.2 (build e0989726)`.
- [ ] Stutter on the laptop: play 5 minutes or more and send the `perf:` lines. Does it stutter less than before? When it stutters, run `ffrap_perf` and say so.
- [ ] Stutter on the desktop: a few minutes is enough. Send the `perf:` lines. The `tick` line should have fewer runs over 25 ms than round 116's (13 to 60 in each 2 minutes), and the `steps` line now names parts such as `extras: rides` or `locks`.
- [ ] The airship (a seed with `start_with_airship` on): the Map screen no longer shows it grey. The log has `airship: maps 20001, 20002 marked visited, for fast travel` once.
- [ ] Fast travel probe. Stand somewhere other than the Town of Sian (on the world map, or in another town), with Sian visited. In the console:
  1. `ffrap_visited 2170`, and note the line it shows.
  2. `ffrap_visited 2170 unvisit`, then open the Map screen and try to fast travel to Sian. Does Sian show grey? Does it travel, or say "Fast Travel cannot be used to go to a place you haven't visited yet"?
  3. If it traveled, go back out. Then `ffrap_visited 2170 unknown` and try again. Does Sian still show on the Map screen? Does it travel?
  4. `ffrap_visited 2170 restore` at the end, before you save.
- [ ] The first time the save loads, the log may have `fast travel: maps ... are on locked continents, marked not visited`, listing maps that were only known. On the Map screen, places on locked continents should be gone or grey. Tell me if one you never visited still shows, or still travels.
- [ ] Kolobos Ruins: let the floor fall, fast travel out from the far side, and come back in by the door. The floor is back, as after Rain's "elbow grease" scene, and the log has `kolobos: the fallen floor put back, flag 112` when you leave.
- [ ] The Archipelago page's Seed tab ends with `Start: on foot on <your continent>, the airship beside you` (or with no airship part on a seed without it).

## Rounds 113 and 114: lifts and rafts after a fast travel out

- [ ] The Water Shrine, the Gronoa Shrine and the Sanctissimus Shrine: ride a lift, fast travel out, come back in by the door. Each lift is where it was on your first visit.
- [ ] If you pass them: the switch floors in Cave of Waters, the Water Shrine and the Weapons Factory, and the Weapons Factory's turning bridges. After a fast travel out and back in by the door, can you still get through? If not, say which one and where you left it.

## Round 108, still open

- [ ] Seed with `shuffle_key_items: false`. Walk into Zoldaad Dungeon. The log has `dungeon key: given in Zoldaad Dungeon`, the bag has the Dungeon Key, and the cell doors open.
