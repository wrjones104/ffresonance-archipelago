# Side quests: design draft

How side quests become locations on an open world seed. The quest rewards go into the multiworld. The quest items stay where the game puts them.

**Asked for (2026-11-17, the user):** side-quest rewards in the pool. The user was not sure about the quest key items, because the quests seem to set flags that do not care about the items. Example: three Ruby Fragments from Archipelago do not wake Carbuncle's stele; only the three world-map spots do.

**Built (round 78, world 0.30.0, mod 0.61.0):** sections 4 to 6, for 28 quests. The option is off by default until a round shows it works.

**Decided (2026-11-17):**
- A quest's reward is a location. Its vanilla reward goes into the pool.
- Quest items that the game never tests (section 2) stay vanilla and leave the pool.
- Key items that the game does test (Throne Room Key, Cabin Key, the Lab Key Cards, the Dungeon Key, Adamantite, the Arena proofs) stay in `shuffle_key_items`.

Facts here come from the game data dump (`dump/tables`, `dump/maps`) unless a round is named. The off-line pass was on 2026-11-17, before round 78. Related: [IDEAS.md](../IDEAS.md) ideas 21 (NPC gifts), 32 (radar), 33 (Mechabo), [bosses.md](bosses.md) (tier 2: fights behind a side quest), [logic.md](logic.md) section 5.

## 1. How a side quest runs in the game

- **Each quest has its own counter,** `{progress:N}` with N not 0. A talk row moves it on (`ProgressList`), and each step's map actor tests it. The main story counter (`{progress:0}`) only gates the start.
- **The game's quest log** is `Datatable/Request/DT_RequestData`: 33 quests, each with an English name, `AcceptCondition`, `CompletionCondition` and `Prize`. This is the list of side quests a player sees, so it is our list too (section 3).
- **A step's actor** is an NPC (`m_EventSettings`, with `m_VisiblFlagCondition`), a trigger zone, an interact spot or a field item. Each holds `Condition` and `EventId` pairs. The row it runs can chain on (`ContinuousEventList`), offer a choice (`ChoicesBranchEventList`) or start a fight (`encountGroupId`, then the group's `battleFinishEventId`).
- **A reward** is the step row's `ObtainItemList`: items, and gil as item `-1`.
- **No quest row writes the story counter.** The only side-counter row that does is `C01_018_01` (story 1110), the Grandshelt Castle quest's start, which is a story scene.

## 2. Quest items: what the game tests

Every quest-item gift row also moves the quest's counter. The next step tests the counter, never the item. So an Archipelago copy does nothing, and the player still has to visit the vanilla spot. The turn-in rows have a `ConsumeItemList`, but taking an item the bag does not hold is no gate.

| Item | Quest | Given by | Next step tests |
|---|---|---|---|
| Ruby Fragment x3 (20030) | Carbuncle | `Summon660_Carbuncle_02`, `_03`, `_04` (world-map field items) | `{progress:45}` 20, 30, 40 |
| Broken Sword Hilt, Blade (20031, 20032) | Iron Splitter (Odin) | `Summon670_Odin_02`, `_03_END` | `{progress:17}` |
| Viscus Vitae, Rushroom, Pure Water, Convalescence Draught, Super Salubrious Salad Stem (20023 to 20027) | Medicinal Mission | `SubEv_C03_TreatmentGirl_*` | `{progress:41}`, flags 321 to 325 |
| Portrait of Dario, Dario's Letter (20028, 20029) | Rogue Rebel | `SubEv_C04_Spy_01`, `_04_True` | `{progress:42}` |
| Dew of Reprieve (20020) | Dream of an Idealist | `SubEv_C01_Rain_ItemGet` | `{progress:31}` |
| Magi-tenna (27006) | the treasure radar | Gaberada free talk | flag 1405, set by the same row (the mod's Progressive Radar sets the radar's state itself) |

Items the game does test, by condition or Blueprint:

