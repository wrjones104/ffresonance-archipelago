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
  Map = { mapId = -1, unitLocation = { X = 0.0, Y = 0.0, Z = 0.0 }, unitDirection = 0 },
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
