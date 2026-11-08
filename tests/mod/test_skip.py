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
    { UnitId = 1006, JoinStatus = 0, Experience = 1650154, HitPoint = 5199, MagicPoint = 521, EquipWeaponId = 10699,
      EquipArmorId = 11301, EquipAccessoryIdList = arr({ 12029 }),
      activeSkillIdList = arr({ 408010, 220070, 220030, 408050, 431120, 408030, 220110 }),
      baseParameterList = arr({ table.unpack(zeros) }) },
  }),
  unitGuest = { HitPoint = 0, MagicPoint = 0 },
  Player = { WinNum = 0 },
  chat = { DataMap = chatMap({ ATC11 = { IsReleased = true, IsAlreadyPlayed = false } }),
           NoticeQueue = arr({ "ATC11" }), LatestNotice = "ATC11" },
  Map = { mapId = -1, unitLocation = { X = 0.0, Y = 0.0, Z = 0.0 }, unitDirection = 0,
          airShipLocation = { X = -6748.5, Y = 7696.7, Z = 72.6 }, airShipDirection = 0, IsRidingAirShip = false },
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
assert lua("G.StoryCounter()") == DOCK_STORY and lua("sd.Map.mapId") == TOWER_MAP
assert lua("sd.Player.WinNum") == 12, "the rest of the save is left alone"
# the "air" start: the world map, riding the airship beside the tower, with flag 31 on
L.execute("G.OPEN_START = G.OPEN_STARTS.air; sd.Progress.eventFlag[32] = false")
ok, report = L.execute("return G.OpenStart()")
assert ok is True and list(report.values())[1] == (
    f"ok   arrival: map {WORLD_MAP} at -5935.0, -8305.0, 2075.0, in the airship, flags 31 on"), list(report.values())
assert lua("sd.Map.IsRidingAirShip") is True and lua("sd.Map.airShipDirection") == 2
assert (lua("sd.Map.airShipLocation.X"), lua("sd.Map.airShipLocation.Y"), lua("sd.Map.airShipLocation.Z")) == (-5935.0, -8305.0, 2075.0)
assert lua("sd.Progress.eventFlag[32]") is True, "flag 31 is Lua element 32"
# the "event" start: story 7090 at the dock, so the tower's two events play
L.execute("G.OPEN_START = G.OPEN_STARTS.event")
ok, report = L.execute("return G.OpenStart()")
assert ok is True and lua("G.StoryCounter()") == EVENT_STORY and lua("sd.Map.mapId") == TOWER_MAP
L.execute("G.OPEN_START = G.OPEN_STARTS.dock; sd.Map.IsRidingAirShip = false")

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
print("skip: ok")