| Item | Test |
|---|---|
| Throne Room Key (20021) | `{item:20021}` on the throne room door (map 3160) |
| Cabin Key (20033) | `{item:20033}` (Pharm) |
| Adamantite (20016) | `{item:20016}>=1` before each of Aileen's weapons |
| Lab Key Cards 1 to 3 (20009 to 20011) | the doors' Blueprint, `Gim_EV_HaveKeyItemLV1` to `LV3` (round 56) |
| Dungeon Key (20019) | its door (the user's logic, `data/gates.tsv`) |
| Arena proofs (29000 to 29002) | `{item:2900N}>=1` |
| Resonance Stone, High-Power Generator (27007, 27008) | the airship's radar steps (the Progressive Radar replaces them) |

None of the 11 untested quest items (20020, 20023 to 20032) is in a chest or a shiny, so taking them out of the pool frees no location. White Jade Stone, Black Jade Stone, Magic Tome and Tunnel Key (20005 to 20008) have no item test in the data either. They are not side-quest items, so they need their own check.

## 3. The quests

All 33 from the quest log. "Done" is the test that reports the check: the counter at or past the value the reward row writes. It is the log's `CompletionCondition` for every quest but two: Mechabo Evolved (the log says 60, the reward row `_06` writes 70) and The Admirable Apprentice (the log says 50, the reward row writes 60). The mod tests `>=` throughout. "Places" lists where the steps happen, by continent (from the steps' map actors). The world map (1000) has steps in many of them; the gen step places those by position.

