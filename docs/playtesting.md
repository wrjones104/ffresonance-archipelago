# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`26e942ac`), world `0.30.0` (`5daa523d`).

Install: copy `FFRArchipelago/Scripts` (it has a new file, `gifts.lua`), and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. **Generate a new seed**: the world has new locations, and an older seed knows none of them. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Builds and options (Round 97)

- [ ] Verify the client's first line says `world version 0.30.0 (build 5daa523d)`, and the mod's log says `version 0.61.0 (build 26e942ac)` and `client: world version 0.30.0 (build 5daa523d)`.
- [ ] In the template yaml, verify `priority_bosses` (Priority Cave Masters) and the new `priority_story_bosses`, and `final_boss_fragments` going up to 40. Generate with `priority_story_bosses: true` once, and check the spoiler puts progression on story bosses.

## Bosses (Round 97)

- [ ] Beat a cave master. Verify the pop-up shows its Archipelago item, the log says `check boss:<group>` and `check fragment:<group>`, and the feed says `Received Crystal Fragment (N/M)`.
- [ ] Beat a story boss the mod brings back (Belmodar in the Earth Shrine, or another on that list). Verify the same: a pop-up with its item, both checks, a fragment. Then walk through a map with Majipots and check they give nothing extra.
- [ ] Beat a boss whose fight gave nothing before: a Nameless Ruins boss, Liquid Thunder, Liquid Flame or Iron Giant, Intangir or Rogue Magitek Weapon, or the Antlion. Verify the pop-up comes up with its item (the game also gives a Potion, the stand-in).
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.

## Lab key cards (Round 97)

- [ ] In the Research Center Ruins (Gronoa), take each key card shiny. Verify the pop-up shows an Archipelago item, the log says `check shiny:3220:32` (then 33, 37), and the doors open with the cards you get from Archipelago.

## NPC gifts (Round 97)

- [ ] Talk to the old man in the Colosseum (Grandshelt) who gave the Lunar Sword and the Brigandine. Verify the pop-up shows the Archipelago item, the log says `gifts: N NPC gift rows give the stand-in` (at load) and `check gift:1400`. The game also gives a Potion, the stand-in.
- [ ] Try one or two more: the two NPCs in the Commercial District (flags 1406, 1407), the Mist Potion NPC in Felicitas (1408) or in Grandshelt Castle (1409), the 200 gil spot in the Town of Mitra (1411), the two in the Town of Sian (1401, and the cat, 1413, after the Mysidia cat). Verify each sends `check gift:<flag>` once.
- [ ] With radar treasures on, talk to the Magi-tenna NPC in Gaberada, the Undertown (Gronoa). Verify `check gift:1405` and an Archipelago item.

## Item colours (Round 97)

- [ ] With no command, open the Quests screen: verify the names show in their colours at once.
