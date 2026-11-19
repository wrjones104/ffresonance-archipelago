# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`0e1022be`), world `0.30.0` (`fbcc579c`), released as v0.30.0.

Install: the release's mod zip and apworld, or copy `FFRArchipelago/Scripts` and `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first, and generate a new seed. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 99

- [ ] Verify the client's first line says `world version 0.30.0 (build fbcc579c)`, and the mod's log says `version 0.61.0 (build 0e1022be)`.
- [ ] Talk to a gift NPC (the Colosseum old man, 1400). Verify the pop-up shows the Archipelago item, the log says `chest pop-up for gift:1400 before its check` and then `check gift:1400`, with no second pop-up.
- [ ] Open a chest near a gift NPC you have not talked to yet (Town of Mitra, Gaberada). Verify the chest's pop-up shows the chest's item, not the gift's.
- [ ] Verify the starting continent's unlock shows purple in the feed, and a `!getitem` filler item light blue.

## Carried over (rounds 97 and 98)

- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] In the Research Center Ruins (Gronoa), take each key card shiny. Verify the pop-up shows an Archipelago item, the log says `check shiny:3220:32` (then 33, 37), and the doors open with the cards you get from Archipelago.
- [ ] On foot from Dirnado (no Airship), verify the tracker shows Lyrical Riddles and Elven Maven out of logic until Liquid Thunder is in logic, and in logic with the Airship.
- [ ] Finish a quest that pays gil (Rear Support, Ahoy! in Lanzelt, or Lyrical Riddles). Verify the pop-up names two items, one line each, each in its colour; the log says `check quest:<id>` and `check quest2:<id>`; and the game pays no gil (the gil is in the pool).
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