| ID | Quest | Counter | Done | Reward (vanilla) | Continents | Needs | First pass? |
|---|---|---|---|---|---|---|---|
| 0 | A New Leaf | 1 | `>=50` | Knight's Medallion | Grandshelt, Olderion, airship deck | Airship | yes |
| 1 | The Twin Titleholders | 2 | `>=50` | Crest of Criticality | Gronoa, Grandshelt (Lost Cave) | | yes |
| 2 | Shimmering Reflections | 3 | `>=50` | Blessed Pendant | Mysidia, Grandshelt, Lanzelt, Olderion | | yes |
| 3 | Beyond the Blue | 4 | `>=50` | Chocobo Nitro | Dirnado, airship | Airship | yes |
| 4 | Nichol's Duty | 5 | `>=60` | Enchanted Ring | Olderion | | yes |
| 5 | Last Respite | 6 | `>=50` | Moonlight Ring | Grandshelt, airship deck | Airship | yes |
| 6 | Token Legacy | 7 | `>=60` | Trick Coin | Zoldaad; starts at any inn | gil for the inn | yes |
| 7 | Mysidia, Ever Blooming | 8 | `>=50` | Amulet of Magic Absorption | Mysidia | | yes |
| 13 | Rear Support, Ahoy! | 28 | `>=40` | Magicite Shard, 500 gil | Lanzelt | 4 Turbo Ethers (quest board) | yes |
| 14 | Dream of an Idealist | 31 | `>=60` | Flamberge, 500 gil | Grandshelt, Lanzelt | | yes |
| 16 | Secrets Unearthed | 30 | `>=90` | Monk's Prayer Beads, Magicite Shard | Kolobos | Chocobo? | yes |
| 17 | Arise, Mechabo! | 16 | `>=20` | Magicite Shard | Dirnado | the start fix (idea 33) | after the fix |
| 26 | Mechabo Evolved | 16 | `>=70` | Magicite | Dirnado | enemy drops | after the fix |
| 27 | Mechabo Unleashed | 16 | `>=100` | Magicite Cryst | Dirnado, airship | Airship, enemy drops | after the fix |
| 18 | Lyrical Riddles | 32 | `>=40` | Magicite Shard, 800 gil | Dirnado | | yes |
| 19 | Elven Maven | 34 | `>=40` | Magicite Shard, 800 gil | Dirnado | | yes |
| 20 | The Weight of Mercy | 33 | `>=50` | Iwakirimaru, 500 gil | Lanzelt, Kolobos | | yes |
| 21 | The Tide from the Sky | 35 | `>=50` | Magicite Shard, 1500 gil | Olderion | | yes |
| 22 | Errand's End | 37 | `>=50` | Amelia, Magicite | Zoldaad, Olderion | Token Legacy done | yes |
| 23 | Forger of Wills | 38 | `>=40` | Aileen, Magicite | Dirnado, Lanzelt, Zoldaad | | yes |
| 24 | Victoria Revivified | 39 | `>=50` | Victoria, Magicite | Mysidia | | yes |
| 25 | The Call from Beyond | 36 | `>=60` | Camille, Magicite | Zoldaad (Phantom Train) | | yes, if the train runs |
| 28 | The Shield of the Weak | 40 | `>=50` | Charlotte, Magicite Cryst | Grandshelt, Lanzelt, Kolobos | | yes |
| 29 | Medicinal Mission | 41 | `>=50` | Magicite Shard, 1500 gil | Olderion | | yes |
| 30 | Rogue Rebel | 42 | `>=70` | Magicite, Rose Circlet | Zoldaad | | yes |
| 31 | O General! My General! | 48 | `>=50` | Wilhelm, Magicite Cryst | Zoldaad (Weapons Factory) | The Call from Beyond done | yes, if the factory opens |
| 32 | The Admirable Apprentice | 47 | `>=60` | Ayaka, Magicite Cryst | Pharm, Olderion, Zoldaad, Dirnado | | yes |
| 33 | "Reunion" | 53 | `>=40` | Magicite, 2500 gil | Gronoa, Mysidia, Dirnado | Elven Maven and Lyrical Riddles done | yes |
| 34 | Mog Tag | 44 | `>=20` | Mist X-Potion | Mysidia | | yes |
| 35 | More Mog Tag | 44 | `>=40` | Magicite | Mysidia | | yes |
| 36 | Even More Mog Tag | 44 | `>=60` | Magicite Cryst | Mysidia | | yes |
| 37 | Battle at the Big Bridge | 54 | | Genji Gloves (twice), Genji Armor | Lanzelt, Olderion, Zoldaad | Gilgamesh's fights | no: bosses.md tier 2 |
| 38 | Iron Splitter | 17 | | Odin | Gronoa, Mysidia | Odin's Shadow | no: bosses.md tier 2 |

That is 31 locations in the first pass: 28 now, and the three Mechabo quests once their start is fixed.

