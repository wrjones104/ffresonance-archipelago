# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`a87aac00`), world `0.30.0` (`84e053e7`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds` (only the client changed: a seed from world build 91d7b935 still plays). Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Build check (Round 85)

- [x] Verify the log prints `version 0.61.0 (build a87aac00)` and, once connected, `client: world version 0.30.0 (build 84e053e7)`.
- Will's note: the client build was actually 91d7b935

## Settings in the Archipelago page: probe (Round 85, mod build 05f33eda)

Build `05f33eda` is `a87aac00` plus this probe (copy `Scripts` again). Nothing changes until you run the commands. If the game crashes, send `ap_trace.txt` and the log: each step is logged before it runs.

- [ ] In game, run `ffrap_apmenu options`. The log should list `apmenu: screen class ...`, `apmenu: view models 0 -> 2`, `apmenu: input contexts 1 -> 2`, then `apmenu: row: class written, view models written (2), input contexts written (2)` and the same for `subsystem`. Close the main menu, open it, and pick Archipelago. Does the full Options screen open, with its tabs and rows, including ours at the bottom of Gameplay? Send a screenshot.
- [ ] In that screen, change one of our settings (EXP, say) and one of the game's, move between tabs, then press Back. Does Back return to the main menu? Does the change stick (a `settings: from the Options screen` line, and the game's setting still changed in System > Options)? If Back does nothing, run `ffrap_apmenu state`, then `ffrap_apmenu close`.
- [ ] Run `ffrap_apmenu tabs` and send the `apmenu: tab ...` lines. Then run `ffrap_apmenu tabs only` and open Archipelago again. Is Gameplay the only tab now? Then open System > Options: is it the same there? Run `ffrap_apmenu tabs all` and check both show every tab again.
- [ ] Run `ffrap_apmenu text`. Archipelago should open the text page again.

## A save not linked to the seed (Round 85)

- [ ] Load a save of the game's own (plain New Game, or any slot not linked) while the client is connected. Verify the log says `apmenu: taken out of the menu (a save not linked to the seed)`, the main menu has no Archipelago entry, and the log says `settings: the game's own, for a save not linked to the seed`. Win a battle and check the EXP and gil are the game's own (not x3).
- [ ] Load the linked save again. Verify the Archipelago entry is back and your settings apply again (a `settings: exp x...` line).
- [ ] Optional: on the unlinked save, run `/bind` in the client. Verify the entry and the settings come back without loading again.

## Archipelago page: shards and safes (Round 85)

- [x] Open the page with shards in the bag. Verify `Tablet Shards: N held` matches the bag, and `Oblivion Palace safes: R ready to open, O opened; the next needs S shards in all` matches what you can open in the palace.
- [ ] Visit the palace, then open the page again. Verify it now also says `M turned in`.

## Fast travel (Round 85)

- [ ] In a dungeon, open Map in the main menu and pick a fast travel place. Verify it asks the usual confirm question and travels, with no "cannot be used while you are in a dungeon". The log should say `fast travel: allowed from dungeons`. Also try it in the middle of a dungeon with a boss, and say if anything goes wrong.
- [ ] On a seed where the Airship is an item, receive it. Verify the log says `airship: maps 20001, 20002 marked visited, for fast travel`, and check whether the Map screen now lists the airship as a place to travel to. If it does not, say what the airship's entry is called, and run `ffrap_snapshot` before and after boarding it once.

## Side quests (Rounds 78 & 85)

- [ ] Play Mog Tag in Mysidia again (a tier not done yet). Verify the pop-up shows the Archipelago item, not "You obtained a vision!", and the log says `chest pop-up for quest:35: text set` (or 34, 36). The game also gives a Potion, the stand-in.
- [ ] Visit the Dwarven Forge in Dirnado. The log should say `mechabo: 2 rows of Verun's first step accept its quest` once per save loaded. Talk to Verun and verify "Arise, Mechabo!" is in the quest log. If you have the Ipooh drops, deliver them and talk to him again, and verify the quest completes.
- [ ] Complete *The Call from Beyond* (from the Imperial Residences) and *O General! My General!* inside the Phantom Train and Weapons Factory.

## Wording (Round 85)

- [ ] Walk into a locked crossing and verify the notice says `The way is closed. You need ...`.

## Client and save session (Round 77)

- [ ] Load a stamped save on a second PC via Steam Cloud and verify it links automatically (`save is stamped with this seed`) without re-granting items.

## Oblivion Palace safes (Round 80)

- [ ] On an older save where shards were already turned in the old way, verify `progress 43` stays where it was or goes up, never down.
