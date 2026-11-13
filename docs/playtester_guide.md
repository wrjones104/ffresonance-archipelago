# Playtester guide

Thanks for helping test the Final Fantasy Resonance Archipelago randomizer. This is an early playtest of the open-world mode, so we are looking for broad feedback on how a full run feels, where logic or progression breaks down, and whether anything crashes.

## What to expect in this build

Selecting **New Game (Archipelago)** on the title screen skips the main story and drops you into an open-world start on your starting continent with your starting party. Continents are locked by airship landing restrictions, bridge blockers, and ferry routes until you receive their Unlock items.

Locations in the pool include treasure chests, world-map shinies, Tablet Shard shinies, Sanctum crystals, story and cave bosses, and airship radar treasures. Party members, visions, key items, the Chocobo, the Airship, and Progressive Radars can all be shuffled depending on your YAML options.

Two goals are supported:
- `final_boss`: collect the required party members, visions, and Crystal Fragments (dropped by story bosses) to open the top of the Crystal Tower and defeat the final boss.
- `tablet_shards`: receive the required number of Tablet Shards.

Universal Tracker is supported if you want to check what is currently in logic while playing.

Known work in progress:
- Quests, NPCs and some pickup spots that hold key items or visions in the base game are not shuffled locations and still give their normal contents. You may get key items or visions that you have already received from the multiworld.
- Espers are all rewarded in their vanilla manner (with the exception of Siren, which is granted from the start).
- Chamber of Arms and the Arena are not touched yet.

## Before you start

- Most other mods have not been tested alongside this mod - use other mods at your own risk.
- If you have it, nake sure `FFRRandomizer` is disabled. If you use `FFRS_QoL` for map markers, leave its encounter rate at `1` and turn off its EXP, Gil, MRP, and encounter overrides so they do not conflict with `FFRArchipelago`.
- Connect the **Final Fantasy Resonance Client** to the server before starting a new game, and start the run from **New Game (Archipelago)** on the title screen (not the regular **New Game**).
- You can change EXP, Gil, MRP, random encounters, encounter rate, enemy scaling, and scaling strength (`Casual`, `Normal`, `Expert`) at any time in **Options > Gameplay** at the bottom of the list. Note that `AP: Scaling strength` stacks with the game's own difficulty setting.

Feel free to play with whatever YAML settings look fun to you. Testing different combinations (`final_boss` vs. `tablet_shards`, starting with or without the Airship or Chocobo, different starting continents and party sizes, solo or multiworld) helps catch issues we have not hit yet.

## What to look out for and report

### 1. Enemy and boss scaling

Enemy levels and stats scale to your party level by default, with bosses scaling higher than regular encounters. We want to know how combat feels across the whole curve of a run:
- Which **AP: Scaling strength** setting (`Casual`, `Normal`, `Expert`) and in-game difficulty did you use?
- How did fights feel early on (around levels 1 to 15 with a small party and limited gear), in the mid-game (around levels 20 to 35), and near the end?
- Did any specific boss or regular enemy feel unfair, overly spongy, or trivial for the point where logic expected you to fight it?
- Did turning scaling off or adjusting the multipliers behave as expected?

### 2. Crashes, freezes, and softlocks

Stability is a high priority. If the game crashes, freezes, or gets stuck in an unrecoverable state:
- Note what you were doing right before it happened (changing maps, entering or leaving battle, opening a menu, boarding or landing the airship, talking to an NPC) and roughly how long the game had been running.
- Check `%LOCALAPPDATA%\FFRS\Saved\Crashes\` for a crash folder matching the timestamp and send it along with your report.
- Send your `UE4SS.log` from `...\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss\UE4SS.log` (or at least the `[FFRAP]` lines near the end).

### 3. Logic and reachability

Tell me anytime the randomizer's expectations do not match the actual game world:
- Was there any location that Universal Tracker or logic said was reachable, but you could not physically get to in game (for example, an area with no airship landing spot, a door or story blocker still closed, a missing key item requirement, or a boss trigger that would not start)?
- Did you reach any location or continent without the item that was supposed to gate it (for example, slipping past a bridge blocker, taking a ferry to a locked continent, or fast-traveling past a lock)?
- Did any check fail to send when you opened, picked up, or defeated it, or send by mistake before you touched it?
- When reporting a location issue, include the exact Archipelago location name (and the map or continent you were on).

### 4. The run as a whole

Let me know how the experience felt from setup to goal:
- Was anything in the installation, YAML setup, or client connection confusing?
- How did the HUD item feed, chest pop-ups, and **Options > Gameplay** menu feel to use?
- How was the pacing? Did progression feel too slow, too fast, or bottlenecked anywhere?
- Did received items, party members, visions, vehicles, and continent unlocks work cleanly when they arrived?
- What worked well, and what felt rough or frustrating?

## Where to find logs

If you hit a bug, crash, or missed check, these files help me track it down:
- Game mod log: `...\FINAL FANTASY RESONANCE\FFRS\Binaries\Win64\ue4ss\UE4SS.log`
- Unreal crash reports: `%LOCALAPPDATA%\FFRS\Saved\Crashes\`
- Archipelago client log: inside your Archipelago installation's `logs\` folder

## Feedback template

You can copy and fill out whatever parts apply when posting your feedback:

```text
Version (mod / apworld):
Seed type (solo / multiworld) and goal:
Notable YAML options (start_with_airship, start_with_chocobo, starting_roster, etc.):
Game difficulty + AP scaling strength:

1. Scaling feel (early / mid / late / bosses):
2. Crashes or freezes (and what happened right before):
3. Logic or reachability issues (exact location names if any):
4. Checks, items, or gates that behaved strangely:
5. General experience (setup, UI, pacing, fun factor, friction points):

Attached logs (if any): UE4SS.log / crash folder / client log
```