**Notes from the data:**
- **Every accept test holds at story 8000** (`{progress:0}>=N`), except Arise, Mechabo!. Its start row `C02_219_02` tests `{progress:0}==2120` (idea 33).
- **Last Respite's last step** (Archwitch Fina on the deck) is shown only while `{progress:0}<8050`. The story reaches 8050 in the Crystal Tower, so the reward is lost after the tower's upper floors.
- **Quest chains:** Errand's End starts only after Token Legacy (`{progress:7}>=60`). O General! starts only after The Call from Beyond (`{progress:36}==60`). "Reunion" needs Elven Maven and Lyrical Riddles (`{progress:34}>=40&{progress:32}>=40`).
- **Token Legacy starts at an inn:** the rest choice runs `ChrEv_0070_001_02` when story is 5060 or more and the gil covers the fee.
- **Medicinal Mission has three ways through.** The Viscus Vitae fight (group 9119) sets flag 321. Rushroom (a world-map spot) and Pure Water (Cave of Waters) set 322 and 323. The Salad Stem path costs 50,000 gil at the Secluded Dwelling (map 11000). Any one way finishes it.
- **Rear Support, Ahoy!** step 3 is a quest-board delivery (`DT_Request_QuestData`, quest 1000): 4 Turbo Ethers (item 20).
- **Mog Tag:** round 84: each reward row holds only the location's item, so the patch left it empty, and an empty row showed "You obtained a vision!" with no chest pop-up to write into. Rows of a quest with no `before` keep the stand-in Potion when they would be left empty.
- **Mog Tag:** one catch per tier, from any of the three moogles. Each moogle has its own reward row per tier (`SubEv_C05_MogChase_06_NPC0n_0t`), and each tier has a `_loot` copy used below story 5040. `SubEv_C05_MogChase_Timeover` sets the counter back to 0.
- **Fights inside quests:** 9081 (Dream of an Idealist), 9082 (Weight of Mercy), 9086 (Tide from the Sky), 9095 (Call from Beyond), 9104 and 9105 (Shield of the Weak), 9107 (Victoria), 9119 (Medicinal Mission), 9134 (Ayaka), 9901 (Twin Titleholders), 9902 (Beyond the Blue), 9906 (Nichol's Duty).
- **Seven quests give a vision:** Amelia, Aileen, Victoria, Camille, Charlotte, Wilhelm and Ayaka. With `shuffle_visions` on, these are already in the pool, and today the quest gives a second copy.
- **Character quests also give stat bonuses** ("Attribute Bonus: Rain"), from the row's unit settings. They stay vanilla.

**Also with rewards, outside the quest log** (a later pass):
- Chloe's weapon (`SubEv_C01_Chloe_Weapon_02`, Ancient Bow, counter 50, Chamber of Arms). It starts after Secrets Unearthed.
- The Kol moogle (`SubEv_C01_Moogle_01`, Magicite Shard).
- Zoldaad Castle's events (`SubEv_Dng_06Zol_44_GimEv_04` Turbo Ether, `_06` Hairpin of Grace).
- The Stone Statue (`SubEv_StoneStatue_Peace_LightUp`, Tyr's Armor). No map actor runs it directly, so something else (a sequence or Blueprint) does.
- Aileen's eight weapons (section 7).
- The rope-jumping game (`Nawatobi`, 6 rewards) and the free-talk gifts (idea 21).
- Gone at our start: the Grandshelt Castle quest (counter 15, Phoenix Down x3). Its start is a story scene at story 1100.

## 4. What the mod does

The same pattern as the radar treasures and the cave masters:

1. **Blank the reward.** Each location's reward row loses the location's item (`item` in `quests.lua`). Until round 81 it was swapped for the stand-in Potion (`BOSS_STAND_IN`) so the game's own pop-up would show; round 81 showed that a row left empty still shows it and still completes the quest. Round 84 showed it can show "You obtained a vision!" instead, so since round 88 a row left empty keeps the stand-in again. A vision comes out of the row: with `shuffle_visions` on it is in the pool already, and with it off its location holds it, as a sanctum holds its own. Since round 98 a quest's second reward (gil, a second item, or the vision) is a location of its own (`key2` and `item2` in `quests.lua`), and comes out too. Before, the gil and a second item (Secrets Unearthed's Magicite Shard, Rogue Rebel's Rose Circlet) stayed in the row. A seed from before round 98 sends no `cfg quest2`, and the mod leaves them in. The engine's list cannot drop one entry, so a row with a vision is emptied and built again.
2. **See the check.** Each tick, read the quest's counter (`game.ProgressValue`) and test it against "Done". A met test reports `quest:<id>` (Mog Tag tiers: `quest:34` to `quest:36`; Mechabo: `quest:17`, `quest:26`, `quest:27`), and `quest2:<id>` for its second reward (round 98). A check stays sent once sent, so the Mog Tag reset does no harm.
3. **Show the item.** Overwrite the pop-up with the scouted item, as for bosses (`BOSS_POPUP_TRIES`). Where the game's pop-up comes before the counter moves (Token Legacy, Mog Tag), it is written while the counter still reads its value before, on the map the reward row runs on (`at` in `quest_steps.tsv`, round 88). The Quests screen's Rewards name the scouted item too: the location's entry in `DT_RequestData`'s `Prize` becomes a text entry (round 88). A quest with two locations has one pop-up with both names, one line each, and two Rewards entries (round 98). With `hide_quest_rewards` (round 103, off by default), the Rewards entries read `???` with no colour; the pop-up still names the item.
4. **Mechabo's start** (idea 33): on a seed save, when `{progress:16}` reads 0, set it to 10.

The quest rows that give quest items are not touched.

## 5. Logic

- **A quest needs every continent its steps use.** Each step's map gives a continent, by its doors (as for chests). A world-map step gets one from its position (`data/continents.tsv`). This answers the scratchpad's note about quests that send you to other continents.
- **Where one event starts a step in several places, any of them does** (Token Legacy starts at any inn). **Where different events start it, all are needed** (Forger of Wills: three NPCs on three continents, each moving the counter on by one, in any order). `quest_steps.tsv` keeps each step's starting event (`start`) for this.
- **Airship maps** (20001 Airship, 20002 Deck) need the Airship.
- **Quest chains** are rules on the earlier quest's location: Errand's End needs Token Legacy, O General! needs The Call from Beyond, "Reunion" needs Elven Maven and Lyrical Riddles.
- **Past a boss on foot** (round 97, the user): a step on a map past Liquid Thunder (Dirnado but Dilmagia) gives the quest the same rule as the chests there: Liquid Thunder's needs, or the Airship. Lyrical Riddles and Elven Maven end in the Dwarven Forge, and were in logic from the start. The fix also caught Beyond the Blue (a step in the Mobliz Shipyard), The Admirable Apprentice (a step on Mt. Thunderclap's upper ledge) and "Reunion" (it needs the first two).
- **Fights:** the groups listed in section 3. First pass: no rule beyond the region. Look at their levels against the scaling once the list is in; boss logic may want some of them.
- **Gil:** Token Legacy needs an inn fee, Rear Support needs 4 Turbo Ethers (sold in shops). No rule.
- **Party members:** no quest step tests the party in the data. Character quests are named for a member but do not need them. But Beyond the Blue needs a party of 4 (a tester, round 112): `party` in `data/quests.tsv`. The starting party counts; with party members not shuffled and fewer than 4 at the start, it is filler only.
- **Keys:** Token Legacy's last step is past the Throne Room Key's door (round 112, `data/gates.tsv`). A quest that starts after another takes its keys too.

## 6. The world

- **A new option, `include_side_quests`** (off by default until a round shows it works, then on; on by default since round 121, for v0.33.0). Its locations are `quest:<id>`, kind `quest`, named "Quest: <name>" (the game's English quest name).
- **Each location's vanilla item:** the reward's first item (not its gil, and not its vision). It goes into the pool like a chest's.
- **Second rewards (round 98, the user):** 17 quests give a second reward, and each is a location of its own, `quest2:<id>` (AP id 6,100,000,000 + quest), named "Quest: <name> - Second Reward", with the quest's own logic. 8 give gil (its Gil item goes into the pool), 2 a second item (Secrets Unearthed's Magicite Shard, Rogue Rebel's Rose Circlet), and 7 a vision (in the pool already with `shuffle_visions`, else held there). The stat bonuses of the character quests are not items and stay with the quest.
- **The key-item pool:** take the 11 untested quest items (20020, 20023 to 20032) out of `PROGRESSION["key"]` whether or not the option is on. They unlock nothing for anyone today.
- **Slot data:** the option goes in `fill_slot_data` and back in `take_slot_data` (Universal Tracker, round 72).

## 7. Later

- **Aileen's weapons** (`C06_AileenWeapon_*`, chapter 6, on the deck). Each of the eight costs one Adamantite (`{item:20016}>=1`, then a `ConsumeItemList`).
  - **How the game runs it (round 105, from the dump):** Aileen shows from `{progress:38}>=40` (Forger of Wills). With story 6000 or more, her first talk sets the counter to 60. At 60 with an Adamantite she offers the eight weapons, each only while none of it is held (`{item:W}==0`; equipped gear counts). Each forge row (`C06_AileenWeapon_<name>_Yes`) gives its weapon, takes one Adamantite and sets flag 1236. The row after it (`_06`) ends the forge (counter 70) as soon as Rain's weapon is held, so in the base game Rain's comes last. Nothing else sets or tests flag 1236 or takes Adamantite.
  - **Built (round 105, world 0.32.0 build e38986f1, mod build 395095c2):** `include_aileens_forge` (off by default). Location `forge:n` is the nth weapon forged, so its rule needs n Adamantite, with Forger of Wills' steps and the deck. Locations by weapon would not work: logic cannot tell which ones a player forges first. The pool has eight Adamantite: the forge's locations hold the copies not in the pool already. The forge still gives the weapon. The mod counts forges by the weapons held, so the count is in the save and works on any computer. The weapons are not in the pool, since a received one would hide its choice. `G.ForgePatch` makes `_06` end the forge only with all eight held. Flag 1236 tells the mod a forge is under way, for its pop-up, and the mod turns it off each time. "Progressive Adamantite" is plain Adamantite: while the Adamantite received outnumber the weapons forged, an empty bag gets one back, in case the game keeps only one copy (to find out in round 105). The three chests that hold Adamantite stay vanilla, so their copies are free forges out of logic.
- **Battle at the Big Bridge, Iron Splitter, the espers and Ultima Weapon** go with the boss work (`bosses.md`, tier 2).
- **Making fetch items real.** The mod could move a counter when an item comes in, as the Progressive Radar does: three Ruby Fragments from Archipelago set `{progress:45}` to 40. Each quest needs its own code, so only if players ask.

## 8. Order of work

1. **Off-line (done, round 78):** a `tools/gen_from_dump.py` step that writes `data/game/quests.tsv` (the quest log: id, name, accept, done, prize, counter) and `data/game/quest_steps.tsv` (each step's counter value, row, map, actor, condition, fight, reward). The 2026-11-17 pass did this with scratch scripts; this makes it a table. `tools/gen_apworld_data.py` builds the locations and their continents from it.
2. **World (done, round 78):** the option, the 28 locations, the rules, the key-item change, tests.
3. **Mod (done, round 78):** the reward patch, the counter checks, the pop-up, the Mechabo start. Tests with `lupa`.
4. **Round 78 in game:**
   - Rear Support, Ahoy! (Lanzelt, short): the pop-up shows the scouted item, the check is sent, the 500 gil still comes.
   - A vision quest with `shuffle_visions` on: no second copy of the vision.
   - Mechabo: Verun is at the Dwarven Forge, and whether the forge plays his first meeting.
   - The Phantom Train (map 3121) and the Weapons Factory (3130) can be reached on our start.
   - **Round 78 results:** six quests sent their checks, and the normal ones showed only the Archipelago item. The character quests with a stat bonus (Nichol's Duty, Last Respite, A New Leaf) showed the stand-in Potion: their counter moves at the start of a long reward scene, and the mod gave up on the pop-up after 30 s, or wrote into the stat bonus dialog, which says "obtained" but has no item line. Round 79: the wait counts only time on the field, and only a dialog with the item line is written (`docs/playtesting.md`).
5. **Later rounds:** the Mechabo quests as locations, then section 7.

## 9. To find out

- Whether the Phantom Train and the Weapons Factory open on our start. Both are story places in Zoldaad.
- Whether a swapped reward shows the stand-in pop-up for a quest row as it does for boss win rows.
- What starts `SubEv_StoneStatue_Peace_LightUp` and `SubEv_C09_UltimaWeapon_04_GetItem` (no map actor runs them).
- The levels of the quest fights against our scaling.
