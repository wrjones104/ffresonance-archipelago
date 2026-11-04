# FFRArchipelago (proof of concept)

A UE4SS Lua mod for Final Fantasy Resonance that does the in-game half of an Archipelago client:

- **Receive:** it reads items from a file and grants them in order. It can grant bag items, visions, party members and story flags. Each item is applied once, tracked by its Archipelago index.
- **Send:** it reports opened chests and changes to the story counter.

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
| On-screen text | `BP_ModSettings:Toast(msg, seconds, hue, worldContext)` | FFRSLib |

FFRSLib is FFR Modding Tools' in-game library by Kanaruu. This mod is separate code that calls the same functions, and it needs neither mod to run. The one exception is on-screen text, which needs the ModSettings panel. Before you publish anything, check the Modding Tools' permissions on Nexus and credit the work properly.

## Files

```
FFRArchipelago/            -> copy to ...\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago
  enabled.txt
  Scripts/main.lua         loop, item queue, checks, console commands
  Scripts/game.lua         every engine call (the only file to fix after a game patch)
  Scripts/bridge.lua       the file link to the client
tools/fake_ap.py           fake Archipelago server for testing
```

At run time the mod writes these files into its own folder: `ap_out.txt`, `ap_state.txt`, `ap_status.txt` and `ffrap_dump.txt`. The fake server writes `ap_in.txt`.

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
story    <counter>
applied  <index>  <ok|fail>  <detail>
```

## In-game test plan

1. **Install.** Copy `FFRArchipelago` into `ue4ss\Mods\`. Start the game and load a save. In `UE4SS.log`, look for `[FFRAP] version 0.1.0 loaded` and then `save loaded, map ...`.
2. **Start the fake server:** `python tools\fake_ap.py`.
3. **Title screen check.** Return to the title screen. `ap_status.txt` should say `in game: false`. If it says `true`, `game.InGame()` needs a better signal before any grant runs there.
4. **Bag item.** Type `item 10100 1 Crimson Saber`. A toast should appear, the bag should hold it, and the server should print `game> applied 0 ok`.
5. **Vision.** Type `vision 13017 Amelia`. Check that it appears on the Equip screen.
6. **Party member.** Type `unit 1002`. Try it twice: once with room in the party, and once with a full party.
7. **Flag.** Type `flag <index>` with an index you know from the Modding Tools.
8. **Chest.** Open a chest. The server should print `game> check chest:<map>:<uid>`. The log shows the actor's open state next to the save's for every chest in a map the first time you enter it.
9. **Story.** Pass a story checkpoint. The server should print `game> story <n>`.
10. **Restart.** Close and reopen the game. Nothing should be granted again, and no old chest should be reported again.
11. **Discovery dump.** In a map with chests, run `ffrap_dump 20` in the UE4SS console. It writes `ffrap_dump.txt` with the chest actor structs and the first rows of `CDT_MapGimmickTreasureBox`.

I tested the bridge, the item queue, retry, de-duplication and restart behaviour off-line, against stub engine functions in Lua 5.4. I have not run any of it in the game.

## Open questions the test plan answers

1. **Party members.** `AddUnit` puts a unit in the *active* party. An Archipelago "party member" item should mean "has joined", which may be `JoinStatus` in `saveData.unitParameterList`. What happens when the party is full?
2. **Chest keys.** Some maps share another map's save list (FFRS_QoL's `chest_items.lua` has an alias table). Steps 8 and 11 show whether `chest:<actor map>:<uid>` is a stable key. The dump also shows which table row fields hold the map and uid, so the apworld location list can come straight from the table.
3. **Grant timing.** Is it safe to grant during battles, cutscenes and menus? So far the only guard is "save data and map manager exist" plus a 2-second settle.
4. **Per-save item index.** The applied count is one number per install. The real mod must store it per save: in the save itself, or in a sidecar file keyed by slot, the way FFRBestiary does. Then loading an older save re-grants exactly what that save lacks.
5. **Vanilla rewards.** Chests still give their own item. Next, patch chest table rows (the randomizer's approach) to a placeholder or nothing. Story events that hand out party members, visions or key items need the same treatment.
6. **Gil.** The Modding Tools can add gil, but FFRSLib has no command for it. Find that call.

## After the POC

1. Replace `fake_ap.py` with a real client: a CommonClient subclass that connects to the server, writes `ReceivedItems` to `ap_in.txt` and sends `ap_out.txt` checks as `LocationChecks`. Later it could become an embedded UE4SS C++ client.
2. Build the apworld:
   - Locations: chests from the table dump, plus story checkpoints and bosses.
   - Items: bag items, 26 visions, 8 party members, key items.
   - Regions:
     - The linear first half is gated by the story counter.
     - After the airship, the continents (Grandshelt, Dirnado, Olderion, Zoldaad, Mysidia, Gronoa, Pharm) are gated by "unlock" items.
     - The Crystal Tower is the goal.
