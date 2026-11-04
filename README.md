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
| `ffrap_sync` | Report every location in `seen.tsv` that the save says is looted, from anywhere in the game (re-sync) |
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
check    chest:<row mapId>:<row ID>     (a rowless chest with a reward: chest:<map>:u<m_UniqueId>)
check    shiny:<map>:<m_UniqueId>
story    <counter>
applied  <index>  <ok|fail>  <detail>
```

`<map>` is always the map as the save keys it, `CPP_MapManager:GetSameMapId()`.

## seen.tsv

The mod appends one line the first time it sees each chest or shiny, across sessions. This builds our own location list and records the key the save knows each location by.

```
kind  map  uid  row  item  count  money  visible-condition
```

- `kind`: `chest` (has a table row), `xchest` (no row), `shiny`, or `spot` (a shiny-class story or quest point with no reward).
- `map` and `uid` are the save's key: `IsOpenTreasureBox(map, uid)` answers for that location from anywhere in the game.
- `row` is the chest table row (`mapId:ID`). For shinies this column holds the Blueprint class instead.

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

**Round 3 (0.3.0, 2026-11-04): passed the steps that were run; the chest save key is found.**
- **Map ids:** `GetSameMapId()` was right at once on every change (2002, 2001, 2015, 5200, 1000, 3001). The save's `Map.mapId` said 3020 the whole time you were in 2002 and 2001.
- **Chest save key: `IsOpenTreasureBox(current map, m_UniqueId)`.** `TypeData.ID` is the same number.
  - It was true for every opened chest: 3020:1, 3020:3 to 3020:6, 3001:0, 3001:1 and the rowless ones.
  - It was false for every closed one.
  - `m_Id` matched nothing. Its one "true" was a collision: `m_Id 7` of chest 3020:7 is the `m_UniqueId` of opened chest 3020:1.
- **Rows and maps do not line up.** Rows `3020:*` sit in map 2002, and rows `2001:*` in map 2001. The row key stays the location key, and `seen.tsv` now records each chest's save key next to it.
- **Rowless chests:** the three in 2002 (`u50`, `u52`, `u54`) had no item and no money and were already open. They look like story chests, whose contents come from an event. 0.3.1 records them but no longer reports them.
- **Shinies:** live pickups (`shiny:1000:137`, `shiny:1000:3`) and already-looted ones (`100`, `150`) were reported. One field shiny (map 3001, uid 80, item 20001) is story-gated: `{progress:31}==20`. Map 2015 has a Medal shiny (item 25004). `seen.tsv` now lists 85 world-map shinies and 8 event spots.
- **Story counter:** a jump made with the Modding Tools' story knob (1130 → 5010 → 1130) was reported as `story 5010`. The client should treat story reports as "reached at least N" and remember the highest value.
- **Clean start:** deleting `ap_state.txt` but keeping `ap_in.txt` re-granted items 0 to 6. That is correct behaviour; the round 3 instructions were wrong. A clean start deletes all three `ap_*.txt` files and restarts the fake server.
- **Not run yet:** whether the second chest gives its real item after `ffrap_blank off`.

## Round 4 test plan (0.3.1)

Keep FFRRandomizer disabled.

1. **Install.** Copy `Scripts/` over the old one. For a clean start, delete `ap_in.txt`, `ap_out.txt` and `ap_state.txt`, then restart the fake server. Keep `seen.tsv`, because 0.3.1 reads the 0.3.0 lines. The log should say `version 0.3.1 loaded`.
2. **Blanking restore.**
   - Run `ffrap_blank on`, then open a chest. Expected: 1 gil.
   - Run `ffrap_blank off`, then open another chest in the same map. Expected: its real item.
3. **Sync.**
   - Delete `ap_out.txt` while the game runs.
   - Go to a different map and run `ffrap_sync`.
   - Every chest and shiny you have opened that is in `seen.tsv` should come back as a `check` line.
4. **More of the list.** Play or fly through a few areas you have not visited yet. `seen.tsv` grows with chests and shinies, each with its save key.

## Open questions

1. **Party members.** `AddUnit` puts a unit in the *active* party and fails when it is full. An Archipelago "party member" item should mean "has joined", which may be `JoinStatus` in `saveData.unitParameterList`.
2. **Location list and save keys.** Chests and shinies are both in the save under `(GetSameMapId, m_UniqueId)`. The save answers at once and from anywhere (rounds 2 and 3). The chest table gives all 238 rows, but not their save keys. Shinies have no table at all. `seen.tsv` collects both as you play. The other options are ZArkadia's generated shiny list (197 spots across 52 maps, used with permission) or reading the level files.
3. **Story chests and story-gated shinies.** Rowless chests with no reward look like story chests; what do they give, and through which event? Some shinies only appear under a story condition (map 3001 uid 80: `{progress:31}==20`), which the apworld's logic must respect.
4. **Grant timing.** Is it safe to grant during battles, cutscenes and menus? So far the only guard is "save data and map manager exist" plus a 2-second settle.
5. **Per-save item index.** The applied count is one number per install. The real mod must store it per save: in the save itself, or in a sidecar file keyed by slot, the way FFRBestiary does. Then loading an older save re-grants exactly what that save lacks. Reported checks can stay per install, because in Archipelago a location checked once stays checked.
6. **Vanilla rewards.**
   - Chests: blanking to 1 gil works. Restoring is being re-tested in round 4.
   - Shinies carry their reward on the actor, so the same trick should work on `m_ItemId` and `m_Money`.
   - Story events that hand out party members, visions or key items need their own approach.
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
