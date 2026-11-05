# Ideas and to-investigate

A scratch pad for ideas that are not on the test plan yet. Each one lists what we already know, from logs, dumps and the installed mods, and what to find out.

The chapter-by-chapter progression (party, vehicles, gates, Visions, Espers) is in [docs/progression.md](docs/progression.md).

## 1. Tablet Shards

**Idea:** Tablet Shards as their own location type, and later a MacGuffin goal ("turn in N shards"). The turn-in rewards could become locations too.

**Known so far:**
- "Tablet Shard" is item 25004. Ids at 20000 and up are kept vanilla right now (`SHUFFLE_ID_LIMIT`), so shards are neither shuffled nor locations yet.
- Shards seem to be a special shiny class, `BP_MapGimmick_FieldItem_Medal_C`:
  - Map 2015, uid 4, item 25004, in `data/shinies.tsv`.
  - Medal spots 13 and 14 on map 3180 in the round 2 log.
  - Map 2020, uid 5, item 25004, found in round 5.
- They are found mostly in towns and dungeons, not on the world map. The progression overview says there are 99, across almost every town, dungeon and overworld segment.
- There is a place in the game where you turn shards in for incremental rewards.

**To find out:**
- How many shards exist, and where. Visiting maps fills `seen.tsv`, and a level-file read would give the full list.
- How the turn-in works: an NPC, shop or event table. What gives the rewards, and how the game remembers which tiers are claimed (a flag, a counter, quest progress?).
- Whether a shard count can be read and set directly (`FindInventory(25004)` / `AddInventory`).
- Apworld design:
  - Shards become progression items.
  - Each turn-in tier becomes a location gated on owning N shards.
  - A new goal option: "turn in all shards" or "collect N shards".

## 2. Skip the prologue

**Idea:** start an Archipelago game after the prologue.

**Known so far:**
- The story counter is `saveData.Progress.Progress[1]`. FFRSLib's `ffrs_story_set` accepts 1020 to 8050, and 1020 is "Leave Grandshelt Castle" (chapter 1).
- Setting the counter alone does not replay what the skipped story did. FFRSLib warns that flags set by later story stay set when going backwards, so going forwards presumably leaves the prologue's flags unset.
- The tools to fill the gap exist: story flags (`SetFlag`), party (`AddUnit`), visions, items, gil, and map travel (`ffrs_travel` / `LoadMapId`).

- The prologue is a tutorial on its own maps (round 5 log: maps 10040 and 10041, story 1000 to 1010), with a temporary Lv. 55 Dark Fina. Chapter 1 begins with Rain and Lasswell in Grandshelt.
- FFRSLib notes that the level cap is 99 only while story flag 1 is on, and 15 without it. That is one example of state the skip has to get right.
- FFRSLib's travel (`ffrs_travel <map> <slot> x y z`) writes the map and arrival point into the save, saves to a slot and reloads the field from it. Its story knob (`ffrs_story_set`) says "save and reload to apply". So the skip can work the same way: change the save, save to a slot, reload.
- The game ships its own debug menu (`ffrs_debug_menu`), and its code has a debug progress editor (`CPP_BFL_DBG_FlagSaveData` `SetProgressList` / `GetProgressList`). If the menu has a chapter jump, it sets things up the way the developers expect.

**Plan (2026-11-05).** Steps 1 to 3 are yours in game; step 4 is the build.

0. **Stop-gap for testing now:** copy your base save for each seed.
   - Connect the client, load the base save, run `ffrs_save <free slot>` (FFRSLib), then type `/bind` in the client.
   - The seed now lives in the new slot, and the base save stays clean.
   - The order matters. If you bind first, the base save's slot is linked too.
1. **What the prologue changes: save snapshots.** Mod 0.5.1's `ffrap_snapshot <name>` writes every field of the loaded save to `snap_<name>.tsv`, and `tools/snapdiff.py` compares two of them.
   1. Start a new game. As soon as the console works in the first battlefield map, run `ffrap_snapshot start`.
   2. After the Iron Giant fight, at the first moment you control Rain, run `ffrap_snapshot after_giant`. This one is optional: it separates the prologue's changes from the start of chapter 1.
   3. At the point where your base save is, run `ffrap_snapshot ch1`. Then save the game to a free slot.
   4. Load your base save and run `ffrap_snapshot base`. Comparing it with `ch1` shows which differences are only noise.
   5. Send the four `snap_*.tsv` files and `UE4SS.log`. Also say which map and spot chapter 1 begins at, and whether a cutscene plays when you arrive.
2. **The game's debug menu.** Run `ffrs_debug_menu` at the title screen and in game, and take a screenshot of each page. Look for a chapter select, a story or scenario jump, a flag or progress editor, or "new game from ...".
3. **A skip by hand.** On a fresh new game, try the simple version with FFRSLib's tools, using the base save's values from `snap_base.tsv` (`live.story`, `live.map`, `live.pawn`):
   - `ffrs_story_set <story>`
   - `ffrs_travel <map> <free slot> <x> <y> <z>`. This overwrites that slot.

   Then note what is wrong: Dark Fina still in the party, Rain or Lasswell missing, a level cap of 15, a cutscene that repeats, or a tutorial that pops up.
4. **The build.** On a new game linked to an Archipelago session, the mod applies the prologue's changes from the diff: story values, flags, party, visions and items. Then it sets the arrival map and point, saves to a slot and reloads. The apworld gets a `skip_prologue` option (on by default), sent in slot data.

