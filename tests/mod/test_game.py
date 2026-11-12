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
function StaticFindObject(path)
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
def ratio(stat, f, t):
    b, c = CURVE[stat]
    f, t = max(1, min(f, 70)), max(1, min(t, 70))
    return (t / f) ** b * math.exp(c * (t - f))
def scaled(v, stat, f, t, knob=100):
    return max(1, math.floor(v * ratio(stat, f, t) * knob / 100 + 0.5))
st = L.eval("G.ScaledStats({ Level = 1, MaxHitPoint = 68, MaxBreakPoint = 50, Attack = 30, Defence = 30,"
            " Intelligence = 15, Mind = 30, Agility = 13, Experience = 12, Money = 20 }, 11)")
assert st.Level == 11 and st.MaxHitPoint == scaled(68, "MaxHitPoint", 1, 11), dict(st)
assert st.Attack == scaled(30, "Attack", 1, 11) and st.Defence == scaled(30, "Defence", 1, 11), dict(st)
# round 31's case: the Soldier (level 30, attack 189) pulled to level 3 now has about a level 3
# enemy's attack (the shipped ones have 45), not 56
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
assert L.eval("unitRows.boss.Level") == 20 and L.eval("unitRows.boss.MaxHitPoint") == scaled(2000, "MaxHitPoint", 4, 20)
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
assert L.eval("unitRows.hunger.Level") == 6 and L.eval("unitRows.hunger.MaxHitPoint") == scaled(HUNGER_HP, "MaxHitPoint", HUNGER_LEVEL, 6), "the boss band"
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
assert L.eval("unitRows.fang.Level") == 6 and L.eval("unitRows.fang.MaxHitPoint") == scaled(ARENA_HP, "MaxHitPoint", ARENA_LEVEL, 6), "the boss band"
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
assert BOXES == 21 and len(L.eval("G.CONTINENTS")) == 10
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
assert line and "18 boxes" in line, line
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
      C01_ArijigokuWin = { ContinuousEventList = {
        { Condition = "!{flag:10}", EventId = FName("C01_ArijigokuWin_01") },
        { Condition = "{flag:10}", EventId = FName("C01_ArijigokuWin_02") } } } },
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
