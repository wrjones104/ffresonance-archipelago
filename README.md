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
data/chests.tsv            every chest table row (ffrap_export): the chest location table
```

At run time the mod writes these files into its own folder: `ap_out.txt`, `ap_state.txt`, `ap_status.txt`, `ffrap_dump.txt`, `chests.tsv` and `seen.tsv`. The fake server writes `ap_in.txt`.

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
check    chest:<row mapId>:<row ID>     (chests with no row: chest:<map>:u<m_UniqueId>)
check    shiny:<map>:<m_UniqueId>
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

**Round 2 (0.2.0, 2026-11-04): mostly passed, and it found three bugs.**
- **Chest export:** 238 rows, 56 maps, no duplicate `mapId:ID` keys, 9 gil chests and no trap rows. Row `3020:0` has `battleGroupId 51`, so it is probably a guarded chest. The export is in `data/chests.tsv`.
- **Shinies:**
  - The reward is on the actor: `m_ItemId`, `m_ItemNum`, `m_Money` on `CPP_MapGimmick_ItemObjectBase`.
  - `CPP_MapGimmick_FieldItem.m_IsOpen` is the picked-up flag.
  - The save (`IsOpenTreasureBox(map, m_UniqueId)`) answers true the moment one is picked up.
  - Classes seen: `BP_MapGimmick_FieldItem_C`, `_Child_C` and `_Medal_C`.
  - The world map (1000) has 93 field items. 8 of them have no item and no money, only a `VisibleCondition`: they are story or quest points, not pick-ups.
- **Save timing:** shinies are in the save at once. Chests never were, under `m_Id`, even after leaving the map and saving. So the save does not key chests by `m_Id`. 0.3.0 logs the other candidates (`m_UniqueId`, `TypeData.ID`, the row's map).
- **Bug 1, wrong current map:** the save's `Map.mapId` lagged minutes behind the real map. Two chests from map 3180 were reported as `chest:1000:0` and `chest:1000:2`. Fixed: the current map is now `CPP_MapManager:GetSameMapId()` (as FFRS_QoL uses), and chests are keyed by their own table row.
- **Bug 2, actors lingering after a map change:** a map's actors outlive the map change for a moment. Fixed: nothing is judged until the map id has held for 3 scans.
- **Bug 3, blanking restore:** after `ffrap_blank off`, chests in the current map still gave 1 gil. They had spawned while blanking was on, so their "original" snapshot was already blank. Fixed: originals are keyed by the row's `mapId:ID`, and a spawned chest restores from those.
- **Rowless chests:** four chests had `m_Id -1` (one in 2010, three already open in 3020). 0.3.0 keys them by `m_UniqueId` and records them in `seen.tsv` to find out what they are.
- **Switching saves:** the applied-item count and the reported checks are per install, not per save. Checks staying reported is right for Archipelago, because a location checked once stays checked. Items need a per-save index (open question 5).

## Round 3 test plan (0.3.0)

Keep FFRRandomizer disabled.

1. **Install.** Copy `Scripts/` over the old one. Delete `ap_out.txt` and `ap_state.txt` for a clean start. The log should say `version 0.3.0 loaded`.
2. **Map ids.** Walk through a few map changes, including the world map. The log prints `map A -> B (save's Map.mapId C)` each time. B should be right straight away.
3. **Chest save key.** On entering a map, the log prints each chest's key and what the save says under each candidate key. Open a chest, leave the map, and come back. Find the candidate that turns `true` for the opened chest. Also try map 2010, which uses rows `2001:*`.
4. **Rowless chests.** Note what the `chest:<map>:u<id>` chests are in game, if you can tell. Their rows in `seen.tsv` show their item fields.
5. **Shinies.** Pick up a few on the world map and in a field map. Each should give `check shiny:<map>:<uid>` within a second or two. Event spots (no reward) must never be reported.
6. **Blanking.** Run `ffrap_blank on`, open a chest, then `ffrap_blank off` and open another in the same map. The second one should give its real item.
7. **Seen list.** Fly around the world map for a while. `seen.tsv` collects every shiny with its reward. That is the start of our own shiny location list.

## After the POC

1. Replace `fake_ap.py` with a real client: a CommonClient subclass that connects to the server, writes `ReceivedItems` to `ap_in.txt` and sends `ap_out.txt` checks as `LocationChecks`. Later it could become an embedded UE4SS C++ client.
2. Build the apworld:
   - Locations: 238 chests from `chests.tsv`, shinies, story checkpoints and bosses.
   - Items: bag items, 26 visions, 8 party members, key items, gil.
   - Regions:
     - The linear first half is gated by the story counter.
     - After the airship, the continents (Grandshelt, Dirnado, Olderion, Zoldaad, Mysidia, Gronoa, Pharm) are gated by "unlock" items.
     - The Crystal Tower is the goal.
