# AI disclosure

> **Draft.** Keep this file up to date as the project changes. Before you share the project, finish the review table and remove this note. The Archipelago Discord requires a pinned disclosure on every implementation it hosts.

## Was AI used?

Yes, a lot.

## Which tools?

Claude Code (Anthropic), using Claude Opus models, in the Claude desktop app.

## What was it used for?

**Written by Claude:**
- The UE4SS Lua mod: `FFRArchipelago/Scripts/main.lua`, `game.lua` and `bridge.lua`.
- The Archipelago world and client: everything in `apworld/ff_resonance`, including its tests and docs.
- The tools in `tools/`: the fake server, the data generator, the apworld builder and the item-name importer.
- Most of the text in `README.md`, `IDEAS.md` and `docs/progression.md`, with notes from me reworded and checked against the game data.
- Research: reading the installed mods (FFR Modding Tools / FFRSLib, FFRS_QoL) and FFR-Randomizer to find out which engine calls and data tables to use.

**Done by me:**
- The project's direction and design: a separate project, the game mod as a proof of concept before the apworld, the location types, and the ideas in `IDEAS.md` (Tablet Shards, skipping the prologue, an open-world mode, vehicle gates).
- The game knowledge in `docs/progression.md`.
- All in-game testing. Each test round's logs, dumps and `seen.tsv` files came from my play sessions. They are how we found out how the game really behaves, and several bugs were found this way that the off-line tests had missed.
- The game data in `data/chests.tsv` and `data/shinies.tsv`, which I exported or recorded in game with the mod's commands.
- Deciding what to keep, and approving each commit.

## How extensively?

Claude wrote nearly all of the code and most of the documentation. My part was design, direction, testing and review.

## How much human review?

Every change was tested in the real game, apart from the items marked "not tested in game yet" in `README.md`. Code review:

| Part | Files | Reviewed by me |
|---|---|---|
| Game mod | `FFRArchipelago/Scripts/*.lua` | not yet |
| World: items, locations, options | `items.py`, `locations.py`, `options.py`, `world.py` | not yet |
| Client and bridge | `client.py`, `components.py` | not yet |
| Generated data | `data.py`, `tools/gen_apworld_data.py` | not yet |
| Tests | `test/` | not yet |
| Docs | `docs/`, `README.md` | not yet |

## Credits

- **FFR-Randomizer** by LordMikoda (MIT): the item names in `data/item_names.tsv` and `data.py`. See `data/LICENSE-FFR-Randomizer.txt`.
- **FFR Modding Tools (FFRSLib)** by Kanaruu, and **FFRS_QoL**: the engine calls this mod uses. No code is copied, but the calls follow theirs. Their permissions are still to be checked; see `README.md`.
- **FFRBestiary**: how the mod tells which save slot is loaded (0.5.0).
- **Item and Chest Markers** by ZArkadia (Nexus mod 25): FFRS_QoL's shiny markers are based on it.
- **The Archipelago logo** (`FFRArchipelago/Assets/archipelago_logo.png`) is the Archipelago project's, used with credit in an unpaid project.
