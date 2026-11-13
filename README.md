# Final Fantasy Resonance for Archipelago (MVP)

Two parts:

- **FFRArchipelago**, a UE4SS Lua mod that does the in-game half.
  - **Receive:** it reads items from a file and grants them in order: bag items, gil, visions, party members and story flags. Each item is applied once per save, tracked by its Archipelago index and by how many items each save slot holds.
  - **Send:** it reports opened chests, picked-up shinies (shining spots) and changes to the story counter.
- **`apworld/ff_resonance`**, the Archipelago world and client.
  - The world generates seeds: chests with consumables, equipment or gil are locations, and shinies are an option. Party members, visions and key items can go in the pool (world 0.3.0), with no logic yet. An open world mode is being designed ([docs/open_world.md](docs/open_world.md)).
  - The client connects the mod to a server through the bridge files.

`tools/fake_ap.py` still plays the server's part for testing the mod alone.

AI use: this project is built with Claude Code. [DISCLOSURE.md](DISCLOSURE.md) says what was AI-written, what I did, and how much has been reviewed.

## Playing the MVP

The world is tested off-line: Archipelago's general tests pass with it, its own tests pass, and a client end-to-end run against a local server passes, with a script standing in for the game. Round 5 played a full seed in the real game, up to the goal and a release (see [docs/playtesting.md](docs/playtesting.md)).

**What the mod needs:**
- **UE4SS**, the only thing it needs to run. ConsoleEnablerMod and BPModLoaderMod come with UE4SS. The console is only for the `ffrap_*` commands.
- **ModSettings** (a Blueprint mod in `Content/Paks/LogicMods`, from the same modding tools as FFRSLib) is optional. In the field, messages ("Received ...", "Sent ...", "Archipelago is paused", "Prologue skipped") go to the mod's own item feed at the bottom right of the HUD (since 0.10.0, on by default). ModSettings' Toast panel takes them off the field (the title screen), when the feed has not been able to show anything for 10 seconds since the game started, and with `ffrap_feed off`. Without ModSettings those few only go to `UE4SS.log`.
- **FFRS_QoL and our settings (round 60).** Both write the EXP, gil and MRP rates and the encounter fields. Ours are written back within 0.1 s (the rates) and 5 s (encounters), so ours are the ones in use. Keep FFRS_QoL's encounter rate at 1: a rate it wrote first is taken as the game's own.
- **Map markers (chests, shinies, Tablet Shards) are left to other mods.** FFRS_QoL with the TreasureMinimap paks beside it works with this mod (round 59): the paks draw the markers, and FFRS_QoL takes a marker away once its spot is found.
- **FFRSLib, FFRS_QoL, FFRBestiary and FFRRandomizer are not needed.** Their code is where the game calls come from (see "Where the game calls come from"), but this mod calls the game directly. FFRRandomizer should stay disabled (IDEAS.md, idea 10).

1. **Mod.** Copy `FFRArchipelago/Scripts` and `FFRArchipelago/Assets` over the installed mod (0.18.0). Delete the old `ap_in.txt`, `ap_out.txt` and `ap_state.txt`, and keep `seen.tsv`. Keep FFRRandomizer disabled.
2. **World.** Run `python tools/build_apworld.py`, then copy `dist/ff_resonance.apworld` into your Archipelago `custom_worlds` folder. Or, from source, copy `apworld/ff_resonance` into `worlds/`.
3. **Seed.**
   - Copy `apworld/Final Fantasy Resonance.yaml` into Archipelago's `Players` folder and set a name.
   - For a short test seed, use `goal: tablet_shards` with a low `tablet_shards_required`, or `goal: final_boss` with low `final_boss_characters`, `final_boss_visions` and `final_boss_fragments`.
   - Run `Generate.py`, then host the seed (`MultiServer.py <zip>`, or the website).
4. **Play.**
   - In the Launcher, open **Final Fantasy Resonance Client** and connect.
   - The client writes `seed` and `cfg blank 1` into `ap_in.txt`, and the mod starts a fresh session.
   - Start a **new game**: the mod links it to the seed, and every Archipelago chest gives 1 gil from then on. To play an existing save instead, load it and type `/bind` in the client.
   - While any other save is loaded, the mod pauses: it grants nothing, reports nothing, and the chests are vanilla.
   - Open a chest: its real item comes from the server, with a "Received ..." message.
5. **Goal.** When the story counter reaches the goal, the client sends the goal status.

