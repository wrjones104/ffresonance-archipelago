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
- **Never save a label read back as text before its string table has loaded.** It reads `<MISSING STRING TABLE ENTRY>`, and writing that back makes it the label (round 37).

**Threads:**
- **Never use `LoopAsync` or `ExecuteAsync`**: their callbacks run Lua on UE4SS's async thread while the game thread runs Lua in the same state. The game crashed at random, in a new place each time. Use `LoopInGameThreadWithDelay` and `ExecuteInGameThreadWithDelay` (round 29).
- **Crash reports:** `%LOCALAPPDATA%\FFRS\Saved\Crashes\*\CrashContext.runtime-xml` holds the stack as module offsets. `UE4SS.pdb` (next to `UE4SS.dll`) names the UE4SS frames, through `dbghelp`.

**Hooks and probes:**
- **Native functions called from Blueprints can be hooked** with `RegisterHook`, and a pre-hook can change their arguments (the title menu's `ExecuteEntry`).
- **Probes:**
  - `ffrap_snapshot` plus `tools/snapdiff.py`: what changed in the save.
  - `ffrap_inspect <class|path>`: an object's fields and functions.
  - `ffrap_find <text>`: classes, functions and fields by name.
  - `ffrap_layout <text>`: the panels around some on-screen text.
  - `ffrap_functions`: function signatures.
  - Off-line, before a probe: `data/game/*.tsv`, or `dotnet run --project tools/dump_game -- assets <path>` for any asset's properties, `structs <regex>` for any class's or struct's fields, and `raw <path>` for files such as the game's ini files.

**Shipping risky changes:**
- **A crash in the engine ends the game before Lua can log.** Ship risky UI work behind a test command, off by default, that logs each step before it runs.
- **A setting the mod saves by itself can come back as a "choice"** (the `feed 1` crash, round 19). A switch the user sets gets its own key, written only when the user sets it.

**Save and story facts:**
- The story counter is `Progress.Progress[1]` in Lua (element 0).
- `eventFlag` is 0-based in snapshots and 1-based in Lua (flag i is element i + 1).
- Features are switched on by event flags in `EnableFlagIdData` fields of the UI's data assets: 14 Equipment, 16 World Map, 18 Recovery, 19 Party, 24 Visions, 26 main menu, 34 fast travel. A new start that skips the story must set them (round 39).
- The prologue skip must run after story 1005 and the game's first autosave, or the opening movie's input lock survives the reload (round 9).

**Tooling:**
- **The Bash tool can collapse backslashes** in heredocs and inline Python (`\\n` arrives as a line break). Write edit scripts and test patches as files with the Write tool, then run them.
- When a test file's version string is replaced in bulk, comments that mention versions change too, so anchor edits on text that does not.
