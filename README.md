# Final Fantasy Resonance for Archipelago

An Archipelago multiworld randomizer for *Final Fantasy Resonance* (Steam, Windows). It consists of an in-game UE4SS Lua mod (`FFRArchipelago`) and an Archipelago world and client (`ff_resonance`).

This project is in active playtesting. If you are helping test a seed, see the [Playtester guide](docs/playtester_guide.md) for what to look out for and how to report feedback.

## What it does

- Choosing **New Game (Archipelago)** on the title screen skips the main story and drops you directly into an open world on your starting continent with your chosen starting party.
- Consumable, equipment, gil, and magicite chests, world-map shinies, Tablet Shard shinies, Sanctum crystals, story and optional bosses, and airship radar treasures are shuffled into the multiworld. Continent unlocks, the Airship, the Chocobo, party members, visions, key items, and Progressive Radars can all be placed in the item pool.
- Locked continents block airship landings, bridges, and ferry routes until you receive their Unlock item.
- Two goals are supported: `final_boss` (collect the required party members, visions, and Crystal Fragments from story bosses to unseal the top of the Crystal Tower and defeat the final boss) and `tablet_shards` (receive the required number of Tablet Shards).
- Enemies and bosses scale to your party level by default. At the bottom of **Options > Gameplay**, you can adjust EXP, Gil, and MRP multipliers, random encounters, encounter rate, enemy scaling, and scaling strength (`Casual`, `Normal`, `Expert`).
- Each Archipelago session links to the save created by **New Game (Archipelago)** and any slot you save it to. Plain **New Game** and other vanilla saves stay untouched; while another save is loaded, the mod pauses automatically.
- Universal Tracker is supported for tracking reachable locations and logic.

Current limitations:
- World-map shinies still grant their normal game pickup alongside sending their Archipelago check.
- Chests that hold key items or visions in the base game are not shuffled locations and still give their normal contents.

## Requirements

- *Final Fantasy Resonance* (Steam, Windows)
- [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) (Unreal Engine 5.6 build), installed in `FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\`
- [Archipelago](https://archipelago.gg/) 0.6.7 or later
- Optional: FFR Modding Tools' `ModSettings` Blueprint mod (`Content/Paks/LogicMods`) for fallback toast messages on the title screen. In-game notifications appear in the mod's own bottom-right HUD feed without `ModSettings`.

### Mod compatibility

Disable `FFRRandomizer` if you have it installed (delete or rename its `enabled.txt`, or disable it in `mods.txt`), because it overwrites the same chest and enemy tables.

`FFRSLib`, `FFRS_QoL`, and `FFRBestiary` are not needed. If you keep `FFRS_QoL` installed alongside `TreasureMinimap` for map markers, leave `FFRS_QoL`'s encounter rate at `1` and disable its EXP, Gil, MRP, and encounter overrides so it does not fight with `FFRArchipelago`.

## Installation

### 1. Install UE4SS

Skip this step if you already have a UE 5.6 build of UE4SS installed (for example, through FFR Modding Tools or another FFRS mod).

1. Download a UE4SS build that supports Unreal Engine 5.6 from [RE-UE4SS releases](https://github.com/UE4SS-RE/RE-UE4SS/releases) (use the experimental / `v3.0.1 Beta` or newer release archive, not the older non-beta `v3.0.1`).
2. Extract the archive into your game's `Win64` folder:
   `...\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\`
   When extracted correctly, `dwmapi.dll` and the `ue4ss` folder sit right next to `FFRS-Win64-Shipping.exe`.

### 2. Install the game mod

1. Copy the `FFRArchipelago` folder (containing `enabled.txt`, `Scripts/`, and `Assets/`) into your game's UE4SS Mods directory:
   `...\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago`
2. If you are updating from an older version of the mod, delete `ap_in.txt`, `ap_out.txt`, and `ap_state.txt` from that folder before starting a new seed. Keep `seen.tsv` if present.

### 3. Install the Archipelago world

- Copy `dist/ff_resonance.apworld` into your Archipelago `custom_worlds` folder.
- If you are running from source instead of the packaged `.apworld`, run `python tools/build_apworld.py` to build `dist/ff_resonance.apworld`, or copy `apworld/ff_resonance` into Archipelago's `worlds/` folder.

## Generating and playing a seed

1. Open the Archipelago Launcher and click **Generate Template Options** to create a YAML for *Final Fantasy Resonance*, or copy [apworld/Final Fantasy Resonance.yaml](apworld/Final%20Fantasy%20Resonance.yaml) into Archipelago's `Players` folder and customize your options.
2. Generate the seed and host it locally (`MultiServer.py`) or on archipelago.gg as usual.
3. Launch *Final Fantasy Resonance*. On the title screen, you should see `FFRArchipelago <version>` above the game's version and a **New Game (Archipelago)** option in the menu.
4. Open the Archipelago Launcher, start **Final Fantasy Resonance Client**, and connect to your server and slot.
   - By default, the client looks for the mod in `C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago`. If your game is installed somewhere else, set `ff_resonance_options.mod_folder` in Archipelago's `host.yaml` or run `/modfolder <path>` in the client.
5. Select **New Game (Archipelago)** in game. The mod links your new save to the active session, skips the prologue, and starts you on your starting continent.
   - To link an existing save manually instead, load it and run `/bind` in the client.
   - If you ever reconnect or suspect a missed check, run `/resync` in the client.

## More information

- [Playtester guide](docs/playtester_guide.md): what to test and how to report feedback.
- [Developer reference](docs/dev.md): repository layout, bridge protocol, data dump tools, and UE4SS console commands.
- [DISCLOSURE.md](DISCLOSURE.md): AI usage disclosure and third-party credits.