**Still to find out:**
- What the prologue changes outside the save object. The reload in step 4 rebuilds what the game derives from the save at load time, but not anything that is never saved.
- Which slot the skip should save to. It must not overwrite a save the player cares about.

## 3. Non-story ("open world") mode

**Idea:** jump the story to a late point once (for example after the airship), so the world is open, and gate progress with Archipelago items instead of story events. Keep boss fights as locations if possible. The full story is long for an Archipelago run.

**Known so far:**
- After the airship most of the world is open, except places that need other story events.
- Continents as unlock items fit Archipelago well:
  - Grandshelt, Lan (02), Kol (03), Dirnado, Olderion, Zoldaad, Mysidia, Gronoa and Pharm.
  - The Crystal Tower is the goal.
  - Chest rows and shinies already carry their region, so location groups exist.
- Story gates read `{progress:N}` and `{flag:N}` conditions. These appear on shinies (`VisibleCondition`) and in `DT_MainScenario`.
- Bosses: FFRRandomizer's probe hooks `CPP_MapManager:Encount`, whose battle entry carries `battleGroupId`, `battleEventId` and `isEvent`. The randomizer already tells boss and event fights apart in the battle tables. So a battle can be started from a table entry, and a win could be detected.

**To find out:**
- Which story counter value and flags give an open world without breaking towns, NPCs or the airship. Which areas stay locked, and by which conditions.
- How to lock a continent when the story does not: block travel, warp the player back, or change map transition data.
- Bosses without their story event: can a boss fight be started on its own (a battle group plus a stage), and can a win be recorded as a check? Field bosses (map symbols) may be easier than cutscene bosses.
- Which story-only rewards (party members, visions, key items) must become Archipelago items so nothing is lost by skipping the story.

## 4. Vehicles: story event or separate unlock?

**Question:** are the Chocobo and the Airship unlocked by a story event, or by separate flags that could be flipped (or items that could be granted) on their own?

**Known so far:**
- The item table has unlock items that look like vehicle and upgrade gates:
  - 30002 "Choboco Saddle" (sic) and 30011 "Chocobo Saddle-Bike", both artifacts.
  - 29520 "Magitek Airship Passkey", a key item.
  - Radar upgrades 27006 Magi-tenna, 27007 Resonance Stone and 27008 High-Power Generator.
  - Colosseum proofs 29000–29003. The Gaia Hammer may be tied to the Fledgling proof.
- FFRS_QoL's item spawner leaves out key items (type 2) and artifacts (type 4). Its comment says they "unlock story features", with the chocobo saddle as the example. So owning the item may be the gate.
- The story gates we have seen read `{progress:N}` and `{flag:N}`. A vehicle could check either: the item, a flag, or the story counter.

**Round 5 results:**
- **Chocobo: item-gated.** `ffrap_grant item 30002` (Choboco Saddle) on a story-1130 save made the chocobo rideable. So "Chocobo" can be a plain Archipelago progression item: grant 30002.
- **29520 Magitek Airship Passkey is cosmetic.** It changes how the airship looks and does not unlock it. You had one already, from a pre-registration reward. So the airship unlock is still unknown, and probably a story flag or the story counter.
- **30011 Chocobo Saddle-Bike did nothing visible.** Its description says it turns a mounted chocobo into a motorcycle. It may be unused, or it may need a condition, for example granting it while riding, or after a map change.

**To find out:**
1. **Airship flag test.** On a save just before the chapter 4 ending, snapshot the flag array before and after the airship unlock. The flags that flip are the candidates. This needs a new console command that dumps the flags (or the changed ones) to a file.
2. **Where the airship is.** Even with the flag set, the airship may need placing on the world map (its map and point). The save's map data (`Map.mapId` plus a point id, per FFRSLib's travel notes) is where to look.
3. **Saddle-Bike.** Try 30011 again while riding a chocobo, and after a map change.
4. **What this means for the apworld:**
   - "Chocobo" (item 30002) becomes a progression item now. Locations become gated by it: Kolobos and Felicitas.
   - "Airship" becomes a progression item once its flag is known: Sanctums, volcanoes, ice islands and Whirlpool Hollow.
   - Radar tiers gate the world-map treasures.
   - This pairs with the open-world mode (idea 3). In story mode, if the story hands out the saddle, that vanilla grant would need blocking for the item to matter.

## 5. Key items and gates from the item table

**Known so far:** these ids are in `data/item_names.tsv`, and they match gates in [docs/progression.md](docs/progression.md):

| Item | Id | Gate |
|---|---|---|
| White Jade Stone | 20005 | Holy, which clears the Bog of No Return (Gronoa west, Odin) |
| Level 1, 2, 3 Lab Key Cards | 20009–20011 | Research Center Ruins |
| Tunnel Key | 20008 | probably the Zoldaad tunnels |
| Dungeon Key, Throne Room Key | 20019, 20021 | Zoldaad Castle |
| Ruby Fragment | 20030 | Carbuncle (3 needed) |
| Broken Sword Hilt, Blade | 20031, 20032 | Odin (Iron Splitter) |
| Magitek Armor Key | 29500 | unknown |
| Archwitch's Grimoire | 29510 | unknown |
| Tablet Shard | 25004 | Tablet Shard turn-in (idea 1) |

**To find out:**
- Which of these does the game check by item, rather than by a story flag set at the same time?
- Each one checked by item could become an Archipelago progression item. That is the start of real logic, even with the story kept.