What to watch for:
- Items arriving: "Received ..." toasts, with the items in the bag.
- Chests giving 1 gil.
- Chests that hold key items still giving them.
- The goal triggering.
- Anything in `UE4SS.log` marked `[FFRAP]`.

The client log is in Archipelago's `logs` folder.

## Where the game calls come from

The engine calls are already measured by mods installed in this game folder:

| Need | Call | Found in |
|---|---|---|
| Grant a bag item | `CPP_BFL_SaveDataInventory:AddInventory(id, n)`, `FindInventory(id)` | FFRSLib (`ffrs_grant_item`) |
| Unlock a vision | grow `saveData.visionList`, set `ID`, copy `synchroPoints` keys, then `AddInventory(id, 1)` | FFRSLib (`ffrs_vision_unlock`) |
| Add a party member | `CPP_VM_Party:AddUnit(id)`, `IsJoinedUnit(id)` | FFRSLib (`ffrs_party_add`) |
| Story flags | `CPP_BFL_SaveDataProgress:SetFlag(i, bool)`, `GetFlag(i)` | FFRSLib (`ffrs_flag`) |
| Story counter | `saveData.Progress.Progress[1]` (1020 to 8050; thousands digit = chapter) | FFRSLib (`ffrs_story`) |
| Save data | `CPP_MuchaSaveDataManager.m_pGameSaveData` | FFRSLib |
| Opened chests | `CPP_BFL_SaveDataMap:IsOpenTreasureBox(mapId, uid)`; live `CPP_MapGimmick_TreasureBox.m_Id` / `m_IsOpen` | FFRS_QoL, FFRRandomizer probe |
| Shinies | `BP_MapGimmick_FieldItem*` actors with `m_UniqueId`; looted state through the same `IsOpenTreasureBox` | FFRS_QoL markers (based on ZArkadia's Item and Chest Markers, Nexus mod 25) |
| Chest table patching | `CDT_MapGimmickTreasureBox` and its parent tables | FFRRandomizer (`tableFamily`) |
| Which save is loaded | save data object name; `Player.SavedDateTime.Ticks`; `GameSaveDataSummaryMap` slot summaries with the same ticks | FFRBestiary (`game.slotForTicks`) |
| On-screen text | `BP_ModSettings:Toast(msg, seconds, hue, worldContext)` | FFRSLib |

FFRSLib is FFR Modding Tools' in-game library by Kanaruu. This mod is separate code that calls the same functions, and it needs neither mod to run. The one exception is on-screen text, which needs the ModSettings panel. Before you publish anything, check the Modding Tools' and ZArkadia's permissions on Nexus and credit the work properly.

## Files

```
FFRArchipelago/            -> copy to ...\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago
  enabled.txt
  Scripts/main.lua         loop, item queue, checks, console commands
  Scripts/game.lua         every engine call (the only file to fix after a game patch)
  Scripts/bridge.lua       the file link to the client
apworld/ff_resonance/      the Archipelago world and client (Final Fantasy Resonance)
  data.py                  generated by tools/gen_apworld_data.py; do not edit
  client.py                the Archipelago client (bridge files <-> server)
apworld/Final Fantasy Resonance.yaml   example player options
tools/fake_ap.py           fake Archipelago server for testing the mod alone
tools/gen_apworld_data.py  data/*.tsv -> apworld/ff_resonance/data.py
tools/build_apworld.py     apworld/ff_resonance -> dist/ff_resonance.apworld
tools/snapdiff.py          compares two ffrap_snapshot files
tools/dump_game/           C# (CUE4Parse): the game's pak files -> dump/ (JSON; git ignores it)
tools/gen_from_dump.py     dump/ -> data/game/*.tsv, and --check against data/*.tsv
data/game/                 tables made from the game's own files (see "The game data dump");
                           tools/gen_apworld_data.py builds the world from them
data/chests.tsv            every chest table row, exported in game (ffrap_export): a record from play
data/shinies.tsv           shinies seen in game (the mod's seen.tsv): marks a shiny "seen"
docs/progression.md        the game's progression, chapter by chapter
docs/logic.md              the progression logic design (draft)
docs/open_world.md         open-world mode design (continent locks, enemy scaling)
docs/playtesting.md        playtest round logs (Rounds 1-32) and active test plans
tests/                     every test; run them all with python tests/run_all.py (tests/README.md)
CLAUDE.md                  how we work, for Claude sessions: conventions, lessons, where things live
FFRArchipelago/Assets/     the Archipelago logo for the title screen
```

After `data/game/*.tsv` or `data/shinies.tsv` changes, run `python tools/gen_apworld_data.py` and commit the regenerated `data.py`.

Ideas and ongoing research (Tablet Shards, trap items, NPC gifts, custom gates) are in [IDEAS.md](IDEAS.md). Open-world mode is designed in [docs/open_world.md](docs/open_world.md), and progression logic in [docs/logic.md](docs/logic.md).

## The game data dump

`tools/dump_game` reads the game's pak files directly, without starting the game, and writes the data as JSON to `dump/`. `tools/gen_from_dump.py` turns that into tables in `data/game/`. These tables are the reference for items, characters, maps and placements, and the world is built from them (since world 0.2.0). The other files in `data/` are records from play.

```
dotnet run --project tools/dump_game -- all
python tools/gen_from_dump.py --check
```

- **Needs:** the .NET 10 SDK, a `Mappings.usmap` and the Oodle DLL. The tool takes the newest usmap from FFR Modding Tools (`%LOCALAPPDATA%\FFR Modding Tools\workspace\mappings`) or from `FFRS\Binaries\Win64\Mappings.usmap`, and the Oodle DLL from FFR Modding Tools' `workspace\tools\oodle`. `--usmap`, `--oodle`, `--game` and `--out` change these paths.
- **Only a newer .NET installed** (round 63: .NET 11): set `DOTNET_ROLL_FORWARD=Major` for the run.
- **After a game patch:** make a new usmap first. Turn on UE4SS's `UsmapDumperMod`, start the game and wait 30 seconds at the title screen. Then turn the mod off again.
- **Only the shipped game.** It reads the base paks, not `~mods` or `LogicMods`. The pak files are not encrypted.
- **`dump/` stays out of git.** It is the game's own data, about 110 MB. Commit only the tables in `data/game/`.
- **Commands:** `all`, `files`, `enums`, `text`, `tables [filter]`, `maps [filter] [--classes regex]`, `assets <path prefix>`. In Git Bash, set `MSYS_NO_PATHCONV=1` before passing a filter that starts with `/`.

| File in `data/game/` | What it is |
|---|---|
| `items.tsv` | All 589 items in the six item tables: id, table, type, equipment detail, name, prices |
| `units.tsv` | All 643 units: 11 playable (the 8 party members, and the guests Ignis, Alluvion and Charlotte), 26 visions, 10 summons (category `Beast`), enemies and bosses |
| `maps.tsv` | All 186 maps: id, key (`01Gra_40`), English name, island, group |
| `chests.tsv` | Every treasure box table row, in the columns of `data/chests.tsv`, plus `boxes`: the placed boxes that are its box (`level:uid`). A row with none is not a location |
| `treasure_actors.tsv` | Every treasure box placed on a map, with its `m_Id`, level and position |
| `field_items.tsv` | Every field item placed on a map, in the columns of `data/shinies.tsv`, plus events, level and position |
| `transitions.tsv` | Every map exit: from map, to map and point, and its condition. This is the map graph |
| `gimmicks.tsv` | Blockers, no-entry zones, doors, event triggers, save points and airship landing points, with their conditions |
| `shops.tsv` | Every shop's stock, one row per item |

`Scripts/field_items.lua` is generated by `tools/gen_apworld_data.py`: every shiny's level id and place, so the mod can tell a live shiny's real id (round 72). At run time the mod writes these files into its own folder: `ap_out.txt`, `ap_state.txt`, `ap_status.txt`, `ffrap_dump.txt`, `chests.tsv`, `seen.tsv` and (from 0.53.0, by `ffrap_gate mark`) `crossings.txt`. The fake server writes `ap_in.txt`.

## Console commands

| Command | What it does |
|---|---|
| `ffrap_status` | What the mod sees right now |
| `ffrap_grant <kind> <id> [n]` | Grant directly, without the bridge: `item`, `gil`, `vision`, `unit`, `flag` |
| `ffrap_dump [rows]` | Chest and shiny discovery dump to `ffrap_dump.txt` |
| `ffrap_export` | Every chest table row to `chests.tsv` |
| `ffrap_blank [on\|off]` | Chests that are Archipelago locations give 1 gil instead of their vanilla reward. Chests with items at id 13000 and up (visions, key items) keep theirs. It is remembered across restarts. The client turns it on. |
| `ffrap_sync` | Report every location in `seen.tsv` that the save says is looted, from anywhere in the game (re-sync). Only in the session's save. |
| `ffrap_snapshot [name]` | Every field of the loaded save to `snap_<name>.tsv`. Compare two with `python tools/snapdiff.py snap_a.tsv snap_b.tsv` (IDEAS.md, idea 2). |
| `ffrap_functions [class ...]` | The functions of game classes, with their parameters, to `functions.txt`. With no class it lists the save-data, debug and new-game classes (IDEAS.md, idea 2). |
| `ffrap_skip [slot] [force]` | Skip the prologue on a new game, once you can move Fina (story 1005). Without a slot it only changes the loaded save; with one it applies the skip again, saves there and reloads. `force` skips before story 1005 anyway, which leaves the opening's input lock behind (round 9): a probe for round 36. Testing only for now (IDEAS.md, idea 2). |
| `ffrap_input [fix]` | Probe for the opening's input lock: logs the player controller's input switches (move and look input ignored) and the game's input manager (`IsEnableInput`, the input mode, the stack of mapping contexts). `fix` calls the manager's `EnableInput` and `ReregistrationCurrentMappingContext`, then the engine's resets (`ResetIgnoreInputFlags`, `EnableInput`, `SetInputMode_GameOnly`), logging each step before it runs. |
| `ffrap_openstart [on\|off\|dock\|air\|event\|at x y z\|now [slot]]` | Test switch, off by default: the prologue skip of a new game goes to the open world start (docs/open_world.md) in place of the Earth Shrine. It writes story 8000 and an arrival, saves and reloads. The arrival, for this run: `dock` (the default) is the Crystal Tower's dock (map 3280); `air` is the world map, riding the airship beside the tower; `event` writes story 7090 at the dock instead, so the tower's two events play and set 8000 (round 36: they write nothing else). Kept in `ap_state.txt` as `openstart`. `at x y z` moves the arrival point until the game closes. `now [slot]` writes the same start into the loaded save (one that already had the skip), saves it to its slot (or `slot`) and reloads, with no new game. With nothing after it, says whether it is on and where it arrives. |
| `ffrap_inspect <class or path> [label]` | One object's fields and functions to `inspect_<name>.tsv` (`inspect_<name>_<label>.tsv` with a label, to keep two states apart): a class name gives its first live instance (else its default object), and a path gives that object (IDEAS.md, idea 6). |
| `ffrap_find <text>` | Every game class or struct, native or Blueprint, whose name or one of its functions or fields holds the text, to `find_<text>.txt`. Walks every object, so the game pauses for a moment. Run it in game: at the title screen it crashed the game once (round 11). |
| `ffrap_title [list\|add]` | `list` logs the entries the title menu shows. `add` adds the Archipelago entry again by hand: the mod adds it at start-up and keeps it there. |
| `ffrap_notice [text]` | Experimental: tries to show the text with the game's quest-notice banner, in the field. |
| `ffrap_logo` | Puts the Archipelago logo at the end of the mod's line on the title screen. The mod does this by itself; the command is for trying it again by hand. |
| `ffrap_layout <text>` | Logs the chain of panels holding the on-screen text that holds `<text>`, up to the screen's root layout. For finding where new HUD elements can go. |
| `ffrap_feed [on\|off\|test [plain]]` | The item feed at the bottom right of the field HUD: on by default; off sends messages to ModSettings' Toast. Kept in `ap_state.txt` as `itemfeed`. `test` shows three sample lines. Every step the feed takes is logged before it runs (`feed step: ...`), so a crash's last line names the call. `test plain` leaves out the styling. `check` logs what the engine says about the feed: the box's and each line's size, visibility and font. |
| `ffrap_bind` | Link the loaded save to the client's session, in place of any earlier one. The same as `/bind` in the client. |
| `ffrap_reset` | Set the loaded save's applied-item count to 0. Re-grants everything to it! |
| `ffrap_scale <level\|low high\|party [range]\|off> [at %] [hp %] [attack %] [magic %] [power %] [boss] [follow]` | Open world probe (docs/open_world.md, section 5): rewrites every enemy's level and stats in `DT_UnitParameter`. `30` puts every enemy at level 30. `10 20` pulls each enemy's own level into 10 to 20. `party 5` pulls it into 80% of the party's average level ± 5; `party` alone is range 2. `off` restores the rows as they were before (their latest values, which another mod may have written: round 33). Options: `at 70` centres the party band on 70% of the party's level (default 80); `hp 70` sets enemy HP to 70%; `attack 60` and `magic 80` set enemy Attack (physical) and Intelligence (magic); `power 80` sets both; `boss` changes bosses too; `follow` moves the party band again each time the party's level changes (on the field only). Each run writes the changed enemies' stats to `scale.txt`. `ffrap_scale` alone says what is in force and checks that the table still holds it; `ffrap_scale show <id or name>` logs that enemy's rows in every unit table loaded. While a rescale is in force, the mod checks the table every 10 seconds on the field and writes it again if it changed (round 33: the FFR Randomizer mod kept writing it). Not saved: a restart undoes it. |
| `ffrap_noland <list\|here\|show [width]\|hide\|lock <box>\|unlock <box>\|refresh\|spawn [half] [top]\|move [half]\|channel <n> <0-2>\|cond <text>\|off>` | Open world probe (docs/open_world.md, section 4): the airship's no-landing boxes. `list` writes every box on the map to `noland.txt`. `here` logs the boxes under you, and what a trace straight down meets: the no-landing boxes whose collision is on, then the ground's height. `show` draws the boxes' outlines (if the game draws them), `hide` hides them. `lock mysidia` makes the game's own Mysidia box block landing (its condition always holds); `unlock` makes it never block; also `gronoa` and `pharm`. Every box with that story condition is written. `here`, `lock` and `spawn` also log each box's collision. `refresh` switches the collision of the boxes we changed on or off to match their condition, to try to apply a change without landing (round 34 probe). `spawn 2000` makes a new box under you, 2000 each way and 1400 tall, its top at z 1093 (the Mysidia box's); `spawn 2000 1800` puts its top at 1800, for high ground. `channel 3 0` sets the spawned boxes' response to collision channel 3 to ignore (1 overlap, 2 block): a probe for the airship's shadow, which a box hides. `move 2000` moves the game's Mysidia box under you and empties its condition. `cond <text>` sets the condition of the spawned and moved boxes (one word). `off` undoes all of it. Each step is logged first. Not saved. |
| `ffrap_story [value]` | Open world probe: sets the loaded save's story counter to any value (FFRSLib's `ffrs_story_set` stops at 8050; the ending sets 9000). Only the counter, no flags. Save and reload to apply. Use it on a save that is not linked to a seed, or the client sees the story move. |
| `ffrap_airship [condition\|off]` | Open world probe: shows or rewrites the airship's spawn condition (`DT_MapAirShip`, shipped `{progress:0}>=4250`). One word, no spaces. `off` restores it. Not saved. From mod 0.54.1, `home` parks the airship of a seed that started on foot at its start point, where it lands at the next map change. |
| `ffrap_bossfight <battle group> [quiet]\|sword\|off` | Test (round 49, IDEAS.md idea 25): the closed chests near you become traps for that battle group, the Chamber of Arms sword pedestal starts it too, and a win is logged. The win plays the sword fight's victory scene, or nothing with `quiet`. `sword` gives the Ancient Greatsword the pedestal needs. `off` undoes it. `watch [class ...]` hooks the talk event and encounter classes and logs their calls; `watch off` stops the logging. |
| `ffrap_set [exp\|gil\|mrp\|encounterrate <number>] [encounters\|scaling <on\|off>] [strength casual\|normal\|expert] [reset]` | The player's settings (round 50): EXP, gil and MRP rates, random encounters and their rate, the seed's enemy scaling and its strength (round 56; each one step harder since round 63). Kept in `settings.txt`. They apply to any save (round 56 kept them to the seed's save; round 57 undid that). Our mod owns these: turn FFRS_QoL's multipliers and encounter settings off, or the two undo each other. |
| `ffrap_menu add\|dump` | Our settings as rows at the end of the Options screen's Gameplay tab, put back by themselves whenever the game's table has lost them, at the title too, from mod 0.43.0 (`add` does it by hand). A value set there wins over `ffrap_set`. `dump` logs the option save's entries and the screen's pending changes. |
| `ffrap_gate <subcommand>` | Experimental gate and custom key-item probe (IDEAS.md, idea 16): `spawn [combo\|box\|rock\|pot\|gate\|world] [dist] [scale]`, `item [id] [count]`, `require <item\|unit\|flag\|off> [id] [count]`, `lock`, `unlock`, `clear`, `status`. From mod 0.53.0, the walking crossings between continents: `mark <continent> <continent> [scale] [dist]` puts a blocker `dist` (default 150) ahead of you at `scale` (default 3) and saves it in `crossings.txt`. It holds while either continent is locked. `unmark` removes the nearest one within 1500, and `crossings` lists them all in the log. From 0.53.1 the mod has the two crossings built in, and `crossings.txt` replaces them when present. A mark goes the way you last walked, at scale 2 by default. `move <dx> <dy> [dz]` (+x is north), `turn [degrees]` and `size <scale>` change the nearest crossing where it stands. |

## Bridge format

Both files are append-only and tab-separated, one record per line.

`ap_in.txt` (client to game):
```
seed   <seed name>:<team>:<slot>                  first line; a new value starts the mod's state over
cfg    blank  <0|1>                               chest blanking
item   <index>  <kind>  <id>  <count>  <label>    kind: item | gil | vision | unit | flag | token (nothing in game)
scout  <base64(key \t item \t player \t flags \t own)>  what a location holds, for the chest pop-up
msg    <text>                                     shown on screen
sync                                              report everything the save says is looted
bind                                              link the loaded save to this session (0.5.0)
```

**Which save a session belongs to (0.5.0).** The mod links each session to one save. A new game started during the session, never saved yet, is linked at once. An existing save is linked by `bind`. The session then remembers every slot the linked game is saved to (`slots` in `ap_state.txt`), and forgets a slot when another game is saved over it. While a save that is not linked is loaded, the mod grants nothing, writes no `check` or `story` lines and turns chest blanking off. Older mods ignore the `bind` line, so the protocol stays 1.

`ap_out.txt` (game to client):
```
hello    <version>  <protocol>
seed     <session>                  the lines after it belong to that session
check    chest:<row mapId>:<row ID>     (a rowless chest with a reward: chest:<map>:u<m_UniqueId>)
check    shiny:<map>:<m_UniqueId>
story    <counter>
won      <battle group>             9056: the last battle, Rain against Sol (mod 0.45.0)
applied  <index>  <ok|fail>  <detail>
```

The client only counts `check`, `story` and `won` lines after a `seed` line for its own session. A new session empties `ap_out.txt`, so checks from another seed, or from before connecting, are never sent.

`<map>` is always the map as the save keys it, `CPP_MapManager:GetSameMapId()`.

## seen.tsv

The mod appends one line the first time it sees each chest or shiny, across sessions. This builds our own location list and records the key the save knows each location by.

```
kind  map  uid  row  item  count  money  visible-condition
```

- `kind`: `chest` (has a table row), `xchest` (no row), `shiny`, or `spot` (a shiny-class story or quest point with no reward).
- `map` and `uid` are the save's key: `IsOpenTreasureBox(map, uid)` answers for that location from anywhere in the game.
- `row` is the chest table row (`mapId:ID`). For shinies this column holds the Blueprint class instead.

## Playtesting and test plans

In-game playtesting results (Rounds 1-71) and the current test plan (Round 72) are documented in [docs/playtesting.md](docs/playtesting.md).
Automated regression tests are documented in [tests/README.md](tests/README.md).

## Project status and open questions

The MVP is functional: the mod receives items (bag items, gil, visions, party members, flags), reports location checks (chests, shinies), supports prologue skipping and session-bound saves, and communicates with the Archipelago client.

Remaining technical questions:
- **Shiny blanking:** World-map shinies currently grant both their native pickup and the Archipelago item. Blanking requires patching actor reward fields on spawn.
- **Grant timing:** Verifying safe grant windows during cutscenes and scripted boss transitions.
- **Story reward suppression:** Suppressing native story rewards when those items are granted via Archipelago in open-world mode.

## Roadmap

Active development is focused on Open-World Mode and Progression Logic:
- **Open-world mode:** Starting at story 7090/8000 with the airship available and the Crystal Tower accessible. Details in [docs/open_world.md](docs/open_world.md).
- **Continent gating:** Locking continent access via BP_MapNonLandingArea_C landing restriction boxes until regional unlock items are acquired.
- **Dynamic enemy scaling:** Adjusting enemy level and stat curves in DT_UnitParameter relative to party level.
- **Progression logic:** Building region graphs and access rules from game data transitions. Details in [docs/logic.md](docs/logic.md).
