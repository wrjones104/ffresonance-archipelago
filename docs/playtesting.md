# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`87f4d742`), world `0.30.0` (`88874051`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds` (the client changed). Close the Launcher and every client window first. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Builds (Round 90)

- [ ] Verify the client's first line says `world version 0.30.0 (build 88874051)`, and the mod's log says `version 0.61.0 (build 87f4d742)` and `client: world version 0.30.0 (build 88874051)`.

## Item colours (Round 90, probes)

- [ ] Type `ffrap_feed colors on`. Four test lines show in the feed. Verify each item name has its colour (Potion light blue, Hookshot purple, Ether dark blue, Bomb Trap red) and the rest of each line is white. The log has `feed step:` lines and `feed colours test: ok, ok, ok, ok`. If the game crashes, send `ap_trace.txt` and the log: the last `feed step:` line is the call that crashed.
- [ ] With colours still on, pick up a few items and send one to another player. Verify each received or sent line colours only the item's name, as the client does. Line positions and fading should be as before.
- [ ] Open any chest, then type `ffrap_popup probe` and send the `popup probe:` lines.
- [ ] Type `ffrap_popup colors on`, then open a chest that is a location. Say what the pop-up shows: the name in a colour, the name in white, or the markup as text (`<text color=...>`). Then `ffrap_popup colors off`. If the game crashes, send `ap_trace.txt` and the log.

## Side quests (Rounds 78 to 90)

- [ ] If you have a save before the end of *The Call from Beyond*, finish it again (a replay now gets its pop-up too). Verify the pop-up shows the Archipelago item, and the log says `chest pop-up for quest:25 before its check`.
- [ ] Mechabo Tackle, step by step. Watch the `mechabo:` lines. At counter 20, talk to Verun at the Dwarven Forge: "Mechabo Evolved" starts and the counter reads 30. Deliver 3 Dhorme Chimera drops (the quest board's "Mechabo Evolved"), then talk to Verun again: the counter reads 40. Verify Lid has Mechabo Tackle, in the menu and in the log line. Send the `mechabo:` lines either way.
