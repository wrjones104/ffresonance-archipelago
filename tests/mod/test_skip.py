"""G.SkipPrologue and G.SaveAndReload against a fake new-game save (the snap_new values)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

import sys

from lupa import lua54

SCRIPTS = str(paths.SCRIPTS).replace("\\", "/")
L = lua54.LuaRuntime(unpack_returned_tuples=True)
L.execute(f'package.path = "{SCRIPTS}/?.lua;" .. package.path')
L.execute(r'''
-- A UE4SS-like TArray: 1-based, # works, reading one past the end grows it by a zeroed element.
function arr(t, zero)
  local a = { items = t, zero = zero == nil and 0 or zero }
  return setmetatable(a, {
    __len = function(self) return #rawget(self, "items") end,
    __index = function(self, k)
      local items = rawget(self, "items")
      if type(k) == "number" then
        if k == #items + 1 then items[k] = rawget(self, "zero") end
        return items[k]
      end
      if k == "Empty" then return function(me) local it = rawget(me, "items") for i = #it, 1, -1 do it[i] = nil end end end
    end,
    __newindex = function(self, k, v) rawget(self, "items")[k] = v end,
  })
end
local function obj(t) t.IsValid = function() return true end
  t.HasAnyInternalFlags = function() return false end; t.HasAnyFlags = function() return false end; return t end

function FName(t) return { s = t, ToString = function(self) return self.s end } end
-- A TMap of chat rows, keyed by name; Add makes an empty row, as the engine zeroes one.
function chatMap(rows)
  local m = { rows = rows }
  function m:ForEach(fn) for id, row in pairs(self.rows) do
    fn({ get = function() return FName(id) end }, { get = function() return row end }) end end
  function m:Add(k, v) self.rows[k:ToString()] = { IsReleased = false, IsAlreadyPlayed = false } end
  return m
end
local flags = {} for i = 1, 1300 do flags[i] = false end
flags[2], flags[9] = true, true                       -- flags 1 and 8: on if the skip runs at 1005
local zeros = {} for i = 1, 20 do zeros[i] = 0 end
sd = obj({
  Progress = { Progress = arr({ 1000, 0 }), eventFlag = arr(flags, false) },
  Party = { partyList = arr({ 1006 }) },
  unitParameterList = arr({
    { UnitId = 1001, JoinStatus = 1, baseParameterList = arr(zeros) },
    { UnitId = 1002, JoinStatus = 1, baseParameterList = arr({ table.unpack(zeros) }) },
    { UnitId = 1006, JoinStatus = 0, commandSkillIdList = arr({}), Experience = 1650154, HitPoint = 5199, MagicPoint = 521, EquipWeaponId = 10699,
      EquipArmorId = 11301, EquipAccessoryIdList = arr({ 12029 }),
      activeSkillIdList = arr({ 408010, 220070, 220030, 408050, 431120, 408030, 220110 }),
      baseParameterList = arr({ table.unpack(zeros) }) },
    { UnitId = 1003, JoinStatus = 1, activeSkillIdList = arr({ 403010 }), commandSkillIdList = arr({}), baseParameterList = arr({}) },
  }),
  unitGuest = { HitPoint = 0, MagicPoint = 0 },
  Player = { WinNum = 0 },
  chat = { DataMap = chatMap({ ATC11 = { IsReleased = true, IsAlreadyPlayed = false } }),
           NoticeQueue = arr({ "ATC11" }), LatestNotice = "ATC11" },
  Map = { mapId = -1, unitLocation = { X = 0.0, Y = 0.0, Z = 0.0 }, unitDirection = 0,
          airShipLocation = { X = -6748.5, Y = 7696.7, Z = 72.6 }, airShipDirection = 0, airShipIslandType = 0, IsRidingAirShip = false,
          IsIntoTheAirShip = false, IsAlreadySpawnAirship = false },
})
bag = { [10699] = 1, [11301] = 1, [12029] = 1, [1] = 4 }
visited, known, saved, reloaded = {}, {}, {}, {}
libs = {
  ["/Script/mucha.Default__CPP_BFL_SaveDataInventory"] = obj({
    SetInventoryItem = function(_, id, n) bag[id] = n end,
    FindInventory = function(_, id) return bag[id] or 0 end }),
  ["/Script/mucha.Default__CPP_BFL_SaveData_PerMap"] = obj({
    AddKnownMap = function(_, m) known[m] = true end, AddVisitedMap = function(_, m) visited[m] = true end,
    IsVisited = function(_, m) return visited[m] == true end }),
  ["/Script/mucha.Default__CPP_BFL_SaveDataProgress"] = obj({
    GetFlag = function(_, i) return sd.Progress.eventFlag[i + 1] end }),
  ["/Script/mucha.Default__CPP_BFL_SaveData"] = obj({ SaveGameData = function(_, slot) saved[#saved + 1] = slot end }),
}
function StaticFindObject(p) return libs[p] end
unitLevels, levelCalls = {}, {}
libs["/Script/mucha.Default__CPP_BFL_Unit"] = obj({
  GetMaxLevel = function() return 99 end,
  GetExpForReachLevel = function(_, id, level) return level == 1 and 0 or level * 100 end,
  SetPlayableUnitExperience = function(_, id, exp, full)
    levelCalls[#levelCalls + 1] = { id = id, full = full }
    unitLevels[id] = exp == 0 and 1 or exp / 100
  end,
  GetPlayableUnitLevel = function(_, id) return unitLevels[id] or 27 end,
})
mgr = obj({ m_pGameSaveData = sd })
mapMgr = obj({ MapTestStartByChoiceSlotLoadSaveData = function(_, slot) reloaded[#reloaded + 1] = slot end })
function FindFirstOf(c)
  if c == "CPP_MuchaSaveDataManager" then return mgr end
  if c == "CPP_MapManager" then return mapMgr end
end
function FindAllOf() return nil end
G = (require("game"))
''')
lua = L.eval

ok, report = L.execute("return G.SkipPrologue()")
lines = list(report.values())
print("\n".join(lines))
assert ok is True, lines
assert all(l.startswith("ok") or l.startswith("     ") for l in lines), lines
assert "     the game reads flag 14 as true" in lines[2], lines[2]

assert lua("G.StoryCounter()") == 1030
on = [i for i in range(1300) if lua(f"sd.Progress.eventFlag[{i + 1}]")]
assert on == [14, 15, 16, 18, 19, 22, 23, 26, 27, 30, 32, 33, 105, 106, 108, 110, 124, 125, 1164, 1225, 1226], on
assert lua("#sd.Party.partyList") == 2 and lua("sd.Party.partyList[1]") == 1001 and lua("sd.Party.partyList[2]") == 1002
assert lua("sd.unitParameterList[1].JoinStatus") == 0 and lua("sd.unitParameterList[2].JoinStatus") == 0
assert lua("sd.unitParameterList[1].baseParameterList[6]") == 3 and lua("sd.unitParameterList[2].baseParameterList[6]") == 0
fina = "sd.unitParameterList[3]"
for field, want in (("JoinStatus", 2), ("Experience", 0), ("HitPoint", 200), ("MagicPoint", 70),
                    ("EquipWeaponId", 10600), ("EquipArmorId", -1)):
    assert lua(f"{fina}.{field}") == want, (field, lua(f"{fina}.{field}"))
assert lua(f"#{fina}.EquipAccessoryIdList") == 0 and lua(f"#{fina}.activeSkillIdList") == 0
for item, n in ((10100, 1), (10200, 1), (11000, 2), (12000, 2), (10699, 0), (11301, 0), (12029, 0), (1, 4)):
    assert lua(f"bag[{item}]") == n, (item, lua(f"bag[{item}]"))
assert lua("sd.unitGuest.HitPoint") == 9999 and lua("sd.unitGuest.MagicPoint") == 9999 and lua("sd.Player.WinNum") == 3
for m in (5010, 2013, 20000, 3001):
    assert lua(f"visited[{m}]") is True and lua(f"known[{m}]") is True
assert lua("sd.Map.mapId") == 3001 and lua("sd.Map.unitLocation.X") == -5775.0 and lua("sd.Map.unitLocation.Z") == -197.85
assert lua("sd.Map.unitDirection") == 2

ok, detail = L.execute("return G.SaveAndReload(0)")
assert ok is True and detail == "saved to slot 0 (map 3001, flag 1 false), reloading", detail
assert lua("saved[1]") == 0 and lua("reloaded[1]") == 0

# round 8: the opening's autosave put the real position back and turned flags 1 and 8 on;
# applying the skip again (story already 1030) restores both
L.execute("""sd.Map.mapId = 10040; sd.Map.unitLocation.Y = 50000.0
  sd.Progress.eventFlag[2] = true; sd.Progress.eventFlag[9] = true""")
ok, report = L.execute("return G.SkipPrologue({ inventory = false })")
assert ok is True, list(report.values())
assert any("inventory left alone" in l for l in report.values())
assert lua("sd.Map.mapId") == 3001 and lua("sd.Map.unitLocation.Y") == 0.0
assert lua("sd.Progress.eventFlag[2]") is False and lua("sd.Progress.eventFlag[9]") is False
assert lua("#sd.Party.partyList") == 2 and lua("bag[11000]") == 2, "applying twice changes nothing else"

# a save that writes the real position over the map: reported, and no reload
L.execute("""libs["/Script/mucha.Default__CPP_BFL_SaveData"].SaveGameData =
  function(_, slot) saved[#saved + 1] = slot; sd.Map.mapId = 10040 end""")
ok, detail = L.execute("return G.SaveAndReload(0)")
assert ok is False and "not 3001" in detail and "Not reloading" in detail, detail
assert lua("#reloaded") == 1, "no second reload"
L.execute("""libs["/Script/mucha.Default__CPP_BFL_SaveData"].SaveGameData = function(_, slot) saved[#saved + 1] = slot end
  sd.Map.mapId = 3001""")

# 0.16.0: the open world start replaces 1030 and the Earth Shrine; the reload then checks for its
# map. 0.18.0 (round 36: the tower's two events wrote only story 8000): the default "dock" start
# writes 8000 at the dock where those events leave the player, so they do not play.
# Round 37: the user chose the air start, so it is the default.
DOCK_STORY, EVENT_STORY, TOWER_MAP, WORLD_MAP = 8000, 7090, 3280, 1000
assert lua("G.OPEN_START.name") == "air", lua("G.OPEN_START.name")
L.execute("G.OPEN_START = G.OPEN_STARTS.dock")
ok, report = L.execute("return G.SkipPrologue({ inventory = false, openStart = true })")
assert ok is True, list(report.values())
assert f"ok   story counter -> {DOCK_STORY}" in list(report.values())
# Round 37: an open world start marks every Active Time Chat as released and played
CHATS = 56
assert f"ok   active time chats: {CHATS} of {CHATS} released and played ({CHATS - 1} rows added), notices cleared, flag 31 on" in list(report.values())
assert lua("#sd.chat.NoticeQueue") == 0 and lua("sd.chat.LatestNotice:ToString()") == "None"
assert lua("sd.chat.DataMap.rows.ATC11.IsAlreadyPlayed") is True and lua("sd.chat.DataMap.rows.ATC63.IsReleased") is True
assert lua("G.ChatState()") == f"{CHATS} rows, {CHATS} released, {CHATS} played; notices [], latest None", lua("G.ChatState()")
assert lua("sd.Progress.eventFlag[32]") is True, "flag 31 is what a chat row turns on"
# Round 39: the Equip screen shows visions only with flag 24, and the story sets 21 with it
assert "ok   open world flags on: 8 features, 53 tutorials" in list(report.values())
# Round 46: Siren is an ability on both Finas, and asking again adds nothing
assert "ok   Siren: summon abilities on both Finas" in list(report.values())
fina_skills = lambda u: [v for v in L.eval(f"rawget(unitAt({u}).activeSkillIdList, 'items')").values()]
L.execute("unitAt = function(id) for i = 1, #sd.unitParameterList do if sd.unitParameterList[i].UnitId == id then return sd.unitParameterList[i] end end end")
assert fina_skills(1003) == [403010, 6, 430980], fina_skills(1003)
assert lua("#unitAt(1006).commandSkillIdList") == 1 and lua("unitAt(1003).commandSkillIdList[1]") == 6
assert lua("sd.Progress.eventFlag[22]") is True and lua("sd.Progress.eventFlag[25]") is True, "flag i is element i + 1"
# Round 44: fast travel (13, 34, 1180) and the Earth Shrine's exit (102)
assert all(lua(f"sd.Progress.eventFlag[{i + 1}]") is True for i in (13, 34, 1180, 102))
# Round 45: staggering (25), Fina's summoning (28), and every tutorial marked seen
assert all(lua(f"sd.Progress.eventFlag[{i + 1}]") is True for i in (25, 28, 1160, 1199, 1217, 1229))
_events = paths.REPO / "dump/tables/FFRS/Content/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.json"
if _events.exists():
    import json
    _rows = json.loads(_events.read_text(encoding="utf8"))["Rows"]
    _seen = {f for k, r in _rows.items() if k.startswith("Tutorial_") for f in r.get("OnFlagList") or [] if f >= 1000}
    assert _seen <= set(L.eval("G.OPEN_WORLD_TUTORIALS").values()), _seen - set(L.eval("G.OPEN_WORLD_TUTORIALS").values())
assert lua("sd.Map.IsAlreadySpawnAirship") is False, "the dock start leaves the airship alone"
# the list of ids is the table's: every ATC row, and no Pinger or Nawatobi rows (dump/ is local)
_chat_table = paths.REPO / "dump/tables/FFRS/Content/Datatable/Chat/Event/CDT_ChatEventData.json" if hasattr(paths, "REPO") else None
if _chat_table and _chat_table.exists():
    import json
    _ids = sorted(k for k in json.loads(_chat_table.read_text(encoding="utf8"))["Rows"] if k.startswith("ATC"))
    assert sorted(L.eval("G.CHAT_IDS").values()) == _ids
assert lua("G.StoryCounter()") == DOCK_STORY and lua("sd.Map.mapId") == TOWER_MAP
assert lua("sd.Map.unitLocation.X") == -2704.8 and lua("sd.Map.unitLocation.Y") == -171166.7
assert lua("sd.Map.IsRidingAirShip") is False, "the dock start leaves the airship alone"
ok, detail = L.execute(f"return G.SaveAndReload(0, {TOWER_MAP})")
assert ok is True and detail == f"saved to slot 0 (map {TOWER_MAP}, flag 1 false), reloading", detail
ok, detail = L.execute("return G.SaveAndReload(0)")
assert ok is False and f"map is {TOWER_MAP}" in detail and "not 3001" in detail, "the default still expects 3001"
# 0.16.1: G.OpenStart writes only the story and the arrival, on a save that already had the skip
L.execute("sd.Progress.Progress[1] = 1030; sd.Map.mapId = 3001; sd.Player.WinNum = 12")
ok, report = L.execute("return G.OpenStart()")
assert ok is True and list(report.values())[:2] == [
    f"ok   story counter -> {DOCK_STORY}", f"ok   arrival: map {TOWER_MAP} at -2704.8, -171166.7, 3002.2"], list(report.values())
assert list(report.values())[2].startswith("ok   active time chats: 56 of 56"), list(report.values())
assert list(report.values())[3] == "ok   open world flags on: 8 features, 53 tutorials", list(report.values())
assert lua("G.StoryCounter()") == DOCK_STORY and lua("sd.Map.mapId") == TOWER_MAP
assert lua("sd.Player.WinNum") == 12, "the rest of the save is left alone"
# the "air" start: the world map, riding the airship beside the tower, with flag 31 on
L.execute("G.OPEN_START = G.OPEN_STARTS.air; sd.Progress.eventFlag[32] = false")
ok, report = L.execute("return G.OpenStart()")
assert ok is True and list(report.values())[1] == (
    f"ok   arrival: map {WORLD_MAP} at -5935.0, -8305.0, 2075.0, in the airship, flags 31 on"), list(report.values())
assert lua("sd.Map.IsRidingAirShip") is True and lua("sd.Map.airShipDirection") == 2
# Round 39: the airship stays on the map after a visit to a town only if it counts as placed
assert lua("sd.Map.IsAlreadySpawnAirship") is True
assert lua("G.AirshipState()") == "placed true, riding true, inside false, at (-5935, -8305, 2075), direction 2, island 0", lua("G.AirshipState()")
assert (lua("sd.Map.airShipLocation.X"), lua("sd.Map.airShipLocation.Y"), lua("sd.Map.airShipLocation.Z")) == (-5935.0, -8305.0, 2075.0)
assert lua("sd.Progress.eventFlag[32]") is True, "flag 31 is Lua element 32"
# the "event" start: story 7090 at the dock, so the tower's two events play
L.execute("G.OPEN_START = G.OPEN_STARTS.event")
ok, report = L.execute("return G.OpenStart()")
assert ok is True and lua("G.StoryCounter()") == EVENT_STORY and lua("sd.Map.mapId") == TOWER_MAP
L.execute("G.OPEN_START = G.OPEN_STARTS.dock; sd.Map.IsRidingAirShip = false")

# Round 44: a seed's own starting party, here Jake leading Archwitch Fina. They join, Rain and
# Lasswell do not, Fina stays usable with her first ability, and the bag holds the starters' gear.
L.execute("""sd.Progress.Progress[1] = 1005; bag = { [10699] = 1, [11301] = 1, [12029] = 1 }
  sd.Party.partyList = arr({ 1006 })
  G.OPEN_START = G.OPEN_STARTS.air
  unitAt = function(id) for i = 1, #sd.unitParameterList do if sd.unitParameterList[i].UnitId == id then return sd.unitParameterList[i] end end end
  table.insert(rawget(sd.unitParameterList, "items"), { UnitId = 1007, JoinStatus = 1, baseParameterList = arr({}) })
  unitAt(1001).JoinStatus = 1; unitAt(1002).JoinStatus = 1""")
ok, report = L.execute("return G.SkipPrologue({ openStart = true, party = { 1007, 1006 } })")
lines = list(report.values())
assert ok is True, lines
assert "ok   party -> [1007, 1006]" in lines and "ok   join status: Jake, Archwitch Fina 0" in lines, lines
assert lua("unitAt(1007).JoinStatus") == 0 and lua("unitAt(1006).JoinStatus") == 0 and lua("unitAt(1001).JoinStatus") == 1
assert lua("unitAt(1006).activeSkillIdList[1]") == 408010 and lua("unitAt(1006).EquipWeaponId") == 10600
assert lua("bag[10700]") == 1 and lua("bag[12022]") == 1 and lua("bag[10600]") == 1, "Jake's and her gear"
assert lua("bag[10100]") is None and lua("bag[10699]") == 0, "Rain's gear stays out, the prologue gear goes"
# Round 44: everyone starts at level 1 with HP and MP filled, Jake's 27 included
assert "ok   party levels: all 8 at level 1" in lines, lines
assert lua("unitLevels[1007]") == 1 and lua("levelCalls[#levelCalls].full") is True
# Round 44: a join ends with JoinStatus 0 and usable. Round 46: and no spare copy of the gear
L.execute("""unitAt(1002).JoinStatus = 1; unitAt(1002).IsUsable = false
libs["/Script/mucha.Default__CPP_BFL_SaveDataInventory"].AddInventory = function(_, id, n) bag[id] = (bag[id] or 0) + n end
bag[10200] = nil""")
L.execute("G.FinishJoin(1002)")
assert lua("unitAt(1002).JoinStatus") == 0 and lua("unitAt(1002).IsUsable") is True and lua("bag[10200]") is None
# Round 44: the save slot's level is Rain's, so while she is away it follows the party
L.execute("""G.PartyLevel = function() return 9, "1007:9" end
G.UnitJoinStatus = function(id) return joinOf[id] end
joinOf = { [1001] = 1 }""")
assert lua("G.SyncSlotLevel()") is True and lua("unitLevels[1001]") == 9
assert lua("G.SyncSlotLevel()") is False, "already there"
L.execute("joinOf[1001] = 0; G.PartyLevel = function() return 20, 'x' end")
assert lua("G.SyncSlotLevel()") is False and lua("unitLevels[1001]") == 9, "once she has joined, her level is her own"
L.execute("G.UnitJoinStatus = nil")
# Round 45: the moogle's screen is closed while the save owns no vision, and opens with the first
L.execute("""
function nameOf(s) return { get = function() return { ToString = function() return s end } end } end
shopRows = { VisionUpgrade = { EventType = 1 }, VisionUpgrade_Main = { EventType = 1 }, FEV_Town_10Cry_41_720_01 = { EventType = 1 },
             Other = { EventType = 1 } }
libs["/Game/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.CDT_TalkEventData_Prod"] = {
  GetFullName = function() return "CDT" end, IsValid = function() return true end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  ForEachRow = function(_, fn) for k, r in pairs(shopRows) do fn(nameOf(k), r) end end }
sd.visionList = arr({}, 0)""")
blocked, rows = L.execute("return G.VisionShopGuard()")
assert blocked is True and rows == 3 and lua("shopRows.VisionUpgrade.EventType") == 0 and lua("shopRows.Other.EventType") == 1
assert lua("G.VisionShopGuard()") is None, "no writes while nothing changes"
L.execute("sd.visionList = arr({ 13017 }, 0)")
blocked, rows = L.execute("return G.VisionShopGuard()")
assert blocked is False and rows == 3 and lua("shopRows.FEV_Town_10Cry_41_720_01.EventType") == 1
L.execute("""sd.visionList = nil""")
# Round 46: the crystals skip to their last row, which keeps its flags and gives nothing
L.execute("""
local function cont(id) return { EventId = FName(id) } end
crystalRows = { Int_LegendEV_10_01 = { EventType = 0, ContinuousEventList = { cont("Int_LegendEV_10_01_MV") } },
  Int_LegendEV_10_01_Short = { EventType = 0, ContinuousEventList = { cont("Int_LegendEV_10_01_MV") } },
  Int_LegendEV_10_07 = { EventType = 0, ObtainItemList = arr({ { ID = 13120 } }), OnFlagList = arr({ 1000, 1017 }) },
  Int_LegendEV_10_02_MV = { EventType = 0 } }
shopRows = crystalRows""")
assert lua("G.CrystalsPatch()") == 3
assert lua("crystalRows.Int_LegendEV_10_01.ContinuousEventList[1].EventId:ToString()") == "Int_LegendEV_10_07"
assert lua("crystalRows.Int_LegendEV_10_01_Short.ContinuousEventList[1].EventId:ToString()") == "Int_LegendEV_10_07"
assert lua("crystalRows.Int_LegendEV_10_01.EventType") == 1 and lua("crystalRows.Int_LegendEV_10_02_MV.EventType") == 0
assert lua("#crystalRows.Int_LegendEV_10_07.ObtainItemList") == 0 and lua("#crystalRows.Int_LegendEV_10_07.OnFlagList") == 2
_crystals = [r.split("\t") for r in (paths.REPO / "data/crystals.tsv").read_text(encoding="utf8").splitlines()[1:]]
_lua = [(c["event"], c["map"], c["flag"]) for c in L.eval("G.CRYSTALS").values()]
assert sorted(_lua) == sorted((int(a), int(b), int(c)) for a, b, c, _ in _crystals), "data/crystals.tsv and G.CRYSTALS differ"
# Round 46: a shiny that is a location is blanked; a key item, a story spot and an open one are not
L.execute("""
function shiny(id, money, open) local a = { m_ItemId = id, m_ItemNum = 2, m_Money = money }
  return { actor = a, itemId = id, money = money, open = open } end
s1, s2, s3, s4, s5 = shiny(10302, -1), shiny(25004, -1), shiny(-1, -1), shiny(10302, -1, true), shiny(-1, 500)""")
assert lua("G.BlankFieldItem(s1, false, true)") is False, "shards only: a normal shiny stays"
assert lua("G.BlankFieldItem(s1, true, false)") is True and lua("s1.actor.m_ItemId") == -1 and lua("s1.actor.m_Money") == 1
assert lua("G.BlankFieldItem(s5, true, false)") is True and lua("s5.actor.m_Money") == 1, "gil too"
assert lua("G.BlankFieldItem(s2, true, false)") is False and lua("s2.actor.m_ItemId") == 25004, "without the option a Tablet Shard stays"
assert lua("G.BlankFieldItem(s3, true, true)") is False and lua("G.BlankFieldItem(s4, true, true)") is False
L.execute("s1.itemId, s1.money = -1, 1")
assert lua("G.BlankFieldItem(s1, true, true)") is False, "already blank"
# Round 47: with the option a Tablet Shard shiny is blanked too; another key item never is
assert lua("G.BlankFieldItem(s2, false, true)") is True and lua("s2.actor.m_ItemId") == -1
L.execute("s6 = shiny(20009, -1)")
assert lua("G.BlankFieldItem(s6, true, true)") is False, "a key card stays"
# Round 45: a chest holding Magicite is blanked like the others; a key item's stays
L.execute("""
chestRows = { { mapId = 3030, ID = 1, ItemId = 25000, ItemNum = 1, Money = -1 }, { mapId = 2031, ID = 20, ItemId = 20016, ItemNum = 1, Money = -1 },
              { mapId = 2020, ID = 1, ItemId = 1, ItemNum = 2, Money = -1 } }
libs["/Game/Datatable/Map/Gimmick/TreasureBox/CDT_MapGimmickTreasureBox.CDT_MapGimmickTreasureBox"] = {
  GetFullName = function() return "chests" end, IsValid = function() return true end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  ForEachRow = function(_, fn) for _, r in ipairs(chestRows) do fn("r", r) end end }
""")
assert lua("G.BlankChests(true)") == 2
assert lua("chestRows[1].ItemId") == -1 and lua("chestRows[1].Money") == 1, "Magicite is blanked"
assert lua("chestRows[2].ItemId") == 20016, "a key item stays"
assert lua("G.BlankChests(false)") == 2 and lua("chestRows[1].ItemId") == 25000, "and it comes back"
# a member who joins later can be set to the party's level, above or below his own
ok, detail = L.execute("return G.SetUnitLevel(1007, 12)")
assert ok is True and detail == "level 12" and lua("unitLevels[1007]") == 12, detail
L.execute("""libs["/Script/mucha.Default__CPP_BFL_Unit"].GetMaxLevel = function() return 15 end""")
ok, detail = L.execute("return G.SetUnitLevel(1007, 40)")
assert ok is True and detail == "level 15", "held to the game's cap"
L.execute("""libs["/Script/mucha.Default__CPP_BFL_Unit"].GetMaxLevel = function() return 99 end""")
L.execute("sd.Party.partyList = arr({ 1006 }); G.OPEN_START = G.OPEN_STARTS.dock")

# the plain prologue skip leaves the chats alone, and a save with no chat data fails the step only
L.execute("sd.chat.DataMap.rows = {}")
ok, report = L.execute("return G.SkipPrologue({ inventory = false })")
assert ok is True and lua("next(sd.chat.DataMap.rows)") is None
L.execute("savedChat = sd.chat; sd.chat = nil")
ok, report = L.execute("return G.OpenStart()")
assert ok is False and list(report.values())[2] == "FAIL active time chats: the save has no chat data"
L.execute("sd.chat = savedChat; G.OPEN_START = G.OPEN_STARTS.dock")

# 0.7.0: an Archipelago item granted before the skip with a starter item's id is kept
L.execute("bag = { [10699] = 1, [11301] = 1, [12029] = 1, [12000] = 1 }; sd.Progress.Progress[1] = 1005")
ok, report = L.execute("return G.SkipPrologue()")
assert ok is True, list(report.values())
assert lua("bag[12000]") == 3 and lua("bag[10699]") == 0 and lua("bag[10100]") == 1, lua("bag[12000]")

# a missing library is reported, and the rest still runs
L.execute('libs["/Script/mucha.Default__CPP_BFL_SaveDataInventory"] = nil; sd.Progress.Progress[1] = 1000')
ok, report = L.execute("return G.SkipPrologue()")
lines = list(report.values())
assert ok is False and any(l.startswith("FAIL inventory") for l in lines), lines
assert sum(1 for l in lines if l.startswith("FAIL")) == 1, lines
# no map manager: the save is written but the reload is left to the player
L.execute("mapMgr.IsValid = function() return false end")
ok, detail = L.execute("return G.SaveAndReload(2)")
assert ok is False and "load the slot by hand" in detail, detail
# Round 49: artifacts in the bag go into the save's artifact list once, on or off as the game ships them
L.execute("""
artifacts = { rows = { [30002] = { IsActive = true } } }
function artifacts:ForEach(fn) for id in pairs(self.rows) do fn({ get = function() return id end }) end end
function artifacts:Add(id, v) self.rows[id] = v end
sd.artifactList = artifacts
libs["/Script/mucha.Default__CPP_BFL_SaveDataInventory"] = { IsValid = function() return true end,
  FindInventory = function(_, id) return bag[id] or 0 end }
bag[30001], bag[30006], bag[30002] = 1, 1, 1""")
added = L.execute("return G.SyncArtifacts()")
assert sorted(added.values()) == [30001, 30006], list(added.values())
assert lua("artifacts.rows[30001].IsActive") is False and lua("artifacts.rows[30006].IsActive") is True
assert len(list(L.execute("return G.SyncArtifacts()").values())) == 0, "nothing twice"
L.execute("bag[30001], bag[30006], bag[30002] = nil, nil, nil")
# Round 49: the boss fight test makes the closed chests near you traps for the group, takes the
# story's scenes off the group, and puts it all back
L.execute("""
talkRows = { ["12Arms_01Sword_1stAwake_Victory"] = { EventType = 0, ObtainItemList = arr({ { ID = 10199 } }), OnFlagList = arr({ 901, 1237 }) },
  ["12Arms_01Sword_1stAwake_Encount"] = { EventType = 0, encountGroupId = 9957 },
  Gim_EV_Majipot_Delete_02 = { EventType = 0, OnFlagList = arr({ 915 }) },
  Other = { EventType = 0, encountGroupId = 5 } }
shopRows = talkRows
siren = { ID = 9013, battleEventId = 77, battleFinishEventId = FName("C01_037_01"), battleFinishLoseEventId = FName("None"),
          battleFinishEscapeEventId = FName("None"), isResultSkipOnWin = true, isResultSkipOnLose = false }
libs["/Game/Datatable/Encount/DT_BattleGroup.DT_BattleGroup"] = {
  GetFullName = function() return "DT" end, IsValid = function() return true end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  ForEachRow = function(_, fn) fn(nameOf("Siren"), siren) end }
local function chest(map, id) return { mapId = map, ID = id, ItemId = 3, ItemNum = 1, Money = -1, IsTrap = false,
  battleGroupId = -1, battleFinishEventId = FName("None") } end
chestRows = { chest(3020, 1), chest(3020, 2), chest(3020, 3), chest(2000, 1) }
local function actor(data, open) return { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
  HasAnyFlags = function() return false end, m_Id = data.ID, m_IsOpen = open, m_TreasureBoxData = data } end
nearChests = { actor(chest(3020, 1), false), actor(chest(3020, 2), true) }
function FindAllOf(c) if c == "CPP_MapGimmick_TreasureBox" then return nearChests end return nil end
libs["/Script/mucha.Default__CPP_BFL_SaveDataProgress"].SetFlag = function(_, i, on) sd.Progress.eventFlag[i + 1] = on end
sd.Progress.eventFlag[1441] = true
said = {}
function say(s) said[#said + 1] = s end""")
ok, detail = L.execute("return G.BossTestArm(1, say)")
assert ok is False and "no battle group 1" in detail, detail
ok, detail = L.execute("return G.BossTestArm(9013, say)")
assert ok is True and "1 chests near you (1 table rows, 1 live), 1 pedestal rows" in detail, detail
fight = 'talkRows["12Arms_01Sword_1stAwake_Encount"].encountGroupId'
assert lua(fight) == 9013 and lua("talkRows.Other.encountGroupId") == 5, "only the sword pedestal's fight row"
assert lua("chestRows[1].IsTrap") is True and lua("chestRows[1].battleGroupId") == 9013
assert lua("chestRows[1].battleFinishEventId:ToString()") == "12Arms_01Sword_1stAwake_Victory"
assert lua("nearChests[1].m_TreasureBoxData.IsTrap") is True and lua("nearChests[1].m_TreasureBoxData.battleGroupId") == 9013, "the live copy too"
assert lua("chestRows[2].IsTrap") is False and lua("chestRows[3].IsTrap") is False, "an opened chest and one far away stay"
win = 'talkRows["12Arms_01Sword_1stAwake_Victory"]'
assert lua(win + ".EventType") == 0, "still a Sequence row, so its scene fades the screen back in"
assert lua("#" + win + ".ObtainItemList") == 0
assert lua(win + ".OnFlagList[1]") == 1440 and lua(win + ".OnFlagList[2]") == 1440
assert lua("siren.battleEventId") == -1 and lua("siren.battleFinishEventId:ToString()") == "12Arms_01Sword_1stAwake_Victory"
assert lua("siren.isResultSkipOnWin") is False
assert lua("sd.Progress.eventFlag[1441]") is False, "the win flag starts off"
assert "start 77, win C01_037_01" in " ".join(L.eval("said").values()), "the group's own events are logged"
ok, detail = L.execute("return G.BossTestArm(9013, say)")
assert ok is True, "arming again starts from the originals"
assert L.execute("return G.BossTestOff(say)") == 5, "the fight row, the win row, two copies of the chest, and the group"
assert lua(fight) == 9957
assert lua("chestRows[1].IsTrap") is False and lua("chestRows[1].battleGroupId") == -1
assert lua("chestRows[1].battleFinishEventId:ToString()") == "None" and lua("nearChests[1].m_TreasureBoxData.IsTrap") is False
assert lua(win + ".OnFlagList[1]") == 901 and lua(win + ".OnFlagList[2]") == 1237 and lua(win + ".EventType") == 0
# quiet: the win row is the magic pots' after-win row, whose flag is ours while the test is on
pot = "talkRows.Gim_EV_Majipot_Delete_02.OnFlagList[1]"
ok, detail = L.execute("return G.BossTestArm(9013, say, true)")
assert ok is True and lua("siren.battleFinishEventId:ToString()") == "Gim_EV_Majipot_Delete_02"
assert lua("chestRows[1].battleFinishEventId:ToString()") == "Gim_EV_Majipot_Delete_02"
assert lua(pot) == 1440 and lua(win + ".OnFlagList[1]") == 901, "the Victory row is left alone"
L.execute("G.BossTestOff(say)")
assert lua(pot) == 915
assert lua("siren.battleEventId") == 77 and lua("siren.battleFinishEventId:ToString()") == "C01_037_01" and lua("siren.isResultSkipOnWin") is True
assert L.execute("return G.BossTestOff(say)") == 0, "nothing to undo"
L.execute("nearChests = {}")
ok, detail = L.execute("return G.BossTestArm(9013, say)")
assert ok is True and "0 chests near you" in detail and lua(fight) == 9013, "the pedestal works with no chest near"
L.execute("G.BossTestOff(say)")
L.execute("function FindAllOf() return nil end")
# Round 49: the watch probe takes a class's native functions, not its getters, delegates or Blueprint events
L.execute("""
local function fn(name, flags) return { GetFName = function() return { ToString = function() return name end } end,
  GetFunctionFlags = function() return flags end } end
libs["/Script/mucha.CPP_MapManager"] = { IsValid = function() return true end, ForEachFunction = function(_, f)
  for _, x in ipairs({ fn("Encount", 0x400), fn("GetMapId", 0x400), fn("OnDone__DelegateSignature", 0x400),
                       fn("BP_Event", 0x800), fn("Execute_EncountStart", 0x401) }) do f(x) end end }""")
paths, flags_read = L.execute('return G.FunctionPaths("CPP_MapManager")')
assert list(paths.values()) == ["/Script/mucha.CPP_MapManager:Encount", "/Script/mucha.CPP_MapManager:Execute_EncountStart"], list(paths.values())
assert flags_read is True and lua('G.FunctionPaths("CPP_Nothing")') is None
# Round 50: our settings as Options rows with tags of their own, copied from a slider and a switch,
# and their values read back from the option save
L.execute("""
local function tagged(t) return { TagName = FName(t) } end
optRows = { a = { Type = 1, EntryTag = tagged("Delegate.UI.System.Option.Root.GameSetting.EncountSensor"), DefaultRadioButtonIndex = 0 },
            b = { Type = 2, EntryTag = tagged("Delegate.UI.System.Option.Root.GameSetting.GamePad.Sensitivity"),
                  SliderInfo = { MinValue = 1, MaxValue = 10, DefaultValue = 5 } } }
optDT = { GetFullName = function() return "opt" end, IsValid = function() return true end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  ForEachRow = function(_, fn) for k, r in pairs(optRows) do fn(nameOf(k), r) end end,
  AddRow = function(_, name, template)
    local copy = {} for k, v in pairs(template) do copy[k] = v end
    copy.EntryTag = { TagName = template.EntryTag.TagName }
    if template.SliderInfo then copy.SliderInfo = { MinValue = 0, MaxValue = 0, DefaultValue = 0 } end
    optRows[name] = copy end,
  FindRow = function(_, name) return optRows[name] end }
libs["/Game/Datatable/UI/Option/Root/GameSetting/DT_OP_GameSetting.DT_OP_GameSetting"] = optDT
FText = FText or function(text) return { ToString = function() return text end } end""")
ok, detail = L.execute("return G.AddOptionRows(say)")
assert ok is True and "2 rows before" in detail and "not added" not in detail and "failed" not in detail, detail
assert lua("optRows.FFRAP_Exp.EntryTag.TagName:ToString()") == "Delegate.UI.System.Option.Root.GameSetting.FFRAP.FFRAP_Exp"
assert lua("optRows.FFRAP_Exp.Type") == 2 and lua("optRows.FFRAP_Exp.SliderInfo.MaxValue") == 10
assert lua("optRows.FFRAP_EncounterRate.SliderInfo.MaxValue") == 5 and lua("optRows.FFRAP_Scaling.Type") == 1
assert lua("optRows.FFRAP_Exp.DisplayText:ToString()") == "AP: EXP rate"
assert lua("optRows.b.EntryTag.TagName:ToString()").endswith("GamePad.Sensitivity"), "the game's own row is left alone"
ok, detail = L.execute("return G.AddOptionRows(say)")
assert "8 rows before" in detail, "a second run adds nothing"
L.execute("""
local function entry(tag, value) return { get = function() return { TagName = FName(tag) } end }, { get = function() return { Value = value } end } end
optSave = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  m_EntrySaveDataList = { ForEach = function(_, fn)
    fn(entry("Delegate.UI.System.Option.Root.GameSetting.FFRAP.FFRAP_Exp", 3))
    fn(entry("Delegate.UI.System.Option.Root.GameSetting.FFRAP.FFRAP_Encounters", 1))
    fn(entry("Delegate.UI.System.Option.Root.GameSetting.FFRAP.FFRAP_Scaling", 0))
    fn(entry("Delegate.UI.System.Option.Root.GameSetting.EncountSensor", 1)) end } }
local prevFFO = FindFirstOf
function FindFirstOf(c) if c == "CPP_MuchaOptionSaveData" then return optSave end return prevFFO(c) end""")
values = L.execute("return G.ReadOptionValues()")
assert dict(values) == {"exp": 3, "encounters": False, "scaling": True}, dict(values)
# Round 50: an artifact can be switched on or off in the artifact list
L.execute("""
artifactRows = { [30010] = { IsActive = false }, [30000] = { IsActive = true } }
sd.artifactList = { ForEach = function(_, fn) for id, row in pairs(artifactRows) do
  fn({ get = function() return id end }, { get = function() return row end }) end end }""")
found, states = L.execute("return G.Artifacts(30010, true)")
assert found is True and lua("artifactRows[30010].IsActive") is True and states == "30000 on, 30010 on", states
found, _ = L.execute("return G.Artifacts(30001, true)")
assert found is False
print("skip: ok")
