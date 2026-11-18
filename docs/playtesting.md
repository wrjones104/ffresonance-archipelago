# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.61.0` (`b93912a5`), world `0.30.0` (`c5fec06a`).

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. The Oblivion Palace locations are renamed (Safe to Chest), so generate a new seed to see the new names; an older seed still plays. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Build check (Round 86)

- [ ] Verify the log prints `version 0.61.0 (build b93912a5)` and, once connected, `client: world version 0.30.0 (build c5fec06a)`.

## A save not linked to the seed (Rounds 85 & 86)

- [ ] On the linked save, run `ffrap_scale 1`. Then load a save of the game's own. Verify the log says `locks: off for a save not linked to the seed (N ferry choices put back)` and `scale: ffrap_scale is off for a save not linked to the seed`, that you can fly or walk onto every continent, that the ferry goes everywhere, and that enemies are at their own levels.
- [ ] Load the linked save again. Verify the locks are back (boxes on locked continents, `The way is closed` at a crossing) and the seed's scaling is on again.

## Archipelago page (Round 86)

- [ ] Open the page. Verify it says `Tablet Shards: N collected` (every shard you have had, held or turned in) and `Oblivion Palace Chests: R ready to open`, and that R is the number of palace chests you can open now.
- [ ] With a new seed, verify the palace locations are named "... N-Shard Chest (...)" in the client and in Universal Tracker.

## Settings in the Archipelago page: probe (Round 86)

Nothing changes until you run the commands. Each step is logged before it runs.

- [ ] Run `ffrap_apmenu options`, then `ffrap_apmenu mode ap`. The log should say `apmenu: SetScene hook registered` and end with `mode ap: N game rows hidden, M heading rows`. Close the main menu, open it, and pick Archipelago. Is there one tab, named Archipelago, with our settings and the page's lines as headings, and none of the game's rows? Send a screenshot. Does the log say `apmenu: SetScene UI.MainMenu.Scene.FFRAP` when you pick it, and a SetScene line for other entries?
- [ ] Still in `mode ap`, open System > Options. It will look the same for now (one tab); say whether it does.
- [ ] Run `ffrap_apmenu mode game`, then `ffrap_apmenu text`. Verify System > Options has every tab and row again, and the Archipelago entry opens the text page.

## Side quests (Rounds 78 & 85)

- [ ] Play Mog Tag in Mysidia again (a tier not done yet). Verify the pop-up shows the Archipelago item, not "You obtained a vision!", and the log says `chest pop-up for quest:35: text set` (or 34, 36). The game also gives a Potion, the stand-in.
- [ ] Load the save, go to the Dwarven Forge in Dirnado and talk to Verun. Verify "Arise, Mechabo!" is now in the quest log. Then defeat two Ipoohs (kills from before may not count), and check whether the quest moves on and Verun's next talk completes it.
- [ ] Complete *The Call from Beyond* (from the Imperial Residences) and *O General! My General!* inside the Phantom Train and Weapons Factory.

## The log on a late bind (Round 86)

- [ ] If you bind a save with many items again, verify the feed says `Receiving N items from Archipelago` and then `Received N items`, and the log has one line for far-away pick-ups per scan and no `sync: check` lines.

## Client and save session (Round 77)

- [ ] Load a stamped save on a second PC via Steam Cloud and verify it links automatically (`save is stamped with this seed`) without re-granting items.
