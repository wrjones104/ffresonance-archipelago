"""main.lua against a stub game module and stubbed UE4SS functions (Lua 5.4 via lupa): the item
queue, checks, sessions, save binding, the per-save count, the skip command, the title entry, the
Archipelago new game, the item feed and the chest pop-up. Each numbered section is one feature."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import paths  # noqa: E402

import os
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
assert lua("root.rows.a.ItemId") == -1 and lua("root.rows.a.Money") == 1
assert lua("parent.rows.b.Money") == 1 and lua("root.rows.t.ItemId") == 5
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
function G.IsChestOpenInSave(m, uid) return G.saveOpen[m .. ":" .. uid] == true end
function G.ChestSaveKeys(m, c) return "" end
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
function G.UnlockVision() return "ok", "" end
function G.HasVision(id) return (G.owned or {})[id] == true end
function G.AddUnit() return "ok", "" end
function G.SetFlag() return "ok", "" end
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
function G.AirshipState() return "placed true" end
function G.AirshipCondition(c) G.airshipWrote = c; return c end
function G.NoLandShadow() return 0, 1, { "box" } end
G.TITLE_NEW_GAME, G.TITLE_ARCHIPELAGO, G.titleAdds = 2, 5, 0
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
function G.FeedLine(text, now) if not G.feedReady then return false, "no field HUD" end G.feed[#G.feed + 1] = text; return true end
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
      function RegisterHook(name, fn) hooks[name] = fn end
    ''')
    G = L.execute(STUB)
    L.globals().package.loaded["game"] = G
    L.execute(f'dofile("{SCRIPTS}/main.lua")')
    return L, G


# a 0.3.0-style seen.tsv line is read and converted
open(path("seen.tsv"), "w", encoding="utf-8", newline="\n").write("xchest\t2002\tu52\trowmap -1\t-1\t1\t-1\t\n")

L, G = boot()
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

# the save says chest 3020:1 (uid 7 in map 2002) is open while the actor does not: reported
G.saveOpen["2002:7"] = True
tick(2)
assert "check\tchest:3020:1\n" in read("ap_out.txt")

# sync from the save, from another map, after ap_out.txt was lost
G.map = 1000
G.saveOpen["2002:63"] = True                                # chest 3020:3, never seen open live
G.saveOpen["2002:30"] = True                                # shiny 30
os.remove(path("ap_out.txt"))
L, G = boot()
G.map = 1000
G.saveOpen = {"2002:7": True, "2002:63": True, "2002:30": True, "2002:54": True}
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
assert L.eval("root.rows.gil.Money") == 1 and L.eval("root.rows.a.ItemId") == -1
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
assert out.startswith(f"hello\t{VERSION}\t1\nseed\tS1:1\n") and "chest:2001:0" not in out, out
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
assert out.startswith(f"hello\t{VERSION}\t1\nseed\tS2:3\n") and "shiny:1000:30" in out and "chest:3020:1" not in out, out
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
# a later load of some other save does not get the Archipelago treatment
G.story = 1030
load(G, "SD_OTHER", "9999")
assert G.skipRuns == runs + 1
assert G.orders >= 1, "the order is checked once the entry is in"
G.ready = False                                   # back at the title screen
tick(13)                                          # two checks: the line, then the logo
assert f"FFRArchipelago {VERSION}" in list(G.titleLines.values()), list(G.titleLines.values())
assert G.describes == 1, "the layout is logged once"
assert len(list(G.logos.values())) >= 1 and list(G.logos.values())[0].endswith("Assets/archipelago_logo.png"), list(G.logos.values())
G.ready = True
print("archipelago new game: ok")

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
inbox("seed\tS12:0:1\nscout\tchest:3020:3\tHookshot\tAlice\t1\t0\nscout\tchest:3020:2\tTent\tJones\t0\t1\n", "w")
L, G = boot5("SD_POP", "0", {})
tick = lambda k: [L.execute("tickFn()") for _ in range(k)]
G.story = 1000
G.chests = L.table()
tick(10)                                   # a new game, linked (no title entry here)
G.popupReady = False                       # the pop-up comes up a moment after the check
G.chests = L.table_from({1: L.table_from({"uid": 3, "open": True, "rowMap": 3020, "rowId": 3, "uniqueId": 63,
                                          "typeId": 63, "itemId": 7, "itemNum": 4, "money": -1})})
tick(4)
assert "check\tchest:3020:3" in read("ap_out.txt"), read("ap_out.txt")
assert list(G.popups.values()) == [], "waits for the pop-up"
G.popupReady = True
tick(2)
assert list(G.popups.values()) == ["You found the following for Alice:\nHookshot"], list(G.popups.values())
# an own item; and a chest with no scout leaves the pop-up alone
G.chests = L.table_from({1: L.table_from({"uid": 2, "open": True, "rowMap": 3020, "rowId": 2, "uniqueId": 8,
                                          "typeId": 8, "itemId": 209, "itemNum": 3, "money": -1}),
                         2: L.table_from({"uid": 4, "open": True, "rowMap": 3020, "rowId": 4, "uniqueId": 9,
                                          "typeId": 9, "itemId": 1, "itemNum": 1, "money": -1})})
tick(6)
assert list(G.popups.values())[1:] == ["You obtained the following:\nTent"], list(G.popups.values())
assert G.restores > 0
# 0.11.2: the fast check: a pop-up that has just come up scans the chests at once and rewrites
# the pop-up in the same pass, with no regular tick in between
n = len(list(G.popups.values()))
inbox("scout\tchest:3020:5\tLongshot\tRat2\t1\t0\n")
tick(1)
G.chests = L.table_from({1: L.table_from({"uid": 5, "open": True, "rowMap": 3020, "rowId": 5, "uniqueId": 10,
                                          "typeId": 10, "itemId": 1, "itemNum": 1, "money": -1})})
G.popupOpen = True
L.execute("fastFn()")
assert "check\tchest:3020:5" in read("ap_out.txt"), "reported by the fast check"
assert list(G.popups.values())[n:] == ["You found the following for Rat2:\nLongshot"], list(G.popups.values())[n:]
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
assert list(G.popups.values())[n + 1:] == ["You found the following for Rat2:\nLongshot"], list(G.popups.values())
# still open on later scans: no more pop-ups
tick(6)
assert len(list(G.popups.values())) == n + 2
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
# defaults (range 2, at 80), and scale.txt.
L, G = boot()
L.globals().G = G
L.execute("""
G.scaleCalls, G.partyLv, G.onField = {}, 40, true
function G.PartyLevel() return G.partyLv, "1001:" .. G.partyLv end
function G.LevelBand(lv, range, at)
  local c = math.max(1, math.floor(lv * (at or 100) / 100 + 0.5))
  return c - range, c + range, c
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
