# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.62.2` (`901ca04e`), world `0.31.2` (`177b8160`). Released before them: v0.31.1 to a few testers (mod `55040fae`, world `937b4b93`, 2026-11-24); v0.31.0 public (mod `7b90595e`, world `66073f7e`, 2026-11-21). Rounds 104 to 111 were built as mod 0.63.0 and world 0.32.0.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Generate a new seed with `include_aileens_forge: true` (side quests on or off): the round 105 save holds two of each early item. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Rounds 113 and 114: lifts and rafts after a fast travel out

Install: copy `FFRArchipelago/Scripts` only (the apworld is round 112's). Your round 112 seed is fine.

- [ ] Builds: the log says `version 0.62.2 (build 901ca04e)`, and the client prints `world version 0.31.2 (build 177b8160)`.
- [ ] The Wind Shrine, as in the Tower of Mysidia: ride a lift, fast travel out, come back in by the door. Each lift is where it was on your first visit. The log has `rides: back as on a first visit: 3070:...` when you leave, and `rides on map 3070: lifts ...` when you come back.
- [ ] The Water Shrine, the Gronoa Shrine and the Sanctissimus Shrine: the same, if you pass them.
- [ ] Cave of Waters: cross on a raft, fast travel out, come back in by the door. A raft waits at the first dock again. The log has `rides: back as on a first visit: 3080 raft <n> -> none` when you leave, and `rides on map 3080: last raft none` when you come back, then the new raft once you ride. If no raft is at any dock, send the log.
- [ ] The Water Shrine's rafts, the same way.
- [ ] If you pass them: the switch floors in Cave of Waters, the Water Shrine and the Weapons Factory, the Weapons Factory's turning bridges, and the falling floor in Kolobos Ruins. After a fast travel out and back in by the door, can you still get through? If not, say which one and where you left it.

## Round 108: key items, fast travel into a locked continent, two Zoldaad shinies

- [ ] Builds: the log says `version 0.63.0 (build 4e6c553b)`, and the client prints `world version 0.32.0 (build 937b4b93)`.
- [ ] Seed with `shuffle_key_items: true`. Try the Abandoned Cabin's door (Pharm), then talk to the man in front of Sian's inn. He says his line from before the cabin and gives no key. The log has `cabin key: the man by Sian's inn no longer gives it`.
- [ ] Seed with `shuffle_key_items: false`. Walk into Zoldaad Dungeon. The log has `dungeon key: given in Zoldaad Dungeon`, the bag has the Dungeon Key, and the cell doors open.
- [ ] On that seed, the spoiler log has items that matter in the Zoldaad Dungeon cells, the throne room, the upper tower, the Abandoned Cabin and the Research Center Ruins' locked rooms (they are in logic now, not filler only). The squad leader's scene in Zoldaad Castle gives the Throne Room Key, and the man by Sian's inn gives the Cabin Key.
- [ ] With Lanzelt locked, do "The Tide from the Sky" in Olderion. The scene goes through Grandport and back. Then the log has `fast travel: maps 2030 are on locked continents, marked not visited`, and the Map screen will not fast travel to Grandport. Once Lanzelt opens, a walk into Grandport makes it a fast travel place again.
- [ ] Radar treasures on: dig every treasure your radars can find. The radar goes quiet, and the log has `every treasure it can find is dug: quiet`. The next Progressive Radar makes it ping again for the new tier. The merchant ship may offer the High-Power Generator after tier 2, as in the game; buying it does nothing.
- [ ] The spoiler log, or the tracker, puts "Zoldaad - World Map - Shiny at SW Peninsula Tip" and "Shiny on South Peninsula West Cove" after the Airship (on an on-foot seed). Tell me if these are not the two shinies the tester meant.

## Rounds 106 and 107: items given twice, the pop-up's two names, the Cabin Key, the Throne Room Key, Grandport's Moogle

- [ ] The spoiler log, or the tracker, puts "Pharm - Abandoned Cabin - NW Corner Chest" after the Cabin Key.
- [ ] The spoiler log, or the tracker, puts "Zoldaad - Castle - Throne Room West Bushes Chest" and "Upper Tower SW Alcove Chest" after the Throne Room Key.
- [ ] Once the save loads, the log has `throne key: 4 squad leader rows give the stand-in`.
- [ ] In Zoldaad Castle, walk to where the squad leader's scene with Shera and Ignis started. The log has `throne key: the squad leader's trigger turned off`, and no scene plays. If it plays anyway, tell me: the key should not come (a Potion comes in its place).
- [ ] The log has `vision moogle: flag 144 set` once. In Grandport Harbor, the vision Moogle is there and its Magicite upgrades work (with a vision; with none, the shop stays closed).

## Round 105, still open: Aileen's forge and Lid's airship line

- [ ] Board the airship on the new seed. Lid does not say "We already found Mysidia...". The log has `radar: step 49 set to 10 (Lid's Mysidia line skipped)`.
- [ ] Finish Forger of Wills (if it is not done yet), then talk to Aileen on the deck with an Adamantite. Forge any weapon. You get the weapon, the pop-up names the Archipelago item, and the log has `check forge:1`.
- [ ] Forge Rain's weapon (Save the Vermillion) before the last one. Aileen still offers the other weapons afterwards. In the base game, Rain's weapon ends the forge.
- [ ] Get two Adamantite before forging (find them, or `/send` them). Tell me what the bag shows: 1 or 2. If 1, the log has `forge: an Adamantite given back` after the first forge, and you can forge again.
- [ ] Equip a forged weapon and wait a few seconds. The `forge: N weapons forged` line in the log does not go down.
- [ ] Tell me how the pop-up and the choice list looked. Every weapon you have not forged shows; the ones you hold do not.

## Carried over (rounds 97 to 101), for the user and the v0.31.0 testers

- [ ] Expert with the game on Expert: if you or a tester try it, note whether it is hard but winnable. Expert is now round 100's Normal with 10% less HP.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
