# FFR Archipelago: notes for Claude

An Archipelago implementation for Final Fantasy Resonance (UE 5.6, game module `/Script/mucha`). Read this first; the README has the full history, round by round.

## The parts

- **The mod**, `FFRArchipelago/` (UE4SS Lua). Install path: `C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago`.
  - `Scripts/main.lua`: the loop, items, checks, sessions, title entry, skip, item feed, chest pop-up, console commands (`ffrap_*`).
  - `Scripts/game.lua`: every engine call. The only file to fix after a game patch.
  - `Scripts/bridge.lua`: the file bridge (`ap_in.txt` from the client, `ap_out.txt` to it). The line formats are in its header.
  - `Assets/`: the Archipelago logo.
- **The apworld and client**, `apworld/ff_resonance/` (`client.py`, `world.py`, `items.py`, `locations.py`, `options.py`, generated `data.py`). `python tools/build_apworld.py` builds `dist/ff_resonance.apworld`.
- **The game data dump**, `tools/dump_game/` (C#, CUE4Parse) and `tools/gen_from_dump.py`. They read the game's pak files off-line and write `data/game/*.tsv`. Use these tables, not FFR-Randomizer's lists, as the reference for items, units, maps, chests, field items, map exits and gimmicks. See "The game data dump" in the README.
- **Docs:**
  - `README.md`: setup, commands, bridge format, test results per round, the current round's test plan, open questions.
  - `IDEAS.md`: numbered ideas and findings, with what is known and what to find out.
  - `docs/progression.md`: the game's chapters and gates.
  - `docs/logic.md`: the progression logic design (in progress).
  - `docs/open_world.md`: the open world design (the main direction since round 30): the cleared state, gates, enemy scaling.
  - `docs/bosses.md`: boss fights as locations, Crystal Fragments, and how the story bosses come back.
  - `DISCLOSURE.md`: the AI disclosure. Keep it accurate.

## How we work

- **Rounds.** Claude builds and tests off-line, then writes a round test plan in the README. The user installs and plays, and sends `UE4SS.log` (`[FFRAP]` lines), screenshots or recordings. Claude records the results in the README as "Round N (mod x.y.z, ...)", fixes what they show, and plans the next round.
- **Versions.**
  - The mod's version is `VERSION` in `main.lua`; bump it with each change the user installs.
  - The world's version is `world_version` in `apworld/ff_resonance/archipelago.json`. When the world or client changes, bump it and rebuild the apworld. The user copies `dist/ff_resonance.apworld` into Archipelago's `custom_worlds` and generates a new seed.
  - Install steps in a test plan must say which of these to copy: `Scripts`, `Assets`, the apworld.
- **Commits:**
  - Commit each finished round on `main` without asking, and say so in the reply.
  - Never push; the user pushes. The user also commits from other machines, so when they mention a commit, `git fetch` and fast-forward first.
- **Tests:** `python tests/run_all.py` runs everything. Add or update a test with every change. See `tests/README.md` for the setup (a `.venv-tests` with `lupa`, and a scratch Archipelago copy from `tests/make_aptest.py`). Never add the world to the user's own Archipelago checkout.
- **Writing style:** plain, simple English in short sentences, for the README, IDEAS, the docs and code comments alike. Every finding goes in the docs with the round it came from.

## Lessons that cost a round each

**UI and widgets (UE4SS Lua):**
- **Never pass a font (`FSlateFontInfo`) or Slate colour (`FSlateColor`) struct to a setter:** it crashes the game. Write a widget's fields directly, before it goes on screen (round 20).
- **`FindFirstOf` can return a widget Blueprint's template**, which is never drawn. Take the instance that `IsVisible()` (round 22).
- **Enum numbers:**
  - Horizontal and vertical alignment: Fill 0, Left/Top 1, Center 2, Right/Bottom 3.
  - `ETextJustify`: Left 0, Center 1, Right 2.
  - `ESlateVisibility`: Visible 0, Collapsed 1, Hidden 2.
- **Text with icons is a `RichTextBlock`**, which is not a `TextBlock`. Search both.
- **Rows added to a game data table do not stay.** The game can load the table again, and the title screen has its own copy. Check for them every tick and add them again (the Options rows, round 57).
- **Never save a label read back as text before its string table has loaded.** It reads `<MISSING STRING TABLE ENTRY>`, and writing that back makes it the label (round 37).

**Threads:**
- **Never use `LoopAsync` or `ExecuteAsync`**: their callbacks run Lua on UE4SS's async thread while the game thread runs Lua in the same state. The game crashed at random, in a new place each time. Use `LoopInGameThreadWithDelay` and `ExecuteInGameThreadWithDelay` (round 29).
- **Crash reports:** `%LOCALAPPDATA%\FFRS\Saved\Crashes\*\CrashContext.runtime-xml` holds the stack as module offsets. `python tools/crashstack.py <folder>` names the UE4SS frames with `UE4SS.pdb`.
- **`pcall` does not catch an access violation.** A null object from an array crashes the game when asked for its name. Ask `IsValid` first (round 41).
- **Actors far from the player may not be loaded.** `FindAllOf` finds the tower's trigger only near it, and it comes back as the game made it (round 57). Act on it every tick, not once per map.
- **A map load frees the old map's objects, and a cached handle to one can crash even on `IsValid`.** `G.ForgetObjects` clears the caches in the `LoadMap` post hook (round 49). That was not enough: an object can be freed with no map load the mod sees (round 71, two crashes). **Never keep a game object from one tick to the next. Keep its path (`G.PathOf`) and find it again with `Find(path)`**, which uses `StaticFindObject` and never touches a freed object.

**Hooks and probes:**
- **Native functions called from Blueprints can be hooked** with `RegisterHook`, and a pre-hook can change their arguments (the title menu's `ExecuteEntry`). A post hook's return value replaces the function's (round 48).
- **Probes:**
  - `ffrap_snapshot` plus `tools/snapdiff.py`: what changed in the save.
  - `ffrap_inspect <class|path>`: an object's fields and functions.
  - `ffrap_find <text>`: classes, functions and fields by name.
  - `ffrap_layout <text>`: the panels around some on-screen text.
  - `ffrap_functions`: function signatures.
  - Off-line, before a probe: `data/game/*.tsv`, or `dotnet run --project tools/dump_game -- assets <path>` for any asset's properties (with `DUMP_BYTECODE=1`, each Blueprint function's code too), `structs <regex>` for any class's or struct's fields, and `raw <path>` for files such as the game's ini files.
  - What a pak mod changes: hard-link the game's `Paks` files into a scratch folder, copy the mod's `.pak`, `.utoc` and `.ucas` in beside them, dump its assets with `--game <that folder>`, and diff against a dump without it. The asset paths are readable as plain text in the mod's `.utoc` (round 55).

**Shipping risky changes:**
- **A crash in the engine ends the game before Lua can log.** Ship risky UI work behind a test command, off by default, that logs each step before it runs.
- **A setting the mod saves by itself can come back as a "choice"** (the `feed 1` crash, round 19). A switch the user sets gets its own key, written only when the user sets it.

**Save and story facts:**
- The story counter is `Progress.Progress[1]` in Lua (element 0).
- `eventFlag` is 0-based in snapshots and 1-based in Lua (flag i is element i + 1).
- Features are switched on by event flags in `EnableFlagIdData` fields of the UI's data assets: 14 Equipment, 16 World Map, 18 Recovery, 19 Party, 24 Visions, 26 main menu, 34 fast travel. A new start that skips the story must set them (round 39).
- More story flags an open start needs: 25 staggering, 28 Fina's summoning, 1160-1199 and 1217-1229 each tutorial's "seen" (round 45).
- A battle's MRP is `ap` in `DT_BattleGroup`, not a field on the enemy (round 47).
- A talk row with `encountGroupId` starts that battle group when the game's own chain reaches it, and the group's `battleFinishEventId` runs after a win. The row run after a win must be a Sequence row: a Blueprint row with no Blueprint leaves the screen black (round 49).
- An esper in the summon menu is an ability on both Finas, added by the event row's `AbilitySettings`; its flag (90 to 98) alone does nothing (round 46).
- A story `NoEntry` zone holds until its event's flag is on (the Earth Shrine's exit needs flag 102, round 44). `gimmicks.tsv` has the conditions.
- `CPP_VM_Party:AddUnit` does not set `JoinStatus`: a unit added only that way gains no EXP and gear on it does not count (round 44).
- The prologue skip must run after story 1005 and the game's first autosave, or the opening movie's input lock survives the reload (round 9).
- **A live field item's `m_UniqueId` can differ from the level's.** Tablet Shards in Felicitas read 0 and 1, while the save keeps them as 8 and 9 (round 63). In Zoldaad Castle a taken shard came back reading another shard's id (round 71). The mod takes a shiny's id from the level's shiny at the same place (`Scripts/field_items.lua`, round 72).
- **`IsOpenTreasureBox(map, uid)` answers from another map's row when the map has no row for that uid yet.** Four Earth Shrine chests were sent on arrival because shinies with the same uids were open elsewhere. Read the map's own rows, `Map.mapGimmick{map}.treasureBox.treasureBoxList` (`game.SaveOpenRows`), and judge a loaded chest by the chest (rounds 64 and 65).
- **The world map's id can come in before the town's pawn is gone.** A position read as the map changed was Grandport's own, and put the airship in Olderion. Check the pawn's class (`BP_MapUnit_Player_Field_C` on the world map) before trusting a world-map position (round 69).
- **On foot, the pawn's rotation reads 0 whichever way the player faces.** Every `ffrap_gate mark` cart went north. Take a direction from the player's movement (round 67).
- **A door's real destinations are in `mTransitionDataList`**, one per flag condition. Its `m_MapId` can be a leftover: every sanctum door on the world map says 10200 (round 63). `transitions.tsv` has them in `destinations`.

**Tooling:**
- **The Bash tool can collapse backslashes** in heredocs and inline Python (`\\n` arrives as a line break). Write edit scripts and test patches as files with the Write tool, then run them.
- **`python -m unittest worlds.ff_resonance.test` runs nothing of ours**: it loads only the package. Name the module, `worlds.ff_resonance.test.test_generation`. The runner printed ok for a long time while 12 tests were stale (round 59).
- **`game.lua`'s main chunk is at Lua's limit of 200 local variables** (round 67). A new top-level `local` fails to compile ("too many local variables"). Put new state in a table or a `G` field, and new helpers on `G`.
- When a test file's version string is replaced in bulk, comments that mention versions change too, so anchor edits on text that does not.
