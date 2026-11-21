# Playtesting checklist

Only open items that still need to be tested in game live here. Once tested, record the results in [docs/playtesting_archive.md](playtesting_archive.md) and remove completed items from this file. Automated suite tests are documented in [tests/README.md](../tests/README.md).

Current builds: mod `0.62.0` (`7b90595e`), world `0.31.0` (`66073f7e`). Released: v0.30.0 (mod `0e1022be`, world `fbcc579c`). v0.31.0 is not posted yet: it will be packaged from these builds after pre-release testing.

Install: copy `FFRArchipelago/Scripts`, and copy `dist/ff_resonance.apworld` into `custom_worlds`. Close the Launcher and every client window first. Generate a new seed: four key items left the pool, and there is a new option. Send the `[FFRAP]` lines of `UE4SS.log`. If the game crashes, send `Mods/FFRArchipelago/ap_trace.txt`, the crash folder, and the log before starting the game again.

## Round 103

- [ ] Verify the client's first line says `world version 0.31.0 (build 66073f7e)`, and the mod's log says `version 0.62.0 (build 7b90595e)`.
- [ ] Open the Archipelago page. Verify two tabs: **Settings** on the gear icon and **Seed** on the monitor icon, with no Sound or Scaling test tab.
- [ ] Open and close the page four or five times. Verify the Settings rows and the Seed lines are in the same order each time.
- [ ] After the page closes, open **System > Options**. Verify the Graphics and Sound tabs show their own rows, and none of ours.
- [ ] Win a battle. Verify the line reads `battle: won (save's win count N), ... strength normal, ...`.
- [ ] Generate with `include_side_quests: true` and `hide_quest_rewards: true`. Verify every reward on the Quests screen reads `???` in white, and that finishing a quest still shows its item in the pop-up.
- [ ] Generate with `hide_quest_rewards: false` (the default). Verify the Quests screen names each item in its colour, as before.
- [ ] Verify the spoiler log and the tracker have no White Jade Stone, Black Jade Stone, Magic Tome or Tunnel Key.

## Carried over (rounds 97 to 101)

- [ ] Expert with the game on Expert: if you or a tester try it, note whether it is hard but winnable. Expert is now round 100's Normal with 10% less HP.
- [ ] Load the save on the other computer, or one played there, and open a new chest on the first map. Verify its pop-up shows its own item, and that the chests opened on the other computer go out with no pop-up (`check chest:...` with no `chest pop-up for` line after it).
- [ ] If the game crashes again, play a session with FFR_MapMarkers and FFRBestiary turned off (delete their `enabled.txt`, or move the folders out of `Mods`), to tell whether the crash is in this mod.
- [ ] Load a save with bosses already beaten: verify the log sends `check fragment:<group>` for each of them.
- [ ] Finish a vision quest (Errand's End, Forger of Wills, The Call from Beyond or another). Verify the same, and that the game gives no vision and no Magicite of its own.
