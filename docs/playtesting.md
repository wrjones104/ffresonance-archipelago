# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.63.1` (`3490441c`), world `0.32.1` (`d62f58e9`), for rounds 120 and 121. Last release: v0.32.0 (public), mod `0.63.0` (`2a1d876c`), world `0.32.0` (`e0989726`), 2026-11-27.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. The apworld changed in round 121 (Adrastea, boss rules, side quests on by default), so **generate a new seed**. Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Open from round 120

- [ ] The builds: the log shows `version 0.63.1 (build 3490441c)`, and the client `world version 0.32.1 (build d62f58e9)`.
- [ ] Stutter on the laptop: play 5 minutes or more on the world map and in towns, and send the `perf:` lines. Is it less than in round 120? In round 120's log the `tick` line averaged 8 to 15 ms, with a slow run every 5 s. `patches: quest colours` should now be about 0.5 ms a run with the Quests screen never opened.
- [ ] Quest colours still work: open the Quests screen. Are the reward names coloured? The log should have `quest colours: SetText hook registered` once.
- [ ] A story boss win: fight one the mod brings back (Kolobos Ruins, or Adrastea below). Before the fight, what does the log's `story boss: map ...` line say in `(N with the stand-in)`? After the win, did any pop-up show? If so, what did it say: a Potion, the Archipelago item, or something else?
- [ ] Lid's radar line: with a Progressive Radar, dig its treasures. Lid should say "the radar seems to have stopped picking up treasure" only after the last one the radar can find, not before. The log has `radar: N of Lid's "stopped picking up treasure" lines set` when it changes.
- [ ] The title label: on the title screen with the client closed, the entry reads "New Game (Archipelago: connect the client)". Start the client and connect while the title stays up. Within about 3 s, does it read "New Game (Archipelago)"? Close the client: does it go back?

## Open from round 121

- [ ] Adrastea in Mobliz Shipyard (map 3060). Go up to where the third lift is, as in the story. The log has `story boss: map 3060 group 9016 flag 1252 ...`; send it, as its `triggers` count says whether the zone is there. Does walking up to the lift start the fight? After the win: `check boss:9016` and `check fragment:9016`, and you stay in the shipyard. If no fight starts, also run `ffrap_lift` there and send the `lift:` lines.
- [ ] Story skills: once Lid is level 30, Fina 40 and Rain 43, a notice "Learned from the story: ..." names Enterprise Airstrike, Holy or The Power Within. Is each one in that character's abilities, and can it be used in battle?
- [ ] Side quests on by default: with a yaml that does not set `include_side_quests`, the spoiler log has the quest locations ("Quest: ...").
