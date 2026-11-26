"""main.lua against a stub game module and stubbed UE4SS functions (Lua 5.4 via lupa): the item
queue, checks, sessions, save binding, the per-save count, the skip command, the title entry, the
Archipelago new game, the item feed and the chest pop-up. Each numbered section is one feature."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

import os
import time
import shutil
import sys
import re
import tempfile

from lupa import lua54

SRC = str(paths.MOD)                  # the repo's mod folder
# A scratch copy, so the repo is never written. It sits in a Mods folder of its own, as installed,
# so the tests can put other mods next to it.
MODS = tempfile.mkdtemp(prefix="ffrap_main_")
WORK = os.path.join(MODS, "FFRArchipelago")
if os.path.exists(WORK):
    shutil.rmtree(WORK)
shutil.copytree(SRC, WORK, ignore=shutil.ignore_patterns("ap_*.txt", "*.tsv", "ffrap_dump.txt"))
SCRIPTS = os.path.join(WORK, "Scripts").replace("\\", "/")
VERSION = re.search(r'local VERSION = "([^"]+)"', open(os.path.join(SRC, "Scripts", "main.lua"), encoding="utf-8").read()).group(1)


def path(name):
    return os.path.join(WORK, name)


def read(name):
    p = path(name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def runtime():
    L = lua54.LuaRuntime(unpack_returned_tuples=True)
    L.execute(f'package.path = "{SCRIPTS}/?.lua;" .. package.path')
    return L


# 1. compile
L = runtime()
for name in ("game", "bridge", "main"):
    src = open(os.path.join(SCRIPTS, name + ".lua"), encoding="utf-8").read()
    ok, err = L.eval("function(s, n) local f, e = load(s, n) return f ~= nil, e end")(src, name)
    assert ok, f"{name}: {err}"
print("compile: ok")

# 2. the real game.BlankChests against a fake composite table, a parent table and live chests
L = runtime()
L.execute(r'''
local function row(map, id, item, n, money, trap)
  return { mapId = map, ID = id, ItemId = item, ItemNum = n, Money = money, IsTrap = trap or false }
end
local function dtable(name, rows, parents)
  local t = { rows = rows, name = name, ParentTables = parents or {} }
  function t:IsValid() return true end
  function t:GetFullName() return self.name end
  function t:ForEachRow(fn) for k, r in pairs(self.rows) do fn(k, r) end end
  return t
end
parent = dtable("parent", { a = row(3020, 1, 10100, 1, -1), b = row(3020, 2, -1, 1, 300), t = row(3020, 3, 5, 1, -1, true) })
root = dtable("root", { a = row(3020, 1, 10100, 1, -1), b = row(3020, 2, -1, 1, 300), t = row(3020, 3, 5, 1, -1, true) }, { parent })
local function actor(r)
  local a = { m_Id = r.ID, m_IsOpen = false, m_UniqueId = 100 + r.ID, TypeData = { ID = 100 + r.ID }, m_TreasureBoxData = r }
  function a:IsValid() return true end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  return a
end
live = {}
function StaticFindObject(p) if p:find("TreasureBox") then return root end return nil end
function FindAllOf(c) if c == "CPP_MapGimmick_TreasureBox" then return live end return nil end
function FindFirstOf() return nil end
G = (require("game"))
''')
lua = L.eval
assert lua("G.BlankChests(true)") == 4                       # 2 rows x 2 tables; the trap row is skipped
# Round 81: blank is nothing (ItemId -1, ItemNum 0, Money 0), which still opens with its pop-up
assert (lua("root.rows.a.ItemId"), lua("root.rows.a.ItemNum"), lua("root.rows.a.Money")) == (-1, 0, 0)
assert lua("parent.rows.b.Money") == 0 and lua("root.rows.t.ItemId") == 5
# a chest spawns while blanking is on: it copies the already-blank row
L.execute("live[1] = (function() local r = {} for k, v in pairs(root.rows.a) do r[k] = v end return r end)()")
L.execute('''local r = live[1]; local a = { m_Id = r.ID, m_IsOpen = false, m_UniqueId = 101, TypeData = { ID = 101 }, m_TreasureBoxData = r }
function a:IsValid() return true end function a:HasAnyInternalFlags() return false end function a:HasAnyFlags() return false end
live[1] = a''')
assert lua("live[1].m_TreasureBoxData.ItemId") == -1
assert lua("G.BlankChests(false)") == 5                      # 4 table rows + the live chest
assert lua("live[1].m_TreasureBoxData.ItemId") == 10100, "0.2.0 bug: live chest stayed blank"
assert lua("root.rows.b.Money") == 300 and lua("parent.rows.a.ItemId") == 10100
assert lua("G.BlankChests(false)") == 0                      # idempotent
print("blanking: ok")

# 3. main with a stub game (0.3.1)
STUB = r'''
local G = { log = {}, ready = true, story = 1020, map = 2002, saveMap = 3020, saveOpen = {} }
function G.InGame() return G.ready end
function G.CurrentMap() return G.map end
function G.MapId() return G.saveMap end
function G.StoryCounter() return G.story end
function G.PartyIds() return {1001} end
function G.Toast() return false end
G.POPUP_COLORS = { on = false }
G.QUEST_COLORS = { on = false }
G.GIFTS = { { key = "gift:1400", flag = 1400, row = "FEV_Town_01Gra_05_981_01", map = 2016, x = 25910, y = -4960 },
            { key = "gift:1405", flag = 1405, row = "FEV_Town_08Gro_01_1540_01", map = 2150, x = 4635, y = -4670, radar = true },
            { key = "gift:1401", flag = 1401, row = "FEV_Town_09Pha_01_1232_01", map = 2170, x = 1100, y = 20810 },
            { key = "gift:1413", flag = 1413, row = "FEV_Town_09Pha_01_9012_02", map = 2170, x = 1165, y = 525 } }
function G.GiftsPatch(radar) G.giftPatches = (G.giftPatches or 0) + 1; G.giftRadar = radar; return 9 end
function G.QuestColorHook() if G.QUEST_COLORS.hooked then return nil end G.QUEST_COLORS.hooked = true return "registered" end
function G.QuestRewardColors(spans, say)
  G.questSpans = spans
  local out = {}
  for label in pairs(spans) do if not G.questDone then out[#out + 1] = "coloured: " .. label end end
  G.questDone = #out > 0 or G.questDone
  return out
end
function G.GetFlag(i) return false end
-- the Archipelago page is on by default; its own section below replaces this
G.APMENU = { Ensure = function() end, Page = function() return nil, "not open" end, Unstick = function() end,
             Unlist = function() return false end }
function G.IsChestOpenInSave(m, uid) return G.saveOpen[m .. ":" .. uid] == true end
function G.SaveOpenRows(m)
  return setmetatable({}, { __index = function(_, uid) if G.saveOpen[m .. ":" .. uid] == true then return true end end })
end
function G.ChestSaveKeys(m, c) return "save keys of " .. tostring(c.uniqueId) end
function G.GameUniqueId(actor)
  if actor and actor.broken then return nil, "no such function" end
  return actor and actor.gameUid
end
G.chests = {
  { uid = 1, open = false, rowMap = 3020, rowId = 1, uniqueId = 7, typeId = 7, itemId = 209, itemNum = 3, money = -1 },
  { uid = 3, open = false, rowMap = 3020, rowId = 3, uniqueId = 63, typeId = 63, itemId = 7, itemNum = 4, money = -1 },
  { uid = -1, open = true, rowMap = -1, rowId = -1, uniqueId = 54, typeId = 54, itemId = -1, itemNum = 1, money = -1 },
  { uid = -1, open = true, rowMap = -1, rowId = -1, uniqueId = 42, typeId = 42, itemId = 5, itemNum = 1, money = -1 },
}
function G.LiveChests() return G.chests end
G.shinies = {
  { uid = 30, open = false, itemId = 16, itemNum = 3, money = -1, class = "BP_MapGimmick_FieldItem_C", visible = "" },
  { uid = 113, open = true, itemId = -1, itemNum = 1, money = -1, class = "BP_MapGimmick_FieldItem_C", visible = "{progress:30}>=20" },
}
function G.LiveFieldItems() return G.shinies end
function G.GrantItem() return "ok", "" end
function G.ApplyRates(e, g, m) G.rates = { e, g, m } return 0 end
function G.ApplyEncounterTables(on, rate) G.encounterTables = { on, rate } return 0, 1 end
function G.ApplyPlayerEncounter(on) G.playerEncounters = on return 0 end
function G.ReadOptionValues() return G.menuValues end
function G.EnsureOptionRows(current)
  G.menuChecks = (G.menuChecks or 0) + 1; G.menuSeed = current
  if G.menuRowsIn then return 0 end
  G.menuRowsIn = true; G.menuAdds = (G.menuAdds or 0) + 1; return 6, "rows"
end
function G.AddOptionRows(say, current) return true, "rows", 6 end
G.SHIPYARD_MAP = 3060
function G.WakeShipyardElevators() G.shipyardCalls = (G.shipyardCalls or 0) + 1; return 0 end
G.LIFT_RESETS = { [3200] = { [13] = 0 } }
G.RAFT_MAPS = { [3080] = true }
G.liftResets = {}
function G.ResetRides(here)
    G.liftResets[#G.liftResets + 1] = here
    if here ~= 3200 and G.liftPending then G.liftPending = false; return { "3200:13 1 -> 0" } end
    return {}
end
function G.RideState(m) if m == 3200 then return G.liftStops end end
G.TOWER_TOP = { map = 3280, x = 15890, y = -55300, reach = 500 }
function G.SealTowerTop(sealed) G.sealed = sealed; return 0 end
function G.UnlockVision() return "ok", "" end
function G.HasVision(id) return (G.owned or {})[id] == true end
function G.AddUnit() return "ok", G.unitDetail or "in the active party" end
function G.VisionShopGuard() return nil end
G.CRYSTALS = { { event = 10, map = 10200, flag = 1000 } }
function G.CrystalsPatch() G.crystalPatches = (G.crystalPatches or 0) + 1; return 3 end
G.BOSSES = { { group = 9079, flag = 146 }, { group = 9083, flag = 215 } }
function G.BossesPatch() G.bossPatches = (G.bossPatches or 0) + 1; return 2 end
G.QUESTS = { { key = "quest:13", counter = 28, value = 40, map = 2030, before = 30, rows = { "SubEv_C01_Zairu_04" },
               key2 = "quest2:13", item2 = -1 },
             { key = "quest:6", counter = 7, value = 60, map = 3160, before = 50, rows = { "ChrEv_0070_006_01" } },
             { key = "quest:34", counter = 44, value = 20, rows = { "SubEv_C05_MogChase_06_NPC01_01" } } }
function G.QuestsPatch(second) G.questPatches = (G.questPatches or 0) + 1; G.questSecond = second; return 2 end
G.MECHABO = { counter = 16, start = 10, delivered = 219, lid = 1004, tackle = 404110, requests = { 17, 26 }, hunt = 1001 }
function G.BoardQuest(id) return G.board or "not on the board" end
function G.OrderRequestQuests(ids) local out = G.toOrder or {}; G.toOrder = nil; return out end
function G.RequestStates(ids) local out = {} for _, id in ipairs(ids) do out[id] = G.requestStates and G.requestStates[id] or "not in the log" end return out end
function G.UnitHasSkill(id, skill) return G.skills and G.skills[skill] end
function G.QuestPrizes(labels) G.prizes = labels; local n = 0; for _ in pairs(labels) do n = n + 1 end; return n end
function G.MechaboPatch() G.mechaboPatches = (G.mechaboPatches or 0) + 1; return 2 end
-- the save's visited maps, and the dungeon fast travel rule as last set
G.visited, G.AIRSHIP_MAPS = {}, { 20001, 20002 }
function G.MarkVisited(maps)
  local marked = {}
  for _, m in ipairs(maps) do
    if not G.visited[m] then G.visited[m] = true; marked[#marked + 1] = m end
  end
  return marked
end
function G.DungeonFastTravel(on)
  if G.fastTravel == on then return nil end
  G.fastTravel = on
  return on and "allowed from dungeons" or "refused from dungeons again (the game's rule)"
end
G.palaceSyncs = 0
function G.PalaceSync()
  G.palaceSyncs = G.palaceSyncs + 1
  if G.palaceSyncs == 1 then return "palace: 5 shards held, 1 steps paid, progress 43 at 11" end
  return nil
end
function G.SyncStoryBossTrigger(say)
  G.storyBossSyncs = (G.storyBossSyncs or 0) + 1
  if G.map == 3000 then return true, "group 9004: 2 triggers" end
  return nil, "no story boss on map " .. tostring(G.map)
end
function G.SetStoryBossReady(on) G.storyBossReady = on; return true end
function G.BlankFieldItem(s) G.blanked = (G.blanked or 0) + 1; return true end
function G.SyncSlotLevel() G.slotSyncs = (G.slotSyncs or 0) + 1; return false end
function G.SetUnitLevel(id, level) G.leveled = { id = id, level = level }; return true, "level " .. level end
function G.PartyLevel() return G.partyLv or 7, "1001:7" end
function G.StoryCounter() return G.story end
function G.SetFlag() return "ok", "" end
-- Round 77: the save stamp, one per save object (a save's flags go where the save goes)
G.STAMP_MAX, G.stamps, G.stampWrites = 4095, {}, 0
function G.SeedTag(key) local h = 0; for i = 1, #key do h = (h * 31 + key:byte(i)) % 2047 end; return h + 1 end
function G.ReadSaveStamp() local s = G.stamps[G.saveObj] or { 0, 0 }; return s[1], s[2] end
function G.WriteSaveStamp(count, tag)
  local s = G.stamps[G.saveObj]
  if s and s[1] == count and s[2] == tag then return 0 end
  G.stamps[G.saveObj] = { count, tag }; G.stampWrites = G.stampWrites + 1; return 1
end
G.blankCalls = {}
function G.BlankChests(on) G.blankCalls[#G.blankCalls + 1] = on return 0 end
G.saveObj, G.saveTicks, G.slotOf = 'SD_1', '0', {}
function G.SaveObjectName() if G.ready then return G.saveObj end return nil end
function G.SavedTicks() return G.saveTicks end
function G.SlotForTicks(t) return G.slotOf[t] end
function G.DumpChests() end
function G.DumpFieldItems() end
function G.ExportChests() return true, "238 rows" end
G.SKIP_FROM_MIN, G.SKIP_FROM_MAX, G.skipRuns, G.reloads = 1005, 1005, 0, {}
G.SKIP_ARRIVAL = { map = 3001 }
G.OPEN_STARTS = { dock = { name = "dock", story = 8000, map = 3280, x = -2704.8, y = -171166.7, z = 3002.2 },
                  air = { name = "air", story = 8000, map = 1000, x = -5935.0, y = -8305.0, z = 2075.0 } }
G.OPEN_START = G.OPEN_STARTS.dock
function G.MarkChatsPlayed(sd) G.chatsMarked = (G.chatsMarked or 0) + 1; return G.chatsOk ~= false, "marked" end
function G.SaveData() return {} end
function G.ChatState() return "56 rows" end
function G.VisionKeys() return "1 visions" end
G.lockSyncs, G.lockOpens = 0, {}
function G.OnField() return true end
function G.ContinentSync() G.lockSyncs = G.lockSyncs + 1; return {"pharm"}, {} end
function G.ContinentClear() G.lockCleared = true end
function G.ContinentMapLoaded(world, place) G.hookWorld, G.hookPlace = world, place; return place and {"pharm"} or nil, "locks off" end
function G.ContinentStatus() return "open []" end
function G.SetContinentOpen(name, open) if name == "narnia" then return nil, "no continent" end G.lockOpens[name] = open; return 1 end
G.WORLD_MAP, G.ferrySyncs, G.crossingLists = 1000, 0, {}
G.CROSSINGS = { { a = "grandshelt", b = "lanzelt", x = 13684, y = 16599, z = 87, yaw = 180.0, scale = 3.0 } }
function G.FerrySync(allOpen)
  G.ferrySyncs = G.ferrySyncs + 1
  if allOpen then G.ferryAllOpen = (G.ferryAllOpen or 0) + 1 end
  return 0
end
function G.IsContinent(name) return name ~= "narnia" end
function G.ContinentOpen(name) return (G.openContinents or {})[name] == true end
function G.CrossingSync(list) G.crossingLists[#G.crossingLists + 1] = list; return 0, 0 end
function G.CrossingNear(list, range) return nil end
function G.CrossingClear() G.crossingsCleared = true end
G.AIRSHIP_FLAG, G.airshipSyncs, G.parks = 1431, {}, {}
G.RADAR_ON_FLAG, G.RADAR_TIER_PROGRESS, G.RADAR_FOUND_PROGRESS = 702, 49, 51
G.RADAR_LID_HEARD = 10
G.RADAR_QUIET = 2
G.VISION_MOOGLE_FLAGS, G.THRONE_KEY = { 144, 145 }, { map = 3160 }
G.CABIN_KEY, G.DUNGEON_KEY = { map = 2170 }, { item = 20019, map = 3150 }
function G.CabinKeyManOff() return 0 end
function G.UnvisitLocked() return {} end
G.RADAR_BANDS = { { upTo = 13, steps = { 20, 30 } }, { upTo = 22, steps = { 40 } }, { upTo = 31, steps = { 50 } } }
G.RADAR = {}
for n = 1, 13 do G.RADAR[n] = { n = n, flag = 703 + n, tier = n <= 5 and 1 or n <= 9 and 2 or 3 } end
G.progress, G.radarPatches = {}, 0
function G.ProgressValue(i) return G.progress[i] or 0 end
function G.SetProgressValue(i, n) G.progress[i] = n; return n end
function G.RadarPatch() G.radarPatches = G.radarPatches + 1; return 13 end
G.BEHEMOTH, G.behemothPatches = { map = 3280 }, 0
function G.BehemothPatch() G.behemothPatches = G.behemothPatches + 1; return 3 end
G.FOOT_STARTS = { lanzelt = { name = "foot lanzelt", story = 8000, map = 1000, x = 12470, y = 14980, z = 65 } }
function G.AirshipItemSync(asItem) G.airshipSyncs[#G.airshipSyncs + 1] = asItem; return nil end
function G.ParkAirship(x, y, z) G.parks[#G.parks + 1] = x .. " " .. y .. " " .. z; return true end
G.shipsOnMap, G.shipFar, G.shipMoves = 0, false, 0
function G.MoveAirships(a, far, step)
    if G.shipsOnMap > 0 and G.shipFar then G.shipMoves = G.shipMoves + 1; return G.shipsOnMap, { "airship from Zoldaad" } end
    return G.shipsOnMap, {}
end
function G.AirshipState() return "placed true" end
function G.AirshipCondition(c) G.airshipWrote = c; return c end
function G.NoLandShadow() return 0, 1, { "box" } end
G.TITLE_LOAD_GAME, G.TITLE_NEW_GAME, G.TITLE_ARCHIPELAGO, G.titleAdds = 1, 2, 5, 0
G.TITLE_LABEL_LIVE, G.TITLE_LABEL_NO_CLIENT = "New Game (Archipelago)", "New Game (Archipelago: connect the client)"
G.titleOk = false   -- the title entry only once a section turns it on
function G.AddTitleEntry()
  G.titleAdds = G.titleAdds + 1
  if G.titleOk then return true, "copied from the New Game row" end
  return false, "DA_Title is not loaded (go to the title screen)"
end
function G.TitleEntries() return "shown [0,1,2,3,4,5], map keys [0,1,2,3,4,5]" end
G.orders, G.titleLines = 0, {}
function G.OrderTitleEntries() G.orders = G.orders + 1; return true, G.orders == 1 and "rebuilt as [0,1,2,5,3,4]" or "already in order" end
G.describes = 0
G.FEED_MAX, G.feedReady, G.feed, G.toasts = 5, true, {}, {}
function G.FeedLine(text, now, opts)
  if not G.feedReady then return false, "no field HUD" end
  G.feed[#G.feed + 1] = text
  G.feedSpans = G.feedSpans or {}
  G.feedSpans[text] = opts and opts.span and (opts.span.text .. "/" .. tostring(opts.span.flags)) or nil
  return true
end
function G.FeedTick() return 0 end
function G.Toast(msg) G.toasts[#G.toasts + 1] = msg; return true end
G.popups, G.popupReady, G.restores = {}, true, 0
function G.ChestPopup(text)
  if not G.popupReady then return false, "no chest pop-up on screen" end
  G.popups[#G.popups + 1] = text
  return true, "text set, item line hidden"
end
function G.ChestPopupRestore() G.restores = G.restores + 1 end
G.popupOpen = false
function G.PopupJustOpened() local o = G.popupOpen; G.popupOpen = false; return o end
G.layoutAsks = 0
function G.LayoutOf(t) G.layoutAsks = G.layoutAsks + 1; if G.layoutAsks == 3 then return { "widget TextBlock Text_Message" } end return nil end
G.logos = {}
function G.TitleVersionLine(line)
  G.titleLines[#G.titleLines + 1] = line
  return (#G.titleLines == 1) and "added" or "already", {}
end
function G.TitleLogo(path, line) G.logos[#G.logos + 1] = path; return "added", "20x21" end
function G.DescribeWidget(w) G.describes = G.describes + 1; return "widget TextBlock" end
function G.SkipPrologue(opts)
  G.skipParty, G.skipArrival = opts.party, opts.arrival
  G.skipRuns = G.skipRuns + 1; G.skipOpen = opts.openStart; G.story = opts.openStart and 7090 or 1030
  return true, { "ok   stub" }
end
function G.SaveAndReload(slot, map)
  G.reloads[#G.reloads + 1] = slot; G.reloadMap = map
  return true, "saved to slot " .. slot .. ", reloading"
end
G.openStarts = 0
function G.OpenStart() G.openStarts = G.openStarts + 1; G.story = 7090; return true, { "ok   stub" } end
G.TEST_KEY_ID, G.gate, G.injectedItems = 29901, nil, {}
function G.HasActiveGate() return G.gate ~= nil end
function G.PlayerPose()
  return { class = "BP_MapUnit_Player_Field_C", x = 0, y = 0, z = 0, yaw = 0, sx = 1 }
end
function G.InjectValuableItem(id)
  id = id or G.TEST_KEY_ID
  G.injectedItems[#G.injectedItems + 1] = id
  return true, 'added row FFRAP_Key_' .. id .. ': ID=' .. id .. ', name="Bridge Crest"'
end
function G.SpawnGate(kind, dist)
  G.gate = {
    kind = kind or "combo", locked = true, x = 200, y = 0, z = 0,
    dist = tonumber(dist) or 220, bumpDist = 165, cond = nil,
  }
  return true, "spawned " .. G.gate.kind
end
function G.SetGateLock(locked)
  if not G.gate then return false, "no active gate" end
  G.gate.locked = locked
  return true, locked and "locked (visible, collision on)" or "unlocked (hidden, collision off)"
end
function G.SetGateRequirement(cond)
  if not G.gate then return false, "no active gate" end
  G.gate.cond = cond
  if not cond then return true, "requirement cleared" end
  local held = G.gateHeld or 0
  local met = held >= (cond.count or 1)
  G.gate.locked = not met
  local txt = string.format("Bridge Crest (%d/%d)", held, cond.count or 1)
  G.gate.condText = txt
  return true, (met and "unlocked: " or "locked, need ") .. txt
end
function G.PollGate()
  if not G.gate then return nil end
  if G.gate.gone then G.gate = nil; return { gone = true } end
  local changed = nil
  if G.gate.cond then
    local held = G.gateHeld or 0
    local need = G.gate.cond.count or 1
    G.gate.condText = string.format("Bridge Crest (%d/%d)", held, need)
    local wantLocked = held < need
    if wantLocked ~= G.gate.locked then
      G.gate.locked = wantLocked
      changed = wantLocked and "locked" or "unlocked"
    end
  end
  return {
    locked = G.gate.locked, changed = changed, condText = G.gate.condText,
    dist = G.gate.dist, bumpDist = G.gate.bumpDist,
    kind = G.gate.kind, mapId = G.map, x = G.gate.x, y = G.gate.y, z = G.gate.z, actors = 2,
  }
end
function G.ClearGate()
  local n = G.gate and 2 or 0
  G.gate = nil
  return n
end
return G
'''


# Lua that captures the mod's log lines, for boot(CAPTURE).
CAPTURE = "logged = {}; print = function(s) logged[#logged + 1] = tostring(s) end"


def boot(before=""):
    L = runtime()
    L.execute(before)
    L.execute('''
      tickFn = nil; commands = {}
      -- the timers must run on the game thread (0.11.4): LoopAsync runs Lua on another thread
      function LoopInGameThreadWithDelay(ms, fn) if ms == 100 then fastFn = fn else tickFn = fn end end
      function LoopAsync(ms, fn) error("LoopAsync used") end
      function ExecuteInGameThread(fn) fn() end
      function RegisterConsoleCommandGlobalHandler(n, fn) commands[n] = fn end
      hooks = {}
      posts = {}
      function RegisterHook(name, fn, post) hooks[name] = fn; posts[name] = post end
      function RegisterLoadMapPostHook(fn) loadMapHook = fn end
    ''')
    G = L.execute(STUB)
    L.globals().package.loaded["game"] = G
    L.execute(f'dofile("{SCRIPTS}/main.lua")')
    return L, G


# a 0.3.0-style seen.tsv line is read and converted
open(path("seen.tsv"), "w", encoding="utf-8", newline="\n").write("xchest\t2002\tu52\trowmap -1\t-1\t1\t-1\t\n")
# Round 100: with no session no save is the seed's, so these runs have one. Their unsaved new game
# is linked to it.
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS0:0:1\n")
# Round 116: the client is connected for these runs. Its heartbeat is read with the game's clock,
# which a later section sets, so this one is written far ahead.
LIVE_FOREVER = 9_999_999_999


def heartbeat(at=LIVE_FOREVER):
    if at is None:
        if os.path.exists(path("ap_alive.txt")):
            os.remove(path("ap_alive.txt"))
    else:
        open(path("ap_alive.txt"), "w", encoding="utf-8", newline="\n").write(f"{at}\tS0:0:1\n")


heartbeat()

L, G = boot(CAPTURE)
# Round 65: the first GetUniqueId answer of a session is logged even when the call fails
G.chests[1].actor = L.table_from({"broken": True})
G.saveOpen["2002:42"] = True                               # round 99: read open on arrival, so the save row must agree
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(10)
assert "check" not in read("ap_out.txt"), "nothing may be judged while the map settles"
tick(2)
out = read("ap_out.txt")
assert "check\tchest:2002:u42\n" in out, out              # rowless chest with a reward
assert "u54" not in out                                    # rowless, empty, already open: not a location
assert "chest:3020:1" not in out and "shiny:" not in out
seen = read("seen.tsv")
assert "chest\t2002\t7\t3020:1\t209\t3\t-1\t\n" in seen, seen
assert "xchest\t2002\t54\t\t-1\t1\t-1\t\n" in seen and "spot\t2002\t113\t" in seen and "shiny\t2002\t30\t" in seen
first = [s for s in L.eval("logged").values() if "(first of the session)" in s]
assert first == ["[FFRAP] chest 2002:7: GetUniqueId failed: no such function (first of the session)\n"], first
G.chests[1].actor = None

# Round 64: the save says chest 3020:1 (uid 7 in map 2002) is open while the loaded chest says
# closed (the Earth Shrine's four). It is not sent, and the log says so once per visit.
L.execute("logged = {}; print = function(s) logged[#logged + 1] = tostring(s) end")
G.saveOpen["2002:7"] = True
tick(6)
assert "chest:3020:1" not in read("ap_out.txt")
disagree = [s for s in L.eval("logged").values() if "chest:3020:1: the save says open" in s]
assert len(disagree) == 1 and "(row true, IsOpenTreasureBox true)" in disagree[0], list(L.eval("logged").values())
# then the player opens it: sent
G.chests[1].open = True
tick(2)
assert "check\tchest:3020:1\n" in read("ap_out.txt")
G.chests[1].open = False
# a chest or shiny whose GetUniqueId differs from m_UniqueId is logged, on the next visit
LEVEL_UID = 80
G.chests[2].actor = L.table_from({"gameUid": LEVEL_UID})
G.map = 2003
tick(2)
G.map = 2002
tick(14)
assert any(f"chest 2002:63: GetUniqueId says {LEVEL_UID}" in s for s in L.eval("logged").values())
G.chests[2].actor = None

# sync from the save, from another map, after ap_out.txt was lost
G.map = 1000
G.saveOpen["2002:63"] = True                                # chest 3020:3, never seen open live
G.saveOpen["2002:30"] = True                                # shiny 30
os.remove(path("ap_out.txt"))
L, G = boot()
G.map = 1000
G.saveOpen = {"2002:7": True, "2002:63": True, "2002:30": True, "2002:54": True}
[L.execute("tickFn()") for _ in range(12)]                 # round 100: the save is judged first
L.execute('commands["ffrap_sync"]("ffrap_sync", {})')
out = read("ap_out.txt")
for key in ("chest:3020:1", "chest:3020:3", "shiny:2002:30"):
    assert f"check\t{key}\n" in out, (key, out)
assert "u54" not in out and "u52" not in out and "113" not in out
L.execute('commands["ffrap_sync"]("ffrap_sync", {})')
assert read("ap_out.txt").count("chest:3020:3") == 1        # sync twice reports once
L.execute('commands["ffrap_status"]("ffrap_status", {})')
print("main: ok")

# 4. 0.4.0: sessions, cfg, sync, gil, and blanking that leaves key-item chests alone
L = runtime()
L.execute(r'''
local function row(map, id, item, n, money)
  return { mapId = map, ID = id, ItemId = item, ItemNum = n, Money = money, IsTrap = false }
end
local function dtable(name, rows)
  local t = { rows = rows, name = name, ParentTables = {} }
  function t:IsValid() return true end
  function t:GetFullName() return self.name end
  function t:ForEachRow(fn) for k, r in pairs(self.rows) do fn(k, r) end end
  return t
end
root = dtable("root", { a = row(2000, 0, 3, 1, -1), key = row(2011, 1, 30006, 1, -1), gil = row(2001, 2, -1, 1, 400) })
function StaticFindObject(p) if p:find("TreasureBox") then return root end return nil end
function FindAllOf() return nil end
function FindFirstOf() return nil end
G = (require("game"))
''')
assert L.eval("G.BlankChests(true)") == 2
assert L.eval("root.rows.key.ItemId") == 30006, "a key-item chest must keep its content"
assert L.eval("root.rows.gil.Money") == 0 and L.eval("root.rows.a.ItemId") == -1
assert L.eval("G.BlankChests(false)") == 2 and L.eval("root.rows.gil.Money") == 400
print("blanking limit: ok")

for name in ("ap_in.txt", "ap_out.txt", "ap_state.txt", "seen.tsv"):
    if os.path.exists(path(name)):
        os.remove(path(name))
# pre-session leftovers: a check from before connecting must not survive the session start
open(path("ap_out.txt"), "w", encoding="utf-8", newline="\n").write("hello\t0.3.1\ncheck\tchest:2001:0\n")
open(path("seen.tsv"), "w", encoding="utf-8", newline="\n").write(
    "chest\t2002\t7\t3020:1\t209\t3\t-1\t\nshiny\t1000\t30\tBP\t16\t3\t-1\t\n")
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write(
    "seed\tS1:1\ncfg\tblank\t1\n"
    "item\t0\titem\t10100\t1\tCrimson Saber\nitem\t1\tgil\t0\t400\t400 Gil from Bob\n")
L, G = boot()
G.GrantGil = L.eval("function(g) return function(n) g.log[#g.log+1] = 'gil'..n return 'ok', '' end end")(G)
G.GrantItem = L.eval("function(g) return function(id, n) g.log[#g.log+1] = 'item'..id..'x'..n return 'ok', '' end end")(G)
G.saveOpen = L.table_from({"2002:7": True})
G.chests = L.table()
G.shinies = L.table()
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
out = read("ap_out.txt")
assert out.startswith(f"hello\t{VERSION}\t2\nseed\tS1:1\n") and "chest:2001:0" not in out, out
state = read("ap_state.txt")
assert "seed\tS1:1" in state and "blank\t1" in state, state
tick(6)
assert list(G.log.values()) == ["item10100x1", "gil400"], list(G.log.values())
out = read("ap_out.txt")
assert "check\tchest:3020:1\n" in out, "sync after a new session: " + out   # from seen.tsv + save
assert "shiny:1000:30" not in out

# restart, same session: nothing re-granted, the seed line is written again for the client
L, G = boot()
G.GrantGil = L.eval("function(g) return function(n) g.log[#g.log+1] = 'gil'..n return 'ok', '' end end")(G)
G.GrantItem = L.eval("function(g) return function(id, n) g.log[#g.log+1] = 'item'..id..'x'..n return 'ok', '' end end")(G)
G.chests = L.table()
G.shinies = L.table()
tick(8)
assert list(G.log.values()) == [], list(G.log.values())
out = read("ap_out.txt")
assert out.count("seed\tS1:1") == 2 and out.count("check\tchest:3020:1") == 1, out

# the client asks for a sync while running
G.saveOpen = L.table_from({"1000:30": True})
with open(path("ap_in.txt"), "a", encoding="utf-8", newline="\n") as f:
    f.write("sync\n")
tick(2)
assert "check\tshiny:1000:30\n" in read("ap_out.txt")

# a new seed starts over: ap_out emptied, items re-applied from index 0
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS2:3\nitem\t0\titem\t1\t3\tPotion x3\n")
tick(4)
out = read("ap_out.txt")
assert out.startswith(f"hello\t{VERSION}\t2\nseed\tS2:3\n") and "shiny:1000:30" in out and "chest:3020:1" not in out, out
assert list(G.log.values())[-1] == "item1x3"
print("sessions: ok")


# 5. 0.5.0: each session belongs to one save
for name in ("ap_in.txt", "ap_out.txt", "ap_state.txt", "seen.tsv"):
    if os.path.exists(path(name)):
        os.remove(path(name))
open(path("seen.tsv"), "w", encoding="utf-8", newline="\n").write("chest\t2002\t7\t3020:1\t209\t3\t-1\t\n")
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write(
    "seed\tS5:0:1\ncfg\tblank\t1\nitem\t0\titem\t1\t1\tPotion\n")


def boot5(obj, ticks, slots):
    L, G = boot()
    G.GrantItem = L.eval("function(g) return function(id, n) g.log[#g.log+1] = 'item'..id..'x'..n return 'ok', '' end end")(G)
    G.chests, G.shinies = L.table(), L.table()
    G.saveOpen = L.table_from({"2002:7": True})
    G.saveObj, G.saveTicks, G.slotOf = obj, ticks, L.table_from(slots)
    return L, G


def load(G, obj, ticks):
    G.ready = False
    tick(1)
    G.ready = True
    G.saveObj, G.saveTicks = obj, ticks
    tick(7)


def state_slots():
    for line in read("ap_state.txt").splitlines():
        if line.startswith("slots\t"):
            return line[6:]
    return None


# a: the session starts while an existing save (slot 2) is loaded: everything pauses
L, G = boot5("SD_A", "500", {"500": 2, "600": 3})
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(8)
out = read("ap_out.txt")
assert list(G.log.values()) == [], "no grant into an unlinked save"
assert "check" not in out and "story" not in out, "round 5 bug 2: nothing reported from an unlinked save: " + out
assert True not in list(G.blankCalls.values()), "chests stay vanilla in an unlinked save"
assert state_slots() == "", state_slots()

# b: /bind links it: the item arrives, the save's loot is synced, the slot is kept
with open(path("ap_in.txt"), "a", encoding="utf-8", newline="\n") as f:
    f.write("bind\n")
tick(3)
out = read("ap_out.txt")
assert list(G.log.values()) == ["item1x1"], list(G.log.values())
assert "check\tchest:3020:1\n" in out and "story\t1020\n" in out, out
assert list(G.blankCalls.values())[-1] is True
assert state_slots() == "2", state_slots()

# c: another save (slot 3) pauses again and unblanks; nothing from it is reported
G.saveOpen = L.table_from({"2002:7": True, "2002:63": True})
G.chests = L.table_from({1: L.table_from({"uid": 3, "open": True, "rowMap": 3020, "rowId": 3, "uniqueId": 63,
                                          "typeId": 63, "itemId": 7, "itemNum": 4, "money": -1})})
load(G, "SD_B", "600")
out = read("ap_out.txt")
assert "chest:3020:3" not in out, out
assert list(G.blankCalls.values())[-1] is False
assert "chest\t2002\t63\t3020:3" in read("seen.tsv"), "seen.tsv still records any save"
# ffrap_sync refuses in an unlinked save
L.execute('commands["ffrap_sync"]("ffrap_sync", {})')
assert "chest:3020:3" not in read("ap_out.txt")

# d: the linked slot loads again: resumes, and the open chest in this map counts now
load(G, "SD_C", "500")
out = read("ap_out.txt")
assert "check\tchest:3020:3\n" in out, out
assert list(G.blankCalls.values())[-1] is True

# e: the linked game saves to slot 4; the summary catches up a tick later
G.saveTicks = "700"
tick(1)
G.slotOf = L.table_from({"500": 2, "600": 3, "700": 4})
tick(1)
assert state_slots() == "2,4", state_slots()

# f: another game saves over slot 4: slot 4 is no longer linked
load(G, "SD_D", "600")
G.slotOf = L.table_from({"500": 2, "600": 3, "700": 4, "900": 4})
G.saveTicks = "900"
tick(2)
assert state_slots() == "2", state_slots()

# g: a new game while the session has a save: paused, not linked
load(G, "SD_E", "0")
assert state_slots() == "2"
G.story = 1030
tick(2)
assert "story\t1030" not in read("ap_out.txt")

# h: restart with an old bind line in ap_in.txt and an unlinked save loaded: stays paused,
# and the slots come back from ap_state.txt
with open(path("ap_in.txt"), "a", encoding="utf-8", newline="\n") as f:
    f.write("item\t1\titem\t2\t1\tHi-Potion\n")
L, G = boot5("SD_F", "600", {"500": 2, "600": 3})
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(8)
assert list(G.log.values()) == [], list(G.log.values())
load(G, "SD_G", "500")
# 0.11.2: slot 2 was linked holding 0 items (b) and never saved again, so the save on disk lacks
# item 1 as well: both are granted
assert list(G.log.values()) == ["item1x1", "item2x1"], list(G.log.values())

# i: a new seed forgets the old save; an unsaved new game links itself
load(G, "SD_H", "0")
assert list(G.log.values()) == ["item1x1", "item2x1"], "a paused new game gets nothing new"
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS6:0:1\nitem\t0\titem\t3\t1\tEther\n")
tick(3)
assert list(G.log.values())[-1] == "item3x1", list(G.log.values())
assert state_slots() == "", state_slots()

# j: ffrap_bind from the console links an existing save
load(G, "SD_I", "600")
L.execute('commands["ffrap_bind"]("ffrap_bind", {})')
assert state_slots() == "3", state_slots()
L.execute('commands["ffrap_status"]("ffrap_status", {})')

# k: a new game (story 1000) whose timestamp matches linked slot 3 is still a new game: paused
granted = len(list(G.log.values()))
with open(path("ap_in.txt"), "a", encoding="utf-8", newline="\n") as f:
    f.write("item\t1\titem\t4\t1\tPhoenix Down\n")
G.story = 1000
load(G, "SD_J", "600")
tick(3)
assert len(list(G.log.values())) == granted, ("no grant into a new game", list(G.log.values()))
assert state_slots() == "3", state_slots()
# the same slot loaded later in the story is the session's save again
G.story = 1030
load(G, "SD_K", "600")
tick(3)
assert list(G.log.values())[-1] == "item4x1", list(G.log.values())
print("save binding: ok")

# 6. ffrap_skip (0.11.2)
def inbox(text, mode="a"):
    with open(path("ap_in.txt"), mode, encoding="utf-8", newline="\n") as f:
        f.write(text)

inbox("seed\tS7:0:1\n", "w")
tick(3)
assert state_slots() == "", state_slots()
G.story = 1000
load(G, "SD_L", "0")                      # a new game: links itself
inbox("item\t0\titem\t9\t1\tTent\n")
tick(3)
assert list(G.log.values())[-1] == "item9x1", list(G.log.values())
# refused later in the story
G.story = 1030
L.execute('commands["ffrap_skip"]("ffrap_skip", {})')
assert G.skipRuns == 0
# round 9: refused during the opening movie (story 1000)
G.story = 1000
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipRuns == 0 and len(list(G.reloads.values())) == 0
G.story = 1005
# no slot: applies, saves nothing
L.execute('commands["ffrap_skip"]("ffrap_skip", {})')
assert G.skipRuns == 1 and len(list(G.reloads.values())) == 0
# with a slot on the same save (story now 1030): applied again before saving; the slot is
# linked before the reload
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipRuns == 2, G.skipRuns
assert list(G.reloads.values()) == [0], list(G.reloads.values())
assert state_slots() == "0", state_slots()
# the reloaded save (slot 0, story 1030) is the session's: the next item arrives
G.slotOf = L.table_from({"800": 0})
load(G, "SD_N", "800")
inbox("item\t1\titem\t10\t1\tPhoenix Down\n")
tick(3)
assert list(G.log.values())[-1] == "item10x1", list(G.log.values())
# a bad slot argument does nothing
L.execute('commands["ffrap_skip"]("ffrap_skip", {"x"})')
assert G.skipRuns == 2
# the reloaded save is a different object at story 1030: refused
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipRuns == 2 and list(G.reloads.values()) == [0]
print("skip command: ok")

# 7. a per-save item count (0.11.2)
# (also: the S8 file below is longer than the S7 one already read; its new first line makes
# the mod read it from the top)
def grants():
    return [g for g in G.log.values() if g.startswith("item")]

def slot_items():
    for line in read("ap_state.txt").splitlines():
        if line.startswith("slotItems\t"):
            return line[len("slotItems\t"):]
    return None

inbox("seed\tS8:0:1\nclient\t0.1.3\nitem\t0\titem\t100\t1\tA\nitem\t1\titem\t101\t1\tB\nitem\t2\titem\t102\t1\tC\n", "w")
tick(3)
G.story, G.slotOf = 1000, L.table_from({})
before = len(grants())
load(G, "SD_P", "0")                             # a new game links itself and gets all three
assert grants()[before:] == ["item100x1", "item101x1", "item102x1"], grants()[before:]
# the game saves to slot 1 with the three items in it
G.saveTicks = "1000"
G.slotOf = L.table_from({"1000": 1})
tick(2)
assert state_slots() == "1" and slot_items() == "1=3", (state_slots(), slot_items())
# a fourth item arrives, and the game is not saved again
inbox("item\t3\titem\t103\t1\tD\n")
tick(3)
assert grants()[-1] == "item103x1"
n = len(grants())
# reloading slot 1: that save has three items, so D is granted again
G.story = 1030
load(G, "SD_Q", "1000")
assert grants()[n:] == ["item103x1"], grants()[n:]
# the game saves to slot 2 with four; slot 1 keeps its three
G.saveTicks = "1100"
G.slotOf = L.table_from({"1000": 1, "1100": 2})
tick(2)
assert state_slots() == "1,2" and slot_items() == "1=3,2=4", (state_slots(), slot_items())
n = len(grants())
load(G, "SD_R", "1100")                          # slot 2 has everything: nothing granted
assert grants()[n:] == [], grants()[n:]
load(G, "SD_S", "1000")                          # slot 1 lacks D again
assert grants()[n:] == ["item103x1"], grants()[n:]
# binding a save the session never had: it gets all four
G.slotOf = L.table_from({"1000": 1, "1100": 2, "1200": 5})
n = len(grants())
load(G, "SD_T", "1200")
assert grants()[n:] == [], "paused: an unlinked save gets nothing"
L.execute('commands["ffrap_bind"]("ffrap_bind", {})')
tick(3)
assert grants()[n:] == ["item100x1", "item101x1", "item102x1", "item103x1"], grants()[n:]
assert state_slots() == "5" and slot_items() == "5=0", (state_slots(), slot_items())
# it saves; then the game restarts with that save loaded: nothing is granted twice
G.saveTicks = "1300"
G.slotOf = L.table_from({"1000": 1, "1100": 2, "1300": 5})
tick(2)
assert slot_items() == "5=4", slot_items()
L, G = boot5("SD_U", "1300", {"1300": 5})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1030
tick(8)
assert [g for g in G.log.values() if g.startswith("item")] == [], list(G.log.values())
assert G.log is not None
print("per-save items: ok")

# 7b. Round 77: the save stamp. A pre-release player updated the mod (and deleted ap_state.txt,
# as the install steps said) or moved to another PC, had to bind again, and got every item twice.
# Now the save says which seed it belongs to and how many items it holds.
SEED_KEY = "S77:0:1"
FOUR_ITEMS = ("item\t0\titem\t100\t1\tA\nitem\t1\titem\t101\t1\tB\n"
              "item\t2\titem\t102\t1\tC\nitem\t3\titem\t103\t1\tD\n")
os.remove(path("ap_state.txt"))
L, G = boot5("SD_V", "1400", {"1400": 3})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1030
G.stamps["SD_V"] = L.table_from({1: 3, 2: G.SeedTag(SEED_KEY)})      # stamped elsewhere: 3 items
inbox(f"seed\t{SEED_KEY}\nclient\t0.1.3\n" + FOUR_ITEMS, "w")
tick(8)
assert grants() == ["item103x1"], "only the item the save lacks: " + str(grants())
assert G.stamps["SD_V"][1] == 4, "the stamp follows the items granted"
assert state_slots() == "3", state_slots()
# a save in a slot the session knows, but stamped by another seed (the slot was reused): paused
G.slotOf = L.table_from({"1400": 3, "1500": 3})
G.stamps["SD_W"] = L.table_from({1: 2, 2: G.SeedTag("S8:0:1")})
n = len(grants())
load(G, "SD_W", "1500")
assert grants()[n:] == [], grants()[n:]
assert G.stamps["SD_W"][1] == 2, "another seed's stamp is left alone"
# a plain new game while the session has a save: paused, and a save that is not the session's
# never gets a stamp
load(G, "SD_X", "0")
assert G.stamps["SD_X"] is None, "no stamp on a save that is not the session's"
print("save stamp: ok")

# 8. the title entry (0.7.3): entry 5 becomes New Game and marks the game
G.titleOk = True
n_adds = G.titleAdds
L.execute('commands["ffrap_title"]("ffrap_title", {"add"})')
assert G.titleAdds == n_adds + 1
hook = L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')
assert hook is not None
L.execute("""param = { v = 5 }; function param:get() return self.v end; function param:set(x) self.v = x end""")
L.execute('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"](nil, param)')
assert L.eval("param.v") == 2, "turned into New Game"
L.execute("""param2 = { v = 1 }; function param2:get() return self.v end; function param2:set(x) self.v = x end""")
L.execute('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"](nil, param2)')
assert L.eval("param2.v") == 1, "Load Game left alone"
L.execute('commands["ffrap_title"]("ffrap_title", {"add"})')    # a second add: still one hook
print("title entry: ok")

# 9. the Archipelago new game (0.11.2): the entry is kept at start-up, a plain New Game stays
# vanilla, the Archipelago one links and skips the prologue by itself once it has autosaved
inbox("seed\tS9:0:1\nitem\t0\titem\t200\t1\tE\n", "w")
G.titleOk = True
tick(7)                                           # titleTick runs every 6 ticks
G.story, G.slotOf = 1000, L.table_from({})
n = len(grants())
load(G, "SD_V1", "0")                             # plain New Game: paused
tick(3)
assert grants()[n:] == [], ("vanilla new game gets nothing", grants()[n:])
hook = L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')
L.execute("""p5 = { v = 5 }; function p5:get() return self.v end; function p5:set(x) self.v = x end""")
hook(None, L.eval("p5"))
assert L.eval("p5.v") == 2
runs, reloads = G.skipRuns, len(list(G.reloads.values()))
load(G, "SD_AP", "0")                             # the Archipelago new game: linked, gets E
assert grants()[n:] == ["item200x1"], grants()[n:]
tick(6)
assert G.skipRuns == runs, "no skip during the opening movie"
G.story = 1005                                    # Fina can move; then the first autosave
tick(6)
assert G.skipRuns == runs, "no skip before the autosave"
G.saveTicks = "3000"
G.slotOf = L.table_from({"3000": 0})
tick(2)                                           # the autosave is seen and linked
assert G.skipRuns == runs, "waits a moment after the autosave"
tick(6)
assert G.skipRuns == runs + 1, G.skipRuns
assert list(G.reloads.values())[reloads:] == [0], list(G.reloads.values())
assert state_slots() == "0", state_slots()
tick(10)
assert G.skipRuns == runs + 1, "once"
# connecting the client to a new seed after the automatic skip re-links and re-skips with the new seed's party
G.story = 8000
# Round 106: the skip's reload, and a later load of the same slot (a game over), hold the items
# given before the save. They are not given again (the feed showed them twice, round 105's save
# got 2 of each).
G.stamps["SD_AP_RELOADED"] = G.stamps["SD_AP"]
load(G, "SD_AP_RELOADED", "3000")
tick(2)
assert grants()[n:] == ["item200x1"], ("the skip's reload gives nothing again", grants()[n:])
G.stamps["SD_AP_GAME_OVER"] = G.stamps["SD_AP"]
load(G, "SD_AP_GAME_OVER", "3000")
tick(2)
assert grants()[n:] == ["item200x1"], ("a game over's load gives nothing again", grants()[n:])
load(G, "SD_AP_RELOADED", "3000")
tick(2)
inbox("seed\tS9B:0:1\ncfg\topenworld\t1\ncfg\tparty\t1004,1005\n", "w")
tick(2)
assert G.skipRuns == runs + 2 and list(G.skipParty.values()) == [1004, 1005], (G.skipRuns, G.skipParty)
assert state_slots() == "0", state_slots()
# a later load of some other save does not get the Archipelago treatment
G.story = 1030
load(G, "SD_OTHER", "9999")
assert G.skipRuns == runs + 2
assert G.orders >= 1, "the order is checked once the entry is in"
G.ready = False                                   # back at the title screen
tick(13)                                          # two checks: the line, then the logo
assert f"FFRArchipelago {VERSION}" in list(G.titleLines.values()), list(G.titleLines.values())
assert G.describes == 1, "the layout is logged once"
assert len(list(G.logos.values())) >= 1 and list(G.logos.values())[0].endswith("Assets/archipelago_logo.png"), list(G.logos.values())
G.ready = True
print("archipelago new game: ok")

# Round 77: the user deleted ap_in.txt for a new seed and chose Archipelago before the client had
# connected. The skip ran for the old seed in ap_state.txt, with no open world: chapter 1. Now
# the skip waits until the client has written a seed line this run.
os.remove(path("ap_in.txt"))
L, G = boot5("SD_TITLE", "0", {})
L.execute("logged = {}; print = function(s) logged[#logged + 1] = tostring(s) end")
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.titleOk, G.story, G.slotOf = True, 1000, L.table_from({})
tick(7)
L.execute("p6 = { v = 5 }; function p6:get() return self.v end; function p6:set(x) self.v = x end")
L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')(None, L.eval("p6"))
runs = G.skipRuns
load(G, "SD_AP2", "0")
G.story, G.saveTicks, G.slotOf = 1005, "4000", L.table_from({"4000": 0})
tick(20)
assert G.skipRuns == runs, "no skip without the client"
waits = [m for m in L.eval("logged").values() if "prologue skip waits" in m]
assert len(waits) == 2, waits      # the title's notice and the field's, once each
inbox("seed\tS77W:0:1\ncfg\topenworld\t1\n", "w")
tick(10)
assert G.skipRuns == runs + 1, "the client connected: the skip runs"
print("skip waits for the client: ok")

# Round 109: the new start. With autosave off the game never saved, so the skip above never ran
# and the seed's save played the prologue. With ffrap_newstart on, the title entry sets up the
# game's data so the new game begins at the arrival (story 8000), with no save and no reload.
ARRIVAL_STORY, INHERITED_SLOT = 8000, 2
os.remove(path("ap_in.txt"))
L, G = boot5("SD_TITLE", "0", {})
L.execute(CAPTURE)
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
L.eval("""function(G)
  G.prepares, G.nsRestores, G.finishes, G.moves, G.armed = {}, 0, {}, 0, false
  G.whereDist, G.whereZ, G.holds = 0, 65, {}
  G.NEW_START = { near = 300, holdTicks = 20 }
  function G.HoldMove(on) G.holds[#G.holds + 1] = tostring(on); return on end
  function G.InputState() return "controller PC_0" end
  function G.NewStartPrepare(opts)
    G.prepares[#G.prepares + 1] = opts.arrival.name .. " " .. table.concat(opts.party or {}, ",")
    G.armed = true
    return true, { "ok   start map 10040 -> " .. opts.arrival.map }
  end
  function G.NewStartRestore()
    if not G.armed then return nil end
    G.armed, G.nsRestores = false, G.nsRestores + 1
    return "start map 10040"
  end
  function G.NewStartFinish(opts)
    G.finishes[#G.finishes + 1] = opts.arrival.name
    return true, { "ok   story counter -> 8000" }
  end
  function G.NewStartWhere(a) return G.whereDist, "map 1000 (arrival 1000)", G.whereZ end
  -- the move lands; with G.sink the player is found below the arrival afterwards
  function G.NewStartMove(a)
    G.moves = G.moves + 1
    G.whereDist, G.whereZ = G.walk or 0, G.sink and a.z - 2000 or a.z
    return true, "moved to the arrival"
  end
end""")(G)
logged = lambda: list(L.eval("logged").values())
G.titleOk, G.slotOf = True, L.table_from({})
inbox("seed\tS109:0:1\ncfg\topenworld\t1\ncfg\tparty\t1004,1005\ncfg\tcontinent\tlanzelt\n", "w")
tick(7)
entry = lambda: L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')(None, L.eval(
    "(function() local p = { v = 5 }; function p:get() return self.v end; function p:set(x) self.v = x end; return p end)()"))
entry()
assert len(list(G.prepares.values())) == 1, "on by default since round 110"
assert "newstart\t" not in read("ap_state.txt"), "the default is not written"
L.execute('commands["ffrap_newstart"]("ffrap_newstart", {"off"})')
entry()
assert len(list(G.prepares.values())) == 1 and not G.armed, "off: the prologue skip as before"
L.execute('commands["ffrap_newstart"]("ffrap_newstart", {"on"})')
assert "newstart\t1" in read("ap_state.txt")
entry()
# Round 109 (the user): on foot by the starting continent's town, for an airship seed too
assert list(G.prepares.values())[-1] == "foot lanzelt 1004,1005", list(G.prepares.values())
# The new game is at the arrival's story, and its timestamp is the autosave slot's it would
# overwrite: still the Archipelago new game, linked, and finished at once.
G.story, G.saveTicks, G.slotOf = ARRIVAL_STORY, "7000", L.table_from({"7000": INHERITED_SLOT})
runs = G.skipRuns
inbox("item\t0\titem\t200\t1\tE\n")
load(G, "SD_NS", "7000")
assert G.nsRestores == 2 and list(G.finishes.values()) == ["foot lanzelt"], (G.nsRestores, list(G.finishes.values()))
assert any("a new game, although its timestamp matches slot 2" in m for m in logged())
assert [g for g in grants() if g == "item200x1"] == ["item200x1"], grants()
tick(20)
assert G.skipRuns == runs, "the prologue skip stays out of it"
assert G.moves == 0, "near the arrival: not moved"
# Round 115: move input is held from the arrival until the player stands there, then given back
assert list(G.holds.values()) == ["true", "false"], list(G.holds.values())
assert any("move input given back (at the arrival)" in m for m in logged())
# Round 109: far from the arrival (where the world map puts a new game): moved. Found below the
# arrival after it (its island not loaded yet): moved again, but only once more.
G.whereDist, G.sink = 28023, True
entry()
load(G, "SD_NS2", "7000")
tick(20)
assert G.moves == 2, G.moves
assert sum(1 for m in logged() if "newstart: after the move:" in m) == 2, logged()[-20:]
assert [g for g in grants() if g == "item200x1"] == ["item200x1", "item200x1"], "once per new game"
G.sink = False
# Round 115: the user walked 359 from the arrival after the move, and a second move froze the pawn.
# A player above the arrival's ground is not moved again, however far they walked.
WALKED = 359
G.whereDist, G.walk, G.moves, G.holds = 28023, WALKED, 0, L.table_from({})
entry()
load(G, "SD_NS115", "7000")
tick(20)
assert G.moves == 1, G.moves
assert list(G.holds.values()) == ["true", "false"], list(G.holds.values())
G.walk = None
# Backing out: a set-up that is never used is put back when the title menu is used again
nsRestores = G.nsRestores
entry()
L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')(None, L.eval(
    "(function() local p = { v = 2 }; function p:get() return self.v end; function p:set(x) self.v = x end; return p end)()"))
assert G.nsRestores == nsRestores + 1 and not G.armed, "a plain New Game after it is vanilla"
# Not used with no seed heard this run, or with no open world start
L.execute('commands["ffrap_newstart"]("ffrap_newstart", {"off"})')
entry()
assert len(list(G.prepares.values())) == 5, list(G.prepares.values())
assert "newstart\t0" in read("ap_state.txt")
# Rain matches the party's level only past the open start's story: in the prologue (a skip that
# never ran) the party is Archwitch Fina at 55
syncs = G.slotSyncs or 0
G.story = 1010
tick(30)
assert (G.slotSyncs or 0) == syncs, "no level sync in the vanilla story"
G.story = ARRIVAL_STORY
tick(30)
assert G.slotSyncs > syncs
print("new start: ok")

# Round 116: the client closed, ap_in.txt still held the last seed, and the entry started that
# seed's start. With no heartbeat, or one older than 10 s, the entry becomes Load Game and starts
# nothing; the label says to connect the client the next time the menu is made.
STALE_SECONDS = 60
L.execute('commands["ffrap_newstart"]("ffrap_newstart", {"on"})')
prepared = len(list(G.prepares.values()))
choice = L.eval("(function() local p = { v = 5 }; function p:get() return self.v end; function p:set(x) self.v = x end; return p end)()")
hook = L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')
for beat in (None, int(time.time()) - STALE_SECONDS):
    heartbeat(beat)
    choice.v = 5
    hook(None, choice)
    assert choice.v == 1, choice.v
    assert len(list(G.prepares.values())) == prepared, "no start set up"
assert any("no new game without the client (the client was last heard" in m for m in logged())
G.ready = False
tick(7)
assert G.TITLE_LABEL == G.TITLE_LABEL_NO_CLIENT, G.TITLE_LABEL
L.execute('commands["ffrap_title"]("ffrap_title", {"refuse", "off"})')
choice.v = 5
hook(None, choice)
assert choice.v == 2 and len(list(G.prepares.values())) == prepared + 1, ("refusing off: a game with no client", logged()[-8:])
L.execute('commands["ffrap_title"]("ffrap_title", {"refuse"})')
heartbeat(int(time.time()))
tick(7)
assert G.TITLE_LABEL == G.TITLE_LABEL_LIVE, G.TITLE_LABEL
choice.v = 5
hook(None, choice)
assert choice.v == 2 and len(list(G.prepares.values())) == prepared + 2
# Round 116 probe: with ffrap_point0 on, the world map's point 0 goes to the arrival once found,
# before the save is in, and back once it is (the Earth Shrine's door leads to it)
EARTH_SHRINE_POINT = (17214, 20957, 0)
L.eval("""function(G, x, y, z)
  G.pointMoves = {}
  function G.MoveStartPoint(to)
    G.pointMoves[#G.pointMoves + 1] = to.x .. "," .. to.y
    return { x = x, y = y, z = z }, "point 0 moved to " .. to.x .. ", " .. to.y
  end
end""")(G, *EARTH_SHRINE_POINT)
L.execute('commands["ffrap_point0"]("ffrap_point0", {"on"})')
G.ready = True
tick(3)
assert list(G.pointMoves.values()) == ["12470,14980"], list(G.pointMoves.values())  # Lanzelt, the seed's continent
assert any(m.startswith("[FFRAP] point 0 (tick): point 0 moved to 12470, 14980") for m in logged())
load(G, "SD_P0", "7000")
assert list(G.pointMoves.values())[-1] == "17214,20957", "put back once the save is in"
L.execute('commands["ffrap_point0"]("ffrap_point0", {"off"})')
L.execute('commands["ffrap_newstart"]("ffrap_newstart", {"off"})')   # as the sections below expect
heartbeat()
print("no new game without the client: ok")

# 10. the item feed (0.11.2): one line per item in game; queued while the HUD is away; a long
# queue shows its last lines and how many more; off sends messages to the Toast again
def feed():
    return list(G.feed.values())

# 0.11.2: the "feed 1" that 0.9.0 wrote by itself does not switch the feed on after a restart
with open(path("ap_state.txt"), "a", encoding="utf-8", newline="\n") as f:
    f.write("feed\t1\n")
L, G = boot5("SD_RESTART", "0", {})
G.titleOk = True
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(8)
hook = L.eval('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"]')
L.execute("""p5 = { v = 5 }; function p5:get() return self.v end; function p5:set(x) self.v = x end""")
inbox("seed\tS10:0:1\n", "w")
tick(3)
G.story, G.slotOf = 1000, L.table_from({})
hook(None, L.eval("p5"))
L.execute("p5.v = 5")
hook(None, L.eval("p5"))
load(G, "SD_F1", "0")
# 0.11.2: on by default (it works since 0.9.5): a line per item
inbox("item\t0\titem\t300\t1\tPotion from Bob\nitem\t1\titem\t301\t1\tEther\n")
tick(3)
assert feed()[-2:] == ["Received Potion from Bob", "Received Ether"], feed()
L.execute('commands["ffrap_feed"]("ffrap_feed", {"test", "plain"})')
assert feed()[-3:] == ["Received Potion from Bob", "Sent Ether to Alice", "Received Rod of Focus"], feed()
inbox("item\t1\titem\t301\t1\tEther again\n")
# seven items arrive while the HUD is away (a battle, a loading screen)
G.feedReady = False
inbox("".join(f"item\t{i}\titem\t{400 + i}\t1\tItem{i}\n" for i in range(2, 9)))
tick(3)
n = len(feed())
G.feedReady = True
tick(1)
assert feed()[n:] == ["and 3 more", "Received Item5", "Received Item6", "Received Item7", "Received Item8"], feed()[n:]
# 0.11.2: once the feed has shown a line, messages wait for the HUD however long it is away
# (round 24: a chest pop-up held for 10 s sent its items to the Toast)
G.feedReady = False
toasts = len(list(G.toasts.values()))
n = len(feed())
inbox("item\t9\titem\t600\t1\tHi-Potion\n")
tick(30)
assert list(G.toasts.values())[toasts:] == [], "still waiting after 15 s"
G.feedReady = True
tick(1)
assert feed()[n:] == ["Received Hi-Potion"], feed()[n:]
# off: messages go to the Toast, with the old combined line
L.execute('commands["ffrap_feed"]("ffrap_feed", {"off"})')
assert "itemfeed\t0" in read("ap_state.txt")
toasts = len(list(G.toasts.values()))
inbox("item\t10\titem\t500\t1\tTent\n")
tick(3)
assert list(G.toasts.values())[toasts:] == ["Received Tent"], list(G.toasts.values())[toasts:]
L.execute('commands["ffrap_feed"]("ffrap_feed", {"on"})')
assert "itemfeed\t1" in read("ap_state.txt")
# Round 85: a save bound late in a seed brought 280 items, a feed line each. With more than ten
# waiting, the feed says so once, and once more when they are all in.
CATCH_UP_ITEMS = 14
n = len(feed())
inbox("".join(f"item\t{i}\titem\t{800 + i}\t1\tCatch{i}\n" for i in range(11, 11 + CATCH_UP_ITEMS)))
tick(12)
assert feed()[n:] == [f"Receiving {CATCH_UP_ITEMS} items from Archipelago", f"Received {CATCH_UP_ITEMS} items"], feed()[n:]
inbox(f"item\t{11 + CATCH_UP_ITEMS}\titem\t900\t1\tLast\n")
tick(3)
assert feed()[-1] == "Received Last", "one at a time again"
print("item feed: ok")

# 11. before the feed has shown anything in a run (it cannot find a HUD), the Toast takes messages
# after 10 s; a successful automatic skip and an Archipelago new game's link are only logged
L, G = boot5("SD_FRESH", "0", {})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.feedReady = False
inbox("seed\tS11:0:1\n", "w")
tick(3)
G.story = 1000
load(G, "SD_FRESH2", "0")
inbox("item\t0\titem\t700\t1\tElixir\n")
tick(3)
assert list(G.toasts.values()) == [] or "Received Elixir" not in list(G.toasts.values())
tick(22)
assert any("Received Elixir" in t for t in G.toasts.values()), list(G.toasts.values())
print("feed fallback: ok")

# 12. the chest pop-up (0.11.2): a scouted chest's check makes the pop-up say what it held
import base64
def b64_scout(key, item, player, flags, own):
    raw = f"{key}\t{item}\t{player}\t{flags}\t{own}"
    return "scout\t" + base64.b64encode(raw.encode("utf-8")).decode("ascii") + "\n"

inbox("seed\tS12:0:1\n" + b64_scout("chest:3020:3", "Hookshot", "Alice", 1, 0) + b64_scout("chest:3020:2", "Tent", "Jones", 0, 1), "w")
L, G = boot5("SD_POP", "0", {})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1000
G.chests = L.table()
tick(10)                                   # a new game, linked (no title entry here)
# these chests appear open with no closed sighting first: the save row agrees, as on a real opening
G.saveOpen = L.table_from({"2002:63": True, "2002:8": True, "2002:9": True, "2002:10": True})
G.popupReady = False                       # the pop-up comes up a moment after the check
G.chests = L.table_from({1: L.table_from({"uid": 3, "open": True, "rowMap": 3020, "rowId": 3, "uniqueId": 63,
                                          "typeId": 63, "itemId": 7, "itemNum": 4, "money": -1})})
tick(4)
assert "check\tchest:3020:3" in read("ap_out.txt"), read("ap_out.txt")
assert list(G.popups.values()) == [], "waits for the pop-up"
G.popupReady = True
tick(2)
assert list(G.popups.values()) == ["You found Alice's:\nHookshot"], list(G.popups.values())
# an own item; and a chest with no scout leaves the pop-up alone
G.chests = L.table_from({1: L.table_from({"uid": 2, "open": True, "rowMap": 3020, "rowId": 2, "uniqueId": 8,
                                          "typeId": 8, "itemId": 209, "itemNum": 3, "money": -1}),
                         2: L.table_from({"uid": 4, "open": True, "rowMap": 3020, "rowId": 4, "uniqueId": 9,
                                          "typeId": 9, "itemId": 1, "itemNum": 1, "money": -1})})
tick(6)
assert list(G.popups.values())[1:] == ["You found:\nTent"], list(G.popups.values())
assert G.restores > 0
# 0.11.2: the fast check: a pop-up that has just come up scans the chests at once and rewrites
# the pop-up in the same pass, with no regular tick in between
n = len(list(G.popups.values()))
inbox(b64_scout("chest:3020:5", "Longshot", "Rat2", 1, 0))
tick(1)
G.chests = L.table_from({1: L.table_from({"uid": 5, "open": True, "rowMap": 3020, "rowId": 5, "uniqueId": 10,
                                          "typeId": 10, "itemId": 1, "itemNum": 1, "money": -1})})
G.popupOpen = True
L.execute("fastFn()")
assert "check\tchest:3020:5" in read("ap_out.txt"), "reported by the fast check"
assert list(G.popups.values())[n:] == ["You found Rat2's:\nLongshot"], list(G.popups.values())[n:]
L.execute("fastFn()")                    # nothing new: nothing happens
assert len(list(G.popups.values())) == n + 1
# 0.11.2 (round 27): an older save reloaded; the chest is closed again, then opened again. Its
# check is already reported, but the pop-up still says what it held.
reported = read("ap_out.txt").count("check\tchest:3020:5")
G.chests = L.table_from({1: L.table_from({"uid": 5, "open": False, "rowMap": 3020, "rowId": 5, "uniqueId": 10,
                                          "typeId": 10, "itemId": 1, "itemNum": 1, "money": -1})})
tick(4)                                  # seen closed
G.chests = L.table_from({1: L.table_from({"uid": 5, "open": True, "rowMap": 3020, "rowId": 5, "uniqueId": 10,
                                          "typeId": 10, "itemId": 1, "itemNum": 1, "money": -1})})
G.popupOpen = True
L.execute("fastFn()")
assert read("ap_out.txt").count("check\tchest:3020:5") == reported, "not reported twice"
assert list(G.popups.values())[n + 1:] == ["You found Rat2's:\nLongshot"], list(G.popups.values())
# still open on later scans: no more pop-ups
tick(6)
assert len(list(G.popups.values())) == n + 2
# Round 47: a shiny's pop-up says what it held, as a chest's does, once it is seen picked up
inbox(f"scout\tshiny:{G.map}:77\tLongshot\tRat2\t1\t0\n")
tick(1)
G.chests = L.table()
G.shinies = L.table_from({1: L.table_from({"uid": 77, "open": False, "itemId": -1, "itemNum": 1, "money": 1})})
tick(4)
n = len(list(G.popups.values()))
G.shinies = L.table_from({1: L.table_from({"uid": 77, "open": True, "itemId": -1, "itemNum": 1, "money": 1})})
G.popupOpen = True
L.execute("fastFn()")
assert f"check\tshiny:{G.map}:77" in read("ap_out.txt"), "reported by the fast check"
assert list(G.popups.values())[n:] == ["You found Rat2's:\nLongshot"], list(G.popups.values())[n:]
G.shinies = L.table()
# Round 63: in Felicitas the live shard read id 1, and the save had the level's id 8. A scouted
# shiny on the map is asked of the save by its own id, and one the seed does not hold is not.
FELICITAS, SHARD_UID, LIVE_UID, NOT_A_LOCATION = 2040, 8, 1, 9
SHARD_8_PLACE = (-2733, -3948)                 # data/game/field_items.tsv
inbox(f"scout\tshiny:{FELICITAS}:{SHARD_UID}\tLongshot\tRat2\t1\t0\n")
tick(1)
G.map = FELICITAS
# the player stands by the shard (round 79: a location is sent only with the player near it)
L.execute(f"package.loaded.game.PlayerPose = function() return {{ x = {SHARD_8_PLACE[0] + 100}, y = {SHARD_8_PLACE[1]}, z = 0 }} end")
G.shinies = L.table_from({1: L.table_from({"uid": LIVE_UID, "open": False, "itemId": -1, "itemNum": 1, "money": 1})})
tick(4)
assert f"check\tshiny:{FELICITAS}:{SHARD_UID}" not in read("ap_out.txt"), "not before the save says so"
G.saveOpen[f"{FELICITAS}:{SHARD_UID}"] = True
G.saveOpen[f"{FELICITAS}:{NOT_A_LOCATION}"] = True
tick(4)
out = read("ap_out.txt")
assert out.count(f"check\tshiny:{FELICITAS}:{SHARD_UID}\n") == 1, out
assert f"shiny:{FELICITAS}:{NOT_A_LOCATION}" not in out
G.shinies = L.table()
# Round 72: a live shiny is known by where it stands. Zoldaad Castle's shard 11, taken, came
# back on a later visit reading id 10 and open (round 71), so 10 was sent with nothing picked up.
ZOLDAAD_CASTLE, SHARD_10_PLACE, SHARD_11_PLACE = 3160, (29089, -1073), (30460, 3846)
inbox(f"scout\tshiny:{ZOLDAAD_CASTLE}:10\tLongshot\tRat2\t1\t0\n"
      f"scout\tshiny:{ZOLDAAD_CASTLE}:11\tLongshot\tRat2\t1\t0\n")
G.map = ZOLDAAD_CASTLE
L.execute(f"package.loaded.game.PlayerPose = function() return {{ x = {SHARD_11_PLACE[0]}, y = {SHARD_11_PLACE[1] + 200}, z = 0 }} end")
tick(2)
G.saveOpen[f"{ZOLDAAD_CASTLE}:11"] = True        # taken on the earlier visit
G.shinies = L.table_from({1: L.table_from({"uid": 10, "open": True, "itemId": 25004, "itemNum": 1, "money": -1,
                                            "x": SHARD_11_PLACE[0] + 20, "y": SHARD_11_PLACE[1] - 30})})
tick(10)
out = read("ap_out.txt")
assert f"check\tshiny:{ZOLDAAD_CASTLE}:11\n" in out and f"shiny:{ZOLDAAD_CASTLE}:10" not in out, out[-300:]
# one far from any level shiny keeps the id it reads
G.shinies = L.table_from({1: L.table_from({"uid": 10, "open": False, "itemId": 25004, "itemNum": 1, "money": -1,
                                            "x": SHARD_10_PLACE[0] + 5000, "y": SHARD_10_PLACE[1]})})
tick(2)
G.shinies = L.table()
# Round 78: checks went out with nothing picked up. The Colosseum's shard (map 2016, uid 2) read
# taken on arrival, and world-map shinies a continent away each time a player boarded the airship.
# A chest or shiny read as taken is sent only with the player near it (round 79).
COLOSSEUM, COLOSSEUM_SHARD = 2016, (25789, -10567)
COLOSSEUM_DOOR = (28000, -2000)                # far from the shard
NEAR = 300
inbox(f"scout\tshiny:{COLOSSEUM}:2\tLongshot\tRat2\t1\t0\n"
      f"scout\tchest:3020:9\tLongshot\tRat2\t1\t0\n")
G.map = COLOSSEUM
L.execute(f"local G = package.loaded.game; G.px, G.py = {COLOSSEUM_DOOR[0]}, {COLOSSEUM_DOOR[1]}; "
          "function G.PlayerPose() return { x = G.px, y = G.py, z = 0 } end")
L.execute("logged = {}; print = function(s) logged[#logged + 1] = tostring(s) end")
G.shinies = L.table_from({1: L.table_from({"uid": 2, "open": True, "itemId": 25004, "itemNum": 1, "money": -1,
                                           "x": COLOSSEUM_SHARD[0], "y": COLOSSEUM_SHARD[1]})})
G.chests = L.table_from({1: L.table_from({"uid": 9, "open": True, "rowMap": 3020, "rowId": 9, "uniqueId": 30,
                                          "itemId": 7, "itemNum": 1, "money": -1, "x": 0, "y": 0})})
tick(10)
out = read("ap_out.txt")
assert f"shiny:{COLOSSEUM}:2" not in out and "chest:3020:9" not in out, out[-200:]
# Round 99: in Waterfall Way two chests nobody opened read open on arrival. One read taken with no
# closed sighting on this visit and no save row saying so is held, whatever the distance. Logged
# once per visit, a scan's together, a chest with what IsOpenTreasureBox says (round 65's fallback).
held = [s for s in L.eval("logged").values() if "never seen closed" in s]
assert len(held) == 1 and "2 locations read as taken but never seen closed" in held[0], held
assert f"shiny:{COLOSSEUM}:2 reads taken (live open, save row false)" in held[0], held
assert "chest:3020:9 reads taken (live open, save row false, IsOpenTreasureBox false)" in held[0], held
# the save row alone, for a scouted shiny that is not loaded, is held while the player is far
G.shinies = L.table()
G.saveOpen[f"{COLOSSEUM}:2"] = True
tick(4)
assert f"shiny:{COLOSSEUM}:2" not in read("ap_out.txt")
far = [s for s in L.eval("logged").values() if "not sent until the player is near it" in s]
assert len(far) == 1 and f"shiny:{COLOSSEUM}:2 reads taken (save row only)" in far[0], far
# the pawn cannot be read: still held
L.execute("package.loaded.game.PlayerPose = function() return nil end")
tick(4)
assert f"shiny:{COLOSSEUM}:2" not in read("ap_out.txt")
# the player walks up to it: sent, and the log says what read it as taken
L.execute(f"local G = package.loaded.game; G.px, G.py = {COLOSSEUM_SHARD[0] + NEAR}, {COLOSSEUM_SHARD[1]}; "
          "function G.PlayerPose() return { x = G.px, y = G.py, z = 0 } end")
tick(2)
assert f"check\tshiny:{COLOSSEUM}:2\n" in read("ap_out.txt")
sent = [s for s in L.eval("logged").values() if f"check shiny:{COLOSSEUM}:2" in s]
assert sent and "(save row only, 300 from the player)" in sent[0], sent
# the player at the chest, which still has no save row: held
L.execute(f"local G = package.loaded.game; G.px, G.py = {NEAR}, 0")
tick(2)
assert "chest:3020:9" not in read("ap_out.txt")
# the player opens it, and the game writes its row: sent, with its pop-up
popups = len(list(G.popups.values()))
G.saveOpen[f"{COLOSSEUM}:30"] = True
tick(2)
assert "check\tchest:3020:9\n" in read("ap_out.txt")
assert list(G.popups.values())[popups:] == ["You found Rat2's:\nLongshot"], list(G.popups.values())
# Round 99: a chest opened on another computer reads open on arrival with its save row. It is
# sent again (the server knows it already), with no pop-up: the last such one's text went into
# the next chest the player opened.
inbox(f"scout\tchest:3020:11\tTent\tRat2\t0\t0\n")
G.saveOpen[f"{COLOSSEUM}:31"] = True
G.chests = L.table_from({1: L.table_from({"uid": 11, "open": True, "rowMap": 3020, "rowId": 11, "uniqueId": 31,
                                          "itemId": 7, "itemNum": 1, "money": -1, "x": NEAR + 500, "y": 0})})
tick(2)
assert "check\tchest:3020:11\n" in read("ap_out.txt")
assert list(G.popups.values())[popups + 1:] == [], list(G.popups.values())
G.chests, G.shinies = L.table(), L.table()
for uid in (2, 30, 31):
    G.saveOpen[f"{COLOSSEUM}:{uid}"] = None
print("chest pop-up: ok")

# 13. experimental gate and custom key-item probe (0.11.3): works standalone even on unlinked saves
L, G = boot5("SD_GATE", "900", {"900": 6})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
tick(6)                                    # settled on an unlinked save
L.execute('commands["ffrap_gate"]("ffrap_gate", {"spawn", "combo", "220"})')
assert G.gate is not None and G.gate.locked is True
assert list(G.feed.values())[-1] == "Gate: spawned combo"

# custom item injection + grant
G.gateHeld = 0
G.GrantItem = L.eval("function(g) return function(id, n) g.gateHeld = (g.gateHeld or 0) + n; g.log[#g.log+1] = 'item'..id..'x'..n; return 'ok', 'held -> '..g.gateHeld end end")(G)
L.execute('commands["ffrap_gate"]("ffrap_gate", {"item"})')
assert list(G.injectedItems.values()) == [29901] and G.gateHeld == 1
assert list(G.log.values())[-1] == "item29901x1"

# bind requirement (3 Bridge Crests): currently 1/3, so locked
L.execute('commands["ffrap_gate"]("ffrap_gate", {"require", "item", "29901", "3"})')
assert G.gate.locked is True
assert list(G.feed.values())[-1] == "Gate: locked, need Bridge Crest (1/3)"

# walk into the locked gate: shows proximity hint once, does not repeat while standing close,
# re-arms after stepping back and waiting 3 s
G.gate.dist = 120
n_feed = len(list(G.feed.values()))
tick(1)
assert list(G.feed.values())[n_feed:] == ["Gate locked: need Bridge Crest (1/3)"]
tick(10)
assert len(list(G.feed.values())) == n_feed + 1, "no spam while standing at the gate"
G.gate.dist = 230
tick(7)                                    # > 3 s later, player backed away
G.gate.dist = 110
tick(1)
assert list(G.feed.values())[-1] == "Gate locked: need Bridge Crest (1/3)"

# collect the remaining 2 Bridge Crests: gate unlocks automatically on next tick
L.execute('commands["ffrap_gate"]("ffrap_gate", {"item", "29901", "2"})')
assert G.gateHeld == 3
tick(1)
assert G.gate.locked is False
assert list(G.feed.values())[-1] == "Gate unlocked! (Bridge Crest (3/3))"

# manual lock clears auto-requirement so it stays locked across ticks; status and clear work
L.execute('commands["ffrap_gate"]("ffrap_gate", {"lock"})')
tick(3)
assert G.gate.locked is True
L.execute('commands["ffrap_gate"]("ffrap_gate", {"status"})')
assert list(G.feed.values())[-1].startswith("Gate (combo): locked")
L.execute('commands["ffrap_gate"]("ffrap_gate", {"clear"})')
assert G.gate is None and list(G.feed.values())[-1] == "Gate cleared (2 actor(s) removed)"
print("gate probe: ok")

# 14. 0.12.0: a vision that cannot go in yet (the save owns none) waits aside; the items after
# it are applied, and it goes in once it can. After a reload it is tried again.
for name in ("ap_in.txt", "ap_out.txt", "ap_state.txt", "seen.tsv"):
    if os.path.exists(path(name)):
        os.remove(path(name))
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write(
    "seed\tS9:1\n"
    "item\t0\tvision\t13100\t1\tWarrior of Light\n"
    "item\t1\titem\t1\t1\tPotion\n"
    "item\t2\tunit\t1004\t1\tLid\n")
L, G = boot()
L.globals().G = G
L.execute(r"""
G.owned, G.visionReady = {}, false
function G.UnlockVision(id)
  if G.owned[id] then return "ok", "already owned" end
  if not G.visionReady then return "wait", "the save owns no vision yet" end
  G.owned[id] = true
  G.log[#G.log + 1] = "vision" .. id
  return "ok", "visionList 2 -> 3"
end
function G.GrantItem(id, n) G.log[#G.log + 1] = "item" .. id .. "x" .. n return "ok", "" end
function G.AddUnit(id) G.log[#G.log + 1] = "unit" .. id return "ok", "" end
""")
G.chests = L.table()
G.shinies = L.table()
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(6)
assert list(G.log.values()) == ["item1x1", "unit1004"], list(G.log.values())
L.execute("G.visionReady = true")
tick(1)
assert list(G.log.values()) == ["item1x1", "unit1004", "vision13100"], list(G.log.values())
tick(2)
assert list(G.log.values()).count("vision13100") == 1, "an unlocked vision is not granted again"
# the game saves to slot 1 (holding all three), then that slot is loaded into a game that lacks
# the vision: the slot's count stands, and the vision alone is tried again
L.execute("G.saveTicks = '5'; G.slotOf['5'] = 1")
tick(2)
L.execute("G.owned = {}; G.saveObj = 'SD_2'")
tick(3)
assert list(G.log.values()).count("vision13100") == 2, list(G.log.values())
assert list(G.log.values()).count("item1x1") == 1
print("waiting vision: ok")

# 15. 0.14.0: ffrap_scale's options (at, hp, power, boss, follow), and follow moving the band when
# the party's level changes, on the field only. 0.15.0: attack and magic apart, party mode's
# defaults (range 2, at 80), and scale.txt. With no seed: round 85 turns ffrap_scale off on a save
# not linked to one.
if os.path.exists(path("ap_state.txt")):
    os.remove(path("ap_state.txt"))
L, G = boot()
L.globals().G = G
L.execute("""
G.scaleCalls, G.partyLv, G.onField = {}, 40, true
function G.PartyLevel() return G.partyLv, "1001:" .. G.partyLv end
function G.LevelBand(lv, range, at, above)
  local c = math.max(1, math.floor(lv * (at or 100) / 100 + 0.5))
  return c - range, c + (above or range), c
end
function G.OnField() return G.onField end
G.check = { 0, 0, nil, false }
function G.ScaleCheck() return G.check[1], G.check[2], G.check[3], G.check[4] end
function G.UnitRows(w) G.shown = w; return { "table T@1", "  298 Metal Gigantuar: level 45" } end
logged = {}
print = function(s) logged[#logged + 1] = tostring(s) end
function G.ScaleEnemies(mode, a, b, boss, knobs)
  G.scaleCalls[#G.scaleCalls + 1] = string.format("%s %s %s %s hp%d atk%d mag%d", mode, tostring(a), tostring(b),
    tostring(boss), knobs.hp, knobs.attack, knobs.magic)
  return 3, "sample", { "1\tSoldier\tlevel 30 -> 3", "2\tBat\tlevel 1 -> 3" }, G.gameChanged
end
""")
calls = lambda: list(G.scaleCalls.values())
L.execute('commands["ffrap_scale"]("ffrap_scale", {"party", "5", "at", "80", "hp", "70", "boss"})')
assert calls() == ["clamp 27 37 true hp70 atk100 mag100"], calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"30", "power", "90"})')
assert calls()[-1] == "fixed 30 nil false hp100 atk90 mag90", calls()
# attack and magic on their own; either one wins over power, in any order
L.execute('commands["ffrap_scale"]("ffrap_scale", {"30", "attack", "60", "power", "80"})')
assert calls()[-1] == "fixed 30 nil false hp100 atk60 mag80", calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"30", "magic", "120"})')
assert calls()[-1] == "fixed 30 nil false hp100 atk100 mag120", calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"20", "10"})')
assert calls()[-1] == "clamp 10 20 false hp100 atk100 mag100", calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"off"})')
assert calls()[-1] == "off nil nil false hp100 atk100 mag100", calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"what"})')
assert len(calls()) == 6, "a bad command changes nothing"
# party alone: range 2 around 80% of the party's level (40 -> 32)
L.execute('commands["ffrap_scale"]("ffrap_scale", {"party"})')
assert calls()[-1] == "clamp 30 34 false hp100 atk100 mag100", calls()
# the changed rows went to scale.txt, under a header line
txt = read("scale.txt").splitlines()
assert txt[0].startswith("-- ffrap_scale clamp 30 34") and txt[1] == "1\tSoldier\tlevel 30 -> 3" and len(txt) == 3, txt
# follow: nothing while the level stands; a new band when it changes; nothing in a battle
L.execute('commands["ffrap_scale"]("ffrap_scale", {"party", "3", "at", "50", "follow"})')
assert calls()[-1] == "clamp 17 23 false hp100 atk100 mag100", calls()
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
tick(20)
assert len(calls()) == 8, calls()
L.execute("G.partyLv = 42; G.onField = false")
tick(20)
assert len(calls()) == 8, "not off the field"
L.execute("G.onField = true")
tick(20)
assert calls()[-1] == "clamp 18 24 false hp100 atk100 mag100" and len(calls()) == 9, calls()
# 0.15.1: ffrap_scale alone says what is in force; the notice names the band
logs = lambda: list(L.globals().logged.values())
assert any("rescaled to party level 40: levels 17 to 23" in l for l in logs()), logs()
L.execute('commands["ffrap_scale"]("ffrap_scale", {})')
assert len(calls()) == 9, "the status changes nothing"
assert any("scale: levels 18 to 24, follow on (party level 42); table check: 0 rows, 0 differ" in l for l in logs()), logs()
# show: one enemy's rows, by name or id
L.execute('commands["ffrap_scale"]("ffrap_scale", {"show", "metal", "gigantuar"})')
assert G.shown == "metal gigantuar" and any("298 Metal Gigantuar: level 45" in l for l in logs()), logs()
# the table no longer holds what we wrote: logged and written again, on the field only
L.execute('G.check = { 300, 12, "Metal Gigantuar (298): level 52, wrote 20", false }')
L.execute("G.onField = false")
tick(40)
assert len(calls()) == 9, "nothing off the field"
L.execute("G.onField = true")
tick(20)
assert len(calls()) == 10 and calls()[-1] == "clamp 18 24 false hp100 atk100 mag100", calls()
assert any("the table changed under us: 12 of 300 rows differ (Metal Gigantuar (298): level 52, wrote 20)" in l
           for l in logs()), logs()
L.execute("G.gameChanged = 12")
L.execute('commands["ffrap_scale"]("ffrap_scale", {"party", "3", "at", "50", "follow"})')
assert any("something else had changed 12 rows since our last write" in l for l in logs()), logs()
L.execute("G.gameChanged = nil")
L.execute('G.check = { 300, 0, nil, false }')
# a plain ffrap_scale turns follow off
L.execute('commands["ffrap_scale"]("ffrap_scale", {"off"})')
L.execute("G.partyLv = 60")
tick(20)
assert calls()[-1] == "off nil nil false hp100 atk100 mag100" and len(calls()) == 12, calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {})')
assert any("no rescale in force" in l for l in logs()), logs()
# off: the check does not run, so nothing is written again
L.execute('G.check = { 300, 12, "x", true }')
tick(40)
assert len(calls()) == 12, calls()
# a fixed level keeps its own text, and is written again as it was
L.execute('commands["ffrap_scale"]("ffrap_scale", {"30"})')
assert any("rescaled, every enemy at level 30" in l for l in logs()), logs()
tick(20)
assert calls()[-1] == "fixed 30 nil false hp100 atk100 mag100" and len(calls()) == 14, calls()
L.execute('G.check = { 300, 0, nil, false }')
print("scale options and follow: ok")

# 16. 0.15.0: ffrap_noland's commands reach game.lua with the right arguments
L, G = boot(CAPTURE)
L.globals().G = G
L.execute("""
G.nl = {}
local box = { name = "BOX", x = 1, y = 2, z = 3, ex = 4, ey = 5, ez = 6, yaw = 0, cond = "c" }
function G.NoLandLine(b) return b.name end
function G.NoLandLock(which, on) G.nl[#G.nl + 1] = "lock " .. which .. " " .. tostring(on) return { box } end
function G.NoLandCollision(b) return "collision of " .. b.name end
function G.NoLandRefresh() G.nl[#G.nl + 1] = "refresh" return 1, 2, 1 end
function G.NoLandHere() G.nl[#G.nl + 1] = "here" return { box }, { x = 1, y = 2, z = 3 } end
function G.NoLandShow(on, w) G.nl[#G.nl + 1] = "show " .. tostring(on) .. " " .. tostring(w) return 7 end
function G.NoLandSpawn(half, top) G.nl[#G.nl + 1] = "spawn " .. tostring(half) .. " " .. tostring(top) return box end
function G.GroundUnder()
  return { { name = "BP_MapNonLandingArea_C_1", z = 370, box = true }, { name = "Landscape_1", z = 50, box = false } }
end
function G.NoLandOff() G.nl[#G.nl + 1] = "off" return 2 end
function G.NoLandChannel(ch, r) G.nl[#G.nl + 1] = "channel " .. ch .. " " .. r return 1 end
""")
for args in ('{"lock", "Pharm"}', '{"unlock", "mysidia"}', '{"here"}', '{"show", "30"}', '{"hide"}', '{"spawn"}',
             '{"spawn", "3000", "2500"}', '{"channel", "3", "0"}', '{"channel", "3", "7"}', '{"refresh"}', '{"off"}'):
    L.execute('commands["ffrap_noland"]("ffrap_noland", %s)' % args)
assert list(G.nl.values()) == ["lock pharm true", "lock mysidia false", "here", "show true 30", "show false nil",
                               "spawn 2000 nil", "spawn 3000 2500", "channel 3 0", "refresh", "off"], list(G.nl.values())
# 0.17.0: `here` logs what a trace straight down meets, and names the ground's height
logged = list(L.globals().logged.values())
assert any("trace down hit BP_MapNonLandingArea_C_1 (a no-landing box) at z 370" in s for s in logged), logged
assert any("trace down hit Landscape_1 at z 50" in s for s in logged)
assert any("Under 1 no-landing boxes: BOX; ground at z 50" in s for s in logged)
print("noland commands: ok")

# 17. 0.15.2 (round 33): the FFR Randomizer mod next to this one undoes our chest blanks and enemy
# rescale every 3 seconds. Its enabled.txt, or a "FFRRandomizer : 1" line in mods.txt, turns it on.
# The warning is logged at start and shown once, on the first save load.
WARNING = "FFR Randomizer is on"
randomizer = os.path.join(MODS, "FFRRandomizer")
os.makedirs(randomizer)


def warnings_after_two_loads():
    L, G = boot(CAPTURE)
    at_start = sum(WARNING in s for s in L.globals().logged.values())
    L.execute("tickFn()")
    G.ready = False
    L.execute("tickFn()")
    G.ready = True
    L.execute("tickFn()")
    return at_start, sum(WARNING in s for s in L.globals().logged.values())


assert warnings_after_two_loads() == (0, 0)
open(os.path.join(randomizer, "enabled.txt"), "w").close()
assert warnings_after_two_loads() == (1, 2)          # the start line, then one notice
os.remove(os.path.join(randomizer, "enabled.txt"))
open(os.path.join(MODS, "mods.txt"), "w").write("Keybinds : 1\nFFRRandomizer : 0\n")
assert warnings_after_two_loads() == (0, 0)
open(os.path.join(MODS, "mods.txt"), "w").write("Keybinds : 1\nFFRRandomizer : 1\n")
assert warnings_after_two_loads() == (1, 2)
os.remove(os.path.join(MODS, "mods.txt"))
print("randomizer warning: ok")

# 18. 0.16.0: ffrap_openstart on makes the prologue skip go to the open world start (story 7090,
# the Crystal Tower). Off by default; the switch is kept in ap_state.txt; `at` moves the arrival.
OPEN_MAP, SHRINE_MAP = 3280, 3001
L, G = boot()
G.story = 1005
load(G, "SD_OPEN", "0")
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipOpen is False and G.reloadMap == SHRINE_MAP, (G.skipOpen, G.reloadMap)
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"on"})')
assert "openstart\t1\n" in read("ap_state.txt"), read("ap_state.txt")
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"at", "100", "-200", "300.5"})')
assert (G.OPEN_START.x, G.OPEN_START.y, G.OPEN_START.z) == (100, -200, 300.5)
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"at", "100"})')
assert G.OPEN_START.x == 100, "a short `at` changes nothing"
L, G = boot()                                     # the switch survives a restart
G.story = 1005
load(G, "SD_OPEN2", "0")
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipOpen is True and G.reloadMap == OPEN_MAP, (G.skipOpen, G.reloadMap)
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"off"})')
assert "openstart\t0\n" in read("ap_state.txt")

# 0.16.1 (round 35: the switch was off and the log did not say so): an Archipelago new game logs
# whether it is on. `now` writes the open world start into the loaded save, saves it to its slot
# and reloads at the Crystal Tower; with no save loaded it does nothing.
L, G = boot(CAPTURE)
G.titleOk = True
L.execute("tickFn()")                             # the first tick adds the entry and hooks the choice
L.execute("""param = { v = 5 }; function param:get() return self.v end; function param:set(x) self.v = x end""")
L.execute('hooks["/Script/mucha.CPP_VM_Title:ExecuteEntry"](nil, param)')
assert any("open world start is off" in s for s in L.globals().logged.values())
G.ready = False
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"now"})')
assert G.openStarts == 0, "no save loaded"
G.story = 1030
G.slotOf = L.table_from({"800": 0})               # the skipped save, in slot 0
load(G, "SD_OPEN3", "800")
reloads = len(list(G.reloads.values()))
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"now"})')
assert G.openStarts == 1 and G.reloadMap == OPEN_MAP, (G.openStarts, G.reloadMap)
assert list(G.reloads.values())[reloads:] == [0], list(G.reloads.values())
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"now", "4"})')
assert list(G.reloads.values())[-1] == 4, "an explicit slot"
# 0.18.0: `air` chooses the world-map arrival for this run; the reload then expects map 1000
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"air"})')
assert any("Open world start is off (air): story 8000, map 1000" in s for s in L.globals().logged.values())
L.execute('commands["ffrap_openstart"]("ffrap_openstart", {"now"})')
assert G.reloadMap == 1000, G.reloadMap
# Round 37: `air` was lost at a restart and the next start came up at the dock. A choice is kept
# under its own key, and a game with no choice writes no key
assert "openarrival\tair\n" in read("ap_state.txt"), read("ap_state.txt")
L, G = boot()
assert G.OPEN_START.name == "air", G.OPEN_START.name
# ffrap_chats shows the state; `done` marks them and says so in the log
G.ready = True
L.execute('commands["ffrap_chats"]("ffrap_chats", {})')
assert (G.chatsMarked or 0) == 0
L.execute('commands["ffrap_chats"]("ffrap_chats", {"done"})')
assert G.chatsMarked == 1
L.execute('commands["ffrap_visions"]("ffrap_visions", {})')
# Round 40: the continent locks. Off by default and writing no key; on keeps them in step, and
# the switch survives a restart. Off clears the boxes.
assert "continentlocks" not in read("ap_state.txt"), read("ap_state.txt")
L.execute('commands["ffrap_lock"]("ffrap_lock", {"on"})')
assert "continentlocks\t1\n" in read("ap_state.txt"), read("ap_state.txt")
L.execute('commands["ffrap_lock"]("ffrap_lock", {"open", "pharm"})')
assert G.lockOpens.pharm is True
L.execute('commands["ffrap_lock"]("ffrap_lock", {"close", "narnia"})')
assert G.lockOpens.narnia is None, "a bad name changes nothing"
L.execute('commands["ffrap_lock"]("ffrap_lock", {"off"})')
assert G.lockCleared is True and "continentlocks\t0\n" in read("ap_state.txt"), read("ap_state.txt")
# Round 44: the seed decides the start: open world, locks and party, until a command says otherwise
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS:0:1\ncfg\topenworld\t1\ncfg\tparty\t1007,1006\n")
L, G = boot()
L.execute("tickFn()")
G.story = 1005
load(G, "SD_SEED", "0")
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipOpen is True and list(G.skipParty.values()) == [1007, 1006], (G.skipOpen, G.skipParty)
L.execute("worldParam = { get = function() return 'the world' end }")
G.hookPlace = None
L.execute("loadMapHook(nil, worldParam)")
assert G.hookPlace is True, "the seed turns the locks on, even over an old saved off"
L.execute('commands["ffrap_lock"]("ffrap_lock", {"off"})')
L.execute("loadMapHook(nil, worldParam)")
assert G.hookPlace is False, "an explicit off wins"
# Round 77: after a map load, ap_trace.txt names each step of the loops, so a crash shows whether
# this mod's loop was running and where. Round 79: it runs all the time, and starts again after
# TRACE_LINES lines so it stays small.
trace = read("ap_trace.txt").splitlines()
assert trace[0].endswith("map load"), trace
L.execute("tickFn()")
trace = read("ap_trace.txt").splitlines()
steps = [line.split(" ", 3)[3] for line in trace[1:]]
assert steps[0] == "tick" and steps[-1] == "tick done" and "items" in steps and "loot" in steps, steps
TRACE_LINES = int(re.search(r"state.TRACE_LINES, state.traceLines, state.traceFile = (\d+)",
                            open(os.path.join(SRC, "Scripts", "main.lua"), encoding="utf-8").read()).group(1))
lines_per_tick = len(trace)
for _ in range(2 * TRACE_LINES // lines_per_tick):
    L.execute("tickFn()")
trace = read("ap_trace.txt").splitlines()
assert trace[-1].endswith("tick done") and len(trace) <= TRACE_LINES, ("still tracing, and started again", len(trace))
L.execute('commands["ffrap_lock"]("ffrap_lock", {"on"})')
assert "continentlocks\t1\n" in read("ap_state.txt")
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").close()
L, G = boot()
L.execute("worldParam = { get = function() return 'the world' end }")
L.execute('commands["ffrap_lock"]("ffrap_lock", {"off"})')
# Round 46: with the seed's cfg, crystals are patched once per save and report by their flag, and
# shinies are blanked
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS:0:1\ncfg\topenworld\t1\ncfg\tshards\t1\ncfg\tcrystals\t1\n")
L, G = boot()
L.execute("tickFn()")
G.story = 8000
load(G, "SD_CRYSTAL", "0")
L.execute('commands["ffrap_bind"]("ffrap_bind", {})')
L.globals().G = G
L.execute("G.shinies = { { uid = 1, itemId = 5, money = -1, open = false } }")
L.execute("for i = 1, 6 do tickFn() end")
assert G.crystalPatches == 1, G.crystalPatches
assert "check\tcrystal:10200" not in read("ap_out.txt")
assert G.blanked >= 1, "a shiny is blanked"
L.execute("local old = G.GetFlag; G.GetFlag = function(i) if i == 1000 then return true end return old and old(i) end")
L.execute("for i = 1, 4 do tickFn() end")
assert read("ap_out.txt").count("check\tcrystal:10200\n") == 1, read("ap_out.txt")
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").close()
# Round 44: in a seed, a member received in the open world joins at the party's level; one
# received before the skip, or already in the party, is left alone
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS:0:1\ncfg\topenworld\t1\n")
L, G = boot()
L.execute("tickFn()")
G.story = 8000
load(G, "SD_LEVEL", "0")
L.execute('commands["ffrap_grant"]("ffrap_grant", {"unit", "1007"})')
assert G.leveled.id == 1007 and G.leveled.level == 7, G.leveled
G.leveled = None
G.story = 1005
L.execute('commands["ffrap_grant"]("ffrap_grant", {"unit", "1008"})')
assert G.leveled is None, "before the skip the party is the prologue's Fina"
G.story = 8000
G.unitDetail = "already joined"
L.execute('commands["ffrap_grant"]("ffrap_grant", {"unit", "1008"})')
assert G.leveled is None, "someone already in the party keeps their level"
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").close()
L, G = boot()
L.execute("worldParam = { get = function() return 'the world' end }")
L.execute('commands["ffrap_lock"]("ffrap_lock", {"off"})')
# Round 42: each map load goes to the game file with the switch's state
L.execute("""worldParam = { get = function() return "the world" end }""")
L.execute('loadMapHook(nil, worldParam)')
assert G.hookWorld == "the world" and G.hookPlace is False, (G.hookWorld, G.hookPlace)
L.execute('commands["ffrap_lock"]("ffrap_lock", {"on"})')
L.execute('loadMapHook(nil, worldParam)')
assert G.hookPlace is True
L.execute('commands["ffrap_lock"]("ffrap_lock", {"off"})')
# Round 39: `state` reads the airship's save fields and writes no spawn condition
L.execute('commands["ffrap_airship"]("ffrap_airship", {"state"})')
assert G.airshipWrote is None, G.airshipWrote
print("open world start: ok")

# 19. 0.17.0: probes for the opening's input lock. `ffrap_skip <slot> force` skips during the
# opening (story 1000) anyway, and says so; without force it still waits for 1005. `ffrap_input`
# logs the controller's state, and `fix` runs game.InputFix, logging each step.
OPENING_STORY = 1000
L, G = boot(CAPTURE)
G.story = OPENING_STORY
load(G, "SD_FORCE", "0")
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipRuns == 0, "refused before 1005"
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0", "force"})')
assert G.skipRuns == 1 and list(G.reloads.values())[-1] == 0, G.skipRuns
logged = list(L.globals().logged.values())
assert any(f"skip: forced at story {OPENING_STORY}" in s for s in logged), logged
L.globals().G = G
L.execute("""
function G.InputState() return "controller PC, move input ignored " .. tostring(G.locked) end
G.locked = true
function G.InputFix(step) step("ResetIgnoreInputFlags"); G.locked = false; return { "EnableInput: no" } end
""")
L.execute('commands["ffrap_input"]("ffrap_input", {})')
L.execute('commands["ffrap_input"]("ffrap_input", {"fix"})')
logged = list(L.globals().logged.values())
assert sum("input: controller PC, move input ignored true" in s for s in logged) == 2, logged
assert any("input step: ResetIgnoreInputFlags" in s for s in logged)
assert any("input: failed: EnableInput: no" in s for s in logged)
assert any("input after fix: controller PC, move input ignored false" in s for s in logged)
# ffrap_inspect's label keeps two states of one object in two files
L.execute('function G.Inspect(target, out) out("object", target) return true end')
L.execute('commands["ffrap_inspect"]("ffrap_inspect", {"CPP_InputManager", "locked"})')
L.execute('commands["ffrap_inspect"]("ffrap_inspect", {"CPP_InputManager"})')
assert read("inspect_CPP_InputManager_locked.tsv") == "object\tCPP_InputManager\n", read("inspect_CPP_InputManager_locked.tsv")
assert read("inspect_CPP_InputManager.tsv") == "object\tCPP_InputManager\n"
print("input lock probes: ok")

# Round 48: in a seed, the Vision Enhancement screen can always be closed; outside one the game decides
VISION_EXIT = 'posts["/Script/mucha.CPP_BFL_VisionUpgrade:IsVisionUpgrade"]'
NO = "{ get = function() return false end }"
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS:0:1\ncfg\topenworld\t1\n")
os.remove(path("ap_state.txt"))                             # a new session: its new game is linked
L, G = boot()
tick(1)
assert L.eval(VISION_EXIT) is not None, "hooked at the first tick"
assert L.execute(f"return {VISION_EXIT}(nil, {NO})") is None, "round 100: not before the save is the seed's"
tick(12)
assert L.execute(f"return {VISION_EXIT}(nil, {NO})") is True, "a seed answers true"
assert L.execute(f"return {VISION_EXIT}(nil, nil)") is True, "even if the game's answer cannot be read"
open(path("ap_in.txt"), "w", encoding="utf-8", newline="\n").write("seed\tS:0:1\ncfg\topenworld\t0\n")
L, G = boot()
tick(1)
assert L.execute(f"return {VISION_EXIT}(nil, {NO})") is None, "a vanilla game is left alone"
print("vision screen exit: ok")

# Round 49: a seed scales enemies by itself, once the open world start is reached, and follows the
# party: HP and power at 75%, bosses too. The console wins for the rest of the run. A save that is
# not the seed's goes back. A seed that is not an open world start is left alone.
SCALE_STUB = """
G.scaleCalls, G.partyLv, G.onField = {}, 10, true
G.party = { 1001, 1002, 1003, 1004 }
function G.PartyIds() return G.party end
function G.PartyLevel() return G.partyLv, "1001:" .. G.partyLv end
function G.LevelBand(lv, range, at, above)
  local c = math.max(1, math.floor(lv * (at or 100) / 100 + 0.5))
  return c - range, c + (above or range), c
end
function G.OnField() return G.onField end
G.wins = 0
function G.WinCount() return G.wins end
function G.ScaleCheck() return 0, 0, nil, false end
function G.ScaleEnemies(mode, a, b, boss, knobs, bossBand)
  G.scaleCalls[#G.scaleCalls + 1] = string.format("%s %s %s %s hp%d atk%d mag%d", mode, tostring(a), tostring(b),
    tostring(boss), knobs.hp, knobs.attack, knobs.magic) ..
    (bossBand and string.format("; bosses %d %d hp%d", bossBand.a, bossBand.b, bossBand.knobs.hp) or "") ..
    (bossBand and string.format("; MRP +%d/+%d", knobs.mrpLift or 0, bossBand.knobs.mrpLift or 0) or "")
  return 3, "sample", {}, 0
end
"""
inbox("seed\tS49:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_SCALE", "0", {"600": 3})
L.globals().G = G
L.execute(SCALE_STUB)
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
calls = lambda: list(G.scaleCalls.values())
G.story = 1000
G.chests = L.table()
tick(30)
assert calls() == [], "not before the open world start"
G.story = 8000
tick(10)
# Normal by default. Round 101: every strength came down a step, and enemies lose more HP than
# Attack. Party level 10 is a quarter of the way up the ramp: centre 87% (9), HP 74%, attack 89%,
# 1 under and 1 over; bosses 101% (10), 101%, 2 each way. MRP is paid as at level 10: enemies 1
# level up, bosses none.
NORMAL_10 = "clamp 8 10 true hp74 atk89 mag89; bosses 8 12 hp101; MRP +1/+0"
assert calls() == [NORMAL_10], calls()
tick(10)
assert len(calls()) == 1, "once"
G.partyLv = 30
tick(10)
assert calls()[-1] == "clamp 27 29 true hp85 atk100 mag100; bosses 29 33 hp105; MRP +2/+0", "the top of the ramp: centre 92% (28), HP 85%, attack 100%; bosses 103% (31), 105%"
# Round 100: above 30 the bands follow 3 levels for every 4 the party gains. Party level 40 counts
# as 37.5: enemies centre 35, bosses 39 (103%), MRP as level 38.
G.partyLv = 40
tick(10)
assert calls()[-1] == "clamp 34 36 true hp85 atk100 mag100; bosses 37 41 hp105; MRP +3/+0", calls()
# Level 60 counts as 52.5: the final boss (Chaotic Darkness, level 55) meets the party at 54.
G.partyLv = 60
tick(10)
assert calls()[-1] == "clamp 47 49 true hp85 atk100 mag100; bosses 52 56 hp105; MRP +5/+0", calls()
L.execute('commands["ffrap_set"]("ffrap_set", {"strength", "casual"})')
tick(10)
assert calls()[-1] == "clamp 45 47 true hp75 atk90 mag90; bosses 51 55 hp100; MRP +7/+0", "casual at 60: bosses at 53, under the game's own 55"
L.execute('commands["ffrap_set"]("ffrap_set", {"reset"})')
G.partyLv = 3
tick(10)
NORMAL_3 = "clamp 2 4 true hp70 atk85 mag85; bosses 1 5 hp100; MRP +0/+0"
assert calls()[-1] == NORMAL_3, "below the ramp: centre 85% (3), HP 70%, attack 85%; bosses 100%, 100%"
# Round 56: a new strength rescales at once. Round 101: expert is the old normal with 10% less
# HP: centre 90% (3), HP 80%, attack 90%, 3 over; bosses 105%, 105%. Casual: centre 80% (2),
# HP 60%, attack 75%; bosses 95% (3), 90%, and MRP paid 1 level up.
L.execute('commands["ffrap_set"]("ffrap_set", {"strength", "expert"})')
tick(10)
assert calls()[-1] == "clamp 2 6 true hp80 atk90 mag90; bosses 1 5 hp105; MRP +0/+0", calls()
L.execute('commands["ffrap_set"]("ffrap_set", {"strength", "casual"})')
tick(10)
assert calls()[-1] == "clamp 1 3 true hp60 atk75 mag75; bosses 1 5 hp90; MRP +1/+0", calls()
L.execute('commands["ffrap_set"]("ffrap_set", {"reset"})')
tick(10)
assert calls()[-1] == NORMAL_3, "back to normal"
# Round 77: bosses lose 12% power for each empty slot of four. Two in the party: 100% x 76%.
G.party = L.table_from([1001, 1002])
tick(10)
assert calls()[-1] == "clamp 2 4 true hp70 atk85 mag85; bosses 1 5 hp76; MRP +0/+0", calls()
G.party = L.table_from([1001])
tick(10)
assert calls()[-1] == "clamp 2 4 true hp70 atk85 mag85; bosses 1 5 hp64; MRP +0/+0", "one in the party: 100% x 64%"
n = len(calls())
tick(10)
assert len(calls()) == n, "no rescale while nothing changes"
G.party = L.table_from([1001, 1002, 1003, 1004])
tick(10)
assert calls()[-1] == NORMAL_3, calls()
# Round 102: a line per battle won: the time off the field, the strength and the party's level.
# A menu (off the field, no win) logs nothing.
TICK_S, BATTLE_TICKS = 0.5, 4
G.wins = 5
tick(1)
L.execute(CAPTURE)
G.onField = False
tick(BATTLE_TICKS)
G.onField = True
tick(1)
assert not any("battle: won" in l for l in L.eval("logged").values()), "no win, no line"
G.onField = False
tick(BATTLE_TICKS)
G.wins = 6
G.onField = True
tick(1)
won = [l for l in L.eval("logged").values() if "battle: won" in l]
assert len(won) == 1 and f"battle: won (save's win count 6), {BATTLE_TICKS * TICK_S:.1f} s off the field; strength normal, party level 3" in won[0], won
G.saveObj, G.saveTicks = "SD_OTHER", "600"     # a save in a slot the seed does not hold
tick(30)
assert calls()[-1].startswith("off "), calls()

inbox("seed\tS49b:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_SCALE2", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
G.story = 1000
G.chests = L.table()
tick(12)
G.story = 8000
tick(10)
assert calls() == [NORMAL_10], calls()
L.execute('commands["ffrap_scale"]("ffrap_scale", {"off"})')
G.partyLv = 30
tick(30)
assert len(calls()) == 2 and calls()[-1].startswith("off "), calls()

inbox("seed\tS49c:0:1\ncfg\topenworld\t0\n", "w")
L, G = boot5("SD_SCALE3", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
G.story = 8000
G.chests = L.table()
tick(30)
assert calls() == [], "not an open world seed"
print("seed scaling: ok")

# Round 100 (the user): a new game of the game's own started Rain at level 55, Fina's prologue
# level. A save that is not the seed's gets none of the seed's writes: no slot level, no table
# patches, the game's airship condition and no messages from the client. After the seed's save
# patched the tables in this run, it is told to restart the game.
os.remove(path("ap_state.txt"))
inbox("seed\tS100:0:1\ncfg\topenworld\t1\ncfg\tcrystals\t1\ncfg\tbosses\t1\ncfg\tairship\t0\n", "w")
L, G = boot5("SD_SEED", "0", {"700": 4})
L.execute(CAPTURE)
G.story = 8000
tick(30)
assert G.crystalPatches == 1 and G.bossPatches == 1, "the seed's new game is patched"
seed_syncs = G.slotSyncs
assert seed_syncs and seed_syncs > 0, "and its unjoined Rain follows the party's level"
assert list(G.airshipSyncs.values())[-1] is True, "the airship waits for its item"
G.saveObj, G.saveTicks = "SD_MAIN", "700"                    # the player's own save, in slot 4
tick(30)
assert G.crystalPatches == 1 and G.bossPatches == 1, "no patches for the player's own save"
assert G.slotSyncs == seed_syncs, "Rain's level is left alone"
assert list(G.airshipSyncs.values())[-1] is False, "the game's own airship condition"
restart = [s for s in L.eval("logged").values() if "restart the game before playing this save" in s]
assert len(restart) == 1, list(L.eval("logged").values())
inbox("msg\tSomeone found their Potion\n")
tick(3)
assert not any("Someone found" in s for s in L.eval("logged").values()), "no messages from the client"

# A run that starts on the player's own save writes nothing of the seed's, even before the save is
# judged: the last save was not the seed's (ap_state.txt's lastok).
L, G = boot5("SD_MAIN", "700", {"700": 4})
L.execute(CAPTURE)
G.story = 8000
tick(30)
assert not G.crystalPatches and not G.bossPatches and not G.slotSyncs, (G.crystalPatches, G.slotSyncs)
assert True not in list(G.airshipSyncs.values()), list(G.airshipSyncs.values())
assert not any("restart the game" in s for s in L.eval("logged").values()), "nothing was patched in this run"

# With no session at all, no save is the seed's.
os.remove(path("ap_state.txt"))
os.remove(path("ap_in.txt"))
L, G = boot5("SD_NEW", "0", {})
L.execute(CAPTURE)
G.story = 8000
tick(30)
assert not any("is linked to the seed" in s for s in L.eval("logged").values()), list(L.eval("logged").values())
assert any("locks: off for a save not linked to the seed" in s for s in L.eval("logged").values())
assert list(G.log.values()) == []
print("saves not linked to the seed: ok")

# Round 57: an open world seed's save gets the Chocobo once; round 58: and the shipyard's elevators
inbox("seed\tS57:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_CHOCOBO", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return G.held or 0 end")
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.chests = L.table()
G.story = 1000
tick(12)
assert "item30002x1" not in list(G.log.values()), "not before the open world start"
G.story = 8000
tick(12)
assert list(G.log.values()).count("item30002x1") == 1, list(G.log.values())
assert G.shipyardCalls is None, "only in the shipyard"
G.map = 3060
tick(12)
assert G.shipyardCalls and G.shipyardCalls > 0
G.map = 2002
G.held = 0
tick(12)
assert list(G.log.values()).count("item30002x1") == 1, "once per save loaded"

# Round 113 (the user): the Tower of Mysidia's lift up waited at its top after a fast travel out.
# Lifts (and, round 114, rafts) go back as on a first visit once per map the player is on; on
# their map, the live state is logged when it changes.
TOWER_OF_MYSIDIA = 3200
L.execute(CAPTURE)
resets_before = len(G.liftResets)
tick(12)
assert len(G.liftResets) == resets_before, "once per map, not each tick"
G.map = TOWER_OF_MYSIDIA
L.execute("G.liftStops = 'lifts 13 at 0, 32 at 0'")
tick(12)
assert list(G.liftResets.values())[-1] == TOWER_OF_MYSIDIA
lines = list(L.eval("logged").values())
assert sum("rides on map 3200: lifts 13 at 0, 32 at 0" in line for line in lines) == 1, lines
L.execute("G.liftStops = 'lifts 13 at 1, 32 at 0'")
tick(12)
assert any("rides on map 3200: lifts 13 at 1, 32 at 0" in line for line in L.eval("logged").values())
G.map = 1000
L.execute("G.liftPending = true")
tick(12)
assert list(G.liftResets.values())[-1] == 1000
assert any("rides: back as on a first visit: 3200:13 1 -> 0" in line for line in L.eval("logged").values())

inbox("seed\tS57b:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_CHOCOBO2", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
G.chests = L.table()
G.story = 8000
tick(12)
assert "item30002x1" not in list(G.log.values()), "a save that holds the saddle gets none"

# Round 67: `cfg chocobo 0` (start_with_chocobo off) makes the saddle an item, so none at the start
inbox("seed\tS67:0:1\ncfg\topenworld\t1\ncfg\tchocobo\t0\n", "w")
L, G = boot5("SD_CHOCOBO3", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 0 end")
G.chests = L.table()
G.story = 8000
tick(12)
assert "item30002x1" not in list(G.log.values()), list(G.log.values())
print("chocobo and shipyard: ok")

# Round 67: the walking crossings come from crossings.txt when there is one, and a bad line is skipped.
# `ffrap_gate mark` adds one ahead of the player, `unmark` takes the nearest away again, and the
# ferry is kept in step on every lock check.
GRANDSHELT_BRIDGE = "grandshelt\tlanzelt\t14000\t17600\t120\t90.0\t3.00\n"
KOLOBOS_PASS = "lanzelt\tkolobos\t8300\t12000\t80\t0.0\t2.50\n"
with open(path("crossings.txt"), "w", encoding="utf-8", newline="\n") as f:
    f.write(GRANDSHELT_BRIDGE + KOLOBOS_PASS + "narnia\tlanzelt\t0\t0\t0\t0\t1\n")
inbox("seed\tS67b:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_CROSS", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
G.chests = L.table()
G.story = 8000
tick(12)
assert G.ferrySyncs > 0, "the ferry is synced with the locks"
last = L.eval("G.crossingLists[#G.crossingLists]")
assert len(last) == 2 and last[1].a == "grandshelt" and last[2].b == "kolobos" and last[2].scale == 2.5, len(last)
G.map = 1000
L.execute("function G.CurrentMap() return G.map end")
L.execute("function G.PlayerPose() return { x = 9000, y = 12000, z = 75, yaw = 90.0, fx = 0.0, fy = 1.0 } end")
L.execute('commands["ffrap_gate"]("ffrap_gate", {"mark", "Lanzelt", "kolobos", "4"})')
lines = read("crossings.txt").splitlines()
assert len(lines) == 2 + 1 and lines[2] == "lanzelt\tkolobos\t9000\t12150\t75\t270.0\t4.00", lines
L.execute('commands["ffrap_gate"]("ffrap_gate", {"mark", "lanzelt", "narnia"})')
assert len(read("crossings.txt").splitlines()) == 3, "an unknown continent is refused"
L.execute('commands["ffrap_gate"]("ffrap_gate", {"unmark"})')
assert read("crossings.txt") == GRANDSHELT_BRIDGE + KOLOBOS_PASS, read("crossings.txt")
assert G.crossingsCleared is True, "the blockers are placed again from the new list"
# Round 67: on foot the pawn always says it faces north, so a mark goes the way the player last
# walked: here 200 to the south-west (-y), so the cart is 150 further on, turned back to face them.
L.execute("G.px, G.py = 9000, 12000; function G.PlayerPose() return { x = G.px, y = G.py, z = 75, yaw = 0.0, fx = 1.0, fy = 0.0 } end")
tick(4)
G.py = 11800
tick(4)
L.execute('commands["ffrap_gate"]("ffrap_gate", {"mark", "lanzelt", "kolobos"})')
assert read("crossings.txt").splitlines()[2] == "lanzelt	kolobos	9000	11650	75	90.0	2.00", read("crossings.txt")
# move, turn and size change the nearest one where it stands
L.execute('commands["ffrap_gate"]("ffrap_gate", {"move", "-20", "35"})')
L.execute('commands["ffrap_gate"]("ffrap_gate", {"turn", "45"})')
L.execute('commands["ffrap_gate"]("ffrap_gate", {"size", "1.5"})')
assert read("crossings.txt").splitlines()[2] == "lanzelt	kolobos	8980	11685	75	135.0	1.50", read("crossings.txt")
assert read("crossings.txt").startswith(GRANDSHELT_BRIDGE + KOLOBOS_PASS), "the others are left alone"
os.remove(path("crossings.txt"))
# with no crossings.txt, the mod's own list is used
L, G = boot5("SD_CROSS2", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
G.chests = L.table()
G.story = 8000
tick(12)
last = L.eval("G.crossingLists[#G.crossingLists]")
assert len(last) == 1 and last[1].x == 13684 and last[1].b == "lanzelt", len(last)
assert not os.path.exists(path("crossings.txt")), "nothing is written until a crossing is changed"
print("crossings: ok")

# Round 69: `cfg airship 0` starts the seed on foot on its starting continent, hides the airship
# behind its item's flag from the first ticks, and parks it where the player stands on the world
# map once the flag turns on, once.
FOOT_START_MAP = 1000
inbox("seed\tS69:0:1\ncfg\topenworld\t1\ncfg\tairship\t0\ncfg\tcontinent\tLanzelt\n", "w")
L, G = boot()
L.execute("tickFn()")
G.story = 1005
load(G, "SD_FOOT", "0")
L.execute('commands["ffrap_skip"]("ffrap_skip", {"0"})')
assert G.skipArrival.name == "foot lanzelt" and G.reloadMap == FOOT_START_MAP, (G.skipArrival, G.reloadMap)
assert list(G.airshipSyncs.values())[-1] is True, "hidden before any map loads"
inbox("seed\tS69b:0:1\ncfg\topenworld\t1\ncfg\tairship\t0\ncfg\tcontinent\tlanzelt\n", "w")
L, G = boot5("SD_AIR", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
L.execute("G.map = 1000; function G.CurrentMap() return G.map end")
L.execute("G.pawn = 'BP_MapUnit_Player_Field_C'")
L.execute("function G.PlayerPose() return { class = G.pawn, x = 500, y = 600, z = 7, yaw = 0, fx = 1, fy = 0 } end")
L.execute("G.airshipFlag = false; local old = G.GetFlag; G.GetFlag = function(i) if i == G.AIRSHIP_FLAG then return G.airshipFlag end return old and old(i) end")
G.chests = L.table()
G.story = 8000
tick(12)
assert len(G.parks) == 0, "no airship yet"
G.airshipFlag = True
tick(12)
# Round 72: it waits at the seed's start even when it comes on the world map: one parked where
# the player stood, inside Gronoa, could not take off
assert list(G.parks.values()) == ["12470 14980 65"], list(G.parks.values())
tick(12)
assert len(G.parks) == 1, "parked once"
# received in a town, the same
L.execute("G.airshipFlag = false")
tick(12)
L.execute("G.pawn = 'BP_MapUnit_Player_C'")
G.airshipFlag = True
tick(12)
assert list(G.parks.values())[-1] == "12470 14980 65", list(G.parks.values())
L.execute('commands["ffrap_airship"]("ffrap_airship", {"home"})')
assert len(G.parks) == 3 and list(G.parks.values())[-1] == "12470 14980 65", "home parks it at the start"
# Round 112 (the user's v0.31.1 run): one that shows up away from the start is moved there,
# the first time an airship is on the world map after it came. Not in town; once only.
assert G.shipMoves == 0
L.execute(CAPTURE)
L.execute("G.shipsOnMap, G.shipFar, G.map = 1, true, 2030")
tick(12)
assert G.shipMoves == 0, "not while in town"
L.execute("G.pawn, G.map = 'BP_MapUnit_Player_Field_C', 1000")
tick(12)
assert G.shipMoves == 1, G.shipMoves
assert len(G.parks) == 4 and list(G.parks.values())[-1] == "12470 14980 65", "the save is parked at the start again"
assert any("away from the start, moved there: airship from Zoldaad" in line for line in L.eval("logged").values())
tick(12)
assert G.shipMoves == 1, "once: the player may fly it anywhere after"
# a seed that starts in the airship puts the game's condition back over ours
inbox("seed\tS69c:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot()
tick(4)
assert list(G.airshipSyncs.values())[-1] is False
print("airship as an item: ok")

# Round 72: the radar's 13 treasures. Its level is the Progressive Radars (item 27006) applied to
# this save. One turns the radar on (flag 702). A treasure's check is its found flag (704 to 716).
# Round 74: the radar works only while its step (progress 49) matches the band of the found count
# (progress 51): 20 or 30 up to 13, 40 up to 22, 50 up to 31. Round 75: the found count is held at
# the top of the level's band, the threshold of its last treasure, so each radar opens its whole
# tier at once. Each dig sets the count to its own number, and the next tick puts it back.
TIER_ONE_OPEN, TIER_TWO_OPEN, TIER_THREE_OPEN = 13, 22, 31
LID_HEARD = 10    # round 105: the radar's step after Lid's "We already found Mysidia..." line
AFTER_FIRST_DIG, AFTER_FIFTH_DIG, AFTER_LAST_DIG = 10, 14, 32
inbox("seed\tS72r:0:1\ncfg\topenworld\t1\ncfg\tradar\t1\n", "w")
L, G = boot5("SD_RADAR", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
L.execute("""G.radarFlags = {}
function G.GetFlag(i) return G.radarFlags[i] == true end
function G.SetFlag(i, on) G.radarFlags[i] = on; return "ok", "" end""")
G.chests = L.table()
G.story = 8000
tick(12)
assert G.radarPatches >= 1, "the dig rows give the pop-up's stand-in"
assert L.eval("G.radarFlags[702]") is None, "no radar yet"
assert L.eval("G.progress[49]") == LID_HEARD, "round 105: Lid's Mysidia line is skipped"
inbox("item\t0\titem\t27006\t1\tProgressive Radar\n")
tick(12)
assert L.eval("G.radarFlags[702]") is True and L.eval("G.progress[49]") == 20, "level 1: installed"
assert L.eval("G.progress[51]") == TIER_ONE_OPEN, "treasures 1 to 5 at once"
L.execute(f"G.progress[49] = 30; G.progress[51] = {AFTER_FIRST_DIG}")    # the game's first dig
tick(12)
assert L.eval("G.progress[49]") == 30, "the game's own step in the band is left alone"
assert L.eval("G.progress[51]") == TIER_ONE_OPEN, "a dig does not close the tier again"
L.execute(f"G.progress[51] = {AFTER_FIFTH_DIG}")
tick(12)
assert L.eval("G.progress[51]") == TIER_ONE_OPEN and L.eval("G.progress[49]") == 30, "level 1 stays in its band"
inbox("item\t1\titem\t27006\t1\tProgressive Radar\n")
tick(12)
assert L.eval("G.progress[51]") == TIER_TWO_OPEN and L.eval("G.progress[49]") == 40
L.execute("G.progress[49] = 41")    # the merchant's in-between step would turn the radar off
tick(12)
assert L.eval("G.progress[49]") == 40
inbox("item\t2\titem\t27006\t1\tProgressive Radar\n")
tick(12)
assert L.eval("G.progress[51]") == TIER_THREE_OPEN and L.eval("G.progress[49]") == 50
L.execute(f"G.progress[51] = {AFTER_LAST_DIG}")
tick(12)
assert L.eval("G.progress[51]") == TIER_THREE_OPEN, "treasure 13 first: the rest of tier 3 stays open"
L.execute("G.radarFlags[704] = true")
tick(12)
assert "check\tradar:1\n" in read("ap_out.txt") and "radar:2" not in read("ap_out.txt"), read("ap_out.txt")[-200:]

# Round 108 (a player): once every treasure of the level's tiers is dug, the count goes two past the
# band's top, out of every band and off the counts the game's own upgrades test (14 and 23), so the
# radar is quiet. The next radar opens its tier again.
TIER_ONE_QUIET, TIER_TWO_QUIET, TIER_THREE_QUIET = 15, 24, 33
UPGRADE_COUNTS = (14, 23)
inbox("seed\tS108r:0:1\ncfg\topenworld\t1\ncfg\tradar\t1\n", "w")
L, G = boot5("SD_RADAR_QUIET", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute("function G.HeldCount(id) return 1 end")
L.execute("""G.radarFlags = {}
function G.GetFlag(i) return G.radarFlags[i] == true end
function G.SetFlag(i, on) G.radarFlags[i] = on; return "ok", "" end""")
G.chests = L.table()
G.story = 8000
inbox("item\t0\titem\t27006\t1\tProgressive Radar\n")
tick(12)
L.execute("for f = 704, 707 do G.radarFlags[f] = true end")    # four of tier 1's five
tick(12)
assert L.eval("G.progress[51]") == TIER_ONE_OPEN, "one left: the radar still pings"
L.execute("G.radarFlags[708] = true")
tick(12)
assert L.eval("G.progress[51]") == TIER_ONE_QUIET, "tier 1 all dug: quiet"
inbox("item\t1\titem\t27006\t1\tProgressive Radar\n")
tick(12)
assert L.eval("G.progress[51]") == TIER_TWO_OPEN and L.eval("G.progress[49]") == 40, "the next radar opens tier 2"
L.execute("for f = 709, 712 do G.radarFlags[f] = true end")
tick(12)
assert L.eval("G.progress[51]") == TIER_TWO_QUIET
inbox("item\t2\titem\t27006\t1\tProgressive Radar\n")
tick(12)
assert L.eval("G.progress[51]") == TIER_THREE_OPEN and L.eval("G.progress[49]") == 50
L.execute("for f = 713, 716 do G.radarFlags[f] = true end")
tick(12)
assert L.eval("G.progress[51]") == TIER_THREE_QUIET
assert not set(UPGRADE_COUNTS) & {TIER_ONE_QUIET, TIER_TWO_QUIET, TIER_THREE_QUIET}
print("radar: ok")

# Round 105: Aileen's forge. Location n is the nth weapon forged, counted from the eight weapons
# in the bag. The forge's flag comes on before a forge's pop-up: the pop-up names the next
# location, and the flag goes off again. The game keeps one Adamantite at most here, so after a
# forge an empty bag gets one back while the Adamantite received outnumber the weapons forged.
FORGE_FLAG, ADAMANTITE = 1236, 20016
RAIN_WEAPON, LASSWELL_WEAPON = 10190, 10290
inbox("seed\tS105f:0:1\ncfg\topenworld\t1\ncfg\tforge\t1\n", "w")
L, G = boot5("SD_FORGE", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute(f"""G.held, G.forgeFlags, G.forgePatches = {{}}, {{}}, 0
G.FORGE = {{ flag = {FORGE_FLAG}, adamantite = {ADAMANTITE},
            weapons = {{ 10190, 10290, 10390, 10490, 10590, 10790, 10890, 10690 }} }}
function G.ForgePatch() G.forgePatches = G.forgePatches + 1; return 1 end
function G.HeldCount(id) return G.held[id] or 0 end
function G.GetFlag(i) return G.forgeFlags[i] == true end
function G.SetFlag(i, on) G.forgeFlags[i] = on; return "ok", "" end
function G.GrantItem(id, n)
  G.log[#G.log + 1] = "item" .. id .. "x" .. n
  G.held[id] = math.min((G.held[id] or 0) + n, 1)
  return "ok", ""
end""")
G.chests = L.table()
G.story = 8000
tick(12)
assert G.forgePatches >= 1, "the forge ends only with all eight weapons"
assert "forge:" not in read("ap_out.txt"), "no weapon yet"
inbox("item\t0\titem\t20016\t1\tAdamantite\nitem\t1\titem\t20016\t1\tAdamantite\n")
inbox(b64_scout("forge:1", "Hookshot", "Alice", 1, 0))
tick(12)
assert L.eval(f"G.held[{ADAMANTITE}]") == 1, "the second copy was lost"
grants = len([g for g in G.log.values() if g == f"item{ADAMANTITE}x1"])
G.popups, G.popupReady = L.table(), True
L.execute(f"G.forgeFlags[{FORGE_FLAG}] = true; G.held[{ADAMANTITE}] = 0; G.held[{RAIN_WEAPON}] = 1")
G.onField = False
tick(4)
assert "check\tforge:1\n" in read("ap_out.txt") and "forge:2" not in read("ap_out.txt"), read("ap_out.txt")[-200:]
assert list(G.popups.values()) == ["You found Alice's:\nHookshot"], list(G.popups.values())
assert L.eval(f"G.forgeFlags[{FORGE_FLAG}]") is False, "the flag goes off for the next forge"
G.onField = True
tick(4)
assert len([g for g in G.log.values() if g == f"item{ADAMANTITE}x1"]) == grants + 1, "the lost copy comes back"
assert L.eval(f"G.held[{ADAMANTITE}]") == 1
L.execute(f"G.forgeFlags[{FORGE_FLAG}] = true; G.held[{ADAMANTITE}] = 0; G.held[{LASSWELL_WEAPON}] = 1")
tick(4)
assert "check\tforge:2\n" in read("ap_out.txt")
before = len(G.log)
tick(8)
assert len(G.log) == before, "two received, two forged: nothing more to give"
print("forge: ok")

# Round 107 (the user): Grandport's vision Moogle shows only with flag 144, from a chapter 1 scene
# the open start skips: a seed's save gets the flag, once. With the key items in the pool, the
# Zoldaad squad leader's rows give the stand-in, and his trigger is turned off on map 3160 only.
# Round 112: flag 145 too, or every Moogle's first talk plays Grandport's scene. A save from
# v0.31.1 already holds 144 and gets 145 alone.
VISION_MOOGLE_FLAG, MOOGLE_SCENE_SEEN, ZOLDAAD_CASTLE = 144, 145, 3160
for keyitems in ("1", "0"):
    inbox(f"seed\tS107{keyitems}:0:1\ncfg\topenworld\t1\ncfg\tkeyitems\t{keyitems}\n", "w")
    L, G = boot5("SD_107_" + keyitems, "0", {})
    L.globals().G = G
    L.execute(SCALE_STUB)
    L.execute("""G.flags107, G.flagSets, G.rowPatches, G.triggerCalls = {}, 0, 0, 0
function G.GetFlag(i) return G.flags107[i] == true end
function G.SetFlag(i, on) G.flags107[i] = on; G.flagSets = G.flagSets + 1; return "ok", "" end
function G.ThroneKeyRowsPatch() G.rowPatches = G.rowPatches + 1; return 4 end
function G.ThroneKeyTriggerOff() G.triggerCalls = G.triggerCalls + 1; return 0 end
G.map = 2030""")
    G.chests = L.table()
    G.story = 8000
    tick(12)
    assert L.eval(f"G.flags107[{VISION_MOOGLE_FLAG}]") is True, "the Moogle shows"
    assert L.eval(f"G.flags107[{MOOGLE_SCENE_SEEN}]") is True, "no Grandport scene at the first Moogle"
    assert G.flagSets == 2, G.flagSets
    sets = G.flagSets
    tick(8)
    assert G.flagSets == sets, "set once"
    assert G.triggerCalls == 0, "not off Zoldaad Castle"
    G.map = ZOLDAAD_CASTLE
    tick(8)
    if keyitems == "1":
        assert G.rowPatches >= 1 and G.triggerCalls >= 1, (G.rowPatches, G.triggerCalls)
    else:
        assert G.rowPatches == 0 and G.triggerCalls == 0, "key items not in the pool: the game's own key stays"
inbox("seed\tS107v:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_107_v0311", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute(f"""G.flags107, G.flagSets = {{ [{VISION_MOOGLE_FLAG}] = true }}, 0
function G.GetFlag(i) return G.flags107[i] == true end
function G.SetFlag(i, on) G.flags107[i] = on; G.flagSets = G.flagSets + 1; return "ok", "" end
G.map = 2030""")
G.chests = L.table()
G.story = 8000
tick(12)
assert L.eval(f"G.flags107[{MOOGLE_SCENE_SEEN}]") is True and G.flagSets == 1, "a v0.31.1 save gets 145 alone"
print("throne key and vision moogle: ok")

# Round 108 (the key item audit): with the key items in the pool, the man by Sian's inn is rewritten
# on map 2170 only. With them not shuffled, the Dungeon Key is given in Zoldaad Dungeon while not
# held. Maps of locked continents are marked not visited on every pass.
SIAN, ZOLDAAD_DUNGEON, DUNGEON_KEY = 2170, 3150, 20019
for keyitems in ("1", "0"):
    inbox(f"seed\tS108{keyitems}:0:1\ncfg\topenworld\t1\ncfg\tkeyitems\t{keyitems}\n", "w")
    L, G = boot5("SD_108_" + keyitems, "0", {})
    L.globals().G = G
    L.execute(SCALE_STUB)
    L.execute(CAPTURE)
    L.execute("""G.manCalls, G.unvisits, G.held108, G.grants108 = 0, 0, {}, 0
function G.CabinKeyManOff() G.manCalls = G.manCalls + 1; return 1 end
function G.UnvisitLocked() G.unvisits = G.unvisits + 1; return G.unvisits == 1 and { 2030 } or {} end
function G.HeldCount(id) return G.held108[id] or 0 end
local grant = G.GrantItem
function G.GrantItem(id, n)
  if id ~= 20019 then return grant(id, n) end
  G.grants108 = G.grants108 + 1; G.held108[id] = (G.held108[id] or 0) + n; return "ok", ""
end
G.map = 2030""")
    G.chests = L.table()
    G.story = 8000
    tick(8)
    assert G.unvisits >= 1, "every pass"
    assert sum("2030 are on locked continents" in l for l in logs()) == 1, "logged once"
    assert G.manCalls == 0 and G.grants108 == 0, "not on their maps"
    G.map = SIAN
    tick(4)
    G.map = ZOLDAAD_DUNGEON
    tick(8)
    if keyitems == "1":
        assert G.manCalls >= 1, "the man stops giving the key"
        assert G.grants108 == 0, "the pool's key is the only one"
    else:
        assert G.manCalls == 0, "key items not in the pool: the man gives his key"
        assert G.grants108 == 1 and L.eval(f"G.held108[{DUNGEON_KEY}]") == 1, "given once, then held"
print("cabin key, dungeon key and locked maps: ok")

# Round 78: side quests. A quest's check is its counter at or past the value its reward row
# writes (Rear Support, Ahoy!: progress 28 at 40). The Mechabo counter (16) starts at 10 on an
# open world seed's save, with or without the quests, and is left alone once it moves.
ZILE_COUNTER, ZILE_REWARD = 28, 40
MECHABO_COUNTER, MECHABO_REQUEST, MECHABO_LATER = 16, 10, 30
inbox("seed\tS78q:0:1\ncfg\topenworld\t1\ncfg\tquests\t1\n", "w")
L, G = boot5("SD_QUESTS", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
G.chests = L.table()
G.story = 8000
tick(12)
assert G.questPatches and G.questPatches >= 1, "the reward rows lose the location's item"
assert L.eval(f"G.progress[{MECHABO_COUNTER}]") == MECHABO_REQUEST, "Verun's repair request"
L.execute(f"G.progress[{ZILE_COUNTER}] = {ZILE_REWARD - 10}")
tick(12)
assert "quest:13" not in read("ap_out.txt"), "a step before the reward is no check"
# Round 78: the reward scene can run past a minute before its pop-up comes (a character quest's
# stat bonus). The pop-up waits through the scene and gives up only after time on the field.
inbox(b64_scout("quest:13", "Hookshot", "Alice", 1, 0))
tick(2)
REWARD_SCENE_TICKS, FIELD_WAIT_TICKS = 200, 60          # 100 s of scene; BOSS_POPUP_TRIES
G.popupReady, G.onField, G.popups = False, False, L.table()
L.execute(f"G.progress[{ZILE_COUNTER}] = {ZILE_REWARD}; G.progress[{MECHABO_COUNTER}] = {MECHABO_LATER}")
tick(REWARD_SCENE_TICKS)
assert "check\tquest:13\n" in read("ap_out.txt") and "quest:34" not in read("ap_out.txt"), read("ap_out.txt")[-200:]
assert "quest2:13" not in read("ap_out.txt") and not G.questSecond, "a seed with no second rewards: no second check"
G.popupReady = True
tick(1)
assert list(G.popups.values()) == ["You found Alice's:\nHookshot"], list(G.popups.values())
G.onField = True
assert L.eval(f"G.progress[{MECHABO_COUNTER}]") == MECHABO_LATER, "the counter is set only at 0"
# Round 79: Token Legacy's row sets its counter only after its pop-ups. While the counter reads
# the value before, an item pop-up in an event on the reward map is the quest's; the check later
# leaves it alone. The same counter value elsewhere, or on the field, writes nothing.
TOKEN_COUNTER, TOKEN_BEFORE, TOKEN_REWARD = 7, 50, 60
ZOLDAAD_CASTLE_MAP, ELSEWHERE_MAP = 3160, 2102
inbox(b64_scout("quest:6", "Seraphim Bow", "Alice", 1, 0))
tick(2)
written = len(G.popups)
L.execute(f"G.progress[{TOKEN_COUNTER}] = {TOKEN_BEFORE}")
G.map, G.onField, G.popupReady = ELSEWHERE_MAP, False, True
tick(2)
assert len(G.popups) == written, "not on the reward map"
G.map, G.onField = ZOLDAAD_CASTLE_MAP, True
tick(2)
assert len(G.popups) == written, "on the field"
G.onField, G.popupReady = False, False
tick(4)
assert len(G.popups) == written, "no pop-up yet"
G.popupReady = True
tick(1)
assert len(G.popups) == written + 1 and G.popups[written + 1] == "You found Alice's:\nSeraphim Bow", list(G.popups.values())
assert "quest:6" not in read("ap_out.txt"), "the check waits for the counter"
L.execute(f"G.progress[{TOKEN_COUNTER}] = {TOKEN_REWARD}")
tick(4)
assert "check\tquest:6\n" in read("ap_out.txt"), read("ap_out.txt")[-200:]
assert len(G.popups) == written + 1, "the check writes no second pop-up"
G.onField = True
# Round 89: Token Legacy played again from an older save of the seed, its check sent already, gets
# its pop-up again; once for that load
L.execute("G.stamps['SD_QUESTS_OLDER'] = G.stamps[G.saveObj]")
load(G, "SD_QUESTS_OLDER", "0")
L.execute(f"G.progress[{TOKEN_COUNTER}] = {TOKEN_BEFORE}")
G.map, G.onField, G.popupReady = ZOLDAAD_CASTLE_MAP, False, True
tick(3)
assert len(G.popups) == written + 2 and G.popups[written + 2] == "You found Alice's:\nSeraphim Bow", list(G.popups.values())
L.execute(f"G.progress[{TOKEN_COUNTER}] = {TOKEN_REWARD}")
G.onField = True
tick(2)
# Round 89 (the user): an item line's flags and name, and a sent item's, colour its name in the feed
L.execute("G.feedReady = true; G.feed = {}; G.feedSpans = {}")
applied = [int(line.split("\t")[1]) for line in read("ap_out.txt").splitlines() if line.startswith("applied\t")]
inbox(f"item\t{max(applied, default=-1) + 1}\titem\t1\t1\tHookshot from Alice\t1\tHookshot\n", "a")
inbox("msg\tSent Ether to Bob\tEther\t2\n", "a")
tick(4)
assert L.eval("G.feedSpans['Received Hookshot from Alice']") == "Hookshot/1", list(G.feed.values())
assert L.eval("G.feedSpans['Sent Ether to Bob']") == "Ether/2", list(G.feed.values())
# Round 91 probes: ffrap_popup colors on traces the next coloured pop-up; ffrap_quest colors on
# hands the quest rewards' spans, by label, to the Quests screen each second
L.execute('commands["ffrap_popup"]("ffrap_popup", {"colors", "on"})')
assert L.eval("package.loaded.game.POPUP_COLORS.on") is True and L.eval("type(package.loaded.game.POPUP_COLORS.trace)") == "function"
L.execute('commands["ffrap_popup"]("ffrap_popup", {"colors", "off"})')
assert L.eval("package.loaded.game.POPUP_COLORS.trace") is None
# Round 88: Mog Tag's tiers run at either of two counter values, while flag 545 (the chase) is on;
# its Potion pop-up came before the check, so the early pop-up writes it
L.execute(CAPTURE)
L.execute("""
  G.QUESTS[#G.QUESTS + 1] = { key = "quest:34", counter = 44, value = 20, map = 2130, before = { 0, 10 },
                              flags = { 545 }, rows = { "SubEv_C05_MogChase_06_NPC01_01" } }
  G.flagsOn = {}
  local oldFlag = G.GetFlag
  function G.GetFlag(i) if G.flagsOn[i] ~= nil then return G.flagsOn[i] end return oldFlag(i) end
""")
MOG_COUNTER, MOG_FIRST_TIER_BEFORE, MOG_CHASE_FLAG, MYSIDIA_MAP = 44, 10, 545, 2130
inbox(b64_scout("quest:34", "Mirage Jacket", "Alice", 1, 0))
tick(2)
written = len(G.popups)
L.execute(f"G.progress[{MOG_COUNTER}] = {MOG_FIRST_TIER_BEFORE}")
G.map, G.onField, G.popupReady = MYSIDIA_MAP, False, True
tick(2)
assert len(G.popups) == written, "no chase on: another pop-up in Mysidia is not Mog Tag's"
L.execute(f"G.flagsOn[{MOG_CHASE_FLAG}] = true")
tick(2)
assert len(G.popups) == written + 1 and G.popups[written + 1] == "You found Alice's:\nMirage Jacket", list(G.popups.values())
G.onField = True
# Round 88 (the user): the Quests screen's Rewards name what each quest location holds
tick(70)
assert L.eval("G.prizes['quest:34']") == "Alice's Mirage Jacket" and L.eval("G.prizes['quest:6']") == "Alice's Seraphim Bow"
assert any("quest rewards show the location's item" in s for s in logs()), logs()
L.execute('commands["ffrap_quest"]("ffrap_quest", {"colors", "on"})')
tick(4)
assert L.eval("G.questSpans[\"Alice's Mirage Jacket\"].text") == "Mirage Jacket" and L.eval("G.questSpans[\"Alice's Mirage Jacket\"].flags") == 1
assert any("quest colours: coloured: " in s for s in logs()), logs()
L.execute('commands["ffrap_quest"]("ffrap_quest", {"colors", "off"})')
assert L.eval("next(G.questSpans)") is None, "off: every row taken out"
# Round 96: on by default and quiet. The first line coloured was logged above (with colors on);
# with them on again by default, no more are
L.execute("package.loaded.game.QUEST_COLORS.on, G.questDone = true, nil; logged = {}")
tick(4)
assert L.eval("G.questDone") is True and not any("quest colours: coloured: " in s for s in logs()), logs()
# and `instant on` registers the SetText hook while the screen is open
L.execute('commands["ffrap_quest"]("ffrap_quest", {"instant", "on"})')
tick(2)
assert any("quest colours: SetText hook registered" in s for s in logs()), logs()
L.execute('package.loaded.game.QUEST_COLORS.on = false')
# Round 88: Verun's counter, the delivery flag and Lid's Mechabo Tackle are logged when they change
L.execute("G.skills = { [404110] = true }")
tick(2)
assert any("mechabo: progress 16 at 30, flag 219 off, quest 17 not in the log, quest 26 not in the log, "
           "board quest 1001 not on the board, Lid has Mechabo Tackle" in s for s in logs()), logs()
L.execute('G.toOrder = { 1001 }')
tick(2)
assert any("mechabo: board quests 1001 ordered, so their kills count" in s for s in logs()), "round 95"
L.execute('G.requestStates = { [17] = "done", [26] = "open" }')
tick(2)
assert any("quest 17 done, quest 26 open" in s for s in logs()), "round 93: the quests' states, when they change"
n = len([s for s in logs() if s.startswith("mechabo: progress")])
tick(4)
assert len([s for s in logs() if s.startswith("mechabo: progress")]) == n, "logged once per change"

inbox("seed\tS78n:0:1\ncfg\topenworld\t1\ncfg\tquests\t0\n", "w")
L, G = boot5("SD_NOQUESTS", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
G.chests = L.table()
G.story = 8000
L.execute(f"G.progress[{ZILE_COUNTER}] = {ZILE_REWARD}")
tick(12)
assert G.questPatches is None and "quest:13" not in read("ap_out.txt"), "quests off: no patch, no check"
assert L.eval(f"G.progress[{MECHABO_COUNTER}]") == MECHABO_REQUEST, "the Mechabo start does not need the quests"

# Round 98 (the user): a quest's second reward (Rear Support, Ahoy!'s 500 gil) is a location of its
# own: the patch takes it out, the check sends both, the pop-up names both and the Quests screen too
inbox("seed\tS98q:0:1\ncfg\topenworld\t1\ncfg\tquests\t1\ncfg\tquest2\t1\n", "w")
L, G = boot5("SD_QUEST2", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
G.chests = L.table()
G.story = 8000
tick(12)
assert G.questSecond is True, "the patch takes the second rewards out too"
inbox(b64_scout("quest:13", "Hookshot", "Alice", 1, 0), "a")
inbox(b64_scout("quest2:13", "Potion", "Me", 0, 1), "a")
tick(2)
G.popupReady, G.onField, G.popups = True, False, L.table()
L.execute(f"G.progress[{ZILE_COUNTER}] = {ZILE_REWARD}")
tick(4)
out = read("ap_out.txt")
assert "check\tquest:13\n" in out and "check\tquest2:13\n" in out, out[-200:]
assert list(G.popups.values()) == ["You found:\nAlice's Hookshot\nPotion"], list(G.popups.values())
G.onField = True
tick(70)
assert L.eval("G.prizes['quest:13']") == "Alice's Hookshot" and L.eval("G.prizes['quest2:13']") == "Potion"
# Round 103 (the user): hide_quest_rewards shows ??? on the Quests screen, with no colour; the
# pop-up when the quest is done still names the item
HIDDEN = "???"
inbox("cfg\thidequests\t1\n", "a")
tick(70)
assert L.eval("G.prizes['quest:13']") == HIDDEN and L.eval("G.prizes['quest2:13']") == HIDDEN, L.eval("G.prizes['quest:13']")
assert L.eval("G.questSpans and next(G.questSpans)") in (None, False), "no colour for a hidden reward"
print("side quests: ok")

# IDEAS.md idea 37: the Oblivion Palace counter is held on a seed's save each tick, and its line
# is logged when it changes (game.PalaceSync, tested in test_game.py).
inbox("seed\tS80p:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_PALACE", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute(CAPTURE)
G.chests = L.table()
G.story = 1030
tick(12)
assert L.eval("G.palaceSyncs") == 0, "not before the open world start"
G.story = 8000
tick(12)
assert L.eval("G.palaceSyncs") >= 2, "every tick on a seed's save"
palace_logs = [s for s in L.eval("logged").values() if "palace:" in s]
assert len(palace_logs) == 1 and "progress 43 at 11" in palace_logs[0], palace_logs
print("palace safes: ok")

# Round 73: the Behemoth fight's assist hits deal 1 damage. The patch runs on a new save and again
# on each way into the Crystal Tower (map 3280), not on every tick there.
patches = G.behemothPatches
assert patches >= 1, "on the new save"
L.execute(CAPTURE)
G.map = 3280
tick(12)
assert G.behemothPatches == patches + 1, "on entering the tower"
tick(12)
assert G.behemothPatches == patches + 1, "not again while there"
G.map = 1000
tick(12)
G.map = 3280
tick(12)
assert G.behemothPatches == patches + 2, "on the next way in"
assert any("behemoth: 3 assist hits set to 1 damage" in s for s in L.eval("logged").values()), "logged"
print("behemoth: ok")

# Round 58: the tower's last climb stays sealed while the client's counts are short, and says so near it
inbox("seed\tS58:0:1\ncfg\topenworld\t1\ncfg\tfinalboss\t2\t6\t3\t12\n", "w")
L, G = boot5("SD_LOCK", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute(CAPTURE)
L.execute("function G.HeldCount(id) return 1 end")
L.execute("function G.PlayerPose() return { x = G.poseX or 0, y = -55300 } end")
G.chests = L.table()
G.story = 8000
G.map = 1000
L.execute("function G.CurrentMap() return G.map end")
tick(12)
assert G.sealed is None, "nothing outside the tower"
G.map = 3280
G.poseX = 0
tick(12)
assert G.sealed is True
assert not any("way to the top is sealed" in x for x in logs()), "not said far away"
G.poseX = 15000
tick(6)
said = [x for x in logs() if "way to the top is sealed" in x]
assert len(said) == 1 and "characters 2/6, visions 3/12" in said[0], said
tick(6)
assert len([x for x in logs() if "way to the top is sealed" in x]) == 1, "once per approach"
# Round 57: the trigger is loaded only near the climb; its absence is logged once per visit
L.execute("""function G.SealTowerTop(sealed) G.sealed = sealed
  if G.towerFar then return nil, "the last climb's trigger was not found" end return 0 end""")
for far in (True, False, True, False):
    G.towerFar = far
    tick(6)
assert len([x for x in logs() if "trigger was not found" in x]) == 1, logs()
assert len([x for x in logs() if "final boss lock: sealed" in x]) == 1, logs()
# Round 88: the Options rows are added only for the Archipelago page, not by the tick
G.menuRowsIn = False
tick(2)
assert not G.menuAdds and not any("rows added" in x for x in logs()), logs()
inbox("cfg\tfinalboss\t6\t6\t12\t12\n", "a")
tick(6)
assert G.sealed is False, "open once both counts are met"
print("final boss lock: ok")

# Round 58: the last battle is won when flag 40 goes off at story 8050; reported once as `won 9056`
L.execute("G.flag40 = true; local old = G.GetFlag; G.GetFlag = function(i) if i == 40 then return G.flag40 end return old and old(i) end")
G.story = 8050
tick(4)
assert "won\t9056" not in read("ap_out.txt"), "flag 40 is on until the win"
G.flag40 = False
tick(4)
assert read("ap_out.txt").count("won\t9056") == 1, read("ap_out.txt")
tick(4)
assert read("ap_out.txt").count("won\t9056") == 1, "once"
print("last battle: ok")

# Round 49: ffrap_bossfight arms, logs a win once, can be turned off, and arms again on a new save
inbox("seed\tS50:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_BOSS", "0", {})
L.globals().G = G
L.execute("""
G.bossArm, G.bossOff, G.bossWon = {}, 0, false
G.BOSS_TEST_FLAG, G.BOSS_TEST_SWORD = 1440, 10198
G.held, G.given = 0, {}
function G.HeldCount(id) return G.held end
function G.GrantItem(id, n) G.given[#G.given + 1] = id; G.held = G.held + n; return "ok", "held 0 -> 1" end
function G.BossTestArm(id, say) G.bossArm[#G.bossArm + 1] = id; return id ~= 1, "detail" end
function G.BossTestOff(say) G.bossOff = G.bossOff + 1; return 3 end
local old = G.GetFlag
function G.GetFlag(i) if i == 1440 then return G.bossWon end return old and old(i) end
local oldSet = G.SetFlag
function G.SetFlag(i, on) if i == 1440 then G.bossWon = on; return "ok", "" end return oldSet(i, on) end
logged = {}
print = function(s) logged[#logged + 1] = tostring(s) end
""")
wins = lambda: [x for x in L.eval("logged").values() if "WIN seen" in x]
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1000
G.chests = L.table()
tick(12)
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"sword"})')
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"sword"})')
assert list(G.given.values()) == [10198], "the Ancient Greatsword, given once"
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"9013"})')
assert list(G.bossArm.values()) == [9013], list(G.bossArm.values())
tick(3)
assert wins() == [], "no win yet"
G.bossWon = True
tick(3)
assert len(wins()) == 1 and G.bossWon is False, wins()
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"off"})')
assert G.bossOff == 1
G.bossWon = True
tick(3)
assert len(wins()) == 1, "off stops the watch"
G.bossWon = False
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"1"})')
assert list(G.bossArm.values()) == [9013, 1], "a failed arm"
G.bossWon = True
tick(3)
assert len(wins()) == 1, "a failed arm does not watch"
print("boss fight test: ok")

# Round 49: ffrap_bossfight watch hooks each function once, logs a call with its plain arguments,
# then holds back repeats, and stops logging when turned off
L.execute("""
function G.FunctionPaths(c)
  if c == "CPP_MapManager" then return { "/Script/mucha.CPP_MapManager:Encount", "/Script/mucha.CPP_MapManager:Warp" }, true end
  return nil
end
""")
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"watch"})')
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"watch"})')
logs = lambda: list(L.eval("logged").values())
assert sum("hooking /Script/mucha.CPP_MapManager:Warp" in x for x in logs()) == 1, "each function hooked once"
assert any("no class CPP_TalkEventManager" in x for x in logs())
L.execute('hooks["/Script/mucha.CPP_MapManager:Warp"](nil, { get = function() return 9013 end }, { get = function() return { ToString = function() return "Siren" end } end })')
L.execute('hooks["/Script/mucha.CPP_MapManager:Warp"](nil)')
warp = [x for x in logs() if "watch: CPP_MapManager:Warp (" in x]
assert len(warp) == 1 and warp[0].rstrip().endswith("watch: CPP_MapManager:Warp (9013, Siren) call 1"), warp
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"watch", "off"})')
L.execute("os.time = function() return 10^9 end")
L.execute('hooks["/Script/mucha.CPP_MapManager:Warp"](nil)')
assert len([x for x in logs() if "watch: CPP_MapManager:Warp (" in x]) == 1, "off stops the logging"
print("watch probe: ok")

# Round 49: items from Archipelago are granted (an old seed can still send an artifact, a plain item now)
inbox("seed\tS51:0:1\nitem\t0\titem\t30001\t1\tExodus\nitem\t1\titem\t1\t1\tPotion\n", "w")
L, G = boot5("SD_ART", "0", {})
G.story = 1000
G.chests = L.table()
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
tick(12)
assert "item30001x1" in list(G.log.values()) and "item1x1" in list(G.log.values()), list(G.log.values())
print("item grant: ok")

# Round 50: ffrap_set changes the settings, keeps them in settings.txt (only what was set), and
# they reach the game; scaling off keeps the seed from scaling enemies
for name in ("settings.txt",):
    try:
        os.remove(path(name))
    except FileNotFoundError:
        pass
inbox("seed\tS52:0:1\ncfg\topenworld\t1\n", "w")
L, G = boot5("SD_SET", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1000
G.chests = L.table()
tick(12)
assert list(G.rates.values()) == [1, 1, 1] and list(G.encounterTables.values()) == [True, 1], "the defaults"
# Round 60: the fast tick writes the rates back when something else has changed them
L.execute(CAPTURE)
L.execute("""G.rateCalls = 0
local plain = G.ApplyRates
function G.ApplyRates(e, g, m) G.rateCalls = G.rateCalls + 1; plain(e, g, m); return G.foreignRates and 3 or 0 end""")
L.execute("fastFn()")
assert G.rateCalls == 1 and list(G.rates.values()) == [1, 1, 1]
G.foreignRates = True
L.execute("fastFn(); fastFn()")
G.foreignRates = False
assert len([x for x in logs() if "written back" in x]) == 1, "logged once"
set_ = lambda *a: L.execute('commands["ffrap_set"]("ffrap_set", {' + ", ".join('"%s"' % x for x in a) + '})')
set_("exp", "2")
set_("encounters", "off")
set_("encounterrate", "9")
set_("scaling", "off")
set_("gil", "lots")
tick(10)
assert list(G.rates.values()) == [2, 1, 1] and list(G.encounterTables.values()) == [False, 5], "held to the range"
assert G.playerEncounters is False
saved = read("settings.txt")
assert "exp 2" in saved and "encounters off" in saved and "encounterrate 5" in saved and "gil" not in saved, saved
G.story = 8000
tick(20)
assert list(G.scaleCalls.values()) == [], "scaling off: the seed does not scale"
# Round 84 (the user): a save not linked to the seed plays as the game made it (round 57 had the
# settings apply to it), and the linked save gets them back
# Round 85: there the continent locks come off once (the boxes, the crossings and the ferry), and
# an ffrap_scale from the linked save goes off too
L.execute('commands["ffrap_scale"]("ffrap_scale", {"1"})')
scaled = len(G.scaleCalls)
L.execute("G.lockCleared = nil; G.ferryAllOpen = 0")
G.slotOf = L.table_from({"900": 5})
load(G, "SD_SET_OTHER", "900")
tick(10)
assert list(G.rates.values()) == [1, 1, 1] and list(G.encounterTables.values()) == [True, 1], "the game's values"
assert G.lockCleared is True and G.ferryAllOpen == 1, "the locks off, once"
assert list(G.scaleCalls.values())[-1].startswith("off "), list(G.scaleCalls.values())
assert len(G.scaleCalls) == scaled + 1, "turned off once"
load(G, "SD_SET", "0")
tick(10)
assert list(G.rates.values()) == [2, 1, 1] and list(G.encounterTables.values()) == [False, 5], "the player's values"
assert G.ferryAllOpen == 1, "the linked save keeps its locks"
L2, G2 = boot5("SD_SET2", "0", {})
L2.execute("tickFn = tickFn")
assert "exp 2" in read("settings.txt"), "kept for the next run"
set_("reset")
assert read("settings.txt").strip() == ""
print("settings: ok")

# Round 50: a value set in the Options screen wins over ffrap_set, and is kept in settings.txt
L.execute('commands["ffrap_set"]("ffrap_set", {"exp", "4"})')
G.menuValues = L.table_from({"exp": 2, "encounters": False})
tick(10)
assert list(G.rates.values())[0] == 2 and list(G.encounterTables.values())[0] is False, "the menu's values"
assert "exp 2" in read("settings.txt") and "encounters off" in read("settings.txt")
print("menu settings: ok")

# Round 88: the Options rows are added when the Archipelago page is written, seeded with the
# current settings; the tick adds none
assert not G.menuAdds, G.menuAdds
print("menu rows: ok")

# Round 59: with the seed's cfg, the boss win rows are patched once per save, a boss reports by its
# win flag, a Crystal Fragment is applied as nothing, and the tower counts fragments
MARAUDER, LIQUID_THUNDER = 9079, 9083
inbox("seed\tS59:0:1\ncfg\topenworld\t1\ncfg\tbosses\t1\ncfg\tgifts\t1\ncfg\tfinalboss\t6\t6\t12\t12\t1\t2\n"
      "item\t0\ttoken\t0\t1\tCrystal Fragment (1/2)\n" + b64_scout(f"boss:{MARAUDER}", "Hookshot", "Alice", 1, 0)
      + b64_scout("gift:1400", "Bow", "Bob", 0, 0), "w")
L, G = boot5("SD_BOSS", "0", {})
L.globals().G = G
L.execute(SCALE_STUB)
L.execute(CAPTURE)
L.execute("function G.HeldCount(id) return 1 end")
L.execute("function G.PlayerPose() return { x = 15000, y = -55300 } end")
L.execute("function G.CurrentMap() return G.map end")
L.execute("G.wonFlags = {}; local old = G.GetFlag; G.GetFlag = function(i) if G.wonFlags[i] then return true end return old and old(i) end")
G.chests = L.table()
G.story = 8000
G.map = 1000
tick(12)
assert G.bossPatches == 1, G.bossPatches
assert "check\tboss:" not in read("ap_out.txt"), "no win yet"
assert "applied\t0" in read("ap_out.txt"), "a fragment is applied, though it is nothing in the game"
L.execute("G.wonFlags[146] = true")
tick(4)
# Round 97 (the user): with the gifts' cfg line, the gift rows are patched once per save, a gift
# reports by its flag, and its pop-up waits for the gift's; the Magi-tenna's only with the radar
assert G.giftPatches == 1 and not G.giftRadar, (G.giftPatches, G.giftRadar)
assert any("gifts: 9 NPC gift rows give the stand-in" in x for x in logs()), logs()
L.execute("G.wonFlags[1400] = true; G.wonFlags[1405] = true")
tick(4)
assert "check\tgift:1400\n" in read("ap_out.txt") and "gift:1405" not in read("ap_out.txt"), read("ap_out.txt")[-300:]
assert read("ap_out.txt").count(f"check\tboss:{MARAUDER}\n") == 1, read("ap_out.txt")
assert read("ap_out.txt").count(f"check\tfragment:{MARAUDER}\n") == 1, "round 97: the boss's fragment with it"
assert f"check\tboss:{LIQUID_THUNDER}" not in read("ap_out.txt")
# Round 60: the win's pop-up says what the boss held; a boss with no scout asks for none (then the gift's)
assert list(G.popups.values()) == ["You found Alice's:\nHookshot", "You found Bob's:\nBow"], list(G.popups.values())
L.execute("G.wonFlags[215] = true; G.popupOpen = true; fastFn()")
assert f"check\tboss:{LIQUID_THUNDER}\n" in read("ap_out.txt"), "the fast check reports a boss as its pop-up comes up"
assert len(list(G.popups.values())) == 2, "no more: Liquid Thunder has no scout"
tick(4)
assert read("ap_out.txt").count(f"check\tboss:{MARAUDER}\n") == 1, "reported once"
assert read("ap_out.txt").count(f"check\tfragment:{MARAUDER}\n") == 1, "its fragment once too"
assert f"check\tfragment:{LIQUID_THUNDER}\n" in read("ap_out.txt")
# Round 98 (the user): a gift's check came after its pop-up had closed. In an event on its map, a
# pop-up is the gift of the nearest NPC whose check is not sent; the check writes no second one
SIAN, NEAR_THE_CAT, FAR_FROM_BOTH = 2170, "{ x = 1200, y = 600 }", "{ x = 9000, y = 9000 }"
inbox(b64_scout("gift:1401", "Ether", "Bob", 0, 0) + b64_scout("gift:1413", "Bell", "Bob", 1, 0), "a")
tick(2)
written = len(G.popups)
L.execute("function G.OnField() return G.onField end")
L.execute(f"function G.PlayerPose() return {FAR_FROM_BOTH} end")
G.map, G.onField, G.popupReady = SIAN, False, True
tick(3)
assert len(G.popups) == written, "no gift NPC near: another pop-up on the map"
L.execute(f"function G.PlayerPose() return {NEAR_THE_CAT} end")
tick(3)
assert len(G.popups) == written + 1 and G.popups[written + 1] == "You found Bob's:\nBell", list(G.popups.values())
assert any("chest pop-up for gift:1413 before its check" in x for x in logs()), logs()
tick(3)
assert len(G.popups) == written + 1, "once"
L.execute("G.wonFlags[1413] = true")
tick(4)
assert "check\tgift:1413\n" in read("ap_out.txt") and len(G.popups) == written + 1, "the check writes no second pop-up"
G.onField = True
L.execute("function G.PlayerPose() return { x = 15000, y = -55300 } end")
G.map = 3280
tick(12)
assert G.sealed is True, "one fragment of two keeps the tower sealed"
said = [x for x in logs() if "way to the top is sealed" in x]
assert len(said) == 1 and "Crystal Fragments 1/2" in said[0], said
inbox("cfg\tfinalboss\t6\t6\t12\t12\t2\t2\n", "a")
tick(6)
assert G.sealed is False, "open with both fragments"
G.map = 3000
tick(12)
assert any("story boss: group 9004: 2 triggers" in x for x in logs()), logs()
# Round 62: the boss's fight waits for the field to be up a while, so coming back from the
# fight does not start it again before its win row runs
assert G.storyBossReady is True
G.onField = False
tick(2)
assert G.storyBossReady is False, "off as soon as the field goes (a battle, a scene, a menu)"
G.onField = True
tick(2)
assert G.storyBossReady is False, "not yet: the field has been back for one check only"
tick(2)
assert G.storyBossReady is True
L.execute('commands["ffrap_bossfight"]("ffrap_bossfight", {"trigger"})')
assert any("boss test: trigger: group 9004: 2 triggers" in x for x in logs()), logs()
G.map = 1000
tick(2)
assert G.storyBossReady is False, "off away from a story boss map"
print("bosses: ok")

# Round 62: items received in a battle came out of it at x 0, so items go in only on the field
RUBY_FRAGMENT = 10513
L.execute("G.bagAdds = {}; function G.GrantItem(id, n) G.bagAdds[#G.bagAdds + 1] = id; return 'ok', 'held 0 -> 1' end")
G.onField = False
inbox(f"item\t1\titem\t{RUBY_FRAGMENT}\t1\tRuby Fragment\n", "a")
tick(4)
assert len(G.bagAdds) == 0, "nothing goes in during a battle, a scene or a menu"
G.onField = True
tick(2)
assert list(G.bagAdds.values()) == [RUBY_FRAGMENT], list(G.bagAdds.values())
assert any("Received Ruby Fragment" in x for x in logs()), logs()
print("items wait for the field: ok")

# Rounds 82 and 83: the Archipelago page is on by default. The entry is kept in the menu every
# tick; its steps are logged until it is first in the menu, and a reason it cannot be yet is
# logged once. `off` stops it for the run and `on` brings it back.
L, G = boot5("SD_APMENU", "0", {})
G.ready = True
L.execute('''
  local G = package.loaded.game
  G.APMENU = { calls = {}, why = nil, done = nil }
  function G.APMENU.Ensure(say)
    G.APMENU.calls[#G.APMENU.calls + 1] = say and "told" or "quiet"
    if G.APMENU.why then return nil, G.APMENU.why end
    return G.APMENU.done
  end
  function G.APMENU.Page(title, makeBody) return nil, "not open" end
  function G.APMENU.Unstick() end
  function G.APMENU.Unlist() G.APMENU.unlists = (G.APMENU.unlists or 0) + 1; return G.APMENU.unlists == 1 end
''')
apcalls = lambda: list(L.eval("package.loaded.game.APMENU.calls").values())
tick = lambda n: [L.execute("tickFn()") for _ in range(n)]
L.execute("logged = {}; print = function(s) logged[#logged + 1] = tostring(s) end")
logged = lambda: list(L.eval("logged").values())
L.execute('package.loaded.game.APMENU.why = "no DA_MainMenuRoot loaded"')
tick(3)
assert apcalls() == ["told"] * 3, "on with no command, and its steps are told"
assert sum("apmenu: not yet: no DA_MainMenuRoot loaded" in s for s in logged()) == 1, "logged once"
L.execute('package.loaded.game.APMENU.why = nil; package.loaded.game.APMENU.done = "scene list; data added, enable added"')
tick(1)
assert any("apmenu: scene list; data added, enable added" in s for s in logged())
L.execute('package.loaded.game.APMENU.done = "row added"')      # the game loads its table again
tick(2)
assert apcalls()[-2:] == ["quiet", "quiet"] and not any("apmenu: row added" in s for s in logged()), \
    "once in the menu, putting it back is quiet"
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"off"})')
n = len(apcalls())
tick(3)
assert len(apcalls()) == n, "off: no more passes"
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"on"})')
assert len(apcalls()) == n + 1, "on: at once"
print("main menu entry: ok")

# The page's text: the goal and checks from the cfg lines, the tower lock, the continents and the
# seed's start. It is made only when the page asks for it (while the page is open).
L.execute('''
  local G = package.loaded.game
  G.APMENU.done = nil
  G.CONTINENTS = { { name = "grandshelt" }, { name = "lanzelt" }, { name = "kolobos" } }
  G.PALACE = { counter = 43, met = 10, item = 25004, map = 2031, steps = { 3, 6, 9, 12 } }
  G.openContinents = { lanzelt = true }
  function G.HeldCount(id) return id == 25004 and 13 or 0 end
  function G.APMENU.Page(title, makeBody) G.APMENU.paged = { title, makeBody() }; return "written" end
  function G.APMENU.Unstick()
    G.APMENU.unsticks = (G.APMENU.unsticks or 0) + 1
    if G.APMENU.unsticks == 2 then return "finished a stale close; x" end
  end
''')
L.execute("logged = {}")
inbox("seed\tS82:0:1\ncfg\topenworld\t1\ncfg\tshinies\t1\ncfg\tquests\t1\ncfg\tbosses\t0\ncfg\tairship\t0\ncfg\tcontinent\tlanzelt\n"
      "cfg\tfinalboss\t3\t4\t1\t2\t2\t5\ncfg\tgoal\tfinal_boss\t0\t99\ncfg\tchecks\t12\t480\n", "w")
tick(2)
title, body = list(L.eval("package.loaded.game.APMENU.paged").values())
assert title == "Archipelago"
assert sum("apmenu: page shown" in s for s in logged()) == 1, "logged the first time only"
assert any("apmenu: finished a stale close" in s for s in logged()), "the fallback runs each tick"
assert body.split("\n") == [
    "Goal: win the last battle at the top of the Crystal Tower",
    "Tower: party members 3/4, Visions 1/2, Crystal Fragments 2/5",
    "Checks: 12 of 480",
    "Items received: 0",
    "Tablet Shards: 13 collected",
    "Oblivion Palace Chests: 4 ready to open",
    "",
    "Continents open: Lanzelt",
    "Continents locked: Grandshelt, Kolobos",
    "Locations: chests, shinies, side quests",
    "Start: on foot on Lanzelt",
], body
inbox("cfg\tgoal\ttablet_shards\t7\t50\n")
tick(2)
body = list(L.eval("package.loaded.game.APMENU.paged").values())[1]
assert body.startswith("Goal: receive 50 Tablet Shards (7 so far)\n"), body
# Round 83: `state` logs the page's screens, `close` is a way out of one that will not close, and
# `tree` writes the open page's widgets to ffrap_apmenu.txt
L.execute('''
  local G = package.loaded.game
  function G.APMENU.State() return { "WBP_TutorialLayout_C_1  activated true", "main menu scene stack: x" } end
  function G.APMENU.Close() G.APMENU.closed = true; return "close asked; IsOpeningProcess false" end
  function G.APMENU.Tree() return { "host x", "  Overlay Overlay_0 (visibility 4)" } end
''')
L.execute("logged = {}")
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"state"})')
assert any("apmenu: WBP_TutorialLayout_C_1  activated true" in s for s in logged())
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"close"})')
assert L.eval("package.loaded.game.APMENU.closed") is True
assert any("apmenu: close asked; IsOpeningProcess false" in s for s in logged())
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"tree"})')
assert read("ffrap_apmenu.txt") == "host x\n  Overlay Overlay_0 (visibility 4)\n"
# Round 85 probe: `options` and `text` switch the entry's screen, `tabs` passes its mode on
L.execute("""
  local G = package.loaded.game
  function G.APMENU.Screen(kind) G.APMENU.screenAsked = kind; return { "row: class written", "subsystem: class written" } end
  function G.APMENU.Tabs(mode) G.APMENU.tabsAsked = mode; return { "tab NewRow: Gameplay" } end
""")
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"options"})')
assert L.eval("package.loaded.game.APMENU.screenAsked") == "options"
assert any("apmenu: row: class written" in s for s in logged())
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"tabs", "only"})')
assert L.eval("package.loaded.game.APMENU.tabsAsked") == "only"
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"tabs"})')
assert L.eval("package.loaded.game.APMENU.tabsAsked") == "list", "tabs alone lists them"
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"text"})')
assert L.eval("package.loaded.game.APMENU.screenAsked") == "text"
# Round 86 probe: `mode ap` hands the page's lines to A.Mode and logs the menu's SetScene calls;
# `mode game` stops the logging
L.execute("""
  local G = package.loaded.game
  function G.APMENU.Mode(kind, lines) G.APMENU.modeAsked = { kind, #lines }; return { "mode " .. kind .. ": done" } end
""")
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"mode", "ap"})')
assert list(L.eval("package.loaded.game.APMENU.modeAsked").values())[0] == "ap"
assert list(L.eval("package.loaded.game.APMENU.modeAsked").values())[1] > 0, "the page's lines"
set_scene = L.eval('hooks["/Script/mucha.CPP_MainMenuSubsystem:SetScene"]')
L.execute("logged = {}")
set_scene(None, L.eval("{ get = function() return { TagName = { ToString = function() return 'UI.MainMenu.Scene.FFRAP' end } } end }"))
assert any("apmenu: SetScene UI.MainMenu.Scene.FFRAP" in s for s in logged()), logged()
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"mode", "game"})')
L.execute("logged = {}")
set_scene(None, L.eval("{ get = function() return { TagName = { ToString = function() return 'UI.MainMenu.Scene.System' end } } end }"))
assert not any("SetScene" in s for s in logged()), "not logged after mode game"
# Round 87: `split off` gives the page one tab, and puts an open page's tables back first
L.execute("package.loaded.game.APMENU.modeSaved = {}")
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"split", "off"})')
assert L.eval("package.loaded.game.APMENU.split") is False
assert list(L.eval("package.loaded.game.APMENU.modeAsked").values())[0] == "game"
L.execute("package.loaded.game.APMENU.modeSaved = nil")
L.execute('commands["ffrap_apmenu"]("ffrap_apmenu", {"split", "on"})')
assert L.eval("package.loaded.game.APMENU.split") is True
# Round 87: picking Archipelago makes the tables our page before its screen opens; they go back
# once the menu has left our scene, at once for another scene, and after 3 s if ours never showed
L.execute("""
  local G = package.loaded.game
  G.APMENU.screen, G.APMENU.top, G.APMENU.modes, G.APMENU.TAG = "options", nil, {}, "UI.MainMenu.Scene.FFRAP"
  function G.APMENU.SceneTop() return G.APMENU.top end
  G.APMENU.written = true
  function G.APMENU.Written() return G.APMENU.written end
  G.menuRowsIn, G.menuAdds = false, 0
  function G.APMENU.Mode(kind, lines)
    G.APMENU.modes[#G.APMENU.modes + 1] = kind
    G.APMENU.modeSaved = kind == "ap" and #lines > 0 or nil
    return { "mode " .. kind .. ": done" }
  end
""")
scene = lambda tag: set_scene(None, L.eval("{ get = function() return { TagName = { ToString = function() return '"
                                           + tag + "' end } } end }"))
modes = lambda: list(L.eval("package.loaded.game.APMENU.modes").values())
OURS, ROOT = "UI.MainMenu.Scene.FFRAP", "UI.MainMenu.Scene.Root"
scene(OURS)
assert modes() == ["ap"], "our page at the click"
assert L.eval("package.loaded.game.menuAdds") == 1, "round 88: our setting rows added for the page"
assert L.eval("package.loaded.game.menuSeed.exp") is not None, "seeded with the settings"
L.execute(f"package.loaded.game.APMENU.top = '{OURS}'")
tick(4)
assert modes() == ["ap"], "kept while the menu is on our scene"
# Round 88: the game loaded the tables again with the page open; written again, logged once
L.execute("logged = {}; package.loaded.game.APMENU.written = false")
tick(2)
assert modes() == ["ap", "ap", "ap"], modes()
assert len([s for s in logged() if "loaded again with the page open" in s]) == 1, logged()
L.execute("package.loaded.game.APMENU.written = true; package.loaded.game.APMENU.modes = { 'ap' }")
L.execute(f"package.loaded.game.APMENU.top = '{ROOT}'")
tick(1)
assert modes() == ["ap", "game"], "back once the menu leaves it"
scene(OURS)
scene("UI.MainMenu.Scene.System")
assert modes()[-2:] == ["ap", "game"], "another scene: back at once"
scene(OURS)
L.execute("package.loaded.game.APMENU.top = nil")
tick(4)
assert modes()[-1] == "ap", "waits for the menu to show our scene"
tick(4)
assert modes()[-1] == "game", "and gives up after 3 s"
assert any("never showed our scene" in s for s in logged()), "said why"
L.execute("package.loaded.game.APMENU.screen = 'text'")
n = len(modes())
scene(OURS)
assert len(modes()) == n, "the text page needs no switch"
# Round 85: shards turned in count once the palace has been read; and the shards the seed has
# sent, when they are more (two Tablet Shards received here, with the bag emptied by a turn-in)
L.execute("package.loaded.game.PALACE.turned = 9")
tick(2)
body = list(L.eval("package.loaded.game.APMENU.paged").values())[1].split("\n")
assert "Tablet Shards: 22 collected" in body, body
inbox("item\t0\titem\t25004\t1\tTablet Shard\nitem\t1\titem\t25004\t1\tTablet Shard\n")
L.execute("package.loaded.game.PALACE.turned = nil; function package.loaded.game.HeldCount() return 0 end")
tick(4)
body = list(L.eval("package.loaded.game.APMENU.paged").values())[1].split("\n")
assert "Tablet Shards: 2 collected" in body and "Oblivion Palace Chests: 0 ready to open" in body, body
# Round 84 (the user): a save not linked to the seed takes the entry out of the menu, once, and
# the linked save puts it back
L.execute("logged = {}")
G.slotOf = L.table_from({"900": 5})
load(G, "SD_APMENU_OTHER", "900")
n = len(apcalls())
tick(3)
assert L.eval("package.loaded.game.APMENU.unlists") >= 3 and len(apcalls()) == n, "out of the menu, not put back"
assert sum("apmenu: taken out of the menu" in s for s in logged()) == 1, "logged once"
load(G, "SD_APMENU", "0")
tick(1)
assert len(apcalls()) > n, "back in the menu"
print("archipelago page lines: ok")

# Round 74: the build, a hash of the mod's scripts, tells test installs apart while the version
# stays the same until a release. It is logged on load, and a CRLF copy gives the same build. The
# Python copy of the hash is tools/package_release.py's, which names a release's mod build.
sys.path.insert(0, str(paths.REPO / "tools"))
from package_release import mod_build  # noqa: E402

L, G = boot(CAPTURE)
build = mod_build(Path(WORK))
assert any(f"version {VERSION} (build {build})" in x for x in list(L.eval("logged").values())), "logged on load"
crlf = tempfile.mkdtemp(prefix="ffrap_crlf_")
os.makedirs(os.path.join(crlf, "Scripts"))
for name in ("main.lua", "game.lua", "bridge.lua", "field_items.lua", "quests.lua", "gifts.lua"):
    text = open(os.path.join(WORK, "Scripts", name), "rb").read().replace(b"\r\n", b"\n")
    open(os.path.join(crlf, "Scripts", name), "wb").write(text.replace(b"\n", b"\r\n"))
B = runtime()
B.execute("bridge = require('bridge')")
assert B.eval(f"bridge.build('{crlf.replace(os.sep, '/')}/')") == build, "a CRLF copy"
print("build:", build, "ok")

# Round 116: a stutter like a heartbeat on slower PCs. A loop run over 25 ms is logged with its
# slow steps (at most once per 10 s), and ffrap_perf logs each loop, step and object search.
SLOW_CHEST_SCAN_MS = 40
L, G = boot(CAPTURE + """
fakeClock = 0
os.clock = function() return fakeClock end
function FindAllOf(c) fakeClock = fakeClock + 0.003; return {} end
""")
G.ready = True
G.LiveChests = L.eval(f"function() fakeClock = fakeClock + {SLOW_CHEST_SCAN_MS / 1000}; return {{}} end")
for _ in range(12):
    L.execute("tickFn()")
L.execute('FindAllOf("CPP_MapGimmick_FieldItem")')
slow = [m for m in L.eval("logged").values() if m.startswith("[FFRAP] perf: a tick took")]
assert len(slow) == 1 and f"loot {SLOW_CHEST_SCAN_MS}" in slow[0], slow
L.execute('commands["ffrap_perf"]("ffrap_perf", {})')
lines = [m for m in L.eval("logged").values() if m.startswith("[FFRAP] perf: ")]
assert any(m.startswith("[FFRAP] perf: tick 12 runs") for m in lines), lines
assert any("searches FindAllOf CPP_MapGimmick_FieldItem 1x 3 ms" in m for m in lines), lines
print("timings: ok")
