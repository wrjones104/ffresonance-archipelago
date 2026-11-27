# Roadmap

What to build next, in order, and what goes together. The ideas themselves, with what is known, are in [IDEAS.md](../IDEAS.md); numbers below are its idea numbers (done ones are in [ideas_archive.md](ideas_archive.md)). This file says only the order and the reasons. Updated 2026-11-27, after v0.32.0.

## Where we are

A tester (2026-11-22, v0.31.0, Normal scaling, progression balancing 65) finished a full seed. Their `UE4SS.log`:

| | |
|---|---|
| Time | about 7.5 hours, start to `Goal complete!` |
| Party level at the last battle | 30 |
| Battles won | 107; median 36 s off the field, 90% under 3 minutes |
| Checks sent | 286: 121 chests, 120 shinies, 14 bosses with their 14 fragments, 12 crystals, 3 gifts, 2 radar |
| Side quests | off (the default) |
| Errors or crashes | none |

What they said: fun and well-rounded; early and mid game fast, late game fine; status effects hard with no Ribbon and few cures; magicite tight but fair; they thought level scaling was a gate at first; their partner's items felt back-loaded (likely the seed). They asked for a separate save location per seed, and a PopTracker pack.

In **v0.32.0** (`2026-11-27`, world `0.32.0`, mod `0.63.0`), we shipped the item pool pass (2 Ribbons, 13 enemy-only accessories, `extra_magicite`, `early_healing_vision`, Proofs of Victory out, Lid's airship line gone), `include_aileens_forge` (8 airship-deck forge locations), and the rounds 106 to 119 stabilization wave: the direct open start with no prologue or slot reload (52), held move input and the `ap_alive.txt` client heartbeat on the title screen (54), the key-item audit and logic fixes (51), lift/raft/Kolobos floor resets after fast travel out (53), walked-in fast travel (57), and the main-loop stutter pass (55).

So the core loop and the opening are solid. The next big release (v0.33.0) focuses on v0.32.0 follow-ups, finishing core progression logic with side quests on by default, and clear in-game UX and scaling controls.

## The order

Each milestone is about one public release.

### 1. Next release: v0.33.0 (world 0.33.0, mod 0.64.0) - UX, scaling controls, and core logic

Work batches across tester builds (`0.32.1` / `0.63.1` onward) in three stages.

#### Stage A: v0.32.0 follow-ups and dungeon/UI fixes

1. Check incoming `perf:` logs on laptops and slower PCs (towns and Dragon's Maw) and trim any remaining slow steps (55).
2. Run the `ffrap_visited` check (`unvisit` and `unknown`) to confirm the Map screen blocks unwalked places (57).
3. Fix story boss item pop-ups so wins (`boss:9012` in round 119) show the scouted Archipelago item instead of missing the dialog (15).
4. Fix Mobliz Shipyard's last lift (elevator 75 on map 3060, via the switch 16 talk chain / `CallSwitch`) so its 2 chests and 2 Tablet Shards are reachable (53).
5. Fix the two radar rough edges: stop Lid's early "stopped finding treasure" line while treasures remain, and allow digging treasures right away when a Progressive Radar arrives mid-flight without a map change (51).
6. Refresh the **New Game (Archipelago)** client-heartbeat label live while the title screen stays open (54).

#### Stage B: Finish core logic and turn side quests on by default

1. Audit story-granted abilities skipped by the open start (`DT_TalkEventData_Chapter*` and `CharaEvent` second Limit Bursts) against `data/game/capabilities.tsv`, and grant what logic or pre-tower play expects (40).
2. Add dump-verified per-boss `BOSS_NEEDS` rules for Tiers C and D in [boss_logic.py](../apworld/ff_resonance/boss_logic.py): Sephiroth (`9138` Phase 3 `light_physical`), Intangir (`7042`), Rogue Magitek Weapon (`7057`), the Sanctissimus gauntlet (`9071` to `9076` and `9044`), and endgame cave masters (`9110` to `9117`). Currently only Tiers A and B have per-boss `BOSS_NEEDS` rules.
3. Switch `include_side_quests` to on by default (`DefaultOnToggle` in [options.py](../apworld/ff_resonance/options.py) and the template YAML), bringing the 28 quest rewards and 17 second rewards (45 checks) into standard seeds. Its logic ([side_quests.md](side_quests.md), section 5) is already done.

#### Stage C: UX, client tracker, and scaling controls

Ideas 49, 56, 58, 11, and 22, plus documentation updates. Most solve the same problem: the player cannot see or tune the seed's state cleanly in game.

1. Add a scaling explanation line on the Seed tab ("Enemies scale to your party level, so no area is out of reach") and update stale sections of [playtester_guide.md](playtester_guide.md) (which still says quests and NPCs are unshuffled and points to `Options > Gameplay`).
2. Build unified Enemy/Boss and Custom scaling on the Settings tab (49 + 56): a `Custom scaling` switch (default Off = Standard). In `Standard` mode, Enemies and Bosses get separate On/Off switches and separate `Casual`, `Normal`, and `Expert` preset rows (copied from `Difficulty`). Turning `Custom scaling` on hides the presets and shows the five percentage sliders from round 102 (`891e70d`: `elevel`, `ehp`, `eatk`, `blevel`, `bpower`), seeded from the active presets and logged on `battle: won`.
3. Mark Archipelago saves on Load and Save slot cards (11): write `server <host:port>` and `player <name>` into `ap_in.txt`, keep a persistent per-slot summary record, and draw the seed/slot line in `WBP_SaveData_Entry_C` (`Vertical_Mid`). This answers "which save is which" without changing the engine's save folder path; look at a separate folder only if testers still mix saves up after the cards.
4. Show a one-time welcome window on a new Archipelago game (22) via `CPP_BFL_Dialog.OpenDialog` on an existing `CDT_DialogBox` row (`Map_FastTravel_CanNot`), covering scaling, continent unlocks, and the **Archipelago** menu entry.
5. Integrate Universal Tracker into Final Fantasy Resonance Client (58): subclass `TrackerGameContext` when `tracker.apworld` is installed (with a clean fallback to `CommonContext` when it is not) so players get the **Tracker** tab in the same client window instead of running two clients. Pure Python work in `client.py`, pairing with Stage B's logic completion.

### 2. More locations (`v0.34.0+`)

Add the remaining locations once core logic and default side quests are settled. Most valuable first:

1. The rest of the bosses: Tier 3 story bosses still missing, then Tier 2 (espers, Gilgamesh, Odin, Ultima Weapon, Chamber of Arms, Arena). This also closes the "not done yet" known issue ([bosses.md](bosses.md), section 5).
2. Mechabo upgrade quests as locations (33). The mod already starts and runs the quest chain (`side_quests.md`).
3. Character-quest stat bonuses as items (45), once we find what writes them.
4. Shopsanity (31), with the ocean merchant ships and hints bought with gil (25, item 5). Gil has little use now, and this gives it one.
5. Librasanity and enemysanity (30), and character abilities as checks (28). Hundreds of locations, so they need lots of filler.

### 3. Multiworld features: DeathLink and traps

Ideas 41 and 20, together. Both need the same piece: something to bank until the next battle starts, then act on the party. Build the battle-start hook and persistent queue in `ap_state.txt` once, then DeathLink and each trap (`Bad Breath`, stat downs) are small on top of it. DeathLink is the one the Archipelago community expects; traps follow.

### 4. PopTracker pack (47)

After milestones 1 and 2, not before. A pack copies the logic and the location list, so each logic change or location rename means a pack update. `data/location_names.tsv` names are already filled apart from the 3 Research Center Ruins lab key card shinies, and Universal Tracker (especially once built into the client in idea 58) covers text and logic tracking in one window until map tracking lands.

### 5. Randomizer extras

Ideas 7 (enemy randomization), 8 (stats, weaknesses), 9 (music shuffle and reroll menu), 46 (custom vision mods), and 50 (the field character follows the party leader), plus shuffled boss order (25.3), random per-seed objectives (25.4), and party slots as items (25.7). Fun, but none of them make a seed fairer.

- 50 is cosmetic but touches the field pawn, which the airship position and gate crossings read (round 69). Cutscenes may look for Rain. Its first step is cheap and goes under Polish: test the Nexus "Change field Leader" mod (Party Members Only) with ours.
- 8 and boss logic touch the same thing: boss logic reads each boss's weaknesses from fixed tables. Weakness randomization must hand its rolls to the logic too, or the logic asks for the wrong elements.
- 7 and 8 clash with FFRRandomizer (10). Settle the compatibility story first.

### Long shot

The in-game client (12). Option B (start the client from the game) is a quality-of-life change with some risk; Option A (a C++ `APCpp` client) is a project of its own. Only if players keep tripping on the separate client.

## Polish, any time

Small items to pick up when a round has room:

- Back-to-back check pop-ups: when two checks arrive at once, the second pop-up shows the game's item (15, known issue).
- The Oblivion Palace safes live refresh when shards arrive while standing inside the palace (37): leave unless cheap.
- Archipelago page layout: headings and framed rows (38). Nice, not needed.
- The two missing gifts, `1407` and `1409` (43).
- Test the Nexus "Change field Leader" mod, Party Members Only version, with ours, and list it in the README if it works (50, way 1). Its permissions do not let us take its code.
- Remove the old autosave prologue-skip fallback once the direct open start (`ffrap_newstart`, v0.32.0) has full playtest mileage (52).
- Fill the `name` column for the 3 Research Center Ruins lab key card shinies (`shiny:3220:32`, `33`, `37`) in [data/location_names.tsv](../data/location_names.tsv).
- Artifacts: parked (26).

## What goes together

| Group | Ideas | Shared piece |
|---|---|---|
| v0.32.0 fixes | 15, 51, 53, 54, 55, 57 | follow-ups to the fifth public playtest build |
| Scaling UI | 49, 56, scaling line | Enemy/Boss presets and Custom sliders on the Settings tab |
| In-game state | 11, 22, 38 | showing seed state in the game's UI |
| Logic | 40, Tier C/D `BOSS_NEEDS`, side quests default on | the capability matrix and default seed pool |
| Battle start | 20, 41 | the banked-effect hook and queue |
| Gil | 31, hints (25.5) | a reason to spend gil |
| Big location counts | 28, 30 | lots of filler |
| Enemy data | 7, 8, boss logic | the logic must read the rolled weaknesses |
| Names | 34, 47 | final location names before a pack |
| Trackers | 47, 58 | `slot_data` rebuild (`take_slot_data`) and client/map tracking |
| Other mods | 10, 50 | the compatibility list |
