"""game.lua against fake UE4SS objects: the save snapshot and snapdiff.py, the probes (inspect,
find, layout), the title menu entry and order, the version line and logo, the item feed, and the
chest pop-up."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

import os
import subprocess
import sys
import tempfile

from lupa import lua54

SCRIPTS = str(paths.SCRIPTS).replace("\\", "/")
WORK = tempfile.mkdtemp(prefix="ffrap_game_")
os.makedirs(WORK, exist_ok=True)

L = lua54.LuaRuntime(unpack_returned_tuples=True)
L.execute(f'package.path = "{SCRIPTS}/?.lua;" .. package.path')
L.execute(r'''
function fname(s) return { ToString = function() return s end } end
function prop(name, kind, extra)
  local p = extra or {}
  function p:GetFName() return fname(name) end
  function p:GetClass() return { GetFName = function() return fname(kind) end } end
  return p
end
function struct(name, props, super)
  local s = { props = props }
  function s:ForEachProperty(fn) for _, p in ipairs(self.props) do fn(p) end end
  function s:GetSuperStruct() return super end
  function s:IsValid() return true end
  function s:GetFName() return fname(name) end
  return s
end
function arr(list)
  local a = { list = list }
  function a:GetArrayNum() return #self.list end
  function a:ForEach(fn) for i, v in ipairs(self.list) do fn(i, { get = function() return v end }) end end
  return a
end
objectClass = struct("Object", { prop("ShouldNotAppear", "IntProperty") })
local unitStruct = struct("FSaveData_Unit", { prop("SaveId", "IntProperty"), prop("JoinStatus", "ByteProperty") })
local progressStruct = struct("FSaveData_Progress", {
  prop("Progress", "ArrayProperty", { GetInner = function() return prop("x", "IntProperty") end }),
  prop("eventFlag", "ArrayProperty", { GetInner = function() return prop("x", "BoolProperty") end }),
})
perMapStruct = struct("FSaveData_PerMap", { prop("bIsVisited", "BoolProperty"), prop("count", "IntProperty") })
function perMapStruct:GetFullName() return "ScriptStruct /Script/mucha.SaveData_PerMap" end
local otherStruct = struct("FSaveData_Small", { prop("count", "IntProperty") })
function otherStruct:GetFullName() return "ScriptStruct /Script/mucha.SaveData_Small" end
local engineStruct = struct("FVector", { prop("X", "DoubleProperty") })
function engineStruct:GetFullName() return "ScriptStruct /Script/CoreUObject.Vector" end
scriptStructs = {}  -- FindAllOf("ScriptStruct") finds nothing in game
perMapStructT, otherStructT = perMapStruct, otherStruct
local wrapperMeta = { __tostring = function() return "UScriptStruct: 00000001E1737738" end }
function structValue(t) return setmetatable(t, wrapperMeta) end
function map(pairsList)
  local m = { list = pairsList }
  function m:ForEach(fn) for _, kv in ipairs(self.list) do
    fn({ get = function() return kv[1] end }, { get = function() return kv[2] end }) end end
  function m:Remove(key)
    for i, kv in ipairs(self.list) do if kv[1] == key then table.remove(self.list, i) return end end
  end
  return m
end
local saveBase = struct("SaveGame", {}, objectClass)
saveClass = struct("CPP_MuchaGameSaveData", {
  prop("Progress", "StructProperty", { GetStruct = function() return progressStruct end }),
  prop("unitParameterList", "ArrayProperty", { GetInner = function()
      return prop("x", "StructProperty", { GetStruct = function() return unitStruct end }) end }),
  prop("PlayTime", "FloatProperty"),
  prop("perMap", "MapProperty"),
}, saveBase)
function makeSave(flags, units, story, playTime, visited)
  local sd = { Progress = { Progress = arr({ story, 5 }), eventFlag = arr(flags) },
               unitParameterList = arr(units), PlayTime = playTime,
               perMap = map({ { 10040, structValue({ bIsVisited = true, count = 1 }) },
                              { 3001, structValue({ bIsVisited = visited, count = 2 }) } }) }
  function sd:GetClass() return saveClass end
  function sd:IsValid() return true end
  function sd:GetFullName() return "CPP_MuchaGameSaveData /Engine/Transient.SD_1" end
  return sd
end
current = nil
mgr = { m_pGameSaveData = nil }
function mgr:IsValid() return true end
function mgr:HasAnyInternalFlags() return false end
function mgr:HasAnyFlags() return false end
function FindFirstOf(c) if c == "CPP_MuchaSaveDataManager" then return mgr end return nil end
function FindAllOf(c)
  if c == "CPP_MuchaSaveDataManager" then return { mgr } end
  if c == "ScriptStruct" then return scriptStructs end
  return nil
end
-- Round 72: game.lua keeps objects between ticks as paths (G.PathOf) and finds them again with
-- StaticFindObject, which in the engine finds only objects that still exist. Fakes get a path here.
fakePaths = {}
function fakePathLookup(path)
  local o = fakePaths[path]
  if o and (not o.IsValid or o:IsValid()) then return o end
  return nil
end
function StaticFindObject(path)
  if fakePathLookup(path) then return fakePathLookup(path) end
  if path == "/Script/mucha.SaveData_PerMap" then return perMapStructT end
  if path == "/Script/mucha.SaveData_Timer" then return otherStructT end
  if path == "/Script/mucha.CPP_BFL_SaveDataParty" then return bflClass end
  return nil
end
local fnAdd = struct("AddUnit", { prop("unitId", "IntProperty"),
  prop("info", "StructProperty", { GetStruct = function() return perMapStruct end }), prop("ReturnValue", "BoolProperty") })
bflClass = { fns = { fnAdd } }
function bflClass:IsValid() return true end
function bflClass:ForEachFunction(fn) for _, f in ipairs(self.fns) do fn(f) end end
G = (require("game"))
G.PathOf = function(o) if not o then return nil end local k = "fake:" .. tostring(o); fakePaths[k] = o; return k end
function snap(path)
  local f = io.open(path, "w")
  local ok = G.Snapshot(function(k, v) f:write(k, "\t", tostring(v), "\n") end)
  f:close()
  return ok
end
''')
lua = L.eval
assert lua("snap('%s')" % (WORK + "/none.tsv").replace("\\", "/")) is False, "no save: false"

L.execute("mgr.m_pGameSaveData = makeSave({false, false, false}, { {SaveId=1, JoinStatus=0} }, 1000, 12.5, false)")
a = (WORK + "/a.tsv").replace("\\", "/")
b = (WORK + "/b.tsv").replace("\\", "/")
assert lua(f"snap('{a}')") is True, open(a).read()
text = open(a).read()
for line in ("save.Progress.Progress.#\t2", "save.Progress.Progress[0]\t1000", "save.Progress.eventFlag[2]\tfalse",
             "save.unitParameterList[0].SaveId\t1", "save.PlayTime\t12.5"):
    assert line in text, (line, text)
assert "ShouldNotAppear" not in text, "UObject's own properties are skipped"

L.execute("mgr.m_pGameSaveData = makeSave({false, true, true}, { {SaveId=1, JoinStatus=1}, {SaveId=2, JoinStatus=1} }, 1030, 99, true)")
assert lua(f"snap('{b}')") is True

tools = str(paths.TOOLS / "snapdiff.py")
out = subprocess.run([sys.executable, tools, a, b], capture_output=True, text=True, encoding="utf-8").stdout
print(out)
for want in ("save.Progress.eventFlag: on 1, 2", "save.Progress.Progress[0]: 1000 -> 1030",
             "save.unitParameterList[0].JoinStatus: 0 -> 1", "+ save.unitParameterList[1].SaveId = 2",
             "save.perMap{3001}.bIsVisited: false -> true"):
    assert want in out, (want, out)
assert "PlayTime" not in out, "noisy fields are left out"
assert "perMap{10040}" not in out, "unchanged map values stay out"

# address-only changes and Japanese keys
c = (WORK + "/c.tsv"); d = (WORK + "/d.tsv")
K = "初級_初級バトル１"
open(c, "w", encoding="utf-8").write("save.x{" + K + "}\tUScriptStruct: 000000024643F7B8\nsave.y\t1\n")
open(d, "w", encoding="utf-8").write("save.x{" + K + "}\tUScriptStruct: 00000001D35A32A8\nsave.y{初級}\t2\n")
out2 = subprocess.run([sys.executable, tools, c, d], capture_output=True, text=True, encoding="utf-8")
assert out2.returncode == 0, out2.stderr
assert "save.x" not in out2.stdout and "初級" in out2.stdout, out2.stdout
lines = []
assert lua("G.ListFunctions('Missing', print)") is None
n = L.eval("G.ListFunctions")("CPP_BFL_SaveDataParty", lambda line: lines.append(line))
assert n == 1 and lines == ["CPP_BFL_SaveDataParty.AddUnit(unitId: IntProperty, info: StructProperty<FSaveData_PerMap>, ReturnValue: BoolProperty)"], lines

# 0.7.2 probes: G.Inspect on a live object (class chain, functions, fields) and G.FindNames
L.execute(r"""
local vmFn = struct("ExecuteEntryEvent", { prop("entry", "StructProperty", { GetStruct = function() return perMapStruct end }) })
local baseClass = struct("CPP_VM_Base", { prop("bOpen", "BoolProperty") }, objectClass)
baseClass.ForEachFunction = function(self, fn) end
vmClass = struct("CPP_VM_Title", { prop("EntryCount", "IntProperty") }, baseClass)
vmClass.ForEachFunction = function(self, fn) fn(vmFn) end
vm = { EntryCount = 6, bOpen = true }
function vm:GetClass() return vmClass end
function vm:GetFullName() return "CPP_VM_Title /Engine/Transient.VM_1" end
function vm:IsValid() return true end
function vm:HasAnyInternalFlags() return false end
function vm:HasAnyFlags() return false end
local oldFindFirstOf = FindFirstOf
function FindFirstOf(c) if c == "CPP_VM_Title" then return vm end return oldFindFirstOf(c) end
local classClass = { GetFName = function() return { ToString = function() return "Class" end } end }
local function asClass(s, path)
  s.GetClass = function() return classClass end
  s.GetFullName = function() return "Class " .. path end
  s.HasAnyInternalFlags = function() return false end
  s.HasAnyFlags = function() return false end
  return s
end
local other = asClass(struct("CPP_OpeningTask", { prop("bIsOpeningProcess", "BoolProperty") }), "/Script/mucha.CPP_OpeningTask")
other.ForEachFunction = function(self, fn) fn(struct("OnOpening", {})) end
local engine = asClass(struct("Actor", { prop("Opening", "BoolProperty") }), "/Script/Engine.Actor")
engine.ForEachFunction = function() end
function ForEachUObject(fn) fn(vm) fn(other) fn(engine) end
""")
lines = []
assert L.eval("G.Inspect")("CPP_VM_Title", lambda k, v: lines.append(f"{k}\t{v}")) is True
text = "\n".join(lines)
print(text)
for want in ("object\tCPP_VM_Title /Engine/Transient.VM_1", "class\tCPP_VM_Title < CPP_VM_Base",
             "function\tCPP_VM_Title.ExecuteEntryEvent(entry: StructProperty<FSaveData_PerMap>)",
             "obj.EntryCount\t6", "obj.bOpen\ttrue"):
    assert want in text, (want, text)
assert L.eval("G.Inspect")("Nothing", lambda k, v: None) is False
found = []
n = L.eval("G.FindNames")("opening", lambda line: found.append(line))
assert n == 3 and found == ["class\tCPP_OpeningTask", "function\tCPP_OpeningTask.OnOpening",
                            "field\tCPP_OpeningTask.bIsOpeningProcess"], found
# 0.7.3: Blueprint classes under /Game count; dying objects are skipped
L.execute(r"""
local bpKind = { GetFName = function() return { ToString = function() return "BlueprintGeneratedClass" end } end }
local bp = struct("BP_Event_C", { prop("IsOpeningProcess", "BoolProperty") })
bp.GetClass = function() return bpKind end
bp.GetFullName = function() return "BlueprintGeneratedClass /Game/Event/BP_Event.BP_Event_C" end
bp.ForEachFunction = function() end
bp.HasAnyInternalFlags = function() return false end
bp.HasAnyFlags = function() return false end
local dying = struct("CPP_Dying", { prop("OpeningX", "BoolProperty") })
dying.HasAnyInternalFlags = function() return true end
dying.HasAnyFlags = function() return false end
dying.GetClass = function() error("crash: should not be asked") end
function ForEachUObject(fn) fn(bp) fn(dying) end
""")
found = []
n = L.eval("G.FindNames")("opening", lambda line: found.append(line))
assert found == ["field\tBP_Event_C.IsOpeningProcess"], found

# 0.7.3 / 0.8.1: the title menu's entry map: add, label, and order under New Game
L.execute(r"""
local function uarr(t)
  local a = { items = t }
  return setmetatable(a, {
    __len = function(self) return #rawget(self, "items") end,
    __index = function(self, k)
      local items = rawget(self, "items")
      if type(k) == "number" then if k == #items + 1 then items[k] = 0 end return items[k] end
    end,
    __newindex = function(self, k, v) rawget(self, "items")[k] = v end,
  })
