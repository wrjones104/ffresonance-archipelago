-- game.lua: every call FFRArchipelago makes into Final Fantasy Resonance.
--
-- Nothing outside this file touches the engine, so when a game patch moves something there is
-- one place to fix. The class names, object paths and call shapes come from two mods that
-- measured them against the running game:
--   * FFRSLib (part of FFR Modding Tools by Kanaruu): AddInventory, AddUnit, SetFlag/GetFlag,
--     the story counter on the save, the vision list, and the settings-panel Toast.
--   * FFRS_QoL: CPP_BFL_SaveDataMap:IsOpenTreasureBox(mapId, uid) for looted chests.
-- This file is our own code calling the same functions. It needs neither mod at run time,
-- except that Toast uses the ModSettings panel when it is installed.
--
-- Grant functions return a code and a detail string:
--   "ok"    the game took it
--   "retry" the game is not ready (title screen, loading, no party view model); try again later
--   "fail"  the game refused it, and retrying will not help (bad id, full party, ...)

local G = {}

-- -------------------------------------------------------------------------------------------
-- Object helpers
-- -------------------------------------------------------------------------------------------

-- True when an object can still be used. FindAllOf can return objects that the engine is
-- destroying: flagged Unreachable or Garbage (internal flags) or BeginDestroyed or
-- FinishDestroyed (object flags). Same masks as FFRSLib.
local function Alive(o)
    if not o then return false end
    local ok, alive = pcall(function()
        return o:IsValid() and not o:HasAnyInternalFlags(0x10200000) and not o:HasAnyFlags(0x18000)
    end)
    return ok and alive == true
end
G.Alive = Alive

local function Find(path)
    local ok, o = pcall(StaticFindObject, path)
    if ok and o and o:IsValid() then return o end
    return nil
end

-- A function library's default object, such as CPP_BFL_SaveDataInventory.
local function Lib(name)
    return Find("/Script/mucha.Default__" .. name)
end

-- Keep UObject references as path strings across ticks and resolve them via StaticFindObject.
-- Cached pointers can be garbage-collected even without a map load, causing IsValid to crash on freed memory.
function G.PathOf(o)
    local ok, full = pcall(function() return o:GetFullName() end)
    return ok and type(full) == "string" and full:match("^%S+ (.+)$") or nil
end

-- The first live instance of a class. Its path is kept, so the next call is one lookup.
local liveCache = {}
local function Live(shortClass)
    local path = liveCache[shortClass]
    local hit = path and Find(path)
    if hit and Alive(hit) then return hit end
    local ok, obj = pcall(FindFirstOf, shortClass)
    if ok and obj and Alive(obj) then
        liveCache[shortClass] = G.PathOf(obj)
        return obj
    end
    liveCache[shortClass] = nil
    return nil
end

-- A number out of a value UE4SS may hand back wrapped (TArray elements, out params).
local function Int(v)
    if type(v) == "number" then return v end
    local ok, got = pcall(function() return v:get() end)
    if ok and type(got) == "number" then return got end
    return nil
end
G.Int = Int

local function PlayerController()
    local ok, all = pcall(FindAllOf, "PlayerController")
    if ok and all then
        for _, c in ipairs(all) do
            if Alive(c) then return c end
        end
    end
    return nil
end

-- -------------------------------------------------------------------------------------------
-- Game state
-- -------------------------------------------------------------------------------------------

-- The save data object the game is running on (UCPP_MuchaGameSaveData), or nil.
function G.SaveData()
    local mgr = Live("CPP_MuchaSaveDataManager")
    if not mgr then return nil end
    local ok, sd = pcall(function() return mgr.m_pGameSaveData end)
    if ok and sd and sd:IsValid() then return sd end
    return nil
end

-- The story counter: element 0 of Progress.Progress. DT_MainScenario names checkpoints from
-- 1020 to 8050, and the thousands digit is the chapter.
function G.StoryCounter()
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, v = pcall(function() return sd.Progress.Progress[1] end)
    if not ok then return nil end
    return Int(v)
end

-- The save's battles-won counter (Player.WinNum), or nil. The prologue skip sets it to 3, the
-- prologue's own wins.
function G.WinCount()
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, v = pcall(function() return sd.Player.WinNum end)
    return ok and Int(v) or nil
end

-- The map the player is on, as the save keys it: CPP_MapManager:GetSameMapId(). Shared areas
-- (e.g. a town's interior and exterior) return the same id, which matches CPP_BFL_SaveDataMap.
-- The save's own Map.mapId (G.MapId below) lags behind transitions, so it is never used for keys.
function G.CurrentMap()
    local mgr = Live("CPP_MapManager")
    if not mgr then return nil end
    local ok, id = pcall(function() return mgr:GetSameMapId() end)
    if not ok then return nil end
    id = Int(id)
    if id and id >= 0 then return id end
    return nil
end

-- The map the save says the player is on. It is the save's record, which is only written now
-- and then, so it is reported for comparison and not used for keys.
function G.MapId()
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, v = pcall(function() return sd.Map.mapId end)
    if not ok then return nil end
    return Int(v)
end

-- -------------------------------------------------------------------------------------------
-- Which save is loaded
-- -------------------------------------------------------------------------------------------
-- The approach is FFRBestiary's (installed in this game folder), which keeps its data per save
-- slot: a load or a new game makes a new save data object, the loaded save's timestamp changes
-- when the game saves, and the slot summaries carry the same timestamp.

-- The loaded save data object's full name. Its unique number differs for every object, so a
-- change of name means a load or a new game.
function G.SaveObjectName()
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, name = pcall(function() return sd:GetFullName() end)
    if ok and name then return tostring(name) end
    return nil
end

-- The loaded save's timestamp (FDateTime ticks), as text so the 64-bit value compares exactly.
function G.SavedTicks()
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, t = pcall(function() return sd.Player.SavedDateTime.Ticks end)
    if ok and t ~= nil then return tostring(t) end
    return nil
end

-- The save slot whose summary has this timestamp (0 is the autosave), or nil: a new game that
-- was never saved, or a summary that has not caught up with a save yet. Read from the manager's
-- own summary map, as FFRBestiary does: FindGameSaveDataSummary's out-param struct comes back as
-- wrappers into memory that is freed after the call.
function G.SlotForTicks(ticks)
    local mgr = Live("CPP_MuchaSaveDataManager")
    if not (mgr and ticks) then return nil end
    local found
    pcall(function()
        mgr.GameSaveDataSummaryMap:ForEach(function(key, value)
            local sum = value:get()
            if not found and sum.bExists and tostring(sum.DateTime.Ticks) == ticks then found = Int(key:get()) end
        end)
    end)
    return found
end

-- True when a save is loaded and the field is running (safe to grant). The title screen may
-- have save data too, so the map manager is the decisive check.
function G.InGame()
    return G.SaveData() ~= nil and Live("CPP_MapManager") ~= nil
end

-- -------------------------------------------------------------------------------------------
-- Grants
-- -------------------------------------------------------------------------------------------

local function Held(inv, id)
    if not inv.FindInventory then return nil end
    local ok, n = pcall(function() return inv:FindInventory(id) end)
    return ok and Int(n) or nil
end

-- Puts n of an item into the bag: consumables, equipment, seeds, valuables, artifacts.
function G.GrantItem(id, n)
    local inv = Lib("CPP_BFL_SaveDataInventory")
    if not (inv and inv.AddInventory) then return "retry", "AddInventory not found" end
    local before = Held(inv, id)
    local ok, err = pcall(function() inv:AddInventory(id, n) end)
    if not ok then return "fail", "AddInventory raised: " .. tostring(err) end
    local after = Held(inv, id)
    if before and after and after == before then
        -- A bad id or an item at its stack limit. Retrying cannot help, so it is a fail.
        return "fail", "count unchanged at " .. after .. " (bad id, or the item is at its limit)"
    end
    return "ok", "held " .. tostring(before) .. " -> " .. tostring(after)
end

-- Whether the save owns a vision: true, false, or nil when the vision library is not loaded.
function G.HasVision(id)
    local lib = Lib("CPP_BFL_Vision")
    if not (lib and lib.HasVision) then return nil end
    local ok, r = pcall(function() return lib:HasVision(id) end)
    if not ok then return nil end
    return r == true
end

local visionRows
local function VisionRowExists(id)
    if not visionRows then
        local dt = Find("/Game/Datatable/Item/Vision/DT_VisionItemData.DT_VisionItemData")
        if not dt then return nil end
        local ids, count = {}, 0
        pcall(function()
            dt:ForEachRow(function(_, row)
                ids[row.ID] = true
                count = count + 1
            end)
        end)
        if count == 0 then return nil end
        visionRows = ids
    end
    return visionRows[id] == true
end

-- A vision entry's synchro map has one key per party member, matching the game's vision struct.
G.VISION_SYNCHRO_KEYS = { 1001, 1002, 1003, 1006, 1004, 1005, 1007, 1008 }

-- Adds a vision to the save's vision list and to the bag, the way FFRSLib's ffrs_vision_unlock
-- does: grow visionList by one zeroed entry, set its ID, initialize the synchro-map keys to 0,
-- and call AddInventory(id, 1).
function G.UnlockVision(id)
    local sd = G.SaveData()
    if not sd then return "retry", "no save data" end
    local exists = VisionRowExists(id)
    if exists == nil then return "retry", "vision table not loaded" end
    if not exists then return "fail", "no DT_VisionItemData row for " .. id end

    local function Has() return G.HasVision(id) == true end
    if Has() then return "ok", "already owned" end

    local list
    if not pcall(function() list = sd.visionList end) or not list then
        return "retry", "visionList unreadable"
    end
    local n = #list

    -- Reading one past the end grows a UE4SS TArray by a zeroed element.
    local okGrow = pcall(function() local _ = list[n + 1] end)
    if not okGrow or #list ~= n + 1 then return "fail", "could not grow visionList" end
    local okSet = pcall(function()
        local e = list[n + 1]
        e.ID = id
        e.awakeningPoint = 0
    end)
    local wrote
    pcall(function() wrote = list[n + 1].ID end)
    if not okSet or wrote ~= id then
        return "fail", "blank vision entry left in the loaded save; reload without saving"
    end
    local keys = 0
    pcall(function()
        local to = list[n + 1].synchroPoints
        for _, key in ipairs(G.VISION_SYNCHRO_KEYS) do
            to:Add(key, 0)
            keys = keys + 1
        end
    end)
    local inv = Lib("CPP_BFL_SaveDataInventory")
    if inv and inv.AddInventory then pcall(function() inv:AddInventory(id, 1) end) end
    return "ok", "visionList " .. n .. " -> " .. (n + 1) .. ", synchro keys " .. keys .. ", HasVision " .. tostring(Has())
end

-- Gil, through the player save library: GetCurrentMoney, GetMaxNumMoney and
-- SetCurrentMoney(value, true, false), as FFRS_QoL's gil multiplier calls them.
function G.GrantGil(n)
    local lib = Lib("CPP_BFL_SaveDataPlayer")
    if not (lib and lib.GetCurrentMoney and lib.SetCurrentMoney) then
        return "retry", "player save library not loaded"
    end
    local cur
    pcall(function() cur = Int(lib:GetCurrentMoney()) end)
    if not cur then return "retry", "cannot read current gil" end
    local cap
    pcall(function() cap = Int(lib:GetMaxNumMoney()) end)
    local want = cur + n
    if cap and cap > 0 and want > cap then want = cap end
    local ok, err = pcall(function() lib:SetCurrentMoney(want, true, false) end)
    if not ok then return "fail", "SetCurrentMoney raised: " .. tostring(err) end
    local after
    pcall(function() after = Int(lib:GetCurrentMoney()) end)
    if after and after ~= want then return "fail", "gil reads " .. after .. " after setting " .. want end
    return "ok", "gil " .. cur .. " -> " .. tostring(after or want)
end

-- Party members. CPP_VM_Party:AddUnit puts a unit in the active party and fails when full.
-- The roster is tracked via JoinStatus in sd.unitParameterList
-- (eUnitJoinStatus: 0 Join, 1 NotJoin, 2 Leave, 3 TemporalLeave, 4 Lost). Units enter the active
-- party when room exists and otherwise join the roster.
local function PartyVM() return Live("CPP_VM_Party") end

local function Joined(vm, id)
    local ok, r = pcall(function() return vm:IsJoinedUnit(id) end)
    return ok and r == true
end

-- AddUnit leaves JoinStatus at NotJoin (which breaks EXP and equipped gear), so every join calls G.FinishJoin.
function G.AddUnit(id)
    local vm = PartyVM()
    if not (vm and vm.AddUnit) then return "retry", "party view model not loaded" end
    if G.UnitJoinStatus(id) == 0 then return "ok", "already joined" end
    if Joined(vm, id) then
        G.FinishJoin(id)
        return "ok", "already joined"
    end
    local ok, r = pcall(function() return vm:AddUnit(id) end)
    if not ok then return "fail", "AddUnit raised: " .. tostring(r) end
    if Joined(vm, id) then
        G.FinishJoin(id)
        return "ok", "in the active party (AddUnit returned " .. tostring(r) .. ")"
    end
    -- The party is full: the roster only.
    local how = G.FinishJoin(id)
    if G.UnitJoinStatus(id) == 0 then
        return "ok", "joined the roster through " .. tostring(how) .. " (AddUnit returned " .. tostring(r) .. ")"
    end
    return "fail", "did not join (AddUnit returned " .. tostring(r) .. "; JoinStatus write " .. tostring(how) .. ")"
end

-- Unit ids in the active party, as a plain table, or nil.
function G.PartyIds()
    local vm = PartyVM()
    if not (vm and vm.GetPartyUnitIdList) then return nil end
    local ok, list = pcall(function() return vm:GetPartyUnitIdList() end)
    if not ok or not list then return nil end
    local out = {}
    local okAll = pcall(function()
        for i = 1, #list do out[#out + 1] = Int(list[i]) end
    end)
    return okAll and out or nil
end

-- Story flags, the {flag:N} values the game's conditions read.
local function ProgressLib() return Lib("CPP_BFL_SaveDataProgress") end

function G.GetFlag(i)
    local lib = ProgressLib()
    if not (lib and lib.GetFlag) then return nil end
    local ok, v = pcall(function() return lib:GetFlag(i) end)
    if not ok then return nil end
    return v == true
end

function G.SetFlag(i, on)
    local lib = ProgressLib()
    if not (lib and lib.SetFlag) then return "retry", "flag library not loaded" end
    if not pcall(function() lib:SetFlag(i, on) end) then return "fail", "SetFlag raised" end
    local now = G.GetFlag(i)
    if now ~= on then return "fail", "flag reads " .. tostring(now) .. " after setting" end
    return "ok", "flag " .. i .. " = " .. tostring(on)
end

-- The save stamp (round 77): how many of the session's items a save holds, and a tag of the
-- session's seed, kept in the save as event flags. ap_state.txt is per PC and was deleted on
-- updates, so a save moved to another PC or kept across an update was bound again and got every
-- item twice. The game's data reads no flag from 1414 to 1449 (round 40); 1420 to 1431, 1440
-- and 1441 are taken. 12 bits count to 4095 items, and 11 bits give 2047 tags (0 is no stamp).
G.STAMP_COUNT_FLAGS = { 1414, 1415, 1416, 1417, 1418, 1419, 1430, 1432, 1433, 1434, 1435, 1436 }
G.STAMP_TAG_FLAGS = { 1437, 1438, 1439, 1442, 1443, 1444, 1445, 1446, 1447, 1448, 1449 }
G.STAMP_MAX = (1 << #G.STAMP_COUNT_FLAGS) - 1

-- FNV-1a of the session key, folded to 1 .. 2047.
function G.SeedTag(key)
    local h = 2166136261
    for i = 1, #key do
        h = ((h ~ key:byte(i)) * 16777619) & 0xFFFFFFFF
    end
    return h % ((1 << #G.STAMP_TAG_FLAGS) - 1) + 1
end

-- Returns the loaded save's count and tag, or nil when a flag cannot be read.
function G.ReadSaveStamp()
    local function bits(flags)
        local n = 0
        for i, flag in ipairs(flags) do
            local on = G.GetFlag(flag)
            if on == nil then return nil end
            if on then n = n | (1 << (i - 1)) end
        end
        return n
    end
    local count, tag = bits(G.STAMP_COUNT_FLAGS), bits(G.STAMP_TAG_FLAGS)
    if count == nil or tag == nil then return nil end
    return count, tag
end

-- Writes the flags that differ from `count` and `tag`. Returns how many it wrote, or nil and why.
function G.WriteSaveStamp(count, tag)
    local wrote = 0
    for _, set in ipairs({ { G.STAMP_COUNT_FLAGS, count }, { G.STAMP_TAG_FLAGS, tag } }) do
        for i, flag in ipairs(set[1]) do
            local want = (set[2] >> (i - 1)) & 1 == 1
            local now = G.GetFlag(flag)
            if now == nil then return nil, "flag library not loaded" end
            if now ~= want then
                local code, detail = G.SetFlag(flag, want)
                if code ~= "ok" then return nil, detail end
                wrote = wrote + 1
            end
        end
    end
    return wrote
end

-- -------------------------------------------------------------------------------------------
-- Chests
-- -------------------------------------------------------------------------------------------

-- The chests in the loaded maps. Each carries a copy of its chest table row in
-- m_TreasureBoxData, so `rowMap` and `rowId` are the row's own mapId and ID: the location key,
-- whatever map the game currently reports. `uid` (m_Id), `uniqueId` (m_UniqueId) and `typeId`
-- (TypeData.ID) are inspected for save-key matching (`m_UniqueId` is used by the save). `x`, `y`:
-- where it stands, for the player-reach test (round 79).
function G.LiveChests()
    local out = {}
    local ok, all = pcall(FindAllOf, "CPP_MapGimmick_TreasureBox")
    if not ok or not all then return out end
    for _, c in ipairs(all) do
        if Alive(c) then
            pcall(function()
                local e = { uid = Int(c.m_Id), open = c.m_IsOpen == true, actor = c }
                pcall(function()
                    e.rowMap = Int(c.m_TreasureBoxData.mapId)
                    e.rowId = Int(c.m_TreasureBoxData.ID)
                    e.itemId = Int(c.m_TreasureBoxData.ItemId)
                    e.itemNum = Int(c.m_TreasureBoxData.ItemNum)
                    e.money = Int(c.m_TreasureBoxData.Money)
                end)
                pcall(function() e.uniqueId = Int(c.m_UniqueId) end)
                pcall(function() e.typeId = Int(c.TypeData.ID) end)
                pcall(function()
                    local loc = c:K2_GetActorLocation()
                    e.x, e.y = loc.X, loc.Y
                end)
                out[#out + 1] = e
            end)
        end
    end
    return out
end

-- CPP_BFL_SaveDataMap:IsOpenTreasureBox fallback: when the map has no row for that uid yet, it
-- returns another map's row with the same uid. The mod judges by G.SaveOpenRows and logs this only.
function G.IsChestOpenInSave(mapId, uid)
    local lib = Lib("CPP_BFL_SaveDataMap")
    if not (lib and lib.IsOpenTreasureBox) then return nil end
    local ok, r = pcall(function() return lib:IsOpenTreasureBox(mapId, uid) end)
    if not ok then return nil end
    return r == true
end

-- The save's own rows for one map's chests and shinies (Map.mapGimmick{map}.treasureBox), as
-- uid -> IsOpen. A uid with no row is not open. Empty when no save is loaded.
function G.SaveOpenRows(mapId)
    local rows = {}
    local sd = G.SaveData()
    if not sd then return rows end
    pcall(function()
        sd.Map.mapGimmick:ForEach(function(key, value)
            if Int(key:get()) ~= mapId then return end
            value:get().treasureBox.treasureBoxList:ForEach(function(_, element)
                local row = element:get()
                local uid = Int(row.UniqueID)
                if uid then rows[uid] = row.IsOpen == true end
            end)
        end)
    end)
    return rows
end

-- Returns the save key ID used by BP_MapGimmick_TreasureBox and BP_MapGimmick_FieldItem (GetUniqueId).
-- Returns the id, or nil and a reason.
function G.GameUniqueId(actor)
    if not Alive(actor) then return nil, "not alive" end
    local ok, v = pcall(function() return actor:GetUniqueId() end)
    if not ok then return nil, tostring(v) end
    local id = Int(v)
    if id == nil then return nil, "returned " .. tostring(v) end
    return id
end

-- Discovery: log what the save reports under each candidate key, e.g.
-- "map 3020 / row map 2001: m_Id 3 false, m_UniqueId 17 true, TypeData.ID 17 true".
function G.ChestSaveKeys(mapId, c)
    local parts = {}
    for _, m in ipairs({ mapId, c.rowMap ~= mapId and c.rowMap or nil }) do
        local cells = {}
        for _, k in ipairs({ { "m_Id", c.uid }, { "m_UniqueId", c.uniqueId }, { "TypeData.ID", c.typeId } }) do
            if k[2] then cells[#cells + 1] = k[1] .. " " .. k[2] .. " " .. tostring(G.IsChestOpenInSave(m, k[2])) end
        end
        parts[#parts + 1] = "map " .. tostring(m) .. ": " .. table.concat(cells, ", ")
    end
    return table.concat(parts, " / ")
end

local CHEST_TABLE = "/Game/Datatable/Map/Gimmick/TreasureBox/CDT_MapGimmickTreasureBox.CDT_MapGimmickTreasureBox"
local CHEST_FIELDS = { "mapId", "ID", "ItemId", "ItemNum", "Money", "IsTrap", "battleGroupId" }

-- A composite table keeps its own copy of the rows, so a patch must reach its parent tables too
-- (parents can be composite as well). Same walk as FFRRandomizer's tableFamily.
local function TableFamily(root)
    local family, seen = {}, {}
    local function visit(dt)
        if not (dt and dt:IsValid()) then return end
        local key = dt:GetFullName()
        if seen[key] then return end
        seen[key] = true
        family[#family + 1] = dt
        pcall(function()
            local parents = dt.ParentTables
            for i = 1, #parents do visit(parents[i]) end
        end)
    end
    visit(root)
    return family
end

local function RowName(name)
    if type(name) == "string" then return name end
    local ok, s = pcall(function() return name:ToString() end)
    return ok and s or tostring(name)
end

-- Every chest row as a plain table, sorted by map and id. nil when the table is not loaded.
function G.ChestRows()
    local dt = Find(CHEST_TABLE)
    if not dt then return nil end
    local rows = {}
    pcall(function()
        dt:ForEachRow(function(name, row)
            local r = { row = RowName(name) }
            for _, f in ipairs(CHEST_FIELDS) do
                local v
                pcall(function() v = row[f] end)
                r[f] = v
            end
            rows[#rows + 1] = r
        end)
    end)
    table.sort(rows, function(a, b)
        if a.mapId ~= b.mapId then return (a.mapId or 0) < (b.mapId or 0) end
        return (a.ID or 0) < (b.ID or 0)
    end)
    return rows
end

-- Writes every chest row to a tab-separated file, for the apworld's location table.
function G.ExportChests(path)
    local rows = G.ChestRows()
    if not rows then return false, "chest table not loaded" end
    local f = io.open(path, "w")
    if not f then return false, "cannot write " .. path end
    f:write("row\t", table.concat(CHEST_FIELDS, "\t"), "\n")
    for _, r in ipairs(rows) do
        local cells = { r.row }
        for _, k in ipairs(CHEST_FIELDS) do cells[#cells + 1] = tostring(r[k]) end
        f:write(table.concat(cells, "\t"), "\n")
    end
    f:close()
    return true, #rows .. " rows"
end

-- Chest blanking: every chest that is an Archipelago location gives nothing instead of its
-- vanilla reward, because the real reward comes from the server. Round 81: an empty chest still
-- opens, is saved as taken and shows the game's pop-up ("0 gil"), which the mod writes into; until
-- then they gave 1 gil. Turning it off restores the originals, and a game restart restores them
-- anyway.
--
-- Chests holding an item at or above SHUFFLE_ID_LIMIT (visions, key items, valuables) are not
-- locations and keep their content. The apworld uses the same limit (tools/gen_apworld_data.py).
local SHUFFLE_ID_LIMIT = 13000
local MAGICITE_FIRST, MAGICITE_LAST = 25000, 25002   -- Magicite chests are shuffled locations too
--
-- Key originals by the row's own mapId and ID rather than a spawned actor's copy, so chests
-- spawned while blanking is active restore to their true vanilla contents when unblanked.
local blankOriginals = {}   -- "mapId:ID" -> { ItemId, ItemNum, Money } as the game shipped them
local BLANK = { ItemId = -1, ItemNum = 0, Money = 0 }

local function RowKey(row)
    return tostring(Int(row.mapId)) .. ":" .. tostring(Int(row.ID))
end

local function IsBlank(row)
    return row.ItemId == BLANK.ItemId and row.Money == BLANK.Money and row.ItemNum == BLANK.ItemNum
end

-- Records a row's reward the first time it is seen un-blanked.
local function Remember(row)
    local key = RowKey(row)
    if not blankOriginals[key] and not IsBlank(row) then
        blankOriginals[key] = { ItemId = row.ItemId, ItemNum = row.ItemNum, Money = row.Money }
    end
end

-- Sets one row (a table row or a chest's copy) blank or back. Returns true when it changed.
local function BlankRow(row, on)
    if row.IsTrap == true then return false end
    local itemId = Int(row.ItemId) or -1
    local shuffled = itemId < SHUFFLE_ID_LIMIT or (itemId >= MAGICITE_FIRST and itemId <= MAGICITE_LAST)
        or (G.blankRadarParts and G.RADAR_PARTS[itemId])
    if not shuffled then return false end
    if on then
        Remember(row)
        if IsBlank(row) then return false end
        row.ItemId, row.ItemNum, row.Money = BLANK.ItemId, BLANK.ItemNum, BLANK.Money
        return true
    end
    local orig = blankOriginals[RowKey(row)]
    if not orig or not IsBlank(row) then return false end
    row.ItemId, row.ItemNum, row.Money = orig.ItemId, orig.ItemNum, orig.Money
    return true
end

-- Applies (on) or undoes (off) the blanking on the chest tables and on the chests already
-- spawned, which carry their own copy of the row. Returns how many rows it changed.
-- Safe to call again and again: rows already in the wanted state are skipped.
function G.BlankChests(on)
    local changed = 0
    local family = TableFamily(Find(CHEST_TABLE))
    -- Every table first records what it holds, so a parent table rebuilt with vanilla rows
    -- still supplies the originals for a composite that is already blank.
    for _, dt in ipairs(family) do
        pcall(function() dt:ForEachRow(function(_, row) pcall(Remember, row) end) end)
    end
    for _, dt in ipairs(family) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                local ok, did = pcall(BlankRow, row, on)
                if ok and did then changed = changed + 1 end
            end)
        end)
    end
    for _, c in ipairs(G.LiveChests()) do
        if not c.open then
            local ok, did = pcall(function() return BlankRow(c.actor.m_TreasureBoxData, on) end)
            if ok and did then changed = changed + 1 end
        end
    end
    return changed
end

-- -------------------------------------------------------------------------------------------
-- Shining spots (shinies)
-- -------------------------------------------------------------------------------------------
-- The sparkly pick-ups on the world map and in fields. They are BP_MapGimmick_FieldItem* actors
-- placed in level files with m_UniqueId; looted state uses IsOpenTreasureBox(saveMapId, uniqueId)
-- and the reward lives on m_ItemId, m_ItemNum, and m_Money. Spots with neither item nor money are
-- story or quest points guarded by VisibleCondition.

local function ClassName(o)
    local ok, n = pcall(function() return o:GetClass():GetFName():ToString() end)
    return ok and n or "?"
end

-- Round 116: every field item Blueprint (FieldItem, _Child, _Medal, _08Gro_40) comes from
-- CPP_MapGimmick_FieldItem, so one search finds them all. The search for every CPP_MapGimmick that
-- this replaces read the class of each gimmick on the map, every second: a stutter on slower PCs.
G.FIELD_ITEM_CLASS = "CPP_MapGimmick_FieldItem"

function G.LiveFieldItems()
    local out = {}
    local ok, all = pcall(FindAllOf, G.FIELD_ITEM_CLASS)
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            pcall(function()
                local e = {
                    uid = Int(a.m_UniqueId),
                    hidden = a.bHidden == true,
                    interact = Int(a.interactType),
                    class = ClassName(a),
                    actor = a,
                }
                -- CPP_MapGimmick_FieldItem.m_IsOpen is the picked-up flag; reward fields live on CPP_MapGimmick_ItemObjectBase.
                pcall(function() e.open = a.m_IsOpen == true end)
                pcall(function()
                    e.itemId, e.itemNum, e.money = Int(a.m_ItemId), Int(a.m_ItemNum), Int(a.m_Money)
                end)
                pcall(function() e.visible = a.VisibleCondition:ToString() end)
                pcall(function()
                    local loc = a:K2_GetActorLocation()
                    e.x, e.y = loc.X, loc.Y
                end)
                out[#out + 1] = e
            end)
        end
    end
    return out
end

-- -------------------------------------------------------------------------------------------
-- On-screen text
-- -------------------------------------------------------------------------------------------

-- Shows text through the ModSettings panel, which is the only on-screen text route known in
-- this game (PrintString is compiled out). Toast takes (Message, Seconds, Hue, WorldContext).
-- Returns false when the panel is not installed; the caller logs the text either way.
function G.Toast(msg, seconds, hue)
    local ctx = PlayerController()
    for _, path in ipairs({
        "/Game/Mods/ModSettings/BP_ModSettings.Default__BP_ModSettings_C",
        "/Game/Mods/ModSettings/BP_ModSettings.BP_ModSettings_C",
    }) do
        local o = Find(path)
        if o and o.Toast then
            local ok = pcall(function() o:Toast(tostring(msg), seconds or 3.0, hue or 180.0, ctx) end)
            if ok then return true end
        end
    end
    return false
end

-- -------------------------------------------------------------------------------------------
-- Discovery dumps, for building the location list
-- -------------------------------------------------------------------------------------------

local function Show(v)
    if type(v) ~= "userdata" then return tostring(v) end
    local text
    if pcall(function() text = v:ToString() end) and text then return text end
    local n = Int(v)
    if n then return tostring(n) end
    local items = {}
    if pcall(function() v:ForEach(function(_, e) items[#items + 1] = tostring(e:get()) end) end) then
        return "[" .. table.concat(items, ",") .. "]"
    end
    return tostring(v)
end

-- Writes every field of a struct value, nested structs `depth` levels down, through `out`.
local function DumpStruct(struct, value, indent, depth, out)
    pcall(function()
        struct:ForEachProperty(function(prop)
            local name = prop:GetFName():ToString()
            local kind = prop:GetClass():GetFName():ToString()
            local v
            pcall(function() v = value[name] end)
            if kind == "StructProperty" and depth > 0 then
                local child
                pcall(function() child = prop:GetStruct() end)
                out(indent .. name .. " : " .. (child and child:GetFName():ToString() or "?"))
                if child then DumpStruct(child, v, indent .. "  ", depth - 1, out) end
            else
                out(indent .. kind .. " " .. name .. " = " .. Show(v))
            end
        end)
    end)
end

-- -------------------------------------------------------------------------------------------
-- Save snapshot, for finding out what a stretch of play changes (the prologue, say)
-- -------------------------------------------------------------------------------------------
-- Every field of the loaded save object, as "path<TAB>value" lines: structs are walked, arrays
-- are written element by element (0-based, like the engine), maps and sets key by key. Two
-- snapshots compare line by line with tools/snapdiff.py.

local SNAP_DEPTH = 8          -- struct levels to walk
local SNAP_ELEMENTS = 20000   -- elements written per array

local function PropKind(prop)
    local kind
    pcall(function() kind = prop:GetClass():GetFName():ToString() end)
    return kind or "?"
end

local SnapStruct

-- The game's save struct types, with the names of their own fields. Found once, on the first
-- snapshot. The names come from the game's executable (2026-11-05); FindAllOf("ScriptStruct")
-- returns nothing in game, so each one is looked up by its path.
local SAVE_STRUCT_NAMES = {
    "Artifact", "Battle", "Bounty", "Chat", "ChatData", "Chocobo", "Colosseum",
    "Colosseum_ProgressData", "Colosseum_ProgressSaveData", "Colosseum_PromotionMatchData",
    "Colosseum_RematchBattleProgress", "DLC", "Demo", "InitGameData", "InitUnitData", "Inventory",
    "InventoryProcedure", "Keyboard", "LastRideRaft", "Map", "MapGimmick", "MapGimmickState",
    "MapGimmick_Switch", "MapGimmick_SwitchSequence", "MapUnderworld", "Map_PingerPoint",
    "MiniGame", "MiniGame_Nawatobi_Data", "Mixture", "MixtureCombine", "Party", "PerMap", "Player",
    "Progress", "Quest", "QuestBoard", "Race", "Request", "RequestData", "ShopItem",
    "Sound_BGMData", "Sound_SaveData", "Timer", "TransferInventoryList", "TransferTargetInventory",
    "TransferTargetInventoryByMap", "TreasureBox", "TreasureBoxList", "UI", "UI_Field",
    "UI_MiniMap", "Unit", "UnitBtlCmdData", "UnitBtlCmdDataBundle", "UnitGuest", "UnitParameter",
    "Vision",
}
-- Other struct types that map values can hold, by full short name (such as title menu entries).
local OTHER_STRUCT_NAMES = { "TitleEntryProperty", "TitleEntryDisplay", "TitleEntryBehavior" }
local saveStructs
local function SaveStructs()
    if saveStructs then return saveStructs end
    saveStructs = {}
    local names = {}
    for _, short in ipairs(SAVE_STRUCT_NAMES) do names[#names + 1] = "SaveData_" .. short end
    for _, full in ipairs(OTHER_STRUCT_NAMES) do names[#names + 1] = full end
    for _, short in ipairs(names) do
        pcall(function()
            local s = StaticFindObject("/Script/mucha." .. short)
            if not (s and s:IsValid()) then return end
            local names = {}
            pcall(function() s:ForEachProperty(function(p) names[#names + 1] = p:GetFName():ToString() end) end)
            if #names > 0 then saveStructs[#saveStructs + 1] = { struct = s, names = names } end
        end)
    end
    return saveStructs
end

-- The struct type of a struct value from a map: the type with the most fields that all read
-- back from the value. nil when none fits (the value is then written as one line).
local function GuessStruct(value)
    local best, bestN
    for _, t in ipairs(SaveStructs()) do
        local all = true
        for _, name in ipairs(t.names) do
            local ok, x = pcall(function() return value[name] end)
            if not ok or x == nil then all = false break end
        end
        if all and (not bestN or #t.names > bestN) then best, bestN = t.struct, #t.names end
    end
    return best
end

local function SnapValue(prop, v, path, depth, out)
    local kind = PropKind(prop)
    if kind == "StructProperty" then
        local s
        pcall(function() s = prop:GetStruct() end)
        if s and v ~= nil and depth > 0 then
            SnapStruct(s, v, path, depth - 1, out)
        else
            out(path, "<struct>")
        end
    elseif kind == "ArrayProperty" then
        local inner, n = nil, 0
        pcall(function() inner = prop:GetInner() end)
        pcall(function() n = v:GetArrayNum() end)
        out(path .. ".#", n)
        if inner and n > 0 then
            pcall(function()
                v:ForEach(function(index, element)
                    local i = index - 1
                    if i >= SNAP_ELEMENTS then return end
                    local ev
                    pcall(function() ev = element:get() end)
                    SnapValue(inner, ev, path .. "[" .. i .. "]", depth, out)
                end)
            end)
        end
    elseif kind == "MapProperty" or kind == "SetProperty" then
        -- Map values can be structs. UE4SS's Lua gives no way to ask a map for its value type,
        -- so the type is matched by field names (GuessStruct), once per map.
        local n, valueStruct, guessed = 0, nil, false
        pcall(function()
            v:ForEach(function(key, value)
                n = n + 1
                local k, e
                pcall(function() k = key:get() end)
                local at = path .. "{" .. Show(k) .. "}"
                if value == nil then
                    out(at, "")
                    return
                end
                pcall(function() e = value:get() end)
                if not guessed and tostring(e):find("^UScriptStruct") then
                    guessed = true
                    valueStruct = GuessStruct(e)
                end
                if valueStruct and depth > 0 then
                    SnapStruct(valueStruct, e, at, depth - 1, out)
                else
                    out(at, Show(e))
                end
            end)
        end)
        out(path .. ".#", n)
    elseif kind == "ObjectProperty" or kind == "ClassProperty" or kind == "SoftObjectProperty"
        or kind == "WeakObjectProperty" then
        local name = "nil"
        pcall(function() if v and v:IsValid() then name = v:GetFullName() end end)
        out(path, name)
    else
        out(path, Show(v))
    end
end

SnapStruct = function(struct, value, path, depth, out)
    local s = struct
    while s do
        local current = s
        pcall(function()
            current:ForEachProperty(function(prop)
                local name = prop:GetFName():ToString()
                local v
                pcall(function() v = value[name] end)
                SnapValue(prop, v, path .. "." .. name, depth, out)
            end)
        end)
        local super
        pcall(function() super = current:GetSuperStruct() end)
        local superName
        pcall(function() superName = super and super:IsValid() and super:GetFName():ToString() end)
        if superName and superName ~= "Object" then s = super else s = nil end
    end
end

-- Writes the snapshot through out(path, value). Returns false when no save is loaded.
function G.Snapshot(out)
    local sd = G.SaveData()
    if not sd then return false end
    out("live.time", os.date("%Y-%m-%d %H:%M:%S"))
    out("live.map", tostring(G.CurrentMap()))
    out("live.story", tostring(G.StoryCounter()))
    pcall(function()
        local loc = PlayerController():K2_GetPawn():K2_GetActorLocation()
        out("live.pawn", string.format("%.1f %.1f %.1f", loc.X, loc.Y, loc.Z))
    end)
    out("live.object", tostring(G.SaveObjectName()))
    out("live.slot", tostring(G.SlotForTicks(G.SavedTicks())))
    out("live.saveStructs", #SaveStructs())   -- types that map values are matched against
    local cls
    pcall(function() cls = sd:GetClass() end)
    if cls then SnapStruct(cls, sd, "save", SNAP_DEPTH, out) end
    return true
end

-- The functions of a /Script/mucha class, as "Class.Function(param: Kind, ...)" lines through
-- out(line). Struct parameters name their struct. Returns the number of functions, or nil when
-- the class is not found.
local function FunctionLines(cls, label, out)
    local n = 0
    pcall(function()
        cls:ForEachFunction(function(fn)
            n = n + 1
            local params = {}
            pcall(function()
                fn:ForEachProperty(function(p)
                    local kind = PropKind(p)
                    if kind == "StructProperty" then
                        pcall(function() kind = kind .. "<" .. p:GetStruct():GetFName():ToString() .. ">" end)
                    end
                    params[#params + 1] = p:GetFName():ToString() .. ": " .. kind
                end)
            end)
            local name = "?"
            pcall(function() name = fn:GetFName():ToString() end)
            out(label .. "." .. name .. "(" .. table.concat(params, ", ") .. ")")
        end)
    end)
    return n
end

-- Returns hookable native RegisterHook paths for a /Script/mucha class (used by ffrap_bossfight watch),
-- skipping frequent getters/checks, delegates, and non-native functions (FUNC_Native = 0x400).
-- Returns paths and whether flags were readable, or nil if the class is not found.
local SKIP_PREFIX = { "Get", "Is", "Can", "Has", "Find", "K2_", "Exec" }
function G.FunctionPaths(className)
    local cls = StaticFindObject("/Script/mucha." .. className)
    if not (cls and cls:IsValid()) then return nil end
    local paths, flagsRead = {}, true
    pcall(function()
        cls:ForEachFunction(function(fn)
            local name
            pcall(function() name = fn:GetFName():ToString() end)
            if not name or name:find("__DelegateSignature", 1, true) then return end
            for _, prefix in ipairs(SKIP_PREFIX) do
                if name:sub(1, #prefix) == prefix and name ~= "Execute_EncountStart" then return end
            end
            local okFlags, flags = pcall(function() return fn:GetFunctionFlags() end)
            if okFlags and type(flags) == "number" then
                if math.floor(flags / 0x400) % 2 ~= 1 then return end
            else
                flagsRead = false
            end
            paths[#paths + 1] = "/Script/mucha." .. className .. ":" .. name
        end)
    end)
    return paths, flagsRead
end

function G.ListFunctions(className, out)
    local cls = StaticFindObject("/Script/mucha." .. className)
    if not (cls and cls:IsValid()) then return nil end
    return FunctionLines(cls, className, out)
end

-- An object to look at: a path ("/Game/UI/..."), else the first live instance of a class
-- name, else that class's default object in /Script/mucha.
local function InspectTarget(target)
    if target:find("/", 1, true) then return Find(target) end
    local ok, obj = pcall(FindFirstOf, target)
    if ok and obj and Alive(obj) then return obj end
    return Find("/Script/mucha.Default__" .. target)
end

-- Every field and function of one object, as "path<TAB>value" lines through out(key, value):
-- what a screen's view model or data asset holds and can be asked to do. Object fields are
-- written by name, not walked. Returns false when nothing matches the target.
function G.Inspect(target, out)
    local obj = InspectTarget(target)
    if not obj then return false end
    local cls
    pcall(function() cls = obj:GetClass() end)
    out("object", obj:GetFullName())
    local chain, c = {}, cls
    while c do
        local name
        pcall(function() name = c:IsValid() and c:GetFName():ToString() end)
        if not name or name == "Object" then break end
        chain[#chain + 1] = name
        local super
        pcall(function() super = c:GetSuperStruct() end)
        c = super
    end
    out("class", table.concat(chain, " < "))
    c = cls
    for _, name in ipairs(chain) do
        FunctionLines(c, name, function(line) out("function", line) end)
        local super
        pcall(function() super = c:GetSuperStruct() end)
        c = super
    end
    if cls then SnapStruct(cls, obj, "obj", 4, out) end
    return true
end

-- Search native classes/structs plus Blueprint-generated classes under /Game.
local TYPE_KINDS = { Class = true, ScriptStruct = true, BlueprintGeneratedClass = true,
                     WidgetBlueprintGeneratedClass = true, AnimBlueprintGeneratedClass = true }

-- Walk every game class/struct (/Script/mucha or Blueprint under /Game) matching `text` on its
-- name, functions, or fields, emitting lines via out(line). Skips objects being destroyed to avoid
-- GC/loading crashes. Returns the match count.
function G.FindNames(text, out)
    local want, n = text:lower(), 0
    local function match(kind, owner, name)
        if name:lower():find(want, 1, true) then
            n = n + 1
            out(kind .. "\t" .. owner .. (name ~= owner and ("." .. name) or ""))
        end
    end
    pcall(function()
        ForEachUObject(function(obj)
            if not Alive(obj) then return end
            local kind
            pcall(function() kind = obj:GetClass():GetFName():ToString() end)
            if not TYPE_KINDS[kind] then return end
            local full
            pcall(function() full = obj:GetFullName() end)
            if not (full and (full:find(" /Script/mucha.", 1, true) or full:find(" /Game/", 1, true))) then return end
            local owner = obj:GetFName():ToString()
            match(kind == "ScriptStruct" and "struct" or "class", owner, owner)
            pcall(function() obj:ForEachFunction(function(fn) match("function", owner, fn:GetFName():ToString()) end) end)
            pcall(function() obj:ForEachProperty(function(p) match("field", owner, p:GetFName():ToString()) end) end)
        end)
    end)
    return n
end

-- -------------------------------------------------------------------------------------------
-- Title menu
-- -------------------------------------------------------------------------------------------
-- Title menu entries use ETitleFunctionType (Continue 0, LoadGame 1, NewGame 2, Option 3,
-- QuitGame 4, Max 5), stored in DA_Title.EntryPropertyMap. Choosing one calls
-- CPP_VM_Title:ExecuteEntry(type). The Archipelago entry uses type 5 as a copy of New Game;
-- the ExecuteEntry hook in main.lua turns it back into New Game.

G.TITLE_LOAD_GAME = 1
G.TITLE_NEW_GAME = 2
G.TITLE_ARCHIPELAGO = 5
local TITLE_DA = "/Game/UI/Title/Data/DA_Title.DA_Title"

-- The entry types the title menu shows, from its view model, and the keys of the data asset's
-- entry map, as text for the log.
function G.TitleEntries()
    local shown, keys = {}, {}
    pcall(function()
        local vm = Live("CPP_VM_Title")
        local list = vm and vm:GetDisplayEntryList()
        if list then for i = 1, #list do shown[#shown + 1] = tostring(Int(list[i]) or list[i]) end end
    end)
    pcall(function()
        local da = Find(TITLE_DA)
        if da then da.EntryPropertyMap:ForEach(function(k) keys[#keys + 1] = tostring(Int(k:get())) end) end
    end)
    return "shown [" .. table.concat(shown, ",") .. "], map keys [" .. table.concat(keys, ",") .. "]"
end

G.TITLE_LABEL = "New Game (Archipelago)"
-- Round 116: the label while no client is connected. The menu reads its rows when it is made,
-- so a change shows the next time the title menu comes up.
G.TITLE_LABEL_NO_CLIENT = "New Game (Archipelago: connect the client)"
G.TITLE_LABEL_LIVE = G.TITLE_LABEL
-- The menu lists the rows in the map's own order, so the Archipelago row goes under New Game
-- by rebuilding the map in this order (OrderTitleEntries).
local TITLE_ORDER = { 0, 1, 2, 5, 3, 4 }
local TITLE_TEXT_MISSING = "MISSING STRING TABLE ENTRY"

-- The title data asset, loaded when asked to and not loaded yet (as FFRSLib loads the System Menu
-- one: the menu reads its asset when it is made, so a row added later shows only next time).
local function TitleAsset(load)
    local da = Find(TITLE_DA)
    if da or not load then return da end
    pcall(function()
        local ksl = Find("/Script/Engine.Default__KismetSystemLibrary")
        ksl:LoadAsset_Blocking(ksl:Conv_SoftObjPathToSoftObjRef(ksl:MakeSoftObjectPath(TITLE_DA)))
    end)
    da = Find(TITLE_DA)
    if not da and LoadAsset then
        pcall(function() LoadAsset(TITLE_DA) end)
        da = Find(TITLE_DA)
    end
    return da
end

-- Adds the Archipelago row to the title data asset as a copy of the New Game row, labelled
-- "Archipelago". Returns ok and a detail ("already there" when it is). With load set, loads the
-- asset first. Tries passing the New Game row's struct as the value first, then an empty table.
function G.AddTitleEntry(load)
    local da = TitleAsset(load)
    if not da then return false, "DA_Title is not loaded (go to the title screen)" end
    local map = da.EntryPropertyMap
    local have, newGame = false, nil
    map:ForEach(function(k, v)
        local key = Int(k:get())
        if key == G.TITLE_ARCHIPELAGO then have = true end
        if key == G.TITLE_NEW_GAME then newGame = v:get() end
    end)
    local function label()
        -- An FText in a Lua table is dropped, so the name is set on the stored row (FFRSLib does
        -- the same for its System Menu entry).
        local okLabel = false
        map:ForEach(function(k, v)
            if Int(k:get()) == G.TITLE_ARCHIPELAGO then
                okLabel = pcall(function() v:get().EntryName = FText(G.TITLE_LABEL) end)
            end
        end)
        return okLabel
    end
    if have then
        label()
        return true, "already there"
    end
    if not newGame then return false, "no New Game row to copy" end
    local how
    if pcall(function() map:Add(G.TITLE_ARCHIPELAGO, newGame) end) then
        how = "copied from the New Game row"
    elseif pcall(function() map:Add(G.TITLE_ARCHIPELAGO, {}) end) then
        how = "added empty (the copy was refused)"
    else
        return false, "EntryPropertyMap:Add refused both ways"
    end
    local now = false
    map:ForEach(function(k) if Int(k:get()) == G.TITLE_ARCHIPELAGO then now = true end end)
    if now and not label() then how = how .. " (the label could not be set)" end
    return now, how .. (now and "" or ", but the row is not in the map afterwards")
end

-- Returns one title row's TitleEntryProperty fields as plain Lua values; the label resolves in
-- the current UI language.
local function ReadTitleRow(v)
    local list = v.DisplayProperty.DisplayPlatformMap
    local platforms = {}
    for i = 1, #list do platforms[i] = Int(list[i]) end
    return {
        name = v.EntryName:ToString(),
        checkSave = v.DisplayProperty.bCheckSaveData == true,
        checkPlatform = v.DisplayProperty.bCheckPlatform == true,
        platforms = platforms,
        action = v.SystemActionTag.TagName:ToString(),
    }
end

-- Puts the Archipelago row under New Game. The menu shows the rows in the map's order, and a
-- map keeps the order rows were added in only when it starts empty, so: read every row, empty
-- the map, add the rows back in TITLE_ORDER, and fill in each row's fields. Before emptying
-- anything it checks that the map takes an empty row, so a refusal leaves the menu as it was.
-- Returns ok and a detail.
function G.OrderTitleEntries()
    local da = Find(TITLE_DA)
    if not da then return false, "DA_Title is not loaded" end
    local map = da.EntryPropertyMap
    local keys, rows = {}, {}
    local okRead, err = pcall(function()
        map:ForEach(function(k, v)
            local key = Int(k:get())
            keys[#keys + 1] = key
            rows[key] = ReadTitleRow(v:get())
        end)
    end)
    if not okRead then return false, "could not read the rows: " .. tostring(err) end
    if table.concat(keys, ",") == table.concat(TITLE_ORDER, ",") then return true, "already in order" end
    for _, k in ipairs(TITLE_ORDER) do
        if not rows[k] then return false, "row " .. k .. " is missing, so the order is left alone" end
        -- While string tables are still loading, FText reads "<MISSING STRING TABLE ENTRY>". Defer
        -- rebuilding instead of baking the placeholder text into plain strings.
        if k ~= G.TITLE_ARCHIPELAGO and (rows[k].name == "" or rows[k].name:find(TITLE_TEXT_MISSING, 1, true)) then
            return false, "row " .. k .. " has no text yet (string table not loaded), so the order waits"
        end
    end
    rows[G.TITLE_ARCHIPELAGO].name = G.TITLE_LABEL
    -- A spare key proves an empty row is accepted; emptying the map removes it again.
    if not pcall(function() map:Add(#TITLE_ORDER, {}) end) then
        return false, "the map refused an empty row, so the order is left alone"
    end
    if not pcall(function() map:Empty() end) then
        pcall(function() map:Remove(#TITLE_ORDER) end)   -- take the spare row out again
        return false, "the map could not be emptied, so the order is left alone"
    end
    local bad = {}
    for _, k in ipairs(TITLE_ORDER) do
        if not pcall(function() map:Add(k, {}) end) then bad[#bad + 1] = k .. " (add)" end
    end
    map:ForEach(function(k, v)
        local key = Int(k:get())
        local r = rows[key]
        if not r then return end
        local okFill = pcall(function()
            local row = v:get()
            row.EntryName = FText(r.name)
            row.DisplayProperty.bCheckSaveData = r.checkSave
            row.DisplayProperty.bCheckPlatform = r.checkPlatform
            row.SystemActionTag.TagName = FName(r.action)
            local list = row.DisplayProperty.DisplayPlatformMap
            for i, p in ipairs(r.platforms) do
                if #list < i then local _ = list[i] end   -- reading one past the end grows it
                list[i] = p
            end
        end)
        if not okFill then bad[#bad + 1] = key .. " (fields)" end
    end)
    local now = {}
    map:ForEach(function(k) now[#now + 1] = tostring(Int(k:get())) end)
    if #bad > 0 then return false, "rebuilt as [" .. table.concat(now, ",") .. "] with problems: " .. table.concat(bad, ", ") end
    return true, "rebuilt as [" .. table.concat(now, ",") .. "]"
end

-- Round 120 (round 117's finding): the menu draws its rows' labels when it is made, so the entry
-- kept "connect the client" after the client connected, until a quit to the title. Rewrites any
-- text on screen that reads one of the Archipelago labels but not `label`. Returns how many.
function G.RefreshTitleLabel(label)
    local stale = { [G.TITLE_LABEL_LIVE] = true, [G.TITLE_LABEL_NO_CLIENT] = true }
    stale[label] = nil
    local changed = 0
    for _, class in ipairs({ "TextBlock", "RichTextBlock" }) do
        local ok, all = pcall(FindAllOf, class)
        for _, tb in ipairs(ok and all or {}) do
            local text
            if Alive(tb) then pcall(function() text = tb:GetText():ToString() end) end
            if text and stale[text] and pcall(function() tb:SetText(FText(label)) end) then changed = changed + 1 end
        end
    end
    return changed
end

-- Writes `line` above the game's version text in the title screen's corner ("1.0.1.0", above
-- copyright lines). Sets left justification (ETextJustify Left = 0) so the wider mod line does
-- not push the version off-screen right. Rechecked periodically because the title widget rebuilds
-- on each return to the title screen. Returns "added", "already", or nil, and the TextBlock.
local JUSTIFY_LEFT = 0
function G.TitleVersionLine(line)
    local ok, all = pcall(FindAllOf, "TextBlock")
    if not ok or not all then return nil end
    for _, tb in ipairs(all) do
        if Alive(tb) then
            local text
            pcall(function() text = tb:GetText():ToString() end)
            if text then
                if text:find(line, 1, true) then
                    pcall(function() tb:SetJustification(JUSTIFY_LEFT) end)
                    return "already", tb
                end
                if text:match("^%d+%.%d+%.%d+%.%d+") then
                    if pcall(function() tb:SetText(FText(line .. "\n" .. text)) end) then
                        pcall(function() tb:SetJustification(JUSTIFY_LEFT) end)
                        return "added", tb
                    end
                end
            end
        end
    end
    return nil
end

-- A widget's place in its layout, for the log: its class, its slot's class, its parent panel
-- and the parent's children. This is what placing the logo next to the version text needs.
function G.DescribeWidget(w)
    local function cls(o)
        local n
        pcall(function() n = o:GetClass():GetFName():ToString() end)
        return n or "?"
    end
    local function name(o)
        local n
        pcall(function() n = o:GetFName():ToString() end)
        return n or "?"
    end
    local parts = { "widget " .. cls(w) .. " " .. name(w) }
    local slot
    pcall(function() slot = w.Slot end)
    if slot and Alive(slot) then parts[#parts + 1] = "slot " .. cls(slot) end
    local parent
    pcall(function() parent = w:GetParent() end)
    if parent and Alive(parent) then
        parts[#parts + 1] = "parent " .. cls(parent) .. " " .. name(parent)
        local n, kids = 0, {}
        pcall(function() n = parent:GetChildrenCount() end)
        for i = 0, n - 1 do
            pcall(function()
                local c = parent:GetChildAt(i)
                kids[#kids + 1] = cls(c) .. " " .. name(c)
            end)
        end
        parts[#parts + 1] = "children [" .. table.concat(kids, ", ") .. "]"
        local grand
        pcall(function() grand = parent:GetParent() end)
        if grand and Alive(grand) then parts[#parts + 1] = "grandparent " .. cls(grand) .. " " .. name(grand) end
    end
    local owner
    pcall(function() owner = w:GetOuter():GetOuter() end)   -- the widget tree, then its widget
    if owner and Alive(owner) then parts[#parts + 1] = "in " .. cls(owner) end
    return table.concat(parts, "; ")
end

-- Places the Archipelago logo in WBP_TitleLayout's Overlay_UI beside the mod version line
-- ("FFRArchipelago <version>"), loading the PNG at runtime and sharing the text's alignment.
local LOGO_PREFIX = "FFRAP_Logo"
local LOGO_ASPECT = 280 / 291   -- the PNG's width over its height
local LOGO_SCALE = 1.15         -- the logo's height, in text lines
local LOGO_GAP = 8              -- between the text and the logo
local logoCount = 0

local function VersionBlock(line)
    local ok, all = pcall(FindAllOf, "TextBlock")
    if not ok or not all then return nil end
    for _, tb in ipairs(all) do
        if Alive(tb) then
            local text
            pcall(function() text = tb:GetText():ToString() end)
            if text and text:find(line, 1, true) then return tb end
        end
    end
    return nil
end

-- Returns "added" or "already" and a detail, or nil and why not.
function G.TitleLogo(path, line)
    local tb = VersionBlock(line)
    if not tb then return nil, "the mod's version line is not on screen" end
    local parent
    pcall(function() parent = tb:GetParent() end)
    if not (parent and Alive(parent)) then return nil, "the version text has no parent panel" end
    local n = 0
    pcall(function() n = parent:GetChildrenCount() end)
    for i = 0, n - 1 do
        local name
        pcall(function() name = parent:GetChildAt(i):GetFName():ToString() end)
        if name and name:find(LOGO_PREFIX, 1, true) == 1 then return "already", name end
    end
    local krl = Find("/Script/Engine.Default__KismetRenderingLibrary")
    if not krl then return nil, "KismetRenderingLibrary not found" end
    local tex
    local okTex, errTex = pcall(function() tex = krl:ImportFileAsTexture2D(PlayerController() or tb, path) end)
    if not (okTex and tex and tex:IsValid()) then
        return nil, "could not load " .. path .. (okTex and "" or (": " .. tostring(errTex)))
    end
    local imageClass = Find("/Script/UMG.Image")
    local tree
    pcall(function() tree = tb:GetOuter() end)
    if not (imageClass and tree) then return nil, "no Image class or widget tree" end
    -- A fresh name each time: constructing over an existing object's name is not safe.
    logoCount = logoCount + 1
    local img
    local okNew, errNew = pcall(function()
        img = StaticConstructObject(imageClass, tree, FName(LOGO_PREFIX .. "_" .. logoCount))
    end)
    if not (okNew and img and img:IsValid()) then return nil, "could not make the Image: " .. tostring(errNew) end
    -- The text block's size and line count give the first line's place and height.
    local width, height = 0, 0
    pcall(function()
        local size = tb:GetDesiredSize()
        width, height = size.X, size.Y
    end)
    local text = ""
    pcall(function() text = tb:GetText():ToString() end)
    local lines = select(2, text:gsub("\n", "\n")) + 1
    if not height or height <= 0 then height = 21.6 * lines end
    local lineHeight = height / lines
    local logoH = math.floor(lineHeight * LOGO_SCALE + 0.5)
    local logoW = math.floor(logoH * LOGO_ASPECT + 0.5)
    pcall(function() img:SetBrushFromTexture(tex, false) end)
    pcall(function() img:SetDesiredSizeOverride({ X = logoW, Y = logoH }) end)
    local slot
    local okAdd, errAdd = pcall(function() slot = parent:AddChildToOverlay(img) end)
    if not (okAdd and slot) then return nil, "AddChildToOverlay failed: " .. tostring(errAdd) end
    -- Same alignment as the version text (left, bottom); moved right past the text, and up to
    -- the first line, centred on it.
    local h, v, pad = "?", "?", nil
    pcall(function() h = tb.Slot.HorizontalAlignment end)
    pcall(function() v = tb.Slot.VerticalAlignment end)
    pcall(function() pad = tb.Slot.Padding end)
    pcall(function() slot:SetHorizontalAlignment(h) end)
    pcall(function() slot:SetVerticalAlignment(v) end)
    local left, top, right, bottom = 0, 0, 0, 0
    pcall(function() left, top, right, bottom = pad.Left, pad.Top, pad.Right, pad.Bottom end)
    local logoLeft = left + width + LOGO_GAP
    local logoBottom = bottom + (height - lineHeight) + (lineHeight - logoH) / 2
    local okPad = pcall(function()
        slot:SetPadding({ Left = logoLeft, Top = top, Right = 0, Bottom = logoBottom })
    end)
    return "added", string.format("%dx%d at left %.1f, bottom %.1f (text %.1fx%.1f, %d lines; alignment %s/%s)%s",
        logoW, logoH, logoLeft, logoBottom, width, height, lines, tostring(h), tostring(v),
        okPad and "" or ", padding not set")
end

-- Logs the panel hierarchy holding the first visible text widget matching `text` (searches both
-- TextBlock and RichTextBlock for icon-bearing prompts).
local TEXT_CLASSES = { "TextBlock", "RichTextBlock" }
function G.LayoutOf(text)
    local tb
    for _, cls in ipairs(TEXT_CLASSES) do
        local ok, all = pcall(FindAllOf, cls)
        if ok and all then
            for _, b in ipairs(all) do
                if Alive(b) then
                    local t
                    pcall(function() t = b:GetText():ToString() end)
                    if t and t:find(text, 1, true) then tb = b break end
                end
            end
        end
        if tb then break end
    end
    if not tb then return nil end
    local chain, w = {}, tb
    for _ = 1, 12 do
        chain[#chain + 1] = G.DescribeWidget(w)
        local parent
        pcall(function() parent = w:GetParent() end)
        if not (parent and Alive(parent)) then
            -- The top of a widget tree: go on from the widget that owns the tree.
            local owner
            pcall(function() owner = w:GetOuter():GetOuter() end)
            if not (owner and Alive(owner)) then break end
            parent = owner
        end
        w = parent
    end
    return chain
end

-- -------------------------------------------------------------------------------------------
-- The item feed
-- -------------------------------------------------------------------------------------------
-- Displays recent sent/received items at the bottom right of the field HUD inside
-- WBP_FieldLayout_C's Overlay_66 (VerticalBox of TextBlocks). Rebuilt whenever the HUD overlay
-- is recreated on map loads.

local FEED_PREFIX = "FFRAP_Feed"
G.FEED_MAX = 5          -- lines on screen at once
G.FEED_SHOW = 10.0      -- seconds a line stays fully visible
G.FEED_FADE = 2.0       -- seconds it then takes to fade out
local FEED_LINE_GAP = { Left = 0, Top = 0, Right = 0, Bottom = 6 }   -- space under each line
-- 140 px up clears the bottom-right "Back" prompt shown in menus and chest pop-ups.
local FEED_PADDING = { Left = 0, Top = 0, Right = 48, Bottom = 140 }
local FEED_FONT_SIZE = 20
-- EHorizontalAlignment and EVerticalAlignment: Fill 0, Left/Top 1, Center 2, Right/Bottom 3.
-- ETextJustify: Left 0, Center 1, Right 2.
local ALIGN_RIGHT, ALIGN_BOTTOM, JUSTIFY_RIGHT = 3, 3, 2
local feed = { box = nil, host = nil, tree = nil, lines = {}, made = 0 }

-- Round 89 (the user): item names in Archipelago's colours, by the item's flags (1 progression,
-- 2 useful, 4 trap). The text client's plum, slateblue, salmon and cyan, as linear colours (UMG's).
G.ITEM_COLORS = {
    progression = { R = 0.429, G = 0.319, B = 0.863 },   -- #AF99EF
    useful = { R = 0.153, G = 0.258, B = 0.807 },        -- #6D8BE8
    trap = { R = 0.956, G = 0.216, B = 0.168 },          -- #FA8072
    filler = { R = 0.0, G = 0.855, B = 0.855 },          -- #00EEEE
}
function G.ItemClass(flags)
    flags = flags or 0
    if flags % 2 == 1 then return "progression" end
    if math.floor(flags / 2) % 2 == 1 then return "useful" end
    if math.floor(flags / 4) % 2 == 1 then return "trap" end
    return "filler"
end
-- Feed lines with the item's name in its colour and in bold. Round 90's probe worked; on since
-- round 91 (ffrap_feed colors off).
G.feedColors = true

-- When G.feedTrace is set (via `ffrap_feed test`), risky UMG calls log first so crashes pinpoint the call.
G.feedTrace = nil
local function step(what)
    if G.feedTrace then G.feedTrace(what) end
end

-- True when a widget is on screen: UWidget.IsVisible is true only for a widget that has a live
-- Slate widget that is visible.
local function Shown(w)
    local ok, v = pcall(function() return w:IsVisible() end)
    return ok and v == true
end

-- Returns the first visible instance of a widget class, filtering out Blueprint template copies.
local function ShownInstance(className)
    local ok, all = pcall(FindAllOf, className)
    if not ok or not all then return nil end
    for _, w in ipairs(all) do
        if Alive(w) and Shown(w) then return w end
    end
    return nil
end

-- The field HUD's overlay and the widget tree to make widgets in, or nil when no field HUD is
-- on screen (off the field, loading, a battle, a menu that hides the HUD).
local function FeedHost()
    local list = ShownInstance("WBP_FieldFuncList2_C")
    if not list then return nil end
    local host, tree
    pcall(function() host = list:GetParent() end)
    pcall(function() tree = list:GetOuter() end)
    if host and Alive(host) and Shown(host) and tree then return host, tree end
    return nil
end

-- True while the field HUD is on screen: not in a battle, a menu, an event or loading.
-- Round 120: a tick asked this five times or so, each a FindAllOf of the field HUD (about 2 ms a
-- tick on the laptop). Inside one loop run (G.BeginRun to G.EndRun, one game frame) the answer is
-- kept; a hook outside the loops asks again each time.
function G.OnField()
    local run = G.run
    if not run then return FeedHost() ~= nil end
    if run.onField == nil then run.onField = FeedHost() ~= nil end
    return run.onField
end
function G.BeginRun() G.run = {} end
function G.EndRun() G.run = nil end

-- Blanks a shiny actor that is an AP location to nothing (matching blanked chests), using the same
-- shuffle limits (`shinies`) and Tablet Shards (`shards`) filter as the apworld. Returns true if modified.
local TABLET_SHARD = 25004
G.SHUFFLED_KEY_ITEMS = { [20009] = true, [20010] = true, [20011] = true }   -- the Research Center's lab key cards
function G.BlankFieldItem(e, shinies, shards)
    if e.open or not e.actor then return false end
    local id, money = e.itemId or -1, e.money or -1
    if id == BLANK.ItemId and money == BLANK.Money then return false end
    local isShard = id == TABLET_SHARD
    -- Round 74: shinies holding Magicite are locations, as Magicite chests are since round 45.
    -- Round 97: the lab key cards' spots are locations too (SHUFFLED_KEY_ITEMS in the generator).
    local isLocation = (id >= 0 and id < SHUFFLE_ID_LIMIT) or (id < 0 and money > 0) or G.SHUFFLED_KEY_ITEMS[id]
        or (id >= MAGICITE_FIRST and id <= MAGICITE_LAST)
    if not ((shards and isShard) or (shinies and isLocation)) then return false end
    return (pcall(function()
        e.actor.m_ItemId, e.actor.m_ItemNum, e.actor.m_Money = BLANK.ItemId, BLANK.ItemNum, BLANK.Money
    end))
end

local function FeedName()
    feed.made = feed.made + 1
    return FName(FEED_PREFIX .. "_" .. feed.made)
end

-- The feed's box in the current HUD, made when needed. Returns the box or nil and why not.
local function FeedBox()
    local host, tree = FeedHost()
    if not host then return nil, "no field HUD on screen" end
    local hostName
    pcall(function() hostName = host:GetFullName() end)
    local kept = feed.box and Find(feed.box)
    if kept and Alive(kept) and feed.host == hostName then return kept end
    local cls = Find("/Script/UMG.VerticalBox")
    if not cls then return nil, "no VerticalBox class" end
    local box
    step("make the box (StaticConstructObject VerticalBox)")
    local okNew, err = pcall(function() box = StaticConstructObject(cls, tree, FeedName()) end)
    if not (okNew and box and box:IsValid()) then return nil, "could not make the box: " .. tostring(err) end
    local slot
    step("add the box to the HUD (AddChildToOverlay)")
    local okAdd, errAdd = pcall(function() slot = host:AddChildToOverlay(box) end)
    if not (okAdd and slot) then return nil, "AddChildToOverlay failed: " .. tostring(errAdd) end
    step("place the box (alignment, padding)")
    pcall(function() slot:SetHorizontalAlignment(ALIGN_RIGHT) end)
    pcall(function() slot:SetVerticalAlignment(ALIGN_BOTTOM) end)
    pcall(function() slot:SetPadding(FEED_PADDING) end)
    feed.box, feed.host, feed.tree, feed.lines = G.PathOf(box), hostName, tree, {}
    return box
end

-- Style a line of text like the HUD's key guide (Text_Name), with a dark shadow. Write primitive
-- fields directly onto the TextBlock's Font and ShadowColorOffset/Color instead of calling
-- SetFont(FSlateFontInfo) or passing FSlateColor structs, which crash UE4SS Lua (round 20).
-- `look`: size (FEED_FONT_SIZE), justify (right), spacing (letter spacing), shadow (opacity, 0.85),
-- offset ({ X, Y }, the shadow's), bold (the font's Bold typeface), color ({ R, G, B }).
local function StyleLine(tb, look)
    -- Key guide uses a CommonTextBlock whose style may supply the font while Font.FontObject is
    -- nil; copying an empty FontObject renders invisible text, so only copy when present.
    local fontObject, typeface
    pcall(function()
        local guide = ShownInstance("WBP_KeyGuide_C")
        if guide then
            local f = guide.Text_Name.Font
            if f.FontObject and f.FontObject:IsValid() then
                fontObject, typeface = f.FontObject, f.TypefaceFontName
            end
        end
    end)
    local fontName = "none, the default font is kept"
    pcall(function() if fontObject then fontName = fontObject:GetFullName() end end)
    step("style: font object and typeface (field writes): " .. fontName)
    if fontObject then
        pcall(function() tb.Font.FontObject = fontObject end)
        pcall(function() tb.Font.TypefaceFontName = typeface end)
    end
    if look.bold and fontObject then
        -- Round 90, the user: the colours alone can be hard to read at a glance. SystemText has
        -- Default, Bold and Italic typefaces.
        step("style: bold typeface (field write)")
        pcall(function() tb.Font.TypefaceFontName = FName("Bold") end)
    end
    step("style: font size (field write)")
    pcall(function() tb.Font.Size = look.size or FEED_FONT_SIZE end)
    if look.spacing then pcall(function() tb.Font.LetterSpacing = look.spacing end) end
    step("style: shadow colour (field writes)")
    pcall(function()
        local c = tb.ShadowColorAndOpacity
        c.R, c.G, c.B, c.A = 0, 0, 0, look.shadow or 0.85
    end)
    if look.offset then pcall(function() tb.ShadowOffset.X, tb.ShadowOffset.Y = look.offset.X, look.offset.Y end) end
    step("style: justification (field write)")
    pcall(function() tb.Justification = look.justify or JUSTIFY_RIGHT end)
    if look.color then
        step("colour (field writes)")
        pcall(function()
            local c = tb.ColorAndOpacity.SpecifiedColor
            c.R, c.G, c.B, c.A = look.color.R, look.color.G, look.color.B, 1
        end)
    end
end

-- A TextBlock holding `text`, made in `tree` (a widget tree, so it lives as long as its screen),
-- styled by `look` before it goes on screen; look.plain leaves the styling out. Nil and why not.
function feed.text(text, look, tree)
    local cls = Find("/Script/UMG.TextBlock")
    if not cls then return nil, "no TextBlock class" end
    local tb
    step("make a line (StaticConstructObject TextBlock)")
    local okNew, err = pcall(function() tb = StaticConstructObject(cls, tree, FeedName()) end)
    if not (okNew and tb and tb:IsValid()) then return nil, "could not make a line: " .. tostring(err) end
    step("set the line's text")
    pcall(function() tb:SetText(FText(text)) end)
    if not look.plain then StyleLine(tb, look) end
    return tb
end

-- A HorizontalBox of `text` before `span` ({ text, flags }), the span in its item colour and in
-- bold, and the text after. Nil when the span is not in the text.
function feed.row(text, span, look, tree)
    if not (span and span.text and span.text ~= "") then return nil end
    local from, to = text:find(span.text, 1, true)
    if not from then return nil end
    local cls = Find("/Script/UMG.HorizontalBox")
    if not cls then return nil end
    local row
    step("make a coloured line (StaticConstructObject HorizontalBox)")
    if not pcall(function() row = StaticConstructObject(cls, tree, FeedName()) end) or not row then return nil end
    local name = {}
    for k, v in pairs(look) do name[k] = v end
    name.color, name.bold = G.ITEM_COLORS[G.ItemClass(span.flags)], true
    for _, part in ipairs({ { text:sub(1, from - 1), look }, { span.text, name }, { text:sub(to + 1), look } }) do
        if part[1] ~= "" then
            local tb = feed.text(part[1], part[2], tree)
            step("add a piece to the line (AddChildToHorizontalBox)")
            if not (tb and pcall(function() row:AddChildToHorizontalBox(tb) end)) then return nil end
        end
    end
    return row
end

-- Adds a line to the feed; `now` is the caller's clock in seconds. opts.plain leaves out the
-- styling (font, colour, shadow, justification); opts.span colours the item's name. Returns true,
-- or false and why not (off the field, say), so the caller can show the text another way.
function G.FeedLine(text, now, opts)
    local box, why = FeedBox()
    if not box then return false, why end
    local look = { plain = opts and opts.plain }
    local tb = G.feedColors and opts and feed.row(text, opts.span, look, feed.tree)
    if not tb then
        tb, why = feed.text(text, look, feed.tree)
        if not tb then return false, why end
    end
    local slot
    step("add the line to the box (AddChildToVerticalBox)")
    local okAdd, errAdd = pcall(function() slot = box:AddChildToVerticalBox(tb) end)
    if not (okAdd and slot) then return false, "AddChildToVerticalBox failed: " .. tostring(errAdd) end
    step("align the line")
    pcall(function() slot:SetHorizontalAlignment(ALIGN_RIGHT) end)
    pcall(function() slot:SetPadding(FEED_LINE_GAP) end)
    step("line done")
    feed.lines[#feed.lines + 1] = { path = G.PathOf(tb), born = now }
    while #feed.lines > G.FEED_MAX do
        local old = Find(feed.lines[1].path)
        if old then pcall(function() old:RemoveFromParent() end) end
        table.remove(feed.lines, 1)
    end
    return true
end

-- Diagnostic dump of the feed box and each line's size, visibility, and font for ffrap_feed check.
function G.FeedReport()
    local out = {}
    local function size(w)
        local s = "?"
        pcall(function() local d = w:GetDesiredSize(); s = string.format("%.0fx%.0f", d.X, d.Y) end)
        return s
    end
    local function vis(w)
        local v, shown = "?", "?"
        pcall(function() v = tostring(w:GetVisibility()) end)
        pcall(function() shown = tostring(w:IsVisible()) end)
        return "visibility " .. v .. ", visible " .. shown
    end
    local lists, shownLists = 0, 0
    pcall(function()
        for _, w in ipairs(FindAllOf("WBP_FieldFuncList2_C") or {}) do
            if Alive(w) then
                lists = lists + 1
                if Shown(w) then shownLists = shownLists + 1 end
            end
        end
    end)
    out[#out + 1] = "key lists (WBP_FieldFuncList2_C): " .. lists .. ", on screen " .. shownLists
    local host = FeedHost()
    out[#out + 1] = "HUD overlay: " .. (host and (size(host) .. ", " .. vis(host)) or "none on screen")
    local box = feed.box and Find(feed.box)
    if not (box and Alive(box)) then
        out[#out + 1] = "box: none"
        return out
    end
    local parent = "?"
    pcall(function() parent = box:GetParent():GetFName():ToString() end)
    local h, v = "?", "?"
    pcall(function() h = tostring(box.Slot.HorizontalAlignment) end)
    pcall(function() v = tostring(box.Slot.VerticalAlignment) end)
    out[#out + 1] = "box: " .. size(box) .. ", " .. vis(box) .. ", in " .. parent ..
        ", alignment " .. h .. "/" .. v
    for i, line in ipairs(feed.lines) do
        local tb = Find(line.path)
        local text, font, fsize, opacity = "?", "?", "?", "?"
        if tb then
            pcall(function() text = tb:GetText():ToString() end)
            pcall(function()
                local f = tb.Font.FontObject
                font = (f and f:IsValid()) and f:GetFName():ToString() or "none"
            end)
            pcall(function() fsize = tostring(tb.Font.Size) end)
            pcall(function() opacity = tostring(tb:GetRenderOpacity()) end)
        end
        out[#out + 1] = string.format("line %d: \"%s\", %s, %s, font %s size %s, opacity %s",
            i, text, tb and size(tb) or "gone", tb and vis(tb) or "gone", font, fsize, opacity)
    end
    if #feed.lines == 0 then out[#out + 1] = "lines: none (they fade after " .. (G.FEED_SHOW + G.FEED_FADE) .. " s)" end
    return out
end

-- Fades and removes old lines. Returns how many are on screen.
function G.FeedTick(now)
    local keep = {}
    for _, line in ipairs(feed.lines) do
        local age = now - line.born
        local tb = Find(line.path)
        if age >= G.FEED_SHOW + G.FEED_FADE or not (tb and Alive(tb)) then
            if tb then pcall(function() tb:RemoveFromParent() end) end
        else
            if age > G.FEED_SHOW then
                local alpha = 1 - (age - G.FEED_SHOW) / G.FEED_FADE
                pcall(function() tb:SetRenderOpacity(alpha) end)
            end
            keep[#keep + 1] = line
        end
    end
    feed.lines = keep
    return #keep
end

-- -------------------------------------------------------------------------------------------
-- The chest pop-up
-- -------------------------------------------------------------------------------------------
-- Blanked chests give nothing (1 gil before round 81), and the general dialog box (WBP_DialogBox_C) still shows "You obtained
-- the following:" over "(gil icon) 1". Rewrites Text_Message to the scouted AP item and collapses
-- Overlay_Custom (the "0 gil" item line), restoring Overlay_Custom when the dialog closes.

local POPUP_MARKER = "obtained"       -- in the game's English chest message
local POPUP_ITEM_LINE = "Overlay_Custom"
local COLLAPSED = 1                   -- ESlateVisibility: Visible 0, Collapsed 1, Hidden 2, ...
local popupHidden = nil               -- { line = path, message = path, visibility = n }
-- Cache the dialog box message widget path once found so fastTick (10 Hz) only polls that widget
-- instead of scanning all RichTextBlocks.
local popupMsgCache = nil
local popupWasShown = false           -- the cached message was on screen at the last check
-- Pre-locate the dialog message widget after each map load (it exists before first opening) so the
-- map's first chest pop-up is caught immediately in fastTick.
local POPUP_MESSAGE_NAME = "Text_Message"
local popupCandidates = {}

-- Finds the dialog box's message widgets, shown or not. Returns how many are kept; 0 when the
-- game has made no dialog box yet.
function G.PrimePopup()
    if #popupCandidates > 0 then return #popupCandidates end
    local ok, all = pcall(FindAllOf, "RichTextBlock")
    for _, b in ipairs(ok and all or {}) do
        if Alive(b) then
            local name
            pcall(function() name = b:GetFName():ToString() end)
            if name == POPUP_MESSAGE_NAME then popupCandidates[#popupCandidates + 1] = G.PathOf(b) end
        end
    end
    return #popupCandidates
end

local function PopupText(b)
    local t
    pcall(function() t = b:GetText():ToString() end)
    return t
end

-- The chest pop-up's message on screen, or nil. Searched for while none is cached.
local function PopupMessage()
    local m = popupMsgCache and Find(popupMsgCache)
    if m and Alive(m) and Shown(m) then
        local t = PopupText(m)
        if t and t:find(POPUP_MARKER, 1, true) then return m end
    end
    local ok, all = pcall(FindAllOf, "RichTextBlock")
    if not ok or not all then return nil end
    for _, b in ipairs(all) do
        if Alive(b) and Shown(b) then
            local t = PopupText(b)
            if t and t:find(POPUP_MARKER, 1, true) then
                popupMsgCache = G.PathOf(b)
                return b
            end
        end
    end
    return nil
end

-- True once each time a chest pop-up comes up, judged from the cached message widget alone, so
-- it is cheap enough to call ten times a second. False until the first pop-up has been found
-- by PopupMessage (the slower search from the regular tick).
function G.PopupJustOpened()
    local m = popupMsgCache and Find(popupMsgCache)
    if not (m and Alive(m) and Shown(m)) then
        popupWasShown = false
        m = nil
        for _, path in ipairs(popupCandidates) do
            local c = Find(path)
            if c and Alive(c) and Shown(c) then
                local t = PopupText(c)
                if t and t:find(POPUP_MARKER, 1, true) then
                    m = c
                    popupMsgCache = path
                    break
                end
            end
        end
        if not m then return false end
    end
    if popupWasShown then return false end
    local t = PopupText(m)
    if t and t:find(POPUP_MARKER, 1, true) then
        popupWasShown = true
        return true
    end
    return false
end

-- Writes `text` into the chest pop-up on screen and collapses its item line. Returns true and a
-- detail, or false and why not (no pop-up on screen yet). A message with no item line beside it is
-- another dialog: in round 78 a character quest's stat bonus said "obtained" before the item
-- pop-up came, took the text, and left the item pop-up as the game made it.
function G.ChestPopup(text, span)
    local msg = PopupMessage()
    if not msg then return false, "no chest pop-up on screen" end
    local parent, line
    pcall(function() parent = msg:GetParent() end)
    local n = 0
    pcall(function() n = parent:GetChildrenCount() end)
    for i = 0, n - 1 do
        local child, name
        pcall(function() child = parent:GetChildAt(i) end)
        pcall(function() name = child:GetFName():ToString() end)
        if name == POPUP_ITEM_LINE and Alive(child) then line = child end
    end
    if not line then return false, "an \"obtained\" message with no item line: not the item pop-up" end
    local message, nameLines = G.PopupSplit(text, span)
    local written = message or text
    if not pcall(function() msg:SetText(FText(written)) end) then return false, "SetText failed" end
    local rowPaths, how = {}, ""
    if nameLines then
        local P, was = G.POPUP_COLORS, G.feedTrace
        G.feedTrace, P.trace = P.trace, nil
        local tree, added, failed = nil, {}, false
        pcall(function() tree = msg:GetOuter() end)
        for _, picked in ipairs(nameLines) do
            local row, slot = feed.row(picked.line, picked.span, P.LOOK, tree), nil
            step("pop-up: add the coloured line (AddChildToVerticalBox)")
            if not (row and pcall(function() slot = parent:AddChildToVerticalBox(row) end) and slot) then
                failed = true
                break
            end
            pcall(function() slot:SetHorizontalAlignment(P.CENTER) end)
            if #added > 0 then pcall(function() slot:SetPadding(P.GAP) end) end
            added[#added + 1] = row
        end
        if failed then
            for _, row in ipairs(added) do pcall(function() row:RemoveFromParent() end) end
            written = text
            pcall(function() msg:SetText(FText(text)) end)
            how = ", the name plain (the coloured line could not be made)"
        else
            for _, row in ipairs(added) do rowPaths[#rowPaths + 1] = G.PathOf(row) end
            how = #added > 1 and ", the names in their colours" or ", the name in its colour"
        end
        step("pop-up: done")
        G.feedTrace = was
    end
    popupWasShown = true   -- this pop-up is handled; the fast check waits for the next one
    local was = 0
    pcall(function() was = line:GetVisibility() end)
    if not pcall(function() line:SetVisibility(COLLAPSED) end) then return true, "text set (the item line would not hide)" .. how end
    popupHidden = { line = G.PathOf(line), message = G.PathOf(msg), visibility = was, rows = rowPaths, text = written }
    return true, "text set, item line hidden" .. how
end

-- Round 90 (the user): the item's name in its colour in the pop-up. The message is a
-- CommonRichTextBlock with no decorators (round 90 probe), so markup cannot colour it: a <text>
-- tag with no style row drew the name black. The line holding the name goes into a row of our
-- own TextBlocks instead (as the feed's), under the message in the dialog's box, styled as the
-- message's text style (BP_SystemTextStyle: size 18, letter spacing 4, shadow 2, 1 at 0.5).
-- Round 91's probe worked: on since round 92 (ffrap_popup colors off). `trace` logs each step of the
-- next coloured pop-up (ffrap_popup colors on).
G.POPUP_COLORS = { on = true, trace = nil, CENTER = 2,
                   LOOK = { size = 18, spacing = 4, shadow = 0.5, offset = { X = 2, Y = 1 }, justify = 1 },
                   -- Round 106 (the user): a quest's two names touched. Space above the second.
                   GAP = { Left = 0, Top = 10, Right = 0, Bottom = 0 } }
-- The message without the lines that hold the spans, and those lines ({ line, span }, in order);
-- or nil with colours off or no span found. `span` is one span or a list (a quest's two rewards).
function G.PopupSplit(text, span)
    if not (G.POPUP_COLORS.on and span) then return nil end
    local wanted, lines, picked = span.text and { span } or span, {}, {}
    for l in (text .. "\n"):gmatch("(.-)\n") do
        local found
        for _, s in ipairs(wanted) do
            if not found and s.text and s.text ~= "" and not s.taken and l:find(s.text, 1, true) then found = s end
        end
        if found then
            found.taken = true
            picked[#picked + 1] = { line = l, span = found }
        else
            lines[#lines + 1] = l
        end
    end
    for _, s in ipairs(wanted) do s.taken = nil end
    if #picked == 0 then return nil end
    return table.concat(lines, "\n"), picked
end

-- Makes the item line visible again once the pop-up has closed. Call every tick.
-- Round 99 (the user): a quest with a stat bonus and an esper showed its next two messages (the
-- bonus, "You can now summon...") in the same dialog, which stayed open, and our coloured names
-- stayed under them. The rows go as soon as the message is no longer ours; the item line stays
-- hidden until the dialog closes, as before.
function G.ChestPopupRestore()
    if not popupHidden then return end
    local function RemovePopupRows()
        for _, path in ipairs(popupHidden.rows) do
            local row = Find(path)
            if row and Alive(row) then pcall(function() row:RemoveFromParent() end) end
        end
        popupHidden.rows = {}
    end
    local line = popupHidden.line and Find(popupHidden.line)
    local msg = popupHidden.message and Find(popupHidden.message)
    if line and Alive(line) and msg and Alive(msg) and Shown(msg) then
        if #popupHidden.rows > 0 and PopupText(msg) ~= popupHidden.text then RemovePopupRows() end
        return
    end
    RemovePopupRows()
    local v = popupHidden.visibility
    if line and Alive(line) then pcall(function() line:SetVisibility(v) end) end
    popupHidden = nil
end

-- Round 90 (the user): the item's name in its colour in the Quests screen's Rewards. Each line is
-- WBP_Quest_Reward_Text_C, whose CommonTextBlock_194 has one style. A block showing one of `spans`
-- (label -> { text, flags }) is replaced by a row of our own TextBlocks: added beside it in a panel
-- (AddChild) with the block collapsed, or in a one-child widget (a NamedSlot) put in its place
-- (SetContent). The list can show the line again for another reward: a row whose block no longer
-- shows its label, or whose label is not in `spans`, is taken out and the block put back.
-- Round 92: walking down from the line found no text block (it sits in the entry panel's named
-- slot); round 93: no CommonTextBlock whose path is in a reward line was found either. The line's
-- own SetText writes CommonTextBlock_194, so the block is the line's property of that name, or
-- else the entry panel's Slot_33_Content (GetContentForSlot). Round 95: it works; on by default
-- since round 96 (ffrap_quest colors off). The tick colours a line a second late at most;
-- `instant` hooks the line's own SetText to colour it at once (round 96's probe worked; on since
-- round 97, ffrap_quest instant off).
G.QUEST_COLORS = { on = true, instant = true, hooked = nil, rows = {}, spans = {},
                   LINE = "WBP_Quest_Reward_Text_C", BLOCK = "CommonTextBlock_194",
                   PANEL = "WBP_IconEntryLayoutPanel_76", SLOT = "Slot_33_Content",
                   SET_TEXT = "/Game/UI/Quest/Bounty/widget/Detail/WBP_Quest_Reward_Text.WBP_Quest_Reward_Text_C:SetText",
                   LOOK = { size = 18, spacing = 4, shadow = 0.5, offset = { X = 2, Y = 1 }, justify = 0 } }
function G.QUEST_COLORS.text(w)
    local t
    pcall(function() t = w:GetText():ToString() end)
    return t
end
-- Puts the game's block back in place of our row. Returns a line for the log.
function G.QUEST_COLORS.restore(blockPath, r)
    local Q, block = G.QUEST_COLORS, Find(blockPath)
    local row, parent = Find(r.row), r.parent and Find(r.parent)
    if r.content and parent and Alive(parent) and block and Alive(block) then
        pcall(function() parent:SetContent(block) end)
    elseif row and Alive(row) then
        pcall(function() row:RemoveFromParent() end)
    end
    if block and Alive(block) then pcall(function() block:SetVisibility(r.visibility) end) end
    Q.rows[blockPath] = nil
    return "taken out: " .. r.label
end
-- Colours one reward line `w` if it shows a scouted label, putting back a row it showed before
-- for another reward. Adds to `out` (lines for the log) and `seen` (what it found). Steps go to `say`.
function G.QUEST_COLORS.line(w, spans, say, out, seen)
    local Q = G.QUEST_COLORS
    local block, how
    pcall(function() block = w[Q.BLOCK] end)
    how = "property"
    if not (block and Alive(block)) then
        block, how = nil, "slot"
        pcall(function() block = w[Q.PANEL]:GetContentForSlot(FName(Q.SLOT)) end)
    end
    if not (block and Alive(block)) then
        seen[#seen + 1] = "no text block"
        return
    end
    local path, text = G.PathOf(block), G.QUEST_COLORS.text(block)
    seen[#seen + 1] = (text and ('"' .. text .. '"' .. (spans[text] and " (scouted)" or "")) or "no text") .. " by " .. how
    local r = path and Q.rows[path]
    if r and (text ~= r.label or not spans[r.label]) then out[#out + 1] = Q.restore(path, r) end
    if not (path and not Q.rows[path] and text and spans[text]) then return end
    local was = G.feedTrace
    G.feedTrace = say
    local parent, tree, row, slot, vis, content = nil, nil, nil, nil, 0, false
    pcall(function() parent = block:GetParent() end)
    pcall(function() tree = block:GetOuter() end)
    local parentName = "nil"
    pcall(function() parentName = parent:GetClass():GetFName():ToString() end)
    pcall(function() vis = block:GetVisibility() end)
    row = parent and feed.row(text, spans[text], Q.LOOK, tree)
    -- Round 94: a NamedSlot holds one child, so AddChild failed, but UE4SS hands back a null
    -- object, which Lua takes as true: the block was hidden and the row went nowhere.
    local function valid(o)
        local okValid, v = pcall(function() return o:IsValid() end)
        return okValid and v == true
    end
    step("quest: add the coloured line to the " .. parentName .. " (AddChild)")
    if row then pcall(function() slot = parent:AddChild(row) end) end
    if not valid(slot) then slot = nil end
    if row and not slot then
        step("quest: put the coloured line in the " .. parentName .. "'s place for the game's (SetContent)")
        pcall(function() slot = parent:SetContent(row) end)
        if not valid(slot) then slot = nil end
        content = slot ~= nil
    end
    if slot then
        if not content then
            step("quest: hide the game's line (SetVisibility)")
            pcall(function() block:SetVisibility(COLLAPSED) end)
        end
        Q.rows[path] = { row = G.PathOf(row), label = text, visibility = vis, content = content, parent = G.PathOf(parent) }
        out[#out + 1] = "coloured: " .. text .. " (in a " .. parentName .. (content and ", in its place" or "") .. ")"
    else
        out[#out + 1] = "not coloured: " .. text .. " (in a " .. parentName .. ")"
    end
    G.feedTrace = was
end
function G.QuestRewardColors(spans, say)
    local Q, out, seen = G.QUEST_COLORS, {}, {}
    Q.spans = spans
    for blockPath, r in pairs(Q.rows) do
        local block = Find(blockPath)
        if not (block and Alive(block)) or G.QUEST_COLORS.text(block) ~= r.label or not spans[r.label] then
            out[#out + 1] = Q.restore(blockPath, r)
        end
    end
    local ok, all = pcall(FindAllOf, Q.LINE)
    for _, w in ipairs(ok and all or {}) do
        if Alive(w) and Shown(w) then Q.line(w, spans, say, out, seen) end
    end
    local summary = string.format("seen: %d reward lines on screen%s%s", #seen, #seen > 0 and ": " or "", table.concat(seen, ", "))
    if summary ~= Q.lastSeen then
        table.insert(out, 1, summary)
        Q.lastSeen = summary
    end
    return out, #seen
end
-- The instant probe: a hook on the reward line's SetText (a Blueprint function, so UE4SS calls it
-- after the text is written). The class loads with the Quests screen, so it is tried until it
-- registers. `log` gets the hook's lines. Returns "registered" the time it registers.
function G.QuestColorHook(log)
    local Q = G.QUEST_COLORS
    if Q.hooked then return nil end
    -- Round 119: a RegisterHook on a class not loaded yet failed at about 7 ms a try, every
    -- second until the Quests screen was first opened.
    if not Find(Q.SET_TEXT:match("^(.-):")) then return nil end
    local ok = pcall(RegisterHook, Q.SET_TEXT, function(self)
        if not (Q.on and Q.instant) then return end
        local w
        pcall(function() w = self:get() end)
        if not (w and Alive(w)) then return end
        local out = {}
        local okLine, err = pcall(Q.line, w, Q.spans, Q.trace, out, {})
        for _, line in ipairs(out) do log("quest colours (instant): " .. line) end
        if not okLine then log("quest colours (instant): failed: " .. tostring(err)) end
    end)
    if not ok then return nil end
    Q.hooked = true
    return "registered"
end

-- Clear cached paths on map load; old map objects are freed and dereferencing stale handles crashes.
function G.ForgetObjects()
    liveCache = {}
    popupMsgCache, popupWasShown, popupHidden = nil, false, nil
    popupCandidates = {}
end

-- Experimental: shows `text` via the game's quest-notice banner view model (NoticeData.NoticeTitle
-- and ExecuteNotics(bool)). Returns ok and a detail.
function G.QuestNotice(text)
    local vm = Live("CPP_VM_QuestNotice")
    if not vm then return false, "no quest notice view model (be in the field)" end
    local set = {}
    if pcall(function() vm.NoticeData.NoticeTitle = FText(text) end) then set[#set + 1] = "NoticeTitle" end
    if pcall(function() vm.NoticeQuestData.Name = FText(text) end) then set[#set + 1] = "quest Name" end
    local okRun, err = pcall(function() vm:ExecuteNotics(true) end)
    if not okRun then return false, "ExecuteNotics raised: " .. tostring(err) end
    local shown
    pcall(function() shown = vm.bDisplayNotice end)
    return true, "set " .. table.concat(set, " and ") .. "; ExecuteNotics ran; bDisplayNotice " .. tostring(shown)
end

-- -------------------------------------------------------------------------------------------
-- Prologue skip
-- -------------------------------------------------------------------------------------------
-- Writes chapter-1 start state directly into the save object before saving and reloading (using
-- game API calls where direct writes are unsafe, such as inventory and visited maps).

G.SKIP_FROM_MAX = 1005    -- prologue story threshold before Fina is controllable
-- Skipping before 1005 (during the opening movie at 1000) leaves the movie's input lock active across
-- reloads; starting from 1005 after the first autosave reloads cleanly.
G.SKIP_FROM_MIN = 1005
G.SKIP_STORY = 1030
local SKIP_FLAGS_ON = { 14, 15, 16, 18, 19, 22, 23, 26, 27, 30, 32, 33, 105, 106, 108, 110, 124, 125,
                        1164, 1225, 1226 }
local SKIP_FLAGS_OFF = { 1, 8 }     -- on between story 1000 and 1005, off again by 1030
local SKIP_PARTY = { 1001, 1002 }   -- Rain, Lasswell
local SKIP_GEAR_OUT = { 10699, 11301, 12029 }   -- Archwitch Fina's prologue gear goes
-- Equipped gear is counted in the bag, so each starter's gear comes in: what DT_InitGameSaveData
-- (NewGame) equips them with. Archwitch Fina's own is the weapon the skip gives her.
local STARTER_GEAR = {
    [1001] = { 10100, 11000, 12000 }, [1002] = { 10200, 11000, 12000 }, [1003] = { 10300, 11500 },
    [1004] = { 10400, 11007 }, [1005] = { 10500, 11509 }, [1006] = { 10600 },
    [1007] = { 10700, 11010, 12022 }, [1008] = { 10800, 11502 },
}
local UNIT_NAMES = { [1001] = "Rain", [1002] = "Lasswell", [1003] = "Fina", [1004] = "Lid", [1005] = "Nichol",
                     [1006] = "Archwitch Fina", [1007] = "Jake", [1008] = "Sakura" }
local ARCHWITCH_FINA, ARCHWITCH_FIRST_SKILL = 1006, 408010
local ALL_PARTY_MEMBERS = { 1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008 }
local SKIP_MAPS = { 5010, 2013, 20000, 3001 }   -- known and visited
-- Open-world starts only mark the battlefield (5010) and, when starting in the airship, its deck
-- (20000), so Grandshelt Castle (2013), Earth Shrine (3001), or the unobtained airship are not
-- immediate fast-travel destinations bypassing continent locks.
G.OPEN_START_MAPS, G.OPEN_START_MAPS_AIRSHIP = { 5010 }, { 5010, 20000 }
-- Round 84 (the user): the Airship item makes the airship a fast travel place at once, as a visit
-- would. 20001 is the airship, 20002 its deck (maps.tsv).
G.AIRSHIP_MAPS = { 20001, 20002 }

-- Marks each map known and visited that the save says is not visited yet. Returns the maps marked,
-- or nil when the save cannot be read.
function G.MarkVisited(maps)
    local perMap = Lib("CPP_BFL_SaveData_PerMap")
    if not perMap then return nil end
    local marked = {}
    for _, m in ipairs(maps) do
        local visited
        pcall(function() visited = perMap:IsVisited(m) end)
        if visited == false and pcall(function() perMap:AddKnownMap(m); perMap:AddVisitedMap(m) end) then
            marked[#marked + 1] = m
        end
    end
    return marked
end

-- Round 84 (the user): fast travel from dungeons. DA_WldMapParameter's FastTravelProperty refuses
-- it with the condition that checks the map type ("Fast Travel cannot be used while you are in a
-- dungeon"). `on` makes that condition's behaviour travel, with the usual confirm dialog; off puts
-- the game's back. The other two conditions (an event under way, a place not visited) stay. Run
-- it every pass: the asset can be loaded again. Returns what changed, or nil.
G.FAST_TRAVEL = { confirm = "UI.Dialog.Box.Map.FastTravel", refuse = "UI.Dialog.Box.Map.FastTravel.CanNot.MapType" }
function G.DungeonFastTravel(on)
    local da = Live("CPP_DA_WldMapParameter")
    if not da then return nil end
    local changed
    pcall(function()
        local list = da.FastTravelProperty.ConditionBehaviorList
        for i = 1, #list do
            local entry = list[i]
            if entry.Condition.bCheckMapType and entry.Behavior.bCanTravel ~= on then
                entry.Behavior.bCanTravel = on
                entry.Behavior.DialogTag.TagName = FName(on and G.FAST_TRAVEL.confirm or G.FAST_TRAVEL.refuse)
                changed = on and "allowed from dungeons" or "refused from dungeons again (the game's rule)"
            end
        end
    end)
    return changed
end
G.SKIP_ARRIVAL = { map = 3001, x = -5775.0, y = 0.0, z = -197.85, direction = 2 }
-- Open-world start sets story 8000 directly (or 7090 at the dock for `event`). Arrivals:
--   dock   story 8000 at the Crystal Tower dock
--   air    story 8000 on the world map riding the airship beside the tower (default)
--   event  story 7090 at the dock near save point 139, letting the two tower events play out
G.OPEN_STARTS = {
    dock = { name = "dock", story = 8000, map = 3280, x = -2704.8, y = -171166.7, z = 3002.2, direction = 2 },
    air = { name = "air", story = 8000, map = 1000, x = -5935.0, y = -8305.0, z = 2075.0, direction = 2,
            airship = true, flags = { 31 } },
    event = { name = "event", story = 7090, map = 3280, x = -2830.0, y = -171140.0, z = 3000.0, direction = 2 },
}
G.OPEN_START = G.OPEN_STARTS.air
-- When `start_with_airship` is off, start on foot at the landing point beside the starting
-- continent's main town (gimmicks.tsv) and park the hidden airship there (spawn condition:
-- flag 1431 / G.AIRSHIP_FLAG) so unlocking it spawns it at the next map load. Each start is an
-- airship landing point of the world map (gimmicks.tsv); `landing` is its id.
G.FOOT_STARTS = {
    grandshelt = { x = 12460.0, y = 20700.0, z = 170.0, landing = 1002 },   -- the Royal Capital
    lanzelt = { x = 12470.0, y = 14980.0, z = 65.0, landing = 2001 },       -- Village of Kol
    kolobos = { x = 5540.0, y = 14600.0, z = 65.0, landing = 3001 },        -- Town of Felicitas
    dirnado = { x = 13190.0, y = 3210.0, z = -12.0, landing = 4002 },       -- Dilmagia
    olderion = { x = -90.0, y = 2680.0, z = 16.0, landing = 5001 },         -- Olderion
    zoldaad = { x = -7200.0, y = 7200.0, z = 64.0, landing = 6002 },        -- Zoldaad
    mysidia = { x = -17515.0, y = -8365.0, z = 96.0, landing = 7001 },      -- Mysidia
    gronoa = { x = 15895.0, y = -14150.0, z = 299.0, landing = 8001 },      -- Gaberada
    pharm = { x = -3920.0, y = -17480.0, z = 90.0, landing = 9001 },        -- Town of Sian
}
for name, a in pairs(G.FOOT_STARTS) do
    a.name, a.story, a.map, a.direction, a.parked = "foot " .. name, 8000, 1000, 2, true
end
G.AIRSHIP_FLAG = 1431
G.AIRSHIP_ITEM_CONDITION = "{flag:1431}"

-- The unitParameterList entry for a unit id, or nil.
local function UnitEntry(sd, unitId)
    local found
    pcall(function()
        local list = sd.unitParameterList
        for i = 1, #list do
            if Int(list[i].UnitId) == unitId then found = list[i] break end
        end
    end)
    return found
end

-- Writes one field and reads it back. Returns true when the value read back is `want`.
local function Put(target, field, want)
    local ok = pcall(function() target[field] = want end)
    local now
    pcall(function() now = target[field] end)
    if type(want) == "number" then now = Int(now) end
    return ok and now == want
end

-- The story counter, as FFRSLib's ffrs_story_set writes it. Returns ok and a report line.
local function WriteStory(sd, n)
    local ok = pcall(function() sd.Progress.Progress[1] = n end)
    return ok and G.StoryCounter() == n, "story counter -> " .. n
end

-- Event flags on and off. eventFlag is 0-based in the snapshots, so flag i is Lua element
-- i + 1. Returns whether the flag array was found, and the flags that did not read back.
local function SetFlags(sd, on, off)
    local flags = nil
    pcall(function() flags = sd.Progress.eventFlag end)
    if not flags then return false, {} end
    local bad = {}
    local function setFlag(i, want)
        local okSet = pcall(function() flags[i + 1] = want end)
        local now
        pcall(function() now = flags[i + 1] end)
        if not okSet or now ~= want then bad[#bad + 1] = i end
    end
    for _, i in ipairs(on or {}) do setFlag(i, true) end
    for _, i in ipairs(off or {}) do setFlag(i, false) end
    return true, bad
end

-- Writes arrival map/coordinates into the save (as ffrs_travel does). `airship` spawns the player
-- riding the airship with event flags set; `parked` places the airship on the world map while the
-- player starts on foot. Returns ok and a report line.
local function WriteArrival(sd, a)
    local ok = pcall(function()
        sd.Map.mapId = a.map
        sd.Map.unitLocation.X = a.x
        sd.Map.unitLocation.Y = a.y
        sd.Map.unitLocation.Z = a.z
        sd.Map.unitDirection = a.direction
        if a.airship then
            sd.Map.airShipLocation.X = a.x
            sd.Map.airShipLocation.Y = a.y
            sd.Map.airShipLocation.Z = a.z
            sd.Map.airShipDirection = a.direction
            sd.Map.IsRidingAirShip = true
            -- Keep false only before the airship's initial placement (DT_MapAirShip initSpawnPointId
            -- 9000 points outside any map/landing table, so otherwise leaving a town loses the airship).
            sd.Map.IsAlreadySpawnAirship = true
        elseif a.parked then
            sd.Map.airShipLocation.X = a.x
            sd.Map.airShipLocation.Y = a.y
            sd.Map.airShipLocation.Z = a.z
            sd.Map.airShipDirection = a.direction
            sd.Map.IsRidingAirShip = false
            sd.Map.IsAlreadySpawnAirship = true
        end
    end)
    local line = "arrival: map " .. a.map .. " at " .. a.x .. ", " .. a.y .. ", " .. a.z
    if a.parked then line = line .. ", on foot, the airship parked there" end
    if a.airship then
        local riding
        pcall(function() riding = sd.Map.IsRidingAirShip end)
        local placed
        pcall(function() placed = sd.Map.IsAlreadySpawnAirship end)
        ok = ok and riding == true and placed == true
        line = line .. ", in the airship"
    end
    if a.flags then
        local found, bad = SetFlags(sd, a.flags)
        ok = ok and found and #bad == 0
        line = line .. ", flags " .. table.concat(a.flags, " ") .. " on"
    end
    return ok and G.MapId() == a.map, line
end

-- Format a UE value as text. Array elements may arrive as UE4SS LocalUnrealParam wrappers that need
-- :get(), and object arrays can hold null elements whose GetFName() crashes without IsValid().
local NULL_OBJECT = "(null)"
local function ObjText(v)
    if type(v) == "string" then return v end
    local okGet, inner = pcall(function() return v:get() end)
    if okGet and inner ~= nil then v = inner end
    if type(v) == "string" then return v end
    local okValid, valid = pcall(function() return v:IsValid() end)
    if okValid and valid == false then return NULL_OBJECT end
    local ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    local okName, n = pcall(function() return v:GetFName():ToString() end)
    if okName and type(n) == "string" then return n end
    return tostring(v)
end

-- Sets JoinStatus = 0 and marks the unit usable without adding spare gear. Returns status string.
function G.FinishJoin(id)
    local how = G.SetJoinStatus(id, 0)
    local sd = G.SaveData()
    local entry = sd and UnitEntry(sd, id)
    if entry then Put(entry, "IsUsable", true) end
    return how
end

-- The quest log's state of each request in `ids`, from the save (request.DataMap, request id ->
-- SaveData_RequestData): "open" (accepted), "done", "not started", or "not in the log"; and the
-- step each is at (ProgressIndex).
G.REQUEST_STATES = { [0] = "not started", [1] = "open", [2] = "done" }
function G.RequestStates(ids)
    local out, steps, want = {}, {}, {}
    for _, id in ipairs(ids) do
        want[id] = true
        out[id] = "not in the log"
    end
    local sd = G.SaveData()
    if not sd then return out, steps end
    pcall(function()
        sd.request.DataMap:ForEach(function(k, v)
            local id = Int(k:get())
            if want[id] then
                local e = v:get()
                out[id] = G.REQUEST_STATES[Int(e.State)] or "?"
                steps[id] = Int(e.ProgressIndex)
            end
        end)
    end)
    return out, steps
end

-- Round 94: on the open start "Arise, Mechabo!" was open, but its hunt (board quest 1001) read
-- none, never ordered, so the Ipooh kills did not count. On a save that had played the story it
-- was ordered (round 86). For each open request in `ids`, the board quests of its current step
-- (DT_RequestData's ProgressList[step].QuestList) that read none are set to ordered. Returns the
-- quest ids set.
function G.OrderRequestQuests(ids)
    local states, steps = G.RequestStates(ids)
    local want, done = {}, {}
    local requests = G.LoadObject(G.MECHABO.requestTable)
    pcall(function()
        requests:ForEachRow(function(_, row)
            local id = Int(row.ID)
            if states[id] ~= "open" or not steps[id] then return end
            local step = row.ProgressList[steps[id] + 1]
            if not step then return end
            for i = 1, #step.QuestList do want[Int(step.QuestList[i])] = true end
        end)
    end)
    if next(want) == nil then return done end
    local sd = G.SaveData()
    pcall(function()
        local list = sd.questBoardList
        for i = 1, #list do
            local q = list[i]
            local qid = Int(q.QuestId)
            if want[qid] and Int(q.State) == 0 then
                q.State = 1
                done[#done + 1] = qid
            end
        end
    end)
    return done
end

-- A quest board quest's state and kills, from the save's questBoardList (EQuest_State: None 0,
-- AfterOrder 1, ConditionAchievement 2, QuestSuccessful 3, QuestFailure 4; KilledCount holds
-- { ID = unit, DeliveryQuantity = kills }). Round 93: "Arise, Mechabo!" was open, and Ipooh kills
-- did not count.
G.BOARD_STATES = { [0] = "none", [1] = "ordered", [2] = "met", [3] = "done", [4] = "failed" }
function G.BoardQuest(questId)
    local sd = G.SaveData()
    local line = "not on the board"
    pcall(function()
        local list = sd.questBoardList
        for i = 1, #list do
            local q = list[i]
            if Int(q.QuestId) == questId then
                local kills = {}
                local k = q.KilledCount
                for j = 1, #k do kills[#kills + 1] = Int(k[j].ID) .. " x" .. Int(k[j].DeliveryQuantity) end
                line = (G.BOARD_STATES[Int(q.State)] or "?") .. ", kills " .. (#kills > 0 and table.concat(kills, " ") or "none")
            end
        end
    end)
    return line
end

-- Whether a unit has learned an ability (activeSkillIdList), or nil with no entry for it.
function G.UnitHasSkill(id, skill)
    local sd = G.SaveData()
    local entry = sd and UnitEntry(sd, id)
    if not entry then return nil end
    local has = false
    pcall(function()
        local list = entry.activeSkillIdList
        for i = 1, #list do has = has or Int(list[i]) == skill end
    end)
    return has
end

-- Active Time Chats: the 56 ATCnn rows of DT_ChatEventData (excluding Pinger and Nawatobi
-- mini-game rows). Save state sits in chat.DataMap (IsReleased, IsAlreadyPlayed) and chat.NoticeQueue.
local CHAT_NUMBERS = { 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 18, 19, 21, 22, 23, 24, 25, 26, 27, 28,
                       29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 47, 48, 49, 50, 51, 52,
                       53, 54, 55, 56, 59, 61, 62, 63 }
G.CHAT_IDS = {}
for i, n in ipairs(CHAT_NUMBERS) do G.CHAT_IDS[i] = string.format("ATC%02d", n) end

-- Marks every Active Time Chat as released and played, and empties the notice queue. A missing
-- row is added empty and filled in the map, the way the title rows are. Safe to run again.
-- Returns ok and a report line.
function G.MarkChatsPlayed(sd)
    local chat, map
    pcall(function() chat = sd.chat; map = chat.DataMap end)
    if not map then return false, "active time chats: the save has no chat data" end
    local have, wanted = {}, {}
    if not pcall(function() map:ForEach(function(k) have[k:get():ToString()] = true end) end) then
        return false, "active time chats: could not read the save's rows"
    end
    local added = 0
    for _, id in ipairs(G.CHAT_IDS) do
        wanted[id] = true
        if not have[id] and pcall(function() map:Add(FName(id), {}) end) then added = added + 1 end
    end
    local marked = 0
    local okMark = pcall(function()
        map:ForEach(function(k, v)
            if wanted[k:get():ToString()] then
                local row = v:get()
                row.IsReleased = true
                row.IsAlreadyPlayed = true
                marked = marked + 1
            end
        end)
    end)
    local okQueue = pcall(function() chat.NoticeQueue:Empty() end)
    pcall(function() chat.LatestNotice = FName("None") end)
    local found, bad = SetFlags(sd, { 31 })
    local ok = okMark and okQueue and marked == #G.CHAT_IDS and found and #bad == 0
    return ok, string.format("active time chats: %d of %d released and played (%d rows added), notices cleared%s, flag 31 on",
        marked, #G.CHAT_IDS, added, okQueue and "" or " FAILED")
end

-- Story flags required in an open-world start:
--   21, 24        visions on the Equip screen (C01_014_04, Mitra)
--   13, 34, 1180  fast travel (Tutorial_FastTravel; 34 unlocks the Map screen)
--   102           Earth Shrine exit (C01_010_02 NoEntry barrier clears when 102 is set)
--   25            staggering enemies (C01_008_02, Earth Shrine boss)
--   28            Fina's esper summoning (C01_037_01_Choice_After)
--   90            Siren earned (ability granted separately by GrantSiren)
-- Flags 1160-1199 and 1217-1229 are tutorial "seen" flags from Tutorial_ talk rows.
local OPEN_WORLD_FEATURES = { 21, 24, 13, 34, 102, 25, 28, 90 }
local OPEN_WORLD_TUTORIALS = {}
for i = 1160, 1199 do OPEN_WORLD_TUTORIALS[#OPEN_WORLD_TUTORIALS + 1] = i end
for i = 1217, 1229 do OPEN_WORLD_TUTORIALS[#OPEN_WORLD_TUTORIALS + 1] = i end
G.OPEN_WORLD_TUTORIALS = OPEN_WORLD_TUTORIALS
local function EnableOpenWorld(sd)
    local found, bad = SetFlags(sd, OPEN_WORLD_FEATURES)
    local foundTutorials, badTutorials = SetFlags(sd, OPEN_WORLD_TUTORIALS)
    for _, flag in ipairs(badTutorials) do bad[#bad + 1] = flag end
    return found and foundTutorials and #bad == 0, string.format("open world flags on: %d features, %d tutorials%s",
        #OPEN_WORLD_FEATURES, #OPEN_WORLD_TUTORIALS, #bad > 0 and (" (failed: " .. table.concat(bad, " ") .. ")") or "")
end

-- The talk event table, the battle group table, and the two kinds of talk row (ETalkEventType).
local SHOP_TABLE = "/Game/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.CDT_TalkEventData_Prod"
local BATTLE_GROUP_TABLE = "/Game/Datatable/Encount/DT_BattleGroup.DT_BattleGroup"
local EVENT_SEQUENCE, EVENT_BLUEPRINT = 0, 1

-- The 16 sanctum crystals (data/crystals.tsv). Short-circuits Int_LegendEV_NN_01 / _01_Short
-- directly to row 07, keeping its flag assignment while clearing its vanilla vision reward and scene.
G.CRYSTALS = {
    { event = 10, map = 10200, flag = 1000 }, { event = 6, map = 10201, flag = 1001 }, { event = 15, map = 10202, flag = 1002 },
    { event = 1, map = 10203, flag = 1003 }, { event = 2, map = 10205, flag = 1007 }, { event = 9, map = 10206, flag = 1009 },
    { event = 3, map = 10207, flag = 1008 }, { event = 7, map = 10208, flag = 1005 }, { event = 8, map = 10209, flag = 1006 },
    { event = 11, map = 10210, flag = 1010 }, { event = 4, map = 10211, flag = 1011 }, { event = 14, map = 10212, flag = 1012 },
    { event = 5, map = 10213, flag = 1013 }, { event = 13, map = 10214, flag = 1014 }, { event = 12, map = 10215, flag = 1015 },
    { event = 16, map = 10216, flag = 1016 },
}

function G.CrystalsPatch()
    local jump, ends = {}, {}
    for _, c in ipairs(G.CRYSTALS) do
        local base = string.format("Int_LegendEV_%02d", c.event)
        jump[base .. "_01"] = base .. "_07"
        jump[base .. "_01_Short"] = base .. "_07"
        ends[base .. "_07"] = true
    end
    local written = 0
    for _, dt in ipairs(TableFamily(Find(SHOP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(name, row)
                local key = ObjText(name)
                if jump[key] then
                    row.EventType = EVENT_BLUEPRINT
                    row.ContinuousEventList[1].EventId = FName(jump[key])
                    written = written + 1
                elseif ends[key] then
                    row.EventType = EVENT_BLUEPRINT
                    row.ObtainItemList:Empty()
                    written = written + 1
                end
            end)
        end)
    end
    return written
end

-- Boss locations (data/bosses.tsv, docs/bosses.md). Each boss trigger checks its own win flag
-- and the victory talk row sets that flag, so the flag reports the check.
G.BOSSES = {
    { group = 9079, flag = 146 }, { group = 9080, flag = 214 }, { group = 9084, flag = 319 },
    { group = 9085, flag = 320 }, { group = 9094, flag = 433 }, { group = 9093, flag = 434 },
    { group = 9109, flag = 548 }, { group = 9110, flag = 549 }, { group = 9111, flag = 550 },
    { group = 9112, flag = 551 }, { group = 9113, flag = 552 }, { group = 9114, flag = 614 },
    { group = 9115, flag = 615 }, { group = 9116, flag = 700 }, { group = 9117, flag = 701 },
    { group = 9138, flag = 1018 }, { group = 7042, flag = 928 }, { group = 7057, flag = 929 },
    { group = 9083, flag = 215 }, { group = 9075, flag = 608 }, { group = 9074, flag = 609 },
    { group = 9073, flag = 610 }, { group = 9072, flag = 611 }, { group = 9071, flag = 612 },
    { group = 9076, flag = 613 }, { group = 9004, flag = 1240 }, { group = 9012, flag = 1241 },
    { group = 9014, flag = 1242 }, { group = 9088, flag = 526 }, { group = 9089, flag = 527 },
    { group = 9060, flag = 113 },   -- Antlion (G.AntlionPatch)
    -- Story bosses added below via G.STORY_BOSSES
    { group = 9013, flag = 1243 }, { group = 9017, flag = 1244 }, { group = 9031, flag = 1245 },
    { group = 9038, flag = 1246 }, { group = 9039, flag = 1247 }, { group = 9040, flag = 1248 },
    { group = 9044, flag = 1249 }, { group = 9046, flag = 1250 }, { group = 9048, flag = 1251 },
}
-- Win rows whose own reward is the location's item now: the 15 cave masters' Magicite, and
-- Sephiroth's vision.
local BOSS_ROWS_NO_REWARD = {
    StrEne_C01_Orge_Destroy = true, StrEne_C02_Eyemeba_Destroy = true, StrEne_C03_ToteAvis_Destroy = true,
    StrEne_C03_MindFlayer_Destroy = true, StrEne_C04_HillGigas_Destroy = true, StrEne_C04_FireHydra_Destroy = true,
    StrEne_C05_Media_Destroy = true, StrEne_C05_IceGigas_Destroy = true, StrEne_C05_Morbol_Destroy = true,
    StrEne_C05_Tyrannosaurus_Destroy = true, StrEne_C05_SkullDragon_Destroy = true,
    StrEne_C06_Bloodysaurus_Destroy = true, StrEne_C06_Cooser_Destroy = true,
    StrEne_C07_Brachioreids_Destroy = true, StrEne_C07_MorbolGreat_Destroy = true,
    Str_LegendEV_07_Boss_05 = true,
}
-- Archaeoaevis's win row writes story 6123, and the Nameless Ruins bosses' chain writes 5064,
-- 5066 and 5070; none must reach a save at story 8000.
local BOSS_ROWS_NO_STORY = {
    Dng_08Gro_43_BattleEnd_01 = true,
    SubEv_BarrierReleased_01 = true,
    SubEv_BarrierReleased_BattleEnd_01_A = true,
    SubEv_BarrierReleased_BattleEnd_02_B = true,
}

-- Story bosses whose triggers and talk rows originally check the story counter. Each entry
-- rewrites the trigger condition to !{flag:N}, routes pre-fight talk through SubEv_C02_SymbolEnemy_Encount,
-- and finishes with sequence Gim_EV_Majipot_Delete_02 setting that boss's flag.
local STORY_BOSS_FIGHT, STORY_BOSS_WIN, MAJIPOT_FLAG = "SubEv_C02_SymbolEnemy_Encount", "Gim_EV_Majipot_Delete_02", 915
-- Kind "list" patches only the matching event list entry (`field`) on actors of `class`, leaving
-- doors functional once defeated. Flags 1240-1260 are unused by vanilla.
G.STORY_BOSSES = {
    [3000] = { group = 9004, flag = 1240, event = "C01_008_02", unit = 10003, kind = "trigger" },
    [3040] = { group = 9012, flag = 1241, event = "C01_030_01", point = 5000, kind = "transition" },
    [2050] = { group = 9014, flag = 1242, event = "C02_208_01", unit = 10037, kind = "npc" },
    -- Siren, at the top of Siren's Tower: the jump spot's door
    [3030] = { group = 9013, flag = 1243, event = "C01_036_01", kind = "list", class = "BP_MapTransitionTrigger_C", field = "m_EventList" },
    -- Aether, Wind Shrine
    [3070] = { group = 9017, flag = 1244, event = "C02_221_01", kind = "list", class = "BP_MapTransitionTrigger_C", field = "m_EventList" },
    -- Tellus, Nameless Ruins: a door like The Hunger's. Its second entry goes nowhere (map -1), so
    -- after the win the first entry is a plain door again: the stairs to the upper floor (round 74).
    [3180] = { group = 9031, flag = 1245, event = "C05_510_01", point = 5000, kind = "transition", reopen = true },
    -- Tellus, Tower of Mysidia. The entry walks the player to a point east of the zone first; from
    -- the zone's sides a stairway is in the way and the walk never ends (round 75). `nowalk` clears it.
    [3200] = { group = 9038, flag = 1246, event = "C05_540_Retry", kind = "list", class = "BP_MapGimmick_EventTrigger_C", field = "m_EventList", nowalk = true },
    -- Lux, Rugged Mountain Path
    [3230] = { group = 9039, flag = 1247, event = "C06_611_01", kind = "list", class = "BP_MapGimmick_EventTrigger_C", field = "m_EventList" },
    -- Elfdrit, Gronoa Shrine. `size` is the zone's new scale. The zone is its actor's root, so the
    -- level's own scale is replaced, not multiplied: round 73's 4 x 4 x 4 made the long, thin lines
    -- shorter (2 x 25 x 2 here; round 75).
    [3240] = { group = 9040, flag = 1248, event = "C06_616_01", kind = "list", class = "CPP_MapGimmick_EventTrigger", field = "m_EventList", size = { X = 6, Y = 30, Z = 4 } },
    -- Gelidus, Sanctissimus Shrine: an automatic door
    [3250] = { group = 9044, flag = 1249, event = "C06_627_01", kind = "list", class = "BP_MapTransitionTrigger_C", field = "m_EventList2" },
    -- Ignis, Mt. Reizan
    [3260] = { group = 9046, flag = 1250, event = "C07_707_01", kind = "list", class = "BP_MapGimmick_EventTrigger_C", field = "m_EventList" },
    -- Tellus, Forest Path (3271, at -1215, 40122, a line across the path, 14.1 x 0.44 x 3). The
    -- story fights him in the Wandering Lands (3270) too; that zone is left to the story, so the
    -- one fight is where its location says (round 76).
    [3271] = { group = 9048, flag = 1251, event = "C07_713_01", kind = "list", class = "BP_MapGimmick_EventTrigger_C", field = "m_EventList", size = { X = 20, Y = 6, Z = 4 } },
}
local STORY_BOSS_EVENTS, STORY_BOSS_GROUPS = {}, {}
for _, b in pairs(G.STORY_BOSSES) do
    STORY_BOSS_EVENTS[b.event] = true
    STORY_BOSS_GROUPS[b.group] = true
end
-- Guard flag required by patched story boss triggers so returning from battle does not re-trigger
-- before the victory row runs. main.lua enables it once the field has settled; flags 1430-1449 are unused.
G.STORY_BOSS_READY_FLAG = 1441

function G.SetStoryBossReady(on)
    if G.GetFlag(G.STORY_BOSS_READY_FLAG) == on then return false end
    G.SetFlag(G.STORY_BOSS_READY_FLAG, on)
    return true
end

local bossTestSaved = nil     -- { talk = {}, group = id, groupFields = {}, chests = { ["map:id"] = {} } }

-- Each talk row, or with `keys` only the rows of those names, found by FindRow. Round 118: a
-- walk of every talk row took 8 to 20 ms, and the story boss step walked them twice a second
-- for two rows.
local function EachTalkRow(fn, keys)
    for _, dt in ipairs(TableFamily(Find(SHOP_TABLE))) do
        if keys then
            for _, key in ipairs(keys) do
                local row
                pcall(function() row = dt:FindRow(key) end)
                if row then pcall(fn, key, row) end
            end
        else
            pcall(function()
                dt:ForEachRow(function(name, row) pcall(fn, ObjText(name), row) end)
            end)
        end
    end
end

local function EachGroupRow(id, fn)
    for _, dt in ipairs(TableFamily(Find(BATTLE_GROUP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                pcall(function() if Int(row.ID) == id then fn(row) end end)
            end)
        end)
    end
end

-- The story's scenes must not run from here: no scene in the battle, none after it, and a loss
-- or an escape runs nothing.
local function BossTestWriteGroup(row, win)
    row.battleEventId = -1
    row.battleFinishEventId = FName(win)
    row.battleFinishLoseEventId = FName("None")
    row.battleFinishEscapeEventId = FName("None")
    row.isResultSkipOnWin = false
    row.isResultSkipOnLose = false
end

-- Replace boss reward with 1 Potion so the victory reward dialog still triggers and the mod can
-- overwrite it with the scouted AP item.
local BOSS_STAND_IN = 1

-- Round 97 (the user): every boss holds a shuffled item, and its pop-up shows it. These bosses'
-- finish rows (each fight's battleFinishEventId) give nothing, so no pop-up came: each gets the
-- stand-in while it has no item. The story bosses the mod brings back share STORY_BOSS_WIN, which
-- is the game's own Majipot row too: SyncStoryBossTrigger gives it the stand-in on their maps only.
G.BOSS_ROWS_ADD_STAND_IN = {
    Dng_08Gro_43_BattleEnd_01 = true, Dng_08Gro_43_BattleEnd_02 = true, Dng_08Gro_43_BattleEnd_03 = true,
    Dng_08Gro_43_BattleEnd_04 = true, Dng_08Gro_43_BattleEnd_05 = true, Dng_08Gro_43_BattleEnd_06 = true,
    SubEv_C02_ThunderMountainEnemy_02 = true, SubEv_BarrierReleased_BattleEnd_Left = true,
    SubEv_BarrierReleased_BattleEnd_Right = true, SubEv_C09_01Gra_41_Delete_01 = true,
    SubEv_C09_01Gra_41_Delete_02 = true, C01_ArijigokuWin_02 = true,
}
-- With `on`, gives an empty reward row the stand-in; without, takes back a lone stand-in. True when written.
function G.StandIn(row, on)
    local list = row.ObtainItemList
    if on and #list == 0 then
        local _ = list[1]
        list[1].ID, list[1].Num = BOSS_STAND_IN, 1
        return true
    end
    if not on and #list == 1 and Int(list[1].ID) == BOSS_STAND_IN then
        list:Empty()
        return true
    end
    return false
end

-- Swaps those rewards for the stand-in, gives the empty finish rows one, takes story values out of
-- win rows, and strips story cutscenes from G.STORY_BOSSES talk and battle-group rows. Safe to run
-- again. Returns the number of rows written.
function G.BossesPatch()
    local written = 0
    EachTalkRow(function(key, row)
        if G.BOSS_ROWS_ADD_STAND_IN[key] and G.StandIn(row, true) then written = written + 1 end
        if BOSS_ROWS_NO_REWARD[key] then
            local reward = row.ObtainItemList[1]
            reward.ID, reward.Num = BOSS_STAND_IN, 1
            written = written + 1
        elseif BOSS_ROWS_NO_STORY[key] then
            row.ProgressList:Empty()
            written = written + 1
        elseif STORY_BOSS_EVENTS[key] then
            row.EventType = EVENT_BLUEPRINT
            row.OnFlagList:Empty()
            row.OffFlagList:Empty()
            row.ProgressList:Empty()
            local list = row.ContinuousEventList
            if #list < 1 then local _ = list[1] end
            list[1].Condition = ""
            list[1].EventId = FName(STORY_BOSS_FIGHT)
            written = written + 1
        end
    end)
    for _, dt in ipairs(TableFamily(Find(BATTLE_GROUP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                local id = Int(row.ID)
                if STORY_BOSS_GROUPS[id] and not (bossTestSaved and bossTestSaved.group == id) then
                    BossTestWriteGroup(row, STORY_BOSS_WIN)
                    written = written + 1
                end
            end)
        end)
    end
    return written
end

-- Antlion (battle group 9060) in Lanzelt's sandpit: route both branches of C01_ArijigokuWin to
-- _Win_02 (sets flag 113) so defeating it permanently clears the passage even without story flag 10.
-- Returns the number of rows written.
G.ANTLION_WIN, G.ANTLION_WIN_FOR_GOOD = "C01_ArijigokuWin", "C01_ArijigokuWin_02"
function G.AntlionPatch()
    local written = 0
    EachTalkRow(function(key, row)
        if key ~= G.ANTLION_WIN then return end
        local list = row.ContinuousEventList
        for i = 1, #list do
            if ObjText(list[i].EventId) ~= G.ANTLION_WIN_FOR_GOOD then
                list[i].EventId = FName(G.ANTLION_WIN_FOR_GOOD)
                written = written + 1
            end
        end
    end)
    return written
end

-- Round 73: in the Crystal Tower's Behemoth fight (battle group 9051, battle event C08_808), the
-- Sworn Six's ally (unit 1014) hits for a fixed 2000, 2000 and 3000. With Behemoth scaled to a low
-- party, those hits alone killed it. They now deal 1, so the scenes still play but the party has
-- to win the fight. No other unit uses these three skills. Returns the number of rows written.
G.BEHEMOTH = { map = 3280, skillTable = "/Game/Datatable/Skill/DT_SkillData.DT_SkillData",
    assistSkills = { [501940] = true, [501950] = true, [501960] = true } }
function G.BehemothPatch()
    local written = 0
    for _, dt in ipairs(TableFamily(Find(G.BEHEMOTH.skillTable))) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                pcall(function()
                    if G.BEHEMOTH.assistSkills[Int(row.ID)] and Int(row.magnification) ~= 1 then
                        row.magnification = 1
                        written = written + 1
                    end
                end)
            end)
        end)
    end
    return written
end

-- Replace radar dig row rewards with 1 Potion so the reward dialog still triggers and displays
-- the scouted AP item. Returns the number of rows written.
function G.RadarPatch()
    local rows = {}
    for _, t in ipairs(G.RADAR) do rows[t.row] = true end
    local written = 0
    EachTalkRow(function(key, row)
        if not rows[key] or #row.ObtainItemList < 1 then return end
        local reward = row.ObtainItemList[1]
        if Int(reward.ID) ~= BOSS_STAND_IN then
            reward.ID, reward.Num = BOSS_STAND_IN, 1
            written = written + 1
        end
    end)
    return written
end

-- Round 120 (round 117's finding): the dig rows of treasures 5, 9 and 13, the last of each tier in
-- the game's order, go on to Lid's "the radar seems to have stopped picking up treasure"
-- (SubEv_C05_TreasureRadar_10_0n). 5's and 9's need step 30 and 40, which the mod holds, and
-- 13's needs nothing, so the line came while treasures were left. Each of those rows goes on to
-- the line only while the dig would leave none the radar can find (`level` Progressive Radars).
-- Flag 703 is set by every dig row, so RADAR_NEVER is never true. Returns the rows written.
G.RADAR_LAST = { [5] = "{progress:49}==30", [9] = "{progress:49}==40", [13] = "" }
G.RADAR_NEVER = "{flag:703}&!{flag:703}"
function G.RadarLidLines(level)
    local want, keys = {}, {}
    for n, line in pairs(G.RADAR_LAST) do
        local last = true
        for _, p in ipairs(G.RADAR) do
            if p.n ~= n and p.tier <= level and G.GetFlag(p.flag) ~= true then last = false end
        end
        want[G.RADAR[n].row] = last and line or G.RADAR_NEVER
        keys[#keys + 1] = G.RADAR[n].row
    end
    local written = 0
    EachTalkRow(function(key, row)
        local entry = row.ContinuousEventList[1]
        if ObjText(entry.Condition) ~= want[key] then
            entry.Condition = want[key]
            written = written + 1
        end
    end, keys)
    return written
end

-- Round 78: side quests that are locations (quests.lua, from data/quests.tsv; docs/side_quests.md).
-- A quest's check is its counter at or past the value its reward row writes.
G.QUESTS = require("quests")
-- Round 97 (the user): the one-time NPC gifts, locations by their flags (gifts.lua).
G.GIFTS = require("gifts")
-- The Mechabo quests run on progress 16, which the story's repair request (C02_219_02, at story
-- 2120 only) sets to 10. Our start skips it, so Verun never shows (IDEAS.md idea 33).
-- C02_219_02 also accepts "Arise, Mechabo!" (request 17) into the quest log. Round 84: Verun asked
-- for the Ipooh drops with no quest in the log. His own rows for that step accept it instead:
-- `_yet` when he asks, and `_ItemGet` when the drops are delivered before talking to him.
-- Round 85: still no quest. Request 17's own row (DT_RequestData C02_MechaboLvUp) is accepted only
-- while `{progress:16}==0&{progress:0}>=2120`, and the start has set the counter to 10, so the
-- Accept was refused. Its accept and occurrence tests become the counter at Verun's step. The
-- quest board's Ipooh hunt (quest 1001) most likely counts only while the quest is accepted.
-- Round 105: Aileen's forge on the airship deck (C06_AileenWeapon_*, docs/side_quests.md section 7).
-- Each forge row gives one of the eight weapons, takes one Adamantite and sets `flag`, before its
-- pop-up. The game lists a weapon only while none is held (equipped gear counts), and the row after
-- each forge (`after`) ends the forge (progress 38 to 70) as soon as Rain's weapon is held. As
-- locations, it ends only with all eight held. Weapons in the choice dialog's order.
G.FORGE = { flag = 1236, adamantite = 20016, after = "C06_AileenWeapon_06", done = "C06_AileenWeapon_06_complete",
            weapons = { 10190, 10290, 10390, 10490, 10590, 10790, 10890, 10690 } }
function G.ForgePatch()
    local all = {}
    for i, id in ipairs(G.FORGE.weapons) do all[i] = "{item:" .. id .. "}>=1" end
    local cond = table.concat(all, "&")
    local written = 0
    EachTalkRow(function(key, row)
        if key ~= G.FORGE.after then return end
        local list = row.ContinuousEventList
        for i = 1, #list do
            if ObjText(list[i].EventId) == G.FORGE.done and ObjText(list[i].Condition) ~= cond then
                list[i].Condition = cond
                written = written + 1
            end
        end
    end)
    return written
end

-- Round 107 (the user): in Zoldaad Castle (map 3160) a walk-in scene with the squad leader, Shera
-- and Ignis (SubEv_Dng_06Zol_44_GimEv_03) runs while the Throne Room Key is not held. Both its
-- answers give the key: _03_A after the battle, _03_B by talking. With the key in the pool, that
-- gave it out of logic. The trigger is turned off on the map (the game judges a zone at the map's
-- load, so its condition alone is not enough: round 76), and the two rows give the stand-in, in
-- case the scene starts before the mod sees the trigger.
G.THRONE_KEY = { item = 20021, map = 3160, event = "SubEv_Dng_06Zol_44_GimEv_03", never = "{progress:0}<0",
                 rows = { SubEv_Dng_06Zol_44_GimEv_03_A = true, SubEv_Dng_06Zol_44_GimEv_03_B = true } }
function G.ThroneKeyRowsPatch()
    local T, written = G.THRONE_KEY, 0
    EachTalkRow(function(key, row)
        if not T.rows[key] then return end
        local list = row.ObtainItemList
        for i = 1, #list do
            if Int(list[i].ID) == T.item then
                list[i].ID = BOSS_STAND_IN
                written = written + 1
            end
        end
    end)
    return written
end
-- How many of the squad leader's triggers were turned off now. Call each tick on the map: a map
-- load makes the trigger again as the game made it.
function G.ThroneKeyTriggerOff()
    local T, changed = G.THRONE_KEY, 0
    local ok, all = pcall(FindAllOf, "CPP_MapGimmick_EventTrigger")
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            pcall(function()
                local list = a.m_EventList
                for i = 1, #list do
                    if ObjText(list[i].EventId) == T.event and ObjText(list[i].Condition) ~= T.never then
                        step("throne key: trigger collision off, SetGimmickCondition 1, condition never")
                        a:SetActorEnableCollision(false)
                        if a.m_GimmickCondition ~= 1 then a:SetGimmickCondition(1, false) end
                        list[i].Condition = T.never
                        changed = changed + 1
                    end
                end
            end)
        end
    end
    return changed
end

-- Round 108 (the key item audit): the man in front of Sian's inn (NPC 22, map 2170) gives the Cabin
-- Key once the cabin's door has been tried (flag 1410), at any story. With the key in the pool, that
-- copy was out of logic. His entry that gives it says his line from before the cabin instead. A row
-- with the stand-in would hand out a Potion at every talk, as his entry holds until the key is held.
-- Call each tick on the map: a map load makes him again as the game made him.
G.CABIN_KEY = { map = 2170, give = "FEV_Town_09Pha_01_1044_02", say = "FEV_Town_09Pha_01_1044_01" }
function G.CabinKeyManOff()
    local C, changed = G.CABIN_KEY, 0
    local ok, all = pcall(FindAllOf, "BP_MapUnit_NPC_C")
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            pcall(function()
                local entries = a.m_EventSettings.EventList
                for i = 1, #entries do
                    local events = entries[i].EventList
                    for j = 1, #events do
                        if ObjText(events[j].EventId) == C.give then
                            step("cabin key: npc entry " .. i .. " -> " .. C.say)
                            events[j].EventId = FName(C.say)
                            changed = changed + 1
                        end
                    end
                end
            end)
        end
    end
    return changed
end

-- Round 108 (the user): with the key items not shuffled, the Dungeon Key never came. Its only
-- source is a drop from the soldier of battle group 9096, whose trigger in Zoldaad Dungeon
-- (SubEv_Dng_06Zol_43_GimEv_01) needs story 4180 exactly. main.lua gives it in the dungeon.
G.DUNGEON_KEY = { item = 20019, map = 3150 }

-- Round 108 (a tester): "The Tide from the Sky" (Olderion) takes the player through Grandport Harbor
-- in a scene (SubEv_C03_Mercedes_02_02, then back to Olderion). The visit made Grandport a fast
-- travel place with Lanzelt still locked. Each map of a locked continent (maps.tsv's island) is
-- marked not visited again (Map.perMapSaveDataMap), so fast travel refuses it.
-- Round 117 (the user): not enough. With Grandport marked not visited, the Map screen still fast
-- travelled there from Waterfall Way. The Map screen greys a place that is not visited, but its
-- "never visited" refusal may test the known mark, so the map is made unknown too (ffrap_visited
-- tests which one it reads).
G.CONTINENT_MAPS = {
    grandshelt = { 2000, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 3000, 3001, 3020, 5198, 10001, 10020, 10216, 10218, 10236, 10237 },
    lanzelt = { 2020, 2030, 2031, 3030, 3031, 10051, 10203, 10208, 10223, 10228 },
    kolobos = { 2040, 3040, 10201, 10221 },
    dirnado = { 2050, 2060, 2061, 3050, 3060, 3061, 3062, 3070, 3290, 5030, 5040, 5041, 5156, 10052, 10202, 10206, 10207, 10222, 10226, 10227 },
    olderion = { 2070, 2080, 2081, 2090, 3080, 3090, 3091, 3100, 3110, 3111, 5031, 5130, 10053, 10054, 10059, 10200, 10205, 10209, 10220, 10225, 10229, 11000 },
    zoldaad = { 2100, 2101, 2102, 2110, 2111, 2112, 2113, 2114, 2120, 3120, 3121, 3130, 3131, 3140, 3150, 3160, 5050, 5090, 5100, 5140, 10030, 10031, 10055, 10056, 10210, 10211, 10212, 10230, 10231, 10232 },
    mysidia = { 2130, 2140, 3170, 3180, 3190, 3200, 3210, 3211, 3212, 3213, 5195, 5197, 10057, 10058, 10213, 10214, 10215, 10233, 10234, 10235 },
    gronoa = { 2150, 2160, 3220, 3230, 3240, 3250, 10060, 10062, 10063, 10064 },
    pharm = { 2170, 2180, 2190, 3010, 3260, 3270, 3271, 3272, 5180, 5181, 10061, 10065, 10066 },
}
-- Round 117 (the user): on an open continent too, a place counts for fast travel only once the
-- player has stood in it on the field. `walked` (map -> true) holds those maps; a continent's map
-- not in it is marked the same way as a locked continent's. Without `walked`, only locked
-- continents. Returns the maps marked now. The map the player is on is left alone.
G.CONTINENT_OF = {}
for name, maps in pairs(G.CONTINENT_MAPS) do
    for _, m in ipairs(maps) do G.CONTINENT_OF[m] = name end
end
function G.UnvisitLocked(walked)
    local sd = G.SaveData()
    if not sd then return {} end
    local locked, here, cleared = {}, G.CurrentMap(), {}
    for _, c in ipairs(G.CONTINENTS) do
        local shut = G.GetFlag(c.flag) == false
        for _, m in ipairs(G.CONTINENT_MAPS[c.name] or {}) do
            if shut or (walked and not walked[m]) then locked[m] = true end
        end
    end
    pcall(function()
        sd.Map.perMapSaveDataMap:ForEach(function(key, value)
            local m = Int(key:get())
            if locked[m] and m ~= here then
                local row = value:get()
                if row.bIsVisited == true or row.bIsKnown == true then
                    row.bIsVisited, row.bIsKnown = false, false
                    cleared[#cleared + 1] = m
                end
            end
        end)
    end)
    return cleared
end

-- Round 117 (the user): Kolobos Ruins' floor falls under the player in a scene
-- (C01_ColobosBridge_02, flag 111) and Rain puts it back from the far side (C01_ColobosBridge_03,
-- flag 112, "elbow grease"). A fast travel out from the far side left the way in blocked for good.
-- Off the ruins' map, a fallen floor is put back as the scene would; the scene gives nothing.
G.KOLOBOS_BRIDGE = { map = 3040, fell = 111, fixed = 112 }

-- The continents' maps the save marks visited: the places a save from before round 117 has
-- already been to count as walked in.
function G.VisitedMaps()
    local sd, out = G.SaveData(), {}
    if not sd then return out end
    pcall(function()
        sd.Map.perMapSaveDataMap:ForEach(function(key, value)
            local m = Int(key:get())
            if G.CONTINENT_OF[m] and value:get().bIsVisited == true then out[#out + 1] = m end
        end)
    end)
    table.sort(out)
    return out
end

-- Round 117 probe (ffrap_visited): a map's known and visited marks, as the save's row holds them
-- and as CPP_BFL_SaveData_PerMap answers. `known` and `visited`, when given, are written first.
function G.MapMarks(m, known, visited)
    local sd = G.SaveData()
    if not sd then return "no save" end
    local row
    pcall(function()
        sd.Map.perMapSaveDataMap:ForEach(function(key, value)
            if Int(key:get()) == m then row = value:get() end
        end)
    end)
    if not row then return "map " .. m .. ": no row in the save" end
    if known ~= nil then row.bIsKnown, row.bIsVisited = known, visited end
    local perMap, answer = Lib("CPP_BFL_SaveData_PerMap"), "?"
    if perMap then pcall(function() answer = tostring(perMap:IsVisited(m)) end) end
    return string.format("map %d: row known %s, visited %s; IsVisited %s", m, tostring(row.bIsKnown),
        tostring(row.bIsVisited), answer)
end

-- Round 107 (the user): Grandport Harbor's vision Moogle (NPC 720, map 2030) shows only with flag
-- 144, which its chapter 1 scene sets (SubEv_C01_Moogle_01, story 1240). The open start skips it,
-- so a Lanzelt start had no Magicite upgrades. Every other town's Moogle has no flag condition.
-- Round 112: every Moogle's shop row (VisionUpgrade, VisionUpgrade_Main) goes on to Grandport's
-- explanation scene SubEv_C01_Moogle_02 while "!{flag:145}&{flag:144}", and that scene only sets
-- 145. With 144 alone it played at the first Moogle anywhere, staged for Grandport, and left the
-- player out of bounds on other maps. Both flags together skip it.
G.VISION_MOOGLE_FLAGS = { 144, 145 }

G.MECHABO = { counter = 16, start = 10, request = 17,
              rows = { "C02_MechaboLvUp_00_yet", "C02_MechaboLvUp_00_ItemGet" },
              requestTable = "/Game/Datatable/Request/DT_RequestData.DT_RequestData",
              requestRow = "C02_MechaboLvUp", accept = "{progress:16}==10",
              -- Round 88: Lid did not learn Mechabo Tackle. It comes from C02_MechaboLvUp_03, run at
              -- counter 30 with flag 219 (the step's drops delivered); the mod logs all three.
              delivered = 219, lid = 1004, tackle = 404110,
              -- Arise, Mechabo!; Mechabo Evolved; Mechabo Unleashed (round 92: no quest showed)
              requests = { 17, 26, 27 },
              hunt = 1001 }   -- request 17's first step: defeat two Ipoohs (unit 55) near the forge
-- Puts an Accept of request 17 first in each of those rows' RequestStateSettings, and request 17's
-- accept and occurrence tests at Verun's step. Safe to run again. Returns the rows written.
function G.MechaboPatch()
    local M, written, wanted = G.MECHABO, 0, {}
    local requests = G.LoadObject(M.requestTable)
    local request
    pcall(function() request = requests:FindRow(M.requestRow) end)
    if request then
        local now
        pcall(function() now = request.AcceptCondition:ToString() end)
        if now ~= M.accept then
            pcall(function()
                request.AcceptCondition = M.accept
                request.Occurrence.Condition = M.accept
            end)
            written = written + 1
        end
    end
    for _, r in ipairs(M.rows) do wanted[r] = true end
    EachTalkRow(function(key, row)
        if not wanted[key] then return end
        local list = row.RequestStateSettings
        -- ERequestStateChangeType: Accept 0, Proceed 1, Complete 2
        if #list >= 1 and Int(list[1].RequestID) == M.request and Int(list[1].Type) == 0 then return end
        local keep = { { M.request, 0, 0 } }
        for i = 1, #list do
            keep[#keep + 1] = { Int(list[i].RequestID), Int(list[i].Type), Int(list[i].ProgressIndex) }
        end
        list:Empty()
        for i, e in ipairs(keep) do
            local _ = list[i]
            list[i].RequestID, list[i].Type, list[i].ProgressIndex = e[1], e[2], e[3]
        end
        written = written + 1
    end)
    return written
end

-- Oblivion Palace (IDEAS.md idea 37): safe n opens at {progress:43} >= 11 + n. The princess's
-- first talk sets the counter to 10 (`met`), and each later talk adds one per step of shards
-- turned in. The steps are DT_TalkEvent_CollectMedal's (data/game/shard_chests.tsv).
G.PALACE = { counter = 43, met = 10, item = 25004, map = 2031,
             steps = { 3, 6, 9, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 60, 64, 68, 72, 76, 80, 84,
                       89, 94, 99 } }

-- Whether at least n shards have been turned in to the princess, or nil when the game cannot say.
-- The count is in SaveData_TransferTargetInventoryByMap, a map of maps, so ask the game's own
-- condition test. It reads the current map's turn-ins: on the world map it said none (round 80).
function G.TurnedInAtLeast(n)
    local lib = Lib("CPP_BFL_Condition")
    if not (lib and lib.IsMeetCondition) then return nil end
    local test = string.format("{transferItem:0,%d}>=%d", G.PALACE.item, n)
    local ok, met = pcall(function() return lib:IsMeetCondition(test, true) end)
    if not ok or type(met) ~= "boolean" then return nil end
    return met
end

-- Shards turned in, 0 to 99, found by halving in 7 condition tests, or nil when the game cannot say.
function G.TurnedInCount()
    local lo, hi = 0, G.PALACE.steps[#G.PALACE.steps]
    while lo < hi do
        local mid = (lo + hi + 1) // 2
        local met = G.TurnedInAtLeast(mid)
        if met == nil then return nil end
        if met then lo = mid else hi = mid - 1 end
    end
    return lo
end

-- Holds the palace counter at `met` plus the steps paid by the shards held and turned in, so each
-- safe opens with no talk. The shards stay in the bag: a talk to the princess still takes them and
-- plays her milestone talks (28, 60 and 99 turned in), and her step loop finds every step done.
-- Never lowers the counter. The turned-in count is read only in the palace, and again only when
-- the held count changes there (she takes them); elsewhere the last reading for the save counts,
-- or none. Returns a status line when it changes.
function G.PalaceSync()
    local P = G.PALACE
    local held = G.HeldCount(P.item)
    if not held then return nil end
    local saveName = tostring(G.SaveObjectName())
    if saveName ~= P.save then P.save, P.turned, P.heldAt = saveName, nil, nil end
    if G.CurrentMap() == P.map and (P.turned == nil or held ~= P.heldAt) then
        P.turned, P.heldAt = G.TurnedInCount(), held
    end
    local paid = 0
    for _, need in ipairs(P.steps) do
        if held + (P.turned or 0) >= need then paid = paid + 1 end
    end
    local now = G.ProgressValue(P.counter)
    if now and now < P.met + paid then now = G.SetProgressValue(P.counter, P.met + paid) end
    local line = string.format("palace: %d shards held, %s turned in, %d steps paid, progress %d at %s",
        held, P.turned and tostring(P.turned) or "not read yet", paid, P.counter, tostring(now))
    if line == P.line then return nil end
    P.line = line
    return line
end

-- Each reward row loses the quest's location item (`item` in quests.lua) and any vision (an item
-- of its own in the world). With `second` (round 98), the second reward (`item2`, -1 for the gil)
-- goes too, as it is a location of its own. Otherwise gil and other items stay. Round 81: a row left empty still completes
-- the quest and shows the game's pop-up for the mod to write into. Round 84: not for Mog Tag. Its
-- rows hold only the location's item, and left empty they showed "You obtained a vision!", which
-- the mod did not find to write into. A quest with no `before` (no pop-up armed ahead of its
-- check) keeps the stand-in Potion in a row that would be left empty. Safe to run again: a row
-- without the item is left alone. Returns the rows written.
G.VISION_IDS = { first = 13000, last = 13999 }
function G.QuestsPatch(second)
    local quests = {}
    for _, q in ipairs(G.QUESTS) do
        for _, r in ipairs(q.rows) do quests[r] = q end
    end
    local written = 0
    EachTalkRow(function(key, row)
        local q = quests[key]
        if not q then return end
        local item, item2 = q.item, second and q.item2
        local list = row.ObtainItemList
        local keep, took, took2, changed = {}, false, false, false
        for i = 1, #list do
            local id, num = Int(list[i].ID), Int(list[i].Num)
            if id >= G.VISION_IDS.first and id <= G.VISION_IDS.last then
                changed = true
            elseif id == item and not took then
                took, changed = true, true
            elseif id == item2 and not took2 then
                took2, changed = true, true
            else
                keep[#keep + 1] = { id = id, num = num }
            end
        end
        if not changed then return end
        -- An empty list shows "You obtained a vision!" (round 84). Round 88: kept for the quests
        -- whose pop-up is written early too, for when that write misses.
        if #keep == 0 then keep[1] = { id = BOSS_STAND_IN, num = 1 } end
        list:Empty()
        for i, e in ipairs(keep) do
            local _ = list[i]
            list[i].ID, list[i].Num = e.id, e.num
        end
        written = written + 1
    end)
    return written
end

-- The NPC gifts' rows give the stand-in in place of their items, as the cave masters' do, so the
-- gift's pop-up comes up for the location's item. The gift sets its flag before the pop-up shows,
-- so the check writes it. The Magi-tenna's gift is a location only with the radar treasures
-- (`radar`). Returns the rows written.
function G.GiftsPatch(radar)
    local rows = {}
    for _, g in ipairs(G.GIFTS) do
        if radar or not g.radar then rows[g.row] = true end
    end
    local written = 0
    EachTalkRow(function(key, row)
        if not rows[key] then return end
        local list = row.ObtainItemList
        if #list == 1 and Int(list[1].ID) == BOSS_STAND_IN and Int(list[1].Num) == 1 then return end
        list:Empty()
        local _ = list[1]
        list[1].ID, list[1].Num = BOSS_STAND_IN, 1
        written = written + 1
    end)
    return written
end

-- Round 88 (the user): the Quests screen's Rewards list shows what each quest location holds.
-- It is DT_RequestData's `Prize`; an entry with ID 0 shows its Text, as "Attribute Bonus: Fina"
-- does. `labels`: location key -> text, for the location's entry (the one with its vanilla item;
-- `key2`'s is `item2`'s, round 98); a location left out gets its vanilla entry back. Returns the
-- entries written.
G.PRIZE = { table = "/Game/Datatable/Request/DT_RequestData.DT_RequestData", slots = {} }
function G.QuestPrizes(labels)
    local P, byId = G.PRIZE, {}
    for _, q in ipairs(G.QUESTS) do byId[tonumber(q.key:match("^quest:(%d+)$"))] = q end
    local requests = G.LoadObject(P.table)
    if not requests then return 0 end
    local written = 0
    pcall(function()
        requests:ForEachRow(function(_, row)
            local q = byId[Int(row.ID)]
            if not q then return end
            local prize = row.Prize
            for _, part in ipairs({ { q.key, q.item }, q.key2 and { q.key2, q.item2 } or nil }) do
                local key, item = part[1], part[2]
                local slot = P.slots[key]
                if not slot then
                    for i = 1, #prize do
                        if Int(prize[i].ID) == item then slot = i end
                    end
                    P.slots[key] = slot
                end
                if slot and slot <= #prize then
                    local label, id, shown = labels[key], Int(prize[slot].ID), ""
                    pcall(function() shown = prize[slot].Text:ToString() end)
                    if label and (id ~= 0 or shown ~= label) then
                        prize[slot].ID = 0
                        prize[slot].Text = FText(label)
                        written = written + 1
                    elseif not label and id == 0 then
                        prize[slot].ID = item
                        prize[slot].Text = FText("")
                        written = written + 1
                    end
                end
            end
        end)
    end)
    return written
end

-- Rewrites the current map's story boss trigger, NPC pawn and shared encounter/win rows so the
-- boss can be fought at story 8000 until its flag is set. When `say` is given (ffrap_bossfight
-- trigger), each step is logged before its engine write runs. Returns true and a summary on a
-- story boss map, or nil and why on any other map.
G.STORY_BOSS_GROUP_WRITE = { map = nil, calls = 0, rows = 0, every = 10 }
function G.SyncStoryBossTrigger(say)
    local step = say or function() end
    local mapId = G.CurrentMap()
    local boss = mapId and G.STORY_BOSSES[mapId]
    if not boss then
        if not bossTestSaved then
            EachTalkRow(function(_, row)
                if #row.OnFlagList >= 1 and Int(row.OnFlagList[1]) ~= MAJIPOT_FLAG then
                    row.OnFlagList[1] = MAJIPOT_FLAG
                end
                G.StandIn(row, false)
            end, { STORY_BOSS_WIN })
        end
        return nil, "no story boss on map " .. tostring(mapId)
    end
    local won = G.GetFlag(boss.flag) == true
    local cond = "!{flag:" .. boss.flag .. "}"
    local fightCond = cond .. "&{flag:" .. G.STORY_BOSS_READY_FLAG .. "}"
    local fightRows, winRows, groupRows, standIns = 0, 0, 0, 0
    if not bossTestSaved then
        step(string.format("story boss: tables for group %d, flag %d (won %s)", boss.group, boss.flag, tostring(won)))
        EachTalkRow(function(key, row)
            if key == STORY_BOSS_FIGHT then
                row.encountGroupId = boss.group
                fightRows = fightRows + 1
            elseif key == STORY_BOSS_WIN then
                for i = 1, #row.OnFlagList do row.OnFlagList[i] = boss.flag end
                G.StandIn(row, true)
                winRows = winRows + 1
                -- Round 120: round 119's win showed no pop-up for the mod to write. This says
                -- whether the row held the stand-in that brings it.
                local list = row.ObtainItemList
                if #list >= 1 and Int(list[1].ID) == BOSS_STAND_IN then standIns = standIns + 1 end
            end
        end, { STORY_BOSS_FIGHT, STORY_BOSS_WIN })
        -- Round 118: the battle groups' table has no row names to find a group by, and a walk of
        -- it is slow, so it is written at the map's first pass and then every `every` passes,
        -- in case the game loaded it again.
        local W = G.STORY_BOSS_GROUP_WRITE
        if W.map ~= mapId then W.calls = 0 end
        if W.calls % W.every == 0 then
            EachGroupRow(boss.group, function(row)
                BossTestWriteGroup(row, STORY_BOSS_WIN)
                groupRows = groupRows + 1
            end)
            W.rows = groupRows
        end
        W.map, W.calls, groupRows = mapId, W.calls + 1, W.rows
    end
    local triggers, transitions, npcs, walks, woken = 0, 0, 0, "", 0
    if boss.kind == "trigger" then
        local ok, all = pcall(FindAllOf, "BP_MapGimmick_EventTrigger_C")
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                local match = false
                pcall(function()
                    local ev = ObjText(a.m_EventList[1].EventId)
                    match = (ev == boss.event or ev == STORY_BOSS_FIGHT)
                end)
                if match then
                    step("story boss: trigger m_EventList[1] -> " .. fightCond .. " / " .. STORY_BOSS_FIGHT)
                    pcall(function()
                        a.m_EventList[1].Condition = fightCond
                        a.m_EventList[1].EventId = FName(STORY_BOSS_FIGHT)
                    end)
                    step("story boss: trigger m_FlagCondition and VisibleCondition -> " .. cond)
                    pcall(function()
                        a.m_FlagCondition = cond
                        a.VisibleCondition = cond
                    end)
                    step("story boss: trigger SetGimmickCondition, SetVisible, SetActorEnableCollision")
                    pcall(function() a:SetGimmickCondition(won and 1 or 0, false) end)
                    pcall(function() a:SetVisible(not won) end)
                    pcall(function() a:SetActorEnableCollision(not won) end)
                    triggers = triggers + 1
                end
            end
        end
    elseif boss.kind == "transition" then
        local ok, all = pcall(FindAllOf, "BP_MapTransitionTrigger_C")
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                local d, match = nil, false
                pcall(function()
                    d = a.mTransitionDataList[1]
                    local ev = #d.EventList >= 1 and ObjText(d.EventList[1].EventId) or nil
                    match = (Int(d.pointId) == boss.point or ev == boss.event or ev == STORY_BOSS_FIGHT)
                end)
                if match and d and won and boss.reopen then
                    step("story boss: transition mTransitionDataList[1] -> a door again (won), fight row only on " .. cond)
                    pcall(function()
                        d.FlagCondition = ""
                        d.isEventOnly = false
                        d.EventList[1].Condition = cond
                        d.EventList[1].EventId = FName(STORY_BOSS_FIGHT)
                    end)
                    transitions = transitions + 1
                elseif match and d then
                    step("story boss: transition mTransitionDataList[1] -> " .. fightCond .. ", isEventOnly true, " .. STORY_BOSS_FIGHT)
                    pcall(function()
                        d.FlagCondition = fightCond
                        d.isEventOnly = true
                        d.EventList[1].Condition = ""
                        d.EventList[1].EventId = FName(STORY_BOSS_FIGHT)
                    end)
                    transitions = transitions + 1
                end
            end
        end
    end
    if boss.unit then
        local ok, all = pcall(FindAllOf, "BP_MapUnit_NPC_C")
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                local uid
                pcall(function() uid = Int(a.m_MapUnitId) end)
                if uid == boss.unit then
                    step("story boss: npc " .. boss.unit .. " m_VisiblFlagCondition -> " .. cond)
                    pcall(function() a.m_VisiblFlagCondition = cond end)
                    if boss.kind == "npc" then
                        step("story boss: npc " .. boss.unit .. " m_EventSettings.EventList[1] -> " .. fightCond .. " / " .. STORY_BOSS_FIGHT)
                        pcall(function()
                            local entry = a.m_EventSettings.EventList[1]
                            entry.Condition = fightCond
                            entry.EventList[1].Condition = ""
                            entry.EventList[1].EventId = FName(STORY_BOSS_FIGHT)
                        end)
                    end
                    step("story boss: npc " .. boss.unit .. " SetVisible, SetActorHiddenInGame, SetActorEnableCollision")
                    pcall(function() a:SetVisible(not won) end)
                    pcall(function() a:SetActorHiddenInGame(won) end)
                    pcall(function() a:SetActorEnableCollision(not won) end)
                    npcs = npcs + 1
                end
            end
        end
    end
    if boss.kind == "list" then
        local ok, all = pcall(FindAllOf, boss.class)
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                pcall(function()
                    local list = a[boss.field]
                    for i = 1, #list do
                        local ev = ObjText(list[i].EventId)
                        if ev == boss.event or ev == STORY_BOSS_FIGHT then
                            step("story boss: " .. boss.class .. " " .. boss.field .. "[" .. i .. "] -> " .. fightCond .. " / " .. STORY_BOSS_FIGHT)
                            list[i].Condition = fightCond
                            list[i].EventId = FName(STORY_BOSS_FIGHT)
                            if boss.size and not won then
                                step(string.format("story boss: SetActorScale3D %s %s %s", boss.size.X, boss.size.Y, boss.size.Z))
                                a:SetActorScale3D(boss.size)
                            end
                            triggers = triggers + 1
                            -- The game judges a zone once, at the map's load, from the rows as
                            -- they were then, and turns it off (m_GimmickCondition 1). It looks
                            -- again only when a flag changes in the game's own way, such as a
                            -- shiny taken, so the first pass did nothing (round 76). Doors are
                            -- left alone: they have always worked.
                            if not won and boss.class:find("EventTrigger", 1, true) and a.m_GimmickCondition ~= 0 then
                                step("story boss: SetGimmickCondition 0 (active)")
                                a:SetGimmickCondition(0, false)
                                woken = woken + 1
                            end
                            if boss.nowalk then
                                step("story boss: " .. boss.field .. "[" .. i .. "].MoveInfo.MoveTargetPoint -> none")
                                pcall(function() list[i].MoveInfo.MoveTargetPoint = nil end)
                                local target = list[i].MoveInfo.MoveTargetPoint
                                walks = "; walk " .. ((target == nil or not target:IsValid()) and "off" or "kept")
                            end
                        end
                    end
                end)
            end
        end
    end
    local detail = string.format("map %d group %d flag %d (won %s): %d fight, %d win (%d with the stand-in), %d group rows; %d triggers, %d transitions, %d npcs%s%s",
        mapId, boss.group, boss.flag, tostring(won), fightRows, winRows, standIns, groupRows, triggers, transitions, npcs, walks,
        woken > 0 and ("; " .. woken .. " zones turned on") or "")
    return true, detail
end

-- Grant Siren's esper summon ability directly to both Finas (units 1003 and 1006: command ability
-- 6 + ability 430980), since flag 90 alone does not unlock the summon command. Idempotent.
local SIREN_UNITS, SIREN_ABILITIES, SIREN_COMMANDS = { 1003, 1006 }, { 6, 430980 }, { 6 }
local function AppendOnce(list, value)
    for i = 1, #list do
        if Int(list[i]) == value then return end
    end
    local n = #list
    local _ = list[n + 1]    -- reading one past the end grows a UE4SS TArray
    list[n + 1] = value
end
local function GrantSiren(sd)
    local ok = true
    for _, unit in ipairs(SIREN_UNITS) do
        local entry = UnitEntry(sd, unit)
        ok = ok and entry ~= nil and pcall(function()
            for _, id in ipairs(SIREN_ABILITIES) do AppendOnce(entry.activeSkillIdList, id) end
            for _, id in ipairs(SIREN_COMMANDS) do AppendOnce(entry.commandSkillIdList, id) end
        end)
    end
    return ok, "Siren: summon abilities on both Finas"
end

-- Guard the moogle's Vision Enhancement shopkeeper talk rows: when no vision is owned, convert the
-- three Blueprint rows to empty Sequence rows (no-ops) so the player cannot enter and get stuck.
-- Writes only on state change; pass `force` after save loads in case tables reloaded. `guard` false
-- (a save not linked to the seed) puts the game's rows back.
local SHOP_ROWS = { VisionUpgrade = true, VisionUpgrade_Main = true, FEV_Town_10Cry_41_720_01 = true }
local shopBlocked = nil
function G.VisionShopGuard(force, guard)
    local sd = G.SaveData()
    if not sd then return nil end
    local owned
    if not pcall(function() owned = #sd.visionList end) or not owned then return nil end
    local block = guard and owned == 0
    if not guard and not shopBlocked then return nil end
    if block == shopBlocked and not force then return nil end
    local written = 0
    for _, dt in ipairs(TableFamily(Find(SHOP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(name, row)
                if SHOP_ROWS[ObjText(name)] then
                    row.EventType = block and EVENT_SEQUENCE or EVENT_BLUEPRINT
                    written = written + 1
                end
            end)
        end)
    end
    shopBlocked = block
    return block, written
end

-- The loaded save's airship fields as text, for the log.
function G.AirshipState()
    local sd = G.SaveData()
    if not sd then return "no save loaded" end
    local text
    local ok = pcall(function()
        local m = sd.Map
        text = string.format("placed %s, riding %s, inside %s, at (%.0f, %.0f, %.0f), direction %s, island %s",
            tostring(m.IsAlreadySpawnAirship), tostring(m.IsRidingAirShip), tostring(m.IsIntoTheAirShip),
            m.airShipLocation.X, m.airShipLocation.Y, m.airShipLocation.Z,
            tostring(Int(m.airShipDirection)), tostring(Int(m.airShipIslandType)))
    end)
    return ok and text or "could not read the airship fields"
end

-- The loaded save's chat state as text, for the log.
function G.ChatState()
    local sd = G.SaveData()
    if not sd then return "no save loaded" end
    local rows, released, played, queue = 0, 0, 0, {}
    local ok = pcall(function()
        sd.chat.DataMap:ForEach(function(_, v)
            local row = v:get()
            rows = rows + 1
            if row.IsReleased then released = released + 1 end
            if row.IsAlreadyPlayed then played = played + 1 end
        end)
        local list = sd.chat.NoticeQueue
        for i = 1, #list do queue[i] = ObjText(list[i]) end
    end)
    if not ok then return "could not read the chat data" end
    local latest = "?"
    pcall(function() latest = ObjText(sd.chat.LatestNotice) end)
    return string.format("%d rows, %d released, %d played; notices [%s], latest %s", rows, released, played, table.concat(queue, ", "), latest)
end

-- Applies the skip to the loaded save. Saves nothing. Returns ok and a list of report lines,
-- one per step ("ok ..." or "FAIL ..."). ok is false when any step failed.
-- opts.inventory = false leaves the inventory alone. Its changes are relative, so that an
-- Archipelago item granted before the skip with the same id as a starter item is kept, and they
-- must be made once per save. Every other step sets an absolute value and can run again.
-- opts.openStart = true writes the open world start (opts.arrival, else G.OPEN_START) in place
-- of story 1030 and the Earth Shrine.
function G.SkipPrologue(opts)
    local doInventory = not (opts and opts.inventory == false)
    local open = (opts and opts.openStart) and (opts.arrival or G.OPEN_START) or nil
    local storyTo = open and open.story or G.SKIP_STORY
    local a = open or G.SKIP_ARRIVAL
    -- Starting party: Rain and Lasswell by default, or the seed's starting party. Non-starting
    -- story flags are unused once story events are skipped.
    local party = (opts and opts.party) or SKIP_PARTY
    local isStarter = {}
    for _, id in ipairs(party) do isStarter[id] = true end
    local report, failed = {}, false
    local function step(ok, what)
        report[#report + 1] = (ok and "ok   " or "FAIL ") .. what
        if not ok then failed = true end
    end
    local sd = G.SaveData()
    if not sd then return false, { "FAIL no save loaded" } end

    step(WriteStory(sd, storyTo))

    local found, bad = SetFlags(sd, SKIP_FLAGS_ON, SKIP_FLAGS_OFF)
    step(found and #bad == 0, "event flags: " .. #SKIP_FLAGS_ON .. " on, " .. #SKIP_FLAGS_OFF .. " off"
        .. (#bad > 0 and (" (failed: " .. table.concat(bad, " ") .. ")") or ""))
    -- Whether the game's own {flag:N} agrees with the array index, for the record.
    local libSays = G.GetFlag(SKIP_FLAGS_ON[1])
    report[#report + 1] = "     the game reads flag " .. SKIP_FLAGS_ON[1] .. " as " .. tostring(libSays)
        .. " (should be true if its numbering matches the array's)"

    -- The party. Reading one past the end grows the array (see UnlockVision).
    local okParty = pcall(function()
        local list = sd.Party.partyList
        list:Empty()
        for i, id in ipairs(party) do
            if #list < i then local _ = list[i] end
            list[i] = id
        end
    end)
    local partyNow = {}
    pcall(function()
        local list = sd.Party.partyList
        for i = 1, #list do partyNow[#partyNow + 1] = tostring(Int(list[i])) end
    end)
    step(okParty and table.concat(partyNow, ",") == table.concat(party, ","), "party -> [" .. table.concat(partyNow, ", ") .. "]")

    -- Join status: the starters in (0); Archwitch Fina (the prologue's Fina) out (2) unless she is one,
    -- and any other non-starter back to NotJoin (1) so a re-skip after a session change leaves no old starter in.
    local rain, fina = UnitEntry(sd, 1001), UnitEntry(sd, ARCHWITCH_FINA)
    local okJoin, joined = rain ~= nil and fina ~= nil, {}
    for _, id in ipairs(party) do
        local entry = UnitEntry(sd, id)
        okJoin = entry ~= nil and Put(entry, "JoinStatus", 0) and Put(entry, "IsUsable", true) and okJoin
        joined[#joined + 1] = UNIT_NAMES[id] or tostring(id)
    end
    for id = 1001, 1008 do
        if not isStarter[id] and id ~= ARCHWITCH_FINA then
            local entry = UnitEntry(sd, id)
            if entry then okJoin = Put(entry, "JoinStatus", 1) and okJoin end
        end
    end
    local joinLine = "join status: " .. table.concat(joined, ", ") .. " 0"
    if not isStarter[ARCHWITCH_FINA] then
        okJoin = fina ~= nil and Put(fina, "JoinStatus", 2) and okJoin
        joinLine = joinLine .. "; Archwitch Fina 2"
    end
    step(okJoin, joinLine)

    -- Rain's baseParameterList[5] (0-based) goes 0 -> 3 in the prologue. Its meaning is unknown.
    local okBase = false
    if rain then pcall(function() okBase = Put(rain.baseParameterList, 6, 3) end) end
    step(okBase, "Rain baseParameterList[5] -> 3")

    -- Archwitch Fina back to level 1, her own weapon, no armor, accessories or skills.
    local okFina = fina ~= nil
    if fina then
        for _, kv in ipairs({ { "Experience", 0 }, { "HitPoint", 200 }, { "MagicPoint", 70 },
                              { "EquipWeaponId", 10600 }, { "EquipArmorId", -1 } }) do
            okFina = Put(fina, kv[1], kv[2]) and okFina
        end
        for _, field in ipairs({ "EquipAccessoryIdList", "activeSkillIdList" }) do
            local n
            pcall(function() fina[field]:Empty() end)
            pcall(function() n = #fina[field] end)
            okFina = (n == 0) and okFina
        end
        -- As a starter she needs her own first ability, as the others start with theirs.
        if isStarter[ARCHWITCH_FINA] then
            okFina = pcall(function()
                local _ = fina.activeSkillIdList[1]
                fina.activeSkillIdList[1] = ARCHWITCH_FIRST_SKILL
            end) and okFina
        end
    end
    step(okFina, "Archwitch Fina reset: Experience 0, HP 200, MP 70, weapon 10600, no armor, accessories or skills")

    -- Inventory, through the game's call: equipped gear is counted in the bag.
    if doInventory then
        local inv = Lib("CPP_BFL_SaveDataInventory")
        local invBad = {}
        local changes = {}
        for _, id in ipairs(party) do
            for _, gear in ipairs(STARTER_GEAR[id] or {}) do changes[#changes + 1] = { gear, 1 } end
        end
        for _, gear in ipairs(SKIP_GEAR_OUT) do changes[#changes + 1] = { gear, -1 } end
        for _, e in ipairs(changes) do
            local before = inv and Held(inv, e[1])
            local want = math.max(0, (before or 0) + e[2])
            local okSet = before ~= nil and pcall(function() inv:SetInventoryItem(e[1], want) end)
            local held = inv and Held(inv, e[1])
            if not okSet or held ~= want then
                invBad[#invBad + 1] = e[1] .. " (" .. tostring(before) .. " -> " .. tostring(held) .. ")"
            end
        end
        step(inv ~= nil and #invBad == 0, "inventory: starter gear in, Fina's prologue gear out"
            .. (#invBad > 0 and (" (wrong: " .. table.concat(invBad, ", ") .. ")") or ""))
    else
        report[#report + 1] = "     inventory left alone (already changed for this save)"
    end

    -- The guest unit's HP and MP, and the battles-won counter.
    step(Put(sd.unitGuest, "HitPoint", 9999) and Put(sd.unitGuest, "MagicPoint", 9999), "guest unit HP, MP -> 9999")
    step(Put(sd.Player, "WinNum", 3), "battles won -> 3")

    -- Maps passed through: known and visited.
    local perMap = Lib("CPP_BFL_SaveData_PerMap")
    local mapBad = {}
    local visitMaps = open and (open.parked and G.OPEN_START_MAPS or G.OPEN_START_MAPS_AIRSHIP) or SKIP_MAPS
    for _, m in ipairs(visitMaps) do
        local okAdd = perMap and pcall(function() perMap:AddKnownMap(m); perMap:AddVisitedMap(m) end)
        local visited
        pcall(function() visited = perMap:IsVisited(m) end)
        if not okAdd or visited ~= true then mapBad[#mapBad + 1] = tostring(m) end
    end
    step(perMap ~= nil and #mapBad == 0, "maps known and visited: " .. table.concat(visitMaps, ", ")
        .. (#mapBad > 0 and (" (failed: " .. table.concat(mapBad, ", ") .. ")") or ""))

    -- Where the reload puts the player: in front of the Earth Shrine, or at the Crystal Tower.
    step(WriteArrival(sd, a))

    if opts and opts.openStart then
        step(G.MarkChatsPlayed(sd))
        step(EnableOpenWorld(sd))
        step(GrantSiren(sd))
        -- Reset every unit to level 1; units joining later scale to the party's current average level.
        local bad = {}
        for _, id in ipairs(ALL_PARTY_MEMBERS) do
            local okLevel, why = G.SetUnitLevel(id, 1)
            if not okLevel then bad[#bad + 1] = why end
        end
        step(#bad == 0, "party levels: all " .. #ALL_PARTY_MEMBERS .. " at level 1"
            .. (#bad > 0 and (" (failed: " .. table.concat(bad, "; ") .. ")") or ""))
    end

    return not failed, report
end

-- Applies the open-world start (G.OPEN_START: story 7090 and Crystal Tower arrival) to a save that
-- already ran the prologue skip. Does not save to disk. Returns ok and report lines.
function G.OpenStart()
    local sd = G.SaveData()
    if not sd then return false, { "FAIL no save loaded" } end
    local okStory, story = WriteStory(sd, G.OPEN_START.story)
    local okMap, arrival = WriteArrival(sd, G.OPEN_START)
    local okChats, chats = G.MarkChatsPlayed(sd)
    local okFlags, flags = EnableOpenWorld(sd)
    return okStory and okMap and okChats and okFlags, { (okStory and "ok   " or "FAIL ") .. story,
        (okMap and "ok   " or "FAIL ") .. arrival, (okChats and "ok   " or "FAIL ") .. chats,
        (okFlags and "ok   " or "FAIL ") .. flags }
end

-- Dump player controller input flags and input manager subsystem state (IsEnableInput, mode, and
-- mapping context stack) for diagnosing input locks.
function G.InputState()
    local pc = PlayerController()
    if not pc then return "no PlayerController" end
    local pawn, move, look = "?", "?", "?"
    pcall(function() pawn = pc:K2_GetPawn():GetClass():GetFName():ToString() end)
    pcall(function() move = tostring(pc:IsMoveInputIgnored()) end)
    pcall(function() look = tostring(pc:IsLookInputIgnored()) end)
    local line = string.format("controller %s, pawn %s, move input ignored %s, look input ignored %s",
        pc:GetFName():ToString(), pawn, move, look)
    local mgr = Live("CPP_InputManager")
    if not mgr then return line .. "; no CPP_InputManager" end
    local enabled, mode, stack = "?", "?", "?"
    pcall(function() enabled = tostring(mgr:IsEnableInput()) end)
    pcall(function() mode = ObjText(mgr:GetCurrentInputModeDebugString()) end)
    pcall(function()
        local list, names = mgr:GetAllIMCStackList(), {}
        for i = 1, #list do names[#names + 1] = ObjText(list[i]) end
        stack = #names .. " [" .. table.concat(names, ", ") .. "]"
    end)
    return string.format("%s; input manager: enabled %s, mode %s, mapping contexts %s", line, enabled, mode, stack)
end

-- Round 115: the player walked while the new start moved them, and froze after a second move.
-- The engine's move-input lock is a counter on the controller: each true needs one false.
-- Returns IsMoveInputIgnored after the call, or nil and why.
function G.HoldMove(on)
    local pc = PlayerController()
    if not pc then return nil, "no PlayerController" end
    local ok, err = pcall(function() pc:SetIgnoreMoveInput(on) end)
    if not ok then return nil, tostring(err) end
    local ignored
    pcall(function() ignored = pc:IsMoveInputIgnored() end)
    return ignored
end

-- Resets for a locked game, one at a time: the game's input manager first (EnableInput, then
-- register its current mapping context again), then the engine's own. step(what) runs before
-- each (it logs, so a crash names the call). Returns the steps that raised.
function G.InputFix(step)
    local pc = PlayerController()
    if not pc then return { "no PlayerController" } end
    local failed = {}
    local function try(what, fn)
        step(what)
        local ok, err = pcall(fn)
        if not ok then failed[#failed + 1] = what .. ": " .. tostring(err) end
    end
    local mgr = Live("CPP_InputManager")
    if mgr then
        try("CPP_InputManager:EnableInput", function() mgr:EnableInput() end)
        try("CPP_InputManager:ReregistrationCurrentMappingContext", function() mgr:ReregistrationCurrentMappingContext() end)
    end
    try("ResetIgnoreInputFlags", function() pc:ResetIgnoreInputFlags() end)
    try("EnableInput", function() pc:EnableInput(pc) end)
    try("SetInputMode_GameOnly", function()
        Find("/Script/UMG.Default__WidgetBlueprintLibrary"):SetInputMode_GameOnly(pc, false)
    end)
    return failed
end

-- Log the first vision entry and its synchro keys (useful for checking keys after future patches).
function G.VisionKeys()
    local sd = G.SaveData()
    if not sd then return "no save loaded" end
    local list
    if not pcall(function() list = sd.visionList end) or not list then return "visionList unreadable" end
    if #list == 0 then return "visionList is empty" end
    local keys, id = {}, "?"
    pcall(function() id = tostring(Int(list[1].ID)) end)
    pcall(function()
        list[1].synchroPoints:ForEach(function(k) keys[#keys + 1] = tostring(Int(k:get())) end)
    end)
    return string.format("%d visions; the first is %s, its synchro keys [%s]", #list, id, table.concat(keys, ", "))
end

-- Writes the loaded save to a slot and starts the field from that slot, as FFRSLib's
-- ffrs_travel does. `map` is the map the skip wrote (default the Earth Shrine's). Returns ok
-- and a detail.
function G.SaveAndReload(slot, map)
    map = map or G.SKIP_ARRIVAL.map
    local lib = Lib("CPP_BFL_SaveData")
    if not (lib and lib.SaveGameData) then return false, "CPP_BFL_SaveData not found" end
    local ok, err = pcall(function() lib:SaveGameData(slot) end)
    if not ok then return false, "SaveGameData(" .. slot .. ") raised: " .. tostring(err) end
    -- An autosave writes the player's real position over the save's map. If SaveGameData does
    -- the same, the reload would land on the prologue map again, so say so.
    local mapNow, flag1 = G.MapId(), G.GetFlag(1)
    local kept = "map " .. tostring(mapNow) .. ", flag 1 " .. tostring(flag1)
    if mapNow ~= map then
        return false, "saved to slot " .. slot .. ", but the save's map is " .. tostring(mapNow)
            .. " after saving, not " .. map .. " (SaveGameData wrote the real position). Not reloading"
    end
    local mgr = Live("CPP_MapManager")
    if not mgr then return false, "saved to slot " .. slot .. " (" .. kept .. "), but no map manager to reload with: load the slot by hand" end
    if not pcall(function() mgr:MapTestStartByChoiceSlotLoadSaveData(slot) end) then
        return false, "saved to slot " .. slot .. " (" .. kept .. "), but the reload did not start: load the slot by hand"
    end
    return true, "saved to slot " .. slot .. " (" .. kept .. "), reloading"
end

-- -------------------------------------------------------------------------------------------
-- The new start: an Archipelago new game that begins at the open world start
-- -------------------------------------------------------------------------------------------
-- Round 109 (a tester's log): with autosave off in the game's Options the new game never saved,
-- so the prologue skip, which waits for the first autosave, never ran, and the seed's save
-- played the prologue and chapter 1. The new start needs no save and no reload. Before the new
-- game begins, the title's pre-hook points the game's start map (CPP_GameSettings's
-- GameStartSettings, 10040 in DefaultProject.ini) at the arrival, and writes the arrival's story,
-- party and flags into DT_InitGameSaveData's NewGame row, which the game builds a new save from.
-- The opening is map 10040's startup event ({progress:0}==1000 -> C01_001_01), so it never
-- plays. Both are put back once the new game is in, so a plain New Game stays vanilla.
G.NEW_START = {
    settings = "/Script/mucha.Default__CPP_GameSettings",
    table = "/Game/Datatable/SaveData/DT_InitGameSaveData.DT_InitGameSaveData",
    row = "NewGame",
    -- Round 110: a new game's save holds ATC11 ("Thoughtful Resolve") released and waiting, as a
    -- vanilla one does. It plays once Lasswell, its RequiredUnitList, is in the party, which a new
    -- start's party is from the first frame. Until NewStartFinish marks every chat played, each
    -- chat waits for a unit who is not in the party.
    chats = "/Game/Datatable/Chat/Event/CDT_ChatEventData.CDT_ChatEventData",
    -- Round 109: the new game stands where the world map puts a new game (south of the Earth
    -- Shrine), so the player and the airship are moved to the arrival. These are the airship's
    -- classes; the first is the actor seen as the pawn while riding (round 37).
    -- Round 118: the parked airship is a gimmick, CPP_MapGimmick_AirShip
    -- (BP_MapGimmick_Vehicle_AirShipe_C).
    airships = { "BP_MapUnitAirShip_C", "CPP_MapUnit_AirShip", "CPP_MapGimmick_AirShip" },
    -- Round 118 (the user): a seed that starts with the airship had none at the start until a
    -- map change. The game places it at the first map load from the save, and the save is parked
    -- only after that load. With no placement in the save, the game's first one is at
    -- DT_MapAirShip's initSpawnPointId (9000, no point), so the start points it at the arrival's
    -- landing point for the new game's first load, and puts it back after.
    spawnTable = "/Game/Datatable/Asset/Map/DT_MapAirShip.DT_MapAirShip",
    -- Map 10040 at story 5270 or later plays C05_536_02 until flag 553 is on. If the game kept
    -- its own start map, this keeps that scene from playing.
    flags = { 553 },
    near = 300,    -- a player this close to the arrival is not moved
    -- Round 115: move input is held from the save's arrival until the player stands at the
    -- arrival, and given back after this many ticks at the latest.
    holdTicks = 20,
    saved = nil,   -- what NewStartPrepare changed, for NewStartRestore
}
do
local NS = G.NEW_START

local function Ints(list)
    local out = {}
    pcall(function() for i = 1, #list do out[i] = Int(list[i]) end end)
    return out
end

local function SetInts(list, values)
    return pcall(function()
        list:Empty()
        for i, v in ipairs(values) do
            if #list < i then local _ = list[i] end
            list[i] = v
        end
    end)
end

-- The row's Progress is a map of progress index to value; the story counter is index 0.
local function StoryOf(progress)
    local found
    pcall(function()
        progress:ForEach(function(k, v) if Int(k:get()) == 0 then found = Int(v:get()) end end)
    end)
    return found
end

local function SetStory(progress, n)
    local done = false
    pcall(function()
        progress:ForEach(function(k, v) if Int(k:get()) == 0 then v:set(n); done = true end end)
    end)
    if not done then pcall(function() progress:Add(0, n) end) end
    return StoryOf(progress) == n
end

local function ReadInitRow(row)
    local r = { party = {}, flags = {}, units = {} }
    r.story = StoryOf(row.Progress)
    pcall(function() r.party = Ints(row.Party.partyList) end)
    pcall(function() r.flags = Ints(row.OnFlagList) end)
    pcall(function()
        local list = row.unitDataList
        for i = 1, #list do
            local u = list[i]
            r.units[i] = { id = Int(u.UnitId), level = Int(u.Level), join = Int(u.JoinStatus),
                           weapon = Int(u.EquipWeaponId), armor = Int(u.EquipArmorId),
                           accessories = Ints(u.EquipAccessoryIdList), skills = Ints(u.SkillList) }
        end
    end)
    return r
end

local function WriteInitRow(row, r, step)
    local ok = true
    if r.story then
        step("NewGame row: story " .. r.story)
        ok = SetStory(row.Progress, r.story) and ok
    end
    step("NewGame row: party " .. table.concat(r.party, ","))
    ok = SetInts(row.Party.partyList, r.party) and ok
    step("NewGame row: " .. #r.flags .. " flags")
    ok = SetInts(row.OnFlagList, r.flags) and ok
    for i, u in ipairs(r.units) do
        step("NewGame row: unit " .. tostring(u.id))
        ok = pcall(function()
            local e = row.unitDataList[i]
            e.Level, e.JoinStatus, e.EquipWeaponId, e.EquipArmorId = u.level, u.join, u.weapon, u.armor
            if not SetInts(e.EquipAccessoryIdList, u.accessories) then error("accessories") end
            if not SetInts(e.SkillList, u.skills) then error("skills") end
        end) and ok
    end
    return ok
end

local function DescribeRow(r)
    local units = {}
    for _, u in ipairs(r.units) do
        units[#units + 1] = string.format("%s:%s:%s", tostring(u.id), tostring(u.level), tostring(u.join))
    end
    return string.format("story %s, party [%s], %d flags, units (id:level:join) %s", tostring(r.story),
        table.concat(r.party, ","), #r.flags, table.concat(units, " "))
end

-- The NewGame row the arrival needs: its story, the party joined at level 1 and everyone else not
-- joined, and the flags the prologue skip writes. Archwitch Fina gets what SkipPrologue leaves her.
local function NewStartRow(r, a, party)
    local isStarter, flags, have = {}, {}, {}
    for _, id in ipairs(party) do isStarter[id] = true end
    for _, list in ipairs({ r.flags, SKIP_FLAGS_ON, OPEN_WORLD_FEATURES, OPEN_WORLD_TUTORIALS, a.flags or {}, NS.flags }) do
        for _, f in ipairs(list) do
            if not have[f] then have[f], flags[#flags + 1] = true, f end
        end
    end
    local units = {}
    for i, u in ipairs(r.units) do
        units[i] = { id = u.id, level = 1, join = isStarter[u.id] and 0 or 1, weapon = u.weapon, armor = u.armor,
                     accessories = u.accessories, skills = u.skills }
        if u.id == ARCHWITCH_FINA then
            units[i].weapon, units[i].armor, units[i].accessories, units[i].skills = 10600, -1, {}, { ARCHWITCH_FIRST_SKILL }
        end
    end
    return { story = a.story, party = party, flags = flags, units = units }
end

local function EachNewGameRow(dt, fn)
    pcall(function()
        dt:ForEachRow(function(name, row) if RowName(name) == NS.row then fn(row) end end)
    end)
end

-- Points the next new game at opts.arrival with opts.party (default Rain and Lasswell).
-- opts.step(what) runs before each write. Returns ok and report lines. A failure leaves the
-- game's data as it was found.
function G.NewStartPrepare(opts)
    local a, step = opts.arrival, opts.step or function() end
    local party = opts.party or SKIP_PARTY
    G.NewStartRestore(step)
    local report, ok = {}, true
    local function line(good, what)
        report[#report + 1] = (good and "ok   " or "FAIL ") .. what
        ok = ok and good
    end
    local saved = { tables = {} }
    NS.saved = saved
    local cdo = Find(NS.settings)
    local was
    if cdo then pcall(function() was = Int(cdo.GameStartSettings.TransitionMapId) end) end
    if not was then
        line(false, "start map: " .. NS.settings .. " not readable")
        G.NewStartRestore(step)
        return false, report
    end
    step("GameStartSettings.TransitionMapId " .. was .. " -> " .. a.map)
    saved.map = was
    pcall(function() cdo.GameStartSettings.TransitionMapId = a.map end)
    local now
    pcall(function() now = Int(cdo.GameStartSettings.TransitionMapId) end)
    line(now == a.map, "start map " .. was .. " -> " .. tostring(now))
    step("load " .. NS.table)
    local rows = 0
    for _, dt in ipairs(TableFamily(G.LoadObject(NS.table))) do
        EachNewGameRow(dt, function(row)
            rows = rows + 1
            local before = ReadInitRow(row)
            local want = NewStartRow(before, a, party)
            saved.tables[#saved.tables + 1] = { path = G.PathOf(dt), row = before }
            local wrote = WriteInitRow(row, want, step)
            local after = DescribeRow(ReadInitRow(row))
            line(wrote and after == DescribeRow(want), "NewGame row in " .. tostring(G.PathOf(dt)) .. ": " .. after)
        end)
    end
    line(rows > 0, "NewGame rows written: " .. rows)
    local isChat, inParty, away = {}, {}, nil
    for _, id in ipairs(G.CHAT_IDS) do isChat[id] = true end
    for _, id in ipairs(party) do inParty[id] = true end
    for _, id in ipairs(ALL_PARTY_MEMBERS) do
        if not away and not inParty[id] then away = id end
    end
    saved.chats = {}
    local held = 0
    step("chats wait for unit " .. tostring(away))
    for _, dt in ipairs(TableFamily(G.LoadObject(NS.chats))) do
        local lists = {}
        pcall(function()
            dt:ForEachRow(function(name, row)
                local key = RowName(name)
                if isChat[key] then
                    lists[key] = Ints(row.RequiredUnitList)
                    if SetInts(row.RequiredUnitList, { away }) then held = held + 1 end
                end
            end)
        end)
        saved.chats[#saved.chats + 1] = { path = G.PathOf(dt), lists = lists }
    end
    -- Not a failure of the start: at worst a chat plays at the first map.
    report[#report + 1] = (held > 0 and "ok   " or "FAIL ") .. "chats wait for unit " .. tostring(away) .. ": " .. held .. " rows"
    if opts.airship and a.landing then
        -- Not a failure either: at worst the airship comes at the next map change, as before.
        local dt = G.LoadObject(NS.spawnTable)
        local was, now
        pcall(function()
            dt:ForEachRow(function(_, row)
                was = was or Int(row.initSpawnPointId)
                row.initSpawnPointId = a.landing
                now = Int(row.initSpawnPointId)
            end)
        end)
        if was then saved.spawnPoint = { path = G.PathOf(dt), id = was } end
        report[#report + 1] = (now == a.landing and "ok   " or "FAIL ") .. "airship's first place: landing point "
            .. tostring(was) .. " -> " .. tostring(now)
    end
    if not ok then G.NewStartRestore(step) end
    return ok, report
end

-- Puts back what NewStartPrepare changed. Returns a line, or nil when nothing was changed.
function G.NewStartRestore(step)
    local saved = NS.saved
    if not saved then return nil end
    step = step or function() end
    NS.saved = nil
    local parts = {}
    if saved.map then
        step("GameStartSettings.TransitionMapId -> " .. saved.map)
        local cdo = Find(NS.settings)
        local okMap = cdo ~= nil and pcall(function() cdo.GameStartSettings.TransitionMapId = saved.map end)
        parts[#parts + 1] = "start map " .. saved.map .. (okMap and "" or " (failed)")
    end
    for _, t in ipairs(saved.tables) do
        local dt = t.path and Find(t.path)
        local done = false
        if dt then EachNewGameRow(dt, function(row) done = WriteInitRow(row, t.row, step) end) end
        parts[#parts + 1] = "NewGame row in " .. tostring(t.path) .. (done and "" or " (not found or failed)")
    end
    local chatRows = 0
    for _, t in ipairs(saved.chats or {}) do
        local dt = t.path and Find(t.path)
        if dt then
            step("chat rows' units in " .. t.path)
            pcall(function()
                dt:ForEachRow(function(name, row)
                    local list = t.lists[RowName(name)]
                    if list and SetInts(row.RequiredUnitList, list) then chatRows = chatRows + 1 end
                end)
            end)
        end
    end
    if saved.chats then parts[#parts + 1] = chatRows .. " chat rows" end
    if saved.spawnPoint then
        local dt = Find(saved.spawnPoint.path)
        local back = dt ~= nil and pcall(function()
            dt:ForEachRow(function(_, row) row.initSpawnPointId = saved.spawnPoint.id end)
        end)
        parts[#parts + 1] = "airship's first place " .. saved.spawnPoint.id .. (back and "" or " (failed)")
    end
    return table.concat(parts, "; ")
end

-- The bag of a new start's save. A vanilla new game holds Archwitch Fina's gear because she is
-- joined in the NewGame row, so the game seems to put a joined unit's gear in the bag. Each
-- starter's piece is topped up to what the party wears, and her prologue gear goes. Nothing has
-- been given to this save yet, so the counts can be set outright.
local function NewStartBag(party)
    local inv = Lib("CPP_BFL_SaveDataInventory")
    if not inv then return false, "inventory: no inventory library" end
    local need, ids = {}, {}
    for _, id in ipairs(party) do
        for _, gear in ipairs(STARTER_GEAR[id] or {}) do need[gear] = (need[gear] or 0) + 1 end
    end
    for gear in pairs(need) do ids[#ids + 1] = gear end
    for _, gear in ipairs(SKIP_GEAR_OUT) do
        if not need[gear] then need[gear], ids[#ids + 1] = 0, gear end
    end
    table.sort(ids)
    local parts, ok = {}, true
    for _, gear in ipairs(ids) do
        local before = Held(inv, gear)
        local want = need[gear] == 0 and 0 or math.max(before or 0, need[gear])
        if before ~= want then pcall(function() inv:SetInventoryItem(gear, want) end) end
        local after = Held(inv, gear)
        ok = ok and after == want
        parts[#parts + 1] = gear .. " " .. tostring(before) .. (before ~= after and ("->" .. tostring(after)) or "")
    end
    return ok, "inventory (held before->after): " .. table.concat(parts, ", ")
end

-- Round 109: Rain started with his armor and accessory in the bag, not on. Each starter wears
-- what the NewGame row (put back by then) gives them. Archwitch Fina's is SkipPrologue's.
local function NewStartEquip(sd, party)
    local row
    for _, dt in ipairs(TableFamily(Find(NS.table))) do
        EachNewGameRow(dt, function(r) row = row or ReadInitRow(r) end)
    end
    if not row then return false, "gear: no NewGame row" end
    local wear, parts, ok = {}, {}, true
    for _, u in ipairs(row.units) do wear[u.id] = u end
    for _, id in ipairs(party) do
        local u, entry = wear[id], UnitEntry(sd, id)
        if id ~= ARCHWITCH_FINA and u and entry then
            local changed = {}
            for _, f in ipairs({ { "EquipWeaponId", u.weapon }, { "EquipArmorId", u.armor } }) do
                local was = Int(entry[f[1]])
                if was ~= f[2] then
                    ok = Put(entry, f[1], f[2]) and ok
                    changed[#changed + 1] = f[1] .. " " .. tostring(was) .. "->" .. f[2]
                end
            end
            local was = table.concat(Ints(entry.EquipAccessoryIdList), ",")
            if was ~= table.concat(u.accessories, ",") then
                ok = SetInts(entry.EquipAccessoryIdList, u.accessories) and ok
                changed[#changed + 1] = "accessories [" .. was .. "]->[" .. table.concat(u.accessories, ",") .. "]"
            end
            parts[#parts + 1] = (UNIT_NAMES[id] or tostring(id)) .. " " .. (#changed > 0 and table.concat(changed, ", ") or "as the row")
        end
    end
    return ok, "gear: " .. table.concat(parts, "; ")
end

-- The rest of the start, on the new game's save once it is in: what SkipPrologue writes (it is
-- all absolute apart from the bag), the starters' gear, then the bag. Saves nothing. Returns ok
-- and report lines.
function G.NewStartFinish(opts)
    local party = opts.party or SKIP_PARTY
    local ok, report = G.SkipPrologue({ inventory = false, openStart = true, party = party, arrival = opts.arrival })
    local okGear, gear = NewStartEquip(G.SaveData(), party)
    report[#report + 1] = (okGear and "ok   " or "FAIL ") .. gear
    local okBag, bag = NewStartBag(party)
    report[#report + 1] = (okBag and "ok   " or "FAIL ") .. bag
    return ok and okGear and okBag, report
end

-- How far the player stands from the arrival (nil off its map), a line for the log, and the
-- pawn's height.
function G.NewStartWhere(a)
    local map = G.CurrentMap()
    local pose, why = G.PlayerPose()
    if not pose then return nil, "map " .. tostring(map) .. ", " .. tostring(why) end
    local d = math.sqrt((pose.x - a.x) ^ 2 + (pose.y - a.y) ^ 2)
    return map == a.map and d or nil, string.format("map %s (arrival %d), pawn %s at %.0f, %.0f, %.0f, %.0f from the arrival",
        tostring(map), a.map, pose.class, pose.x, pose.y, pose.z, d), pose.z
end

-- Moves each airship actor on the map that stands farther than `far` from `a` to it. step(what)
-- runs before each move. Returns how many airship actors are on the map, and a part per move.
function G.MoveAirships(a, far, step)
    local to = { X = a.x, Y = a.y, Z = a.z }
    local parts, seen, count = {}, {}, 0
    for _, class in ipairs(NS.airships) do
        local okAll, all = pcall(FindAllOf, class)
        for _, ship in ipairs(okAll and all or {}) do
            local key = Alive(ship) and ship:GetFullName()
            if key and not seen[key] then
                seen[key], count = true, count + 1
                local at
                pcall(function() at = ship:K2_GetActorLocation() end)
                local d = at and math.sqrt((at.X - a.x) ^ 2 + (at.Y - a.y) ^ 2) or math.huge
                if d > far then
                    step("airship K2_SetActorLocation " .. key)
                    local okShip = pcall(function() ship:K2_SetActorLocation(to, false, {}, true) end)
                    parts[#parts + 1] = string.format("airship %s from %.0f, %.0f%s", class,
                        at and at.X or 0, at and at.Y or 0, okShip and "" or " (raised)")
                end
            end
        end
    end
    return count, parts
end

-- Moves the airship (when it is on the map) and then the player on foot to the arrival.
-- step(what) runs before each move. Returns ok and a line.
function G.NewStartMove(a, step)
    local pose, why = G.PlayerPose()
    if not pose then return false, tostring(why) end
    local to = { X = a.x, Y = a.y, Z = a.z }
    local count, parts = G.MoveAirships(a, -1, step)
    if count == 0 then parts[1] = "no airship on the map" end
    step(string.format("K2_SetActorLocation %.0f, %.0f, %.0f", a.x, a.y, a.z))
    local ok = pcall(function() pose.pawn:K2_SetActorLocation(to, false, {}, true) end)
    parts[#parts + 1] = ok and "moved to the arrival" or "K2_SetActorLocation raised"
    return ok, table.concat(parts, "; ")
end
end

-- The property of an object's class (or a parent class) named `field`, or nil.
local function FindProperty(obj, field)
    local found
    pcall(function()
        local cls = obj:GetClass()
        while cls and cls:IsValid() and not found do
            cls:ForEachProperty(function(p)
                if not found and p:GetFName():ToString() == field then found = p end
            end)
            cls = cls:GetSuperStruct()
        end
    end)
    return found
end

-- Live chests in this map, with their table data, plus the chest table's first rows.
-- Answers: which field of the table row is the map id and which is the uid, so the apworld
-- location list can come straight from CDT_MapGimmickTreasureBox.
function G.DumpChests(out, maxRows)
    local mapId = G.CurrentMap()
    out("map " .. tostring(mapId) .. " (save's Map.mapId " .. tostring(G.MapId()) .. "), story "
        .. tostring(G.StoryCounter()))
    for _, c in ipairs(G.LiveChests()) do
        out(string.format("chest row %s:%s m_Id %s open %s; save: %s", tostring(c.rowMap), tostring(c.rowId),
            tostring(c.uid), tostring(c.open), mapId and G.ChestSaveKeys(mapId, c) or "?"))
        for _, field in ipairs({ "m_TreasureBoxData", "m_EventData" }) do
            local p = FindProperty(c.actor, field)
            local s
            if p then pcall(function() s = p:GetStruct() end) end
            if s then
                out("  " .. field .. " : " .. s:GetFName():ToString())
                DumpStruct(s, c.actor[field], "    ", 2, out)
            end
        end
    end
    local dt = Find("/Game/Datatable/Map/Gimmick/TreasureBox/CDT_MapGimmickTreasureBox.CDT_MapGimmickTreasureBox")
    if not dt then
        out("chest table not loaded")
        return
    end
    local rowStruct
    pcall(function() rowStruct = dt.RowStruct end)
    local shown = 0
    pcall(function()
        dt:ForEachRow(function(name, row)
            shown = shown + 1
            if shown > (maxRows or 5) then return end
            out("row " .. Show(name))
            if rowStruct then DumpStruct(rowStruct, row, "  ", 1, out) end
        end)
    end)
    out("chest table rows: " .. shown)
end

-- Every property of a field item's own classes (the Blueprint and the game's C++ bases, up to
-- the engine's Actor), with values. This is where its reward fields will show up.
function G.DumpFieldItems(out)
    local mapId = G.CurrentMap()
    local items = G.LiveFieldItems()
    out(string.format("map %s: %d field items", tostring(mapId), #items))
    for _, it in ipairs(items) do
        out(string.format("field item %s uid %s hidden %s interact %s, save says %s", it.class,
            tostring(it.uid), tostring(it.hidden), tostring(it.interact),
            tostring(mapId and it.uid and G.IsChestOpenInSave(mapId, it.uid))))
        pcall(function()
            local cls = it.actor:GetClass()
            while cls and cls:IsValid() do
                local cname = cls:GetFName():ToString()
                if cname == "Actor" or cname == "Object" then break end
                out("  class " .. cname)
                cls:ForEachProperty(function(prop)
                    local name = prop:GetFName():ToString()
                    local kind = prop:GetClass():GetFName():ToString()
                    local v
                    pcall(function() v = it.actor[name] end)
                    if kind == "StructProperty" then
                        local s
                        pcall(function() s = prop:GetStruct() end)
                        out("    " .. name .. " : " .. (s and s:GetFName():ToString() or "?"))
                        if s then DumpStruct(s, v, "      ", 1, out) end
                    else
                        out("    " .. kind .. " " .. name .. " = " .. Show(v))
                    end
                end)
                cls = cls:GetSuperStruct()
            end
        end)
    end
end

-- -------------------------------------------------------------------------------------------
-- Artificial gates and custom key items (experimental)
-- -------------------------------------------------------------------------------------------
-- Inactive unless `ffrap_gate` runs from the console. Logs risky calls via G.gateTrace beforehand.

G.TEST_KEY_ID = 29901
G.TEST_KEY_NAME = "Bridge Crest"
G.TEST_KEY_DESC = "An Archipelago test key item used to unseal gated bridges."
G.gateTrace = nil

local VALUABLE_DT = "/Game/Datatable/Item/DT_ValuableItemData.DT_ValuableItemData"
local GATE_SPECS = {
    box = { { pkg = "/Game/BP/Map/Gimmick/BP_MapGimmick_BlockingBox", name = "BP_MapGimmick_BlockingBox" } },
    rock = { { pkg = "/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockingBase_Rock", name = "BP_MapGimmick_BlockingBase_Rock" } },
    pot = { { pkg = "/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockingBase_Child_MagicPot", name = "BP_MapGimmick_BlockingBase_Child_MagicPot" } },
    gate = { { pkg = "/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockObject_Gate", name = "BP_MapGimmick_BlockObject_Gate" } },
    world = { { pkg = "/Game/BP/Map/Gimmick/Child/BlockObject/BP_MapGimmick_BlockingBase_Wld01Gra_01", name = "BP_MapGimmick_BlockingBase_Wld01Gra_01" } },
}
GATE_SPECS.combo = { GATE_SPECS.box[1], GATE_SPECS.pot[1] }

local customItemNames = { [G.TEST_KEY_ID] = G.TEST_KEY_NAME }
local gateState = nil

local function gateStep(what)
    if G.gateTrace then G.gateTrace(what) end
end

local function AsText(v)
    if v == nil then return nil end
    if type(v) == "string" then return v end
    local ok, s = pcall(function() return v:ToString() end)
    if ok and type(s) == "string" then return s end
    local okGet, g = pcall(function() return v:get():ToString() end)
    if okGet and type(g) == "string" then return g end
    return tostring(v)
end

-- Loads an object by path, using KismetSystemLibrary first (LoadAsset crashed once after fast
-- travel in FFRSLib).
local function LoadObject(path)
    local o = Find(path)
    if o then return o end
    gateStep("LoadAsset_Blocking " .. path)
    pcall(function()
        local ksl = Find("/Script/Engine.Default__KismetSystemLibrary")
        ksl:LoadAsset_Blocking(ksl:Conv_SoftObjPathToSoftObjRef(ksl:MakeSoftObjectPath(path)))
    end)
    o = Find(path)
    if not o and LoadAsset then
        gateStep("LoadAsset fallback " .. path)
        pcall(function() LoadAsset(path) end)
        o = Find(path)
    end
    return o
end
G.LoadObject = LoadObject   -- for functions defined above this point

-- Loads a cooked Blueprint's generated class (`<pkg>.<name>_C`), trying the class path first and
-- AssetRegistryHelpers second (as FFRSLib loads BP_PackSection_C).
local function LoadBlueprintClass(pkg, name)
    local className = name .. "_C"
    local classPath = pkg .. "." .. className
    local cls = LoadObject(classPath)
    if cls then return cls end
    gateStep("AssetRegistryHelpers:GetAsset " .. classPath)
    pcall(function()
        local helpers = Find("/Script/AssetRegistry.Default__AssetRegistryHelpers")
        if helpers then
            cls = helpers:GetAsset({
                PackageName = FName(pkg),
                AssetName = FName(className),
            })
        end
    end)
    if cls and cls:IsValid() then return cls end
    return nil
end

function G.HeldCount(id)
    local inv = Lib("CPP_BFL_SaveDataInventory")
    return inv and Held(inv, id) or nil
end

-- Roster status for a playable unit: 0 joined, 1 never joined, 2 left, or nil when unknown.
function G.UnitJoinStatus(unitId)
    local lib = Lib("CPP_BFL_SaveDataUnit")
    if lib and lib.GetJoinStatus then
        local ok, st = pcall(function() return lib:GetJoinStatus(unitId) end)
        local n = ok and Int(st) or nil
        if n ~= nil then return n end
    end
    local sd = G.SaveData()
    local u = sd and UnitEntry(sd, unitId)
    return u and Int(u.JoinStatus) or nil
end

-- Sets a playable unit's roster status. Returns how it was written ("library" or "save
-- field"), or nil when neither worked.
function G.SetJoinStatus(unitId, status)
    local lib = Lib("CPP_BFL_SaveDataUnit")
    if lib and lib.SetJoinStatus then
        local ok = pcall(function() lib:SetJoinStatus(unitId, status) end)
        if ok and G.UnitJoinStatus(unitId) == status then return "library" end
    end
    local sd = G.SaveData()
    local u = sd and UnitEntry(sd, unitId)
    if u and Put(u, "JoinStatus", status) then return "save field" end
    return nil
end

function G.IsUnitJoined(unitId)
    local st = G.UnitJoinStatus(unitId)
    if st ~= nil then return st == 0 end
    local vm = PartyVM()
    return vm ~= nil and Joined(vm, unitId)
end

local function CanOverwriteItem(id, rowName)
    if type(rowName) == "string" and rowName:sub(1, 10) == "FFRAP_Key_" then return true end
    return id >= 29900 or id == 20018 or (id >= 30012 and id <= 30016)
end

-- Adds or updates a key item row in DT_ValuableItemData. AddRow drops FText fields passed in a
-- Lua table, so an existing row is cloned first and FText fields are set on the stored row.
function G.InjectValuableItem(id, name, desc)
    id = tonumber(id) or G.TEST_KEY_ID
    name = (name and name ~= "") and name or G.TEST_KEY_NAME
    desc = (desc and desc ~= "") and desc or G.TEST_KEY_DESC

    local dt = LoadObject(VALUABLE_DT)
    if not dt then return false, "DT_ValuableItemData could not be loaded" end

    local total, template, existingName, existingRow = 0, nil, nil, nil
    gateStep("scan DT_ValuableItemData")
    pcall(function()
        dt:ForEachRow(function(k, row)
            total = total + 1
            local rid = Int(row.ID)
            if not template or rid == 20008 then template = row end
            if rid == id then
                existingName = AsText(k)
                existingRow = row
            end
        end)
    end)

    local rowName, r, how
    if existingRow then
        if not CanOverwriteItem(id, existingName) then
            return false, "item " .. id .. " is a vanilla item (row " .. tostring(existingName)
                .. "); use >= 29900, 20018, or 30012..30016"
        end
        rowName, r = existingName, existingRow
        how = "updated row " .. tostring(rowName)
    else
        rowName = "FFRAP_Key_" .. tostring(id)
        gateStep("DT_ValuableItemData:AddRow " .. rowName)
        local added = false
        if template and pcall(function() dt:AddRow(rowName, template) end) then
            added = true
        elseif pcall(function() dt:AddRow(rowName, {}) end) then
            added = true
        end
        if not added then return false, "DT_ValuableItemData:AddRow refused " .. rowName end
        gateStep("DT_ValuableItemData:FindRow " .. rowName)
        pcall(function() r = dt:FindRow(rowName) end)
        if not r then
            pcall(function()
                dt:ForEachRow(function(k, row)
                    if not r and AsText(k) == rowName then r = row end
                end)
            end)
        end
        if not r then return false, "AddRow ran, but FindRow(" .. rowName .. ") returned nil" end
        how = "added row " .. rowName .. " (table had " .. total .. " rows)"
    end

    gateStep("write fields on " .. tostring(rowName))
    pcall(function() r.ID = id end)
    pcall(function() r.sortId = 9900 + (id % 100) end)
    pcall(function() r.nameSg = FText(name) end)
    pcall(function() r.namePl = FText(name .. "s") end)
    pcall(function() r.nameDetSg = FText("a " .. name) end)
    pcall(function() r.nameDetPl = FText(name .. "s") end)
    pcall(function() r.description = FText(desc) end)
    pcall(function()
        r.buyingPrice = 0
        r.sellingPrice = 0
        r.isAvailableSale = false
    end)

    local readId, readName
    pcall(function() readId = Int(r.ID) end)
    pcall(function() readName = AsText(r.nameSg) end)
    customItemNames[id] = name
    if readId ~= id then
        return false, how .. ", but r.ID read back as " .. tostring(readId)
    end
    return true, how .. ": ID=" .. tostring(readId) .. ', name="' .. tostring(readName) .. '"'
end

-- The player pawn's position, facing, scale and world, or nil and a reason.
function G.PlayerPose()
    local pc = PlayerController()
    if not pc then return nil, "no PlayerController" end
    local pawn
    pcall(function() pawn = pc:K2_GetPawn() end)
    if not (pawn and Alive(pawn)) then return nil, "no player pawn" end
    local loc
    pcall(function() loc = pawn:K2_GetActorLocation() end)
    if not (loc and type(loc.X) == "number") then return nil, "cannot read pawn location" end
    local yaw = 0
    pcall(function()
        local rot = pawn:K2_GetActorRotation()
        if rot and type(rot.Yaw) == "number" then yaw = rot.Yaw end
    end)
    local fx, fy
    pcall(function()
        local fwd = pawn:GetActorForwardVector()
        if fwd and type(fwd.X) == "number" and (fwd.X ~= 0 or fwd.Y ~= 0) then
            fx, fy = fwd.X, fwd.Y
        end
    end)
    if not fx then
        local rad = yaw * math.pi / 180.0
        fx, fy = math.cos(rad), math.sin(rad)
    end
    local sx, sy, sz = 1, 1, 1
    pcall(function()
        local s = pawn:GetActorScale3D()
        if s and type(s.X) == "number" then sx, sy, sz = s.X, s.Y, s.Z end
    end)
    local pawnClass = "?"
    pcall(function() pawnClass = pawn:GetClass():GetFName():ToString() end)
    local world
    pcall(function() world = pawn:GetWorld() end)
    if not (world and world:IsValid()) then pcall(function() world = pc:GetWorld() end) end
    if not (world and world:IsValid()) then return nil, "no valid UWorld" end
    return {
        pawn = pawn, world = world, class = pawnClass,
        x = loc.X, y = loc.Y, z = loc.Z, yaw = yaw, fx = fx, fy = fy,
        sx = sx, sy = sy, sz = sz,
    }
end

function G.HasActiveGate()
    return gateState ~= nil
end

-- Destroys any spawned test gate actors and resets gate state. Returns how many actors were cleared.
function G.ClearGate()
    if not gateState then return 0 end
    local n = 0
    for _, a in ipairs(gateState.actors or {}) do
        if Alive(a) then
            n = n + 1
            gateStep("destroy gate actor")
            pcall(function() a:SetActorEnableCollision(false) end)
            pcall(function() a:SetActorHiddenInGame(true) end)
            pcall(function() a:K2_DestroyActor() end)
        end
    end
    gateState = nil
    return n
end

-- Spawns one blocker Blueprint (a GATE_SPECS entry) at `loc` facing `rot`, visible and solid.
-- Returns the actor, or nil and why. A field of G, not a local: the main chunk is at Lua's limit
-- of 200 locals.
function G.SpawnBlocker(world, spec, loc, rot, scale)
    local cls = LoadBlueprintClass(spec.pkg, spec.name)
    if not cls then return nil, "could not load class " .. spec.pkg .. "." .. spec.name .. "_C" end
    gateStep("SpawnActor " .. spec.name)
    local actor
    local okSpawn = pcall(function() actor = world:SpawnActor(cls, loc, rot) end)
    if not (okSpawn and actor and actor:IsValid()) then
        gateStep("SpawnActor empty-transform fallback " .. spec.name)
        pcall(function() actor = world:SpawnActor(cls, {}, {}) end)
    end
    if not (actor and actor:IsValid()) then return nil, "SpawnActor failed for " .. spec.name end
    -- SpawnActor can ignore the transform table, so the place is set again when it did.
    local ax, ay
    pcall(function()
        local aloc = actor:K2_GetActorLocation()
        if aloc then ax, ay = aloc.X, aloc.Y end
    end)
    if not ax or math.abs(ax - loc.X) + math.abs(ay - loc.Y) > 1.0 then
        gateStep("K2_SetActorLocation " .. spec.name)
        pcall(function() actor:K2_SetActorLocation(loc, false, {}, true) end)
        pcall(function() actor:K2_SetActorRotation(rot, true) end)
    end
    if scale then
        gateStep("SetActorScale3D " .. spec.name)
        pcall(function() actor:SetActorScale3D({ X = scale, Y = scale, Z = scale }) end)
    end
    gateStep("enable visibility and collision " .. spec.name)
    pcall(function() actor:SetActorHiddenInGame(false) end)
    pcall(function() actor:SetActorEnableCollision(true) end)
    return actor
end

-- Spawns a test gate `dist` units ahead of the player. `kind` is combo (BlockingBox + MagicPot),
-- box, rock, pot, gate or world. Raw NPC pawns crash or self-destruct without MapManager setup,
-- so `npc` is refused. Replaces any previous test gate.
function G.SpawnGate(kind, dist, scale)
    kind = (kind and kind ~= "") and kind:lower() or "combo"
    if kind == "npc" then
        return false, "npc pawns crash when spawned directly; use combo, box, rock, pot, gate or world"
    end
    local mapId = G.CurrentMap()
    local specs = GATE_SPECS[kind]
    if not specs then
        return false, 'unknown gate kind "' .. tostring(kind) .. '" (use combo, box, rock, pot, gate, world)'
    end

    local pose, why = G.PlayerPose()
    if not pose then return false, why end
    dist = tonumber(dist) or (mapId == 1000 and 120 or 220)
    local sc = scale and tonumber(scale) or nil

    G.ClearGate()

    local tx = pose.x + pose.fx * dist
    local ty = pose.y + pose.fy * dist
    local tz = pose.z
    local tyaw = (pose.yaw + 180.0) % 360.0
    local locArg = { X = tx, Y = ty, Z = tz }
    local rotArg = { Pitch = 0.0, Yaw = tyaw, Roll = 0.0 }

    local spawned, names = {}, {}
    for _, spec in ipairs(specs) do
        local actor, why = G.SpawnBlocker(pose.world, spec, locArg, rotArg, sc)
        if not actor then
            gateState = { actors = spawned }
            G.ClearGate()
            return false, why
        end
        spawned[#spawned + 1] = actor
        names[#names + 1] = spec.name
    end

    gateState = {
        kind = kind,
        mapId = mapId,
        x = tx, y = ty, z = tz,
        dist = dist,
        bumpDist = math.max(90.0, dist * 0.75),
        locked = true,
        actors = spawned,
        cond = nil,
    }
    return true, string.format(
        "spawned %s (%s) at (%.1f, %.1f, %.1f), %.0f ahead of %s (scale %.2f)",
        kind, table.concat(names, " + "), tx, ty, tz, dist, pose.class, pose.sx
    )
end

local function LiveGateActors()
    if not gateState then return nil end
    local live = {}
    for _, a in ipairs(gateState.actors or {}) do
        if Alive(a) then live[#live + 1] = a end
    end
    gateState.actors = live
    if #live == 0 then
        gateState = nil
        return nil
    end
    return live
end

function G.SetGateLock(locked)
    local live = LiveGateActors()
    if not live then return false, "no active gate (spawn one first, or the map changed)" end
    for _, a in ipairs(live) do
        gateStep((locked and "lock" or "unlock") .. " gate actor")
        pcall(function() a:SetActorHiddenInGame(not locked) end)
        pcall(function() a:SetActorEnableCollision(locked) end)
    end
    gateState.locked = locked
    return true, locked and "locked (visible, collision on)" or "unlocked (hidden, collision off)"
end

function G.CheckGateCondition(cond)
    if not cond then return false, "none" end
    if cond.kind == "item" then
        local need = cond.count or 1
        local held = G.HeldCount(cond.id) or 0
        local label = customItemNames[cond.id] or ("item " .. tostring(cond.id))
        return held >= need, string.format("%s (%d/%d)", label, held, need)
    elseif cond.kind == "unit" then
        local st = G.UnitJoinStatus(cond.id)
        local joined = G.IsUnitJoined(cond.id)
        return joined, string.format("unit %d (%s, JoinStatus=%s)", cond.id, joined and "joined" or "missing", tostring(st))
    elseif cond.kind == "flag" then
        local on = G.GetFlag(cond.id) == true
        return on, string.format("flag %d (%s)", cond.id, tostring(on))
    end
    return false, "unknown condition " .. tostring(cond.kind)
end

function G.SetGateRequirement(cond)
    if not LiveGateActors() then return false, "no active gate (run ffrap_gate spawn first)" end
    gateState.cond = cond
    if not cond then return true, "requirement cleared" end
    local met, text = G.CheckGateCondition(cond)
    G.SetGateLock(not met)
    return true, (met and "unlocked: " or "locked, need ") .. text
end

-- Polls the active gate once: checks actor liveness, re-evaluates any requirement, and measures
-- horizontal distance from the player pawn.
function G.PollGate()
    if not gateState then return nil end
    if not LiveGateActors() then return { gone = true } end
    local changed, condText = nil, nil
    if gateState.cond then
        local met
        met, condText = G.CheckGateCondition(gateState.cond)
        local wantLocked = not met
        if wantLocked ~= gateState.locked then
            G.SetGateLock(wantLocked)
            changed = wantLocked and "locked" or "unlocked"
        end
    end
    local dist = nil
    local pose = G.PlayerPose()
    if pose then
        local dx, dy = pose.x - gateState.x, pose.y - gateState.y
        dist = math.sqrt(dx * dx + dy * dy)
    end
    return {
        locked = gateState.locked,
        changed = changed,
        condText = condText,
        dist = dist,
        bumpDist = gateState.bumpDist,
        kind = gateState.kind,
        mapId = gateState.mapId,
        x = gateState.x, y = gateState.y, z = gateState.z,
        actors = #gateState.actors,
    }
end

-- -------------------------------------------------------------------------------------------
-- Open-world systems: enemy scaling, airship, no-landing zones
-- -------------------------------------------------------------------------------------------
-- Enemy stats are fixed per unit in DT_UnitParameter (LevelParamId = -1), so scaling rewrites
-- table rows directly using a log-linear fit from normal encounter groups (docs/open_world.md):
--   log(stat) = a + b*log(level) + c*level
--   stat(L) = base * (L / baseLevel)^b * e^(c * (L - baseLevel))
-- Levels above 70 clamp to 70 for the curve. MP is left untouched.
local UNIT_TABLE = "/Game/Datatable/Unit/DT_UnitParameter.DT_UnitParameter"
G.ENEMY_CURVE = {
    MaxHitPoint = { 0.3675, 0.08917 }, MaxBreakPoint = { -0.1249, 0.05094 },
    Attack = { 0.3207, 0.02946 }, Defence = { 0.7752, 0.00867 },
    Intelligence = { 0.5644, 0.03269 }, Mind = { 0.7289, 0.01236 },
    Agility = { 0.7853, 0.00899 }, Experience = { -0.0647, 0.12967 }, Money = { 0.0934, 0.09910 },
    -- Battle-group MRP (`ap` in DT_BattleGroup) fitted against group average enemy level.
    BattleMRP = { 0.0689, 0.06162 },
}
G.CURVE_TOP = 70
-- Round 77: bosses take HP from a curve fitted to the game's own bosses up to level 60 (102 rows
-- of 5,000 to 600,000 HP). The enemy curve is much steeper: Siren (level 11, 20,000 HP) scaled to
-- 57 had 2,434,404 HP, where the game's level-50 bosses have 130,000 to 250,000. This one gives
-- her about 320,000.
G.BOSS_CURVE = { MaxHitPoint = { 0.91163, 0.02766 } }
-- Round 77: Defence grows as the curve's factor to this power, when it grows. Physical skills fell
-- behind magic late in a run. Scaling down is left as it was.
G.DEFENCE_GROWTH = 0.75
local GROWTH_ORDER = { "MaxHitPoint", "MaxBreakPoint", "Attack", "Defence", "Intelligence", "Mind",
                       "Agility", "Experience", "Money" }
-- Tuning multipliers: `hp` scales HP, `attack` scales Attack, `magic` scales Intelligence.
local KNOB_STATS = { MaxHitPoint = "hp", Attack = "attack", Intelligence = "magic" }
local CATEGORY_ENEMY, CATEGORY_BOSS = 2, 3     -- eUnitCategory
-- Units in boss battle groups (G.BOSSES) scale as bosses even if categorized as Enemy (e.g. The
-- Hunger and cave masters); those with 0 base EXP receive story-boss EXP (~1350 around Lv 13-14).
local BOSS_EXP_LEVEL, BOSS_EXP = 14, 1350

-- Arena rank battles (9705-9721: Brawler 1 through Champion 5 plus Microchus spawns) also scale as
-- bosses since their units appear nowhere else. Fledgling battles (9700-9704) share field-enemy
-- rows and are excluded; Arena enemies keep 0 EXP.
local ARENA_BOSS_GROUPS = { first = 9705, last = 9721 }

-- The units scaled as bosses whatever their category: those in a boss location's group (they get
-- a boss's EXP when they ship with none), and those in the Arena's rank battles.
local function BossUnitIds()
    local groups, units, arena = {}, {}, {}
    for _, b in ipairs(G.BOSSES) do groups[b.group] = true end
    for _, dt in ipairs(TableFamily(Find(BATTLE_GROUP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                pcall(function()
                    local id = Int(row.ID)
                    local into = (groups[id] and units)
                        or (id >= ARENA_BOSS_GROUPS.first and id <= ARENA_BOSS_GROUPS.last and arena)
                    if not into then return end
                    local list = row.UnitIdList
                    for i = 1, #list do into[Int(list[i])] = true end
                end)
            end)
        end)
    end
    return units, arena
end
G.MAX_LEVEL = 99

-- How much a stat grows from level `from` to level `to` (a factor; 1 when they are equal).
-- `curves` (optional) replaces ENEMY_CURVE's entries for the stats it has.
function G.CurveRatio(stat, from, to, curves)
    local k = (curves and curves[stat]) or G.ENEMY_CURVE[stat]
    if not k then return 1 end
    from = math.max(1, math.min(from, G.CURVE_TOP))
    to = math.max(1, math.min(to, G.CURVE_TOP))
    local ratio = (to / from) ^ k[1] * math.exp(k[2] * (to - from))
    if stat == "Defence" and ratio > 1 then ratio = ratio ^ G.DEFENCE_GROWTH end
    return ratio
end

-- The stats of a unit moved from its own level to `level`. Pure: `orig` holds Level and the
-- stats in ENEMY_CURVE. `knobs` (optional) holds percentages: hp (MaxHitPoint), attack
-- (Attack) and magic (Intelligence), 100 when missing. A stat that is 0 stays 0, and no other stat goes
-- below 1. `curves` goes to CurveRatio (G.BOSS_CURVE for bosses).
function G.ScaledStats(orig, level, knobs, curves)
    knobs = knobs or {}
    local out = { Level = level }
    for _, k in ipairs(GROWTH_ORDER) do
        local v = orig[k] or 0
        if v > 0 then
            local knob = KNOB_STATS[k] and knobs[KNOB_STATS[k]] or 100
            out[k] = math.max(1, math.floor(v * G.CurveRatio(k, orig.Level, level, curves) * knob / 100 + 0.5))
        else
            out[k] = v
        end
    end
    return out
end

-- The level an enemy gets. mode "fixed": every enemy at `a`. mode "clamp": the enemy's own
-- level, pulled into a .. b (the "within N levels of the party" idea). Anything else: its own.
function G.ScaledLevel(own, mode, a, b)
    local lv = own
    if mode == "fixed" then lv = a
    elseif mode == "clamp" then lv = math.min(math.max(own, a), b) end
    return math.max(1, math.min(G.MAX_LEVEL, math.floor(lv)))
end

-- Target enemy level band centered on `at`% of party level, clamped to [center - range, center + above].
-- Values below 100 compensate for party outleveling later vanilla regions.
function G.LevelBand(partyLevel, range, at, above)
    local c = math.max(1, math.floor(partyLevel * (at or 100) / 100 + 0.5))
    return c - range, c + (above or range), c
end

-- A party member's level: CPP_BFL_Unit:GetPlayableUnitLevel (FFRSLib's ffrs_unit_level reads
-- it the same way). nil when unknown.
function G.UnitLevel(unitId)
    local lib = Lib("CPP_BFL_Unit")
    if not lib then return nil end
    local ok, lv = pcall(function() return lib:GetPlayableUnitLevel(unitId) end)
    lv = ok and Int(lv) or nil
    if lv and lv > 0 then return lv end
    return nil
end

-- Sets a unit's level via XP (as ffrs_unit_level does) and refills HP/MP via isMaxStatusSet so
-- lowered units do not retain higher-level HP. Returns ok and a detail.
function G.SetUnitLevel(unitId, level)
    local lib = Lib("CPP_BFL_Unit")
    if not (lib and lib.GetExpForReachLevel and lib.SetPlayableUnitExperience) then return false, "no unit library" end
    local max
    pcall(function() max = Int(lib:GetMaxLevel()) end)
    if max and max > 0 and level > max then level = max end
    local exp
    pcall(function() exp = Int(lib:GetExpForReachLevel(unitId, level)) end)
    if exp == nil or (level > 1 and exp <= 0) then return false, "no level table for unit " .. unitId end
    if not pcall(function() lib:SetPlayableUnitExperience(unitId, exp, true) end) then
        return false, "SetPlayableUnitExperience raised for unit " .. unitId
    end
    local now = G.UnitLevel(unitId)
    if now ~= level then return false, "unit " .. unitId .. " reads level " .. tostring(now) .. " after setting " .. level end
    return true, "level " .. level
end

-- Save slot level is read from Rain even if Rain has not joined, so keep her level synced to the
-- active party while she remains unjoined. Returns true when a level write occurred.
local RAIN = 1001
function G.SyncSlotLevel()
    if G.UnitJoinStatus(RAIN) == 0 then return false end
    local level = G.PartyLevel()
    if not level or G.UnitLevel(RAIN) == level then return false end
    return (G.SetUnitLevel(RAIN, level))
end

-- The active party's average level, rounded, and the members' levels as text ("1001:5 1002:4").
-- nil when the party or any level cannot be read.
function G.PartyLevel()
    local ids = G.PartyIds()
    if not ids or #ids == 0 then return nil, "no party" end
    local sum, parts = 0, {}
    for _, id in ipairs(ids) do
        local lv = G.UnitLevel(id)
        if not lv then return nil, "no level for unit " .. tostring(id) end
        sum = sum + lv
        parts[#parts + 1] = id .. ":" .. lv
    end
    return math.floor(sum / #ids + 0.5), table.concat(parts, " ")
end

-- Sets the story counter (Progress[0]) of the loaded save, as FFRSLib's ffrs_story_set does,
-- but for any value: that one stops at 8050, and the ending sets 9000. Returns the value read
-- back. Save and reload for the maps to follow it.
function G.SetStoryCounter(n)
    local sd = G.SaveData()
    if not sd then return nil end
    pcall(function() sd.Progress.Progress[1] = n end)
    return G.StoryCounter()
end

-- Any progress value, {progress:i} in the game's conditions (element i + 1 in Lua), or nil.
function G.ProgressValue(i)
    local sd = G.SaveData()
    if not sd then return nil end
    local ok, v = pcall(function() return sd.Progress.Progress[i + 1] end)
    return ok and Int(v) or nil
end

function G.SetProgressValue(i, n)
    local sd = G.SaveData()
    if not sd then return nil end
    pcall(function() sd.Progress.Progress[i + 1] = n end)
    return G.ProgressValue(i)
end

-- Airship radar treasures: 13 sea pinger points enabled by flag 702 (radar), each hidden by its
-- found flag (704-716). Points 6 on need {progress:49} >= 40, 10 on >= 50. Each point also needs
-- the found count {progress:51} at a threshold (point 2 >= 10, 3 >= 11 ... 13 >= 31), and each dig
-- row sets the count to a fixed value (10, 11 ... 32), so in the game they come one at a time.
-- The radar itself works only while DT_MapPingerData's condition holds: step {progress:49} must be
-- one of a band's steps while the found count is at most the band's `upTo` (round 74). A band's
-- `upTo` is also the threshold of its last point, so the mod holds the count there: each
-- Progressive Radar opens its whole tier at once (round 75). Band N is Progressive Radar N.
G.RADAR_ON_FLAG, G.RADAR_TIER_PROGRESS, G.RADAR_FOUND_PROGRESS = 702, 49, 51
-- Round 105: on the first boarding after story 5040 with the radar's step at 0, Lid says "We
-- already found Mysidia..." (SubEv_C05_TreasureRadar_02, from DT_MapAirShip), which sets the step
-- to 10. Our start skips that story, so the line made no sense. Every other test of the step reads
-- 0 and 10 alike, so a seed's save starts at 10.
G.RADAR_LID_HEARD = 10
G.RADAR_BANDS = {
    { upTo = 13, steps = { 20, 30 } },
    { upTo = 22, steps = { 40 } },
    { upTo = 31, steps = { 50 } },
}
-- The radar's three parts (Magi-tenna, Resonance Stone, High-Power Generator). With the radar's
-- treasures on, the Progressive Radars take their place, and Mt. Reizan's chest with the Resonance
-- Stone is a location like any other chest: main.lua sets blankRadarParts (round 75).
G.RADAR_PARTS, G.blankRadarParts = { [27006] = true, [27007] = true, [27008] = true }, false
-- Round 108 (a player): in the game the radar goes quiet once every treasure it can find is dug, until
-- the next part. The mod held the count in the band, so it kept pinging. With every treasure of the
-- level's tiers found, the count goes RADAR_QUIET past the band's top: out of every band, and off
-- the exact counts (14 and 23) the game's own part upgrades test.
G.RADAR_QUIET = 2
G.RADAR = {}
for n = 1, 13 do
    G.RADAR[n] = { n = n, flag = 703 + n, row = string.format("SubEv_C05_TreasureRadar_01_%02d", n),
                   tier = n <= 5 and 1 or n <= 9 and 2 or 3 }
end

-- Track latest external values as "originals" (e.g. if FFRRandomizer overwrites enemy rows every 3s)
-- so turning scaling off restores current table values rather than stale pre-mod values.
local scaleOriginals = {}   -- unit id -> { Level = n, MaxHitPoint = n, ... } as the game last had it
-- Battle-group MRP (`ap`) lives on the battle group table and scales with group average level.
-- `mrpLevels` is unit id -> the level its MRP is paid at (its new level plus the band's mrpLift).
local groupOriginals, groupWrote = {}, {}   -- battle group id -> MRP as shipped, and as last written
local function ScaleBattleGroups(mode, mrpLevels)
    local changed = 0
    for _, dt in ipairs(TableFamily(Find(BATTLE_GROUP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                pcall(function()
                    local id, now = Int(row.ID), Int(row.ap) or 0
                    if groupWrote[id] == nil or groupWrote[id] ~= now then groupOriginals[id] = now end
                    local orig, want = groupOriginals[id], groupOriginals[id]
                    if mode ~= "off" and orig > 0 then
                        local from, to, n = 0, 0, 0
                        local units = row.UnitIdList
                        for i = 1, #units do
                            local unit = Int(units[i])
                            if mrpLevels[unit] and scaleOriginals[unit] then
                                from, to, n = from + scaleOriginals[unit].Level, to + mrpLevels[unit], n + 1
                            end
                        end
                        if n > 0 then
                            want = math.max(1, math.floor(orig * G.CurveRatio("BattleMRP", from / n, to / n) + 0.5))
                        end
                    end
                    if now ~= want then
                        row.ap = want
                        changed = changed + 1
                    end
                    groupWrote[id] = want
                end)
            end)
        end)
    end
    return changed
end
local scaleWrote = {}       -- unit id -> the values we last wrote into that row
local scaleWanted = nil     -- unit id -> the level the last rescale wrote (nil: none, or "off")
local scaleTables = nil     -- the tables the last rescale wrote, as "name@address" text

-- A table as text: its full name and its address, so a table loaded again (a new object at
-- a new address) can be told from the one we wrote.
local function TableKey(dt)
    local name, addr = "?", nil
    pcall(function() name = dt:GetFullName() end)
    pcall(function() addr = dt:GetAddress() end)
    return name .. "@" .. tostring(addr)
end

local function TableKeys(family)
    local keys = {}
    for _, dt in ipairs(family) do keys[#keys + 1] = TableKey(dt) end
    return table.concat(keys, ", ")
end

-- Rescales every enemy row (and bosses too, if withBosses) by mode, a, b, as in ScaledLevel,
-- with the tuning knobs of ScaledStats. `bossBand` ({ a, b, knobs }) gives bosses their own band
-- and knobs. A knobs table's `mrpLift` (levels, optional) pays battle MRP as if the band were
-- that many levels higher, so a band set under the party's level does not cut MRP.
-- mode "off" restores the originals. Returns how many
-- rows changed, one sample line (the first enemy that changed) for the log, a line per changed
-- row (for scale.txt), and how many rows something else had changed since our last write
-- (their values became the new originals).
function G.ScaleEnemies(mode, a, b, withBosses, knobs, bossBand)
    local family = TableFamily(Find(UNIT_TABLE))
    if #family == 0 then return nil, "DT_UnitParameter not loaded" end
    local changed, sample, lines, gameChanged = 0, nil, {}, 0
    local wanted, mrpLevels = {}, {}
    local bossUnits, arenaUnits = BossUnitIds()
    local fields = { "Level" }
    for _, k in ipairs(GROWTH_ORDER) do fields[#fields + 1] = k end
    for _, dt in ipairs(family) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                local okRow, err = pcall(function()
                    local cat = Int(row.Category)
                    local id = Int(row.ID)
                    local isBoss = cat == CATEGORY_BOSS
                        or (cat == CATEGORY_ENEMY and (bossUnits[id] == true or arenaUnits[id] == true))
                    -- "off" puts every row back, bosses too: the seed's own "off" passes no withBosses.
                    if not ((cat == CATEGORY_ENEMY and not isBoss) or ((withBosses or mode == "off") and isBoss)) then return end
                    local now = {}
                    for _, k in ipairs(fields) do now[k] = Int(row[k]) or 0 end
                    local orig = scaleOriginals[id]
                    local wrote = scaleWrote[id]
                    if orig and wrote then
                        for _, k in ipairs(fields) do
                            if now[k] ~= wrote[k] then orig = nil end
                        end
                        if not orig then gameChanged = gameChanged + 1 end
                    end
                    if not orig then
                        orig = now
                        scaleOriginals[id] = orig
                    end
                    local want, mrpLevel = orig, nil
                    if mode ~= "off" then
                        local base = orig
                        if bossUnits[id] and orig.Experience == 0 then
                            base = {}
                            for k, v in pairs(orig) do base[k] = v end
                            base.Experience = math.floor(BOSS_EXP * G.CurveRatio("Experience", BOSS_EXP_LEVEL, orig.Level) + 0.5)
                        end
                        local band = (isBoss and bossBand) or { a = a, b = b, knobs = knobs }
                        want = G.ScaledStats(base, G.ScaledLevel(orig.Level, mode, band.a, band.b), band.knobs,
                                             isBoss and G.BOSS_CURVE or nil)
                        local lift = band.knobs and band.knobs.mrpLift or 0
                        if lift > 0 then
                            mrpLevel = G.ScaledLevel(orig.Level, mode, band.a + lift, band.b and (band.b + lift))
                        end
                    end
                    wanted[id] = want.Level
                    mrpLevels[id] = mrpLevel or want.Level
                    local diff = false
                    for _, k in ipairs(fields) do
                        if now[k] ~= want[k] then
                            row[k] = want[k]
                            diff = true
                        end
                    end
                    scaleWrote[id] = want
                    if diff then
                        changed = changed + 1
                        lines[#lines + 1] = string.format(
                            "%d\t%s\tlevel %d -> %d\tHP %d\tAttack %d\tIntelligence %d\tDefence %d\tMind %d\tEXP %d",
                            id, AsText(row.Name) or "?", orig.Level, Int(row.Level) or -1, Int(row.MaxHitPoint) or -1,
                            Int(row.Attack) or -1, Int(row.Intelligence) or -1, Int(row.Defence) or -1,
                            Int(row.Mind) or -1, Int(row.Experience) or -1)
                        if not sample then
                            sample = string.format("%s (%d): level %d -> %d, HP %d -> %d, Attack %d -> %d, EXP %d -> %d",
                                AsText(row.Name) or "?", id, orig.Level, Int(row.Level) or -1, orig.MaxHitPoint,
                                Int(row.MaxHitPoint) or -1, orig.Attack, Int(row.Attack) or -1,
                                orig.Experience, Int(row.Experience) or -1)
                        end
                    end
                end)
                if not okRow then sample = sample or ("row error: " .. tostring(err)) end
            end)
        end)
    end
    local groups = ScaleBattleGroups(mode, mrpLevels)
    if groups > 0 then sample = (sample and (sample .. "; ") or "") .. "MRP changed in " .. groups .. " battle groups" end
    local bossCount, arenaCount = 0, 0
    for _ in pairs(bossUnits) do bossCount = bossCount + 1 end
    for _ in pairs(arenaUnits) do arenaCount = arenaCount + 1 end
    sample = (sample and (sample .. "; ") or "") .. bossCount .. " units in boss groups, " .. arenaCount .. " in the Arena"
    if mode == "off" then scaleWanted, scaleTables = nil, nil
    else scaleWanted, scaleTables = wanted, TableKeys(family) end
    return changed, sample, lines, gameChanged
end

-- Verify whether DT_UnitParameter still matches what the last rescale wrote (detecting table reloads
-- or overwrites by other mods). Returns checked count, mismatch count, one sample, and reload flag;
-- nil if no rescale is active or the table is unloaded.
function G.ScaleCheck()
    if not scaleWanted then return nil, "no rescale in force" end
    local family = TableFamily(Find(UNIT_TABLE))
    if #family == 0 then return nil, "DT_UnitParameter not loaded" end
    local checked, differ, sample = 0, 0, nil
    for _, dt in ipairs(family) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                pcall(function()
                    local id = Int(row.ID)
                    local want = id and scaleWanted[id]
                    if not want then return end
                    checked = checked + 1
                    local lv = Int(row.Level)
                    if lv ~= want then
                        differ = differ + 1
                        sample = sample or string.format("%s (%d): level %s, HP %s, wrote level %d", AsText(row.Name) or "?",
                            id, tostring(lv), tostring(Int(row.MaxHitPoint)), want)
                    end
                end)
            end)
        end)
    end
    return checked, differ, sample, TableKeys(family) ~= scaleTables
end

-- The rows of one unit (by id, or by a piece of its name) in every unit table loaded, not only
-- the one at UNIT_TABLE: a second copy of the table would explain a battle that ignores our
-- rewrite. Returns lines of text: the table, then the row's level and stats, and what the last
-- rescale wanted.
function G.UnitRows(what)
    local id = tonumber(what)
    local needle = (not id) and tostring(what or ""):lower() or nil
    local tables, seen = {}, {}
    local function add(dt)
        if dt and Alive(dt) then
            local k = TableKey(dt)
            if not seen[k] then seen[k] = true; tables[#tables + 1] = dt end
        end
    end
    for _, dt in ipairs(TableFamily(Find(UNIT_TABLE))) do add(dt) end
    local ok, all = pcall(FindAllOf, "DataTable")
    for _, dt in ipairs(ok and all or {}) do
        local name = ""
        pcall(function() name = dt:GetFullName() end)
        if name:find("UnitParameter", 1, true) and not name:find("Calc", 1, true) then add(dt) end
    end
    local out = {}
    for _, dt in ipairs(tables) do
        out[#out + 1] = "table " .. TableKey(dt)
        pcall(function()
            dt:ForEachRow(function(rowName, row)
                pcall(function()
                    local rid = Int(row.ID)
                    local name = AsText(row.Name) or "?"
                    if (id and rid == id) or (needle and needle ~= "" and name:lower():find(needle, 1, true)) then
                        local orig = scaleOriginals[rid]
                        out[#out + 1] = string.format(
                            "  %d %s (row %s, category %s): level %s, HP %s, Attack %s, Intelligence %s, Defence %s; game's level %s; last rescale wanted %s",
                            rid or -1, name, RowName(rowName), tostring(Int(row.Category)), tostring(Int(row.Level)),
                            tostring(Int(row.MaxHitPoint)), tostring(Int(row.Attack)), tostring(Int(row.Intelligence)),
                            tostring(Int(row.Defence)), tostring(orig and orig.Level or Int(row.Level)),
                            tostring(scaleWanted and scaleWanted[rid] or "nothing"))
                    end
                end)
            end)
        end)
    end
    if #tables == 0 then out[1] = "no unit table loaded" end
    return out
end

-- The airship's spawn condition, in DT_MapAirShip (shipped: "{progress:0}>=4250", the end of
-- chapter 4). With `cond`, writes it first. Returns the condition read back, or nil and why.
local AIRSHIP_TABLE = "/Game/Datatable/Asset/Map/DT_MapAirShip.DT_MapAirShip"
G.AIRSHIP_CONDITION = "{progress:0}>=4250"
function G.AirshipCondition(cond)
    local dt = Find(AIRSHIP_TABLE)
    if not dt then return nil, "DT_MapAirShip not loaded" end
    local now, err = nil, "no row"
    pcall(function()
        dt:ForEachRow(function(_, row)
            if cond then
                local ok, e = pcall(function() row.spawnCondition = cond end)
                if not ok then err = "write failed: " .. tostring(e) end
            end
            now = AsText(row.spawnCondition)
        end)
    end)
    if now == nil then return nil, err end
    return now
end

-- Rewrites DT_MapAirShip's spawn condition for airship-as-an-item seeds (re-applied because the
-- table can reload). Off restores vanilla only over mod conditions, preserving ffrap_airship tests.
function G.AirshipItemSync(asItem)
    local want = asItem and G.AIRSHIP_ITEM_CONDITION or G.AIRSHIP_CONDITION
    local now = G.AirshipCondition()
    if now == nil or now == want or (not asItem and now ~= G.AIRSHIP_ITEM_CONDITION) then return nil end
    return G.AirshipCondition(want)
end

-- Moves the save's parked airship. While it is hidden, the game places it from here at the next
-- map change. Returns true when the place reads back.
function G.ParkAirship(x, y, z)
    local sd = G.SaveData()
    if not sd then return false end
    pcall(function()
        sd.Map.airShipLocation.X, sd.Map.airShipLocation.Y, sd.Map.airShipLocation.Z = x, y, z
        sd.Map.IsRidingAirShip = false
        sd.Map.IsAlreadySpawnAirship = true
    end)
    local readX
    pcall(function() readX = sd.Map.airShipLocation.X end)
    return readX == x
end

-- No-landing boxes. The world map has 111 BP_MapNonLandingArea_C actors, each holding a
-- CPP_MapAirShipCanNeverLandingBox with m_Condition (empty or true blocks landing). Blueprint
-- has no script; C++ CPP_MapNonLandingArea evaluates the box and condition.
-- Boxes must sit at terrain ground height (centered at Z=393, +/-700 like the Mysidia box); boxes
-- placed too high act as solid ground and let the airship land atop them.
local NOLAND_CLASS = "BP_MapNonLandingArea_C"
local NOLAND_PKG, NOLAND_NAME = "/Game/BP/Map/BP_MapNonLandingArea", "BP_MapNonLandingArea"
G.MYSIDIA_BOX_CONDITION = "{progress:0}<5020"
G.NOLAND_Z, G.NOLAND_HALF_Z = 393, 700
-- The game's three story locks, by the condition they ship with.
G.STORY_BOXES = { mysidia = "{progress:0}<5020", gronoa = "{progress:0}<6000", pharm = "{progress:0}<7020" }
G.COND_ALWAYS, G.COND_NEVER = "{progress:0}>=0", "{progress:0}<0"
local nolandSpawned = {}     -- actors spawned by the probe
local ShadowIgnoreAdd

-- The airship's list of actors its shadow ignores, or nil for any other pawn. The class is
-- checked first: the field does not exist on a pawn on foot.
local function ShadowList(pawn)
    local className = ""
    pcall(function() className = pawn:GetClass():GetFName():ToString() end)
    if not className:find("AirShip", 1, true) then return nil end
    local list
    pcall(function() list = pawn.m_ShadowDecalSphareTraceActorsToIgnore end)
    return list
end
local nolandMoved = nil      -- { actor, x, y, z, ex, ey, ez, cond } of the game's box we moved
local nolandCollision = {}   -- { actor, enabled } of boxes whose collision NoLandRefresh changed, as found
local nolandLocks = {}       -- which -> { on = bool, boxes = { { actor, cond }, ... } }: story boxes we wrote

local function BoxOf(actor)
    local box
    pcall(function() box = actor.m_pBoxComponent end)
    if box and Alive(box) then return box end
    pcall(function() box = actor.RootComponent end)
    if box and Alive(box) then return box end
    return nil
end

local function V3(v)
    if v and type(v.X) == "number" then return v.X, v.Y, v.Z end
    return nil
end

-- One box as a table: actor, name, x y z, extent ex ey ez, yaw, cond.
local function BoxInfo(actor)
    local info = { actor = actor, name = "?", cond = "" }
    pcall(function() info.name = actor:GetFName():ToString() end)
    pcall(function() info.x, info.y, info.z = V3(actor:K2_GetActorLocation()) end)
    pcall(function() info.yaw = actor:K2_GetActorRotation().Yaw end)
    local box = BoxOf(actor)
    if box then
        pcall(function() info.ex, info.ey, info.ez = V3(box:GetUnscaledBoxExtent()) end)
        if not info.ex then pcall(function() info.ex, info.ey, info.ez = V3(box.BoxExtent) end) end
    end
    pcall(function() info.cond = AsText(actor.m_Condition) or "" end)
    return info
end

local function BoxLine(i)
    return string.format("%s at (%.0f, %.0f, %.0f) half-size (%s, %s, %s) yaw %s, condition \"%s\"",
        i.name, i.x or 0, i.y or 0, i.z or 0, tostring(i.ex and math.floor(i.ex)), tostring(i.ey and math.floor(i.ey)),
        tostring(i.ez and math.floor(i.ez)), tostring(i.yaw and math.floor(i.yaw)), tostring(i.cond))
end
G.NoLandLine = BoxLine

-- Format a no-landing box's collision state: actor enabled, ECollisionEnabled (0 none, 1 query,
-- 2 physics, 3 both), profile/object type, and channel responses (0 ignore, 1 overlap, 2 block).
local COLLISION_CHANNELS = { 0, 1, 2, 3, 4, 5, 6, 7, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31 }
function G.NoLandCollision(i)
    local actor = i.actor
    local box = actor and BoxOf(actor)
    if not box then return "no box component" end
    local actorOn, enabled, profile, objType, hidden = "?", "?", "?", "?", "?"
    pcall(function() actorOn = tostring(actor:GetActorEnableCollision()) end)
    pcall(function() enabled = tostring(Int(box:GetCollisionEnabled())) end)
    pcall(function() profile = box:GetCollisionProfileName():ToString() end)
    pcall(function() objType = tostring(Int(box:GetCollisionObjectType())) end)
    pcall(function() hidden = tostring(box.bHiddenInGame) end)
    local low, high = {}, {}
    for _, ch in ipairs(COLLISION_CHANNELS) do
        local r = "?"
        pcall(function() r = tostring(Int(box:GetCollisionResponseToChannel(ch))) end)
        if ch < 14 then low[#low + 1] = r else high[#high + 1] = r end
    end
    return string.format("collision: actor %s, enabled %s, profile %s, object type %s, channels 0-7 %s, 14-31 %s, hidden %s",
        actorOn, enabled, profile, objType, table.concat(low), table.concat(high), hidden)
end

-- Every no-landing box on the loaded map, as BoxInfo tables.
function G.NoLandBoxes()
    local out = {}
    local ok, all = pcall(FindAllOf, NOLAND_CLASS)
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then out[#out + 1] = BoxInfo(a) end
    end
    return out
end

-- Whether the point (x, y) is inside the box `i` seen from above (the box turned by its yaw).
-- Pure.
function G.BoxHolds(i, x, y)
    if not (i.x and i.ex and i.ey) then return false end
    local r = math.rad(-(i.yaw or 0))
    local dx, dy = x - i.x, y - i.y
    local lx = dx * math.cos(r) - dy * math.sin(r)
    local ly = dx * math.sin(r) + dy * math.cos(r)
    return math.abs(lx) <= i.ex and math.abs(ly) <= i.ey
end

-- The boxes under the player (seen from above), and the player's pose.
function G.NoLandHere()
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local out = {}
    for _, i in ipairs(G.NoLandBoxes()) do
        if G.BoxHolds(i, pose.x, pose.y) then out[#out + 1] = i end
    end
    return out, pose
end

-- Line trace down on the Visibility channel from the player (ignoring player/airship) to inspect
-- all overlapping no-landing boxes and ground height (useful where high terrain buries default Z bounds).
local TRACE_DOWN_TO = -20000
local TRACE_MAX_HITS = 4
function G.GroundUnder()
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local ksl = Find("/Script/Engine.Default__KismetSystemLibrary")
    if not ksl then return nil, "KismetSystemLibrary not found" end
    local boxes = {}
    for _, i in ipairs(G.NoLandBoxes()) do boxes[i.name] = i end
    local hits, fromZ = {}, pose.z
    for _ = 1, TRACE_MAX_HITS do
        local hit, okHit = {}, false
        gateStep("noland: LineTraceSingle from z " .. math.floor(fromZ))
        local okCall, err = pcall(function()
            okHit = ksl:LineTraceSingle(pose.pawn, { X = pose.x, Y = pose.y, Z = fromZ },
                { X = pose.x, Y = pose.y, Z = TRACE_DOWN_TO }, 0, false, {}, 0, hit, true,
                { R = 0, G = 0, B = 0, A = 0 }, { R = 0, G = 0, B = 0, A = 0 }, 0.0)
        end)
        if not okCall then return nil, "LineTraceSingle failed: " .. tostring(err) end
        if not okHit then break end
        -- Trace returns the hit component, so identify boxes via their owning actor's name.
        local name, z, hitObj = "?", nil, nil
        pcall(function() hitObj = hit.HitObjectHandle.ReferenceObject:Get() end)
        pcall(function() name = hitObj:GetFName():ToString() end)
        pcall(function() name = hitObj:GetOwner():GetFName():ToString() end)
        pcall(function() z = hit.ImpactPoint.Z end)
        if type(z) ~= "number" then break end
        local box = boxes[name]
        hits[#hits + 1] = { name = name, z = z, box = box ~= nil }
        if not (box and box.z and box.ez) then break end
        fromZ = box.z - box.ez - 1
    end
    return hits
end

-- Puts a box at (x, y, z) with half-size (hx, hy, hz) and the condition `cond`. Each step goes
-- to the trace (G.gateTrace) before it runs. Returns the box read back.
local function PlaceBox(actor, x, y, z, hx, hy, hz, cond)
    local box = BoxOf(actor)
    if not box then return nil, "no box component" end
    gateStep("noland: K2_SetActorLocation")
    pcall(function() actor:K2_SetActorLocation({ X = x, Y = y, Z = z }, false, {}, true) end)
    gateStep("noland: K2_SetActorRotation")
    pcall(function() actor:K2_SetActorRotation({ Pitch = 0.0, Yaw = 0.0, Roll = 0.0 }, true) end)
    gateStep("noland: SetBoxExtent")
    local okExt, e = pcall(function() box:SetBoxExtent({ X = hx, Y = hy, Z = hz }, true) end)
    if not okExt then return nil, "SetBoxExtent failed: " .. tostring(e) end
    if cond then
        gateStep("noland: write m_Condition")
        local okC, ce = pcall(function() actor.m_Condition = cond end)
        if not okC then return BoxInfo(actor), "m_Condition write failed: " .. tostring(ce) end
    end
    return BoxInfo(actor)
end

-- Adds spawned boxes to the airship shadow trace ignore list (`m_ShadowDecalSphareTraceActorsToIgnore`),
-- which makes the airship's red no-landing shadow render over them while blocking landing.
-- Returns before/after list sizes, non-vanilla entries, and null entry count (nil if not on airship).
ShadowIgnoreAdd = function(pawn, actors)
    actors = actors or nolandSpawned
    local list = ShadowList(pawn)
    if not list then return nil end
    local before = #list
    local listed, ours = {}, {}
    for i = 1, before do listed[ObjText(list[i])] = true end
    for _, a in ipairs(actors) do
        if Alive(a) then
            local name = ObjText(a)
            ours[name] = true
            if not listed[name] then
                local n = #list
                gateStep("noland: add to the shadow's ignore list")
                pcall(function()
                    local _ = list[n + 1]    -- reading one past the end grows a UE4SS TArray
                    list[n + 1] = a
                end)
            end
        end
    end
    local names, nulls = {}, 0
    for i = 1, #list do
        local name = ObjText(list[i])
        if name == NULL_OBJECT then
            nulls = nulls + 1
        elseif ours[name] or not name:find("^BP_MapNonLandingArea_C_") then
            names[#names + 1] = name
        end
    end
    return before, #list, names, nulls
end

-- Spawns a no-landing box under the player: `half` across each way (default 2000), 1400 tall,
-- top at `top` (default 1093, raised above GroundUnder when terrain is elevated). Returns box or nil, why.
function G.NoLandSpawn(half, top)
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local cls = LoadBlueprintClass(NOLAND_PKG, NOLAND_NAME)
    if not cls then return nil, "could not load " .. NOLAND_NAME .. "_C" end
    local z = (top or (G.NOLAND_Z + G.NOLAND_HALF_Z)) - G.NOLAND_HALF_Z
    gateStep("noland: SpawnActor")
    local actor
    pcall(function() actor = pose.world:SpawnActor(cls, { X = pose.x, Y = pose.y, Z = z }, { Pitch = 0, Yaw = 0, Roll = 0 }) end)
    if not (actor and Alive(actor)) then return nil, "SpawnActor failed" end
    nolandSpawned[#nolandSpawned + 1] = actor
    half = half or 2000
    local box, problem = PlaceBox(actor, pose.x, pose.y, z, half, half, G.NOLAND_HALF_Z, nil)
    ShadowIgnoreAdd(pose.pawn)   -- keep the airship shadow visible over the spawned box
    return box, problem
end

-- Moves the game's own Mysidia box (the one with condition {progress:0}<5020) under the
-- player, with half-size `half`, its own height and an empty condition. Keeps where it was,
-- for NoLandOff.
function G.NoLandMove(half)
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local target = nolandMoved and nolandMoved.actor
    if not (target and Alive(target)) then
        target = nil
        for _, i in ipairs(G.NoLandBoxes()) do
            if i.cond == G.MYSIDIA_BOX_CONDITION then target = i.actor; nolandMoved = i; break end
        end
    end
    if not target then return nil, "the Mysidia box (condition " .. G.MYSIDIA_BOX_CONDITION .. ") is not on this map" end
    half = half or 2000
    return PlaceBox(target, pose.x, pose.y, nolandMoved.z or G.NOLAND_Z, half, half, nolandMoved.ez or G.NOLAND_HALF_Z, "")
end

-- Set spawned no-landing box collision response for a channel (0 ignore, 1 overlap, 2 block).
function G.NoLandChannel(channel, response)
    local n = 0
    for _, a in ipairs(nolandSpawned) do
        local box = Alive(a) and BoxOf(a)
        if box then
            gateStep("noland: SetCollisionResponseToChannel " .. channel .. " " .. response)
            if pcall(function() box:SetCollisionResponseToChannel(channel, response) end) then n = n + 1 end
        end
    end
    return n
end

-- Writes `cond` into every box the probe spawned or moved. Returns how many, and the last one.
function G.NoLandCondition(cond)
    local n, last, err = 0, nil, nil
    local all = {}
    for _, a in ipairs(nolandSpawned) do all[#all + 1] = a end
    if nolandMoved then all[#all + 1] = nolandMoved.actor end
    for _, a in ipairs(all) do
        if Alive(a) then
            gateStep("noland: write m_Condition")
            local ok, e = pcall(function() a.m_Condition = cond end)
            if ok then n = n + 1 else err = tostring(e) end
            last = BoxInfo(a)
        end
    end
    return n, last, err
end

-- One of the game's story boxes (mysidia, gronoa or pharm) locked (on: its condition always
-- holds, so no landing) or unlocked (it never holds). The box stays where the game put it.
-- Returns the box read back, or nil and why.
-- Rewrites every box carrying that story condition (some areas have multiple boxes). Returns box list, or nil and why.
function G.NoLandLock(which, on)
    local orig = G.STORY_BOXES[which]
    if not orig then return nil, "no story box called " .. tostring(which) .. " (mysidia, gronoa, pharm)" end
    local rec = nolandLocks[which]
    local live = rec and #rec.boxes > 0
    for _, b in ipairs(rec and rec.boxes or {}) do
        if not Alive(b.actor) then live = false end
    end
    if not live then
        rec = { boxes = {} }
        for _, i in ipairs(G.NoLandBoxes()) do
            if i.cond == orig then rec.boxes[#rec.boxes + 1] = { actor = i.actor, cond = orig } end
        end
        if #rec.boxes == 0 then return nil, "the " .. which .. " box (condition " .. orig .. ") is not on this map" end
        nolandLocks[which] = rec
    end
    rec.on = on
    local want = on and G.COND_ALWAYS or G.COND_NEVER
    local out, err = {}, nil
    for _, b in ipairs(rec.boxes) do
        gateStep("noland: write m_Condition")
        local ok, e = pcall(function() b.actor.m_Condition = want end)
        if not ok then err = "m_Condition write failed: " .. tostring(e) end
        out[#out + 1] = BoxInfo(b.actor)
    end
    return out, err
end

-- Immediately update box collision for modified boxes to match their written conditions (COND_ALWAYS
-- or "" enables collision, COND_NEVER disables it; untouched boxes are skipped). Returns counts and collision flag.
function G.NoLandRefresh()
    local onType
    for _, i in ipairs(G.NoLandBoxes()) do
        if i.cond == "" then
            local b = BoxOf(i.actor)
            pcall(function() onType = Int(b:GetCollisionEnabled()) end)
            if onType and onType > 0 then break end
            onType = nil
        end
    end
    onType = onType or 1
    local targets = {}
    for _, a in ipairs(nolandSpawned) do targets[#targets + 1] = a end
    if nolandMoved then targets[#targets + 1] = nolandMoved.actor end
    for _, rec in pairs(nolandLocks) do
        for _, b in ipairs(rec.boxes) do targets[#targets + 1] = b.actor end
    end
    local nOn, nOff = 0, 0
    for _, a in ipairs(targets) do
        if Alive(a) then
            local cond = BoxInfo(a).cond
            local want = nil
            if cond == "" or cond == G.COND_ALWAYS then want = onType elseif cond == G.COND_NEVER then want = 0 end
            local box = BoxOf(a)
            if want and box then
                local was
                pcall(function() was = Int(box:GetCollisionEnabled()) end)
                local known = false
                for _, c in ipairs(nolandCollision) do if c.actor == a then known = true end end
                if not known and was then nolandCollision[#nolandCollision + 1] = { actor = a, enabled = was } end
                gateStep("noland: SetCollisionEnabled " .. want)
                if pcall(function() box:SetCollisionEnabled(want) end) then
                    if want > 0 then nOn = nOn + 1 else nOff = nOff + 1 end
                end
            end
        end
    end
    return nOn, nOff, onType
end

-- Draws the boxes (on) or hides them again. A box component is a shape, and shapes draw
-- their outline when not hidden in game; whether this build draws them is the probe. The
-- line width is a plain float field, written before the component is shown. Returns how many.
function G.NoLandShow(on, width)
    local n = 0
    for _, i in ipairs(G.NoLandBoxes()) do
        local box = BoxOf(i.actor)
        if box then
            if on then
                gateStep("noland: LineThickness")
                pcall(function() box.LineThickness = width or 40.0 end)
            end
            gateStep("noland: SetHiddenInGame")
            if pcall(function() box:SetHiddenInGame(not on, false) end) then n = n + 1 end
        end
    end
    return n
end

-- Re-adds any spawned boxes missing from the active airship's m_ShadowDecalSphareTraceActorsToIgnore
-- list (e.g. after boarding). Returns as ShadowIgnoreAdd, or nil and why.
function G.NoLandShadow()
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local before, after, names = ShadowIgnoreAdd(pose.pawn)
    if not before then return nil, "the player is not riding the airship" end
    return before, after, names
end

-- -------------------------------------------------------------------------------------------
-- Continent locks (docs/open_world.md, section 4)
-- -------------------------------------------------------------------------------------------
-- The airship cannot land on a locked continent. Each continent is covered by our own no-landing
-- boxes, drawn by hand on a map of the game's landscape tiles, landing points and exits so that
-- each of those lies in exactly one continent (a test checks this). Boxes are (x0, y0, x1, y1).
-- The seas between continents take the slack, as the airship cannot land on water anyway. The
-- Crystal Tower's exit is in no box.
-- Boxes on the airship's shadow ignore list show the red no-landing shadow and block landing across
-- boarding; map transitions destroy spawned boxes, so ContinentSync re-creates them on world-map loads.
-- Each continent lock maps to an unused event flag (1420-1429; off = locked, on = open).
-- Round 77: Grandshelt's own landscape reaches south to y 16367 at x 12782 to 15373, the land at
-- the north end of the stone bridge (13684, 16599) with World Map Shiny 127. It was in Lanzelt's
-- box, so a player landed there without Grandshelt's unlock. Grandshelt now starts at y 16700 there.
G.WORLD_MAP = 1000
G.CONTINENTS = {
    { name = "grandshelt", flag = 1420, boxes = { { 8400, 17500, 20600, 24000 }, { 12700, 16700, 15400, 17500 } } },
    { name = "lanzelt", flag = 1421, boxes = { { 7050, 9050, 18200, 13650 }, { 8400, 13650, 18200, 16700 }, { 10350, 8300, 18200, 9050 }, { 8400, 16700, 12700, 17500 }, { 15400, 16700, 18200, 17500 } } },
    { name = "kolobos", flag = 1422, boxes = { { 1860, 9700, 7000, 13650 }, { 1860, 13650, 8350, 20200 } } },
    { name = "dirnado", flag = 1423, boxes = { { 10350, -3600, 23100, 6400 } } },
    { name = "olderion", flag = 1424, boxes = { { -3300, -5050, 10300, 8950 }, { -3300, -7400, 3300, -5050 }, { -6120, -2650, -3300, 6050 } } },
    { name = "zoldaad", flag = 1425, boxes = { { -17100, 6100, -6200, 22200 }, { -6200, 9000, 1300, 22200 }, { -6200, 6100, -3300, 9000 } } },
    { name = "mysidia", flag = 1426, boxes = { { -20400, -13900, -14200, -1600 } } },
    { name = "gronoa", flag = 1427, boxes = { { 6700, -16000, 24600, -5100 }, { 10350, -5100, 24600, -3650 }, { 8950, -23600, 24600, -16000 } } },
    { name = "pharm", flag = 1428, boxes = { { -12750, -12300, -6200, 1000 }, { -12750, -22200, 3800, -12300 }, { 3800, -18950, 8950, -16000 } } },
    { name = "ardra", flag = 1429, boxes = { { -23900, 15700, -18600, 22300 } } },
}

-- The placed boxes, by continent name. Good only for the world in continentWorld: the player
-- controller's name is new on every map load, and a pointer into an unloaded map must not be
-- touched, so a new name means forgetting them all without asking them anything.
local continentActors, continentWorld, continentListed = {}, nil, nil
local continentListedLength, continentSeen, continentFresh = nil, 0, false
-- The walking crossings' blockers (G.CrossingSync), by index in the list given, and the world
-- they were placed in. One table, as the main chunk is at Lua's limit of 200 locals.
local crossing = { actors = {}, world = nil }
-- Sync passes that must observe an active controller before placing boxes (world-map arrival settles
-- before actors persist).
G.CONTINENT_SETTLE = 3

local function ContinentNamed(name)
    for _, c in ipairs(G.CONTINENTS) do
        if c.name == name then return c end
    end
    return nil
end

local function DestroyContinent(name)
    for _, a in ipairs(continentActors[name] or {}) do
        if Alive(a) then pcall(function() a:K2_DestroyActor() end) end
    end
    continentActors[name] = nil
end

-- Spawns one continent's boxes. Returns the actors, or nil and why; a partial set is removed.
local function PlaceContinent(world, cls, c)
    local list = {}
    local function give_up(why)
        for _, a in ipairs(list) do pcall(function() a:K2_DestroyActor() end) end
        return nil, why
    end
    for _, b in ipairs(c.boxes) do
        local cx, cy, hx, hy = (b[1] + b[3]) / 2, (b[2] + b[4]) / 2, (b[3] - b[1]) / 2, (b[4] - b[2]) / 2
        local actor
        gateStep("locks: SpawnActor " .. c.name)
        pcall(function() actor = world:SpawnActor(cls, { X = cx, Y = cy, Z = G.NOLAND_Z }, { Pitch = 0, Yaw = 0, Roll = 0 }) end)
        if not (actor and Alive(actor)) then return give_up("SpawnActor failed for " .. c.name) end
        list[#list + 1] = actor
        local placed, why = PlaceBox(actor, cx, cy, G.NOLAND_Z, hx, hy, G.NOLAND_HALF_Z, nil)
        if not placed then return give_up(c.name .. ": " .. tostring(why)) end
    end
    return list
end

-- A box set for every locked continent, none for an open one, in `world`. Returns the names
-- placed and the names removed, or nil and why.
local function PlaceLocked(world)
    local placed, removed, cls = {}, {}, nil
    for _, c in ipairs(G.CONTINENTS) do
        local open = G.GetFlag(c.flag)
        if open == true then
            if continentActors[c.name] then
                DestroyContinent(c.name)
                removed[#removed + 1] = c.name
            end
        elseif open == false then
            local have, whole = continentActors[c.name], continentActors[c.name] ~= nil
            for _, a in ipairs(have or {}) do whole = whole and Alive(a) end
            if not whole then
                DestroyContinent(c.name)
                cls = cls or LoadBlueprintClass(NOLAND_PKG, NOLAND_NAME)
                if not cls then return nil, "could not load " .. NOLAND_NAME .. "_C" end
                local list, why = PlaceContinent(world, cls, c)
                if not list then return nil, why end
                continentActors[c.name] = list
                placed[#placed + 1] = c.name
            end
        end
    end
    return placed, removed
end

-- Runs from the LoadMap post-hook so boxes are placed before frame 1 when loading a save mid-air.
-- Any map transition clears previously spawned boxes; when `place` is false, only clears tracking.
-- Returns as PlaceLocked, or nil and why.
G.WORLD_LEVEL = "Wld_PL"
function G.ContinentMapLoaded(world, place)
    continentActors, continentListed, continentListedLength = {}, nil, nil
    crossing.actors, crossing.world = {}, nil
    continentFresh, continentSeen = true, G.CONTINENT_SETTLE
    if not place then return nil, "locks off" end
    if ObjText(world) ~= G.WORLD_LEVEL then return nil, "not the world map" end
    return PlaceLocked(world)
end

-- Makes the world match the save: a box set for every locked continent, none for an open one,
-- every box on the airship's shadow list. Safe to call often. Does nothing off the world map.
-- The load hook does the first placing; this repairs anything that differs afterwards.
-- Returns the names placed and the names removed (either can be empty) and, when the boxes went
-- on the airship's shadow list, a line about that; or nil and why.
function G.ContinentSync()
    if G.CurrentMap() ~= G.WORLD_MAP then return nil, "not on the world map" end
    local pose, whyPose = G.PlayerPose()
    if not pose then return nil, whyPose end
    local pc = PlayerController()
    local world = pc and ObjText(pc)
    if not world then return nil, "no PlayerController" end
    if world ~= continentWorld then
        if continentFresh then
            continentWorld, continentFresh = world, false   -- the boxes the hook placed belong to this one
        else
            continentWorld, continentActors, continentListed, continentListedLength, continentSeen = world, {}, nil, nil, 0
        end
    end
    continentSeen = continentSeen + 1
    if continentSeen < G.CONTINENT_SETTLE then return {}, {} end
    local placed, removed = PlaceLocked(pose.world)
    if not placed then return nil, removed end
    local all = {}
    for _, list in pairs(continentActors) do
        for _, a in ipairs(list) do all[#all + 1] = a end
    end
    -- A pawn's list is read each time: boarding can make a new airship, or the game can fill it
    -- again, and only its length is cheap to compare.
    local key, line = ObjText(pose.pawn) .. ":" .. #all, nil
    local list = ShadowList(pose.pawn)
    if #all > 0 and list and (key ~= continentListed or #list ~= continentListedLength) then
        local before, after, _, nulls = ShadowIgnoreAdd(pose.pawn, all)
        if before then
            continentListed, continentListedLength = key, after
            line = string.format("%d boxes on the airship's shadow list (%d -> %d, %d null)", #all, before, after, nulls)
        end
    end
    return placed, removed, line
end

-- Removes every lock box from the world, for `ffrap_lock off`. The saves' flags are left alone.
function G.ContinentClear()
    for name in pairs(continentActors) do DestroyContinent(name) end
    continentActors, continentListed = {}, nil
    G.CrossingClear()
end

-- Removes every crossing blocker; the next CrossingSync places them again from its list.
function G.CrossingClear()
    for _, a in pairs(crossing.actors) do
        if Alive(a) then pcall(function() a:K2_DestroyActor() end) end
    end
    crossing.actors = {}
end

-- Opens or closes one continent, or "all", in the loaded save. Returns how many, or nil and why.
function G.SetContinentOpen(name, open)
    local sd = G.SaveData()
    if not sd then return nil, "no save loaded" end
    local chosen = {}
    if name == "all" then
        chosen = G.CONTINENTS
    else
        local c = ContinentNamed(name)
        if not c then return nil, "no continent named " .. tostring(name) end
        chosen = { c }
    end
    local flags = {}
    for _, c in ipairs(chosen) do flags[#flags + 1] = c.flag end
    local found, bad = SetFlags(sd, open and flags or {}, open and {} or flags)
    if not found or #bad > 0 then return nil, "could not write flags " .. table.concat(bad, " ") end
    return #chosen
end

-- The locks as text, for the log.
function G.ContinentStatus()
    local opened, locked, boxes = {}, {}, 0
    for _, c in ipairs(G.CONTINENTS) do
        local list = G.GetFlag(c.flag) == true and opened or locked
        list[#list + 1] = c.name
        boxes = boxes + #(continentActors[c.name] or {})
    end
    return string.format("open [%s]; locked [%s]; %d boxes placed", table.concat(opened, ", "), table.concat(locked, ", "), boxes)
end

function G.ContinentOpen(name)
    local c = ContinentNamed(name)
    return c ~= nil and G.GetFlag(c.flag) == true
end

function G.IsContinent(name)
    return ContinentNamed(name) ~= nil
end

-- -------------------------------------------------------------------------------------------
-- Walking crossings and the ferry (docs/open_world.md, section 4)
-- -------------------------------------------------------------------------------------------
-- Landing locks only block the airship; on foot, world-map bridges/ferries link continents (`a`, `b`,
-- `x`, `y`, `z`, `yaw`, `scale`) and stay blocked while either continent is locked. main.lua passes
-- crossings.txt when present, otherwise G.CROSSINGS. Stone bridges are landscape geometry (+X north),
-- not actors, so coordinates reflect in-game placement via ffrap_gate.
G.CROSSINGS = {
    { a = "grandshelt", b = "lanzelt", x = 13684, y = 16599, z = 87, yaw = 90.0, scale = 1.5 },
    { a = "lanzelt", b = "kolobos", x = 7834, y = 13928, z = 61, yaw = 90.0, scale = 1.5 },
}

-- Places a blocker for every crossing with a locked side and removes the rest. Runs only once the
-- world map has settled (as the landing locks do). Returns the number placed and removed, or nil
-- and why.
function G.CrossingSync(list)
    if G.CurrentMap() ~= G.WORLD_MAP then return nil, "not on the world map" end
    if continentSeen < G.CONTINENT_SETTLE or not continentWorld then return nil, "settling" end
    if crossing.world ~= continentWorld then crossing.actors, crossing.world = {}, continentWorld end
    local pose, why = G.PlayerPose()
    if not pose then return nil, why end
    local placed, removed = 0, 0
    for i, c in ipairs(list) do
        local open = G.ContinentOpen(c.a) and G.ContinentOpen(c.b)
        local actor = crossing.actors[i]
        if actor and not Alive(actor) then actor = nil end
        if open and actor then
            gateStep("crossing: destroy " .. c.a .. "-" .. c.b)
            pcall(function() actor:K2_DestroyActor() end)
            actor = nil
            removed = removed + 1
        elseif not open and not actor then
            local spawned, whySpawn = G.SpawnBlocker(pose.world, GATE_SPECS.world[1], { X = c.x, Y = c.y, Z = c.z },
                { Pitch = 0.0, Yaw = c.yaw, Roll = 0.0 }, c.scale)
            if not spawned then return nil, "crossing " .. c.a .. "-" .. c.b .. ": " .. tostring(whySpawn) end
            actor = spawned
            placed = placed + 1
        end
        crossing.actors[i] = actor
    end
    return placed, removed
end

-- The nearest crossing with a locked side within `range` of the player, and the names of its
-- locked sides; or nil.
function G.CrossingNear(list, range)
    local pose = G.PlayerPose()
    if not pose or G.CurrentMap() ~= G.WORLD_MAP then return nil end
    local best, bestD = nil, range
    for _, c in ipairs(list) do
        local d = math.sqrt((pose.x - c.x) ^ 2 + (pose.y - c.y) ^ 2)
        if d < bestD and not (G.ContinentOpen(c.a) and G.ContinentOpen(c.b)) then best, bestD = c, d end
    end
    if not best then return nil end
    local locked = {}
    for _, side in ipairs({ best.a, best.b }) do
        if not G.ContinentOpen(side) then locked[#locked + 1] = side end
    end
    return best, locked, bestD
end

-- The ferry joins Grandport Harbor (Lanzelt), Dirnado, Olderion and Zoldaad. Past story 3210
-- each port's menu offers the other three. Choosing a port runs Gim_EV_ShipMovement_0N_Cushion,
-- which chains to the trip (the menu sets flag 84 to 87 for where you are, the cushion 80 to 83
-- for where you go). A port whose continent is locked gets the menu's own cancel row instead,
-- so choosing it ends the talk as "no" does.
G.FERRY_PORTS = { "lanzelt", "dirnado", "olderion", "zoldaad" }
G.FERRY_MENUS = {
    Gim_EV_ShipMovement_01_03_Choice = { ports = { 2, 3, 4 }, cancel = "Gim_EV_ShipMovement_Cancel_Gra" },
    Gim_EV_ShipMovement_02_03_Choice = { ports = { 1, 3, 4 }, cancel = "Gim_EV_ShipMovement_Cancel" },
    Gim_EV_ShipMovement_03_02_Choice = { ports = { 1, 2, 4 }, cancel = "Gim_EV_ShipMovement_Cancel" },
    Gim_EV_ShipMovement_04_01_Choice = { ports = { 1, 2, 3 }, cancel = "Gim_EV_ShipMovement_Cancel" },
}

-- Points each menu choice at its trip or at the cancel row, by the ports' continents (`allOpen`:
-- every trip, as the game has it). Safe to call often: it writes only what differs. Returns the
-- number of choices written.
function G.FerrySync(allOpen)
    local written = 0
    for _, dt in ipairs(TableFamily(Find(SHOP_TABLE))) do
        for rowName, menu in pairs(G.FERRY_MENUS) do
            local row
            pcall(function() row = dt:FindRow(rowName) end)
            if row then
                for i, port in ipairs(menu.ports) do
                    local want = (allOpen or G.ContinentOpen(G.FERRY_PORTS[port]))
                        and string.format("Gim_EV_ShipMovement_%02d_Cushion", port) or menu.cancel
                    pcall(function()
                        local entry = row.ChoicesBranchEventList[i].EventList[1]
                        if ObjText(entry.EventId) ~= want then
                            entry.EventId = FName(want)
                            written = written + 1
                        end
                    end)
                end
            end
        end
    end
    return written
end

-- Removes the spawned boxes, puts the moved one back and gives the story boxes their own
-- conditions again. Returns how many were undone.
function G.NoLandOff()
    local n = 0
    for _, a in ipairs(nolandSpawned) do
        if Alive(a) then
            gateStep("noland: K2_DestroyActor")
            pcall(function() a:K2_DestroyActor() end)
            n = n + 1
        end
    end
    nolandSpawned = {}
    local m = nolandMoved
    if m and Alive(m.actor) then
        PlaceBox(m.actor, m.x, m.y, m.z, m.ex or 2400, m.ey or 6000, m.ez or 700, m.cond)
        if m.yaw and m.yaw ~= 0 then pcall(function() m.actor:K2_SetActorRotation({ Pitch = 0.0, Yaw = m.yaw, Roll = 0.0 }, true) end) end
        n = n + 1
    end
    nolandMoved = nil
    for _, rec in pairs(nolandLocks) do
        for _, b in ipairs(rec.boxes) do
            if Alive(b.actor) then
                gateStep("noland: write m_Condition")
                pcall(function() b.actor.m_Condition = b.cond end)
                n = n + 1
            end
        end
    end
    nolandLocks = {}
    for _, c in ipairs(nolandCollision) do
        local box = Alive(c.actor) and BoxOf(c.actor)
        if box then
            gateStep("noland: SetCollisionEnabled " .. c.enabled)
            pcall(function() box:SetCollisionEnabled(c.enabled) end)
        end
    end
    nolandCollision = {}
    return n
end

-- -------------------------------------------------------------------------------------------
-- Boss fight probe (ffrap_bossfight)
-- -------------------------------------------------------------------------------------------
-- Turns nearby closed chests (via IsTrap / battleGroupId / battleFinishEventId, modifying both live
-- actor copies and table rows) and the Chamber of Arms sword pedestal (map 3290; needs Ancient
-- Greatsword and flag 901 off) into triggers for an arbitrary battle group.
-- Post-battle talk rows must point to a Sequence row so the faded battle screen fades back in
-- (otherwise the screen stays black): either the Victory row's scene or Gim_EV_Majipot_Delete_02
-- for `quiet` (flag replaced with G.BOSS_TEST_FLAG). `off` restores everything except the Victory item.
G.BOSS_TEST_FLAG = 1440       -- no condition or talk row in the game uses flags 1430 to 1449
G.BOSS_TEST_SWORD = 10198     -- the Ancient Greatsword, which the sword pedestal checks for
local BOSS_TEST_FIGHT, BOSS_TEST_VICTORY, BOSS_TEST_QUIET = "12Arms_01Sword_1stAwake_Encount", "12Arms_01Sword_1stAwake_Victory", "Gim_EV_Majipot_Delete_02"

-- Chest table rows, then the copies held by the closed chests that are loaded.
local function EachChestData(fn)
    for _, dt in ipairs(TableFamily(Find(CHEST_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(_, row) pcall(fn, row, false) end)
        end)
    end
    for _, c in ipairs(G.LiveChests()) do
        if not c.open then pcall(fn, c.actor.m_TreasureBoxData, true) end
    end
end

local function ChestKey(data) return Int(data.mapId) .. ":" .. Int(data.ID) end

function G.BossTestOff(say)
    local saved = bossTestSaved
    if not saved then return 0 end
    say("boss test: putting the tables back")
    local restored = 0
    EachTalkRow(function(key, row)
        local o = saved.talk[key]
        if not o then return end
        if o.encount then
            row.encountGroupId = o.encount
        else
            for i, flag in ipairs(o.flags) do row.OnFlagList[i] = flag end
        end
        restored = restored + 1
    end)
    EachChestData(function(data)
        local o = saved.chests[ChestKey(data)]
        if not o then return end
        data.IsTrap = o.trap
        data.battleGroupId = o.group
        data.battleFinishEventId = FName(o.finish)
        restored = restored + 1
    end)
    local f = saved.groupFields
    EachGroupRow(saved.group, function(row)
        row.battleEventId = f.start
        row.battleFinishEventId = FName(f.finish)
        row.battleFinishLoseEventId = FName(f.lose)
        row.battleFinishEscapeEventId = FName(f.escape)
        row.isResultSkipOnWin = f.skipWin
        row.isResultSkipOnLose = f.skipLose
        restored = restored + 1
    end)
    bossTestSaved = nil
    return restored
end

-- Returns true and what was written, or false and why. `say` logs each step before it runs.
function G.BossTestArm(id, say, quiet)
    G.BossTestOff(say)
    say("boss test: reading battle group " .. tostring(id))
    local fields
    EachGroupRow(id, function(row)
        fields = fields or { start = Int(row.battleEventId), finish = ObjText(row.battleFinishEventId),
            lose = ObjText(row.battleFinishLoseEventId), escape = ObjText(row.battleFinishEscapeEventId),
            skipWin = row.isResultSkipOnWin, skipLose = row.isResultSkipOnLose }
    end)
    if not fields then return false, "no battle group " .. tostring(id) end
    say(string.format("boss test: the group's own events: start %s, win %s, lose %s, escape %s", tostring(fields.start), fields.finish, fields.lose, fields.escape))

    local near = {}
    for _, c in ipairs(G.LiveChests()) do
        if not c.open and c.rowMap then near[c.rowMap .. ":" .. tostring(c.rowId)] = true end
    end
    local saved = { talk = {}, group = id, groupFields = fields, chests = {} }
    bossTestSaved = saved
    local win, fight, rows, live, group = 0, 0, 0, 0, 0
    local winRow = quiet and BOSS_TEST_QUIET or BOSS_TEST_VICTORY
    say("boss test: writing the sword pedestal's fight row and the win row, " .. winRow)
    EachTalkRow(function(key, row)
        if key == BOSS_TEST_FIGHT then
            saved.talk[key] = saved.talk[key] or { encount = Int(row.encountGroupId) }
            row.encountGroupId = id
            fight = fight + 1
        elseif key == winRow then
            if not saved.talk[key] then
                local flags = {}
                for i = 1, #row.OnFlagList do flags[i] = Int(row.OnFlagList[i]) end
                saved.talk[key] = { flags = flags }
            end
            if not quiet then row.ObtainItemList:Empty() end
            for i = 1, #row.OnFlagList do row.OnFlagList[i] = G.BOSS_TEST_FLAG end
            win = win + 1
        end
    end)
    say("boss test: making the chests near you traps")
    EachChestData(function(data, isLive)
        local key = ChestKey(data)
        if not near[key] then return end
        saved.chests[key] = saved.chests[key] or { trap = data.IsTrap, group = Int(data.battleGroupId), finish = ObjText(data.battleFinishEventId) }
        data.IsTrap = true
        data.battleGroupId = id
        data.battleFinishEventId = FName(winRow)
        if isLive then live = live + 1 else rows = rows + 1 end
    end)
    say("boss test: writing the battle group")
    EachGroupRow(id, function(row)
        BossTestWriteGroup(row, winRow)
        group = group + 1
    end)
    G.SetFlag(G.BOSS_TEST_FLAG, false)
    local count = 0
    for _ in pairs(near) do count = count + 1 end
    local detail = string.format("group %d: %d chests near you (%d table rows, %d live), %d pedestal rows, %d win rows, %d group rows",
        id, count, rows, live, fight, win, group)
    if fight == 0 or win == 0 or group == 0 then
        G.BossTestOff(say)
        return false, detail .. " (something is missing, so nothing is left changed)"
    end
    return true, detail
end

-- -------------------------------------------------------------------------------------------
-- Player settings
-- -------------------------------------------------------------------------------------------
-- EXP, gil, and MRP multipliers (DT_GameDifficultyParam) plus random encounter toggles/rates
-- (regional MAP_DATA tables and current player encounter threshold). Note: FFRS_QoL writes the same
-- fields, so turn off FFRS_QoL's versions if both mods are installed.
do
local DIFFICULTY_TABLE = "/Game/Datatable/Difficulty/DT_GameDifficultyParam.DT_GameDifficultyParam"
local SHIPPED_RATES = { Easy = { 1, 1, 1 }, Normal = { 1, 1, 1 }, Expert = { 1, 1, 1.5 } }
local NO_ENCOUNTER = 1.0e9
local mapOriginals = {}        -- "table|row" -> the row's encounter fields as first seen
local thresholdOriginals = {}  -- player full name -> encounter distance before encounters went off

local function Near(a, b) return math.abs((a or 0) - (b or 0)) < 1e-4 end

-- Returns how many difficulty rows changed.
function G.ApplyRates(exp, gil, mrp)
    local changed = 0
    for _, dt in ipairs(TableFamily(Find(DIFFICULTY_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(name, row)
                local base = SHIPPED_RATES[ObjText(name)]
                if not base then return end
                local e, g, m = base[1] * exp, base[2] * gil, base[3] * mrp
                if not (Near(row.ExpRate, e) and Near(row.MoneyRate, g) and Near(row.MRPointRate, m)) then
                    row.ExpRate, row.MoneyRate, row.MRPointRate = e, g, m
                    changed = changed + 1
                end
            end)
        end)
    end
    return changed
end

local function MapDataTables()
    local out = {}
    local ok, all = pcall(FindAllOf, "DataTable")
    for _, dt in ipairs(ok and all or {}) do
        if Alive(dt) then
            local okName, name = pcall(function() return dt:GetRowStruct():GetFName():ToString() end)
            if okName and name == "MAP_DATA" then out[#out + 1] = dt end
        end
    end
    return out
end

-- Writes the map tables. Returns how many rows changed and how many tables were found.
function G.ApplyEncounterTables(on, rate)
    local changed, tables = 0, MapDataTables()
    for _, dt in ipairs(tables) do
        local path = "?"
        pcall(function() path = dt:GetFullName() end)
        pcall(function()
            dt:ForEachRow(function(name, row)
                local key = path .. "|" .. ObjText(name)
                local o = mapOriginals[key]
                if not o then
                    o = { on = row.doMovementEncount, row.encountMinMovementLength, row.encountMaxMovementLength,
                          row.chocoboEncountMinMovementLength, row.chocoboEncountMaxMovementLength }
                    mapOriginals[key] = o
                end
                local wantOn = on and o.on
                local want = { o[1] / rate, o[2] / rate, o[3] / rate, o[4] / rate }
                if row.doMovementEncount ~= wantOn or not (Near(row.encountMinMovementLength, want[1]) and
                    Near(row.encountMaxMovementLength, want[2]) and Near(row.chocoboEncountMinMovementLength, want[3]) and
                    Near(row.chocoboEncountMaxMovementLength, want[4])) then
                    row.doMovementEncount = wantOn
                    row.encountMinMovementLength, row.encountMaxMovementLength = want[1], want[2]
                    row.chocoboEncountMinMovementLength, row.chocoboEncountMaxMovementLength = want[3], want[4]
                    changed = changed + 1
                end
            end)
        end)
    end
    return changed, #tables
end

-- The player on this map. Safe to call often. Returns how many players changed.
function G.ApplyPlayerEncounter(on)
    local changed = 0
    local ok, players = pcall(FindAllOf, "CPP_MapUnit_Playable")
    for _, p in ipairs(ok and players or {}) do
        if Alive(p) then
            pcall(function()
                local key = p:GetFullName()
                local now = p.m_EncountThresholdDistance
                if not on and now < NO_ENCOUNTER then
                    thresholdOriginals[key] = now
                    p.m_EncountThresholdDistance = NO_ENCOUNTER
                    changed = changed + 1
                elseif on and thresholdOriginals[key] then
                    if now >= NO_ENCOUNTER then p.m_EncountThresholdDistance = thresholdOriginals[key] end
                    thresholdOriginals[key] = nil
                    changed = changed + 1
                end
            end)
        end
    end
    return changed
end
end

-- Options > Gameplay custom rows in DT_OP_GameSetting. Each row uses an EntryTag copied from a
-- vanilla Slider or RadioButton so m_EntrySaveDataList (CPP_MuchaOptionSaveData) persists it; we
-- also seed missing OPTION_SAVEDATA_SETTING entries (Slider 1, RadioButton 2) because Apply only
-- updates pre-existing save entries.
do
local OPTION_GAMEPLAY = "/Game/Datatable/UI/Option/Root/GameSetting/DT_OP_GameSetting.DT_OP_GameSetting"
local OPTION_SLIDER = "Delegate.UI.System.Option.Root.GameSetting.GamePad.Sensitivity"
local OPTION_SWITCH = "Delegate.UI.System.Option.Root.GameSetting.EncountSensor"
-- Copy DT_OP_RadioButton_Difficulty choices (Casual, Normal, Expert) for scaling strength with
-- an independent EntryTag so changing it leaves the game's actual difficulty untouched.
local OPTION_CHOICE = "Delegate.UI.System.Option.Root.GameSetting.Difficulty"
local OPTION_TAG = "Delegate.UI.System.Option.Root.GameSetting.FFRAP."
G.OPTION_ROWS = {
    { key = "exp", row = "FFRAP_Exp", copy = OPTION_SLIDER, min = 1, max = 10, default = 1,
      label = "AP: EXP rate", help = "EXP from battles, as a multiple of normal." },
    { key = "gil", row = "FFRAP_Gil", copy = OPTION_SLIDER, min = 1, max = 10, default = 1,
      label = "AP: Gil rate", help = "Gil from battles, as a multiple of normal." },
    { key = "mrp", row = "FFRAP_Mrp", copy = OPTION_SLIDER, min = 1, max = 10, default = 1,
      label = "AP: MRP rate", help = "MRP from battles, as a multiple of normal." },
    { key = "encounters", row = "FFRAP_Encounters", copy = OPTION_SWITCH, default = 0,
      label = "AP: Random encounters", help = "Off: walking never starts a battle. Bosses and set battles still happen." },
    -- Slider moves in integer steps with no fractional step field, so each tick represents 0.5x
    -- (0.5-3.0). Renamed row avoids misreading old whole-rate saved values as half steps.
    { key = "encounterrate", row = "FFRAP_EncounterHalves", copy = OPTION_SLIDER, min = 1, max = 6, default = 2, step = 0.5,
      label = "AP: Encounter rate (x0.5)", help = "How often random battles come, in halves: 1 is half as often, 2 is normal, 6 is three times as often." },
    { key = "scaling", row = "FFRAP_Scaling", copy = OPTION_SWITCH, default = 0,
      label = "AP: Enemy scaling", help = "Enemies follow your party's level. Off: the game's own levels." },
    -- RadioButton labels come from referenced DT_RadioButton tables, keeping labels within UI bounds.
    { key = "strength", row = "FFRAP_ScalingStrength", copy = OPTION_CHOICE, choices = 3, default = 1,
      label = "AP: Scaling strength", help = "How strong scaled enemies and bosses are. It stacks with the game's own difficulty." },
}

local ENTRY_SLIDER, ENTRY_RADIO = 1, 2

-- The option save's entries for our tags, added where missing. `current` is setting key -> number
-- or boolean. Returns how many were added, or nil when the option save is not found.
local optionEntriesSeeded = false
local function SeedOptionEntries(current)
    local save = Live("CPP_MuchaOptionSaveData")
    if not save then return nil end
    optionEntriesSeeded = true
    local have = {}
    pcall(function()
        save.m_EntrySaveDataList:ForEach(function(k) pcall(function() have[ObjText(k:get().TagName)] = true end) end)
    end)
    local added = 0
    for _, o in ipairs(G.OPTION_ROWS) do
        local tag = OPTION_TAG .. o.row
        if not have[tag] then
            local v = current[o.key]
            local value
            if o.min then
                local steps = tonumber(v) and math.floor(tonumber(v) / (o.step or 1) + 0.5) or o.default
                value = math.min(o.max, math.max(o.min, steps))
            elseif o.choices then value = math.min(o.choices - 1, math.max(0, math.floor(tonumber(v) or o.default)))
            else value = (v == false) and 1 or 0 end
            if pcall(function()
                save.m_EntrySaveDataList:Add({ TagName = FName(tag) }, { Value = value, IsDisplay = true, Type = o.min and ENTRY_SLIDER or ENTRY_RADIO })
            end) then added = added + 1 end
        end
    end
    return added
end

-- EOP_BaseMenu_Command_ShowType. Since round 88 (the user: the settings only in the Archipelago
-- page) our rows are in the table only while the page is open: added when it opens, removed when
-- it closes (APMENU.Mode), so neither the title screen's Options nor System > Options has them.
G.SHOW_TYPE = { all = 0, title = 1, game = 2 }
function G.AddOptionRows(say, current)
    say("menu: loading " .. OPTION_GAMEPLAY)
    local dt = LoadObject(OPTION_GAMEPLAY)
    if not dt then return false, "DT_OP_GameSetting could not be loaded" end
    local templates, have, count = {}, {}, 0
    pcall(function()
        dt:ForEachRow(function(name, row)
            count = count + 1
            have[ObjText(name)] = row
            local tag
            pcall(function() tag = ObjText(row.EntryTag.TagName) end)
            if tag then templates[tag] = templates[tag] or row end
        end)
    end)
    local done, added = {}, 0
    for _, o in ipairs(G.OPTION_ROWS) do
        local row = have[o.row]
        if not row and templates[o.copy] then
            say("menu: AddRow " .. o.row)
            if pcall(function() dt:AddRow(o.row, templates[o.copy]) end) then
                pcall(function() row = dt:FindRow(o.row) end)
                added = added + 1
            end
        end
        if row then
            say("menu: writing " .. o.row)
            local ok = pcall(function()
                row.EntryTag.TagName = FName(OPTION_TAG .. o.row)
                row.DisplayText = FText(o.label)
                row.ItemDescription = FText(o.help)
                if o.min then
                    row.SliderInfo.MinValue, row.SliderInfo.MaxValue, row.SliderInfo.DefaultValue = o.min, o.max, o.default
                else
                    row.DefaultRadioButtonIndex = o.default
                end
            end)
            pcall(function() row.ShowCommandData.ShowType = G.SHOW_TYPE.all end)
            done[#done + 1] = o.row .. (ok and "" or " (write failed)")
        else
            done[#done + 1] = o.row .. " (not added)"
        end
    end
    say("menu: option save entries")
    local seeded = SeedOptionEntries(current or {})
    return true, count .. " rows before; " .. table.concat(done, ", ") .. "; " ..
        (seeded and (seeded .. " option save entries added") or "no option save found"), added
end

-- Ensure our custom Options rows are present in DT_OP_GameSetting (re-inserted whenever the game
-- reloads the table, including at the title screen). Returns rows added, or nil and reason.
function G.EnsureOptionRows(current)
    local dt = LoadObject(OPTION_GAMEPLAY)
    if not dt then return nil, "DT_OP_GameSetting could not be loaded" end
    local present = false
    pcall(function() present = dt:FindRow(G.OPTION_ROWS[1].row) ~= nil end)
    if present then
        if not optionEntriesSeeded then SeedOptionEntries(current or {}) end
        return 0
    end
    local ok, detail, added = G.AddOptionRows(function() end, current)
    if not ok then return nil, detail end
    return added, detail
end

-- Our rows' values from the option save, as setting key -> number or boolean, for the rows the
-- player has set (the game saves a row once it is applied). nil when the option save is not found.
function G.ReadOptionValues()
    local save = Live("CPP_MuchaOptionSaveData")
    if not save then return nil end
    local byTag = {}
    for _, o in ipairs(G.OPTION_ROWS) do byTag[OPTION_TAG .. o.row] = o end
    local out = {}
    pcall(function()
        save.m_EntrySaveDataList:ForEach(function(k, v)
            pcall(function()
                local o = byTag[ObjText(k:get().TagName)]
                if not o then return end
                local value = v:get().Value
                if o.min then out[o.key] = value * (o.step or 1)
                elseif o.choices then out[o.key] = math.floor(value + 0.5)
                else out[o.key] = math.floor(value + 0.5) == 0 end
            end)
        end)
    end)
    return out
end

-- Diagnostic dump for ffrap_menu dump: lists every option save object's entries and open Options
-- screen pending changes (CPP_VM_Option.ChangingOptionSetting). Returns lines.
function G.OptionDump()
    local lines = {}
    local function entries(map, label)
        local n, ours = 0, {}
        pcall(function()
            map:ForEach(function(k, v)
                n = n + 1
                local tag, value = "?", "?"
                pcall(function() tag = ObjText(k:get().TagName) end)
                pcall(function() value = tostring(v:get().Value) end)
                if tag:find("FFRAP", 1, true) or n <= 3 then ours[#ours + 1] = tag:gsub("^Delegate%.UI%.System%.Option%.Root%.", "") .. "=" .. value end
            end)
        end)
        lines[#lines + 1] = label .. ": " .. n .. " entries; " .. table.concat(ours, ", ")
    end
    for _, class in ipairs({ "CPP_MuchaOptionSaveData", "CPP_VM_Option" }) do
        local ok, all = pcall(FindAllOf, class)
        local list = ok and all or {}
        lines[#lines + 1] = class .. ": " .. #list .. " found"
        for i, o in ipairs(list) do
            if Alive(o) then
                local name = "?"
                pcall(function() name = o:GetFullName() end)
                if class == "CPP_MuchaOptionSaveData" then
                    entries(o.m_EntrySaveDataList, "  " .. i .. " " .. name)
                else
                    entries(o.ChangingOptionSetting, "  " .. i .. " " .. name .. " pending")
                end
            end
        end
    end
    return lines
end
end


-- Crystal Tower final boss lock (map 3280): disables collision on gimmick 133's interact trigger
-- (C08_Dng_10Cry_41_CanNotRetrun_01, point of no return to floor 3281) until thresholds are met.
-- Matched by gimmicks.tsv coordinates. Returns 1 if toggled, 0 if unchanged, or nil with distance info.
G.TOWER_TOP = { map = 3280, x = 15890, y = -55300, reach = 500 }
function G.SealTowerTop(sealed)
    if G.CurrentMap() ~= G.TOWER_TOP.map then return nil, "not in the Crystal Tower" end
    local ok, all = pcall(FindAllOf, "BP_MapGimmick_InteractEventTrigger_C")
    local best, bestDistance
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            local loc
            pcall(function() loc = a:K2_GetActorLocation() end)
            if loc then
                local d = math.sqrt((loc.X - G.TOWER_TOP.x) ^ 2 + (loc.Y - G.TOWER_TOP.y) ^ 2)
                if not bestDistance or d < bestDistance then best, bestDistance = a, d end
            end
        end
    end
    if not best or bestDistance > G.TOWER_TOP.reach then
        return nil, "the last climb's trigger was not found (nearest trigger " ..
            (bestDistance and string.format("%.0f away", bestDistance) or "none") .. ")"
    end
    local collides
    pcall(function() collides = best:GetActorEnableCollision() end)
    if collides == not sealed then return 0 end
    gateStep((sealed and "seal" or "open") .. " the tower's last climb")
    pcall(function() best:SetActorEnableCollision(not sealed) end)
    return 1
end

-- Mobliz Shipyard (map 3060): activate elevators 73 and 75 (disabled by default until skipped
-- chapter-2 puzzle/cutscene triggers) so open-world players can reach upper chests and shards.
-- Returns how many elevators were activated.
G.SHIPYARD_MAP = 3060
local SHIPYARD_ELEVATORS = { [73] = true, [75] = true }
local GIMMICK_ACTIVE = 0   -- eMapGimmickState: Active 0, Deactive 1
function G.WakeShipyardElevators()
    local ok, all = pcall(FindAllOf, "BP_MapGimmick_Floor_Elevator_Interact_002_C")
    local woke = 0
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            local uid, condition
            pcall(function() uid, condition = a.m_UniqueId, a.m_GimmickCondition end)
            if SHIPYARD_ELEVATORS[uid] and condition ~= GIMMICK_ACTIVE then
                gateStep("turn on shipyard elevator " .. uid)
                pcall(function() a:SetGimmickCondition(GIMMICK_ACTIVE, false) end)
                woke = woke + 1
            end
        end
    end
    return woke
end

-- Round 120 probe (ffrap_lift): Mobliz Shipyard's lift 75 is on but stands at the bottom, and
-- nothing at the top calls it. It is the only lift there with no stops and no arrival points in
-- the level. The keypad Blueprint has CallSwitch(stop, direction: Up 1, Down 2), which returns
-- false when the lift is at that stop already, and Execute_BP(stop), the keypad's own call.
-- With no `uid`, lists the keypad lifts on the map. Returns lines for the log.
G.LIFT_DIRECTIONS = { up = 1, down = 2 }
function G.LiftProbe(uid, action, stop, direction)
    local ok, all = pcall(FindAllOf, "BP_MapGimmick_Floor_Elevator_Interact_C")
    local out, me = {}, G.PlayerPose()
    for _, a in ipairs(ok and all or {}) do
        if Alive(a) then
            local id, cond, key, call, pos, points = -1, "?", "?", "?", nil, "?"
            pcall(function() id = Int(a.m_UniqueId) end)
            if not uid or id == uid then
                pcall(function() cond = tostring(Int(a.m_GimmickCondition)) end)
                pcall(function() key = tostring(Int(a.m_CurrentSplineKeyIndex)) end)
                pcall(function() call = tostring(a.m_IsCallSwitch) end)
                pcall(function() pos = a:K2_GetActorLocation() end)
                pcall(function()
                    local spline = a:GetComponentByClass(StaticFindObject("/Script/Engine.SplineComponent"))
                    points = tostring(spline:GetNumberOfSplinePoints())
                end)
                local far = (pos and me) and string.format(", %.0f from you", math.sqrt((pos.X - me.x) ^ 2 + (pos.Y - me.y) ^ 2 + (pos.Z - me.z) ^ 2)) or ""
                out[#out + 1] = string.format("lift %d (%s): condition %s, stop %s of %s points, call switch %s, at %s%s",
                    id, ClassName(a), cond, key, points, call,
                    pos and string.format("%.0f, %.0f, %.0f", pos.X, pos.Y, pos.Z) or "?", far)
                if action == "call" then
                    gateStep(string.format("lift %d: CallSwitch(%d, %d)", id, stop, direction))
                    local okCall, moved = pcall(function() return a:CallSwitch(stop, direction) end)
                    out[#out + 1] = "CallSwitch(" .. stop .. ", " .. direction .. "): " .. (okCall and tostring(moved) or ("failed: " .. tostring(moved)))
                elseif action == "exec" then
                    gateStep(string.format("lift %d: Execute_BP(%d)", id, stop))
                    local okExec, err = pcall(function() a:Execute_BP(stop) end)
                    out[#out + 1] = "Execute_BP(" .. stop .. "): " .. (okExec and "called" or ("failed: " .. tostring(err)))
                elseif action == "on" then
                    pcall(function() a:SetGimmickCondition(GIMMICK_ACTIVE, false) end)
                    out[#out + 1] = "turned on"
                end
            end
        end
    end
    if #out == 0 then out[1] = uid and ("no keypad lift " .. uid .. " on this map") or "no keypad lifts on this map" end
    return out
end

-- Round 113 (the user): a lift with m_IsSave keeps its stop (spline point index) in the save, in
-- Map.mapGimmick{map}.gimmickState{uid}, and moves only when ridden. The game puts some lifts at a
-- stop when the player arrives at a given point, not all and not at every point. In the Tower of
-- Mysidia, lift 13 goes up; a fast travel out from the top and back in by the door (point 0) left
-- it at its top, as the game resets it only at the bottom save point and from the way down. In
-- each map here the only way in from another map is the door a first visit uses (point 0). So
-- while the player is on another map, each lift is put back at its first-visit stop
-- (m_InitStepIndex), and the game's own arrival rules then run as on a first visit.
-- data/game/lifts.tsv (tools/lift_audit.py): map -> { lift uid = first-visit stop }.
G.LIFT_RESETS = {
    [3070] = { [41] = 0, [68] = 0, [69] = 0, [70] = 0, [71] = 1, [72] = 0, [73] = 0, [74] = 1 },  -- Wind Shrine
    [3110] = { [72] = 0 },                                                                          -- Water Shrine
    [3200] = { [13] = 0, [32] = 0 },                                                                -- Tower of Mysidia
    [3240] = { [14] = 0, [24] = 0 },                                                                -- Gronoa Shrine
    [3250] = { [96] = 0, [116] = 0, [117] = 0, [118] = 0, [119] = 0, [120] = 0 },                   -- Sanctissimus Shrine
}
G.LIFT_CLASSES = {
    "BP_MapGimmick_Floor_Elevator_Interact2_001_C", "BP_MapGimmick_Floor_Elevator_Interact2_002_C",
    "BP_MapGimmick_Floor_Elevator_Interact2_003_C", "BP_MapGimmick_Floor_Elevator_Interact2_004_C",
}
-- Round 114 (a tester, via the user): the rafts in these two do the same. The save keeps the last
-- raft ridden on each map (Map.lastRideRaftMap{map}.UniqueID), and the game shows the rafts by it.
-- A first visit has no row. The only way in to both is the first visit's door (point 0), so the
-- row is taken out while the player is on another map.
G.RAFT_MAPS = { [3080] = true, [3110] = true }   -- Cave of Waters, Water Shrine

-- Puts the lifts of G.LIFT_RESETS back at their first-visit stops, and takes out the last raft of
-- G.RAFT_MAPS, on every map but `here`. Returns a part per change ("3200:13 1 -> 0", "3080 raft
-- 47 -> none"). A lift never used has no row.
function G.ResetRides(here)
    local moved, sd = {}, G.SaveData()
    if not sd then return moved end
    pcall(function()
        sd.Map.mapGimmick:ForEach(function(key, value)
            local m = Int(key:get())
            local lifts = G.LIFT_RESETS[m]
            if not lifts or m == here then return end
            value:get().gimmickState:ForEach(function(uidKey, saved)
                local uid, row = Int(uidKey:get()), saved:get()
                local stop = lifts[uid]
                if stop and Int(row.Value) ~= stop then
                    moved[#moved + 1] = string.format("%d:%d %s -> %d", m, uid, tostring(Int(row.Value)), stop)
                    row.Value = stop
                end
            end)
        end)
    end)
    local rafts = {}
    pcall(function()
        sd.Map.lastRideRaftMap:ForEach(function(key, value)
            local m = Int(key:get())
            if G.RAFT_MAPS[m] and m ~= here then rafts[#rafts + 1] = { map = m, uid = Int(value:get().UniqueID) } end
        end)
    end)
    for _, raft in ipairs(rafts) do
        if pcall(function() sd.Map.lastRideRaftMap:Remove(raft.map) end) then
            moved[#moved + 1] = string.format("%d raft %s -> none", raft.map, tostring(raft.uid))
        end
    end
    table.sort(moved)
    return moved
end

-- The last raft ridden on this map in the save, or nil.
function G.LastRaft(mapId)
    local sd, uid = G.SaveData(), nil
    if not sd then return nil end
    pcall(function()
        sd.Map.lastRideRaftMap:ForEach(function(key, value)
            if Int(key:get()) == mapId then uid = Int(value:get().UniqueID) end
        end)
    end)
    return uid
end

-- On a map of G.LIFT_RESETS or G.RAFT_MAPS, the live stop of each of its lifts that is loaded and
-- the save's last raft ("lifts 13 at 0, 32 at 0; last raft 47"), or nil.
function G.RideState(mapId)
    local lifts, parts = G.LIFT_RESETS[mapId] or {}, {}
    if not (G.LIFT_RESETS[mapId] or G.RAFT_MAPS[mapId]) then return nil end
    for _, class in ipairs(G.LIFT_CLASSES) do
        local ok, all = pcall(FindAllOf, class)
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                local uid, stop
                pcall(function() uid, stop = Int(a.m_UniqueId), Int(a.m_CurrentSplineKeyIndex) end)
                if uid and lifts[uid] then parts[#parts + 1] = uid .. " at " .. tostring(stop) end
            end
        end
    end
    table.sort(parts)
    local line = #parts > 0 and ("lifts " .. table.concat(parts, ", ")) or nil
    if G.RAFT_MAPS[mapId] then
        line = (line and line .. "; " or "") .. "last raft " .. tostring(G.LastRaft(mapId) or "none")
    end
    return line
end

-- -------------------------------------------------------------------------------------------
-- The Archipelago page: an entry in the main menu (IDEAS.md idea 38, rounds 82 and 83)
-- -------------------------------------------------------------------------------------------
-- FFR Bestiary adds its entry with a pak that replaces DT_MainMenuScene and a tag table. A second
-- pak like it would drop whichever row loaded first, so ours is added from Lua, as the Options
-- rows are: AddRow into DT_MainMenuScene (a copy of System's row, opening the Tutorial screen),
-- the tag into DA_MainMenuRoot.DisplaySceneList before System, and the row into the menu
-- subsystem's maps when the subsystem was built before the row was there. The Tutorial screen is
-- one framed window that no main menu page or other mod uses; the page puts its text there.
-- A function, not a `do` block: the main chunk is at Lua's limit of 200 locals, and a block's
-- locals count toward it.
;(function()
local SCENE_TABLE = "/Game/UI/MainMenu/Data/DT_MainMenuScene.DT_MainMenuScene"
local SYSTEM_TAG = "UI.MainMenu.Scene.System"
local MENU_LAYOUT = "WBP_MainMenuLayout"
G.APMENU = {
    ROW = "FFRAP_Archipelago",
    NAME = "Archipelago",
    -- Never registered as a gameplay tag; round 82 showed the menu needs no more (nor do the
    -- Options rows' tags).
    TAG = "UI.MainMenu.Scene.FFRAP",
    LAYOUT = "/Game/UI/Tutorial/WBP_TutorialLayout.WBP_TutorialLayout_C",
    -- Which screen the entry opens: `options`, the game's Options screen made our page (round 87),
    -- or `text`, the Tutorial screen with the page's lines (rounds 83 to 86; ffrap_apmenu text).
    screen = "options",
    OPTIONS_LAYOUT = "/Game/UI/Option/Widget/WBP_OptionLayout.WBP_OptionLayout_C",
    -- Round 87 (the user): the page has two tabs, our settings and the seed's lines. false puts the
    -- lines under the settings in one tab, as the round's first build did (ffrap_apmenu split off).
    split = true,
    SETTINGS_TAB = "Settings",
    SEED_TAB = "Seed",
    -- The seed's lines as Command rows (WBP_OP_Command, whose click does nothing in its
    -- Blueprint), which take the cursor, so a gamepad scrolls the Seed tab. No heading does
    -- (round 87). Round 88: the probe worked, and the user liked the look better, so it is the
    -- default. ffrap_apmenu seedrows heading puts headings back.
    seedRows = "command",
}
local A = G.APMENU
-- The game opens its Options screen from DT_GameLayoutWidget_System's UI.Layout.Option row, which
-- gives it two view models (CPP_VM_Option, CPP_VM_OptionKeyBind) and two more input contexts
-- (UI_Info, OptionMenu). Round 82 opened it from our entry with only the screen class, and it came
-- up empty. Main menu rows hold the same LayoutData, so ours can carry them too.
local GAME_LAYOUT_TABLE = "/Game/Datatable/UI/GameLayout/DT_GameLayoutWidget_System.DT_GameLayoutWidget_System"
local OPTION_LAYOUT_TAG = "UI.Layout.Option"
local OPTION_ROOT_TABLE = "/Game/Datatable/UI/Option/DT_Option_Root.DT_Option_Root"
-- A condition the story counter can never meet: a tab with it is left out (probe `tabs only`).
local NEVER = "{progress:0}<0"
local GAMEPLAY_CATEGORY = 0   -- FOP_Parent_CommandCategory: Gameplay 0, Graphic 1, KeyboardMouse 2, Gamepad 3, Sound 4
-- Round 103 (the user): the Seed tab is the Graphics tab, for its monitor icon (it was Sound's).
local SEED_CATEGORY = 1
local function screenPath() return A.screen == "options" and A.OPTIONS_LAYOUT or A.LAYOUT end

local function quiet() end
local function tagOf(v)
    local s
    pcall(function() s = ObjText(v.TagName) end)
    return s
end
local function className(path) return path:match("%.([^.]+)$") end
local function screenClass() return className(screenPath()) end
local function activated(w)
    local ok, v = pcall(function() return w:IsActivated() end)
    return ok and v == true
end

-- The row, added where missing with our tag, name and screen. Returns "added", "present", or nil
-- and why not.
function A.Row(say)
    local dt = LoadObject(SCENE_TABLE)
    if not dt then return nil, "DT_MainMenuScene could not be loaded" end
    local mine, system
    pcall(function()
        dt:ForEachRow(function(name, row)
            if ObjText(name) == A.ROW then mine = row end
            if tagOf(row.SceneTag) == SYSTEM_TAG then system = row end
        end)
    end)
    if mine then return "present" end
    if not system then return nil, "no System row to copy" end
    say("apmenu: AddRow " .. A.ROW .. " (a copy of System's)")
    if not pcall(function() dt:AddRow(A.ROW, system) end) then return nil, "AddRow failed" end
    pcall(function() mine = dt:FindRow(A.ROW) end)
    if not mine then return nil, "AddRow left no row" end
    say("apmenu: row tag, texts and screen")
    pcall(function() mine.SceneTag.TagName = FName(A.TAG) end)
    pcall(function() mine.EntryName = FText(A.NAME) end)
    pcall(function() mine.SceneTitle = FText(A.NAME) end)
    -- A soft class: written as the reference KismetSystemLibrary makes (round 82).
    local ksl = Find("/Script/Engine.Default__KismetSystemLibrary")
    if not pcall(function()
        mine.LayoutData.LayoutWidget = ksl:Conv_SoftClassPathToSoftClassRef(ksl:MakeSoftClassPath(A.LAYOUT))
    end) then return nil, "the row's screen could not be written" end
    if A.screen ~= "text" then A.WriteScreen(mine.LayoutData, say) end
    return "added"
end

-- The LayoutData the chosen screen opens with: the game's Options layout row for `options`,
-- System's main menu row (no view models) for `text`. Returns it, or nil and why not.
local function screenSource()
    if A.screen == "options" then
        local dt = LoadObject(GAME_LAYOUT_TABLE)
        if not dt then return nil, "DT_GameLayoutWidget_System could not be loaded" end
        local found
        pcall(function()
            dt:ForEachRow(function(_, row) if tagOf(row.LayoutTag) == OPTION_LAYOUT_TAG then found = row.LayoutData end end)
        end)
        return found, found == nil and "no UI.Layout.Option row" or nil
    end
    local dt = LoadObject(SCENE_TABLE)
    local found
    pcall(function()
        dt:ForEachRow(function(_, row) if tagOf(row.SceneTag) == SYSTEM_TAG then found = row.LayoutData end end)
    end)
    return found, found == nil and "no System row" or nil
end

-- Writes the chosen screen into one LayoutData: its class, view models and input contexts, each
-- step told to `say` before it runs. Returns a line.
function A.WriteScreen(data, say)
    local src, why = screenSource()
    if not src then return "not written: " .. why end
    local ksl = Find("/Script/Engine.Default__KismetSystemLibrary")
    say("apmenu: screen class " .. screenPath())
    local okClass = pcall(function()
        data.LayoutWidget = ksl:Conv_SoftClassPathToSoftClassRef(ksl:MakeSoftClassPath(screenPath()))
    end)
    local vms, from = data.ViewModelDataList, src.ViewModelDataList
    say("apmenu: view models " .. #vms .. " -> " .. #from)
    local okVms = pcall(function()
        vms:Empty()
        for i = 1, #from do
            local _ = vms[i]
            vms[i].ViewModelClass = from[i].ViewModelClass
            vms[i].IsManualContextName = from[i].IsManualContextName
            vms[i].ManualContextName = from[i].ManualContextName
        end
    end)
    local ctx, fromCtx = data.IMCData.childMappingContextList, src.IMCData.childMappingContextList
    say("apmenu: input contexts " .. #ctx .. " -> " .. #fromCtx)
    local okCtx = pcall(function()
        local want = {}
        for i = 1, #fromCtx do want[i] = Int(fromCtx[i]) end
        ctx:Empty()
        for i, v in ipairs(want) do ctx[i] = v end
    end)
    return string.format("class %s, view models %s (%d), input contexts %s (%d)", okClass and "written" or "failed",
        okVms and "written" or "failed", #vms, okCtx and "written" or "failed", #ctx)
end

-- Switches the entry to `text` or `options`: our table row and the menu subsystem's copy of it.
-- Returns lines.
function A.Screen(kind, say)
    A.screen = kind
    local out = {}
    local dt = LoadObject(SCENE_TABLE)
    local row
    pcall(function() row = dt:FindRow(A.ROW) end)
    out[#out + 1] = "row: " .. (row and A.WriteScreen(row.LayoutData, say) or "not added yet; it opens " .. kind .. " when it is")
    local sub = Live("CPP_MainMenuSubsystem")
    local copy
    if sub then
        pcall(function() sub.SceneDataMap:ForEach(function(k, v) if tagOf(k:get()) == A.TAG then copy = v:get() end end) end)
    end
    out[#out + 1] = "subsystem: " .. (copy and A.WriteScreen(copy.LayoutData, say) or "no copy (title screen?)")
    return out
end

-- The Options screen as our page (IDEAS.md idea 39; round 85 showed the entry can open it and
-- that its tabs are read at each open, round 86 that this looks right). `ap` leaves out every tab
-- but Gameplay and Graphics, hides the game's rows in their tables (ShowType TitleOnly: not in
-- game) and shows ours, and adds a heading row for each of `lines` (copies of the keyboard tab's
-- first SubHeader; all these tables hold OP_BaseMenu_EntryInfo rows). Each tab shows the row table
-- its DT_Option_Root row names, so the Graphics tab, its rows hidden, holds the headings (round 87,
-- on the Sound tab until round 103). With A.split off, that tab is left out too and the headings go
-- under our settings. `game` puts it all back and hides ours again. Each step is told to `say` before it runs. Returns lines.
local KEYBOARD_TABLE = "/Game/Datatable/UI/Option/Root/KeyboardMouseSetting/DT_OP_KeyboardMouseSetting.DT_OP_KeyboardMouseSetting"
local HEADING_ROW = "SubHeader_共通"
local GAMEPLAY_TABLE = "/Game/Datatable/UI/Option/Root/GameSetting/DT_OP_GameSetting.DT_OP_GameSetting"
local SEED_TABLE = "/Game/Datatable/UI/Option/Root/GraphicSetting/DT_OP_GraphicSetting.DT_OP_GraphicSetting"
-- Sets every row of the table at `path` but `keep`'s to TitleOnly, each old ShowType kept in
-- `saved.show[path]` (a value kept from before the game loaded the table again stays). Returns
-- how many it hid.
local function hideRows(path, keep, saved, say)
    local dt, hidden = LoadObject(path), 0
    local show = saved.show[path] or {}
    saved.show[path] = show
    pcall(function()
        dt:ForEachRow(function(name, row)
            local key = ObjText(name)
            if keep[key] then
                pcall(function() row.ShowCommandData.ShowType = G.SHOW_TYPE.game end)
                return
            end
            if show[key] == nil then show[key] = Int(row.ShowCommandData.ShowType) end
            say("apmenu: row " .. key .. " ShowType " .. tostring(show[key]) .. " -> TitleOnly")
            pcall(function() row.ShowCommandData.ShowType = G.SHOW_TYPE.title end)
            hidden = hidden + 1
        end)
    end)
    return hidden
end
local function setShowTypes(path, show)
    local dt = LoadObject(path)
    for key, t in pairs(show) do
        local row
        pcall(function() row = dt:FindRow(key) end)
        if row then pcall(function() row.ShowCommandData.ShowType = t end) end
    end
end
-- Round 103: last first. The row map reuses freed slots last-freed-first, so rows removed in
-- order came back reversed at the next open, and the page's rows changed order at each open.
local function removeRows(path, names, say)
    local dt, removed = LoadObject(path), 0
    for i = #names, 1, -1 do
        local name = names[i]
        say("apmenu: RemoveRow " .. name)
        if pcall(function() dt:RemoveRow(name) end) then removed = removed + 1 end
    end
    return removed
end
local COMMAND_TYPE = 14   -- EOP_BaseMenu_EntryType: Subheader 15, Command 14
-- Whether the tables still hold the page written by Mode "ap". The game loads DT_OP_GameSetting
-- again from time to time (round 57), with none of our changes: on round 88's first open the page
-- showed the game's rows, as on a table loaded after the SetScene hook had written the old one.
function A.Written()
    local saved = A.modeSaved
    if not saved then return false end
    local rows, info, root = LoadObject(GAMEPLAY_TABLE), LoadObject(saved.infoPath), LoadObject(OPTION_ROOT_TABLE)
    local ok = false
    pcall(function()
        local label
        root:ForEachRow(function(_, row)
            if Int(row.CommandCategory) == GAMEPLAY_CATEGORY then label = row.DisplayText:ToString() end
        end)
        ok = label == saved.name and rows:FindRow(G.OPTION_ROWS[1].row) ~= nil
            and (#saved.info == 0 or info:FindRow(saved.info[1]) ~= nil)
    end)
    return ok
end
-- Our setting rows must be in DT_OP_GameSetting before `ap` (G.EnsureOptionRows); `game` removes
-- them. On tables the game has loaded again since, `ap` writes the page again, keeping the tab
-- names and ShowTypes it saved first.
function A.Mode(kind, lines, say)
    local out = A.Tabs(kind == "ap" and "only" or "all", say)
    local root, rows = LoadObject(OPTION_ROOT_TABLE), LoadObject(GAMEPLAY_TABLE)
    local tabs = {}
    pcall(function()
        root:ForEachRow(function(_, row) tabs[Int(row.CommandCategory)] = row end)
    end)
    if not (tabs[GAMEPLAY_CATEGORY] and rows) then
        out[#out + 1] = "no Gameplay tab or no DT_OP_GameSetting"
        return out
    end
    local ours, ourNames = {}, {}
    for _, o in ipairs(G.OPTION_ROWS) do
        ours[o.row] = true
        ourNames[#ourNames + 1] = o.row
    end
    local before = A.modeSaved
    if kind == "ap" and before and A.Written() then
        out[#out + 1] = "mode ap: already so"
    elseif kind == "ap" then
        local split = A.split and tabs[SEED_CATEGORY] ~= nil and LoadObject(SEED_TABLE) ~= nil
        local saved = { show = before and before.show or {}, labels = before and before.labels or {}, info = {},
                        infoPath = split and SEED_TABLE or GAMEPLAY_TABLE }
        local names = { [GAMEPLAY_CATEGORY] = split and A.SETTINGS_TAB or A.NAME }
        if split then names[SEED_CATEGORY] = A.SEED_TAB end
        saved.name = names[GAMEPLAY_CATEGORY]
        for category, label in pairs(names) do
            local tab = tabs[category]
            if saved.labels[category] == nil then pcall(function() saved.labels[category] = tab.DisplayText:ToString() end) end
            say("apmenu: tab " .. category .. " named " .. label)
            pcall(function() tab.DisplayText = FText(label) end)
        end
        local hidden = hideRows(GAMEPLAY_TABLE, ours, saved, say)
        if split then hidden = hidden + hideRows(SEED_TABLE, {}, saved, say) end
        local keyboard, infoRows, heading = LoadObject(KEYBOARD_TABLE), LoadObject(saved.infoPath), nil
        pcall(function() heading = keyboard:FindRow(HEADING_ROW) end)
        local command = A.seedRows == "command"
        for _, text in ipairs(heading and lines or {}) do
            if text == "" then goto nextLine end
            local name = "FFRAP_Info" .. (#saved.info + 1)
            say("apmenu: " .. (command and "command" or "heading") .. " row " .. name .. ": " .. text)
            local row
            pcall(function() row = infoRows:FindRow(name) end)
            if not row and pcall(function() infoRows:AddRow(name, heading) end) then
                pcall(function() row = infoRows:FindRow(name) end)
            end
            if row then
                pcall(function() row.DisplayText = FText(text) end)
                if command then pcall(function() row.Type = COMMAND_TYPE end) end
                saved.info[#saved.info + 1] = name
            end
            ::nextLine::
        end
        if before and #before.info > #saved.info then
            local extra = {}
            for i = #saved.info + 1, #before.info do extra[#extra + 1] = before.info[i] end
            removeRows(before.infoPath, extra, say)
        end
        A.modeSaved = saved
        out[#out + 1] = string.format("mode ap: %d game rows hidden, %d %s rows%s%s%s", hidden, #saved.info,
            command and "command" or "heading", split and " on the " .. A.SEED_TAB .. " tab" or "",
            heading and "" or " (no SubHeader row to copy)", before and " (written again)" or "")
    elseif kind == "game" and before then
        for category, label in pairs(before.labels) do
            say("apmenu: tab " .. category .. " named " .. label)
            pcall(function() tabs[category].DisplayText = FText(label) end)
        end
        for path, show in pairs(before.show) do setShowTypes(path, show) end
        local removed = removeRows(before.infoPath, before.info, say)
        removeRows(GAMEPLAY_TABLE, ourNames, say)
        A.modeSaved = nil
        out[#out + 1] = string.format("mode game: rows shown again, %d of %d heading rows removed", removed, #before.info)
    else
        out[#out + 1] = "mode " .. kind .. ": already so"
    end
    return out
end

-- The Options screen's tabs (DT_Option_Root): `list` reads them; `only` leaves out every tab but
-- Gameplay (and Graphics, with A.split) with a condition never met; `all` puts the conditions back.
-- Returns lines.
A.tabConditions = {}
function A.Tabs(mode, say)
    local dt = LoadObject(OPTION_ROOT_TABLE)
    if not dt then return { "DT_Option_Root could not be loaded" } end
    local out = {}
    pcall(function()
        dt:ForEachRow(function(name, row)
            local key, cond, label = ObjText(name), "?", "?"
            pcall(function() cond = row.Condition:ToString() end)
            pcall(function() label = row.DisplayText:ToString() end)
            local category = Int(row.CommandCategory)
            local kept = category == GAMEPLAY_CATEGORY or (A.split and category == SEED_CATEGORY)
            if mode == "only" and not kept and cond ~= NEVER then
                A.tabConditions[key] = cond
                say("apmenu: tab " .. key .. " (" .. label .. ") condition -> " .. NEVER)
                pcall(function() row.Condition = NEVER end)
            elseif mode == "all" and A.tabConditions[key] then
                say("apmenu: tab " .. key .. " (" .. label .. ") condition back to \"" .. A.tabConditions[key] .. "\"")
                pcall(function() row.Condition = A.tabConditions[key] end)
                A.tabConditions[key] = nil
            end
            pcall(function() cond = row.Condition:ToString() end)
            out[#out + 1] = string.format("tab %s: %s, category %s, condition \"%s\"", key, label, tostring(category), cond)
        end)
    end)
    if #out == 0 then out[1] = "DT_Option_Root has no rows" end
    return out
end

-- Our tag in DA_MainMenuRoot.DisplaySceneList, before System. Returns "added", "present" or nil.
function A.List(say)
    local da = Live("CPP_DA_MainMenuRoot")
    if not da then return nil, "no DA_MainMenuRoot loaded" end
    local list = da.DisplaySceneList
    local n = #list
    if n == 0 then return nil, "the scene list is empty" end
    for i = 1, n do
        if tagOf(list[i]) == A.TAG then return "present" end
    end
    say("apmenu: scene list " .. n .. " -> " .. (n + 1) .. ", before System")
    local last = tagOf(list[n])
    if last == SYSTEM_TAG then
        list[n + 1] = { TagName = FName(last) }
        list[n].TagName = FName(A.TAG)
    else
        list[n + 1] = { TagName = FName(A.TAG) }
    end
    return "added"
end

-- Takes our tag out of DisplaySceneList again (an engine list cannot drop one entry, so it is
-- emptied and built again). Returns true when it was there.
function A.Unlist()
    local da = Live("CPP_DA_MainMenuRoot")
    if not da then return false end
    local list = da.DisplaySceneList
    local keep, found = {}, false
    for i = 1, #list do
        local tag = tagOf(list[i])
        if tag == A.TAG then found = true else keep[#keep + 1] = tag end
    end
    if not found then return false end
    list:Empty()
    for i, tag in ipairs(keep) do list[i] = { TagName = FName(tag) } end
    return true
end

-- Our tag in the menu subsystem's SceneDataMap and SceneEnableMap (one subsystem per world, which
-- may have copied the table before the row was there). Returns a line, or nil and why not.
function A.Subsystem(say)
    local sub = Live("CPP_MainMenuSubsystem")
    if not sub then return nil, "no main menu subsystem (title screen?)" end
    local inData, inEnable = false, nil
    pcall(function() sub.SceneDataMap:ForEach(function(k) if tagOf(k:get()) == A.TAG then inData = true end end) end)
    pcall(function() sub.SceneEnableMap:ForEach(function(k, v) if tagOf(k:get()) == A.TAG then inEnable = v:get() end end) end)
    local parts = {}
    if inData then parts[#parts + 1] = "data present"
    else
        local row
        pcall(function() row = LoadObject(SCENE_TABLE):FindRow(A.ROW) end)
        if not row then return nil, "no row to copy into the subsystem" end
        say("apmenu: SceneDataMap:Add")
        local ok, err = pcall(function() sub.SceneDataMap:Add({ TagName = FName(A.TAG) }, row) end)
        parts[#parts + 1] = ok and "data added" or ("data add failed: " .. tostring(err))
    end
    if inEnable == nil then
        say("apmenu: SceneEnableMap:Add true")
        local ok = pcall(function() sub.SceneEnableMap:Add({ TagName = FName(A.TAG) }, true) end)
        parts[#parts + 1] = ok and "enable added" or "enable add failed"
    else
        parts[#parts + 1] = "enable " .. tostring(inEnable)
    end
    return table.concat(parts, ", ")
end

-- Every tick: the row, the scene list and the subsystem. Returns what was written, nil when
-- nothing was, or nil and why not. `say` is told each step before it writes.
function A.Ensure(say)
    say = say or quiet
    local done = {}
    local row, why = A.Row(say)
    if not row then return nil, why end
    if row == "added" then done[#done + 1] = "row added" end
    local list, whyList = A.List(say)
    if not list then return nil, whyList end
    if list == "added" then done[#done + 1] = "scene list" end
    local sub = A.Subsystem(say)
    if sub and sub:find("added", 1, true) then done[#done + 1] = sub end
    return #done > 0 and table.concat(done, "; ") or nil
end

-- Our screen when it is open: the activated Tutorial screen under the main menu, or nil. Real
-- tutorials open elsewhere and are never touched.
local function openHost()
    local ok, all = pcall(FindAllOf, screenClass())
    for _, w in ipairs(ok and all or {}) do
        local full = G.PathOf(w)
        if Alive(w) and full and full:find(MENU_LAYOUT, 1, true) and activated(w) then return w end
    end
end

-- Every widget of a screen, depth first, into nested user widgets: visit(widget, name, depth).
-- Round 83: GetWidgetFromName found none of the Tutorial screen's parts, while this walk reached
-- them all.
local WALK_MAX, WALK_DEPTH = 600, 14
local function walkScreen(host, visit)
    local seen = 0
    local function walk(w, depth)
        if seen >= WALK_MAX or depth > WALK_DEPTH or not Alive(w) then return end
        seen = seen + 1
        local name = "?"
        pcall(function() name = w:GetFName():ToString() end)
        visit(w, name, depth)
        local root
        pcall(function() root = w.WidgetTree.RootWidget end)
        if root and Alive(root) then walk(root, depth + 1) end
        local n = 0
        pcall(function() n = w:GetChildrenCount() end)
        for i = 0, n - 1 do
            local c
            pcall(function() c = w:GetChildAt(i) end)
            if c then walk(c, depth + 1) end
        end
    end
    local root
    pcall(function() root = host.WidgetTree.RootWidget end)
    walk(root, 1)
end

-- The open screen's widget tree, one line per widget (ffrap_apmenu tree). Returns lines, or nil
-- when the page is not open.
function A.Tree()
    local host = openHost()
    if not host then return nil end
    local out = { "host " .. tostring(G.PathOf(host)) }
    walkScreen(host, function(w, name, depth)
        local cls, vis = "?", "?"
        pcall(function() cls = w:GetClass():GetFName():ToString() end)
        pcall(function() vis = tostring(w:GetVisibility()) end)
        out[#out + 1] = string.rep("  ", depth) .. cls .. " " .. name .. " (visibility " .. vis .. ")"
    end)
    return out
end

-- The Tutorial screen (WBP_Tutorial) has a title, an image box, a description, a page count and
-- two arrows. The page keeps the window and the title, and widens the description box from 750
-- to the image box's 1180.
local PAGE_HIDE = { "SizeBox_2", "Overlay_ButtonNext", "Overlay_ButtonPreview", "HorizontalBox_215" }
local COLLAPSED = 1
local TEXT_WIDTH = 1180

-- The screen's own open/close state (CPP_EU_WBP_Activatable), as one line.
local function openFlags(w)
    local f = {}
    for _, k in ipairs({ "IsOpeningProcess", "IsClosingProcess", "IsCanInput", "bIsCanceling" }) do
        local v
        pcall(function() v = w[k] end)
        f[#f + 1] = k .. " " .. tostring(v)
    end
    local finish
    pcall(function() finish = w.CloseStateProperty.IsEnableDefaultFinisheCall end)
    f[#f + 1] = "close finish " .. tostring(finish)
    return table.concat(f, ", ")
end

-- Our page on the open screen: `title`, makeBody() in the description, and the rest hidden. The
-- body is made only while the page is open. Only what differs from the screen is written, so if
-- the game fills the screen again when it opens, the next tick puts the page back. Steps are told
-- to `say` once per screen instance. Returns "written", "same", or nil and why not.
function A.Page(title, makeBody, say)
    say = say or quiet
    local host = A.screen == "text" and openHost()
    if not host then
        A.reopenFor = nil
        return nil, "not open"
    end
    local full = G.PathOf(host)
    local first = A.pageHost ~= full
    local tell = first and say or quiet
    local parts, count = {}, 0
    walkScreen(host, function(w, name)
        count = count + 1
        if not parts[name] then parts[name] = w end
    end)
    local titleText, bodyText = parts.Text_Title, parts.Text_Description
    if not (titleText and bodyText) then
        return nil, "no Text_Title or Text_Description among the screen's " .. count .. " widgets"
    end
    local wrote = false
    local function setText(w, name, text)
        local now
        pcall(function() now = w:GetText():ToString() end)
        if now == text then return end
        tell("apmenu: page " .. name)
        pcall(function() w:SetText(FText(text)) end)
        wrote = true
    end
    setText(titleText, "title", title)
    setText(bodyText, "text", makeBody())
    for _, name in ipairs(PAGE_HIDE) do
        local w = parts[name]
        local vis
        if w then pcall(function() vis = w:GetVisibility() end) end
        if w and vis ~= COLLAPSED then
            tell("apmenu: page hides " .. name)
            pcall(function() w:SetVisibility(COLLAPSED) end)
            wrote = true
        end
    end
    local box = parts.SizeBox_1
    if box and first then
        tell("apmenu: page text box " .. TEXT_WIDTH .. " wide, any height")
        pcall(function() box:ClearHeightOverride() end)
        pcall(function() box:SetWidthOverride(TEXT_WIDTH) end)
    end
    -- Round 83: Back asks the screen to close (A_Close, then FinishedClose at its end), but the menu
    -- turns the screen off at once, so FinishedClose never ran. The screen stayed "closing", and
    -- the next open and the next Back were refused. With the default finish on, the base class
    -- finishes a close itself.
    local finish
    pcall(function() finish = host.CloseStateProperty.IsEnableDefaultFinisheCall end)
    if finish == false then
        tell("apmenu: page CloseStateProperty.IsEnableDefaultFinisheCall true")
        pcall(function() host.CloseStateProperty.IsEnableDefaultFinisheCall = true end)
    end
    -- If the screen still comes back at opacity 0 with no open under way, ask it to open, once per
    -- opening (OnRequestOpen: A_Open, then FinishedOpen at its end).
    local opacity, opening
    pcall(function() opacity = host:GetRenderOpacity() end)
    pcall(function() opening = host.IsOpeningProcess end)
    if type(opacity) == "number" and opacity < 0.99 and opening ~= true and A.reopenFor ~= full then
        A.reopenFor = full
        say("apmenu: page screen at opacity " .. opacity .. " (" .. openFlags(host) .. "); OnRequestOpen")
        local okOpen, err = pcall(function() host:OnRequestOpen() end)
        if not okOpen then
            say("apmenu: OnRequestOpen failed (" .. tostring(err) .. "); render opacity -> 1")
            pcall(function() host:SetRenderOpacity(1.0) end)
        end
        wrote = true
    end
    A.pageHost = full
    return wrote and "written" or "same"
end

-- Our screen off but still "closing": the fallback for when the default finish above does not
-- take. After three ticks (1.5 s) in that state, FinishedClose. Returns a line when it acts.
A.stale = {}
function A.Unstick(say)
    local ok, all = pcall(FindAllOf, screenClass())
    for _, w in ipairs(ok and all or {}) do
        local full = G.PathOf(w)
        if Alive(w) and full and full:find(MENU_LAYOUT, 1, true) and not activated(w) then
            local closing
            pcall(function() closing = w.IsClosingProcess end)
            if closing == true then
                A.stale[full] = (A.stale[full] or 0) + 1
                if A.stale[full] == 3 then
                    say("apmenu: screen off but still closing (" .. openFlags(w) .. "); FinishedClose")
                    pcall(function() w:FinishedClose() end)
                    return "finished a stale close; " .. openFlags(w)
                end
            else
                A.stale[full] = nil
            end
        end
    end
end

-- Every instance of our screen, for when the page goes wrong: activated, visible, visibility,
-- render opacity, open/close state, and the main menu's scene stack. Returns lines.
function A.State()
    local out = {}
    local ok, all = pcall(FindAllOf, screenClass())
    for _, w in ipairs(ok and all or {}) do
        if Alive(w) then
            local vis, visibility, opacity
            pcall(function() vis = w:IsVisible() end)
            pcall(function() visibility = w:GetVisibility() end)
            pcall(function() opacity = w:GetRenderOpacity() end)
            out[#out + 1] = string.format("%s  activated %s  visible %s  visibility %s  opacity %s; %s", tostring(G.PathOf(w)),
                tostring(activated(w)), tostring(vis), tostring(visibility), tostring(opacity), openFlags(w))
        end
    end
    if #out == 0 then out[1] = screenClass() .. ": none" end
    local vm = Live("CPP_VM_MainMenu")
    local stack = {}
    if vm then pcall(function() for i = 1, #vm.SceneDataStack do stack[#stack + 1] = tostring(tagOf(vm.SceneDataStack[i])) end end) end
    out[#out + 1] = "main menu scene stack: " .. (vm and table.concat(stack, ", ") or "no view model")
    return out
end

-- The scene at the top of the main menu's stack (a tag), or nil with no main menu.
function A.SceneTop()
    local vm = Live("CPP_VM_MainMenu")
    local top
    if vm then pcall(function() top = tagOf(vm.SceneDataStack[#vm.SceneDataStack]) end) end
    return top
end

-- A way out when the page will not close. With our screen open: ask it to close the way Back does
-- (OnRequestClose). With it already off but the menu still on our scene (the empty background of
-- round 83): the menu view model's PopScene(). Returns a line.
function A.Close(say)
    local host = openHost()
    if host then
        say("apmenu: OnRequestClose " .. tostring(G.PathOf(host)) .. " (" .. openFlags(host) .. ")")
        local okCall, err = pcall(function() host:OnRequestClose() end)
        return okCall and ("close asked; " .. openFlags(host)) or ("OnRequestClose failed: " .. tostring(err))
    end
    local vm = Live("CPP_VM_MainMenu")
    local top
    if vm then pcall(function() top = tagOf(vm.SceneDataStack[#vm.SceneDataStack]) end) end
    if top ~= A.TAG then return "the page is not open and the menu is not on it (" .. tostring(top) .. ")" end
    say("apmenu: CPP_VM_MainMenu:PopScene (the stack ends with our scene)")
    local okPop, errPop = pcall(function() vm:PopScene() end)
    local now
    pcall(function() now = tagOf(vm.SceneDataStack[#vm.SceneDataStack]) end)
    return okPop and ("PopScene; the stack ends with " .. tostring(now)) or ("PopScene failed: " .. tostring(errPop))
end
end)()

return G
