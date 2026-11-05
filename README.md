# Final Fantasy Resonance for Archipelago (MVP)

Two parts:

- **FFRArchipelago**, a UE4SS Lua mod that does the in-game half.
  - **Receive:** it reads items from a file and grants them in order: bag items, gil, visions, party members and story flags. Each item is applied once per save, tracked by its Archipelago index and by how many items each save slot holds.
  - **Send:** it reports opened chests, picked-up shinies (shining spots) and changes to the story counter.
- **`apworld/ff_resonance`**, the Archipelago world and client.
  - The world generates seeds: chests with consumables, equipment or gil are locations, and shinies are an option.
  - The client connects the mod to a server through the bridge files.

`tools/fake_ap.py` still plays the server's part for testing the mod alone.

AI use: this project is built with Claude Code. [DISCLOSURE.md](DISCLOSURE.md) says what was AI-written, what I did, and how much has been reviewed.

## Playing the MVP

The world is tested off-line: Archipelago's general tests pass with it, its own tests pass, and a client end-to-end run against a local server passes, with a script standing in for the game. Round 5 played a full seed in the real game, up to the goal and a release (see "Test results so far").

**What the mod needs:**
- **UE4SS**, the only thing it needs to run. ConsoleEnablerMod and BPModLoaderMod come with UE4SS. The console is only for the `ffrap_*` commands.
- **ModSettings** (a Blueprint mod in `Content/Paks/LogicMods`, from the same modding tools as FFRSLib) is optional. In the field, messages ("Received ...", "Sent ...", "Archipelago is paused", "Prologue skipped") go to the mod's own item feed at the bottom right of the HUD (since 0.10.0, on by default). ModSettings' Toast panel takes them off the field (the title screen), when the feed has not been able to show anything for 10 seconds since the game started, and with `ffrap_feed off`. Without ModSettings those few only go to `UE4SS.log`.
- **FFRSLib, FFRS_QoL, FFRBestiary and FFRRandomizer are not needed.** Their code is where the game calls come from (see "Where the game calls come from"), but this mod calls the game directly. FFRRandomizer should stay disabled (IDEAS.md, idea 10).