end
local function ftext(t) return { s = t, ToString = function(self) return self.s end } end
function FText(t) return ftext(t) end
function FName(t) return { s = t, ToString = function(self) return self.s end } end
local function row(name, checkSave, action, platforms)
  return { EntryName = ftext(name),
           DisplayProperty = { bCheckSaveData = checkSave, bCheckPlatform = #platforms > 0, DisplayPlatformMap = uarr(platforms) },
           SystemActionTag = { TagName = FName(action) } }
end
local function copy(r) return row(r.EntryName:ToString(), r.DisplayProperty.bCheckSaveData,
    r.SystemActionTag.TagName:ToString(), (function() local t = {} for i = 1, #r.DisplayProperty.DisplayPlatformMap do t[i] = r.DisplayProperty.DisplayPlatformMap[i] end return t end)()) end
function tmap(pairsList, noEmpty)
  local m = { list = pairsList }
  function m:ForEach(fn) for _, kv in ipairs(self.list) do
    fn({ get = function() return kv[1] end }, { get = function() return kv[2] end }) end end
  function m:Add(k, v)
    -- like the engine: the value is copied in; an empty table makes a zeroed row
    local stored = (v.EntryName and copy(v)) or row("", false, "None", {})
    self.list[#self.list + 1] = { k, stored }
  end
  function m:Remove(k) for i, kv in ipairs(self.list) do if kv[1] == k then table.remove(self.list, i) return end end end
  if not noEmpty then function m:Empty() self.list = {} end end
  return m
end
function titleRows()
  return { {0, row("Continue", true, "None", {})}, {1, row("Load Game", true, "System.Action.Declare.Load", {})},
           {2, row("New Game", false, "None", {})}, {3, row("Options", false, "System.Action.Declare.Option", {})},
           {4, row("Quit Game", false, "System.Action.Declare.QuitGame.Title", {1})} }
end
titleDA = { EntryPropertyMap = tmap(titleRows()) }
function titleDA:IsValid() return true end
local oldSFO = StaticFindObject
function StaticFindObject(p) if p == "/Game/UI/Title/Data/DA_Title.DA_Title" then return titleDA end return oldSFO(p) end
function keysOf() local t = {} for _, kv in ipairs(titleDA.EntryPropertyMap.list) do t[#t + 1] = kv[1] end return table.concat(t, ",") end
function rowOf(k) for _, kv in ipairs(titleDA.EntryPropertyMap.list) do if kv[1] == k then return kv[2] end end end
""")
ok, detail = L.execute("return G.AddTitleEntry()")
assert ok is True and detail == "copied from the New Game row", detail
assert L.eval("rowOf(5).EntryName:ToString()") == "New Game (Archipelago)"
assert L.eval("rowOf(2).EntryName:ToString()") == "New Game", "the copy, not the original, is relabelled"
ok, detail = L.execute("return G.AddTitleEntry()")
assert ok is True and detail == "already there", detail
assert "map keys [0,1,2,3,4,5]" in L.eval("G.TitleEntries()"), L.eval("G.TitleEntries()")
ok, detail = L.execute("return G.OrderTitleEntries()")
assert ok is True and detail == "rebuilt as [0,1,2,5,3,4]", detail
assert L.eval("keysOf()") == "0,1,2,5,3,4"
for k, name, save, action, plats in ((0, "Continue", True, "None", 0), (1, "Load Game", True, "System.Action.Declare.Load", 0),
                                     (2, "New Game", False, "None", 0), (5, "New Game (Archipelago)", False, "None", 0),
                                     (3, "Options", False, "System.Action.Declare.Option", 0),
                                     (4, "Quit Game", False, "System.Action.Declare.QuitGame.Title", 1)):
    assert L.eval(f"rowOf({k}).EntryName:ToString()") == name, (k, L.eval(f"rowOf({k}).EntryName:ToString()"))
    assert L.eval(f"rowOf({k}).DisplayProperty.bCheckSaveData") is save, k
    assert L.eval(f"rowOf({k}).SystemActionTag.TagName:ToString()") == action, k
    assert L.eval(f"#rowOf({k}).DisplayProperty.DisplayPlatformMap") == plats, k
assert L.eval("rowOf(4).DisplayProperty.DisplayPlatformMap[1]") == 1 and L.eval("rowOf(4).DisplayProperty.bCheckPlatform") is True
ok, detail = L.execute("return G.OrderTitleEntries()")
assert ok is True and detail == "already in order", detail
# Round 37: a label read while its string table is still loading is left in place: the rebuild
# would write the placeholder as plain text. The order waits for the next check.
L.execute("titleDA.EntryPropertyMap = tmap(titleRows()); G.AddTitleEntry()")
L.execute("rowOf(3).EntryName = FText('<MISSING STRING TABLE ENTRY>')")
ok, detail = L.execute("return G.OrderTitleEntries()")
assert ok is False and detail == "row 3 has no text yet (string table not loaded), so the order waits", detail
assert L.eval("keysOf()") == "0,1,2,3,4,5", "the map is untouched"
L.execute("rowOf(3).EntryName = FText('Options')")
ok, detail = L.execute("return G.OrderTitleEntries()")
assert ok is True and detail == "rebuilt as [0,1,2,5,3,4]", detail
assert L.eval("rowOf(3).EntryName:ToString()") == "Options"
# a map that cannot be emptied: the order is left alone and the spare row taken out again
L.execute("titleDA.EntryPropertyMap = tmap(titleRows(), true)")
L.execute("G.AddTitleEntry()")
ok, detail = L.execute("return G.OrderTitleEntries()")
assert ok is False and "left alone" in detail, detail
assert L.eval("keysOf()") == "0,1,2,3,4,5", L.eval("keysOf()")

# 0.8.1: the mod's name above the game's version text
L.execute(r"""
local function tb(text) local t = { text = text }
  function t:GetText() local me = self return { ToString = function() return me.text end } end
  function t:SetText(f) self.text = f:ToString() end
  function t:SetJustification(j) self.justify = j end
  function t:IsValid() return true end
  function t:HasAnyInternalFlags() return false end
  function t:HasAnyFlags() return false end
  return t end
blocks = { tb("Continue"), tb("1.0.1.0"), tb("© SQUARE ENIX") }
local oldFAO = FindAllOf
function FindAllOf(c) if c == "TextBlock" then return blocks end return oldFAO(c) end
""")
assert L.eval('(G.TitleVersionLine("FFRArchipelago 0.8.1"))') == "added"
assert L.eval("blocks[2].text") == "FFRArchipelago 0.8.1\n1.0.1.0", L.eval("blocks[2].text")
assert L.eval("blocks[2].justify") == 0, "left-justified"
L.execute("blocks[2].justify = 2")
assert L.eval('(G.TitleVersionLine("FFRArchipelago 0.8.1"))') == "already"
assert L.eval("blocks[2].justify") == 0, "kept left-justified"
# Round 120: the entry's label on screen follows the client while the title stays up
L.execute("blocks[1].text = G.TITLE_LABEL_NO_CLIENT")
assert L.eval("G.RefreshTitleLabel(G.TITLE_LABEL_LIVE)") == 1 and L.eval("blocks[1].text") == "New Game (Archipelago)"
assert L.eval("G.RefreshTitleLabel(G.TITLE_LABEL_LIVE)") == 0, "once"
assert L.eval("G.RefreshTitleLabel(G.TITLE_LABEL_NO_CLIENT)") == 1 and L.eval("blocks[1].text") == L.eval("G.TITLE_LABEL_NO_CLIENT")
assert L.eval("blocks[3].text") == "© SQUARE ENIX", "other text is left alone"
L.execute("blocks[1].text = 'Continue'")
# its layout, for the logo
L.execute(r"""
local function w(cls, name) local o = { cls = cls, name = name }
  function o:GetClass() local me = self return { GetFName = function() return { ToString = function() return me.cls end } end } end
  function o:GetFName() local me = self return { ToString = function() return me.name end } end
  function o:IsValid() return true end
  function o:HasAnyInternalFlags() return false end
  function o:HasAnyFlags() return false end
  return o end
local panel = w("VerticalBox", "Box_Copyright")
local kids = { blocks[2], w("TextBlock", "Text_Copyright"), w("TextBlock", "Text_Logo") }
blocks[2].GetClass = function() return { GetFName = function() return { ToString = function() return "TextBlock" end } end } end
blocks[2].GetFName = function() return { ToString = function() return "Text_Version" end } end
blocks[2].Slot = w("VerticalBoxSlot", "slot")
blocks[2].GetParent = function() return panel end
function panel:GetChildrenCount() return #kids end
function panel:GetChildAt(i) return kids[i + 1] end
function panel:GetParent() return w("CanvasPanel", "Root") end
blocks[2].GetOuter = function() return { GetOuter = function() return w("WBP_Title_C", "WBP_Title") end } end
""")
desc = L.eval("G.DescribeWidget(blocks[2])")
assert desc == ("widget TextBlock Text_Version; slot VerticalBoxSlot; parent VerticalBox Box_Copyright; "
                "children [TextBlock Text_Version, TextBlock Text_Copyright, TextBlock Text_Logo]; "
                "grandparent CanvasPanel Root; in WBP_Title_C"), desc
# 0.8.3: the logo above the version line, in the version text's overlay
L.execute(r"""
local tree = { name = "WidgetTree" }
blocks[2].GetOuter = function() return tree end
blocks[2].Slot.HorizontalAlignment = 1
blocks[2].Slot.VerticalAlignment = 3
blocks[2].Slot.Padding = { Left = 40, Top = 0, Right = 0, Bottom = 60 }
blocks[2].GetDesiredSize = function() return { X = 150, Y = 36 } end
local panel = blocks[2]:GetParent()
local kids = { blocks[2] }
function panel:GetChildrenCount() return #kids end
function panel:GetChildAt(i) return kids[i + 1] end
function panel:AddChildToOverlay(img)
  kids[#kids + 1] = img
  local slot = {}
  function slot:SetHorizontalAlignment(a) self.h = a end
  function slot:SetVerticalAlignment(a) self.v = a end
  function slot:SetPadding(m) self.pad = m end
  img.slot = slot
  return slot
end
texture = { IsValid = function() return true end }
loaded = nil
krl = { ImportFileAsTexture2D = function(_, ctx, path) loaded = path return texture end }
krl.IsValid = function() return true end
imageClass = { IsValid = function() return true end }
local oldSFO2 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/Engine.Default__KismetRenderingLibrary" then return krl end
  if p == "/Script/UMG.Image" then return imageClass end
  return oldSFO2(p)
end
made = {}
function StaticConstructObject(cls, outer, name)
  local img = { cls = cls, outer = outer, nm = name:ToString() }
  function img:IsValid() return true end
  function img:GetFName() local me = self return { ToString = function() return me.nm end } end
  function img:SetBrushFromTexture(t, match) self.tex = t end
  function img:SetDesiredSizeOverride(sz) self.size = sz end
  made[#made + 1] = img
  return img
end
""")
result, detail = L.execute('return G.TitleLogo("C:/Mods/FFRArchipelago/Assets/archipelago_logo.png", "FFRArchipelago 0.8.1")')
assert result == "added", (result, detail)
assert detail == "20x21 at left 198.0, bottom 76.5 (text 150.0x36.0, 2 lines; alignment 1/3)", detail
assert L.eval("loaded") == "C:/Mods/FFRArchipelago/Assets/archipelago_logo.png"
assert L.eval("made[1].nm") == "FFRAP_Logo_1" and L.eval("made[1].tex == texture") is True
assert L.eval("made[1].size.Y") == 21 and L.eval("made[1].size.X") == 20
assert L.eval("made[1].slot.h") == 1 and L.eval("made[1].slot.v") == 3
assert L.eval("made[1].slot.pad.Bottom") == 76.5 and L.eval("made[1].slot.pad.Left") == 198
result, detail = L.execute('return G.TitleLogo("C:/x.png", "FFRArchipelago 0.8.1")')
assert result == "already" and detail == "FFRAP_Logo_1", (result, detail)
assert L.eval("#made") == 1
result, detail = L.execute('return G.TitleLogo("C:/x.png", "FFRArchipelago 9.9.9")')
assert result is None and "not on screen" in detail, detail

# 0.8.4: the chain of panels holding some on-screen text
chain = L.execute('return G.LayoutOf("FFRArchipelago")')
lines = list(chain.values())
assert lines[0].startswith("widget TextBlock Text_Version; slot VerticalBoxSlot"), lines
assert lines[1].startswith("widget VerticalBox Box_Copyright"), lines
assert L.execute('return G.LayoutOf("no such text")') is None
# 0.10.1: text with icons is a RichTextBlock, which is searched too
L.execute(r"""
rich = { text = "You obtained the following:" }
function rich:GetText() local me = self return { ToString = function() return me.text end } end
function rich:IsValid() return true end
function rich:HasAnyInternalFlags() return false end
function rich:HasAnyFlags() return false end
function rich:GetClass() return { GetFName = function() return { ToString = function() return "RichTextBlock" end } end } end
function rich:GetFName() return { ToString = function() return "Text_Message" end } end
local oldFAO4 = FindAllOf
function FindAllOf(c) if c == "RichTextBlock" then return { rich } end return oldFAO4(c) end
""")
chain = L.execute('return G.LayoutOf("obtained")')
assert chain is not None and list(chain.values())[0].startswith("widget RichTextBlock Text_Message"), chain
# 0.11.0: the chest pop-up says what the chest held, the item line is hidden, then restored
L.execute(r"""
rich.shown = true
function rich:IsVisible() return self.shown end
function rich:SetText(f) self.text = f:ToString() end
local itemLine = { name = "Overlay_Custom", vis = 0 }
function itemLine:GetFName() local me = self return { ToString = function() return me.name end } end
function itemLine:IsValid() return true end
function itemLine:HasAnyInternalFlags() return false end
function itemLine:HasAnyFlags() return false end
function itemLine:GetVisibility() return self.vis end
function itemLine:SetVisibility(v) self.vis = v end
popupLine = itemLine
local box = { kids = { rich, itemLine } }
function box:GetChildrenCount() return #self.kids end
function box:GetChildAt(i) return self.kids[i + 1] end
rich.GetParent = function() return box end
""")
ok, detail = L.execute('return G.ChestPopup("You found the following for Alice:\\nHookshot")')
assert ok is True and detail == "text set, item line hidden", detail
assert L.eval("rich.text") == "You found the following for Alice:\nHookshot"
assert L.eval("popupLine.vis") == 1, "collapsed"
L.execute("G.ChestPopupRestore()")
assert L.eval("popupLine.vis") == 1, "still collapsed while the pop-up is up"
L.execute("rich.shown = false")
L.execute("G.ChestPopupRestore()")
assert L.eval("popupLine.vis") == 0, "visible again once the pop-up is gone"
ok, detail = L.execute('return G.ChestPopup("x")')
assert ok is False and detail == "no chest pop-up on screen", detail
# Round 78: a character quest's stat bonus said "obtained" in a dialog with no item line. It is
# left alone, so the item pop-up after it still gets the text.
L.execute('rich.text = "Rain obtained an attribute bonus"; rich.shown = true; box_kids = rich:GetParent().kids; '
          'table.remove(box_kids, 2)')
ok, detail = L.execute('return G.ChestPopup("You found:\\nHookshot")')
assert ok is False and "no item line" in detail, detail
assert L.eval("rich.text") == "Rain obtained an attribute bonus"
L.execute('box_kids[2] = popupLine; rich.text = "You obtained the following:\\nPotion"')
ok, detail = L.execute('return G.ChestPopup("You found:\\nHookshot")')
assert ok is True and detail == "text set, item line hidden", detail
L.execute('rich.shown = false; G.ChestPopupRestore(); rich.text = "x"')
# 0.11.1: PopupJustOpened, from the cached message widget: true once per pop-up
assert L.eval("G.PopupJustOpened()") is False, "closed (the fast check sees it closed between pop-ups)"
L.execute('rich.text = "You obtained the following:"; rich.shown = true')
assert L.eval("G.PopupJustOpened()") is True
assert L.eval("G.PopupJustOpened()") is False, "once per pop-up"
L.execute("rich.shown = false")
assert L.eval("G.PopupJustOpened()") is False
L.execute("rich.shown = true")
assert L.eval("G.PopupJustOpened()") is True, "the next pop-up"
ok, detail = L.execute('return G.ChestPopup("You obtained the following:\\nTent")')
assert ok is True
assert L.eval("G.PopupJustOpened()") is False, "a rewritten pop-up is not a new one"
L.execute('rich.shown = false; rich.text = "Quit the game?"')
assert L.eval("G.PopupJustOpened()") is False
L.execute("rich.shown = true")
assert L.eval("G.PopupJustOpened()") is False, "another dialog in the same box is not a chest pop-up"
# Round 60: a map load forgets the widget. It is found again by name before any pop-up is shown,
# so the first pop-up on the new map is seen by the fast check too.
L.execute('G.ForgetObjects(); rich.shown = false; rich.text = "You obtained the following:"')
assert L.eval("G.PopupJustOpened()") is False, "forgotten"
assert L.eval("G.PrimePopup()") == 1
L.execute('rich.shown = true; rich.text = "Quit the game?"')
assert L.eval("G.PopupJustOpened()") is False, "the dialog box with another message"
L.execute('rich.shown = false')
L.eval("G.PopupJustOpened()")
L.execute('rich.shown = true; rich.text = "You obtained the following:"')
assert L.eval("G.PopupJustOpened()") is True, "the first pop-up after a map load"
assert L.eval("G.PopupJustOpened()") is False, "once"

# 0.9.0: the item feed on the field HUD
L.execute(r"""
local function w(cls, name) local o = { cls = cls, name = name, kids = {} }
  function o:GetClass() local me = self return { GetFName = function() return { ToString = function() return me.cls end } end } end
  function o:GetFName() local me = self return { ToString = function() return me.name end } end
  function o:GetFullName() return self.cls .. " " .. self.name end
  function o:IsValid() return not self.dead end
  function o:HasAnyInternalFlags() return false end
  function o:HasAnyFlags() return false end
  return o end
hudTree = { name = "FieldTree" }
hud = w("Overlay", "Overlay_66")
function hud:AddChildToOverlay(c)
  self.kids[#self.kids + 1] = c
  local slot = {}
  function slot:SetHorizontalAlignment(a) self.h = a end
  function slot:SetVerticalAlignment(a) self.v = a end
  function slot:SetPadding(m) self.pad = m end
  c.slot = slot
  c.parent = self
  return slot
end
funcList = w("WBP_FieldFuncList2_C", "WBP_FieldFuncList2")
function funcList:GetParent() return hud end
function funcList:GetOuter() return hudTree end
guide = w("WBP_KeyGuide_C", "WBP_KeyGuide")
gameFont = { name = "GameFont" }
function gameFont:IsValid() return true end
function gameFont:GetFullName() return "Font /Game/UI/Font/GameFont.GameFont" end
function gameFont:GetFName() return { ToString = function() return "GameFont" end } end
guide.Text_Name = { Font = { Size = 26, FontObject = gameFont, TypefaceFontName = "Regular" } }
local vbClass, tbClass = { IsValid = function() return true end }, { IsValid = function() return true end }
local oldSFO3 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/UMG.VerticalBox" then return vbClass end
  if p == "/Script/UMG.TextBlock" then return tbClass end
  return oldSFO3(p)
end
local oldSCO = StaticConstructObject
function StaticConstructObject(cls, outer, name)
  if cls == vbClass then
    local box = w("VerticalBox", name:ToString())
    box.outer = outer
    function box:AddChildToVerticalBox(tb)
      self.kids[#self.kids + 1] = tb
      tb.parent = self
      local slot = {}
      function slot:SetHorizontalAlignment(a) self.h = a end
      function slot:SetPadding(m) self.pad = m end
      tb.slot = slot
      return slot
    end
    return box
  end
  if cls == tbClass then
    local tb = w("TextBlock", name:ToString())
    tb.Font = { Size = 24, FontObject = "Roboto", TypefaceFontName = "Default" }
    tb.ShadowColorAndOpacity = { R = 0, G = 0, B = 0, A = 0 }
    tb.Justification = 0
    function tb:SetText(f) self.text = f:ToString() end
    -- round 20: passing a font struct crashed the game; these must not be called any more
    local function crash() error("CRASH: a struct-taking setter was called") end
    tb.SetFont, tb.SetColorAndOpacity, tb.SetShadowOffset, tb.SetShadowColorAndOpacity, tb.SetJustification =
      crash, crash, crash, crash, crash
    function tb:SetRenderOpacity(a) self.opacity = a end
    function tb:RemoveFromParent()
      local p = self.parent
      for i, k in ipairs(p.kids) do if k == self then table.remove(p.kids, i) break end end
      self.parent = nil
    end
    return tb
  end
  return oldSCO(cls, outer, name)
end
local oldFFO2 = FindFirstOf
function FindFirstOf(c)
  if c == "WBP_FieldFuncList2_C" then return hudOn and funcList or nil end
  if c == "WBP_KeyGuide_C" then return guide end
  return oldFFO2(c)
end
hudOn = false
-- round 22: FindFirstOf found a template copy that is never drawn; the on-screen one comes second
function hud:IsVisible() return true end
function funcList:IsVisible() return true end
function guide:IsVisible() return true end
templateHud = w("Overlay", "Overlay_66_template")
function templateHud:IsVisible() return false end
templateList = w("WBP_FieldFuncList2_C", "WBP_FieldFuncList2_template")
function templateList:IsVisible() return false end
function templateList:GetParent() return templateHud end
function templateList:GetOuter() return { name = "TemplateTree" } end
templateGuide = w("WBP_KeyGuide_C", "WBP_KeyGuide_template")
function templateGuide:IsVisible() return false end
templateGuide.Text_Name = { Font = { Size = 26, FontObject = nil, TypefaceFontName = "None" } }
local oldFAO2 = FindAllOf
function FindAllOf(c)
  if c == "WBP_FieldFuncList2_C" then return hudOn and { templateList, funcList } or { templateList } end
  if c == "WBP_KeyGuide_C" then return { templateGuide, guide } end
  return oldFAO2(c)
end
""")
ok, why = L.execute('return G.FeedLine("Received Potion", 0)')
assert ok is False and why == "no field HUD on screen", why
assert L.eval("#templateHud.kids") == 0, "nothing goes into the template"
L.execute("hudOn = true")
for i, msg in enumerate(["Received Potion from Bob", "Sent Ether to Alice"]):
    ok = L.execute(f'return G.FeedLine("{msg}", {i})')
    assert ok is True, ok
assert L.eval("#hud.kids") == 1, "one box"
# Round 120: inside one loop run the field HUD is looked for once; outside the runs, each time
L.execute(r"""
hudSearches = 0
local oldFAO3 = FindAllOf
function FindAllOf(c) if c == "WBP_FieldFuncList2_C" then hudSearches = hudSearches + 1 end return oldFAO3(c) end
""")
L.execute("G.BeginRun()")
assert L.eval("G.OnField()") is True and L.eval("G.OnField()") is True
L.execute("hudOn = false")
assert L.eval("G.OnField()") is True, "kept for the rest of the run"
L.execute("G.EndRun()")
assert L.eval("hudSearches") == 1, L.eval("hudSearches")
assert L.eval("G.OnField()") is False and L.eval("hudSearches") == 2
L.execute("hudOn = true")
assert L.eval("hud.kids[1].slot.h") == 3 and L.eval("hud.kids[1].slot.v") == 3, "right is 3 (round 21)"
assert L.eval("hud.kids[1].slot.pad.Right") == 48 and L.eval("hud.kids[1].slot.pad.Bottom") == 140
assert L.eval("hud.kids[1].outer == hudTree") is True
box = "hud.kids[1]"
assert L.eval(f"#{box}.kids") == 2 and L.eval(f"{box}.kids[2].text") == "Sent Ether to Alice"
assert L.eval(f"{box}.kids[1].Font.FontObject.name") == "GameFont" and L.eval(f"{box}.kids[1].Font.TypefaceFontName") == "Regular"
assert L.eval(f"{box}.kids[1].Font.Size") == 20
assert L.eval(f"{box}.kids[1].Justification") == 2 and L.eval(f"{box}.kids[1].slot.h") == 3
assert L.eval(f"{box}.kids[1].ShadowColorAndOpacity.A") == 0.85
assert L.eval(f"{box}.kids[1].slot.pad.Bottom") == 6, "space under each line (round 23)"
assert L.eval("guide.Text_Name.Font.Size") == 26 and L.eval("guide.Text_Name.Font.FontObject.name") == "GameFont", "the key guide's own font is left alone"
# a key guide with no font object of its own: the line keeps its default font
L.execute("guide.Text_Name.Font.FontObject = nil")
L.execute('G.FeedLine("default font", 1)')
assert L.eval(f"{box}.kids[#{box}.kids].Font.FontObject") == "Roboto", L.eval(f"{box}.kids[#{box}.kids].Font.FontObject")
L.execute("guide.Text_Name.Font.FontObject = gameFont")
# the report
L.execute("""
function hud:GetDesiredSize() return { X = 1600, Y = 900 } end
function hud:GetVisibility() return 0 end
function hud:IsVisible() return true end
""")
L.execute("""for _, k in ipairs(hud.kids[1].kids) do
  k.GetDesiredSize = function() return { X = 200, Y = 24 } end
  k.GetVisibility = function() return 4 end
  k.IsVisible = function() return true end
  k.GetRenderOpacity = function() return 1.0 end
end
hud.kids[1].GetParent = function() return hud end
hud.kids[1].Slot = { HorizontalAlignment = 3, VerticalAlignment = 3 }
hud.kids[1].GetDesiredSize = function() return { X = 200, Y = 120 } end
hud.kids[1].GetVisibility = function() return 4 end
hud.kids[1].IsVisible = function() return true end""")
report = list(L.eval("G.FeedReport()").values())
print("\n".join(report))
assert report[0] == "key lists (WBP_FieldFuncList2_C): 2, on screen 1", report[0]
assert report[1] == "HUD overlay: 1600x900, visibility 0, visible true", report[1]
assert report[2] == "box: 200x120, visibility 4, visible true, in Overlay_66, alignment 3/3", report[2]
assert report[3].startswith('line 1: "') and "200x24" in report[3] and "font GameFont size 20" in report[3], report[3]
# 0.9.1: each step is announced before it runs; plain leaves out the styling
L.execute("trace = {}; G.feedTrace = function(w) trace[#trace + 1] = w end")
L.execute('G.FeedLine("traced", 1)')
steps = list(L.eval("trace").values())
assert steps[0] == "make a line (StaticConstructObject TextBlock)" and any(x.startswith("style: font object and typeface (field writes): ") for x in steps) and steps[-1] == "line done", steps
L.execute("trace = {}")
L.execute('G.FeedLine("traced plain", 1, { plain = true })')
steps = list(L.eval("trace").values())
assert not any(s.startswith("style:") for s in steps) and steps[-1] == "line done", steps
L.execute("G.feedTrace = nil")
for i in range(3):
    L.execute(f'G.FeedLine("filler {i}", 1)')
# five at most
for i in range(5):
    L.execute(f'G.FeedLine("line {i}", 2)')
assert L.eval(f"#{box}.kids") == 5 and L.eval(f"{box}.kids[1].text") == "line 0", L.eval(f"{box}.kids[1].text")
# fading: shown 6 s, then fades over 1.5 s, then gone
assert L.eval("G.FeedTick(7.0)") == 5 and L.eval("G.FEED_SHOW") == 10.0 and L.eval("G.FEED_FADE") == 2.0
assert L.eval(f"{box}.kids[1].opacity") is None, "not fading before 6 s"
L.execute("G.FeedTick(13.0)")
assert abs(L.eval(f"{box}.kids[1].opacity") - (1 - 1.0 / 2.0)) < 1e-9
assert L.eval("G.FeedTick(14.1)") == 0 and L.eval(f"#{box}.kids") == 0
# a new HUD (a map change): a new box in the new overlay
L.execute('hud2 = hud; hud = setmetatable({ kids = {}, name = "Overlay_66b" }, { __index = hud2 }); function hud:GetFullName() return "Overlay Overlay_66b" end')
L.execute('funcList.GetParent = function() return hud end')
L.execute('function hud:IsVisible() return true end')
assert L.execute('return G.FeedLine("after the map change", 10)') is True
assert L.eval("#hud.kids") == 1 and L.eval("hud.kids[1].kids[1].text") == "after the map change"
# Round 89 (the user): the item's name in its Archipelago colour, by its flags (1 progression,
# 2 useful, 4 trap, else filler), and in bold (round 90). On by default since round 91; off, one
# TextBlock as before.
assert [L.eval(f"G.ItemClass({f})") for f in (0, 1, 2, 3, 4, 6)] == \
    ["filler", "progression", "useful", "progression", "trap", "useful"]
L.execute(r"""
local hbClass = { IsValid = function() return true end }
local oldSFO4 = StaticFindObject
function StaticFindObject(p) if p == "/Script/UMG.HorizontalBox" then return hbClass end return oldSFO4(p) end
local oldSCO4 = StaticConstructObject
function StaticConstructObject(cls, outer, name)
  if cls == hbClass then
    local row = { cls = "HorizontalBox", name = name:ToString(), kids = {} }
    function row:IsValid() return true end
    function row:HasAnyInternalFlags() return false end
    function row:HasAnyFlags() return false end
    function row:GetFullName() return "HorizontalBox " .. self.name end
    function row:AddChildToHorizontalBox(tb) self.kids[#self.kids + 1] = tb; tb.parent = self; return {} end
    function row:SetRenderOpacity(a) self.opacity = a end
    function row:RemoveFromParent()
      local p = self.parent
      for i, k in ipairs(p.kids) do if k == self then table.remove(p.kids, i) break end end
    end
    return row
  end
  local made = oldSCO4(cls, outer, name)
  if made and made.Font then made.ColorAndOpacity = { SpecifiedColor = { R = 1, G = 1, B = 1, A = 1 } } end
  return made
end
""")
HOOKSHOT_SPAN = '{ span = { text = "Hookshot", flags = 1 } }'
assert L.eval("G.feedColors") is True
L.execute("G.feedColors = false")
L.execute(f'G.FeedLine("Received Hookshot from Alice", 11, {HOOKSHOT_SPAN})')
last = "hud.kids[1].kids[#hud.kids[1].kids]"
assert L.eval(f"{last}.text") == "Received Hookshot from Alice", "colours off: one TextBlock"
L.execute("G.feedColors = true")
L.execute(f'G.FeedLine("Received Hookshot from Alice", 12, {HOOKSHOT_SPAN})')
assert L.eval(f"{last}.cls") == "HorizontalBox", L.eval(f"{last}.cls")
assert [L.eval(f"{last}.kids[{i}].text") for i in (1, 2, 3)] == ["Received ", "Hookshot", " from Alice"]
PLUM_R, CYAN_R = 0.429, 0.0
assert L.eval(f"{last}.kids[2].ColorAndOpacity.SpecifiedColor.R") == PLUM_R, "progression: plum"
assert L.eval(f"{last}.kids[1].ColorAndOpacity.SpecifiedColor.R") == 1, "the rest stays white"
assert L.eval(f"{last}.kids[2].Font.Size") == 20, "each piece styled as a line is"
assert L.eval(f"{last}.kids[2].Font.TypefaceFontName:ToString()") == "Bold", "the name in bold (round 90)"
assert L.eval(f"{last}.kids[1].Font.TypefaceFontName") == "Regular", "the rest keeps the key guide's typeface"
L.execute('G.FeedLine("Received Potion", 13, { span = { text = "Potion", flags = 0 } })')
assert L.eval(f"#{last}.kids") == 2 and L.eval(f"{last}.kids[2].ColorAndOpacity.SpecifiedColor.R") == CYAN_R, \
    "nothing after the name: two pieces; filler: cyan"
L.execute('G.FeedLine("Received 3 items", 14, { span = { text = "Potion", flags = 0 } })')
assert L.eval(f"{last}.text") == "Received 3 items", "a span not in the text: one TextBlock"
L.execute("G.FeedTick(30.0)")
# Round 91 probe: the pop-up's message keeps the lines without the name; the name's line goes into
# our own coloured row
SPLIT = 'G.PopupSplit("You found Alice\'s:\\nHookshot", { text = "Hookshot", flags = 1 })'
assert L.eval("G.POPUP_COLORS.on") is True, "on by default since round 92"
L.execute("G.POPUP_COLORS.on = false")
assert L.eval(SPLIT) is None, "off: the message stays as it is"
L.execute("G.POPUP_COLORS.on = true")
assert L.eval(f"(select(1, {SPLIT}))") == "You found Alice's:"
assert L.eval(f"(select(2, {SPLIT}))[1].line") == "Hookshot" and L.eval(f"(select(2, {SPLIT}))[1].span.flags") == 1
# Round 98: a quest's two rewards, one line each, each with its own span
SPLIT_TWO = 'G.PopupSplit("You found:\\nPotion\\nAlice\'s Hookshot", { { text = "Potion", flags = 0 }, { text = "Hookshot", flags = 1 } })'
assert L.eval(f"(select(1, {SPLIT_TWO}))") == "You found:"
assert L.eval(f"#(select(2, {SPLIT_TWO}))") == 2
assert L.eval(f"(select(2, {SPLIT_TWO}))[2].line") == "Alice's Hookshot" and L.eval(f"(select(2, {SPLIT_TWO}))[2].span.text") == "Hookshot"
assert L.eval('G.PopupSplit("You found:\\nPotion", { text = "Ether", flags = 0 })') is None, "a span not in the text"
L.execute("G.POPUP_COLORS.on = false")
# Round 91 probe: with colours on, the pop-up's name line becomes our own row under the message,
# centred and styled as the message's text; it goes when the pop-up closes
L.execute(r"""
local box = rich:GetParent()
box.kids = { rich, popupLine }
function box:AddChildToVerticalBox(w)
  self.kids[#self.kids + 1] = w; w.parent = self
  local slot = {}
  function slot:SetHorizontalAlignment(a) self.h = a end
  function slot:SetPadding(m) self.pad = m end
  w.slot = slot
  return slot
end
rich.GetOuter = function() return hudTree end
rich.text, rich.shown, popupLine.vis = "You obtained the following:", true, 0
G.POPUP_COLORS.on = true
""")
ok, detail = L.execute('return G.ChestPopup("You found Alice\'s:\\nHookshot", { text = "Hookshot", flags = 1 })')
assert ok is True and detail == "text set, item line hidden, the name in its colour", detail
assert L.eval("rich.text") == "You found Alice's:"
popupRow = "rich:GetParent().kids[3]"
assert L.eval(f"{popupRow}.cls") == "HorizontalBox" and L.eval(f"{popupRow}.slot.h") == 2, "centred under the message"
assert L.eval(f"{popupRow}.kids[1].text") == "Hookshot" and L.eval(f"{popupRow}.kids[1].ColorAndOpacity.SpecifiedColor.R") == PLUM_R
MESSAGE_SIZE, MESSAGE_SPACING = 18, 4
assert L.eval(f"{popupRow}.kids[1].Font.Size") == MESSAGE_SIZE and L.eval(f"{popupRow}.kids[1].Font.LetterSpacing") == MESSAGE_SPACING
L.execute("G.ChestPopupRestore()")
assert L.eval("#rich:GetParent().kids") == 3, "kept while the pop-up is up"
L.execute("rich.shown = false; G.ChestPopupRestore()")
assert L.eval("#rich:GetParent().kids") == 2 and L.eval("popupLine.vis") == 0, "gone with the pop-up; the item line back"
# Round 98: two rewards, two coloured rows, both gone with the pop-up
L.execute('rich.text, rich.shown, popupLine.vis = "You obtained the following:", true, 0')
ok, detail = L.execute('return G.ChestPopup("You found:\\nPotion\\nAlice\'s Hookshot", { { text = "Potion", flags = 0 }, { text = "Hookshot", flags = 1 } })')
assert ok is True and detail == "text set, item line hidden, the names in their colours", detail
assert L.eval("rich.text") == "You found:" and L.eval("#rich:GetParent().kids") == 4
assert L.eval("rich:GetParent().kids[3].kids[1].ColorAndOpacity.SpecifiedColor.R") == CYAN_R
assert L.eval("rich:GetParent().kids[4].kids[2].ColorAndOpacity.SpecifiedColor.R") == PLUM_R
# Round 106 (the user): the two names touched. The second row has space above it.
POPUP_NAME_GAP = 10
assert L.eval("rich:GetParent().kids[3].slot.pad") is None, "no space above the first name"
assert L.eval("rich:GetParent().kids[4].slot.pad.Top") == POPUP_NAME_GAP
L.execute("rich.shown = false; G.ChestPopupRestore()")
assert L.eval("#rich:GetParent().kids") == 2, "both rows gone with the pop-up"
# Round 99: a quest's stat bonus and "You can now summon..." came next in the same open dialog,
# with our names still under them. The rows go when the message changes; the item line stays
# hidden until the dialog closes.
L.execute('rich.text, rich.shown, popupLine.vis = "You obtained the following:", true, 0')
ok, detail = L.execute('return G.ChestPopup("You found Alice\'s:\\nHookshot", { text = "Hookshot", flags = 1 })')
assert ok is True and L.eval("#rich:GetParent().kids") == 3, detail
L.execute('rich.text = "Nichol obtained an attribute bonus"; G.ChestPopupRestore()')
assert L.eval("#rich:GetParent().kids") == 2, "our row gone under the game's next message"
assert L.eval("popupLine.vis") == 1, "the item line still hidden while the dialog is open"
L.execute("rich.shown = false; G.ChestPopupRestore()")
assert L.eval("popupLine.vis") == 0, "the item line back once it closes"
L.execute("G.POPUP_COLORS.on = false")
# Round 93: a Quests screen Rewards text showing a scouted item is replaced by our row. The blocks
# are found as CommonTextBlocks in a reward line (round 92: walking down from the line found none).
# In a one-child slot (the entry panel's named slot) the row takes the block's place; in a panel
# it goes beside the hidden block. A line the list reuses for another reward gets its own back.
L.execute(r"""
local function widget(cls, name)
  local p = { cls = cls, name = name, kids = {} }
  function p:GetFName() local me = self return { ToString = function() return me.name end } end
  function p:GetClass() local me = self return { GetFName = function() return { ToString = function() return me.cls end } end } end
  function p:IsValid() return true end
  function p:HasAnyInternalFlags() return false end
  function p:HasAnyFlags() return false end
  function p:GetFullName() return self.cls .. " " .. self.path end
  return p
end
rewardSlot = widget("NamedSlot", "Content")
rewardSlot.path = "/Engine/Transient.WBP_IconEntryLayoutPanel_C_1.WidgetTree.Content"
-- round 94: a full NamedSlot's AddChild hands back a null object, which Lua takes as true
function rewardSlot:AddChild(w) return { IsValid = function() return false end } end
function rewardSlot:SetContent(w) self.content = w; return { IsValid = function() return true end } end
rewardBlock = widget("CommonTextBlock", "CommonTextBlock_194")
rewardBlock.path = "/Engine/Transient.WBP_Quest_Reward_Text_C_3.WidgetTree.CommonTextBlock_194"
rewardBlock.text, rewardBlock.vis = "Alice's Hookshot", 0
function rewardBlock:GetText() local me = self return { ToString = function() return me.text end } end
function rewardBlock:GetParent() return self.parentWidget end
function rewardBlock:GetOuter() return hudTree end
function rewardBlock:GetVisibility() return self.vis end
function rewardBlock:SetVisibility(v) self.vis = v end
function rewardBlock:IsVisible() return true end
rewardBlock.parentWidget = rewardSlot
rewardSlot.content = rewardBlock
otherBlock = widget("CommonTextBlock", "CommonTextBlock_194")
otherBlock.path = "/Engine/Transient.WBP_Menu_C_1.WidgetTree.CommonTextBlock_194"
function otherBlock:GetText() return { ToString = function() return "Alice's Hookshot" end } end
function otherBlock:IsVisible() return true end
rewardLine = widget("WBP_Quest_Reward_Text_C", "WBP_Quest_Reward_Text_C_3")
rewardLine.path = "/Engine/Transient.WBP_Quest_Reward_Text_C_3"
rewardLine.CommonTextBlock_194 = rewardBlock
function rewardLine:IsVisible() return true end
local oldFAO9 = FindAllOf
function FindAllOf(c) if c == "WBP_Quest_Reward_Text_C" then return { rewardLine } end return oldFAO9(c) end
questSpans = { ["Alice's Hookshot"] = { text = "Hookshot", flags = 2 } }
""")
assert L.eval("select(2, G.QuestRewardColors({}))") == 1, "one reward line on screen"
L.eval("G.QuestRewardColors({})")
lines = list(L.eval("(G.QuestRewardColors(questSpans))").values())
SEEN_HOOKSHOT = 'seen: 1 reward lines on screen: "Alice\'s Hookshot" (scouted) by property'
assert lines == [SEEN_HOOKSHOT, "coloured: Alice's Hookshot (in a NamedSlot, in its place)"], lines
assert L.eval("rewardSlot.content.cls") == "HorizontalBox", "the row in the block's place"
assert L.eval("rewardBlock.vis") == 0, "nothing hidden: the block is out of the slot"
assert [L.eval(f"rewardSlot.content.kids[{i}].text") for i in (1, 2)] == ["Alice's ", "Hookshot"]
SLATEBLUE_R = 0.153
assert L.eval("rewardSlot.content.kids[2].ColorAndOpacity.SpecifiedColor.R") == SLATEBLUE_R
assert L.eval("rewardSlot.content.kids[1].Justification") == 0, "left, as the game's line"
assert list(L.eval("(G.QuestRewardColors(questSpans))").values()) == [], "once"
L.execute('rewardBlock.text = "Phoenix Down"')
lines = list(L.eval("(G.QuestRewardColors(questSpans))").values())
assert lines[-1] == "taken out: Alice's Hookshot" and L.eval("rewardSlot.content == rewardBlock") is True, lines
# in a panel: the row beside the block, which is hidden
L.execute(r"""
rewardPanel = { kids = { rewardBlock }, name = "Box", cls = "HorizontalBox", path = "/Engine/Transient.Box" }
function rewardPanel:AddChild(w) self.kids[#self.kids + 1] = w; w.parent = self; return { IsValid = function() return true end } end
function rewardPanel:GetClass() local me = self return { GetFName = function() return { ToString = function() return me.cls end } end } end
function rewardPanel:IsValid() return true end
function rewardPanel:HasAnyInternalFlags() return false end
function rewardPanel:HasAnyFlags() return false end
function rewardPanel:GetFullName() return "HorizontalBox " .. self.path end
rewardBlock.parentWidget, rewardBlock.text = rewardPanel, "Alice's Hookshot"
""")
lines = list(L.eval("(G.QuestRewardColors(questSpans))").values())
assert lines[-1] == "coloured: Alice's Hookshot (in a HorizontalBox)", lines
assert L.eval("rewardBlock.vis") == 1 and L.eval("#rewardPanel.kids") == 2
assert list(L.eval("(G.QuestRewardColors({}))").values())[-1] == "taken out: Alice's Hookshot", "off: all taken out"
assert L.eval("rewardBlock.vis") == 0 and L.eval("#rewardPanel.kids") == 1
# no property of that name: the entry panel's named slot gives the block
L.execute(r"""
rewardLine.CommonTextBlock_194 = nil
rewardLine.WBP_IconEntryLayoutPanel_76 = { GetContentForSlot = function(self, name) if name:ToString() == "Slot_33_Content" then return rewardBlock end end }
""")
lines = list(L.eval("(G.QuestRewardColors(questSpans))").values())
assert lines[0] == 'seen: 1 reward lines on screen: "Alice\'s Hookshot" (scouted) by slot', lines
L.eval("G.QuestRewardColors({})")
L.execute("rewardLine.WBP_IconEntryLayoutPanel_76 = nil")
assert list(L.eval("(G.QuestRewardColors(questSpans))").values()) == ["seen: 1 reward lines on screen: no text block"]
# Round 96: on by default; `instant` hooks the line's own SetText (a Blueprint function, so the
# hook runs after the text is written) and colours that line at once, and puts back a row the
# line showed for another reward
assert L.eval("G.QUEST_COLORS.on") is True and L.eval("G.QUEST_COLORS.instant") is True, "round 97: both on"
L.execute("G.QUEST_COLORS.instant = false")
L.execute(r"""
rewardLine.CommonTextBlock_194 = rewardBlock
rewardBlock.parentWidget, rewardSlot.content, rewardBlock.text = rewardSlot, rewardBlock, "Alice's Hookshot"
questHooks, instantLog = {}, {}
function RegisterHook(name, fn) questHooks[name] = fn end
G.QUEST_COLORS.spans = questSpans
""")
# Round 119: no try until the line's class is loaded (a failed RegisterHook took about 7 ms)
assert L.eval("G.QuestColorHook(function() end)") is None and not L.eval("next(questHooks)"), "the class is not loaded yet"
L.execute('fakePaths["/Game/UI/Quest/Bounty/widget/Detail/WBP_Quest_Reward_Text.WBP_Quest_Reward_Text_C"] = { IsValid = function() return true end }')
assert L.eval("G.QuestColorHook(function(s) instantLog[#instantLog + 1] = s end)") == "registered"
assert L.eval("G.QuestColorHook(function() end)") is None, "once"
hook = 'questHooks["/Game/UI/Quest/Bounty/widget/Detail/WBP_Quest_Reward_Text.WBP_Quest_Reward_Text_C:SetText"]'
L.execute(f"{hook}({{ get = function() return rewardLine end }})")
assert L.eval("#instantLog") == 0 and L.eval("rewardSlot.content == rewardBlock") is True, "instant off: nothing"
L.execute("G.QUEST_COLORS.instant = true")
L.execute(f"{hook}({{ get = function() return rewardLine end }})")
assert L.eval("rewardSlot.content.cls") == "HorizontalBox", "coloured at once"
assert list(L.eval("instantLog").values()) == ["quest colours (instant): coloured: Alice's Hookshot (in a NamedSlot, in its place)"]
L.execute('rewardBlock.text = "Phoenix Down"')
L.execute(f"{hook}({{ get = function() return rewardLine end }})")
assert L.eval("rewardSlot.content == rewardBlock") is True, "the line written for another reward: the game's back"
L.execute("G.QUEST_COLORS.instant = false")

# the quest-notice banner try
L.execute(r"""
noticeVM = { NoticeData = { NoticeTitle = nil }, NoticeQuestData = { Name = nil }, bDisplayNotice = false }
function noticeVM:ExecuteNotics(on) self.bDisplayNotice = on end
function noticeVM:IsValid() return true end
function noticeVM:HasAnyInternalFlags() return false end
function noticeVM:HasAnyFlags() return false end
local oldFFO = FindFirstOf
function FindFirstOf(c) if c == "CPP_VM_QuestNotice" then return noticeVM end return oldFFO(c) end
""")
ok, detail = L.execute('return G.QuestNotice("Received Tent")')
assert ok is True and detail == "set NoticeTitle and quest Name; ExecuteNotics ran; bDisplayNotice true", detail
assert L.eval("noticeVM.NoticeData.NoticeTitle:ToString()") == "Received Tent"
L.execute('blocks = {}')
assert L.eval('(G.TitleVersionLine("FFRArchipelago 0.8.1"))') is None
print("probes: ok")
print("snapshot: ok")

# Round 65: the save's own chest rows for a map. Map 3000 has no row for uid 4 yet, and map 1000
# has an open shiny row 4: IsOpenTreasureBox answered true from it. SaveOpenRows does not.
EARTH_SHRINE, WORLD_MAP, SHARED_UID, CHEST_UID = 3000, 1000, 4, 14
L.execute(f"""
local function boxRow(id, uid, open) return {{ ID = id, UniqueID = uid, IsOpen = open }} end
local sd = makeSave({{false}}, {{ {{SaveId=1, JoinStatus=0}} }}, 8000, 1, true)
sd.Map = {{ mapGimmick = map({{
  {{ {WORLD_MAP}, {{ treasureBox = {{ treasureBoxList = arr({{ boxRow(-1, {SHARED_UID}, true) }}) }} }} }},
  {{ {EARTH_SHRINE}, {{ treasureBox = {{ treasureBoxList = arr({{ boxRow(2, {CHEST_UID}, false) }}) }} }} }},
}}) }}
mgr.m_pGameSaveData = sd
""")
assert L.eval(f"G.SaveOpenRows({WORLD_MAP})[{SHARED_UID}]") is True
assert L.eval(f"G.SaveOpenRows({EARTH_SHRINE})[{SHARED_UID}]") is None, "no row on this map: not open"
assert L.eval(f"G.SaveOpenRows({EARTH_SHRINE})[{CHEST_UID}]") is False
assert L.eval("next(G.SaveOpenRows(9999))") is None
L.execute("mgr.m_pGameSaveData = nil")
assert L.eval("next(G.SaveOpenRows(1000))") is None, "no save: no rows"
print("save rows: ok")

# 0.11.3: experimental custom key items and conditional map gates (ffrap_gate)
L.execute(r"""
valuableRows = {
  Row_Potion = { ID = 1, nameSg = FText("Potion"), isAvailableSale = true },
  Row_TunnelKey = { ID = 20008, sortId = 12, nameSg = FText("Tunnel Key"), isAvailableSale = false },
  Row_Temp = { ID = 30012, sortId = 99, nameSg = FText("[TEMP] Placeholder"), isAvailableSale = false },
}
valuableDT = { rows = valuableRows }
function valuableDT:IsValid() return true end
function valuableDT:ForEachRow(fn)
  for k, r in pairs(self.rows) do fn(fname(k), r) end
end
function valuableDT:AddRow(name, tpl)
  -- Match UE4SS: FText fields passed in AddRow's table are dropped until written on FindRow.
  local copy = {}
  for k, v in pairs(tpl or {}) do
    if type(v) ~= "table" then copy[k] = v end
  end
  self.rows[name] = copy
end
function valuableDT:FindRow(name) return self.rows[name] end

bag = {}
invLib = {
  FindInventory = function(_, id) return bag[id] or 0 end,
  AddInventory = function(_, id, n)
    if id == 29901 and not valuableRows["FFRAP_Key_29901"] then return end
    bag[id] = (bag[id] or 0) + n
  end,
}
function invLib:IsValid() return true end

joinStatuses = { [1001] = 0, [1006] = 2 }
unitLib = { GetJoinStatus = function(_, id) return joinStatuses[id] end }
function unitLib:IsValid() return true end

spawnedActors = {}
local function makeActorClass(cname)
  local c = { cname = cname }
  function c:IsValid() return true end
  function c:GetFName() return fname(self.cname) end
  return c
end
actorClasses = {
  ["/Game/BP/Map/Gimmick/BP_MapGimmick_BlockingBox.BP_MapGimmick_BlockingBox_C"] = makeActorClass("BP_MapGimmick_BlockingBox_C"),
  ["/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockingBase_Child_MagicPot.BP_MapGimmick_BlockingBase_Child_MagicPot_C"] = makeActorClass("BP_MapGimmick_BlockingBase_Child_MagicPot_C"),
  ["/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockingBase_Wld01Gra_01.BP_MapGimmick_BlockingBase_Wld01Gra_01_C"] = makeActorClass("BP_MapGimmick_BlockingBase_Wld01Gra_01_C"),
}

fakeWorld = {}
function fakeWorld:IsValid() return true end
function fakeWorld:SpawnActor(cls, loc, rot)
  local a = {
    cls = cls.cname,
    x = loc.X or 0, y = loc.Y or 0, z = loc.Z or 0,
    yaw = rot.Yaw or 0,
    hidden = false, collision = true, dead = false,
  }
  function a:IsValid() return not self.dead end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  function a:K2_GetActorLocation() return { X = self.x, Y = self.y, Z = self.z } end
  function a:K2_SetActorLocation(l) self.x, self.y, self.z = l.X, l.Y, l.Z end
  function a:K2_SetActorRotation(r) self.yaw = r.Yaw end
  function a:SetActorScale3D(s) self.scale = s.X end
  function a:SetActorHiddenInGame(h) self.hidden = h end
  function a:SetActorEnableCollision(on) self.collision = on end
  function a:K2_DestroyActor() self.dead = true end
  spawnedActors[#spawnedActors + 1] = a
  return a
end

fakePawn = { x = 100.0, y = 200.0, z = 10.0, yaw = 0.0, fx = 0.0, fy = 1.0, sx = 1.0 }
function fakePawn:IsValid() return true end
function fakePawn:HasAnyInternalFlags() return false end
function fakePawn:HasAnyFlags() return false end
function fakePawn:K2_GetActorLocation() return { X = self.x, Y = self.y, Z = self.z } end
function fakePawn:K2_GetActorRotation() return { Pitch = 0, Yaw = self.yaw, Roll = 0 } end
function fakePawn:GetActorForwardVector() return { X = self.fx, Y = self.fy, Z = 0 } end
function fakePawn:GetActorScale3D() return { X = self.sx, Y = self.sx, Z = self.sx } end
function fakePawn:GetClass() return { GetFName = function() return fname("BP_MapUnit_Player_Field_C") end } end
function fakePawn:GetWorld() return fakeWorld end

fakePC = {}
function fakePC:IsValid() return true end
function fakePC:HasAnyInternalFlags() return false end
function fakePC:HasAnyFlags() return false end
function fakePC:K2_GetPawn() return fakePawn end
function fakePC:GetWorld() return fakeWorld end

fakeMapId = 3001
fakeMapMgr = { GetSameMapId = function() return fakeMapId end }
function fakeMapMgr:IsValid() return true end
function fakeMapMgr:HasAnyInternalFlags() return false end
function fakeMapMgr:HasAnyFlags() return false end

local prevSFO = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Item/DT_ValuableItemData.DT_ValuableItemData" then return valuableDT end
  if p == "/Script/mucha.Default__CPP_BFL_SaveDataInventory" then return invLib end
  if p == "/Script/mucha.Default__CPP_BFL_SaveDataUnit" then return unitLib end
  if actorClasses[p] then return actorClasses[p] end
  return prevSFO(p)
end
local prevFAO = FindAllOf
function FindAllOf(c)
  if c == "PlayerController" then return { fakePC } end
  return prevFAO(c)
end
local prevFFO = FindFirstOf
function FindFirstOf(c)
  if c == "CPP_MapManager" then return fakeMapMgr end
  return prevFFO(c)
end
""")

# Round 49: after a map load the cached map manager is forgotten, so a freed one is never touched
L.execute("""
staleMgr = fakeMapMgr
G.CurrentMap()
touched = false
function staleMgr:IsValid() touched = true; return true end
fakeMapMgr = { GetSameMapId = function() return 4242 end }
function fakeMapMgr:IsValid() return true end
function fakeMapMgr:HasAnyInternalFlags() return false end
function fakeMapMgr:HasAnyFlags() return false end
G.ForgetObjects()
""")
assert L.eval("G.CurrentMap()") == 4242 and L.eval("touched") is False, "the old map manager was asked again"
L.execute("fakeMapMgr = staleMgr; function staleMgr:IsValid() return true end; G.ForgetObjects()")

L.execute("gateSteps = {}; G.gateTrace = function(s) gateSteps[#gateSteps + 1] = s end")
ok, detail = L.execute("return G.InjectValuableItem()")
assert ok is True and 'added row FFRAP_Key_29901' in detail and 'Bridge Crest' in detail, detail
assert L.eval('valuableRows.FFRAP_Key_29901.nameSg:ToString()') == "Bridge Crest"
assert L.eval('valuableRows.FFRAP_Key_29901.description:ToString()').startswith("An Archipelago test key item")
assert L.eval('valuableRows.FFRAP_Key_29901.isAvailableSale') is False
assert len(list(L.eval("gateSteps").values())) >= 3
# idempotent update on second call, refuses overwriting vanilla Potion (1), allows [TEMP] (30012)
ok2, detail2 = L.execute("return G.InjectValuableItem(29901, 'Island Sigil')")
assert ok2 is True and 'updated row FFRAP_Key_29901' in detail2 and 'Island Sigil' in detail2, detail2
ok_bad, why_bad = L.execute("return G.InjectValuableItem(1, 'Clobber')")
assert ok_bad is False and "vanilla item" in why_bad, why_bad
ok_tmp, detail_tmp = L.execute("return G.InjectValuableItem(30012, 'Unused Key')")
assert ok_tmp is True and "updated row Row_Temp" in detail_tmp, detail_tmp
# restore Bridge Crest name and grant 1
L.execute("G.InjectValuableItem(29901, 'Bridge Crest')")
code, gdetail = L.execute("return G.GrantItem(29901, 1)")
assert code == "ok" and L.eval("G.HeldCount(29901)") == 1, (code, gdetail)

# spawn combo gate 220 units ahead along +Y
ok, sdetail = L.execute("return G.SpawnGate('combo', 220, 2.5)")
assert ok is True and "BP_MapGimmick_BlockingBox + BP_MapGimmick_BlockingBase_Child_MagicPot" in sdetail, sdetail
assert L.eval("#spawnedActors") == 2
assert abs(L.eval("spawnedActors[1].x") - 100.0) < 1e-6 and abs(L.eval("spawnedActors[1].y") - 420.0) < 1e-6
assert L.eval("spawnedActors[1].scale") == 2.5
assert L.eval("spawnedActors[1].collision") is True and L.eval("spawnedActors[1].hidden") is False

# require 3 Bridge Crests: currently 1/3 -> stays locked; 3/3 -> PollGate unlocks; 2/3 -> re-locks
ok, rdetail = L.execute("return G.SetGateRequirement({ kind = 'item', id = 29901, count = 3 })")
assert ok is True and rdetail == "locked, need Bridge Crest (1/3)", rdetail
L.execute("G.GrantItem(29901, 2)")
poll = L.eval("G.PollGate()")
assert poll.changed == "unlocked" and poll.locked is False and poll.condText == "Bridge Crest (3/3)"
assert L.eval("spawnedActors[1].collision") is False and L.eval("spawnedActors[1].hidden") is True
L.execute("bag[29901] = 2")
poll2 = L.eval("G.PollGate()")
assert poll2.changed == "locked" and poll2.locked is True
assert L.eval("spawnedActors[1].collision") is True and L.eval("spawnedActors[1].hidden") is False

# unit requirement: Fina (1006, JoinStatus=2) locks; Rain (1001, JoinStatus=0) unlocks
ok, udetail = L.execute("return G.SetGateRequirement({ kind = 'unit', id = 1006 })")
assert ok is True and "unit 1006 (missing, JoinStatus=2)" in udetail, udetail
assert L.eval("spawnedActors[1].collision") is True
ok, udetail2 = L.execute("return G.SetGateRequirement({ kind = 'unit', id = 1001 })")
assert ok is True and "unit 1001 (joined, JoinStatus=0)" in udetail2, udetail2
assert L.eval("spawnedActors[1].collision") is False

# npc is refused (raw NPC pawns crash or self-destruct); spawning `world` on map 1000 replaces
# previous actors at default dist 120
ok_npc, why_npc = L.execute("return G.SpawnGate('npc')")
assert ok_npc is False and "npc pawns crash" in why_npc, why_npc
L.execute("fakeMapId = 1000")
ok, wdetail = L.execute("return G.SpawnGate('world')")
assert ok is True and "BP_MapGimmick_BlockingBase_Wld01Gra_01" in wdetail, wdetail
assert L.eval("spawnedActors[1].dead") is True and L.eval("spawnedActors[2].dead") is True
assert abs(L.eval("spawnedActors[3].y") - 320.0) < 1e-6

# actor destroyed by map unload: PollGate reports gone; ClearGate on live actor cleans up
L.execute("G.SpawnGate('box', 150)")
assert L.eval("G.ClearGate()") == 1 and L.eval("G.HasActiveGate()") is False
L.execute("G.SpawnGate('box', 150); spawnedActors[#spawnedActors].dead = true")
assert L.eval("G.PollGate().gone") is True and L.eval("G.HasActiveGate()") is False
L.execute("G.gateTrace = nil")
print("gates: ok")

# 0.12.0: a party member joins the active party when there is room, and the roster otherwise
# (JoinStatus 0, eUnitJoinStatus::Join); a vision before the save owns any waits
L.execute(r"""
joinStatuses[1004], joinStatuses[1005], joinStatuses[1007] = 1, 1, 1
partyFull = false
partyVM = {}
function partyVM:IsValid() return true end
function partyVM:HasAnyInternalFlags() return false end
function partyVM:HasAnyFlags() return false end
function partyVM:IsJoinedUnit(id) return joinStatuses[id] == 0 end
function partyVM:AddUnit(id)
  if partyFull then return false end
  joinStatuses[id] = 0
  return true
end
function unitLib:SetJoinStatus(id, st) joinStatuses[id] = st end
visionLib = { owned = {} }
function visionLib:IsValid() return true end
function visionLib:HasVision(id) return self.owned[id] == true end
local prevFFO2 = FindFirstOf
function FindFirstOf(c)
  if c == "CPP_VM_Party" then return partyVM end
  return prevFFO2(c)
end
local prevSFO2 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/mucha.Default__CPP_BFL_Vision" then return visionLib end
  return prevSFO2(p)
end
""")
code, detail = L.execute("return G.AddUnit(1004)")
assert code == "ok" and "in the active party" in detail, (code, detail)
L.execute("partyFull = true")
code, detail = L.execute("return G.AddUnit(1005)")
assert code == "ok" and "joined the roster through library" in detail, (code, detail)
assert L.eval("joinStatuses[1005]") == 0
code, detail = L.execute("return G.AddUnit(1005)")
assert code == "ok" and detail == "already joined", (code, detail)
# the library cannot write it: refused, and said so
L.execute("unitLib.SetJoinStatus = nil")
code, detail = L.execute("return G.AddUnit(1007)")
assert code == "fail" and "did not join" in detail, (code, detail)
assert L.eval("G.HasVision(13100)") is False
L.execute("visionLib.owned[13100] = true")
assert L.eval("G.HasVision(13100)") is True
print("party members and HasVision: ok")

# 0.13.0: open world probes. Enemy rows rescaled by level (ffrap_scale), and the airship's
# spawn condition (ffrap_airship). 0.14.0: the curve (L / own)^b * e^(c (L - own)), capped at
# level 70, and the hp and power knobs.
import math
CURVE = {"MaxHitPoint": (0.3675, 0.08917), "Attack": (0.3207, 0.02946), "Intelligence": (0.5644, 0.03269),
         "Defence": (0.7752, 0.00867), "Experience": (-0.0647, 0.12967)}
# Round 77: Defence grows at the curve's factor to the power 0.75; bosses' HP has its own curve.
DEFENCE_GROWTH = 0.75
BOSS_CURVE = {"MaxHitPoint": (0.91163, 0.02766)}
def ratio(stat, f, t, curves=None):
    b, c = (curves or {}).get(stat) or CURVE[stat]
    f, t = max(1, min(f, 70)), max(1, min(t, 70))
    r = (t / f) ** b * math.exp(c * (t - f))
    return r ** DEFENCE_GROWTH if stat == "Defence" and r > 1 else r
def scaled(v, stat, f, t, knob=100):
    return max(1, math.floor(v * ratio(stat, f, t) * knob / 100 + 0.5))
def scaled_boss(v, f, t):
    return max(1, math.floor(v * ratio("MaxHitPoint", f, t, BOSS_CURVE) + 0.5))
st = L.eval("G.ScaledStats({ Level = 1, MaxHitPoint = 68, MaxBreakPoint = 50, Attack = 30, Defence = 30,"
            " Intelligence = 15, Mind = 30, Agility = 13, Experience = 12, Money = 20 }, 11)")
assert st.Level == 11 and st.MaxHitPoint == scaled(68, "MaxHitPoint", 1, 11), dict(st)
assert st.Attack == scaled(30, "Attack", 1, 11) and st.Defence == scaled(30, "Defence", 1, 11), dict(st)
# round 31's case: the Soldier (level 30, attack 189) pulled to level 3 now has about a level 3
# enemy's attack (the shipped ones have 45), not 56
# Round 77: Siren (level 11, 20,000 HP) at level 57 had 2,434,404 HP on the enemy curve. On the
# bosses' curve she has about 320,000, near the game's own level-50 bosses (130,000 to 250,000).
SIREN = "{ Level = 11, MaxHitPoint = 20000, Defence = 70 }"
siren = L.eval(f"G.ScaledStats({SIREN}, 57, nil, G.BOSS_CURVE)")
assert siren.MaxHitPoint == scaled_boss(20000, 11, 57) and 300000 < siren.MaxHitPoint < 340000, siren.MaxHitPoint
assert L.eval(f"G.ScaledStats({SIREN}, 57)").MaxHitPoint > 2000000, "the enemy curve, for comparison"
assert siren.Defence == scaled(70, "Defence", 11, 57) and siren.Defence < 70 * 4, siren.Defence
assert L.eval("G.ScaledStats({ Level = 40, Defence = 300 }, 10)").Defence == scaled(300, "Defence", 40, 10), \
    "scaling down is as before"
down3 = L.eval("G.ScaledStats({ Level = 30, MaxHitPoint = 1000, Attack = 189, Experience = 30 }, 3)")
assert 38 <= down3.Attack <= 46 and down3.Attack == scaled(189, "Attack", 30, 3), dict(down3)
# the knobs: hp moves HP, attack moves Attack, magic moves Intelligence, nothing else
k = L.eval("G.ScaledStats({ Level = 10, MaxHitPoint = 500, Attack = 80, Intelligence = 50, Defence = 60 }, 10,"
           " { hp = 50, attack = 80, magic = 120 })")
assert k.MaxHitPoint == 250 and k.Attack == 64 and k.Intelligence == 60 and k.Defence == 60, dict(k)
# above level 70 the curve stops growing
assert abs(L.eval("G.CurveRatio('MaxHitPoint', 70, 99)") - 1.0) < 1e-9
assert abs(L.eval("G.CurveRatio('Attack', 99, 50)") - ratio("Attack", 70, 50)) < 1e-9
assert L.eval("G.CurveRatio('MaxMagicPoint', 1, 50)") == 1
# the band: centred on at% of the party's level
a, b, c = L.execute("return G.LevelBand(40, 5, 80)")
assert (a, b, c) == (27, 37, 32), (a, b, c)
a, b, c = L.execute("return G.LevelBand(1, 2, 80)")
assert (a, b, c) == (-1, 3, 1), (a, b, c)
a, b, c = L.execute("return G.LevelBand(52, 1)")
assert (a, b, c) == (51, 53, 52), (a, b, c)
a, b, c = L.execute("return G.LevelBand(8, 1, 92, 3)")
assert (a, b, c) == (6, 10, 7), "round 63: 1 under the centre, 3 over"
same = L.eval("G.ScaledStats({ Level = 7, MaxHitPoint = 300, Attack = 66, Money = 0 }, 7)")
assert same.MaxHitPoint == 300 and same.Attack == 66 and same.Money == 0, dict(same)
down = L.eval("G.ScaledStats({ Level = 50, MaxHitPoint = 3, Attack = 2 }, 1)")
assert down.MaxHitPoint == 1 and down.Attack == 1, "no stat below 1"
assert L.eval("G.ScaledLevel(30, 'clamp', 5, 15)") == 15
assert L.eval("G.ScaledLevel(2, 'clamp', 5, 15)") == 5
assert L.eval("G.ScaledLevel(9, 'clamp', 5, 15)") == 9
assert L.eval("G.ScaledLevel(9, 'fixed', 140)") == 99 and L.eval("G.ScaledLevel(9, 'fixed', -3)") == 1
assert L.eval("G.ScaledLevel(9, 'off', 20)") == 9

L.execute(r"""
unitRows = {
  bat = { ID = 2, Category = 2, Name = FText("Steel Bat"), Level = 1, MaxHitPoint = 68, MaxBreakPoint = 50,
          Attack = 30, Defence = 30, Intelligence = 15, Mind = 30, Agility = 13, Experience = 12, Money = 20 },
  boss = { ID = 9004, Category = 3, Name = FText("Belmodar"), Level = 4, MaxHitPoint = 2000, MaxBreakPoint = 100,
           Attack = 60, Defence = 40, Intelligence = 30, Mind = 40, Agility = 20, Experience = 100, Money = 300 },
  rain = { ID = 1001, Category = 1, Name = FText("Rain"), Level = 1, MaxHitPoint = 300, MaxBreakPoint = 0,
           Attack = 30, Defence = 20, Intelligence = 10, Mind = 10, Agility = 10, Experience = 0, Money = 0 },
}
unitDT = {}
function unitDT:IsValid() return true end
function unitDT:GetFullName() return "DataTable /Game/Datatable/Unit/DT_UnitParameter" end
function unitDT:ForEachRow(fn) for k, r in pairs(unitRows) do fn(fname(k), r) end end
airRow = { spawnCondition = "{progress:0}>=4250" }
airDT = {}
function airDT:IsValid() return true end
function airDT:ForEachRow(fn) fn(fname("NewRow"), airRow) end
local prevSFO3 = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Unit/DT_UnitParameter.DT_UnitParameter" then return unitDT end
  if p == "/Game/Datatable/Asset/Map/DT_MapAirShip.DT_MapAirShip" then return airDT end
  return prevSFO3(p)
end
""")
n, sample, _ = L.execute("return G.ScaleEnemies('fixed', 20, nil, false)")[:3]
assert n == 1 and "Steel Bat (2): level 1 -> 20" in sample, (n, sample)
assert L.eval("unitRows.bat.Level") == 20 and L.eval("unitRows.bat.MaxHitPoint") == scaled(68, "MaxHitPoint", 1, 20)
assert L.eval("unitRows.boss.Level") == 4 and L.eval("unitRows.rain.Level") == 1, "bosses and party left alone"
n, _, _ = L.execute("return G.ScaleEnemies('fixed', 20, nil, false)")[:3]
assert n == 0, "already scaled: nothing to do"
# the next scale works from the shipped row, not from the scaled one
n, _, _ = L.execute("return G.ScaleEnemies('clamp', 5, 15, true)")[:3]
assert n == 2 and L.eval("unitRows.bat.Level") == 5 and L.eval("unitRows.boss.Level") == 5, n
assert L.eval("unitRows.bat.MaxHitPoint") == scaled(68, "MaxHitPoint", 1, 5)
# the knobs reach the rows
n, _, lines = L.execute("return G.ScaleEnemies('clamp', 5, 15, true, { hp = 50 })")[:3]
assert n == 2 and L.eval("unitRows.bat.MaxHitPoint") == scaled(68, "MaxHitPoint", 1, 5, 50), n
# Round 49: bosses can have their own band and knobs
L.execute("G.ScaleEnemies('clamp', 1, 3, true, { hp = 50 }, { a = 20, b = 20, knobs = { hp = 100 } })")
assert L.eval("unitRows.boss.Level") == 20 and L.eval("unitRows.boss.MaxHitPoint") == scaled_boss(2000, 4, 20)
assert L.eval("unitRows.bat.Level") == 1 and L.eval("unitRows.bat.MaxHitPoint") == scaled(68, "MaxHitPoint", 1, 1, 50)
n, _, lines = L.execute("return G.ScaleEnemies('clamp', 5, 15, true, { hp = 50 })")[:3]
# a line per changed row, for scale.txt
assert len(lines) == 2 and any(("level 1 -> 5\tHP %d\t" % scaled(68, "MaxHitPoint", 1, 5, 50)) in l for l in lines.values()), list(lines.values())
# Round 47: a battle's MRP follows its enemies' average level; a battle with no scaled enemy, and
# one worth nothing, are left alone
L.execute("""
groupRows = { a = { ID = 1, ap = 100, UnitIdList = { 2, 2 } }, b = { ID = 2, ap = 50, UnitIdList = { 9004 } },
              c = { ID = 3, ap = 0, UnitIdList = { 2 } }, d = { ID = 4, ap = 7, UnitIdList = { 1001 } } }
groupDT = {}
function groupDT:IsValid() return true end
function groupDT:GetFullName() return "DataTable /Game/Datatable/Encount/DT_BattleGroup" end
function groupDT:ForEachRow(fn) for k, r in pairs(groupRows) do fn(fname(k), r) end end
local prevSFOg = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Encount/DT_BattleGroup.DT_BattleGroup" then return groupDT end
  return prevSFOg(p)
end
""")
_, sample, _ = L.execute("return G.ScaleEnemies('clamp', 20, 20, true, { hp = 50 })")[:3]
assert "MRP changed in 2 battle groups" in sample, sample
expect = max(1, int(100 * L.eval("G.CurveRatio('BattleMRP', 1, 20)") + 0.5))
assert L.eval("groupRows.a.ap") == expect, (L.eval("groupRows.a.ap"), expect)
assert L.eval("groupRows.b.ap") == max(1, int(50 * L.eval("G.CurveRatio('BattleMRP', 4, 20)") + 0.5))
assert L.eval("groupRows.c.ap") == 0 and L.eval("groupRows.d.ap") == 7
# Round 101: mrpLift pays MRP as if the band were that many levels higher. The rows keep the
# band's level; a band with no lift (the bosses' here) pays at its own level.
MRP_LIFT = 5
L.execute(f"G.ScaleEnemies('clamp', 20, 20, true, {{ hp = 50, mrpLift = {MRP_LIFT} }}, {{ a = 20, b = 20, knobs = {{ hp = 100 }} }})")
assert L.eval("unitRows.bat.Level") == 20, "the row keeps the band's level"
assert L.eval("groupRows.a.ap") == max(1, int(100 * L.eval(f"G.CurveRatio('BattleMRP', 1, {20 + MRP_LIFT})") + 0.5))
assert L.eval("groupRows.b.ap") == max(1, int(50 * L.eval("G.CurveRatio('BattleMRP', 4, 20)") + 0.5)), "the boss's group: no lift"
L.execute("G.ScaleEnemies('clamp', 1, 99, true, { hp = 50 })")      # every enemy back at its own level
assert L.eval("groupRows.a.ap") == 100 and L.eval("groupRows.b.ap") == 50, "worked out from the shipped value"
L.execute("G.ScaleEnemies('clamp', 5, 15, true, { hp = 50 })")
# 0.15.1: the check sees what the last rescale wrote; a row written over, or a table loaded
# again, shows up
checked, differ, sample, reloaded = L.execute("return G.ScaleCheck()")
assert (checked, differ, sample, reloaded) == (2, 0, None, False), (checked, differ, sample, reloaded)
L.execute("for k, v in pairs({ Level = 1, MaxHitPoint = 68, MaxBreakPoint = 50, Attack = 30, Defence = 30, Intelligence = 15,"
          " Mind = 30, Agility = 13, Experience = 12, Money = 20 }) do unitRows.bat[k] = v end")
checked, differ, sample, reloaded = L.execute("return G.ScaleCheck()")
assert (checked, differ, reloaded) == (2, 1, False) and sample == "Steel Bat (2): level 1, HP 68, wrote level 5", sample
L.execute("function unitDT:GetAddress() return 4096 end; function unitDT:HasAnyInternalFlags() return false end; function unitDT:HasAnyFlags() return false end")
assert L.execute("return G.ScaleCheck()")[3] is True, "a new address is a table loaded again"
L.execute("G.ScaleEnemies('clamp', 5, 15, true, { hp = 50 })")
assert L.execute("return G.ScaleCheck()")[1:] == (0, None, False)
# Round 62: The Hunger is an Enemy-category unit with no EXP. In a boss location's group it is
# scaled as a boss and gets a story boss's EXP for its level.
THE_HUNGER, HUNGER_GROUP, HUNGER_LEVEL, HUNGER_HP = 113, 9012, 9, 2500
L.execute(f"""
unitRows.hunger = {{ ID = {THE_HUNGER}, Category = 2, Name = FText("The Hunger"), Level = {HUNGER_LEVEL}, MaxHitPoint = {HUNGER_HP},
  MaxBreakPoint = 80, Attack = 90, Defence = 40, Intelligence = 60, Mind = 40, Agility = 20, Experience = 0, Money = 0 }}
groupRows.hunger = {{ ID = {HUNGER_GROUP}, ap = 0, UnitIdList = {{ {THE_HUNGER} }} }}""")
_, sample, _ = L.execute("return G.ScaleEnemies('clamp', 2, 3, true, { hp = 50 }, { a = 6, b = 6, knobs = { hp = 100 } })")[:3]
assert "units in boss groups" in sample, sample
assert L.eval("unitRows.hunger.Level") == 6 and L.eval("unitRows.hunger.MaxHitPoint") == scaled_boss(HUNGER_HP, HUNGER_LEVEL, 6), "the boss band"
boss_exp = int(1350 * L.eval(f"G.CurveRatio('Experience', 14, {HUNGER_LEVEL})") + 0.5)
assert L.eval("unitRows.hunger.Experience") == max(1, int(boss_exp * L.eval(f"G.CurveRatio('Experience', {HUNGER_LEVEL}, 6)") + 0.5))
assert L.eval("unitRows.bat.Level") == 2, "a plain enemy keeps the enemies' band"
L.execute("G.ScaleEnemies('clamp', 2, 3, false, { hp = 50 })")
assert L.eval("unitRows.hunger.Level") == 6, "without bosses, a boss group's unit is left alone"
L.execute("G.ScaleEnemies('off', nil, nil, false, { hp = 100 })")
assert L.eval("unitRows.hunger.Level") == HUNGER_LEVEL and L.eval("unitRows.hunger.Experience") == 0, "off gives the shipped row back, bosses too"
assert L.eval("unitRows.boss.Level") == 4
# Round 63: the Arena's rank battles from Brawler Battle 1 (group 9705) on are scaled as bosses and
# keep their 0 EXP. Fledgling Battle 1 (9700) holds field enemies, which stay plain enemies.
DARK_FANG, BRAWLER_1, WYVERN, FLEDGLING_1, ARENA_LEVEL, ARENA_HP = 4001, 9705, 198, 9700, 40, 135000
L.execute(f"""
unitRows.fang = {{ ID = {DARK_FANG}, Category = 2, Name = FText("Dark Fang"), Level = {ARENA_LEVEL}, MaxHitPoint = {ARENA_HP},
  MaxBreakPoint = 80, Attack = 900, Defence = 400, Intelligence = 600, Mind = 400, Agility = 200, Experience = 0, Money = 0 }}
unitRows.wyvern = {{ ID = {WYVERN}, Category = 2, Name = FText("Wyvern"), Level = 26, MaxHitPoint = 4700,
  MaxBreakPoint = 80, Attack = 300, Defence = 200, Intelligence = 200, Mind = 200, Agility = 100, Experience = 400, Money = 0 }}
groupRows.brawler = {{ ID = {BRAWLER_1}, ap = 0, UnitIdList = {{ {DARK_FANG} }} }}
groupRows.fledgling = {{ ID = {FLEDGLING_1}, ap = 0, UnitIdList = {{ {WYVERN} }} }}""")
_, sample, _ = L.execute("return G.ScaleEnemies('clamp', 2, 3, true, { hp = 50 }, { a = 6, b = 6, knobs = { hp = 100 } })")[:3]
assert "1 in the Arena" in sample, sample
assert L.eval("unitRows.fang.Level") == 6 and L.eval("unitRows.fang.MaxHitPoint") == scaled_boss(ARENA_HP, ARENA_LEVEL, 6), "the boss band"
assert L.eval("unitRows.fang.Experience") == 0, "the Arena pays in items"
assert L.eval("unitRows.wyvern.Level") == 3, "a Fledgling battle's field enemy keeps the enemies' band"
L.execute("unitRows.fang = nil; unitRows.wyvern = nil; groupRows.brawler = nil; groupRows.fledgling = nil")
L.execute("unitRows.hunger = nil; groupRows.hunger = nil; G.ScaleEnemies('clamp', 5, 15, true, { hp = 50 })")
# the rows of one unit, by id or name, in every unit table
L.execute("""
local prevFAO6 = FindAllOf
copyDT = { rows = { x = { ID = 2, Category = 2, Name = FText("Steel Bat"), Level = 33 } } }
function copyDT:IsValid() return true end
function copyDT:HasAnyInternalFlags() return false end
function copyDT:HasAnyFlags() return false end
function copyDT:GetFullName() return "DataTable /Game/Other/DT_UnitParameter_Copy" end
function copyDT:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
calcDT = { rows = {} }
for k, v in pairs(copyDT) do if type(v) == "function" then calcDT[k] = v end end
function calcDT:GetFullName() return "DataTable /Game/Datatable/Unit/DT_UnitParameterCalc" end
function FindAllOf(c)
  if c == "DataTable" then return { copyDT, calcDT, unitDT } end
  return prevFAO6(c)
end
""")
rows = list(L.eval("G.UnitRows('steel')").values())
assert len(rows) == 4 and rows[0].startswith("table DataTable /Game/Datatable/Unit/DT_UnitParameter@4096"), rows
assert "2 Steel Bat (row bat, category 2): level 5" in rows[1] and "game's level 1; last rescale wanted 5" in rows[1], rows
assert rows[2].startswith("table DataTable /Game/Other/DT_UnitParameter_Copy") and "level 33" in rows[3], rows
assert len(list(L.eval("G.UnitRows('9004')").values())) == 3, "by id; the copy has no row 9004"
n, _, _ = L.execute("return G.ScaleEnemies('off', nil, nil, true)")[:3]
assert n == 2 and L.eval("unitRows.bat.MaxHitPoint") == 68 and L.eval("unitRows.boss.Experience") == 100, n
assert L.execute("return G.ScaleCheck()")[0] is None, "nothing in force after off"
# round 33: another mod (the FFR Randomizer) writes its own values into a row (Steel Bat at level
# 47). The next rescale takes them as the base, and off gives them back, not the shipped ones.
L.execute("G.ScaleEnemies('fixed', 10, nil, false)")
L.execute("for k, v in pairs({ Level = 47, MaxHitPoint = 4800, Attack = 422, Experience = 1760 }) do unitRows.bat[k] = v end")
n, sample, _, game_changed = L.execute("return G.ScaleEnemies('fixed', 10, nil, false)")
assert n == 1 and game_changed == 1 and "level 47 -> 10, HP 4800 -> " in sample, (n, game_changed, sample)
assert L.eval("unitRows.bat.MaxHitPoint") == scaled(4800, "MaxHitPoint", 47, 10)
n, _, _, game_changed = L.execute("return G.ScaleEnemies('fixed', 10, nil, false)")
assert n == 0 and game_changed == 0, "our own write is not the game's"
L.execute("G.ScaleEnemies('off')")
assert L.eval("unitRows.bat.Level") == 47 and L.eval("unitRows.bat.MaxHitPoint") == 4800, "off gives the game's row back"

assert L.eval("G.AirshipCondition()") == "{progress:0}>=4250"
assert L.eval("G.AirshipCondition('{progress:0}>=0')") == "{progress:0}>=0"
assert L.eval("airRow.spawnCondition") == "{progress:0}>=0"
# Round 69: a seed with the airship as an item hides it behind flag 1431; a seed without puts the
# game's condition back over that one only, so an ffrap_airship test stays.
L.execute("airRow.spawnCondition = '{progress:0}>=4250'")
assert L.eval("G.AirshipItemSync(true)") == "{flag:1431}" and L.eval("G.AirshipItemSync(true)") is None
assert L.eval("G.AirshipItemSync(false)") == "{progress:0}>=4250"
L.execute("airRow.spawnCondition = '{progress:0}>=0'")
assert L.eval("G.AirshipItemSync(false)") is None and L.eval("airRow.spawnCondition") == "{progress:0}>=0"
L.execute("airDT = nil")
now, err = L.execute("return G.AirshipCondition('x')")
assert now is None and "not loaded" in err, (now, err)
print("open world probes (scale, airship): ok")

# the party's average level (GetPlayableUnitLevel), and the story counter at any value
L.execute(r"""
levels = { [1001] = 5, [1002] = 8 }
unitBFL = {}
function unitBFL:IsValid() return true end
function unitBFL:GetPlayableUnitLevel(id) return levels[id] or 0 end
function partyVM:GetPartyUnitIdList() return { 1001, 1002 } end
local prevSFO4 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/mucha.Default__CPP_BFL_Unit" then return unitBFL end
  return prevSFO4(p)
end
""")
lv, detail = L.execute("return G.PartyLevel()")
assert lv == 7 and detail == "1001:5 1002:8", (lv, detail)
L.execute("levels[1002] = nil")
lv, detail = L.execute("return G.PartyLevel()")
assert lv is None and "1002" in detail, (lv, detail)
L.execute("mgr.m_pGameSaveData = makeSave({false}, { {SaveId=1, JoinStatus=0} }, 1130, 1, false)")
assert L.eval("G.SetStoryCounter(9000)") == 9000 and L.eval("G.StoryCounter()") == 9000
print("party level and story counter: ok")

# 0.14.0: the no-landing boxes (ffrap_noland). The game's Mysidia box is moved and put back; a
# spawned box is removed.
L.execute(r"""
function makeBoxActor(name, x, y, z, ex, ey, ez, cond)
  local box = { ex = ex, ey = ey, ez = ez }
  function box:IsValid() return true end
  function box:HasAnyInternalFlags() return false end
  function box:HasAnyFlags() return false end
  function box:GetUnscaledBoxExtent() return { X = self.ex, Y = self.ey, Z = self.ez } end
  function box:SetBoxExtent(v) self.ex, self.ey, self.ez = v.X, v.Y, v.Z end
  function box:SetHiddenInGame(h) self.hidden = h end
  box.coll = (cond == "" or cond == "{progress:0}<5020") and 1 or 0
  function box:GetCollisionEnabled() return self.coll end
  function box:SetCollisionEnabled(v) self.coll = v end
  function box:GetCollisionProfileName() return fname("NoLanding") end
  function box:GetCollisionObjectType() return 14 end
  function box:GetCollisionResponseToChannel(ch) if ch == 14 then return 2 elseif ch == 3 then return 0 else return 1 end end
  local a = { x = x, y = y, z = z, yaw = 0, m_Condition = cond, m_pBoxComponent = box, nm = name, dead = false }
  function a:IsValid() return not self.dead end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  function a:GetFName() return fname(self.nm) end
  function a:K2_GetActorLocation() return { X = self.x, Y = self.y, Z = self.z } end
  function a:K2_GetActorRotation() return { Pitch = 0, Yaw = self.yaw, Roll = 0 } end
  function a:K2_SetActorLocation(l) self.x, self.y, self.z = l.X, l.Y, l.Z end
  function a:K2_SetActorRotation(r) self.yaw = r.Yaw end
  function a:K2_DestroyActor() self.dead = true end
  return a
end
nolandActors = {
  makeBoxActor("BP_MapNonLandingArea_C_0", 16643, 21655, -33, 90, 210, 32, ""),
  makeBoxActor("BP_MapNonLandingArea_C_42", -18053, -8493, 393, 2400, 6000, 700, "{progress:0}<5020"),
}
actorClasses["/Game/BP/Map/BP_MapNonLandingArea.BP_MapNonLandingArea_C"] = { cname = "BP_MapNonLandingArea_C",
  IsValid = function() return true end }
local spawnOld = fakeWorld.SpawnActor
function fakeWorld:SpawnActor(cls, loc, rot)
  if cls.cname == "BP_MapNonLandingArea_C" then
    local a = makeBoxActor("BP_MapNonLandingArea_C_spawned", loc.X, loc.Y, loc.Z, 100, 100, 100, "")
    nolandActors[#nolandActors + 1] = a
    return a
  end
  return spawnOld(self, cls, loc, rot)
end
local prevFAO5 = FindAllOf
function FindAllOf(c)
  if c == "BP_MapNonLandingArea_C" then return nolandActors end
  return prevFAO5(c)
end
fakePawn.x, fakePawn.y, fakePawn.z = 5000, 6000, 900
""")
boxes = L.eval("G.NoLandBoxes()")
assert len(boxes) == 2 and boxes[2].cond == "{progress:0}<5020" and boxes[2].ex == 2400, dict(boxes[2])
line = L.eval("G.NoLandLine(G.NoLandBoxes()[2])")
assert line == 'BP_MapNonLandingArea_C_42 at (-18053, -8493, 393) half-size (2400, 6000, 700) yaw 0, condition "{progress:0}<5020"', line
# move: the Mysidia box goes around the player, with an empty condition
box, why = L.execute("local b, w = G.NoLandMove(4000); return b, w")
assert why is None and box.x == 5000 and box.y == 6000 and box.z == 393 and box.ex == 4000 and box.ez == 700 and box.cond == "", (dict(box), why)
# spawn: a new box around the player
box, why = L.execute("local b, w = G.NoLandSpawn(2500); return b, w")
assert why is None and box.ex == 2500 and box.ey == 2500 and box.x == 5000 and box.z == 393 and box.ez == 700, (dict(box), why)
assert L.eval("#G.NoLandBoxes()") == 3
# cond: written to both test boxes, not to the others
n, last, err = L.execute("local n, l, e = G.NoLandCondition('{progress:0}<0'); return n, l, e")
assert n == 2 and err is None and last.cond == "{progress:0}<0", (n, err)
assert L.eval("nolandActors[2].m_Condition") == "{progress:0}<0" and L.eval("nolandActors[1].m_Condition") == ""
# off: the spawned box is gone and the Mysidia box is back as shipped
assert L.eval("G.NoLandOff()") == 2
assert L.eval("nolandActors[3].dead") is True
m = L.eval("nolandActors[2]")
assert (m.x, m.y, m.z, m.m_pBoxComponent.ex, m.m_pBoxComponent.ey, m.m_Condition) == (-18053, -8493, 393, 2400, 6000, "{progress:0}<5020"), dict(m)
# no Mysidia box on this map: refused
L.execute("nolandActors = { nolandActors[1] }")
box, why = L.execute("local b, w = G.NoLandMove(); return b, w")
assert box is None and "not on this map" in why, why
# 0.15.0: here, lock, unlock, show
L.execute("""
nolandActors[#nolandActors + 1] = makeBoxActor("BP_MapNonLandingArea_C_1", -5930, -17400, 240, 473, 304, 130, "{progress:0}<7020")
nolandActors[#nolandActors].yaw = 0
""")
L.execute("fakePawn.x, fakePawn.y = -5900, -17200")
here, pose = L.execute("return G.NoLandHere()")
assert len(here) == 1 and here[1].name == "BP_MapNonLandingArea_C_1", [dict(h) for h in here.values()]
L.execute("fakePawn.x, fakePawn.y = -5900, -17000")
assert L.eval("#G.NoLandHere()") == 0
# a box turned by its yaw: (0, 0) half-size 100 x 10, turned 90 degrees, holds (0, 50) but not (50, 0)
assert L.eval("G.BoxHolds({ x = 0, y = 0, ex = 100, ey = 10, yaw = 90 }, 0, 50)") is True
assert L.eval("G.BoxHolds({ x = 0, y = 0, ex = 100, ey = 10, yaw = 90 }, 50, 0)") is False
assert L.eval("G.BoxHolds({ x = 0, y = 0, ex = 100, ey = 10, yaw = 0 }, 50, 0)") is True
# collision as text
col = L.eval("G.NoLandCollision(G.NoLandBoxes()[1])")
assert col == ("collision: actor ?, enabled 1, profile NoLanding, object type 14, channels 0-7 11101111, "
               "14-31 211111111111111111, hidden nil"), col
# 0.15.1: every box with the story condition is locked (a second Pharm box here)
L.execute("""
nolandActors[#nolandActors + 1] = makeBoxActor("BP_MapNonLandingArea_C_7", -6500, -17000, 240, 100, 100, 50, "{progress:0}<7020")
""")
boxes, why = L.execute("local b, w = G.NoLandLock('pharm', true); return b, w")
assert why is None and len(boxes) == 2 and boxes[1].cond == "{progress:0}>=0" and boxes[1].x == -5930, why
assert L.eval("nolandActors[3].m_Condition") == "{progress:0}>=0"
# refresh: the locked boxes get the collision of a box with no condition (1), now
n_on, n_off, on_type = L.execute("return G.NoLandRefresh()")
assert (n_on, n_off, on_type) == (2, 0, 1) and L.eval("nolandActors[2].m_pBoxComponent.coll") == 1
boxes, why = L.execute("local b, w = G.NoLandLock('pharm', false); return b, w")
assert why is None and boxes[2].cond == "{progress:0}<0", why
assert L.execute("return G.NoLandRefresh()") == (0, 2, 1) and L.eval("nolandActors[3].m_pBoxComponent.coll") == 0
box, why = L.execute("local b, w = G.NoLandLock('gronoa', true); return b, w")
assert box is None and "not on this map" in why, why
box, why = L.execute("local b, w = G.NoLandLock('narshe', true); return b, w")
assert box is None and "no story box" in why, why
assert L.eval("G.NoLandShow(true, 25)") == 3
assert L.eval("nolandActors[2].m_pBoxComponent.hidden") is False and L.eval("nolandActors[2].m_pBoxComponent.LineThickness") == 25
assert L.eval("G.NoLandShow(false)") == 3 and L.eval("nolandActors[2].m_pBoxComponent.hidden") is True
# off gives the story boxes their own condition and collision back
L.execute("G.NoLandLock('pharm', true); G.NoLandRefresh()")
assert L.eval("G.NoLandOff()") == 2
assert L.eval("nolandActors[2].m_Condition") == "{progress:0}<7020" and L.eval("nolandActors[3].m_Condition") == "{progress:0}<7020"
assert L.eval("nolandActors[2].m_pBoxComponent.coll") == 0 and L.eval("nolandActors[3].m_pBoxComponent.coll") == 0

# 0.17.0 (round 35: the Pharm box may be buried under high ground): spawn takes the box's top,
# and the trace down lists the no-landing boxes it meets (collision on) and then the ground.
FLIGHT_Z, BOX_TOP, PHARM_GROUND, HIGH_GROUND = 1500, 2500, 50, 800
box, why = L.execute(f"local b, w = G.NoLandSpawn(2000, {BOX_TOP}); return b, w")
assert why is None and box.z == BOX_TOP - 700 and box.ez == 700, (dict(box), why)
L.execute("G.NoLandOff()")
L.execute(r"""
groundZ = 0
local ksl = {}
function ksl:IsValid() return true end
function ksl:HasAnyInternalFlags() return false end
function ksl:HasAnyFlags() return false end
-- the highest surface under the start: a box with its collision on, or the ground
function ksl:LineTraceSingle(ctx, s, e, query, complex, ignore, draw, hit)
  local bestZ, bestName = groundZ, "Landscape_1"
  for _, a in ipairs(nolandActors) do
    local b = a.m_pBoxComponent
    local top = a.z + b.ez
    if not a.dead and b.coll > 0 and top <= s.Z and top > bestZ and math.abs(s.X - a.x) <= b.ex and math.abs(s.Y - a.y) <= b.ey then
      bestZ, bestName = top, a.nm
    end
  end
  if bestZ > s.Z then return false end
  -- round 36: the game hands back the component; its owner is the actor
  local owner = { nm = bestName }
  function owner:GetFName() return fname(self.nm) end
  local component = { nm = bestName == "Landscape_1" and "LandscapeHeightfieldCollisionComponent_77" or "BoxComponent" }
  function component:GetFName() return fname(self.nm) end
  function component:GetOwner() return owner end
  hit.HitObjectHandle = { ReferenceObject = { Get = function() return component end } }
  hit.ImpactPoint = { X = s.X, Y = s.Y, Z = bestZ }
  return true
end
local prevSFO6 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/Engine.Default__KismetSystemLibrary" then return ksl end
  return prevSFO6(p)
end
""")
L.execute(f"fakePawn.x, fakePawn.y, fakePawn.z = -5900, -17200, {FLIGHT_Z}; groundZ = {PHARM_GROUND}")
L.execute("G.NoLandLock('pharm', true); G.NoLandRefresh()")
hits = [dict(h) for h in L.eval("G.GroundUnder()").values()]
assert hits == [{"name": "BP_MapNonLandingArea_C_1", "z": 370, "box": True},
                {"name": "Landscape_1", "z": PHARM_GROUND, "box": False}], hits
# high ground over the box: the trace stops at the ground and never meets the box
# 0.18.0: a spawned box's response to one channel (the shadow probe); the game's boxes are left alone
L.execute("G.NoLandSpawn(500)")
L.execute("local b = nolandActors[#nolandActors].m_pBoxComponent; function b:SetCollisionResponseToChannel(ch, r) self.resp = { [ch] = r } end")
assert L.eval("G.NoLandChannel(3, 0)") == 1
assert L.eval("nolandActors[#nolandActors].m_pBoxComponent.resp[3]") == 0
L.execute("G.NoLandOff()")
# Round 37: the shadow's own ignore list on the airship takes the spawned boxes
assert L.eval("select(2, G.NoLandShadow())") == "the player is not riding the airship"
L.execute(r"""
local items = { { get = function() return { GetFName = function() return fname("SomeActor") end } end },
                { get = function() return { GetFName = function() return fname("BP_MapNonLandingArea_C_3") end } end } }
fakePawn.m_ShadowDecalSphareTraceActorsToIgnore = setmetatable({}, {
  __len = function() return #items end,
  __index = function(_, k) if k == #items + 1 then items[k] = { get = function() return { GetFName = function() return fname("grown") end } end } end return items[k] end,
  __newindex = function(_, k, v) items[k] = { get = function() return v end } end,
})
savedPawnClass = fakePawn.GetClass
fakePawn.GetClass = function() return { GetFName = function() return fname("BP_MapUnitAirShip_C") end } end
G.NoLandSpawn(500)                 -- round 38: a spawn lists the box by itself
shadowResult = { G.NoLandShadow() }
""")
assert L.eval("shadowResult[1]") == 3 and L.eval("shadowResult[2]") == 3, "listed by the spawn, and not listed twice"
names = list(L.eval("shadowResult[3]").values())
assert len(names) == 2 and names[0] == "SomeActor" and "BP_MapNonLandingArea_C_3" not in names, names
# Round 40: the continent locks. Every world-map landing point and exit lies in at most one
# continent, a box set appears for each locked one, it goes when the flag opens it, and a new
# world (a new controller name) forgets the old actors without touching them.
L.execute(r"""
continentFlags = {}
spawnCount, spawnNames = 0, {}
local spawnBefore = fakeWorld.SpawnActor
function fakeWorld:SpawnActor(cls, loc, rot)
  local a = spawnBefore(self, cls, loc, rot)
  spawnCount = spawnCount + 1
  a.nm = "BP_MapNonLandingArea_C_lock" .. spawnCount
  return a
end
savedGetFlag, savedMap = G.GetFlag, G.CurrentMap
G.GetFlag = function(i) return continentFlags[i] == true end
G.CurrentMap = function() return G.WORLD_MAP end
fakePC.GetFName = function() return fname(fakePCName or "PC_1") end
""")
BOXES = sum(len(c["boxes"]) for c in L.eval("G.CONTINENTS").values())
# Round 77: 24 boxes; Grandshelt takes the land at the stone bridge's north end from Lanzelt.
assert BOXES == 24 and len(L.eval("G.CONTINENTS")) == 10
# Round 41: boxes wait for the controller to settle (a world still arriving lost its first set)
SETTLE = L.eval("G.CONTINENT_SETTLE")
def sync():
    """ContinentSync as always three values: placed, removed and the listing line (False if none)."""
    return L.execute("local a, b, c = G.ContinentSync(); return a, b, c or false")
def settle():
    for _ in range(SETTLE - 1):
        early, gone, _ = sync()
        assert len(early) == 0 and len(gone) == 0, "nothing goes in before the world settles"
settle()
assert L.eval("spawnCount") == 0
placed, removed, line = sync()
assert len(placed) == 10 and len(removed) == 0, (placed, removed)
assert L.eval("spawnCount") == BOXES
assert line.startswith(f"{BOXES} boxes on the airship's shadow list") and line.endswith(", 0 null)"), line
listed = L.eval("#fakePawn.m_ShadowDecalSphareTraceActorsToIgnore")
assert listed >= BOXES, listed
placed, removed, line = sync()
assert len(placed) == 0 and len(removed) == 0 and L.eval("spawnCount") == BOXES, "nothing to do the second time"
L.execute("continentFlags[1428] = true")   # Pharm opens
placed, removed, line = sync()
assert list(removed.values()) == ["pharm"] and len(placed) == 0, list(removed.values())
assert "open [pharm]; locked [grandshelt," in L.eval("G.ContinentStatus()"), L.eval("G.ContinentStatus()")
# a box lost to a map change comes back; the open continent does not
L.execute("""for _, a in ipairs(nolandActors) do if a.nm:find("lock", 1, true) then a.IsValid = function() error("stale pointer touched") end end end
fakePCName = "PC_2" """)
before = L.eval("spawnCount")
settle()
placed, removed, line = sync()
assert len(placed) == 9 and "pharm" not in list(placed.values()), list(placed.values())
assert L.eval("spawnCount") == before + BOXES - 3, "the 3 Pharm boxes stay out"
assert L.eval("select(2, G.SetContinentOpen('narnia', true))") == "no continent named narnia"
# Round 41: the crash on boarding. A null entry in the list must never be asked its name, and a
# list the game filled again (a different length) takes the boxes again.
L.execute(r"""
nullNameAsked = false
local nullObject = { IsValid = function() return false end,
                     GetFName = function() nullNameAsked = true; error("access violation") end }
local shadow = fakePawn.m_ShadowDecalSphareTraceActorsToIgnore
shadow[#shadow + 1] = nullObject
""")
placed, removed, line = sync()
assert line and line.endswith(", 1 null)"), line
assert L.eval("nullNameAsked") is False, "a null entry was asked its name"
placed, removed, line = sync()
assert line is False, "the same list is not gone over again"
# Round 42: the load hook places the boxes in the new world at once, with no settling, and the
# sync that follows adopts them instead of placing a second set
L.execute(r"""
hookWorld = setmetatable({ IsValid = function() return true end, GetFName = function() return fname("Wld_PL") end },
                         { __index = fakeWorld })
function hookWorld:SpawnActor(cls, loc, rot) return fakeWorld.SpawnActor(fakeWorld, cls, loc, rot) end
fakePCName = "PC_3"
""")
before = L.eval("spawnCount")
placed, why = L.execute("return G.ContinentMapLoaded(hookWorld, true)")
assert len(placed) == 9 and L.eval("spawnCount") == before + BOXES - 3, (len(placed), L.eval("spawnCount") - before)
placed, removed, line = sync()
assert len(placed) == 0 and L.eval("spawnCount") == before + BOXES - 3, "the sync adopts the hook's boxes"
assert line and f"{BOXES - 3} boxes" in line, line
# Round 67: a walking crossing holds while either side is locked and goes once both are open.
# A map load forgets it, and the next sync places it again.
L.execute("""crossingList = { { a = 'grandshelt', b = 'lanzelt', x = 14000, y = 17600, z = 120, yaw = 90, scale = 3 },
                              { a = 'pharm', b = 'mysidia', x = -9000, y = -9000, z = 50, yaw = 0, scale = 2 } }""")
GRANDSHELT, LANZELT = 1420, 1421
def crossings():
    return L.execute("return G.CrossingSync(crossingList)")
before = L.eval("spawnCount")
assert crossings() == (2, 0) and L.eval("spawnCount") == before + 2, "Pharm is open, Mysidia is not"
last = L.eval("spawnedActors[#spawnedActors - 1]")
assert (last.x, last.y, last.yaw, last.scale, last.cls) == (14000, 17600, 90, 3, "BP_MapGimmick_BlockingBase_Wld01Gra_01_C")
assert crossings() == (0, 0), "placed once"
L.execute(f"continentFlags[{GRANDSHELT}] = true")
assert crossings() == (0, 0), "Lanzelt is still locked"
near, locked, _ = L.execute("fakePawn.x, fakePawn.y = 14100, 17500; return G.CrossingNear(crossingList, 900)")
assert near.a == "grandshelt" and list(locked.values()) == ["lanzelt"], list(locked.values())
L.execute(f"continentFlags[{LANZELT}] = true")
assert crossings() == (0, 1) and last.dead, "both open: the blocker goes"
assert L.execute("return G.CrossingNear(crossingList, 900)") is None
L.execute("""for _, list in ipairs({ spawnedActors, nolandActors }) do
  for _, a in ipairs(list) do if a.nm and a.nm:find("lock", 1, true) or a.cls then a.dead = true end end
end
G.ContinentMapLoaded(hookWorld, false)""")
assert crossings() == (1, 0), "a map load forgets them: the closed one is placed again"
L.execute(f"continentFlags[{GRANDSHELT}], continentFlags[{LANZELT}] = nil, nil")
L.execute("fakePawn.x, fakePawn.y = 100.0, 200.0; G.CrossingClear()")
assert L.eval("spawnedActors[#spawnedActors].dead"), "CrossingClear removes them"
# another map, or the switch off: the old boxes are forgotten and nothing is placed
L.execute("hookWorld.GetFName = function() return fname('Town_02Lan') end")
before = L.eval("spawnCount")
assert L.eval("select(2, G.ContinentMapLoaded(hookWorld, true))") == "not the world map"
assert L.eval("select(2, G.ContinentMapLoaded(hookWorld, false))") == "locks off"
assert L.eval("spawnCount") == before and "0 boxes placed" in L.eval("G.ContinentStatus()")
L.execute("hookWorld.GetFName = function() return fname('Wld_PL') end")
# off the world map, nothing happens
L.execute("G.CurrentMap = function() return 2070 end")
assert L.eval("select(2, G.ContinentSync())") == "not on the world map"
L.execute("G.CurrentMap = function() return G.WORLD_MAP end; G.ContinentClear()")
assert "0 boxes placed" in L.eval("G.ContinentStatus()")
L.execute("G.GetFlag, G.CurrentMap = savedGetFlag, savedMap; fakePC.GetFName = nil")
# on foot the shadow list is left alone: that field does not exist on a walking pawn
L.execute("fakePawn.GetClass = function() return { GetFName = function() return fname('BP_MapUnit_Player_C') end } end")
assert L.eval("select(2, G.NoLandShadow())") == "the player is not riding the airship"
L.execute("fakePawn.GetClass = savedPawnClass")

# the rectangles against the game's own points: each is in one continent at most, the right one
import csv as _csv
_rows = lambda n: list(_csv.DictReader(open(paths.REPO / "data/game" / n, encoding="utf8"), delimiter="\t"))
_conts = {c["name"]: [tuple(b.values()) for b in c["boxes"].values()] for c in L.eval("G.CONTINENTS").values()}
def _in(x, y):
    return [n for n, bs in _conts.items() if any(b[0] <= x <= b[2] and b[1] <= y <= b[3] for b in bs)]
_names = list(_conts)
for _i, _a in enumerate(_names):
    for _b in _names[_i + 1:]:
        for _p in _conts[_a]:
            for _q in _conts[_b]:
                assert not (_p[0] < _q[2] and _q[0] < _p[2] and _p[1] < _q[3] and _q[1] < _p[3]), (_a, _b, _p, _q)
_points = [(float(r["x"]), float(r["y"]), r["id"]) for r in _rows("gimmicks.tsv") if r["class"] == "BP_MapAirShipLandingPoint_C"]
_points += [(float(r["x"]), float(r["y"]), r["toMap"]) for r in _rows("transitions.tsv") if r["map"] == "1000" and r["x"]]
assert len(_points) > 150
_where = {_p: _in(_p[0], _p[1]) for _p in _points}
assert all(len(v) <= 1 for v in _where.values()), [k for k, v in _where.items() if len(v) > 1]
assert [k for k, v in _where.items() if not v] == [(-3498.0, -8440.0, "3280")], "only the Crystal Tower's exit is in no continent"
for _px, _py, _name in ((12460, 20700, "grandshelt"), (12470, 14980, "lanzelt"), (5812, 14044, "kolobos"), (13190, 3210, "dirnado"),
                        (-90, 2680, "olderion"), (-7200, 7200, "zoldaad"), (-17515, -8365, "mysidia"), (15895, -14150, "gronoa"),
                        (-3920, -17480, "pharm")):
    assert _in(_px, _py) == [_name], (_px, _py, _in(_px, _py))
assert not _in(-5935, -8305), "the air start is over the sea, in no continent"
# Round 69: each start on foot is on its own continent
for _name, _a in L.eval("G.FOOT_STARTS").items():
    assert _in(_a.x, _a.y) == [_name], (_name, _in(_a.x, _a.y))
assert len(list(L.eval("G.FOOT_STARTS").items())) == 9
# Round 118: each start on foot is a landing point, and `landing` is that point's id
_landing = {(float(r["x"]), float(r["y"])): int(r["id"]) for r in _rows("gimmicks.tsv") if r["class"] == "BP_MapAirShipLandingPoint_C"}
for _name, _a in L.eval("G.FOOT_STARTS").items():
    assert _landing.get((_a.x, _a.y)) == _a.landing, (_name, _a.landing, _landing.get((_a.x, _a.y)))
# Round 67: each built-in walking crossing stands in one of the two continents it joins
for _c in L.eval("G.CROSSINGS").values():
    assert _in(_c.x, _c.y)[0] in (_c.a, _c.b), (_c.a, _c.b, _in(_c.x, _c.y))
# the rectangles are one table in two places: the apworld's data and the mod's
_tsv = {}
for r in _rows("../continents.tsv"):
    _tsv.setdefault(r["name"], []).append((int(r["x0"]), int(r["y0"]), int(r["x1"]), int(r["y1"])))
assert _tsv == _conts, "data/continents.tsv and G.CONTINENTS differ"
_flags = {c["name"]: c["flag"] for c in L.eval("G.CONTINENTS").values()}
assert {r["name"]: int(r["flag"]) for r in _rows("../continents.tsv")} == _flags
print("continent locks: ok")

L.execute("fakePawn.m_ShadowDecalSphareTraceActorsToIgnore = nil; G.NoLandOff()")
L.execute(f"groundZ = {HIGH_GROUND}")
hits = [dict(h) for h in L.eval("G.GroundUnder()").values()]
assert hits == [{"name": "Landscape_1", "z": HIGH_GROUND, "box": False}], hits
L.execute("G.NoLandOff()")
print("no-landing boxes: ok")

# 0.17.0: the input probe (the opening's input lock, round 9). The state reads the controller's
# switches; fix runs the engine's resets in order, says each step first, and reports a failure.
L.execute(r"""
fakePC.moveIgnored, fakePC.lookIgnored, fakePC.calls = true, true, {}
function fakePC:GetFName() return fname("BP_PlayerController_C_0") end
function fakePC:IsMoveInputIgnored() return self.moveIgnored end
function fakePC:IsLookInputIgnored() return self.lookIgnored end
function fakePC:ResetIgnoreInputFlags() self.moveIgnored, self.lookIgnored = false, false; self.calls[#self.calls + 1] = "reset" end
function fakePC:EnableInput(pc) error("EnableInput is not callable here") end
local wbl = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
              HasAnyFlags = function() return false end }
function wbl:SetInputMode_GameOnly(pc, flush) pc.calls[#pc.calls + 1] = "game only " .. tostring(flush) end
local prevSFO7 = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/UMG.Default__WidgetBlueprintLibrary" then return wbl end
  return prevSFO7(p)
end
inputSteps = {}
""")
state = L.eval("G.InputState()")
assert state == ("controller BP_PlayerController_C_0, pawn BP_MapUnit_Player_Field_C, move input ignored true, "
                 "look input ignored true; no CPP_InputManager"), state
failed = list(L.eval("G.InputFix(function(s) inputSteps[#inputSteps + 1] = s end)").values())
assert list(L.eval("inputSteps").values()) == ["ResetIgnoreInputFlags", "EnableInput", "SetInputMode_GameOnly"]
assert len(failed) == 1 and failed[0].startswith("EnableInput: "), failed
assert list(L.eval("fakePC.calls").values()) == ["reset", "game only false"]
assert "move input ignored false" in L.eval("G.InputState()")
# 0.18.0 (round 36: the controller's switches were false even in the locked game): the game's
# own input manager. Its state goes on the line, and fix calls its EnableInput and its
# ReregistrationCurrentMappingContext before the engine's resets.
L.execute(r"""
inputMgr = { enabled = false, calls = {} }
function inputMgr:IsValid() return true end
function inputMgr:HasAnyInternalFlags() return false end
function inputMgr:HasAnyFlags() return false end
function inputMgr:IsEnableInput() return self.enabled end
function inputMgr:GetCurrentInputModeDebugString() return { ToString = function() return "UIOnly" end } end
function inputMgr:GetAllIMCStackList()
  -- Round 37: an element comes back in a wrapper, and the object is inside it
  local imc = { GetFName = function() return fname("IMC_Event") end }
  return { { get = function() return imc end } }
end
function inputMgr:EnableInput() self.enabled = true; self.calls[#self.calls + 1] = "enable" end
function inputMgr:ReregistrationCurrentMappingContext() self.calls[#self.calls + 1] = "reregister" end
local prevFFO8 = FindFirstOf
function FindFirstOf(c) if c == "CPP_InputManager" then return inputMgr end return prevFFO8(c) end
inputSteps = {}
""")
state = L.eval("G.InputState()")
assert state.endswith("; input manager: enabled false, mode UIOnly, mapping contexts 1 [IMC_Event]"), state
failed = list(L.eval("G.InputFix(function(s) inputSteps[#inputSteps + 1] = s end)").values())
assert list(L.eval("inputSteps").values())[:2] == ["CPP_InputManager:EnableInput",
                                                  "CPP_InputManager:ReregistrationCurrentMappingContext"]
assert list(L.eval("inputMgr.calls").values()) == ["enable", "reregister"]
assert "input manager: enabled true" in L.eval("G.InputState()")
print("input probe: ok")

# Round 37: the first vision's synchro keys, for a save with no vision to copy them from
L.execute(r"""
visionSD = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
             HasAnyFlags = function() return false end, visionList = {} }
savedSaveData = G.SaveData
G.SaveData = function() return visionSD end
""")
assert L.eval("G.VisionKeys()") == "visionList is empty"
L.execute(r"""
local keys = { 1001, 1002 }
visionSD.visionList = { { ID = 13017, synchroPoints = { ForEach = function(_, fn)
  for _, k in ipairs(keys) do fn({ get = function() return k end }) end end } } }
""")
assert L.eval("G.VisionKeys()") == "1 visions; the first is 13017, its synchro keys [1001, 1002]", L.eval("G.VisionKeys()")
# Round 38: a save with no vision gets the entry with its keys written, with nothing to copy
L.execute(r"""
local owned = {}
local function fobj(t) t.IsValid = function() return true end; t.HasAnyInternalFlags = function() return false end
  t.HasAnyFlags = function() return false end; return t end
local visionLib = fobj({ HasVision = function(_, id) return owned[id] == true end })
local invLib = fobj({ AddInventory = function(_, id) owned[id] = true end })
local visionTable = fobj({ ForEachRow = function(_, fn) fn(nil, { ID = 13017 }) end })
local prevSFO9 = StaticFindObject
function StaticFindObject(p)
  if p:find("CPP_BFL_Vision", 1, true) then return visionLib end
  if p:find("CPP_BFL_SaveDataInventory", 1, true) then return invLib end
  if p:find("DT_VisionItemData", 1, true) then return visionTable end
  return prevSFO9(p)
end
visionItems = {}
visionSD.visionList = setmetatable({}, {
  __len = function() return #visionItems end,
  __index = function(_, k)
    if k == #visionItems + 1 then
      local keys = { n = 0 }
      visionItems[k] = { ID = 0, awakeningPoint = 1, synchroPoints = { Add = function(_, key, v) keys.n = keys.n + 1; keys[key] = v end }, keys = keys }
    end
    return visionItems[k]
  end,
})
G.SaveData = function() return visionSD end
""")
code, detail = L.execute("return G.UnlockVision(13017)")
assert code == "ok" and "visionList 0 -> 1, synchro keys 8" in detail, (code, detail)
assert L.eval("visionItems[1].ID") == 13017 and L.eval("visionItems[1].awakeningPoint") == 0
assert L.eval("visionItems[1].keys.n") == 8 and L.eval("visionItems[1].keys[1006]") == 0
L.execute("G.SaveData = savedSaveData")

# Round 50: the player's settings. Reward rates are multiples of the shipped ones (MRP is 1.5 on
# Expert); encounters off clears doMovementEncount and puts the player's distance out of reach;
# a rate divides the walking distances; back on, everything is as first seen.
L.execute("""
diffRows = { Easy = { ExpRate = 1, MoneyRate = 1, MRPointRate = 1 }, Expert = { ExpRate = 1, MoneyRate = 1, MRPointRate = 1.5 } }
diffDT = { IsValid = function() return true end, GetFullName = function() return "DataTable DT_GameDifficultyParam" end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end }
function diffDT:ForEachRow(fn) for k, r in pairs(diffRows) do fn(fname(k), r) end end
mapRow = { doMovementEncount = true, encountMinMovementLength = 800, encountMaxMovementLength = 1600,
           chocoboEncountMinMovementLength = 2000, chocoboEncountMaxMovementLength = 4000 }
mapDT = { IsValid = function() return true end, GetFullName = function() return "DataTable DT_MapData_01Gra" end,
  HasAnyInternalFlags = function() return false end, HasAnyFlags = function() return false end,
  GetRowStruct = function() return { GetFName = function() return { ToString = function() return "MAP_DATA" end } end } end }
function mapDT:ForEachRow(fn) fn(fname("1000"), mapRow) end
walker = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
  HasAnyFlags = function() return false end, GetFullName = function() return "BP_MapUnit_Player_Field_C /Game/Map.Player" end,
  m_EncountThresholdDistance = 1234 }
local prevSFOd = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Difficulty/DT_GameDifficultyParam.DT_GameDifficultyParam" then return diffDT end
  return prevSFOd(p)
end
local prevFAOd = FindAllOf
function FindAllOf(c)
  if c == "DataTable" then return { mapDT } end
  if c == "CPP_MapUnit_Playable" then return { walker } end
  return prevFAOd(c)
end
""")
assert L.eval("G.ApplyRates(2, 3, 0.5)") == 2
assert L.eval("diffRows.Easy.ExpRate") == 2 and L.eval("diffRows.Easy.MoneyRate") == 3
assert L.eval("diffRows.Expert.MRPointRate") == 0.75, "a multiple of Expert's shipped 1.5"
assert L.eval("G.ApplyRates(2, 3, 0.5)") == 0, "nothing to write twice"
rows, tables = L.execute("return G.ApplyEncounterTables(false, 1)")
assert (rows, tables) == (1, 1) and L.eval("mapRow.doMovementEncount") is False
assert L.eval("G.ApplyPlayerEncounter(false)") == 1 and L.eval("walker.m_EncountThresholdDistance") == 1.0e9
assert L.eval("G.ApplyPlayerEncounter(false)") == 0, "once"
L.execute("G.ApplyEncounterTables(true, 2)")
assert L.eval("mapRow.doMovementEncount") is True and L.eval("mapRow.encountMinMovementLength") == 400, "twice the battles"
assert L.eval("mapRow.chocoboEncountMaxMovementLength") == 2000
assert L.eval("G.ApplyPlayerEncounter(true)") == 1 and L.eval("walker.m_EncountThresholdDistance") == 1234
L.execute("G.ApplyEncounterTables(true, 1); G.ApplyRates(1, 1, 1)")
assert L.eval("mapRow.encountMaxMovementLength") == 1600 and L.eval("diffRows.Expert.MRPointRate") == 1.5
print("settings: ok")

# Round 67: the ferry. Each port's menu (from story 3210) offers the other three ports; a port on a
# locked continent runs the menu's cancel row instead of the trip. The rows are written in every
# table of the talk family, and only when they differ.
L.execute(r"""
local function menu(ports, cancel)
  local branches = {}
  for i, p in ipairs(ports) do branches[i] = { EventList = { { EventId = FName(string.format("Gim_EV_ShipMovement_%02d_Cushion", p)) } } } end
  branches[#branches + 1] = { EventList = { { EventId = FName(cancel) } } }
  return { ChoicesBranchEventList = branches }
end
local function talkTable(name, parents)
  local t = { rows = {
      Gim_EV_ShipMovement_01_03_Choice = menu({ 2, 3, 4 }, "Gim_EV_ShipMovement_Cancel_Gra"),
      Gim_EV_ShipMovement_02_03_Choice = menu({ 1, 3, 4 }, "Gim_EV_ShipMovement_Cancel"),
      Gim_EV_ShipMovement_03_02_Choice = menu({ 1, 2, 4 }, "Gim_EV_ShipMovement_Cancel"),
      Gim_EV_ShipMovement_04_01_Choice = menu({ 1, 2, 3 }, "Gim_EV_ShipMovement_Cancel"),
      SubEv_C05_TreasureRadar_01_01 = { ObtainItemList = { { ID = 20016, Num = 1 } } },
      SubEv_C05_TreasureRadar_01_13 = { ObtainItemList = { { ID = 12059, Num = 1 } } },
      SubEv_Dng_06Zol_44_GimEv_03_A = { ObtainItemList = { { ID = 20021, Num = 1 } } },
      SubEv_Dng_06Zol_44_GimEv_03_B = { ObtainItemList = { { ID = 20021, Num = 1 } } },
      SubEv_Dng_06Zol_44_GimEv_04 = { ObtainItemList = { { ID = 20, Num = 1 } } },
      C01_ArijigokuWin = { ContinuousEventList = {
        { Condition = "!{flag:10}", EventId = FName("C01_ArijigokuWin_01") },
        { Condition = "{flag:10}", EventId = FName("C01_ArijigokuWin_02") } } },
      C06_AileenWeapon_06 = { ContinuousEventList = {
        { Condition = "{item:10190}==1", EventId = FName("C06_AileenWeapon_06_complete") },
        { Condition = "{item:20016}==0", EventId = FName("C06_AileenWeapon_06_Nohave") } } } },
    ParentTables = parents or {} }
  function t:IsValid() return true end
  function t:HasAnyInternalFlags() return false end
  function t:HasAnyFlags() return false end
  function t:GetFullName() return "DataTable " .. name end
  function t:FindRow(n) return self.rows[n] end
  function t:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
  return t
end
gimTalk = talkTable("DT_TalkEventData_GimEV_Prod")
cdtTalk = talkTable("CDT_TalkEventData_Prod", { gimTalk })
local prevSFOf = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.CDT_TalkEventData_Prod" then return cdtTalk end
  return prevSFOf(p)
end
ferryFlags = { [1421] = true, [1424] = true }   -- Lanzelt and Olderion open
ferrySavedGetFlag = G.GetFlag
G.GetFlag = function(i) return ferryFlags[i] == true end
function ferryChoice(t, row, i) return t.rows[row].ChoicesBranchEventList[i].EventList[1].EventId:ToString() end
""")
# Dirnado and Zoldaad are each in the other three ports' menus, and there are two tables
CLOSED_CHOICES = 2 * 3 * 2
written = L.eval("G.FerrySync()")
assert written == CLOSED_CHOICES, written
for table in ("cdtTalk", "gimTalk"):
    choice = lambda row, i: L.eval(f"ferryChoice({table}, '{row}', {i})")
    assert choice("Gim_EV_ShipMovement_01_03_Choice", 1) == "Gim_EV_ShipMovement_Cancel_Gra", "Grandport to Dirnado"
    assert choice("Gim_EV_ShipMovement_01_03_Choice", 2) == "Gim_EV_ShipMovement_03_Cushion", "Grandport to Olderion"
    assert choice("Gim_EV_ShipMovement_01_03_Choice", 4) == "Gim_EV_ShipMovement_Cancel_Gra", "no stays no"
    assert choice("Gim_EV_ShipMovement_03_02_Choice", 1) == "Gim_EV_ShipMovement_01_Cushion", "Olderion to Grandport"
    assert choice("Gim_EV_ShipMovement_03_02_Choice", 3) == "Gim_EV_ShipMovement_Cancel", "Olderion to Zoldaad"
assert L.eval("G.FerrySync()") == 0, "nothing to write the second time"
L.execute("ferryFlags[1423], ferryFlags[1425] = true, true")
assert L.eval("G.FerrySync()") == CLOSED_CHOICES
assert L.eval("ferryChoice(gimTalk, 'Gim_EV_ShipMovement_02_03_Choice', 3)") == "Gim_EV_ShipMovement_04_Cushion"
assert L.eval("ferryChoice(cdtTalk, 'Gim_EV_ShipMovement_01_03_Choice', 1)") == "Gim_EV_ShipMovement_02_Cushion"
# Round 85: a save not linked to the seed gets every trip back, whatever its flags say
L.execute("ferryFlags = {}")
assert L.eval("G.FerrySync(true)") == 0, "every trip already open"
assert L.eval("G.FerrySync()") == 2 * 3 * 4, "closed again by the flags"
assert L.eval("G.FerrySync(true)") == 2 * 3 * 4
assert L.eval("ferryChoice(gimTalk, 'Gim_EV_ShipMovement_03_02_Choice', 3)") == "Gim_EV_ShipMovement_04_Cushion"
L.execute("G.GetFlag = ferrySavedGetFlag")
print("ferry: ok")

# Round 69: a win over the Antlion always runs the row that sets flag 113, so the sandpit clears
# for good with or without story flag 10. One choice to change in each of the two tables.
ANTLION_CHOICES_TO_CHANGE = 2
assert L.eval("G.AntlionPatch()") == ANTLION_CHOICES_TO_CHANGE
for table in ("cdtTalk", "gimTalk"):
    for i in (1, 2):
        assert L.eval(f"{table}.rows.C01_ArijigokuWin.ContinuousEventList[{i}].EventId:ToString()") == "C01_ArijigokuWin_02"
assert L.eval("G.AntlionPatch()") == 0, "nothing to write the second time"
print("antlion: ok")

# Round 105: Aileen's forge ends (progress 38 to 70) only with all eight weapons held, not as soon
# as Rain's is. The row's other branches stay. One row in each of the two tables.
ALL_EIGHT = ("{item:10190}>=1&{item:10290}>=1&{item:10390}>=1&{item:10490}>=1&{item:10590}>=1"
             "&{item:10790}>=1&{item:10890}>=1&{item:10690}>=1")
assert L.eval("G.ForgePatch()") == 2
for table in ("cdtTalk", "gimTalk"):
    assert L.eval(f"{table}.rows.C06_AileenWeapon_06.ContinuousEventList[1].Condition") == ALL_EIGHT
    assert L.eval(f"{table}.rows.C06_AileenWeapon_06.ContinuousEventList[2].Condition") == "{item:20016}==0"
assert L.eval("G.ForgePatch()") == 0, "nothing to write the second time"
print("forge: ok")

# Round 107 (the user): Zoldaad Castle's squad leader gave the Throne Room Key out of logic. Both
# of his answers give the stand-in, in both tables; the spy's row next to them is left alone. His
# walk-in trigger is turned off on the map, once per trigger the game makes.
THRONE_KEY, STAND_IN, SPY_GIFT = 20021, 1, 20
SQUAD_LEADER_ROWS = 2 * 2
assert L.eval("G.ThroneKeyRowsPatch()") == SQUAD_LEADER_ROWS
for table in ("cdtTalk", "gimTalk"):
    for row in ("SubEv_Dng_06Zol_44_GimEv_03_A", "SubEv_Dng_06Zol_44_GimEv_03_B"):
        assert L.eval(f"{table}.rows.{row}.ObtainItemList[1].ID") == STAND_IN, (table, row)
    assert L.eval(f"{table}.rows.SubEv_Dng_06Zol_44_GimEv_04.ObtainItemList[1].ID") == SPY_GIFT
assert L.eval("G.ThroneKeyRowsPatch()") == 0, "nothing to write the second time"
L.execute(r'''
local function trigger(event)
  local a = { m_EventList = { { Condition = "{item:20021}==0", EventId = FName(event) } }, m_GimmickCondition = 0, collision = true }
  function a:IsValid() return true end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  function a:SetActorEnableCollision(on) self.collision = on end
  function a:SetGimmickCondition(c) self.m_GimmickCondition = c end
  return a
end
squadLeader, otherTrigger = trigger("SubEv_Dng_06Zol_44_GimEv_03"), trigger("SubEv_Dng_06Zol_44_GimEv_05_01")
local prevFAOThrone = FindAllOf
function FindAllOf(c) if c == "CPP_MapGimmick_EventTrigger" then return { squadLeader, otherTrigger } end return prevFAOThrone(c) end
''')
assert L.eval("G.ThroneKeyTriggerOff()") == 1
assert L.eval("squadLeader.m_EventList[1].Condition") == "{progress:0}<0"
assert L.eval("squadLeader.collision") is False and L.eval("squadLeader.m_GimmickCondition") == 1, "off"
assert L.eval("otherTrigger.m_EventList[1].Condition") == "{item:20021}==0" and L.eval("otherTrigger.collision") is True
assert L.eval("G.ThroneKeyTriggerOff()") == 0, "once per trigger"
print("throne key: ok")

# Round 108: the man by Sian's inn says his line from before the cabin in place of the one that
# gives the Cabin Key. His other entries, and other NPCs, are left alone.
L.execute(r'''
local function npc(events)
  local entries = {}
  for i, e in ipairs(events) do entries[i] = { Condition = "", EventList = { { EventId = FName(e) } } } end
  local a = { m_EventSettings = { EventList = entries } }
  function a:IsValid() return true end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  return a
end
cabinMan = npc({ "FEV_Town_09Pha_01_1044_01", "FEV_Town_09Pha_01_1044_02", "FEV_Town_09Pha_01_1044_03" })
otherNpc = npc({ "FEV_Town_09Pha_01_1050_01" })
local prevFAOCabin = FindAllOf
function FindAllOf(c) if c == "BP_MapUnit_NPC_C" then return { otherNpc, cabinMan } end return prevFAOCabin(c) end
''')
assert L.eval("G.CabinKeyManOff()") == 1
before_cabin = "FEV_Town_09Pha_01_1044_01"
assert L.eval("cabinMan.m_EventSettings.EventList[2].EventList[1].EventId:ToString()") == before_cabin
assert L.eval("cabinMan.m_EventSettings.EventList[3].EventList[1].EventId:ToString()") == "FEV_Town_09Pha_01_1044_03"
assert L.eval("otherNpc.m_EventSettings.EventList[1].EventList[1].EventId:ToString()") == "FEV_Town_09Pha_01_1050_01"
assert L.eval("G.CabinKeyManOff()") == 0, "once per NPC"
print("cabin key: ok")

# Round 116: a stutter like a heartbeat on slower PCs. The shiny scan searched every map gimmick
# each second and read each one's class. Every field item Blueprint comes from
# CPP_MapGimmick_FieldItem, so it is the only search.
L.execute(r'''
local function shiny(uid, class)
  local a = { m_UniqueId = uid, bHidden = false, interactType = 0, m_IsOpen = false, m_ItemId = 16, m_ItemNum = 1,
              m_Money = -1, VisibleCondition = { ToString = function() return "" end } }
  function a:IsValid() return true end
  function a:HasAnyInternalFlags() return false end
  function a:HasAnyFlags() return false end
  function a:GetClass() return { GetFName = function() return { ToString = function() return class end } end } end
  function a:K2_GetActorLocation() return { X = 1, Y = 2, Z = 3 } end
  return a
end
fieldSearches = {}
local medal, plain = shiny(8, "BP_MapGimmick_FieldItem_Medal_C"), shiny(9, "BP_MapGimmick_FieldItem_C")
local prevFAOFields = FindAllOf
function FindAllOf(c)
  fieldSearches[#fieldSearches + 1] = c
  if c == "CPP_MapGimmick_FieldItem" then return { medal, plain } end
  return prevFAOFields(c)
end
fieldItems = G.LiveFieldItems()
FindAllOf = prevFAOFields
''')
assert list(L.eval("fieldSearches").values()) == ["CPP_MapGimmick_FieldItem"], list(L.eval("fieldSearches").values())
assert [L.eval(f"fieldItems[{i}].class") for i in (1, 2)] == ["BP_MapGimmick_FieldItem_Medal_C", "BP_MapGimmick_FieldItem_C"]
assert L.eval("fieldItems[1].uid") == 8 and L.eval("fieldItems[2].itemId") == 16
print("field items, one search: ok")

# Round 108 (a tester): a quest scene visited Grandport with Lanzelt locked, and fast travel took
# the player there. Maps of a locked continent are marked not visited, but the map the player is
# on. An open continent's maps, and maps of no continent (the battlefield), stay.
GRANDPORT, OBLIVION_PALACE, KOL, OLDERION_TOWN, BATTLEFIELD = 2030, 2031, 2040, 2070, 5010
LANZELT_FLAG, KOLOBOS_FLAG = 1421, 1422
L.execute(f"""
local sd = makeSave({{false}}, {{ {{SaveId=1, JoinStatus=0}} }}, 8000, 1, true)
local function seen() return {{ bIsKnown = true, bIsVisited = true, bIsCleared = false }} end
sd.Map = {{ perMapSaveDataMap = map({{
  {{ {GRANDPORT}, seen() }}, {{ {OBLIVION_PALACE}, seen() }}, {{ {KOL}, seen() }},
  {{ {OLDERION_TOWN}, seen() }}, {{ {BATTLEFIELD}, seen() }},
}}) }}
mgr.m_pGameSaveData = sd
saveMaps = sd.Map.perMapSaveDataMap
prevGetFlag108, prevCurrentMap108 = G.GetFlag, G.CurrentMap
function G.GetFlag(i) return i ~= {LANZELT_FLAG} and i ~= {KOLOBOS_FLAG} end
here108 = {OBLIVION_PALACE}
function G.CurrentMap() return here108 end
""")
L.execute("""
function visited108(m)
  local out
  saveMaps:ForEach(function(k, v) if k:get() == m then out = v:get().bIsVisited end end)
  return out
end
""")
assert sorted(L.eval("G.UnvisitLocked()").values()) == [GRANDPORT, KOL]
assert L.eval(f"visited108({GRANDPORT})") is False and L.eval(f"visited108({KOL})") is False
# Round 117: fast travel still went to Grandport marked not visited; the map is made unknown too.
L.execute("function known117(m) local out; saveMaps:ForEach(function(k, v) if k:get() == m then out = v:get().bIsKnown end end); return out end")
assert L.eval(f"known117({GRANDPORT})") is False and L.eval(f"known117({OLDERION_TOWN})") is True
assert L.eval(f"visited108({OBLIVION_PALACE})") is True, "the player is there"
assert L.eval(f"visited108({OLDERION_TOWN})") is True and L.eval(f"visited108({BATTLEFIELD})") is True
assert len(L.eval("G.UnvisitLocked()")) == 0, "nothing more to clear"
# Round 117: on an open continent, a place not walked in is marked the same way; the walked ones stay
assert L.eval("G.CONTINENT_OF[2070]") == "olderion" and L.eval("G.CONTINENT_OF[5010]") is None
assert sorted(L.eval("G.VisitedMaps()").values()) == [OBLIVION_PALACE, OLDERION_TOWN]
assert len(L.eval(f"G.UnvisitLocked({{ [{OLDERION_TOWN}] = true }})")) == 0, "walked in"
assert list(L.eval("G.UnvisitLocked({})").values()) == [OLDERION_TOWN], "a scene's visit"
assert L.eval(f"visited108({OLDERION_TOWN})") is False and L.eval(f"known117({OLDERION_TOWN})") is False
L.execute(f"saveMaps:ForEach(function(k, v) if k:get() == {OLDERION_TOWN} then local r = v:get(); r.bIsVisited, r.bIsKnown = true, true end end)")
# Round 117 probe (ffrap_visited): the row's marks, written only when asked
assert L.eval(f"G.MapMarks({OLDERION_TOWN})").startswith(f"map {OLDERION_TOWN}: row known true, visited true")
assert L.eval(f"G.MapMarks({OLDERION_TOWN}, true, false)").startswith(f"map {OLDERION_TOWN}: row known true, visited false")
assert L.eval(f"known117({OLDERION_TOWN})") is True and L.eval(f"visited108({OLDERION_TOWN})") is False
assert L.eval("G.MapMarks(9999)") == "map 9999: no row in the save"
L.execute("G.GetFlag, G.CurrentMap = prevGetFlag108, prevCurrentMap108; mgr.m_pGameSaveData = nil")
assert L.eval("G.MapMarks(2070)") == "no save"
assert len(L.eval("G.UnvisitLocked()")) == 0, "no save: nothing"

# Round 113 (the user): lifts keep their stop in the save (Map.mapGimmick{map}.gimmickState{uid}).
# Off their map, the lifts in G.LIFT_RESETS go back to their first-visit stop. Other gimmicks' rows
# and the map the player is on stay. Round 114: the last raft of Cave of Waters and the Water
# Shrine is taken out too (a first visit has none); another map's row stays.
WIND_SHRINE, TOWER_OF_MYSIDIA, CAVE_OF_WATERS, WATER_SHRINE, RAFT_TOWN = 3070, 3200, 3080, 3110, 2090
TOWER_LIFT_UP, TOWER_LIFT_DOWN, TOWER_SWITCH, WIND_LIFT, CAVE_RAFT, SHRINE_RAFT = 13, 32, 50, 71, 47, 66
L.execute(f"""
local sd = makeSave({{false}}, {{ {{SaveId=1, JoinStatus=0}} }}, 8000, 1, true)
local function stop(v) return {{ Value = v, value2 = 0, State = 0 }} end
sd.Map = {{ mapGimmick = map({{
  {{ {TOWER_OF_MYSIDIA}, {{ gimmickState = map({{ {{ {TOWER_LIFT_UP}, stop(1) }}, {{ {TOWER_LIFT_DOWN}, stop(0) }},
                                             {{ {TOWER_SWITCH}, stop(1) }} }}) }} }},
  {{ {WIND_SHRINE}, {{ gimmickState = map({{ {{ {WIND_LIFT}, stop(0) }} }}) }} }},
}}), lastRideRaftMap = map({{
  {{ {CAVE_OF_WATERS}, {{ UniqueID = {CAVE_RAFT} }} }}, {{ {WATER_SHRINE}, {{ UniqueID = {SHRINE_RAFT} }} }},
  {{ {RAFT_TOWN}, {{ UniqueID = 15 }} }},
}}) }}
mgr.m_pGameSaveData = sd
towerRows = sd.Map.mapGimmick
""")
L.execute("""
function liftStop(m, uid)
  local out
  towerRows:ForEach(function(k, v)
    if k:get() == m then v:get().gimmickState:ForEach(function(u, s) if u:get() == uid then out = s:get().Value end end) end
  end)
  return out
end
""")
assert L.eval(f"G.RideState({WATER_SHRINE})") == "last raft 66", "no lift loaded: the raft alone"
assert L.eval("G.RideState(1000)") is None, "no lifts or rafts here"
assert list(L.eval(f"G.ResetRides({WATER_SHRINE})").values()) == [
    "3070:71 0 -> 1", "3080 raft 47 -> none", "3200:13 1 -> 0"], "the Wind Shrine lift's first-visit stop is 1"
assert L.eval(f"G.LastRaft({CAVE_OF_WATERS})") is None
assert L.eval(f"G.LastRaft({WATER_SHRINE})") == SHRINE_RAFT, "the player's own map stays"
assert L.eval(f"G.LastRaft({RAFT_TOWN})") == 15, "not a raft map of the table"
assert L.eval(f"liftStop({TOWER_OF_MYSIDIA}, {TOWER_LIFT_UP})") == 0
assert L.eval(f"liftStop({TOWER_OF_MYSIDIA}, {TOWER_SWITCH})") == 1, "not a lift of the table"
assert L.eval(f"liftStop({WIND_SHRINE}, {WIND_LIFT})") == 1
assert list(L.eval("G.ResetRides(1000)").values()) == ["3110 raft 66 -> none"], "the player's own map waited"
assert len(L.eval("G.ResetRides(1000)")) == 0, "nothing more to put back"
L.execute("mgr.m_pGameSaveData = nil")
assert len(L.eval("G.ResetRides(1000)")) == 0, "no save: nothing"
assert L.eval(f"G.RideState({WATER_SHRINE})") == "last raft none"

# The live stops, for the log.
L.execute(f"""
local function lift(uid, stop) return {{ m_UniqueId = uid, m_CurrentSplineKeyIndex = stop,
    IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
    HasAnyFlags = function() return false end }} end
prevFindAllOf113 = FindAllOf
function FindAllOf(c)
  if c == "BP_MapGimmick_Floor_Elevator_Interact2_004_C" then return {{ lift({TOWER_LIFT_DOWN}, 0), lift({TOWER_LIFT_UP}, 1) }} end
  return prevFindAllOf113(c)
end
""")
assert L.eval(f"G.RideState({TOWER_OF_MYSIDIA})") == "lifts 13 at 1, 32 at 0"
assert L.eval(f"G.RideState({WIND_SHRINE})") is None, "none loaded"
assert L.eval("G.RideState(1000)") is None, "no lifts here"
L.execute("FindAllOf = prevFindAllOf113")

# G.LIFT_RESETS is data/game/lifts.tsv's saved Interact2 lifts, in maps whose only way in from
# another map is the first visit's door (point 0 in transitions.tsv), with their first-visit stop.
import csv
with open(paths.REPO / "data/game/transitions.tsv", encoding="utf-8") as f:
    transitions = list(csv.DictReader(f, delimiter="\t"))
ways_in = {}
for r in transitions:
    into = [r["toMap"]] + [d.split("[")[0].strip() for d in r["destinations"].split(";")]
    for m in into:
        if m and m != r["map"]:
            ways_in.setdefault(m, set()).add(r["toPoint"])
want = {}
with open(paths.REPO / "data/game/lifts.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if "Interact2" in r["class"] and r["saved"] == "true" and ways_in.get(r["map"]) == {"0"}:
            want.setdefault(int(r["map"]), {})[int(r["uid"])] = int(r["init"])
have = {m: dict(lifts.items()) for m, lifts in L.eval("G.LIFT_RESETS").items()}
assert have == want, (have, want)
print("lifts: ok")

# The table matches maps.tsv: each continent's maps, by island.
import csv
islands = {"MagiNationMysidia": "mysidia"}
want = {}
with open(paths.REPO / "data/game/maps.tsv", encoding="utf-8") as f:
    for r in csv.DictReader(f, delimiter="\t"):
        if r["island"] not in ("None", "LandOfTheCrystals"):
            want.setdefault(islands.get(r["island"], r["island"].lower()), set()).add(int(r["id"]))
have = {name: set(maps.values()) for name, maps in L.eval("G.CONTINENT_MAPS").items()}
assert have == want, set(have) ^ set(want)
continents = {c["name"] for c in L.eval("G.CONTINENTS").values()}
assert set(have) <= continents, set(have) - continents
print("locked maps: ok")

# Round 72: a radar treasure's reward is the location's now: its dig row gives the pop-up's
# stand-in Potion (1), in both tables, once
RADAR_ROWS_TO_CHANGE = 2 * 2
assert L.eval("G.RadarPatch()") == RADAR_ROWS_TO_CHANGE
assert L.eval("gimTalk.rows.SubEv_C05_TreasureRadar_01_13.ObtainItemList[1].ID") == 1
assert L.eval("G.RadarPatch()") == 0
assert L.eval("#G.RADAR") == 13 and L.eval("G.RADAR[13].flag") == 716
print("radar rows: ok")

# Round 120: Lid's "stopped picking up treasure" line comes after the dig of treasure 5, 9 or 13
# only when that dig leaves nothing the radar can find
RADAR_NEVER = "{flag:703}&!{flag:703}"
L.execute(r"""
for n, cond in pairs({ [5] = "{progress:49}==30", [9] = "{progress:49}==40", [13] = "" }) do
  local row = gimTalk.rows[G.RADAR[n].row] or { ObtainItemList = {} }
  row.ContinuousEventList = { { Condition = cond, EventId = FName("SubEv_C05_TreasureRadar_10") } }
  gimTalk.rows[G.RADAR[n].row] = row
end
radarDug = {}
radarSavedGetFlag = G.GetFlag
G.GetFlag = function(i) return radarDug[i] == true end
""")
lid_line = lambda n: L.eval(f"gimTalk.rows[G.RADAR[{n}].row].ContinuousEventList[1].Condition")
assert L.eval("G.RadarLidLines(1)") == 3 and lid_line(5) == RADAR_NEVER, "treasures 1 to 4 left"
L.execute("for n = 1, 4 do radarDug[G.RADAR[n].flag] = true end")
assert L.eval("G.RadarLidLines(1)") == 1 and lid_line(5) == "{progress:49}==30", "5 is the last of tier 1"
assert lid_line(9) == RADAR_NEVER and lid_line(13) == RADAR_NEVER
L.execute("radarDug[G.RADAR[5].flag] = true")
assert L.eval("G.RadarLidLines(2)") == 1 and lid_line(5) == RADAR_NEVER, "tier 2's treasures are left now"
L.execute("for n = 6, 8 do radarDug[G.RADAR[n].flag] = true end")
assert L.eval("G.RadarLidLines(2)") == 1 and lid_line(9) == "{progress:49}==40"
assert L.eval("G.RadarLidLines(2)") == 0, "once"
L.execute("G.GetFlag = radarSavedGetFlag")
print("radar lines: ok")

# Round 78: a side quest's reward row loses the location's item (round 81: no stand-in Potion),
# and keeps its gil and a second item. A vision comes out too. The list here behaves like the engine's array: Empty() clears it, and reading one index
# past the end adds an element.
L.execute(r"""
local function itemList(entries)
  local items = {}
  local list = setmetatable({}, {
    __index = function(_, i)
      if i == "Empty" then return function() for k in pairs(items) do items[k] = nil end end end
      if i == #items + 1 then items[i] = { ID = 0, Num = 0 } end
      return items[i]
    end,
    __len = function() return #items end })
  for i, e in ipairs(entries) do items[i] = { ID = e[1], Num = e[2] } end
  return list
end
questRows = {
  SubEv_C01_Zairu_04 = { ObtainItemList = itemList({ { 25000, 1 }, { -1, 500 } }) },
  ChrEv_0340_005_01 = { ObtainItemList = itemList({ { 25001, 1 }, { 13017, 1 } }) },
  ChrEv_0420_005_01 = { ObtainItemList = itemList({ { 13051, 1 }, { 25002, 1 } }) },
  SubEv_C01_Chloe_04 = { ObtainItemList = itemList({ { 12032, 1 }, { 25000, 1 } }) },
  SubEv_C05_MogChase_06_NPC01_01 = { ObtainItemList = itemList({ { 33, 1 } }) },
  FEV_Town_01Gra_05_981_01 = { ObtainItemList = itemList({ { 10113, 1 }, { 11014, 1 } }) },
  FEV_Town_08Gro_01_1540_01 = { ObtainItemList = itemList({ { 27006, 1 } }) },
}
questTable = { rows = questRows, ParentTables = {} }
function questTable:IsValid() return true end
function questTable:HasAnyInternalFlags() return false end
function questTable:HasAnyFlags() return false end
function questTable:GetFullName() return "DataTable DT_TalkEventData_SubEv_Chapter01" end
function questTable:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local prevQuestFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.CDT_TalkEventData_Prod" then return questTable end
  return prevQuestFind(p)
end
function rewards(row)
  local list, out = questRows[row].ObtainItemList, {}
  for i = 1, #list do out[#out + 1] = list[i].ID .. "x" .. list[i].Num end
  return table.concat(out, " ")
end
""")
QUEST_ROWS_TO_CHANGE = 5
STAND_IN_POTION = "1x1"
assert L.eval("G.QuestsPatch()") == QUEST_ROWS_TO_CHANGE
assert L.eval("rewards('SubEv_C01_Zairu_04')") == "-1x500", "the location's item goes, the gil stays"
assert L.eval("rewards('ChrEv_0340_005_01')") == STAND_IN_POTION,     "Amelia: the Magicite is the location's, the vision comes out; round 88: an empty row keeps the stand-in"
assert L.eval("rewards('ChrEv_0420_005_01')") == STAND_IN_POTION, "Ayaka: the vision first, then the Magicite Cryst"
assert L.eval("rewards('SubEv_C01_Chloe_04')") == "25000x1", "the Prayer Beads are the location's; the Shard stays"
assert L.eval("rewards('SubEv_C05_MogChase_06_NPC01_01')") == STAND_IN_POTION, \
    "round 84: Mog Tag's row left empty showed a vision pop-up; it keeps the stand-in"
assert L.eval("G.QuestsPatch()") == 0, "nothing to write the second time: the Shard is not the location's"
# Round 98 (the user): with second rewards, the gil and the Shard are locations too
assert L.eval("G.QuestsPatch(true)") == 2
assert L.eval("rewards('SubEv_C01_Zairu_04')") == STAND_IN_POTION, "the gil goes"
assert L.eval("rewards('SubEv_C01_Chloe_04')") == STAND_IN_POTION, "the Shard goes"
assert L.eval("G.QuestsPatch(true)") == 0
# Round 97 (the user): an NPC gift's row gives the stand-in in place of both its items; the
# Magi-tenna's only with the radar treasures
GIFT_ROWS = 7   # round 98: 1407 and 1409 left out; 1403 unreachable at story 8000
assert L.eval("#G.GIFTS") == GIFT_ROWS and L.eval("G.GIFTS[1].key") == "gift:1400" and L.eval("G.GIFTS[1].flag") == 1400
assert L.eval("G.GIFTS[1].map") == 2016 and L.eval("G.GIFTS[1].x") == 25910, "round 98: where the NPC stands"
assert L.eval("G.GiftsPatch(false)") == 1
assert L.eval("rewards('FEV_Town_01Gra_05_981_01')") == STAND_IN_POTION, "the Lunar Sword and the Brigandine go"
assert L.eval("rewards('FEV_Town_08Gro_01_1540_01')") == "27006x1", "no radar treasures: the Magi-tenna stays"
assert L.eval("G.GiftsPatch(true)") == 1 and L.eval("rewards('FEV_Town_08Gro_01_1540_01')") == STAND_IN_POTION
assert L.eval("G.GiftsPatch(true)") == 0, "once"
# quests.lua, generated from data/quests.tsv: 28 quests, each with a counter, a value and rows
assert L.eval("#G.QUESTS") == 28
assert L.eval("G.QUESTS[1].key") == "quest:0" and L.eval("G.QUESTS[1].counter") == 1 and L.eval("G.QUESTS[1].value") == 50
assert L.eval("G.MECHABO.counter") == 16 and L.eval("G.MECHABO.start") == 10
assert L.eval("G.QUESTS[1].item") == 12050, "the location's item, which the rows lose"
assert L.eval("G.QUESTS[1].key2") is None, "A New Leaf: one item and a stat bonus"
# Round 88 (the user): the Quests screen's Rewards show the scouted item. DT_RequestData's Prize
# entry for the location's vanilla item becomes a text entry (ID 0), as the game's stat bonus
# line is; the other entries stay; a quest left out gets its vanilla entry back.
L.execute(r"""
local function prizeEntry(id) return { ID = id, Num = 1, Text = FText("") } end
requestTable = { rows = {
  ["カーミル"] = { ID = 25, Prize = { prizeEntry(13033), prizeEntry(25001) } },
  ChrEv_0010 = { ID = 0, Prize = { prizeEntry(12050) } },
  NotALocation = { ID = 17, Prize = { prizeEntry(25000) } } } }
function requestTable:IsValid() return true end
function requestTable:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local prevPrizeFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Request/DT_RequestData.DT_RequestData" then return requestTable end
  return prevPrizeFind(p)
end
function prizeText(row)
  local out = {}
  for _, e in ipairs(requestTable.rows[row].Prize) do out[#out + 1] = e.ID .. ":" .. e.Text:ToString() end
  return table.concat(out, " ")
end
""")
CALL_LABEL = "Alice's Hookshot"
assert L.eval(f"G.QuestPrizes({{ ['quest:25'] = \"{CALL_LABEL}\" }})") == 1
assert L.eval("prizeText('カーミル')") == f"13033: 0:{CALL_LABEL}", "the Magicite is the location's; the Ribbon stays"
assert L.eval("prizeText('ChrEv_0010')") == "12050:", "a quest with no scout keeps its own"
assert L.eval("prizeText('NotALocation')") == "25000:"
assert L.eval(f"G.QuestPrizes({{ ['quest:25'] = \"{CALL_LABEL}\" }})") == 0, "already written"
requestReload = "requestTable.rows['カーミル'].Prize[2] = { ID = 25001, Num = 1, Text = FText('') }"
L.execute(requestReload)
assert L.eval(f"G.QuestPrizes({{ ['quest:25'] = \"{CALL_LABEL}\" }})") == 1, "written again on a table loaded again"
assert L.eval("G.QuestPrizes({})") == 1 and L.eval("prizeText('カーミル')") == "13033: 25001:", "a save not linked: the game's own"
# Round 98: the second reward's location has the vision's entry
SECOND_LABEL = "Bob's Ether"
assert L.eval(f"G.QuestPrizes({{ ['quest:25'] = \"{CALL_LABEL}\", ['quest2:25'] = \"{SECOND_LABEL}\" }})") == 2
assert L.eval("prizeText('カーミル')") == f"0:{SECOND_LABEL} 0:{CALL_LABEL}"
assert L.eval("G.QuestPrizes({})") == 2 and L.eval("prizeText('カーミル')") == "13033: 25001:"
# Round 93: the quest log's states, from the save's request.DataMap (round 92: Verun showed no quest)
L.execute(r"""
local function entry(k, state) return { get = function() return k end }, { get = function() return { State = state } end } end
requestSave = { request = { DataMap = { ForEach = function(self, fn)
  local k, v = entry(17, 1); fn(k, v); k, v = entry(26, 2); fn(k, v) end } } }
local oldSaveData = G.SaveData
function G.SaveData() return requestSave end
requestStates = G.RequestStates({ 17, 26, 27 })
G.SaveData = oldSaveData
""")
assert [L.eval(f"requestStates[{i}]") for i in (17, 26, 27)] == ["open", "done", "not in the log"]
# Round 94: a quest board quest's state and kills (round 93: the Ipooh kills did not count)
L.execute(r"""
local oldSaveData = G.SaveData
function G.SaveData() return { questBoardList = { { QuestId = 1001, State = 1, KilledCount = { { ID = 55, DeliveryQuantity = 1 } } } } } end
boardLines = { G.BoardQuest(1001), G.BoardQuest(1002) }
G.SaveData = oldSaveData
""")
assert list(L.eval("boardLines").values()) == ["ordered, kills 55 x1", "not on the board"]
# Round 95: an open request's current step's board quests that read none are ordered
L.execute(r"""
local oldSaveData = G.SaveData
board = { { QuestId = 1001, State = 0, KilledCount = {} }, { QuestId = 1002, State = 0, KilledCount = {} },
          { QuestId = 1003, State = 3, KilledCount = {} } }
local function entry(k, state, step) return { get = function() return k end }, { get = function() return { State = state, ProgressIndex = step } end } end
function G.SaveData() return { questBoardList = board, request = { DataMap = { ForEach = function(self, fn)
  local k, v = entry(17, 1, 0); fn(k, v); k, v = entry(26, 2, 0); fn(k, v) end } } } end
requestRows = { rows = {
  C02_MechaboLvUp = { ID = 17, ProgressList = { { QuestList = { 1001 } }, { QuestList = {} } } },
  C02_MechaboLvUp_02 = { ID = 26, ProgressList = { { QuestList = { 1002 } } } } } }
function requestRows:IsValid() return true end
function requestRows:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local prevOrderFind = StaticFindObject
function StaticFindObject(p) if p == G.MECHABO.requestTable then return requestRows end return prevOrderFind(p) end
ordered = G.OrderRequestQuests({ 17, 26, 27 })
orderedAgain = G.OrderRequestQuests({ 17, 26, 27 })
StaticFindObject, G.SaveData = prevOrderFind, oldSaveData
""")
assert list(L.eval("ordered").values()) == [1001], "17 is open at step 0; 26 is done, so its hunt is left alone"
assert L.eval("board[1].State") == 1 and L.eval("board[2].State") == 0 and L.eval("board[3].State") == 3
assert L.eval("#orderedAgain") == 0, "once"
print("quest rows: ok")

# Round 84: the open start skips C02_219_02, which accepts request 17 into the quest log. Verun's
# rows for the first step accept it instead, ahead of what they already do, once.
L.execute(r"""
local function requestList(entries)
  local items = {}
  local list = setmetatable({}, {
    __index = function(_, i)
      if i == "Empty" then return function() for k in pairs(items) do items[k] = nil end end end
      if i == #items + 1 then items[i] = { RequestID = 0, Type = 0, ProgressIndex = 0 } end
      return items[i]
    end,
    __len = function() return #items end })
  for i, e in ipairs(entries) do items[i] = { RequestID = e[1], Type = e[2], ProgressIndex = e[3] } end
  return list
end
questRows.C02_MechaboLvUp_00_yet = { RequestStateSettings = requestList({}) }
questRows.C02_MechaboLvUp_00_ItemGet = { RequestStateSettings = requestList({ { 17, 1, 1 } }) }
questRows.C02_MechaboLvUp_01 = { RequestStateSettings = requestList({ { 17, 2, 0 } }) }
local function fstr(v) return { ToString = function() return v end } end
local store = { AcceptCondition = fstr("{progress:16}==0&{progress:0}>=2120"),
                Occurrence = { Condition = "{progress:16}==0&{progress:0}>=2120" } }
mechaboRequest = setmetatable({}, { __index = store,
  __newindex = function(_, k, v) store[k] = type(v) == "string" and fstr(v) or v end })
requestDT = { rows = { C02_MechaboLvUp = mechaboRequest } }
function requestDT:IsValid() return true end
function requestDT:FindRow(name) return self.rows[name] end
local prevRequestFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/Request/DT_RequestData.DT_RequestData" then return requestDT end
  return prevRequestFind(p)
end
function requests(row)
  local list, out = questRows[row].RequestStateSettings, {}
  for i = 1, #list do out[#out + 1] = list[i].RequestID .. ":" .. list[i].Type .. ":" .. list[i].ProgressIndex end
  return table.concat(out, " ")
end
""")
ACCEPT_17 = "17:0:0"
VERUN_STEP = "{progress:16}==10"
MECHABO_ROWS_AND_REQUEST = 3
assert L.eval("G.MechaboPatch()") == MECHABO_ROWS_AND_REQUEST
assert L.eval("mechaboRequest.AcceptCondition:ToString()") == VERUN_STEP, \
    "round 85: the quest's own accept test was the counter at 0, which the start had already passed"
assert L.eval("mechaboRequest.Occurrence.Condition") == VERUN_STEP
assert L.eval("requests('C02_MechaboLvUp_00_yet')") == ACCEPT_17, "Verun asks for the drops: accepted"
assert L.eval("requests('C02_MechaboLvUp_00_ItemGet')") == ACCEPT_17 + " 17:1:1", "accepted, then its step"
assert L.eval("requests('C02_MechaboLvUp_01')") == "17:2:0", "the rest of the chain is the game's"
assert L.eval("G.MechaboPatch()") == 0, "nothing to write the second time"
print("mechabo quest log: ok")

# Round 73: the Sworn Six's three assist skills in the Behemoth fight deal a fixed 1 damage, and
# no other skill changes (Ruin, 500100, is the same ally's own attack and is used elsewhere too).
L.execute("""
skillRows = { water = { ID = 501940, magnification = 2000 }, light = { ID = 501950, magnification = 2000 },
  both = { ID = 501960, magnification = 3000 }, ruin = { ID = 500100, magnification = 12 } }
skillTable = { rows = skillRows, ParentTables = {} }
function skillTable:IsValid() return true end
function skillTable:GetFullName() return "DataTable DT_SkillData" end
function skillTable:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local prevSkillFind = StaticFindObject
function StaticFindObject(p)
  if p == G.BEHEMOTH.skillTable then return skillTable end
  return prevSkillFind(p)
end
""")
ASSIST_SKILLS = 3
assert L.eval("G.BehemothPatch()") == ASSIST_SKILLS
for row in ("water", "light", "both"):
    assert L.eval(f"skillRows.{row}.magnification") == 1, row
assert L.eval("skillRows.ruin.magnification") == 12, "the ally's own attack is left alone"
assert L.eval("G.BehemothPatch()") == 0, "nothing to write the second time"
print("behemoth assist hits: ok")

# Round 72: the map manager is kept as its path. Once the engine frees it (here: no longer found by
# path, and any touch fails as an access violation would), the next call finds the new one and
# never asks the old one anything. Round 71 crashed twice on IsValid of a freed, kept object.
L.execute("""
oldMgr = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
           HasAnyFlags = function() return false end, GetSameMapId = function() return 1000 end,
           GetFullName = function() return "CPP_MapManager /Game/Map/Wld/Wld_PL.Wld_PL:PersistentLevel.MapManager" end }
newMgr = { IsValid = function() return true end, HasAnyInternalFlags = function() return false end,
           HasAnyFlags = function() return false end, GetSameMapId = function() return 2000 end }
liveMgr = oldMgr
savedFindFirstOf = FindFirstOf
FindFirstOf = function(c) if c == "CPP_MapManager" then return liveMgr end return savedFindFirstOf(c) end
G.ForgetObjects()
""")
assert L.eval("G.CurrentMap()") == 1000
L.execute("""
for k, v in pairs(fakePaths) do if v == oldMgr then fakePaths[k] = nil end end
touchedFreed = false
local function freed() touchedFreed = true; error("access violation") end
oldMgr.IsValid, oldMgr.GetSameMapId, oldMgr.HasAnyInternalFlags, oldMgr.HasAnyFlags = freed, freed, freed, freed
liveMgr = newMgr
""")
assert L.eval("G.CurrentMap()") == 2000, "the new map's manager"
assert L.eval("touchedFreed") is False, "the old one is never touched: in the game that is a crash pcall cannot catch"
L.execute("FindFirstOf = savedFindFirstOf; G.ForgetObjects()")
print("kept objects as paths: ok")

# Round 77: the save stamp. A save keeps how many of the session's items it holds, and its seed's
# tag, in event flags, so it is known on another PC and after ap_state.txt is deleted.
L.execute("""
stampFlags, stampSets = {}, 0
savedGetFlag2, savedSetFlag2 = G.GetFlag, G.SetFlag
G.GetFlag = function(i) return stampFlags[i] == true end
G.SetFlag = function(i, on) stampFlags[i] = on; stampSets = stampSets + 1; return "ok", "" end
""")
SESSION_KEY = "AP_12345678901234567890:0:1"
OTHER_KEY = "AP_98765432109876543210:0:1"
tag = L.eval(f'G.SeedTag("{SESSION_KEY}")')
assert 1 <= tag <= 2047 and tag == L.eval(f'G.SeedTag("{SESSION_KEY}")'), tag
assert tag != L.eval(f'G.SeedTag("{OTHER_KEY}")'), "two seeds get two tags"
assert L.execute("local c, t = G.ReadSaveStamp(); return c, t") == (0, 0), "a save with no stamp"
RECEIVED = 437
assert L.eval(f"G.WriteSaveStamp({RECEIVED}, {tag})") > 0
assert L.execute("local c, t = G.ReadSaveStamp(); return c, t") == (RECEIVED, tag)
assert L.eval(f"G.WriteSaveStamp({RECEIVED}, {tag})") == 0, "flags already right are not written again"
assert L.eval(f"G.WriteSaveStamp({RECEIVED + 1}, {tag})") >= 1
assert L.execute("local c, t = G.ReadSaveStamp(); return c, t") == (RECEIVED + 1, tag)
assert L.eval("G.STAMP_MAX") == 4095
used = set(L.eval("G.STAMP_COUNT_FLAGS").values()) | set(L.eval("G.STAMP_TAG_FLAGS").values())
assert len(used) == 23 and not used & {L.eval("G.AIRSHIP_FLAG"), L.eval("G.BOSS_TEST_FLAG"), L.eval("G.STORY_BOSS_READY_FLAG")}
assert not used & {c["flag"] for c in L.eval("G.CONTINENTS").values()}, "no continent lock flag"
L.execute("G.GetFlag = function() return nil end")
assert L.eval("G.ReadSaveStamp()") is None, "no flag library: no stamp"
L.execute("G.GetFlag, G.SetFlag = savedGetFlag2, savedSetFlag2")
print("save stamp: ok")

# IDEAS.md idea 37: the Oblivion Palace safes. The steps are the turn-in table's, and the turned-in
# count is asked of the game's own condition test, as the princess's talk rows test it.
shard_rows = list(_csv.DictReader(open(paths.REPO / "data/game/shard_chests.tsv", encoding="utf-8"), delimiter="\t"))
assert list(L.eval("G.PALACE.steps").values()) == [int(r["shards"]) for r in shard_rows], "steps match the dump"
assert L.eval("G.PALACE.counter") == 43 and L.eval("G.PALACE.met") == 10
L.execute("""
TURNED_IN, conditionAsks = 0, {}
conditionLib = {}
function conditionLib:IsValid() return true end
function conditionLib:IsMeetCondition(test, flag)
  conditionAsks[#conditionAsks + 1] = test
  local n = tonumber(test:match("^{transferItem:0,25004}>=(%d+)$"))
  return n ~= nil and TURNED_IN >= n
end
local prevConditionFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Script/mucha.Default__CPP_BFL_Condition" then return conditionLib end
  return prevConditionFind(p)
end
""")
SHARDS_TURNED_IN = 20
L.execute(f"TURNED_IN = {SHARDS_TURNED_IN}")
assert L.eval(f"G.TurnedInAtLeast({SHARDS_TURNED_IN})") is True
assert L.eval(f"G.TurnedInAtLeast({SHARDS_TURNED_IN + 1})") is False
assert L.eval("conditionAsks[1]") == "{transferItem:0,25004}>=20", "the princess rows' own test"
assert L.eval("G.TurnedInCount()") == SHARDS_TURNED_IN
assert L.eval("#conditionAsks") <= 2 + 7, "the count by halving: 7 tests"
# The sync: progress 43 at 10 plus the steps the shards held and turned in pay for (safe n opens at
# 11 + n). The shards stay in the bag for her milestone talks, and the counter is never lowered.
# Round 80: the condition test reads the current map's turn-ins, so it is asked in the palace only.
L.execute("""
palaceHeld, palaceProgress, palaceSave, palaceMap = 0, {}, "SD_PALACE", 1000
savedPalace = { G.HeldCount, G.ProgressValue, G.SetProgressValue, G.SaveObjectName, G.CurrentMap }
G.HeldCount = function(id) return palaceHeld end
G.ProgressValue = function(i) return palaceProgress[i] or 0 end
G.SetProgressValue = function(i, n) palaceProgress[i] = n; return n end
G.SaveObjectName = function() return palaceSave end
G.CurrentMap = function() return palaceMap end
savedMeet = conditionLib.IsMeetCondition
function conditionLib:IsMeetCondition(test, flag)
  if palaceMap ~= 2031 then return test:match(">=0$") ~= nil end
  return savedMeet(self, test, flag)
end
""")
PALACE_COUNTER, PRINCESS_MET = 43, 10
PALACE_MAP, WORLD_MAP = 2031, 1000
progress = lambda: L.eval(f"palaceProgress[{PALACE_COUNTER}]")
# Round 80, the user's save: chests 1 and 2 taken the old way (6 turned in, counter 12), 4 held
L.execute(f"TURNED_IN = 6; palaceHeld = 4; palaceProgress[{PALACE_COUNTER}] = 12")
asks = L.eval("#conditionAsks")
assert L.eval("G.PalaceSync()") == "palace: 4 shards held, not read yet turned in, 1 steps paid, progress 43 at 12"
assert L.eval("#conditionAsks") == asks, "not asked on the world map"
L.execute(f"palaceMap = {PALACE_MAP}")
assert L.eval("G.PalaceSync()") == "palace: 4 shards held, 6 turned in, 3 steps paid, progress 43 at 13"
assert progress() == PRINCESS_MET + 3, "10 shards in all: the third safe (9 shards) opens"
asks = L.eval("#conditionAsks")
assert L.eval("G.PalaceSync()") is None, "the line only when it changes"
assert L.eval("#conditionAsks") == asks, "asked again only when the held count changes"
L.execute(f"palaceMap = {WORLD_MAP}; palaceHeld = 7")    # 3 more come in on the world map
L.eval("G.PalaceSync()")
assert progress() == PRINCESS_MET + 4, "the palace's last reading still counts: 13 in all"
L.execute(f"palaceMap = {PALACE_MAP}; palaceHeld = 0; TURNED_IN = 13")    # a talk: she takes the 7
L.eval("G.PalaceSync()")
assert progress() == PRINCESS_MET + 4, "her loop has nothing left to do"
L.execute("palaceHeld = 14")                  # 27 in all: past the 24-shard step, short of 28
L.eval("G.PalaceSync()")
assert progress() == PRINCESS_MET + 7, "held and turned in count together"
L.execute(f"palaceProgress[{PALACE_COUNTER}] = {PRINCESS_MET + 20}")
L.eval("G.PalaceSync()")
assert progress() == PRINCESS_MET + 20, "never lowered"
L.execute("palaceProgress = {}; palaceHeld = 0; TURNED_IN = 99; palaceSave = 'SD_OTHER'")
assert L.eval("G.PalaceSync()") == "palace: 0 shards held, 99 turned in, 25 steps paid, progress 43 at 35"
L.execute("palaceMap = 1000; palaceProgress = {}; palaceSave = 'SD_NEW'")
assert L.eval("G.PalaceSync()") == "palace: 0 shards held, not read yet turned in, 0 steps paid, progress 43 at 10",     "a new save: the palace opens, no safe yet"
L.execute("StaticFindObject = (function(prev) return function(p) if p:find('CPP_BFL_Condition') then return nil end return prev(p) end end)(StaticFindObject)")
L.execute("palaceMap = 2031; palaceHeld = 4")
L.eval("G.PalaceSync()")
assert progress() == PRINCESS_MET + 1, "no condition test: the shards held still count"
L.execute("G.HeldCount, G.ProgressValue, G.SetProgressValue, G.SaveObjectName, G.CurrentMap = table.unpack(savedPalace)")
print("palace safes: ok")

# Rounds 82 and 83: the Archipelago entry in the main menu, with no pak. The row is a copy of
# System's in DT_MainMenuScene that opens the Tutorial screen, the tag goes before System in
# DisplaySceneList, and the subsystem gets the row when it was built without it.
SYSTEM_PATH = "/Game/UI/MainMenu/System/WBP_MainMenuSystem.WBP_MainMenuSystem_C"
TUTORIAL_PATH = "/Game/UI/Tutorial/WBP_TutorialLayout.WBP_TutorialLayout_C"
OWN_TAG = "UI.MainMenu.Scene.FFRAP"
L.execute(r"""
local function soft(p) return { path = p } end
local function sceneRow(tag, name, layout)
  return { SceneTag = { TagName = FName(tag) }, EntryName = FText(name), SceneTitle = FText(name),
           LayoutData = { LayoutWidget = soft(layout) } }
end
local function copyRow(r)
  return sceneRow(r.SceneTag.TagName:ToString(), r.EntryName:ToString(), r.LayoutData.LayoutWidget.path)
end
function freshSceneTable()
  sceneDT.rows = { ["ジャーナル"] = sceneRow("UI.MainMenu.Scene.Journal", "Quests", "/Game/J.J_C"),
                   ["システム"] = sceneRow("UI.MainMenu.Scene.System", "System", "SYSTEM_PATH") }
end
sceneDT = {}
function sceneDT:IsValid() return true end
function sceneDT:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
function sceneDT:AddRow(name, tpl) self.rows[name] = copyRow(tpl) end
function sceneDT:FindRow(name) return self.rows[name] end
freshSceneTable()
local function live(o) o.IsValid = function() return true end; o.HasAnyInternalFlags = function() return false end
  o.HasAnyFlags = function() return false end; return o end
local function fakeMap()
  local m = { list = {} }
  function m:ForEach(fn) for _, kv in ipairs(self.list) do fn({ get = function() return kv[1] end }, { get = function() return kv[2] end }) end end
  function m:Add(k, v) self.list[#self.list + 1] = { k, type(v) == "table" and v.SceneTag and copyRow(v) or v } end
  return m
end
menuRoot = live({ DisplaySceneList = { { TagName = FName("UI.MainMenu.Scene.Journal") }, { TagName = FName("UI.MainMenu.Scene.System") } } })
menuSub = live({ SceneDataMap = fakeMap(), SceneEnableMap = fakeMap() })
menuSub.SceneDataMap:Add({ TagName = FName("UI.MainMenu.Scene.System") }, sceneDT.rows["システム"])
menuSub.SceneEnableMap:Add({ TagName = FName("UI.MainMenu.Scene.System") }, true)
apKsl = { MakeSoftClassPath = function(_, p) return p end,
          Conv_SoftClassPathToSoftClassRef = function(_, p) return soft(p) end,
          Conv_SoftClassReferenceToString = function(_, v) return v.path end }
function apKsl:IsValid() return true end
local prevSFO = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/UI/MainMenu/Data/DT_MainMenuScene.DT_MainMenuScene" then return sceneDT end
  if p == "/Script/Engine.Default__KismetSystemLibrary" then return apKsl end
  return prevSFO(p)
end
local prevFFO = FindFirstOf
function FindFirstOf(c)
  if c == "CPP_DA_MainMenuRoot" then return menuRoot end
  if c == "CPP_MainMenuSubsystem" then return menuSub end
  return prevFFO(c)
end
says = {}
function say(s) says[#says + 1] = s end
function listTags()
  local t = {}
  for i = 1, #menuRoot.DisplaySceneList do t[i] = menuRoot.DisplaySceneList[i].TagName:ToString() end
  return table.concat(t, ",")
end
function subTags(m)
  local t = {}
  m:ForEach(function(k, v) t[#t + 1] = k:get().TagName:ToString() .. "=" .. tostring(type(v:get()) == "table" and v:get().LayoutData.LayoutWidget.path or v:get()) end)
  return table.concat(t, ",")
end
""".replace("SYSTEM_PATH", SYSTEM_PATH))
assert lua("G.APMENU.screen") == "options", "round 87: the entry opens the Options screen as our page"
L.execute("G.APMENU.screen = 'text'")   # the Tutorial screen here; the probe below writes the Options one
assert lua("G.APMENU.Ensure(say)") == "row added; scene list; data added, enable added"
assert lua("sceneDT.rows.FFRAP_Archipelago.SceneTag.TagName:ToString()") == OWN_TAG
assert lua("sceneDT.rows.FFRAP_Archipelago.EntryName:ToString()") == "Archipelago"
assert lua("sceneDT.rows.FFRAP_Archipelago.LayoutData.LayoutWidget.path") == TUTORIAL_PATH, "opens the Tutorial screen"
assert lua("sceneDT.rows['システム'].SceneTag.TagName:ToString()") == "UI.MainMenu.Scene.System", "System's row untouched"
assert lua("sceneDT.rows['システム'].LayoutData.LayoutWidget.path") == SYSTEM_PATH, "System still opens its own screen"
assert lua("listTags()") == f"UI.MainMenu.Scene.Journal,{OWN_TAG},UI.MainMenu.Scene.System", "before System"
assert lua("subTags(menuSub.SceneDataMap)") == f"UI.MainMenu.Scene.System={SYSTEM_PATH},{OWN_TAG}={TUTORIAL_PATH}"
assert lua("subTags(menuSub.SceneEnableMap)") == f"UI.MainMenu.Scene.System=true,{OWN_TAG}=true"
says = list(L.eval("says").values())
assert says[0] == "apmenu: AddRow FFRAP_Archipelago (a copy of System's)", says
assert "apmenu: row tag, texts and screen" in says, says
assert any("scene list 2 -> 3" in s for s in says) and any("SceneDataMap:Add" in s for s in says), says
L.execute("says = {}")
assert lua("G.APMENU.Ensure(say)") is None, "nothing to write the second time"
assert lua("#says") == 0, "and nothing logged"
# the game loads the table again: the row comes back with its screen, and nothing else moves
L.execute("freshSceneTable()")
assert lua("G.APMENU.Ensure(say)") == "row added"
assert lua("sceneDT.rows.FFRAP_Archipelago.LayoutData.LayoutWidget.path") == TUTORIAL_PATH
assert lua("listTags()").count(OWN_TAG) == 1
# a scene list that does not end in System (another mod went last): ours goes at the end
L.execute("menuRoot.DisplaySceneList = { { TagName = FName('UI.MainMenu.Scene.Journal') } }")
assert lua("G.APMENU.List(say)") == "added" and lua("listTags()") == f"UI.MainMenu.Scene.Journal,{OWN_TAG}"
# the title screen: no subsystem and no scene list yet
L.execute("savedRoot, menuRoot = menuRoot, nil; G.ForgetObjects()")
assert lua("select(2, G.APMENU.Ensure(say))") == "no DA_MainMenuRoot loaded"
L.execute("menuRoot = savedRoot; G.ForgetObjects()")
# Round 84: on a save not linked to the seed the entry leaves the scene list, once
L.execute(f"""
local list = {{ {{ TagName = FName('UI.MainMenu.Scene.Journal') }}, {{ TagName = FName('{OWN_TAG}') }},
                {{ TagName = FName('UI.MainMenu.Scene.System') }} }}
list.Empty = function(self) for i = #self, 1, -1 do self[i] = nil end end
menuRoot.DisplaySceneList = list
""")
assert lua("G.APMENU.Unlist()") is True
assert lua("listTags()") == "UI.MainMenu.Scene.Journal,UI.MainMenu.Scene.System", "the rest stays in order"
assert lua("G.APMENU.Unlist()") is False, "already out"
print("main menu entry: ok")

# Round 85 probe (idea 39): `options` gives our row and the subsystem's copy the Options screen,
# with the view models and input contexts of the game's own UI.Layout.Option row; `text` puts the
# Tutorial screen back with System's (none). The list fakes behave like the engine's arrays.
L.execute(r"""
function engineArray(entries, blank)
  local items = {}
  for i, e in ipairs(entries) do items[i] = e end
  return setmetatable({}, {
    __index = function(_, i)
      if i == "Empty" then return function() for k in pairs(items) do items[k] = nil end end end
      if i == #items + 1 and blank then items[i] = blank() end
      return items[i]
    end,
    __newindex = function(_, i, v) items[i] = v end,
    __len = function() return #items end })
end
local function vmBlank() return { ViewModelClass = nil, IsManualContextName = false, ManualContextName = FName("None") } end
local function giveLists(data, vms, ctx)
  data.ViewModelDataList = engineArray(vms, vmBlank)
  data.IMCData = { childMappingContextList = engineArray(ctx) }
end
UI_MAINMENU, UI_INFO, OPTION_MENU = 5, 3, 9
giveLists(sceneDT.rows["システム"].LayoutData, {}, { UI_MAINMENU })
giveLists(sceneDT.rows.FFRAP_Archipelago.LayoutData, {}, { UI_MAINMENU })
for _, kv in ipairs(menuSub.SceneDataMap.list) do
  if kv[1].TagName:ToString() == "UI.MainMenu.Scene.FFRAP" then giveLists(kv[2].LayoutData, {}, { UI_MAINMENU }); subCopy = kv[2] end
end
local optionLayout = { LayoutTag = { TagName = FName("UI.Layout.Option") }, LayoutData = {} }
giveLists(optionLayout.LayoutData,
  { { ViewModelClass = "CPP_VM_Option", IsManualContextName = false, ManualContextName = FName("None") },
    { ViewModelClass = "CPP_VM_OptionKeyBind", IsManualContextName = true, ManualContextName = FName("CPP_VM_KeyBind") } },
  { UI_INFO, OPTION_MENU })
gameLayoutDT = { rows = { ["System_ヘルプ"] = { LayoutTag = { TagName = FName("UI.Layout.System.Help") }, LayoutData = {} },
                          ["System_オプション"] = optionLayout } }
function gameLayoutDT:IsValid() return true end
function gameLayoutDT:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local function fstr(v) return { ToString = function() return v end } end
local function tabRow(category, label, cond)
  local store = { CommandCategory = category, DisplayText = FText(label), Condition = fstr(cond) }
  return setmetatable({}, { __index = store,
    __newindex = function(_, k, v) store[k] = type(v) == "string" and fstr(v) or v end })
end
optionRoot = { rows = { NewRow = tabRow(0, "Gameplay", ""), NewRow_0 = tabRow(1, "Graphics", ""),
                        NewRow_3 = tabRow(4, "Sound", "") } }
function optionRoot:IsValid() return true end
function optionRoot:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
local prevOptFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/UI/GameLayout/DT_GameLayoutWidget_System.DT_GameLayoutWidget_System" then return gameLayoutDT end
  if p == "/Game/Datatable/UI/Option/DT_Option_Root.DT_Option_Root" then return optionRoot end
  return prevOptFind(p)
end
function screenOf(data)
  local vms, ctx = {}, {}
  for i = 1, #data.ViewModelDataList do
    local v = data.ViewModelDataList[i]
    vms[#vms + 1] = tostring(v.ViewModelClass) .. (v.IsManualContextName and ("@" .. v.ManualContextName:ToString()) or "")
  end
  for i = 1, #data.IMCData.childMappingContextList do ctx[#ctx + 1] = data.IMCData.childMappingContextList[i] end
  return data.LayoutWidget.path .. " | " .. table.concat(vms, ",") .. " | " .. table.concat(ctx, ",")
end
""")
OPTIONS_PATH = "/Game/UI/Option/Widget/WBP_OptionLayout.WBP_OptionLayout_C"
OPTIONS_SCREEN = f"{OPTIONS_PATH} | CPP_VM_Option,CPP_VM_OptionKeyBind@CPP_VM_KeyBind | 3,9"
TEXT_SCREEN = f"{TUTORIAL_PATH} |  | 5"
L.execute("says = {}")
lines = list(L.eval("G.APMENU.Screen('options', say)").values())
assert lines[0].startswith("row: class written, view models written (2), input contexts written (2)"), lines
assert lines[1].startswith("subsystem: class written"), lines
assert lua("screenOf(sceneDT.rows.FFRAP_Archipelago.LayoutData)") == OPTIONS_SCREEN
assert lua("screenOf(subCopy.LayoutData)") == OPTIONS_SCREEN, "the menu's own copy too"
assert lua("screenOf(sceneDT.rows['システム'].LayoutData)") == f"{SYSTEM_PATH} |  | 5", "System's row untouched"
assert "apmenu: view models 0 -> 2" in list(L.eval("says").values()), "each step told before it runs"
L.eval("G.APMENU.Screen('text', say)")
assert lua("screenOf(sceneDT.rows.FFRAP_Archipelago.LayoutData)") == TEXT_SCREEN, "the page again"
assert lua("screenOf(subCopy.LayoutData)") == TEXT_SCREEN
# the Options tabs: `only` leaves out all but Gameplay and Graphics (round 87: the page's second
# tab), `all` puts their conditions back
NEVER = "{progress:0}<0"
tabs = list(L.eval("G.APMENU.Tabs('only', say)").values())
assert sorted(tabs) == sorted(['tab NewRow: Gameplay, category 0, condition ""',
                               'tab NewRow_0: Graphics, category 1, condition ""',
                               f'tab NewRow_3: Sound, category 4, condition "{NEVER}"']), tabs
tabs = list(L.eval("G.APMENU.Tabs('all', say)").values())
assert all(t.endswith('condition ""') for t in tabs), tabs
print("options screen probe: ok")

# Round 86 probe: `mode ap` makes the Options screen our page. One tab, named Archipelago; the
# game's rows hidden in game (ShowType TitleOnly) and ours left alone; a heading row per page line,
# copied from the keyboard tab's SubHeader. `mode game` puts it all back.
L.execute(r"""
local function fstr(v) return { ToString = function() return v end } end
local function optionRow(showType, label)
  return { ShowCommandData = { ShowType = showType }, DisplayText = fstr(label) }
end
local function table_(rows)
  local t = { rows = rows }
  function t:IsValid() return true end
  function t:ForEachRow(fn) for k, r in pairs(self.rows) do fn(fname(k), r) end end
  function t:FindRow(n) return self.rows[n] end
  function t:AddRow(n, tpl) self.rows[n] = { ShowCommandData = { ShowType = tpl.ShowCommandData.ShowType }, DisplayText = tpl.DisplayText } end
  function t:RemoveRow(n) self.rows[n] = nil end
  return t
end
GAMEPLAY_ONLY = 2
gameSetting = table_({ ["難易度"] = optionRow(GAMEPLAY_ONLY, "Difficulty"), ["初期化"] = optionRow(0, "Reset"),
                       FFRAP_Exp = optionRow(GAMEPLAY_ONLY, "EXP") })
keyboardSetting = table_({ ["SubHeader_共通"] = optionRow(0, "UI / Main Menu") })
seedSetting = table_({ NewRow = optionRow(0, "Master"), NewRow_4 = optionRow(0, "Reset") })
local gameplayTab = optionRoot.rows.NewRow
local tabStore = { DisplayText = fstr("Gameplay") }
local prevModeFind = StaticFindObject
function StaticFindObject(p)
  if p == "/Game/Datatable/UI/Option/Root/GameSetting/DT_OP_GameSetting.DT_OP_GameSetting" then return gameSetting end
  if p == "/Game/Datatable/UI/Option/Root/KeyboardMouseSetting/DT_OP_KeyboardMouseSetting.DT_OP_KeyboardMouseSetting" then return keyboardSetting end
  if p == "/Game/Datatable/UI/Option/Root/GraphicSetting/DT_OP_GraphicSetting.DT_OP_GraphicSetting" then return seedSetting end
  return prevModeFind(p)
end
function rowText(name, t) local r = (t or gameSetting).rows[name]; return r and r.DisplayText:ToString() end
function tabText(row) return optionRoot.rows[row].DisplayText:ToString() end
""")
TITLE_ONLY = 1
PAGE_LINES = '{ "Goal: win the last battle", "", "Checks: 12 of 480" }'   # a blank line makes no heading
# Round 87 (the user): two tabs. Gameplay's is our settings, Graphics' holds the page's lines with
# its own rows hidden. These run with headings; Command rows, the default since round 88, below.
assert lua("G.APMENU.seedRows") == "command"
L.execute("G.APMENU.seedRows = 'heading'")
lines = list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())
assert lines[-1] == "mode ap: 4 game rows hidden, 2 heading rows on the Seed tab", lines
# Round 103 (the user): the Seed tab is the Graphics tab, for its monitor icon
assert lua("tabText('NewRow')") == "Settings" and lua("tabText('NewRow_0')") == "Seed"
assert lua("optionRoot.rows.NewRow_3.Condition:ToString()") == NEVER, "the other tabs are left out"
assert lua("gameSetting.rows['難易度'].ShowCommandData.ShowType") == TITLE_ONLY
assert lua("seedSetting.rows.NewRow.ShowCommandData.ShowType") == TITLE_ONLY, "the graphics rows are hidden"
assert lua("seedSetting.rows.NewRow_4.ShowCommandData.ShowType") == TITLE_ONLY, "so is the Reset button"
assert lua("gameSetting.rows.FFRAP_Exp.ShowCommandData.ShowType") == 2, "our rows stay"
assert lua("rowText('FFRAP_Info1', seedSetting)") == "Goal: win the last battle"
assert lua("rowText('FFRAP_Info2', seedSetting)") == "Checks: 12 of 480"
assert lua("rowText('FFRAP_Info1')") is None, "not under the settings"
assert lua("G.APMENU.Written()") is True
assert list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())[-1] == "mode ap: already so"
# Round 88: the game loads a table again with the page open (here the Seed tab's); the page is
# written again, and the ShowTypes saved first still put the game's rows back
L.execute("""
local function fresh(label) return { ShowCommandData = { ShowType = 0 }, DisplayText = { ToString = function() return label end } } end
seedSetting.rows = { NewRow = fresh("Master"), NewRow_4 = fresh("Reset") }
""")
assert lua("G.APMENU.Written()") is False
lines = list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())
assert lines[-1] == "mode ap: 4 game rows hidden, 2 heading rows on the Seed tab (written again)", lines
assert lua("rowText('FFRAP_Info1', seedSetting)") == "Goal: win the last battle"
assert lua("seedSetting.rows.NewRow.ShowCommandData.ShowType") == TITLE_ONLY
assert lua("G.APMENU.Written()") is True
# the tab list loaded again: its names are the game's, so the page is written again too
L.execute("optionRoot.rows.NewRow.DisplayText = FText('Gameplay')")
assert lua("G.APMENU.Written()") is False
assert list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())[-1].endswith("(written again)")
assert lua("tabText('NewRow')") == "Settings"
lines = list(L.eval("G.APMENU.Mode('game', {}, say)").values())
assert lines[-1] == "mode game: rows shown again, 2 of 2 heading rows removed", lines
# Round 103: removed last first, so the row map's freed slots take them back in order at the next
# open (the page's rows changed order at each open)
removes = [l for l in L.eval("says").values() if l.startswith("apmenu: RemoveRow FFRAP_")]
assert removes[:2] == ["apmenu: RemoveRow FFRAP_Info2", "apmenu: RemoveRow FFRAP_Info1"], removes
assert lua("tabText('NewRow')") == "Gameplay" and lua("tabText('NewRow_0')") == "Graphics"
assert lua("gameSetting.rows['難易度'].ShowCommandData.ShowType") == 2 and lua("gameSetting.rows['初期化'].ShowCommandData.ShowType") == 0
assert lua("seedSetting.rows.NewRow.ShowCommandData.ShowType") == 0 and lua("seedSetting.rows.NewRow_4.ShowCommandData.ShowType") == 0
assert lua("rowText('FFRAP_Info1', seedSetting)") is None, "the heading rows are gone"
assert lua("tabText('NewRow')") == "Gameplay", "the name saved before the tab list was loaded again"
assert lua("gameSetting.rows.FFRAP_Exp") is None, \
    "round 88: our rows leave the table, so System > Options and the title screen lack them"
assert lua("optionRoot.rows.NewRow_3.Condition:ToString()") == "", "every tab again"
# split off: one tab named Archipelago, the lines under our settings, Graphics left out (round 87)
L.execute("G.APMENU.split = false")
lines = list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())
assert lines[-1] == "mode ap: 2 game rows hidden, 2 heading rows", lines
assert lua("tabText('NewRow')") == "Archipelago" and lua("tabText('NewRow_0')") == "Graphics"
assert lua("optionRoot.rows.NewRow_0.Condition:ToString()") == NEVER
assert lua("seedSetting.rows.NewRow.ShowCommandData.ShowType") == 0, "the graphics rows untouched"
assert lua("rowText('FFRAP_Info1')") == "Goal: win the last battle"
L.eval("G.APMENU.Mode('game', {}, say)")
assert lua("rowText('FFRAP_Info1')") is None and lua("tabText('NewRow')") == "Gameplay"
assert lua("optionRoot.rows.NewRow_0.Condition:ToString()") == ""
L.execute("G.APMENU.split = true")
# Round 88: the seed's lines as Command rows, so the cursor and a gamepad's scroll reach them
L.execute("G.APMENU.seedRows = 'command'")
lines = list(L.eval(f"G.APMENU.Mode('ap', {PAGE_LINES}, say)").values())
assert lines[-1] == "mode ap: 4 game rows hidden, 2 command rows on the Seed tab", lines
COMMAND_TYPE = 14
assert lua("seedSetting.rows.FFRAP_Info1.Type") == COMMAND_TYPE
L.eval("G.APMENU.Mode('game', {}, say)")
print("options page probe: ok")

# Round 84 (the user): fast travel from a dungeon. The condition that checks the map type travels
# with the usual confirm dialog; the event and not-visited conditions stay; off puts it back.
L.execute("""
local function cond(mapType, tag)
  return { Condition = { bCheckMapType = mapType }, Behavior = { bCanTravel = false, DialogTag = { TagName = FName(tag) } } }
end
wldParam = { FastTravelProperty = { ConditionBehaviorList = {
  cond(true, 'UI.Dialog.Box.Map.FastTravel.CanNot.MapType'), cond(false, 'UI.Dialog.Box.Map.FastTravel.CanNot.Event'),
  cond(false, 'UI.Dialog.Box.Map.FastTravel.CanNot.LockMap') } } }
wldParam.IsValid = function() return true end
wldParam.HasAnyInternalFlags = function() return false end
wldParam.HasAnyFlags = function() return false end
local prevWldFFO = FindFirstOf
function FindFirstOf(c) if c == 'CPP_DA_WldMapParameter' then return wldParam end return prevWldFFO(c) end
function travelRule(i)
  local b = wldParam.FastTravelProperty.ConditionBehaviorList[i].Behavior
  return tostring(b.bCanTravel) .. ' ' .. b.DialogTag.TagName:ToString()
end
""")
assert lua("G.DungeonFastTravel(true)") == "allowed from dungeons"
assert lua("travelRule(1)") == "true UI.Dialog.Box.Map.FastTravel"
assert lua("travelRule(2)") == "false UI.Dialog.Box.Map.FastTravel.CanNot.Event", "an event under way still refuses"
assert lua("travelRule(3)") == "false UI.Dialog.Box.Map.FastTravel.CanNot.LockMap", "a place not visited still refuses"
assert lua("G.DungeonFastTravel(true)") is None, "nothing to write the second time"
assert lua("G.DungeonFastTravel(false)").startswith("refused from dungeons again")
assert lua("travelRule(1)") == "false UI.Dialog.Box.Map.FastTravel.CanNot.MapType"
print("dungeon fast travel: ok")

# Round 84 (the user): the Airship item marks the airship's maps visited, for fast travel.
L.execute("""
perMapLib = { visited = { [20002] = true }, known = {} }
function perMapLib:IsVisited(m) return self.visited[m] == true end
function perMapLib:AddKnownMap(m) self.known[m] = true end
function perMapLib:AddVisitedMap(m) self.visited[m] = true end
perMapLib.IsValid = function() return true end
local prevPerMapFind = StaticFindObject
function StaticFindObject(p)
  if p == '/Script/mucha.Default__CPP_BFL_SaveData_PerMap' then return perMapLib end
  return prevPerMapFind(p)
end
""")
assert lua("table.concat(G.MarkVisited(G.AIRSHIP_MAPS), ',')") == "20001", "the deck was visited already"
assert lua("perMapLib.known[20001]") is True
assert lua("#G.MarkVisited(G.AIRSHIP_MAPS)") == 0, "nothing the second time"
print("airship visited: ok")

# Round 82 result: the Tutorial screen opens from the entry as one framed window. The page sets
# its title and description, hides the image box, the arrows and the page count, widens the text
# box, and writes only what differs, so a screen the game fills again is put back on the next tick.
L.execute(r"""
local function widget(name, text, kids)
  local w = { name = name, text = text, vis = 4, cleared = false, kids = kids or {} }
  function w:IsValid() return true end
  function w:HasAnyInternalFlags() return false end
  function w:HasAnyFlags() return false end
  function w:GetFName() local n = self.name; return { ToString = function() return n end } end
  function w:GetChildrenCount() return #self.kids end
  function w:GetChildAt(i) return self.kids[i + 1] end
  function w:GetText() local s = self.text; return { ToString = function() return s end } end
  function w:SetText(t) self.text = t:ToString() end
  function w:GetVisibility() return self.vis end
  function w:SetVisibility(v) self.vis = v end
  function w:ClearHeightOverride() self.cleared = true end
  function w:SetWidthOverride(x) self.width = x end
  w.opacity = 1.0
  function w:GetRenderOpacity() return self.opacity end
  function w:SetRenderOpacity(o) self.opacity = o end
  return w
end
pageParts = {}
for _, n in ipairs({ "SizeBox_2", "Overlay_ButtonNext", "Overlay_ButtonPreview", "HorizontalBox_215" }) do
  pageParts[n] = widget(n)
end
pageParts.Text_Title = widget("Text_Title", "TITLE")
pageParts.Text_Description = widget("Text_Description", "TEXT")
pageParts.SizeBox_1 = widget("SizeBox_1", nil, { pageParts.Text_Description })
-- as in the round 82 tree: the parts are in WBP_Tutorial's own widget tree, under the layout's
-- root, and the game's GetWidgetFromName found none of them, so the fake has none
local inner = widget("WBP_Tutorial")
tutorialInner = inner
inner.WidgetTree = { RootWidget = widget("VerticalBox_0", nil, { pageParts.Text_Title, pageParts.SizeBox_2,
  pageParts.SizeBox_1, pageParts.HorizontalBox_215, pageParts.Overlay_ButtonNext, pageParts.Overlay_ButtonPreview }) }
tutorialHost = setmetatable(widget("host"), { __tostring = function() return "WBP_MainMenuLayout_C_1.WBP_TutorialLayout_C_1" end })
tutorialHost.WidgetTree = { RootWidget = widget("Overlay_0", nil, { widget("WBP_BGDimming"), inner }) }
tutorialHost.active = true
tutorialHost.CloseStateProperty = { IsEnableDefaultFinisheCall = false }
function tutorialHost:IsActivated() return self.active end
local prevFAO = FindAllOf
function FindAllOf(c) if c == "WBP_TutorialLayout_C" then return { tutorialHost } end return prevFAO(c) end
says = {}
""")
L.execute('bodies = 0; function pageBody() bodies = bodies + 1; return "Goal: x\\nChecks: 2 of 5" end')
page = lambda: L.eval('G.APMENU.Page("Archipelago", pageBody, say)')
assert page() == "written"
assert lua("pageParts.Text_Title.text") == "Archipelago" and lua("pageParts.Text_Description.text") == "Goal: x\nChecks: 2 of 5"
for hidden in ("SizeBox_2", "Overlay_ButtonNext", "Overlay_ButtonPreview", "HorizontalBox_215"):
    assert lua(f"pageParts.{hidden}.vis") == 1, hidden
assert lua("pageParts.SizeBox_1.cleared") is True and lua("pageParts.SizeBox_1.width") == 1180, "the text box: wider, any height"
first = lua("#says")
assert first >= 6 and lua("says[1]") == "apmenu: page title", list(L.eval("says").values())
assert page() == "same" and lua("#says") == first, "nothing to write, nothing told"
L.execute('pageParts.Text_Description.text = "TEXT"; pageParts.SizeBox_2.vis = 4')   # the game fills it again
assert page() == "written" and lua("pageParts.Text_Description.text").startswith("Goal: x")
assert lua("pageParts.SizeBox_2.vis") == 1 and lua("#says") == first, "the same screen: the steps are told once"
tree = list(L.eval('G.APMENU.Tree()').values())
assert tree[0].startswith("host ") and any(line.startswith("          ? Text_Description") for line in tree), tree
# round 83: Back asked the screen to close and the menu turned it off at once, so its closing
# never finished, and the next open and Back were refused. The page turns on the base class's
# default finish for a close, once per screen.
assert lua("tutorialHost.CloseStateProperty.IsEnableDefaultFinisheCall") is True
assert "apmenu: page CloseStateProperty.IsEnableDefaultFinisheCall true" in list(L.eval("says").values())
# If the screen still comes back at opacity 0 with no open under way, the page asks it to open
# (OnRequestOpen) once per opening; its open animation then runs up from 0.
L.execute('''
  tutorialHost.opens, tutorialHost.IsOpeningProcess, tutorialHost.IsCanInput = 0, false, false
  function tutorialHost:OnRequestOpen() self.opens = self.opens + 1; self.opacity = 0.2 end
  function tutorialHost:OnRequestClose() self.closes = (self.closes or 0) + 1 end
  tutorialHost.opacity = 0
''')
assert page() == "written" and lua("tutorialHost.opens") == 1
assert lua("says[#says]") == ("apmenu: page screen at opacity 0 (IsOpeningProcess false, IsClosingProcess nil, "
                              "IsCanInput false, bIsCanceling nil, close finish true); OnRequestOpen"), lua("says[#says]")
assert page() == "same" and lua("tutorialHost.opens") == 1, "not again while its animation runs"
L.execute("tutorialHost.active = false")
assert L.eval(f'select(2, G.APMENU.Page("Archipelago", pageBody, say))') == "not open"
L.execute("tutorialHost.active = true; tutorialHost.opacity = 0; tutorialHost.IsOpeningProcess = true")
page()
assert lua("tutorialHost.opens") == 1, "the menu's own open is under way: left alone"
L.execute("tutorialHost.active = false")
page()
L.execute("tutorialHost.active = true; tutorialHost.IsOpeningProcess = false")    # the next opening
page()
assert lua("tutorialHost.opens") == 2, "asked again on the next opening"
L.execute("tutorialHost.opacity = 1.0")
state = "\n".join(L.eval('G.APMENU.State()').values())
assert "activated true  visible nil  visibility 4  opacity 1.0; IsOpeningProcess false" in state, state
assert "main menu scene stack: " in state, state
# close asks an open screen to close the way Back does
assert lua(f'G.APMENU.Close(say)').startswith("close asked; IsOpeningProcess false")
assert lua("tutorialHost.closes") == 1
# the fallback: a screen off but still closing gets FinishedClose after three ticks, once
L.execute('''
  tutorialHost.active, tutorialHost.IsClosingProcess, tutorialHost.finishes = false, true, 0
  function tutorialHost:FinishedClose() self.finishes = self.finishes + 1 end
''')
assert lua(f'G.APMENU.Unstick(say)') is None
assert lua(f'G.APMENU.Unstick(say)') is None
assert lua(f'G.APMENU.Unstick(say)').startswith("finished a stale close")
assert lua(f'G.APMENU.Unstick(say)') is None and lua("tutorialHost.finishes") == 1, "once"
# the empty background: our screen off, the menu still on our scene. close pops the scene.
L.execute(f'''
  menuVM = {{ SceneDataStack = {{ {{ TagName = FName("UI.MainMenu.Scene.Root") }}, {{ TagName = FName("{OWN_TAG}") }} }} }}
  function menuVM:IsValid() return true end
  function menuVM:HasAnyInternalFlags() return false end
  function menuVM:HasAnyFlags() return false end
  function menuVM:PopScene() table.remove(self.SceneDataStack) end
  local prevFFO = FindFirstOf
  function FindFirstOf(c) if c == "CPP_VM_MainMenu" then return menuVM end return prevFFO(c) end
''')
assert lua(f'G.APMENU.Close(say)') == "PopScene; the stack ends with UI.MainMenu.Scene.Root"
assert lua(f'G.APMENU.Close(say)').startswith("the page is not open and the menu is not on it")
assert L.eval(f'select(2, G.APMENU.Page("Archipelago", pageBody, say))') == "not open"
made = lua("bodies")
L.eval(f'G.APMENU.Page("Archipelago", pageBody, say)')
assert lua("bodies") == made, "the text is made only while the page is open"
print("archipelago page: ok")

# Round 120 probe: ffrap_lift lists the keypad lifts and calls one's CallSwitch or Execute_BP
SHIPYARD_TOP_LIFT, TOP_STOP, UP = 75, 1, 1
L.execute(f'''
  liftCalls = {{}}
  shipLift = {{ m_UniqueId = {SHIPYARD_TOP_LIFT}, m_GimmickCondition = 0, m_CurrentSplineKeyIndex = 0, m_IsCallSwitch = false }}
  function shipLift:IsValid() return true end
  function shipLift:HasAnyInternalFlags() return false end
  function shipLift:HasAnyFlags() return false end
  function shipLift:GetClass() return {{ GetFName = function() return {{ ToString = function() return "BP_MapGimmick_Floor_Elevator_Interact_002_C" end }} end }} end
  function shipLift:K2_GetActorLocation() return {{ X = -400, Y = 14400, Z = -1620 }} end
  function shipLift:GetComponentByClass() return {{ GetNumberOfSplinePoints = function() return 2 end }} end
  function shipLift:CallSwitch(stop, dir) liftCalls[#liftCalls + 1] = "call " .. stop .. " " .. dir return stop ~= self.m_CurrentSplineKeyIndex end
  function shipLift:Execute_BP(stop) liftCalls[#liftCalls + 1] = "exec " .. stop end
  local prevLiftFAO = FindAllOf
  function FindAllOf(c) if c == "BP_MapGimmick_Floor_Elevator_Interact_C" then return {{ shipLift }} end return prevLiftFAO(c) end
''')
listed = list(L.eval("G.LiftProbe()").values())
assert listed[0].startswith(f"lift {SHIPYARD_TOP_LIFT} (BP_MapGimmick_Floor_Elevator_Interact_002_C): condition 0, stop 0 of 2 points, "
                            "call switch false, at -400, 14400, -1620"), listed
called = list(L.eval(f"G.LiftProbe({SHIPYARD_TOP_LIFT}, 'call', {TOP_STOP}, {UP})").values())
assert called[-1] == f"CallSwitch({TOP_STOP}, {UP}): true" and L.eval("liftCalls[1]") == f"call {TOP_STOP} {UP}", called
assert list(L.eval(f"G.LiftProbe({SHIPYARD_TOP_LIFT}, 'exec', {TOP_STOP})").values())[-1] == f"Execute_BP({TOP_STOP}): called"
assert list(L.eval("G.LiftProbe(72)").values()) == ["no keypad lift 72 on this map"]
print("lift probe: ok")
