# FFRArchipelago (proof of concept)

A UE4SS Lua mod for Final Fantasy Resonance that does the in-game half of an Archipelago client:

- **Receive:** it reads items from a file and grants them in order. It can grant bag items, visions, party members and story flags. Each item is applied once, tracked by its Archipelago index.
- **Send:** it reports opened chests, picked-up shinies (shining spots) and changes to the story counter.

Nothing talks to an Archipelago server yet. `tools/fake_ap.py` plays the server's part, so the game side can be proven first.

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
| On-screen text | `BP_ModSettings:Toast(msg, seconds, hue, worldContext)` | FFRSLib |

FFRSLib is FFR Modding Tools' in-game library by Kanaruu. This mod is separate code that calls the same functions, and it needs neither mod to run. The one exception is on-screen text, which needs the ModSettings panel. Before you publish anything, check the Modding Tools' and ZArkadia's permissions on Nexus and credit the work properly.

## Files

```
FFRArchipelago/            -> copy to ...\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago
  enabled.txt
  Scripts/main.lua         loop, item queue, checks, console commands
  Scripts/game.lua         every engine call (the only file to fix after a game patch)
  Scripts/bridge.lua       the file link to the client
tools/fake_ap.py           fake Archipelago server for testing
```

At run time the mod writes these files into its own folder: `ap_out.txt`, `ap_state.txt`, `ap_status.txt`, `ffrap_dump.txt` and `chests.tsv`. The fake server writes `ap_in.txt`.

## Console commands

| Command | What it does |
|---|---|
| `ffrap_status` | What the mod sees right now |
| `ffrap_grant <kind> <id> [n]` | Grant directly, without the bridge: `item`, `vision`, `unit`, `flag` |
| `ffrap_dump [rows]` | Chest and shiny discovery dump to `ffrap_dump.txt` |
| `ffrap_export` | Every chest table row to `chests.tsv` |
| `ffrap_blank [on\|off]` | Experiment: every non-trap chest gives 1 gil instead of its vanilla reward. It is remembered across restarts. |
| `ffrap_savecheck` | Ask the save about every chest and shiny reported so far |
| `ffrap_reset` | Forget the applied-item count. Re-grants everything! |

## Bridge format

Both files are append-only and tab-separated, one record per line.

`ap_in.txt` (client to game):
```
item  <index>  <kind>  <id>  <count>  <label>     kind: item | vision | unit | flag
msg   <text>
```

`ap_out.txt` (game to client):
```
hello    <version>
check    chest:<mapId>:<uid>
check    shiny:<mapId>:<uid>
story    <counter>
applied  <index>  <ok|fail>  <detail>
```

## Test results so far

**Round 1 (0.1.0, 2026-11-04): passed.**
- **Grants:** bag items, vision unlock (with all 8 synchro keys), party add and the duplicate guards all worked. Party add refused a unit when the party was full.
- **Story counter:** reported live (5062 → 5064).
- **Chest checks:** reported live (`chest:3180:0`, `chest:3180:2`).
- **The dump showed:**
  - The chest table has 238 rows. Each row's `mapId` and `ID` match the live chest's `m_TreasureBoxData`, so `chest:<mapId>:<ID>` from the table is the location key. Row names do not encode the map.
  - Gil chests have `ItemId = -1` and a `Money` value. `IsTrap` and `battleGroupId` are on every row.
  - `IsOpenTreasureBox` answered `false` for two chests opened moments before. Live checks use the chest's own `m_IsOpen`, so they work. A reconnect re-sync needs the save, so round 2 finds out when the save catches up.

## Round 2 test plan (0.2.0)

Disable FFRRandomizer for these tests: delete or rename its `enabled.txt`. It patches the same chest rows, and the two mods would fight over them.

1. **Install.** Copy the new `FFRArchipelago` over the old one. Keep its `ap_*.txt` files, or delete them for a clean start. The log should say `version 0.2.0 loaded`.
2. **Chest export.** Run `ffrap_export`, then copy `chests.tsv` into this repo under `data/`. It should hold 238 rows.
3. **Save timing.**
   - Open a chest, then leave the map. The log prints `save check after leaving map ...` for it.
   - Save the game, then run `ffrap_savecheck`.
   - Together these show when `IsOpenTreasureBox` catches up: on leaving the map, on saving, or never for this key.
4. **Shinies, world map.** Pick up a few shinies on the world map, then fly far away and come back.
   - The log has a line for each shiny when it is first seen.
   - It prints `changed` (hidden or no interaction) when one is picked up.
   - It prints `is gone` when an actor vanishes. Watch whether "gone" happens on pickup, on streaming out, or both.
   - The server prints `check shiny:1000:<uid>` when a pickup is detected.
5. **Shinies, field map.** Do the same in a dungeon or town with shinies.
6. **Shiny dump.** Next to a shiny you have not picked up, run `ffrap_dump`. The field item section lists every property of the shiny's classes. That is where its reward (item id, count, maybe a lottery table) should show up.
7. **Chest blanking.**
   - Run `ffrap_blank on`, then open a chest you have not opened yet, in this map and in a new map.
   - Note what the "obtained" popup says (expected: 1 gil).
   - Check that the chest counts as opened and the server gets the check.
   - Run `ffrap_blank off` afterwards.

## Open questions

1. **Party members.** `AddUnit` puts a unit in the *active* party and fails when it is full. An Archipelago "party member" item should mean "has joined", which may be `JoinStatus` in `saveData.unitParameterList`.
2. **Save timing.** When does `IsOpenTreasureBox` see a newly opened chest? (Round 2, step 3.)
3. **Shiny pickup signal and contents.** Which actor field changes on pickup, and where the reward is defined. (Round 2, steps 4 to 6.) A full location list needs every shiny's map and uid. ZArkadia's generated list has 197 spots across 52 save maps, about 90 of them on the world map. We either ask to use that list or generate our own from the level files.
4. **Grant timing.** Is it safe to grant during battles, cutscenes and menus? So far the only guard is "save data and map manager exist" plus a 2-second settle.
5. **Per-save item index.** The applied count is one number per install. The real mod must store it per save: in the save itself, or in a sidecar file keyed by slot, the way FFRBestiary does. Then loading an older save re-grants exactly what that save lacks.
6. **Vanilla rewards.** Chests: round 2, step 7. Shinies and story events that hand out party members, visions or key items need the same treatment.
7. **Gil.** The Modding Tools can add gil, but FFRSLib has no command for it. Find that call. The chest table's `Money` field shows the game already grants gil from chests.

## After the POC

1. Replace `fake_ap.py` with a real client: a CommonClient subclass that connects to the server, writes `ReceivedItems` to `ap_in.txt` and sends `ap_out.txt` checks as `LocationChecks`. Later it could become an embedded UE4SS C++ client.
2. Build the apworld:
   - Locations: 238 chests from `chests.tsv`, shinies, story checkpoints and bosses.
   - Items: bag items, 26 visions, 8 party members, key items, gil.
   - Regions:
     - The linear first half is gated by the story counter.
     - After the airship, the continents (Grandshelt, Dirnado, Olderion, Zoldaad, Mysidia, Gronoa, Pharm) are gated by "unlock" items.
     - The Crystal Tower is the goal.