1. **Mod.** Copy `FFRArchipelago/Scripts` and `FFRArchipelago/Assets` over the installed mod (0.11.0). Delete the old `ap_in.txt`, `ap_out.txt` and `ap_state.txt`, and keep `seen.tsv`. Keep FFRRandomizer disabled.
2. **World.** Run `python tools/build_apworld.py`, then copy `dist/ff_resonance.apworld` into your Archipelago `custom_worlds` folder. Or, from source, copy `apworld/ff_resonance` into `worlds/`.
3. **Seed.**
   - Copy `apworld/Final Fantasy Resonance.yaml` into Archipelago's `Players` folder and set a name.
   - For a first test, set `goal_story_checkpoint` to a value a little past your save, e.g. 1130.
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
tools/import_item_names.py FFR-Randomizer's ItemNames.lua -> data/item_names.tsv
tools/snapdiff.py          compares two ffrap_snapshot files
data/chests.tsv            every chest table row (ffrap_export): the chest location table
data/shinies.tsv           shinies seen in game (the mod's seen.tsv)
data/item_names.tsv        item id -> name, from FFR-Randomizer by LordMikoda (MIT)
```

After `data/*.tsv` changes, run `python tools/gen_apworld_data.py` and commit the regenerated `data.py`.

Ideas that are not on the test plan yet (Tablet Shards, skipping the prologue, an open-world mode) are in [IDEAS.md](IDEAS.md).

At run time the mod writes these files into its own folder: `ap_out.txt`, `ap_state.txt`, `ap_status.txt`, `ffrap_dump.txt`, `chests.tsv` and `seen.tsv`. The fake server writes `ap_in.txt`.

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
| `ffrap_skip [slot]` | Skip the prologue on a new game, once you can move Fina (story 1005). Without a slot it only changes the loaded save; with one it applies the skip again, saves there and reloads. Testing only for now (IDEAS.md, idea 2). |
| `ffrap_inspect <class or path>` | One object's fields and functions to `inspect_<name>.tsv`: a class name gives its first live instance (else its default object), and a path gives that object (IDEAS.md, idea 6). |
| `ffrap_find <text>` | Every game class or struct, native or Blueprint, whose name or one of its functions or fields holds the text, to `find_<text>.txt`. Walks every object, so the game pauses for a moment. Run it in game: at the title screen it crashed the game once (round 11). |
| `ffrap_title [list\|add]` | `list` logs the entries the title menu shows. `add` adds the Archipelago entry again by hand: the mod adds it at start-up and keeps it there. |
| `ffrap_notice [text]` | Experimental: tries to show the text with the game's quest-notice banner, in the field. |
| `ffrap_logo` | Puts the Archipelago logo at the end of the mod's line on the title screen. The mod does this by itself; the command is for trying it again by hand. |
| `ffrap_layout <text>` | Logs the chain of panels holding the on-screen text that holds `<text>`, up to the screen's root layout. For finding where new HUD elements can go. |
| `ffrap_feed [on\|off\|test [plain]]` | The item feed at the bottom right of the field HUD: on by default; off sends messages to ModSettings' Toast. Kept in `ap_state.txt` as `itemfeed`. `test` shows three sample lines. Every step the feed takes is logged before it runs (`feed step: ...`), so a crash's last line names the call. `test plain` leaves out the styling. `check` logs what the engine says about the feed: the box's and each line's size, visibility and font. |
| `ffrap_bind` | Link the loaded save to the client's session, in place of any earlier one. The same as `/bind` in the client. |
| `ffrap_reset` | Set the loaded save's applied-item count to 0. Re-grants everything to it! |

## Bridge format

Both files are append-only and tab-separated, one record per line.

`ap_in.txt` (client to game):
```
seed  <seed name>:<team>:<slot>                  first line; a new value starts the mod's state over
cfg   blank  <0|1>                               chest blanking
item  <index>  <kind>  <id>  <count>  <label>    kind: item | gil | vision | unit | flag
msg   <text>                                     shown on screen
sync                                             report everything the save says is looted
bind                                             link the loaded save to this session (0.5.0)
```

**Which save a session belongs to (0.5.0).** The mod links each session to one save. A new game started during the session, never saved yet, is linked at once. An existing save is linked by `bind`. The session then remembers every slot the linked game is saved to (`slots` in `ap_state.txt`), and forgets a slot when another game is saved over it. While a save that is not linked is loaded, the mod grants nothing, writes no `check` or `story` lines and turns chest blanking off. Older mods ignore the `bind` line, so the protocol stays 1.

`ap_out.txt` (game to client):
```
hello    <version>  <protocol>
seed     <session>                  the lines after it belong to that session
check    chest:<row mapId>:<row ID>     (a rowless chest with a reward: chest:<map>:u<m_UniqueId>)
check    shiny:<map>:<m_UniqueId>
story    <counter>
applied  <index>  <ok|fail>  <detail>
```

The client only counts `check` and `story` lines after a `seed` line for its own session. A new session empties `ap_out.txt`, so checks from another seed, or from before connecting, are never sent.

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
- **Switching saves:** reported checks are per install, which is right for Archipelago, because a location checked once stays checked. Since mod 0.7.0 the applied-item count is per save (open question 5).

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

**Round 5 (mod 0.4.0 with the MVP apworld and client, 2026-11-05): passed.**
This was the first real Archipelago game: a new game, a local MultiServer, the 0.6.7 Launcher and the goal set to 1130.
- **Checks and items:** 20 chests in 5 maps were each sent as a check before the goal. Each one gave 1 gil, and its real item arrived from the server with a "Received ..." toast about 1 second later.
- **Reconnect:** the client was closed overnight and reconnected. The mod kept the session (17 items already applied) and granted nothing twice.
- **Goal:** story 1130 sent the goal, and the toast showed once. The server's auto release then sent the other 196 items. The mod applied them 5 at a time, every half second, with one toast per batch. All 216 were applied, including the gil items (9930 -> 13930 gil), which is the first in-game test of gil grants.
- **Blanking restore (from round 4):** after `ffrap_blank off`, chest 2020:1 gave its real item in the same map. After `ffrap_blank on`, chest 2020:0 gave 1 gil.
- **Sync (from round 4):** `ffrap_sync` reported "0 new checks from 137 known locations", which is correct because nothing had been missed.
- **Shinies:** shinies are off by default, so their checks (`shiny:1000:150`, `1000:137`, `2015:4`, `1000:127`) were reported and ignored by the client. A second Tablet Shard (Medal class) was found at map 2020, uid 5.
- **Vehicles (IDEAS.md, idea 4):**
  - `ffrap_grant item 30002` (Choboco Saddle) made the chocobo rideable. The chocobo is gated by the item alone.
  - 29520 (Magitek Airship Passkey) only changes how the airship looks. It does not unlock the airship. You already had one, from a pre-registration reward.
  - 30011 (Chocobo Saddle-Bike) did nothing visible. It may be unused, or need a condition we have not found.
- **Bug 1, seed name:** the 0.6.7 client never stores the room's seed name, so the session key was `unknown:0:1`. Every seed with the same slot would get that key, and the mod would skip a new seed's items as already applied. Fixed in the client: it reads the seed name from `RoomInfo` itself, and it does not connect to the game if there is none.
- **Bug 2, checks from another save:** the session started while an old save (story 1095) was loaded. The sync on that load reported `shiny:1000:150` from the old save into the new session. It was ignored because shinies are off, but a chest would have been sent. See open question 8.
- **Item names:** items 5 and 6 have no name in `item_names.tsv`, so they showed as "Item 5" and "Item 6". Their vanilla chests are Mysidia Dungeon 45 Chest 0 and Olderion Dungeon 43 Chest 4.

Rounds 6 to 9 (2026-11-05) worked out and tested the prologue skip; their results are in IDEAS.md, idea 2.

**Round 10 (mod 0.7.0, 2026-11-05): per-save item count passed; `/bind` not tested.**
- **New game and skip:** the new game linked itself. `ffrap_skip 0` ran after the first autosave, and the reload linked slot 0 with 0 items.
- **Per-save count:** the game was saved to slot 3 (`3=0`), and two chests in map 3001 then sent their checks and brought Briar Edge and Nodachi. Loading slot 3 again logged `slot 3 holds: 0 applied (was 2)` and granted both again. Saving to slot 4 recorded `4=2`, and loading slot 4 granted nothing. Loading slot 3 later granted both again, as it should.
- **Pausing:** an older save (slot 1) and a second new game were both paused. `ffrap_skip` during the second game's opening movie was refused with the "wait until you can move" message.
- **`/bind` not tested:** the client said "Could not find command bind". The session key was `unknown:0:1` too. Both mean the installed client was older than world 0.1.1, because the round 10 plan did not say to install the new apworld. World 0.1.3 makes this visible: the client logs its world version when it starts, and writes a `client` line to `ap_in.txt` that the mod logs (`client: world version 0.1.3`). Until the new apworld is installed, `ffrap_bind` in the game console does the same as `/bind`.

**Round 11 (mod 0.7.2, world 0.1.3, 2026-11-05): passed.** With the current apworld installed, the session key had the seed's number, `/bind` linked an older save, and that save received every item. The title-screen probes ran: see IDEAS.md, idea 6.

**Round 12 (mod 0.7.3, 2026-11-05): the title entry works.**
- `ffrap_title add` added row 5. The menu showed it (as a second "New Game", at the bottom) only after a trip into a game and back: the menu reads its list when it is made.
- Every choice logged `title: entry <n> chosen` (Continue 0, Load 1, Options 3, Quit 4). Choosing row 5 logged `entry 5`, showed "starting a new game for the seed" and started a normal new game. It was paused, because the session already had a save. 0.8.0 links it.
- The row's fields are `EntryName` (the label), `DisplayProperty` (`bCheckSaveData`, `bCheckPlatform`, `DisplayPlatformMap`) and `SystemActionTag`.
- `ffrap_find Opening` found `IsOpeningProcess` only on widgets (the finger cursor, menu titles, a combo box): a widget's open animation, not the game's opening. `ffrap_find NewGame` found the class `CPP_Task_NewGame`. No crash in game.

**Round 13 (mod 0.8.0, 2026-11-05): passed.**
- **The entry:** "title: Archipelago entry ready" came half a second after the mod loaded, and the entry was on the first title screen.
- **Plain New Game:** it was paused, with the message pointing at the Archipelago entry.
- **The Archipelago new game:** it linked to the new seed. The game autosaved to slot 0 two seconds after story 1005, and the skip ran by itself 1.5 seconds later (`skip (automatic): saved to slot 0 (map 3001, flag 1 false)`). It landed at the Earth Shrine, ready to play.
- **Checks and items:** the two chests in map 3001 sent their checks and brought 400 Gil and an Ether. Loading slot 0 (saved before they arrived) granted both again, as it should.

**Round 14 (mod 0.8.1, 2026-11-05): passed.**
- **The title menu** read Continue, Load Game, New Game, New Game (Archipelago), Options, Quit Game (`entry order rebuilt as [0,1,2,5,3,4]`). Every entry still worked.
- **The version line** showed "FFRArchipelago 0.8.1" above "1.0.1.0", and again after coming back from a game. The block is right-justified, though, so "1.0.1.0" moved right. 0.8.2 sets it to left-justified.
- **New Game (Archipelago)** linked, delivered the seed's items, and skipped the prologue by itself. Three chests in map 3000 sent their checks.
- **Notice probes:** `ffrap_find Notice` found 42 names, and `CPP_VM_QuestNotice` was inspected (IDEAS.md, idea 6).

**Round 15 (mod 0.8.2, 2026-11-05): passed.**
- **The title corner:** "FFRArchipelago 0.8.2" and "1.0.1.0" now both start at the left edge, in line with the copyright lines.
- **The layout line:** the version text is `Text_ApplicationVersion` in an `OverlaySlot` of the `Overlay` `Overlay_UI`. Its siblings are `TextBlock_1` and `WidgetSwitcher_0`, the grandparent is `Overlay_3`, and it is all in `WBP_TitleLayout_C`.
- **Messages:** the cyan line under the quest tracker in the recording ("Received Resonate Staff", and FFRS_QoL's "Normal speed") is this mod's message, drawn with ModSettings' Toast. `ffrap_notice` was not run.
- **Functions:** `CPP_BFL_Chat.Notice` takes a chat event id (`InEventId`), not text, so it cannot show our messages.

**Round 16 (mod 0.8.3, 2026-11-05):**
- **The logo:** `ffrap_logo` worked with no crash. It put the logo above "FFRArchipelago 0.8.3" (`alignment 1/3, text padding 60,0,50,97, text height 43.2`). You asked for it on the same line as the version, so 0.8.4 puts it at the end of that line, one line high.
- **The quest banner:** `ffrap_notice` showed nothing. The banner is likely driven by quest data and its own animation, not the title text. Dropped in favour of an item feed (IDEAS.md, idea 14).

**Round 17 (mod 0.8.4, 2026-11-05): passed.**
- **The logo** was added by itself at the end of "FFRArchipelago 0.8.4" (`24x25 at left 264.6, bottom 116.9`), and came back on the next title.
- **The field HUD:** `ffrap_layout Quests` reached `WBP_FieldLayout_C`'s `Overlay_66`, which holds the minimap, the key list (`WBP_FieldFuncList2`), the quest tracker (`WBP_FieldQuestLayout`) and the place name. Two screenshots show the fullest HUDs: the bottom right is empty in both.
- **The save card:** `ffrap_layout Tranquility` (on the Load screen) found `WBP_SaveData_Entry_C` with `Text_ChapterName`, `Text_PlaceName` and `Text_PlayLevel` (IDEAS.md, idea 11).

**Round 18 (mod 0.9.0, 2026-11-05): the game crashed.** Continue, Load Game and New Game all ended in "Fatal error!". In each run the last log line was "Archipelago is paused": the first message after the load, and in 0.9.0 the first time the feed made its box on the field HUD. Only the feed is new there, so it is the cause. A crash in the engine stops the Lua before it can log, so the log does not say which call. 0.9.1 turns the feed off by default and logs each step before it runs.

**Round 19 (mod 0.9.1, 2026-11-05): still crashed.** The feed was meant to be off, but it was on. 0.9.0 had written `feed 1` to `ap_state.txt` by itself, because it was on by default, and 0.9.1 read that as switched on. The second run logged one "Received ..." line per item, which only happens with the feed on. Those five items came during the opening movie, before the field HUD existed, so they waited in the feed's queue. The game crashed after story 1005, when the HUD appeared and the queue was shown. The step logging only ran for `ffrap_feed test`, so the log did not name the call. 0.9.2 ignores the old `feed` line (the switch is now `itemfeed`) and logs the feed's steps every time.

**Round 20 (mod 0.9.2, 2026-11-05): the crash is found.**
- **Loading:** no crash on load.
- **`ffrap_feed test plain`** worked twice, with every step logged.
- **`ffrap_feed test`** crashed the game twice. Both times the last line was `feed step: style: copy the key guide's font`, the call `tb:SetFont(guide.Text_Name.Font)`.
- **Why:** a font (`FSlateFontInfo`) holds engine-only parts that a struct passed from Lua does not carry. The setters that take a Slate colour (`FSlateColor`) have the same problem.
- **0.9.3** styles each line by writing its fields (font object, typeface, size, shadow colour, justification) before the line goes on screen. No setter is given a struct.

**Round 21 (mod 0.9.3, 2026-11-05): no crash, but no lines showed.**
- **What ran:** `ffrap_feed test` and the real items (`ffrap_feed on`, a `/bind` with five items, three chests) ran every step, and every line logged `line done`. None showed on screen.
- **Two causes found:**
  - **Alignment:** the alignment numbers were wrong. Unreal counts Fill 0, Left/Top 1, Center 2, Right/Bottom 3, and the feed used 2 for right, so the box was centred.
  - **Font:** the font copy may have emptied the font. The key guide's text is a `CommonTextBlock`, which can take its font from a style when drawn and leave its own font object empty. A line with an empty font object draws nothing.
- **The "Back" prompt:** menus and the chest pop-up put a "Back" prompt at the very bottom right.

**Round 22 (mod 0.9.4, 2026-11-05): no lines showed, and `ffrap_feed check` showed why.**
- **The HUD overlay the feed used:** `0x0, visible false`. Our box in it was too. In UE, `IsVisible` is false for a widget with no live on-screen widget behind it.
- **The cause:** `FindFirstOf("WBP_FieldFuncList2_C")` found a copy of the key list that is never drawn, likely the template a widget Blueprint keeps. The feed went into that copy.
- **The font:** the key guide font came back empty for the same reason (`none, the default font is kept`).
- **Messages:** with the feed on, every message went to that invisible feed instead of ModSettings' Toast, so items showed only in the client.

**Round 23 (mod 0.9.5, 2026-11-05): the item feed works.**
- `ffrap_feed check` found 2 key lists, 1 on screen, and an overlay 525x400 and visible. The lines were 26 px tall in the game's own font, `SystemText` (`/Game/UI/Font/SystemText`).
- Lines showed at the bottom right, right-justified with a shadow ("Received Celaeno Fragments", "Received Repeater Rifle", and the test lines).
- **Chest items:** a chest's item line waits in the queue while the chest pop-up is up, and shows once it is closed: Monk's Prayer Beads arrived at 15:33:12.98 and its line was made at 15:33:13.48. So the feed never meets the pop-up's "Back" prompt.
- **Your notes:** a little more space between lines, and a little longer on screen (you prefer them fading out over staying, as in TUNIC and Hollow Knight).

**Round 24 (mod 0.10.0, 2026-11-05):**
- **The feed:** on by default, with the new spacing and time, and it feels right. Chest items showed after the pop-up was closed ("Received Mist Hi-Potion x2", "Received Dreadwing Mallet", "Received Stout Armor").
- **Messages that should be quiet:** "Prologue skipped ..." showed on a new game. The new game's "linked to the seed" went to the Toast during the opening movie.
- **The pop-up probe:** it found no text holding "obtained", though the pop-up was up: twice the HUD stayed hidden for more than 10 s after a chest. The item line, "(gil icon) 1", is text with an icon in it, which in UE is a `RichTextBlock`, not a `TextBlock`. The probe only searched TextBlocks.
- **The 10-second fallback misfired:** a chest pop-up held for 10 s sent its items to the Toast.

**Round 25 (mod 0.10.1, 2026-11-05): passed.** The new game showed neither "linked to the seed" nor "Prologue skipped", and a chest pop-up held open still sent its item to the feed once closed. The `chest pop-up layout` lines from this round's log are still to be read (IDEAS.md, idea 13).

## Round 26 test plan (mod 0.11.0, world 0.1.4)

This round tests the chest pop-up (IDEAS.md, idea 13).

1. **Install both.**
   - Copy `FFRArchipelago/Scripts` and `FFRArchipelago/Assets` over the installed mod. The log should say `version 0.11.0 loaded`.
   - Copy `dist/ff_resonance.apworld` (world 0.1.4) over the one in Archipelago's `custom_worlds`, and generate a new seed with it. A seed with a second player shows the "for Alice" text.
2. **Connect.** The client should log "Told the game what N location(s) hold, for its chest pop-up", and `ap_in.txt` gets `scout` lines.
3. **Open chests.**
   - **Your own item:** the pop-up should change from the gil line to "You obtained the following:" and the item's name.
   - **Another player's item:** "You found the following for <player>:" and the item's name.
   - The gil icon and "1" should disappear. The log says `chest pop-up for chest:...: text set, item line hidden`.
   - The text may change a moment after the pop-up appears.
4. **Other pop-ups:** after a chest, open something else that uses a pop-up (a vanilla chest in a save that is not linked, or the Quit dialog). Its own content should show normally.
5. Send `UE4SS.log` (the `[FFRAP]` lines) and a screenshot of each kind of pop-up.

## Open questions

1. **Party members.** `AddUnit` puts a unit in the *active* party and fails when it is full. An Archipelago "party member" item should mean "has joined", which may be `JoinStatus` in `saveData.unitParameterList`.
2. **Location list and save keys.** Chests and shinies are both in the save under `(GetSameMapId, m_UniqueId)`. The save answers at once and from anywhere (rounds 2 and 3). The chest table gives all 238 rows, but not their save keys. Shinies have no table at all. `seen.tsv` collects both as you play. The other options are ZArkadia's generated shiny list (197 spots across 52 maps, used with permission) or reading the level files.
3. **Story chests and story-gated shinies.** Rowless chests with no reward look like story chests; what do they give, and through which event? Some shinies only appear under a story condition (map 3001 uid 80: `{progress:31}==20`), which the apworld's logic must respect.
4. **Grant timing.** Is it safe to grant during battles, cutscenes and menus? So far the only guard is "save data and map manager exist" plus a 2-second settle.
5. **Per-save item index. Done in mod 0.7.0** (see below). Before that, the applied count was one number per install. The real mod must store it per save: in the save itself, or in a sidecar file keyed by slot, the way FFRBestiary does. Then loading an older save re-grants exactly what that save lacks. Reported checks can stay per install, because in Archipelago a location checked once stays checked. Save linking (mod 0.5.0) makes this matter sooner: `/bind` on a different save in the middle of a seed keeps the count, so that save never gets the items applied before. The prologue skip makes a new save for each seed, so it needs this first.
   - **How it works:** the mod keeps every item of the session in memory, and `ap_state.txt` keeps, for each linked slot, how many of them the save in that slot holds (`slotItems 1=3,2=4`).
   - **When the game saves:** the mod notes the count at that moment against the slot. Items granted after that and never saved are granted again when that slot is loaded.
   - **New saves:** a new game, and a save linked with `/bind` that the session did not own before, start at 0 and get every item.
   - **Mod reload:** the state also names the live save the count is for (`live <object>|<timestamp>`), so reloading the mod while the same save is loaded grants nothing twice.
   - **The skip:** `ffrap_skip <slot>` links its slot with the count the save holds when it saves. Its inventory changes are now relative and made once per save, so an Archipelago item with a starter item's id is kept.
   - **Bridge fix, found on the way:** a new seed's `ap_in.txt` that was already longer than the old one was read from the old position, so its `seed` line was missed. The mod now also starts over when the file's first line changes.
6. **Vanilla rewards.**
   - Chests: blanking to 1 gil and restoring both work (round 5).
   - Shinies carry their reward on the actor, so the same trick should work on `m_ItemId` and `m_Money`.
   - Story events that hand out party members, visions or key items need their own approach.
7. **Gil.** Solved: `CPP_BFL_SaveDataPlayer` `GetCurrentMoney` / `SetCurrentMoney`, tested in round 5.
8. **Checks from another save.** Fixed in 0.5.0 and tested off-line only: each session is linked to one save (see "Bridge format"), and every other save is paused. Not tested in game yet: that a new game has no slot until it is saved, and that a save's timestamp matches its slot summary in this game version. FFRBestiary relies on both.

## After the POC

1. Replace `fake_ap.py` with a real client: a CommonClient subclass that connects to the server, writes `ReceivedItems` to `ap_in.txt` and sends `ap_out.txt` checks as `LocationChecks`. Later it could become an embedded UE4SS C++ client.
2. Build the apworld:
   - Locations: 238 chests from `chests.tsv`, shinies, story checkpoints and bosses.
   - Items: bag items, 26 visions, 8 party members, key items, gil.
   - Regions:
     - The linear first half is gated by the story counter.
     - After the airship, the continents (Grandshelt, Dirnado, Olderion, Zoldaad, Mysidia, Gronoa, Pharm) are gated by "unlock" items.
     - The Crystal Tower is the goal.
