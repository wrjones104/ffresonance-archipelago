# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`22b9afbc`), world `0.30.0` (`91355310`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. The round 97 checks can go on with the seed you are playing: the new Scripts keep their old behaviour on it. The round 98 checks need a **new seed**. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Bosses (Round 97)

- [ ] Beat a cave master. Verify the pop-up shows its Archipelago item, the log says `check boss:<group>` and `check fragment:<group>`, and the feed says `Received Crystal Fragment (N/M)`.
- [ ] Beat a boss whose fight gave nothing before: a Nameless Ruins boss, Liquid Thunder, Liquid Flame or Iron Giant, Intangir or Rogue Magitek Weapon, or the Antlion. Verify the pop-up comes up with its item (the game also gives a Potion, the stand-in).
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.

## Lab key cards (Round 97)

- [ ] In the Research Center Ruins (Gronoa), take each key card shiny. Verify the pop-up shows an Archipelago item, the log says `check shiny:3220:32` (then 33, 37), and the doors open with the cards you get from Archipelago.

## NPC gifts (Round 97)

- [ ] Talk to the old man in the Colosseum (Grandshelt) who gave the Lunar Sword and the Brigandine. Verify the pop-up shows the Archipelago item, the log says `gifts: N NPC gift rows give the stand-in` (at load) and `check gift:1400`. The game also gives a Potion, the stand-in.
- [ ] Try one or two more: the two NPCs in the Commercial District (flags 1406, 1407), the Mist Potion NPC in Felicitas (1408) or in Grandshelt Castle (1409), the 200 gil spot in the Town of Mitra (1411), the two in the Town of Sian (1401, and the cat, 1413, after the Mysidia cat). Verify each sends `check gift:<flag>` once.
- [ ] With radar treasures on, talk to the Magi-tenna NPC in Gaberada, the Undertown (Gronoa). Verify `check gift:1405` and an Archipelago item.

## Builds (Round 98)

- [ ] On a new seed, verify the client's first line says `world version 0.30.0 (build 91355310)`, and the mod's log says `version 0.61.0 (build 22b9afbc)` and `client: world version 0.30.0 (build 91355310)`.

## Quest logic (Round 98)

- [ ] On foot from Dirnado (no Airship), verify the tracker shows Lyrical Riddles and Elven Maven out of logic until Liquid Thunder is in logic, and in logic with the Airship.

## Second quest rewards (Round 98)

- [ ] At load, verify the log says `quests: N reward rows without the location's item`.
- [ ] Finish a quest that pays gil (Rear Support, Ahoy! in Lanzelt, or Lyrical Riddles). Verify the pop-up names two items, one line each, each in its colour; the log says `check quest:<id>` and `check quest2:<id>`; and the game pays no gil (the gil is in the pool).
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
- [ ] Open the Quests screen on a quest with two rewards: verify the Rewards name both items, each in its colour.
