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

-- The first live instance of a class, cached until it goes invalid.
local liveCache = {}
local function Live(shortClass)
    local hit = liveCache[shortClass]
    if hit and Alive(hit) then return hit end
    local ok, obj = pcall(FindFirstOf, shortClass)
    if ok and obj and Alive(obj) then
        liveCache[shortClass] = obj
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

-- The map the player is on, as the save keys it: CPP_MapManager:GetSameMapId(). Maps that share
-- a save list (a town's inside and outside, say) answer with the same id, and that id is the one
-- CPP_BFL_SaveDataMap:IsOpenTreasureBox wants. Found in FFRS_QoL's markers. Round 2 showed the
-- save's own Map.mapId (G.MapId below) can lag minutes behind the map you are actually in.
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

-- True when a save is loaded and the field is running. This is a guess at "safe to grant":
-- save data exists and the map manager exists. The title screen may also have save data, so
-- the map manager is the stronger signal. Verify this in the test plan (README, step 3).
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

-- A vision entry's synchro map has one key per party member. Read from the game's own entries
-- in round 38 (`ffrap_visions`, a chapter 6 save).
G.VISION_SYNCHRO_KEYS = { 1001, 1002, 1003, 1006, 1004, 1005, 1007, 1008 }

-- Adds a vision to the save's vision list and to the bag, the way FFRSLib's ffrs_vision_unlock
-- does: grow visionList by one zeroed entry, set its ID, write the synchro-map keys at 0, then
-- AddInventory(id, 1). The keys were copied from the first entry until round 38, so a save with
-- no vision had to wait for one, and the open world start never gets one from the story.
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

-- Party members. CPP_VM_Party:AddUnit puts a unit in the ACTIVE party, and fails when it is
-- full (round 1). The roster is each unit's JoinStatus in sd.unitParameterList
-- (eUnitJoinStatus: 0 Join, 1 NotJoin, 2 Leave, 3 TemporalLeave, 4 Lost), which the story's own
-- talk events set through ChangeUnitJoinStatusList (data dump, round 30). So a unit goes into
-- the active party when there is room, and otherwise joins the roster as the story would.
local function PartyVM() return Live("CPP_VM_Party") end

local function Joined(vm, id)
    local ok, r = pcall(function() return vm:IsJoinedUnit(id) end)
    return ok and r == true
end

-- Round 44: AddUnit puts a unit in the party but leaves its JoinStatus at NotJoin. Rain then got
-- no EXP, and gear on her did not count as equipped. So every join goes through G.FinishJoin.
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

-- -------------------------------------------------------------------------------------------
-- Chests
-- -------------------------------------------------------------------------------------------

-- The chests in the loaded maps. Each carries a copy of its chest table row in
-- m_TreasureBoxData, so `rowMap` and `rowId` are the row's own mapId and ID: the location key,
-- whatever map the game currently reports. `uid` (m_Id), `uniqueId` (m_UniqueId) and `typeId`
-- (TypeData.ID) are the candidates for the save's key, which round 2 showed is not m_Id.
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
                out[#out + 1] = e
            end)
        end
    end
    return out
end

-- What the save says about one chest. A map that shares another map's save list needs that
-- map's id here (FFRS_QoL's chest_items.lua lists such aliases), so the actor's map id and the
-- save's answer can disagree. The POC logs both until we know the rule.
function G.IsChestOpenInSave(mapId, uid)
    local lib = Lib("CPP_BFL_SaveDataMap")
    if not (lib and lib.IsOpenTreasureBox) then return nil end
    local ok, r = pcall(function() return lib:IsOpenTreasureBox(mapId, uid) end)
    if not ok then return nil end
    return r == true
end

-- Discovery: what the save says about a chest under each candidate key, as one string, e.g.
-- "map 3020 / row map 2001: m_Id 3 false, m_UniqueId 17 true, TypeData.ID 17 true".
-- Round 2: IsOpenTreasureBox(map, m_Id) was false for every chest, opened or not.
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

-- Chest blanking: every chest that is an Archipelago location gives 1 gil instead of its
-- vanilla reward, because the real reward comes from the server. 1 gil is the shape the game's
-- own gil chests use (ItemId -1, Money N). Turning it off restores the originals, and a game
-- restart restores them anyway.
--
-- Chests holding an item at or above SHUFFLE_ID_LIMIT (visions, key items, valuables) are not
-- locations and keep their content. The apworld uses the same limit (tools/gen_apworld_data.py).
local SHUFFLE_ID_LIMIT = 13000
local MAGICITE_FIRST, MAGICITE_LAST = 25000, 25002   -- round 45: chests with Magicite are shuffled too
--
-- The originals are keyed by the row's own mapId and ID, never by where the copy lives. A chest
-- that spawns while blanking is on copies the already-blank row, so a snapshot of the spawned
-- chest would "restore" it to blank. That was the 0.2.0 bug: after ffrap_blank off, chests in
-- the map you were standing in still gave 1 gil until you left.
local blankOriginals = {}   -- "mapId:ID" -> { ItemId, ItemNum, Money } as the game shipped them
local BLANK = { ItemId = -1, ItemNum = 1, Money = 1 }

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
    if itemId >= SHUFFLE_ID_LIMIT and not (itemId >= MAGICITE_FIRST and itemId <= MAGICITE_LAST) then return false end
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
-- The sparkly pick-ups on the world map and in fields. They are not in a data table: they are
-- BP_MapGimmick_FieldItem* actors placed in the level files, each with an m_UniqueId.
-- FFRS_QoL's markers (based on ZArkadia's Item and Chest Markers, Nexus mod 25) treat a spot as
-- looted when CPP_BFL_SaveDataMap:IsOpenTreasureBox(saveMapId, uniqueId) says so, the same
-- call as chests. Round 2 confirmed that, live: the save answers true the moment a shiny is
-- picked up. The reward is on the actor: m_ItemId, m_ItemNum, m_Money. Spots with neither an
-- item nor money are story or quest points that only show under a VisibleCondition.

local function ClassName(o)
    local ok, n = pcall(function() return o:GetClass():GetFName():ToString() end)
    return ok and n or "?"
end

function G.LiveFieldItems()
    local out, seen = {}, {}
    for _, cls in ipairs({ "CPP_MapGimmick", "BP_MapGimmick_FieldItem_C" }) do
        local ok, all = pcall(FindAllOf, cls)
        for _, a in ipairs(ok and all or {}) do
            if Alive(a) then
                local cname = ClassName(a)
                local addr
                pcall(function() addr = a:GetAddress() end)
                if cname:find("FieldItem", 1, true) and not (addr and seen[addr]) then
                    if addr then seen[addr] = true end
                    pcall(function()
                        local e = {
                            uid = Int(a.m_UniqueId),
                            hidden = a.bHidden == true,
                            interact = Int(a.interactType),
                            class = cname,
                            actor = a,
                        }
                        -- Round 2 dump: CPP_MapGimmick_FieldItem.m_IsOpen is the picked-up flag,
                        -- and the reward is on the actor (CPP_MapGimmick_ItemObjectBase).
                        pcall(function() e.open = a.m_IsOpen == true end)
                        pcall(function()
                            e.itemId, e.itemNum, e.money = Int(a.m_ItemId), Int(a.m_ItemNum), Int(a.m_Money)
                        end)
                        pcall(function() e.visible = a.VisibleCondition:ToString() end)
                        out[#out + 1] = e
                    end)
                end
            end
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
-- Other struct types that map values can have, by their full short name: the title menu's
-- entries (round 11 probes; the names come from the executable).
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

-- Round 49 probe (ffrap_bossfight watch): the native functions of a /Script/mucha class that
-- are worth hooking, as RegisterHook paths. Left out: getters and checks (called all the time),
-- delegates (RegisterHook cannot hook them), and functions that are not native when the flags
-- can be read (FUNC_Native is 0x400). Returns the paths and whether the flags could be read, or
-- nil when the class is not found.
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

-- The kinds of type object FindNames looks in: native classes and structs, and the classes
-- Blueprints make (round 11: the opening's names were not on any native class).
local TYPE_KINDS = { Class = true, ScriptStruct = true, BlueprintGeneratedClass = true,
                     WidgetBlueprintGeneratedClass = true, AnimBlueprintGeneratedClass = true }

-- Every game class or struct (/Script/mucha, or a Blueprint under /Game) whose own name, or the
-- name of one of its functions or fields, holds `text` (any case), as lines through out(line).
-- Walks every object once, so the game pauses for a moment. Objects being destroyed are skipped
-- (round 11: the walk crashed the game at the title screen). Returns the number of matches.
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
-- Title menu (IDEAS.md, idea 6). Experimental.
-- -------------------------------------------------------------------------------------------
-- The title menu's entries are ETitleFunctionType values (Continue 0, LoadGame 1, NewGame 2,
-- Option 3, QuitGame 4, Max 5), with one row each in DA_Title.EntryPropertyMap, and choosing one
-- calls CPP_VM_Title:ExecuteEntry(type) (round 11 probes). The Archipelago entry is type 5: a
-- copy of the New Game row. A hook on ExecuteEntry turns it into New Game (main.lua).

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

-- One title row's fields, as plain Lua values: everything TitleEntryProperty holds (round 12
-- inspect). The label is kept as the text it shows, in the current language.
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
        -- Round 37: every row but ours read "<MISSING STRING TABLE ENTRY>", at random, until a
        -- restart. A label reads like that while its string table is still loading, and the
        -- rebuild below writes each label back as plain text, so the placeholder became the
        -- label for that run. The order waits for the next check, with the map untouched.
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

-- Writes `line` above the game's version text in the title screen's corner ("1.0.1.0", then
-- the copyright lines). The version is a TextBlock whose text starts with four dotted numbers;
-- the new line goes in front of it, so it shows above when the block grows upwards. The title
-- widget is made again each time the title shows, so this is checked again now and then.
-- The block is right-justified, which pushed the version to the right once our longer line
-- widened it (round 14), so it is set to left-justified (ETextJustify Left = 0).
-- Returns "added", "already" or nil when no version text is on screen, and the TextBlock.
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

-- The Archipelago logo at the end of the mod's line in the title screen's corner. Round 15
-- found the version text (Text_ApplicationVersion) in an Overlay (Overlay_UI) of
-- WBP_TitleLayout, so an Image added to that overlay can share the text's alignment and be
-- placed by padding. Round 16 put it above the text (padding 60,0,50,97, two lines 43.2 high);
-- now it is one line high, just right of the first line ("FFRArchipelago <version>"), whose
-- width is the block's width because it is the longer line. The picture is loaded from the
-- mod's PNG at run time.
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

-- The chain of panels holding the first on-screen text widget whose text holds `text`, from
-- the widget up to the root, for the log: where a HUD element (the item feed) could go. Text
-- with icons in it is a RichTextBlock, which is not a TextBlock (round 24: the chest pop-up's
-- "(gil icon) 1"), so both kinds are searched.
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
-- The item feed (IDEAS.md, idea 14)
-- -------------------------------------------------------------------------------------------
-- A few lines of text at the bottom right of the field HUD: what arrived and what was sent.
-- Round 17's ffrap_layout found the field HUD's overlay: WBP_FieldLayout_C's Overlay_66 holds
-- the minimap, the key list (WBP_FieldFuncList2), the quest tracker and the place name. The
-- feed is one more child of it: a VerticalBox with a TextBlock per line, made in the field
-- layout's widget tree the way the title logo is. The HUD is made again on loads and map
-- changes, so the box is made again when its overlay changes.

local FEED_PREFIX = "FFRAP_Feed"
G.FEED_MAX = 5          -- lines on screen at once
G.FEED_SHOW = 10.0      -- seconds a line stays fully visible (round 23: a little longer)
G.FEED_FADE = 2.0       -- seconds it then takes to fade out
local FEED_LINE_GAP = { Left = 0, Top = 0, Right = 0, Bottom = 6 }   -- space under each line
-- 140 px up: clear of the "Back" prompt that menus and the chest pop-up put at the very bottom
-- right (round 21).
local FEED_PADDING = { Left = 0, Top = 0, Right = 48, Bottom = 140 }
local FEED_FONT_SIZE = 20
-- EHorizontalAlignment and EVerticalAlignment are Fill 0, Left/Top 1, Center 2, Right/Bottom 3.
-- 0.9.0 to 0.9.3 had right as 2, which is centre (round 21). ETextJustify is Left 0, Center 1,
-- Right 2.
local ALIGN_RIGHT, ALIGN_BOTTOM, JUSTIFY_RIGHT = 3, 3, 2
local feed = { box = nil, host = nil, tree = nil, lines = {}, made = 0 }

-- Round 18: 0.9.0 crashed the game the first time it made the feed in the field. A crash in the
-- engine ends the game before the Lua can log anything, so while the feed is being tested every
-- risky call is announced through G.feedTrace first: the last line in UE4SS.log names the call.
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

-- The first instance of a widget class that is on screen. FindFirstOf can hand back a copy that
-- is never drawn, such as the template a widget Blueprint keeps (round 22: the feed went into a
-- 0x0, never-visible HUD, and the key guide's font came back empty).
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
function G.OnField()
    return FeedHost() ~= nil
end

-- Round 46: a shiny that is a location gives 1 gil, as a blanked chest does, and the check is the
-- real reward. The reward is on the actor. Same rule as the apworld's: items below the shuffle
-- limit and gil (`shinies`), and Tablet Shards (`shards`, round 47). Returns true when it wrote.
local TABLET_SHARD = 25004
function G.BlankFieldItem(e, shinies, shards)
    if e.open or not e.actor then return false end
    local id, money = e.itemId or -1, e.money or -1
    if id == BLANK.ItemId and money == BLANK.Money then return false end
    local isShard = id == TABLET_SHARD
    local isLocation = (id >= 0 and id < SHUFFLE_ID_LIMIT) or (id < 0 and money > 0)
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
    if feed.box and Alive(feed.box) and feed.host == hostName then return feed.box end
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
    feed.box, feed.host, feed.tree, feed.lines = box, hostName, tree, {}
    return box
end

-- Makes the text look like the HUD's own: the key guide's font (its Text_Name, as FFRSLib reads
-- it) at FEED_FONT_SIZE, with a dark shadow, right-justified. The text stays the default white.
--
-- Round 20: `tb:SetFont(guide.Text_Name.Font)` crashed the game. A font (FSlateFontInfo) or a
-- Slate colour (FSlateColor) holds engine-only parts that a struct passed from Lua does not
-- carry, so no function here is given one. Each field is written into the new line's own
-- properties instead (plain values, an object and a name), before the line is added to the box:
-- the engine builds the on-screen text from these properties when the line is added.
local function StyleLine(tb)
    -- The key guide's text is a CommonTextBlock, which can take its font from a style when it is
    -- drawn and leave its own Font.FontObject empty. A line given an empty font object draws
    -- nothing (round 21: every step worked and no line showed), so the font is only copied
    -- when there is one.
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
    step("style: font size (field write)")
    pcall(function() tb.Font.Size = FEED_FONT_SIZE end)
    step("style: shadow colour (field writes)")
    pcall(function()
        local c = tb.ShadowColorAndOpacity
        c.R, c.G, c.B, c.A = 0, 0, 0, 0.85
    end)
    step("style: justification (field write)")
    pcall(function() tb.Justification = JUSTIFY_RIGHT end)
end

-- Adds a line to the feed; `now` is the caller's clock in seconds. opts.plain leaves out the
-- styling (font, colour, shadow, justification). Returns true, or false and why not (off the
-- field, say), so the caller can show the text another way.
function G.FeedLine(text, now, opts)
    local box, why = FeedBox()
    if not box then return false, why end
    local cls = Find("/Script/UMG.TextBlock")
    if not cls then return false, "no TextBlock class" end
    local tb
    step("make a line (StaticConstructObject TextBlock)")
    local okNew, err = pcall(function() tb = StaticConstructObject(cls, feed.tree, FeedName()) end)
    if not (okNew and tb and tb:IsValid()) then return false, "could not make a line: " .. tostring(err) end
    step("set the line's text")
    pcall(function() tb:SetText(FText(text)) end)
    if not (opts and opts.plain) then StyleLine(tb) end
    local slot
    step("add the line to the box (AddChildToVerticalBox)")
    local okAdd, errAdd = pcall(function() slot = box:AddChildToVerticalBox(tb) end)
    if not (okAdd and slot) then return false, "AddChildToVerticalBox failed: " .. tostring(errAdd) end
    step("align the line")
    pcall(function() slot:SetHorizontalAlignment(ALIGN_RIGHT) end)
    pcall(function() slot:SetPadding(FEED_LINE_GAP) end)
    step("line done")
    feed.lines[#feed.lines + 1] = { tb = tb, born = now }
    while #feed.lines > G.FEED_MAX do
        pcall(function() feed.lines[1].tb:RemoveFromParent() end)
        table.remove(feed.lines, 1)
    end
    return true
end

-- What the engine says about the feed, as lines for the log: the box's and each line's size,
-- visibility and font. ffrap_feed check (round 21: the lines were made and none showed).
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
    if not (feed.box and Alive(feed.box)) then
        out[#out + 1] = "box: none"
        return out
    end
    local parent = "?"
    pcall(function() parent = feed.box:GetParent():GetFName():ToString() end)
    local h, v = "?", "?"
    pcall(function() h = tostring(feed.box.Slot.HorizontalAlignment) end)
    pcall(function() v = tostring(feed.box.Slot.VerticalAlignment) end)
    out[#out + 1] = "box: " .. size(feed.box) .. ", " .. vis(feed.box) .. ", in " .. parent ..
        ", alignment " .. h .. "/" .. v
    for i, line in ipairs(feed.lines) do
        local text, font, fsize, opacity = "?", "?", "?", "?"
        pcall(function() text = line.tb:GetText():ToString() end)
        pcall(function()
            local f = line.tb.Font.FontObject
            font = (f and f:IsValid()) and f:GetFName():ToString() or "none"
        end)
        pcall(function() fsize = tostring(line.tb.Font.Size) end)
        pcall(function() opacity = tostring(line.tb:GetRenderOpacity()) end)
        out[#out + 1] = string.format("line %d: \"%s\", %s, %s, font %s size %s, opacity %s",
            i, text, size(line.tb), vis(line.tb), font, fsize, opacity)
    end
    if #feed.lines == 0 then out[#out + 1] = "lines: none (they fade after " .. (G.FEED_SHOW + G.FEED_FADE) .. " s)" end
    return out
end

-- Fades and removes old lines. Returns how many are on screen.
function G.FeedTick(now)
    local keep = {}
    for _, line in ipairs(feed.lines) do
        local age = now - line.born
        if age >= G.FEED_SHOW + G.FEED_FADE or not Alive(line.tb) then
            pcall(function() line.tb:RemoveFromParent() end)
        else
            if age > G.FEED_SHOW then
                local alpha = 1 - (age - G.FEED_SHOW) / G.FEED_FADE
                pcall(function() line.tb:SetRenderOpacity(alpha) end)
            end
            keep[#keep + 1] = line
        end
    end
    feed.lines = keep
    return #keep
end

-- -------------------------------------------------------------------------------------------
-- The chest pop-up (IDEAS.md, idea 13)
-- -------------------------------------------------------------------------------------------
-- A chest that is an Archipelago location gives 1 gil, so its pop-up says "You obtained the
-- following:" over a "(gil icon) 1" line. Round 25 found the pop-up: the game's general dialog
-- box (WBP_DialogBox_C), whose message is a CommonRichTextBlock (Text_Message) beside an
-- Overlay (Overlay_Custom) that holds the item line. The message is rewritten with what the
-- chest held for Archipelago, and the item line is collapsed. The dialog box is used by other
-- pop-ups too, so the line is made visible again once this pop-up has closed.

local POPUP_MARKER = "obtained"       -- in the game's English chest message
local POPUP_ITEM_LINE = "Overlay_Custom"
local COLLAPSED = 1                   -- ESlateVisibility: Visible 0, Collapsed 1, Hidden 2, ...
local popupHidden = nil               -- { line = widget, message = widget, visibility = n }
-- The dialog box is made once and used again, so its message widget is kept once found: the
-- fast check (PopupJustOpened, ten times a second) then asks only that widget, instead of
-- searching every rich text in the game (round 26: "the wait is real").
local popupMsgCache = nil
local popupWasShown = false           -- the cached message was on screen at the last check

local function PopupText(b)
    local t
    pcall(function() t = b:GetText():ToString() end)
    return t
end

-- The chest pop-up's message on screen, or nil. Searched for while none is cached.
local function PopupMessage()
    local m = popupMsgCache
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
                popupMsgCache = b
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
    local m = popupMsgCache
    if not (m and Alive(m) and Shown(m)) then
        popupWasShown = false
        return false
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
-- detail, or false and why not (no pop-up on screen yet).
function G.ChestPopup(text)
    local msg = PopupMessage()
    if not msg then return false, "no chest pop-up on screen" end
    if not pcall(function() msg:SetText(FText(text)) end) then return false, "SetText failed" end
    popupWasShown = true   -- this pop-up is handled; the fast check waits for the next one
    local parent
    pcall(function() parent = msg:GetParent() end)
    local n = 0
    pcall(function() n = parent:GetChildrenCount() end)
    for i = 0, n - 1 do
        local child, name
        pcall(function() child = parent:GetChildAt(i) end)
        pcall(function() name = child:GetFName():ToString() end)
        if name == POPUP_ITEM_LINE and Alive(child) then
            local was = 0
            pcall(function() was = child:GetVisibility() end)
            if pcall(function() child:SetVisibility(COLLAPSED) end) then
                popupHidden = { line = child, message = msg, visibility = was }
                return true, "text set, item line hidden"
            end
        end
    end
    return true, "text set (no item line found to hide)"
end

-- Makes the item line visible again once the pop-up has closed. Call every tick.
function G.ChestPopupRestore()
    if not popupHidden then return end
    if not Alive(popupHidden.line) then
        popupHidden = nil
        return
    end
    if Alive(popupHidden.message) and Shown(popupHidden.message) then return end
    local v = popupHidden.visibility
    pcall(function() popupHidden.line:SetVisibility(v) end)
    popupHidden = nil
end

-- Round 49: the game crashed on leaving a cave, in a Lua tick that asked a freed object for its
-- name. A map load frees the old map's objects, and a few were still cached here, above all the
-- map manager, which is asked every tick. Even IsValid on such a handle can crash, so a map load
-- forgets them before the next tick. They are found again when next needed.
function G.ForgetObjects()
    liveCache = {}
    popupMsgCache, popupWasShown, popupHidden = nil, false, nil
end

-- Tries to show `text` with the game's quest-notice banner (the "new quest" pop-up): the
-- banner's view model holds NoticeData.NoticeTitle and ExecuteNotics(bool) (round 14 probes).
-- Experimental: returns ok and a detail.
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
-- Prologue skip (IDEAS.md, idea 2)
-- -------------------------------------------------------------------------------------------
-- Makes a new game's save look like the start of chapter 1 in front of the Earth Shrine: the
-- fields the prologue changes, measured by save snapshots on 2026-11-05 (new game at story
-- 1000 against chapter 1 at story 1030). Fields are written straight into the save object,
-- because the skip ends with a save and a reload and the save object is what gets written.
-- The game's own calls are used where a direct write is awkward (inventory, visited maps).

G.SKIP_FROM_MAX = 1005    -- a save up to this story counter is still at the prologue's start
-- Round 9: a skip during the opening movie (story 1000) reloads into the shrine with no menus
-- and no movement; the movie's input lock outlives the reload. From 1005, when the player first
-- controls Fina (the game autosaves there), the reload comes up clean.
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
G.SKIP_ARRIVAL = { map = 3001, x = -5775.0, y = 0.0, z = -197.85, direction = 2 }
-- The open world start (round 31, found with FFRSLib's story and travel tools): story 7090,
-- then the Crystal Tower (map 3280), where two events move the story to 8000. Round 36's
-- snapshots showed those events write nothing else into the save, so the start can write 8000
-- itself and put the player where the events leave them, and then nothing plays. Arrivals:
--   dock   story 8000 at the tower's dock, where the events end
--   air    story 8000 on the world map, riding the airship beside the tower: what boarding at
--          the dock wrote (the airship's place and direction, riding, event flag 31). The
--          default since round 37, when the user chose it over the dock
--   event  story 7090 at the dock, near save point 139: the two events play (rounds 31, 35)
G.OPEN_STARTS = {
    dock = { name = "dock", story = 8000, map = 3280, x = -2704.8, y = -171166.7, z = 3002.2, direction = 2 },
    air = { name = "air", story = 8000, map = 1000, x = -5935.0, y = -8305.0, z = 2075.0, direction = 2,
            airship = true, flags = { 31 } },
    event = { name = "event", story = 7090, map = 3280, x = -2830.0, y = -171140.0, z = 3000.0, direction = 2 },
}
G.OPEN_START = G.OPEN_STARTS.air

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

-- The map and point a reload starts the player at, as FFRSLib's ffrs_travel writes them. An
-- arrival with `airship` also puts the airship there with the player riding it, and `flags`
-- are turned on (what boarding the airship wrote in round 36). Returns ok and a report line.
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
            -- Round 39: the airship was gone after a visit to a town. While this is false the
            -- game has not placed its airship yet, and its first placement (DT_MapAirShip's
            -- initSpawnPointId 9000) names a point that is in no map or landing table.
            sd.Map.IsAlreadySpawnAirship = true
        end
    end)
    local line = "arrival: map " .. a.map .. " at " .. a.x .. ", " .. a.y .. ", " .. a.z
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

-- A game value as text: a name, a string or an object's name. Array elements can come back in a
-- UE4SS wrapper that needs :get() first (round 37: the mapping contexts logged as
-- "LocalUnrealParam: 00000000713B9288").
-- Round 41: an array of objects can hold a null one, and asking a null object for its name is an
-- access violation that no pcall catches: the game crashed. IsValid is safe to ask.
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

-- What a join needs besides the party list: JoinStatus 0 and usable. Nothing is put in the bag:
-- round 46 saw a spare copy of the unit's gear. Returns how the status was set.
function G.FinishJoin(id)
    local how = G.SetJoinStatus(id, 0)
    local sd = G.SaveData()
    local entry = sd and UnitEntry(sd, id)
    if entry then Put(entry, "IsUsable", true) end
    return how
end

-- Active Time Chats (round 37: the user wants them all done). The 56 chats of DT_ChatEventData
-- (the rows named ATCnn; the table's Pinger and Nawatobi rows are mini-game lines, not chats).
-- The save keeps one row per chat in chat.DataMap (IsReleased, IsAlreadyPlayed), and the chats
-- waiting to be announced in chat.NoticeQueue. Every chat row turns on event flag 31.
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

-- What the story turns on that an open world start still needs:
--   21, 24   visions on the Equip screen (round 39: C01_014_04, at Mitra)
--   13, 34, 1180   fast travel, as Tutorial_FastTravel sets them (round 44; 34 is the Map screen's own)
--   102      the Earth Shrine's exit (round 44: its NoEntry event holds while 102 is off; C01_010_02)
--   25       staggering enemies (round 45: C01_008_02, the Earth Shrine's boss)
--   28       Fina's esper summoning (round 45: C01_037_01_Choice_After, after Siren)
--   90       Siren earned (round 45); her summon itself is an ability, see GrantSiren
-- 1160-1199 and 1217-1229 are every tutorial's "seen" flag (round 45: the OnFlagList of every
-- Tutorial_ row in the talk event table). Tutorials in battles and on maps test these.
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

-- The talk event table, and the two kinds of row in it (ETalkEventType).
local SHOP_TABLE = "/Game/Datatable/Event/TalkEvent/CDT_TalkEventData_Prod.CDT_TalkEventData_Prod"
local EVENT_SEQUENCE, EVENT_BLUEPRINT = 0, 1

-- The 16 sanctum crystals (round 46; data/crystals.tsv). Walking up to one starts event
-- Int_LegendEV_NN_01, or _01_Short after your first; a long scene and three questions end in
-- Int_LegendEV_NN_07, which sets the crystal's flag and gives the vision. So: the opening rows
-- jump straight to row 07, row 07 keeps its flags and gives nothing, and no scene plays (a
-- Blueprint row with no Blueprint is a no-op: the table has such rows, which the story runs).
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

-- Round 46: flag 90 alone did not put Siren in the summon menu. An esper is an ability on both
-- Finas: the event after her fight has AddAbilities [6, 430980] and AddCommandAbilities [6] for
-- units 1003 and 1006. 6 is the summon command, 430980 is Siren. Her fight is a story event, so
-- both Finas simply start with her. Safe to run again.
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

-- Round 45: the moogle's Vision Enhancement screen has no way out when the save owns no vision.
-- The three talk events that open it are Blueprint rows. While the save owns none they are made
-- Sequence rows, which with no sequence set do nothing (the table has such rows, as cushions).
-- Writes only when the state changes; `force` after a save loads, as a reload can restore a table.
local SHOP_ROWS = { VisionUpgrade = true, VisionUpgrade_Main = true, FEV_Town_10Cry_41_720_01 = true }
local shopBlocked = nil
function G.VisionShopGuard(force)
    local sd = G.SaveData()
    if not sd then return nil end
    local owned
    if not pcall(function() owned = #sd.visionList end) or not owned then return nil end
    local block = owned == 0
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
-- opts.openStart = true writes the open world start (G.OPEN_START) in place of story 1030 and
-- the Earth Shrine.
function G.SkipPrologue(opts)
    local doInventory = not (opts and opts.inventory == false)
    local storyTo = (opts and opts.openStart) and G.OPEN_START.story or G.SKIP_STORY
    local a = (opts and opts.openStart) and G.OPEN_START or G.SKIP_ARRIVAL
    -- The starting party: Rain and Lasswell, or what the seed says (round 44). Nothing in the save
    -- needs either of them: the game's hard-coded uses are story events, which this start skips.
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

    -- Join status: the starters in (0); Archwitch Fina (the prologue's Fina) out (2) unless she is one.
    local rain, fina = UnitEntry(sd, 1001), UnitEntry(sd, ARCHWITCH_FINA)
    local okJoin, joined = rain ~= nil and fina ~= nil, {}
    for _, id in ipairs(party) do
        local entry = UnitEntry(sd, id)
        okJoin = entry ~= nil and Put(entry, "JoinStatus", 0) and Put(entry, "IsUsable", true) and okJoin
        joined[#joined + 1] = UNIT_NAMES[id] or tostring(id)
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
    for _, m in ipairs(SKIP_MAPS) do
        local okAdd = perMap and pcall(function() perMap:AddKnownMap(m); perMap:AddVisitedMap(m) end)
        local visited
        pcall(function() visited = perMap:IsVisited(m) end)
        if not okAdd or visited ~= true then mapBad[#mapBad + 1] = tostring(m) end
    end
    step(perMap ~= nil and #mapBad == 0, "maps known and visited: " .. table.concat(SKIP_MAPS, ", ")
        .. (#mapBad > 0 and (" (failed: " .. table.concat(mapBad, ", ") .. ")") or ""))

    -- Where the reload puts the player: in front of the Earth Shrine, or at the Crystal Tower.
    step(WriteArrival(sd, a))

    if opts and opts.openStart then
        step(G.MarkChatsPlayed(sd))
        step(EnableOpenWorld(sd))
        step(GrantSiren(sd))
        -- Round 44: Jake came in at his story level, 27. Everyone starts at 1, and a member who
        -- joins later comes in at the party's level (main.lua).
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

-- Writes the open world start (G.OPEN_START: story 7090 and the Crystal Tower arrival) into
-- the loaded save, for a save that has already had the prologue skip (round 31 did these two
-- steps by hand after the skip). Saves nothing. Returns ok and report lines, as SkipPrologue.
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

-- Round 9: a reload during the opening movie came up with no menus and no movement, and what
-- holds that lock is not known yet (IDEAS.md, idea 6). The input state as text, to compare a
-- locked game with a normal one: the player controller's own switches (round 36: false in the
-- movie, the locked game and a normal game alike, so not those), then the game's own input
-- manager (a world subsystem, new on each map): IsEnableInput, its input mode, and its stack of
-- mapping contexts.
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

-- The first vision's entry and its synchro keys, to the log. Round 38 read G.VISION_SYNCHRO_KEYS
-- with this; a future patch or DLC that adds a party member would show here.
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
-- Artificial gates and custom key items (IDEAS.md, idea 16). Experimental.
-- -------------------------------------------------------------------------------------------
-- Off until `ffrap_gate` runs from the console. Every engine call announces itself through
-- G.gateTrace first so UE4SS.log names the call if the engine crashes.

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
        local cls = LoadBlueprintClass(spec.pkg, spec.name)
        if not cls then
            gateState = { actors = spawned }
            G.ClearGate()
            return false, "could not load class " .. spec.pkg .. "." .. spec.name .. "_C"
        end
        gateStep("SpawnActor " .. spec.name)
        local actor
        local okSpawn = pcall(function() actor = pose.world:SpawnActor(cls, locArg, rotArg) end)
        if not (okSpawn and actor and actor:IsValid()) then
            gateStep("SpawnActor empty-transform fallback " .. spec.name)
            pcall(function() actor = pose.world:SpawnActor(cls, {}, {}) end)
        end
        if not (actor and actor:IsValid()) then
            gateState = { actors = spawned }
            G.ClearGate()
            return false, "SpawnActor failed for " .. spec.name
        end
        -- Ensure the actor sits at (tx, ty, tz) even when SpawnActor ignored the transform table.
        local ax, ay, az
        pcall(function()
            local aloc = actor:K2_GetActorLocation()
            if aloc then ax, ay, az = aloc.X, aloc.Y, aloc.Z end
        end)
        if not ax or math.abs(ax - tx) + math.abs(ay - ty) > 1.0 then
            gateStep("K2_SetActorLocation " .. spec.name)
            pcall(function() actor:K2_SetActorLocation(locArg, false, {}, true) end)
            pcall(function() actor:K2_SetActorRotation(rotArg, true) end)
        end
        if sc then
            gateStep("SetActorScale3D " .. spec.name)
            pcall(function() actor:SetActorScale3D({ X = sc, Y = sc, Z = sc }) end)
        end
        gateStep("enable visibility and collision " .. spec.name)
        pcall(function() actor:SetActorHiddenInGame(false) end)
        pcall(function() actor:SetActorEnableCollision(true) end)
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
-- Open world probes (rounds 31 and 32): enemy levels, the airship, no-landing boxes
-- -------------------------------------------------------------------------------------------
-- Enemy stats are fixed per unit in DT_UnitParameter: no enemy has a level curve
-- (LevelParamId -1). So a scaled enemy is a rewritten row.
--
-- How a stat moves with level (round 32): a fit over the normal enemies of the encounter
-- tables, log(stat) = a + b*log(level) + c*level (r2 0.48 to 0.88; docs/open_world.md).
-- Only the ratio between two levels is used, so `a` drops out:
--   stat at L = own stat * (L / own)^b * e^(c * (L - own)).
-- Round 31 used a plain growth per level. That moved low enemies too little: a level 30
-- enemy pulled to level 2 kept too much attack. Levels above 70 (the last level in the data)
-- count as 70 for the curve. MP is left alone: it does not follow level.
local UNIT_TABLE = "/Game/Datatable/Unit/DT_UnitParameter.DT_UnitParameter"
G.ENEMY_CURVE = {
    MaxHitPoint = { 0.3675, 0.08917 }, MaxBreakPoint = { -0.1249, 0.05094 },
    Attack = { 0.3207, 0.02946 }, Defence = { 0.7752, 0.00867 },
    Intelligence = { 0.5644, 0.03269 }, Mind = { 0.7289, 0.01236 },
    Agility = { 0.7853, 0.00899 }, Experience = { -0.0647, 0.12967 }, Money = { 0.0934, 0.09910 },
    -- Not a unit's stat: the MRP a battle gives, `ap` in DT_BattleGroup, against its enemies'
    -- average level. Round 47: 459 groups without a boss, r2 0.70.
    BattleMRP = { 0.0689, 0.06162 },
}
G.CURVE_TOP = 70
local GROWTH_ORDER = { "MaxHitPoint", "MaxBreakPoint", "Attack", "Defence", "Intelligence", "Mind",
                       "Agility", "Experience", "Money" }
-- Which stats each tuning knob multiplies: `hp` the HP, `attack` the physical damage stat,
-- `magic` the magic one (round 33: physical hits were much stronger than spells).
local KNOB_STATS = { MaxHitPoint = "hp", Attack = "attack", Intelligence = "magic" }
local CATEGORY_ENEMY, CATEGORY_BOSS = 2, 3     -- eUnitCategory
G.MAX_LEVEL = 99

-- How much a stat grows from level `from` to level `to` (a factor; 1 when they are equal).
function G.CurveRatio(stat, from, to)
    local k = G.ENEMY_CURVE[stat]
    if not k then return 1 end
    from = math.max(1, math.min(from, G.CURVE_TOP))
    to = math.max(1, math.min(to, G.CURVE_TOP))
    return (to / from) ^ k[1] * math.exp(k[2] * (to - from))
end

-- The stats of a unit moved from its own level to `level`. Pure: `orig` holds Level and the
-- stats in ENEMY_CURVE. `knobs` (optional) holds percentages: hp (MaxHitPoint), attack
-- (Attack) and magic (Intelligence), 100 when missing. A stat that is 0 stays 0, and no other stat goes
-- below 1.
function G.ScaledStats(orig, level, knobs)
    knobs = knobs or {}
    local out = { Level = level }
    for _, k in ipairs(GROWTH_ORDER) do
        local v = orig[k] or 0
        if v > 0 then
            local knob = KNOB_STATS[k] and knobs[KNOB_STATS[k]] or 100
            out[k] = math.max(1, math.floor(v * G.CurveRatio(k, orig.Level, level) * knob / 100 + 0.5))
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

-- The band of enemy levels for a party level: centred on `at` percent of the party's level
-- (100: the party's own level), plus or minus `range`. In the shipped game the party gets well
-- ahead of the enemies from Olderion on (round 32), so `at` below 100 is closer to it.
function G.LevelBand(partyLevel, range, at)
    local c = math.max(1, math.floor(partyLevel * (at or 100) / 100 + 0.5))
    return c - range, c + range, c
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

-- Sets a party member's level, as the XP the game says it takes (FFRSLib's ffrs_unit_level), and
-- fills HP and MP for it (isMaxStatusSet: without it a unit brought down from level 27 keeps
-- level 27's HP). Round 44. Returns ok and a detail.
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

-- Round 44: the save slot's level stayed at 1 in a party without Rain, so the game takes it from
-- her. While she has not joined her level is ours to set: it follows the party. She joins at the
-- party's level anyway. Returns true when it wrote a level.
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

-- Round 33's log: a rescale read Steel Bat (shipped level 1, HP 68) as level 47, HP 4800, and
-- later 214 rows no longer held what we wrote. The FFR Randomizer mod did both: its enemy
-- shuffle gives Steel Bat the stats of Nanochu (level 47), and it writes its rows again every
-- 3 seconds. So "original" is the table's latest values, not the shipped ones: a row that
-- changed since our last write gives a new original, and `off` gives back what is there.
local scaleOriginals = {}   -- unit id -> { Level = n, MaxHitPoint = n, ... } as the game last had it
-- Round 47: MRP is on the battle group, not the enemy, so a rescale left it alone, and a seed that
-- started on a late continent got far more of it. A group's MRP follows its enemies' average level.
local BATTLE_GROUP_TABLE = "/Game/Datatable/Encount/DT_BattleGroup.DT_BattleGroup"
local groupOriginals, groupWrote = {}, {}   -- battle group id -> MRP as shipped, and as last written
local function ScaleBattleGroups(mode, wanted)
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
                            if wanted[unit] and scaleOriginals[unit] then
                                from, to, n = from + scaleOriginals[unit].Level, to + wanted[unit], n + 1
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
-- and knobs (round 49: bosses were too easy at the enemies' 75%). mode "off" restores the originals. Returns how many
-- rows changed, one sample line (the first enemy that changed) for the log, a line per changed
-- row (for scale.txt), and how many rows something else had changed since our last write
-- (their values became the new originals).
function G.ScaleEnemies(mode, a, b, withBosses, knobs, bossBand)
    local family = TableFamily(Find(UNIT_TABLE))
    if #family == 0 then return nil, "DT_UnitParameter not loaded" end
    local changed, sample, lines, gameChanged = 0, nil, {}, 0
    local wanted = {}
    local fields = { "Level" }
    for _, k in ipairs(GROWTH_ORDER) do fields[#fields + 1] = k end
    for _, dt in ipairs(family) do
        pcall(function()
            dt:ForEachRow(function(_, row)
                local okRow, err = pcall(function()
                    local cat = Int(row.Category)
                    if not (cat == CATEGORY_ENEMY or (withBosses and cat == CATEGORY_BOSS)) then return end
                    local id = Int(row.ID)
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
                    local want = orig
                    if mode ~= "off" then
                        local band = (cat == CATEGORY_BOSS and bossBand) or { a = a, b = b, knobs = knobs }
                        want = G.ScaledStats(orig, G.ScaledLevel(orig.Level, mode, band.a, band.b), band.knobs)
                    end
                    wanted[id] = want.Level
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
    local groups = ScaleBattleGroups(mode, wanted)
    if groups > 0 then sample = (sample and (sample .. "; ") or "") .. "MRP changed in " .. groups .. " battle groups" end
    if mode == "off" then scaleWanted, scaleTables = nil, nil
    else scaleWanted, scaleTables = wanted, TableKeys(family) end
    return changed, sample, lines, gameChanged
end

-- Round 33: a Pharm enemy showed a level that the last rescale did not give it. Whether the
-- table still holds what the last rescale wrote. Returns how many rows it checked, how many
-- differ, one sample ("Metal Gigantuar (298): level 45, HP 9000, wrote level 3"), and whether the table is a
-- different object now (loaded again). nil when no rescale is in force, or the table is gone.
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

-- No-landing boxes (round 32). The world map has 111 BP_MapNonLandingArea_C actors.
-- Each is a box (a CPP_MapAirShipCanNeverLandingBox component) with an m_Condition string;
-- while the condition holds (or when it is empty), the airship cannot land in the box. Before
-- story 5020 one big box (2400 x 6000 x 700, condition {progress:0}<5020) keeps the airship
-- off Mysidia. So a continent lock can be the same: a big box with our own condition. The
-- Blueprint has no script: the box and the condition are read by C++ (CPP_MapNonLandingArea).
--
-- Round 32: a box spawned at the airship, 6000 tall, lifted the airship over it (its collision
-- counts as ground), and the airship could still land. So boxes now go where the game puts
-- its own: centred at height 393, 700 up and down, like the Mysidia box.
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

-- Round 33: a changed condition took effect only after the airship landed and took off again,
-- and a spawned box hid the airship's shadow. So the game reads the condition at some moments
-- and does something to the box; the collision is the first guess. A box's collision as text:
-- the actor's switch, the component's ECollisionEnabled (0 none, 1 query, 2 physics, 3 both),
-- its profile and object type, and its response to channels 0 to 7 and 14 to 31 (the game's
-- own channels), one digit each (0 ignore, 1 overlap, 2 block).
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

-- Round 35: `lock pharm` did nothing that could be seen, and the Pharm story box was not found
-- by eye. It sits at z 110 to 370, and some of Pharm is high ground, so the box may be buried.
-- What is under the player: a line trace straight down on the Visibility channel, which the
-- no-landing boxes block while their collision is on. The player's own actor (the airship in
-- flight) is ignored. A no-landing box that is hit is listed, and the trace goes on from under
-- its bottom, so the ground comes last. Returns a list of { name, z, box }, or nil and why.
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
        -- Round 36: the hit is a component (BoxComponent, LandscapeHeightfieldCollisionComponent_80),
        -- so the box is known by its owner's name.
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

-- Adds the spawned boxes that are not listed yet to the shadow's ignore list on `pawn`. The
-- airship's shadow is placed by a sphere trace, and the game lists every one of its own
-- no-landing boxes for that trace to ignore (round 38: 111 boxes, the airship itself,
-- CPP_MuchaWorldSetting and StaticMeshActor_2). A listed box gives the red shadow over it, and
-- landing stays blocked. Returns the list's size before and after, and the names in it that are
-- not the game's own boxes, and how many entries are null (round 41); nil when `pawn` is not the
-- airship. `actors` defaults to the probe's spawned boxes.
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

-- Spawns a new no-landing box under the player: `half` across each way (default 2000), 1400
-- tall, its top at `top` (default 1093: the Mysidia box's top). Round 35: on high ground the
-- default box may be buried, so the top can be set above the ground that GroundUnder finds.
-- Returns the box, or nil and why.
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
    ShadowIgnoreAdd(pose.pawn)   -- round 38: without this the shadow is gone over the box
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

-- Round 36: over a spawned box the airship's shadow is gone. The boxes block the Visibility
-- channel (3), which a shadow is likely placed with. Sets the spawned boxes' response to one
-- channel (0 ignore, 1 overlap, 2 block), to find a setting that keeps the shadow and still
-- blocks landing. Returns how many boxes took it.
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
-- Every box with the story condition is written (round 33: a lock that did nothing may have
-- missed a second box). Returns the boxes read back (a list), or nil and why.
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

-- Round 34 probe: make the boxes we changed take effect now, without landing. Each box's
-- collision is switched on (as on a box with no condition, which always blocks) when its
-- condition is one that holds, and off when it never holds. Only conditions we wrote are
-- judged: "" and COND_ALWAYS hold, COND_NEVER does not; other boxes are left alone. Returns
-- how many were switched on and off, and the collision value used for "on".
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

-- Round 37: setting channels 3 and 4 did not bring the shadow back; round 38: this list did
-- (CPP_MapUnit_AirShip.m_ShadowDecalSphareTraceActorsToIgnore). A spawn now does it by itself.
-- This adds any spawned box the airship the player is riding has not listed: after boarding
-- again, say. Returns as ShadowIgnoreAdd, or nil and why.
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
-- Round 38 and 39: a box on the shadow's ignore list gives the red shadow and blocks landing, and
-- the listing lasts through boarding. Round 40: a box does not last through a map change, so
-- ContinentSync places them again each time the world map loads.
-- A continent's lock is one event flag in the save: off is locked, on is open. So an unlock
-- belongs to the save, and an Archipelago item can open one with the existing `flag` item kind.
-- Flags 1420 to 1429 are used nowhere in the game's data (the game's own run up to 1413, then 1450).
G.WORLD_MAP = 1000
G.CONTINENTS = {
    { name = "grandshelt", flag = 1420, boxes = { { 8400, 17500, 20600, 24000 } } },
    { name = "lanzelt", flag = 1421, boxes = { { 7050, 9050, 18200, 13650 }, { 8400, 13650, 18200, 17500 }, { 10350, 8300, 18200, 9050 } } },
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
-- Syncs that must see one controller before boxes go in. Round 41: on the way back from a town
-- the boxes were placed once while the world map was still arriving, and again 3 seconds later.
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

-- Round 42: after loading a save in the air, the player could land in the first seconds, before
-- the first sync. This runs from the engine's LoadMap post hook, so the boxes are in before the
-- first frame of the new map and the player never has a moment without them. A new map always
-- means the old boxes are gone, so they are forgotten here whatever the map is. `place` is the
-- switch: off only forgets. Returns as PlaceLocked, or nil and why.
G.WORLD_LEVEL = "Wld_PL"
function G.ContinentMapLoaded(world, place)
    continentActors, continentListed, continentListedLength = {}, nil, nil
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
-- The boss fight test (ffrap_bossfight, round 49; IDEAS.md, idea 25)
-- -------------------------------------------------------------------------------------------
-- Can any boss be fought from anywhere, and can a win be seen? A battle group names the talk row
-- to run after a win (battleFinishEventId), which is how strong enemies give rewards. Mods 0.35.0
-- to 0.35.3 started the fight from a sanctum crystal through a borrowed talk row, and no battle
-- started in four tries, with the row's own group too. So the trigger is now a chest. Every chest
-- row has IsTrap, battleGroupId and battleFinishEventId: a monster-in-a-box. No shipped chest sets
-- IsTrap, so whether the engine still acts on it is what this finds out. The closed chests loaded
-- near the player become traps for the group. A live chest keeps its own copy of its row, so the
-- copy and the table row are both written, as chest blanking does.
-- The second trigger is the game's own: the sword pedestal in the Chamber of Arms (map 3290)
-- asks "challenge?" and goes straight to its fight row. Only that row's group number changes, so
-- the rest of the chain is as shipped. It needs the Ancient Greatsword in the bag and flag 901
-- off. If Siren appears there but not from a crystal, the crystal failure was our chain.
-- The win row sets a flag nothing else uses, so flag 901 stays off and the pedestal can be used
-- again. Round 49: with the Victory row made a Blueprint row with no Blueprint, both wins ended
-- on a black screen. The screen is faded out after a battle, and every after-win row the game
-- ships is a Sequence row. So the win row is now either the Victory row with its own scene
-- (only its flags and item change), or, with `quiet`, the magic pot fights' after-win row
-- Gim_EV_Majipot_Delete_02: a short shared sequence whose only effect is flag 915, which our
-- flag replaces. Round 49 tried choice_cancel (a Sequence row with no sequence) for `quiet`, and
-- the screen stayed black too: an after-win row needs a sequence to fade back in. `off` undoes
-- it all but the Victory row's item, which comes back when the game restarts.
G.BOSS_TEST_FLAG = 1440       -- no condition or talk row in the game uses flags 1430 to 1449
G.BOSS_TEST_SWORD = 10198     -- the Ancient Greatsword, which the sword pedestal checks for
local BOSS_TEST_FIGHT, BOSS_TEST_VICTORY, BOSS_TEST_QUIET = "12Arms_01Sword_1stAwake_Encount", "12Arms_01Sword_1stAwake_Victory", "Gim_EV_Majipot_Delete_02"
local bossTestSaved = nil     -- { talk = {}, group = id, groupFields = {}, chests = { ["map:id"] = {} } }

local function EachTalkRow(fn)
    for _, dt in ipairs(TableFamily(Find(SHOP_TABLE))) do
        pcall(function()
            dt:ForEachRow(function(name, row) pcall(fn, ObjText(name), row) end)
        end)
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
-- Player settings (round 50; IDEAS.md, idea 18)
-- -------------------------------------------------------------------------------------------
-- EXP, gil and MRP rates, random encounters and their rate. Our mod owns these. FFRS_QoL writes
-- the same rows with its multipliers and encounter settings, so with both on they undo each
-- other: turn FFRS_QoL's versions off. The rates are the reward rates per difficulty in
-- DT_GameDifficultyParam, as shipped: 1 for all, but MRP 1.5 on Expert. A random encounter comes
-- after walking a random distance between a map's encountMin/MaxMovementLength (the chocobo's
-- apart), and only where doMovementEncount is on. Those are MAP_DATA rows, one table per region.
-- A rate divides the distances, so 2 is twice as many battles. A map's row is read as it loads,
-- so while encounters are off the player on the current map also gets an encounter distance out
-- of reach, as FFRS_QoL does.
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

-- Round 50: our settings as rows of the game's Options screen, Gameplay tab (ffrap_menu add). The
-- tab is the rows of DT_OP_GameSetting. Round 50's probe showed the screen draws rows we add. A
-- row has a Type (Slider or RadioButton), a DisplayText, an ItemDescription (the footer) and an
-- EntryTag. The game saves each row's value as a float under its EntryTag, in the option save's
-- m_EntrySaveDataList (CPP_MuchaOptionSaveData): a slider's number, or a switch's index (On 0,
-- Off 1). So our rows get tags of their own, copied from a slider and a switch of the game's, and
-- their values are read back from that map. Sliders move in steps of 1.
-- Round 51: the screen held our values as pending changes, but Apply saved none of them: the save
-- had no entry under our tags, and the game only updates entries it has. So adding the rows also
-- adds an entry per tag (OPTION_SAVEDATA_SETTING: Value, IsDisplay, Type: Slider 1, RadioButton 2),
-- seeded from the current settings, unless the save has one already (the game keeps it on disk).
local OPTION_GAMEPLAY = "/Game/Datatable/UI/Option/Root/GameSetting/DT_OP_GameSetting.DT_OP_GameSetting"
local OPTION_SLIDER = "Delegate.UI.System.Option.Root.GameSetting.GamePad.Sensitivity"
local OPTION_SWITCH = "Delegate.UI.System.Option.Root.GameSetting.EncountSensor"
-- Round 56: the Difficulty row's choices (DT_OP_RadioButton_Difficulty) read Casual, Normal and
-- Expert, which is what our scaling strength needs. A copy has our tag, so it does not change the
-- game's own difficulty.
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
    { key = "encounterrate", row = "FFRAP_EncounterRate", copy = OPTION_SLIDER, min = 1, max = 5, default = 1,
      label = "AP: Encounter rate", help = "How often random battles come: 1 is normal, 5 is five times as often." },
    { key = "scaling", row = "FFRAP_Scaling", copy = OPTION_SWITCH, default = 0,
      label = "AP: Enemy scaling", help = "Enemies follow your party's level. Off: the game's own levels." },
    { key = "strength", row = "FFRAP_ScalingStrength", copy = OPTION_CHOICE, choices = 3, default = 1,
      label = "AP: Scaling strength", help = "How strong scaled enemies and bosses are. It stacks with the game's own difficulty." },
}

local ENTRY_SLIDER, ENTRY_RADIO = 1, 2

-- The option save's entries for our tags, added where missing. `current` is setting key -> number
-- or boolean. Returns how many were added, or nil when the option save is not found.
local function SeedOptionEntries(current)
    local save = Live("CPP_MuchaOptionSaveData")
    if not save then return nil end
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
            if o.min then value = math.min(o.max, math.max(o.min, tonumber(v) or o.default))
            elseif o.choices then value = math.min(o.choices - 1, math.max(0, math.floor(tonumber(v) or o.default)))
            else value = (v == false) and 1 or 0 end
            if pcall(function()
                save.m_EntrySaveDataList:Add({ TagName = FName(tag) }, { Value = value, IsDisplay = true, Type = o.min and ENTRY_SLIDER or ENTRY_RADIO })
            end) then added = added + 1 end
        end
    end
    return added
end

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
                if o.min then out[o.key] = value
                elseif o.choices then out[o.key] = math.floor(value + 0.5)
                else out[o.key] = math.floor(value + 0.5) == 0 end
            end)
        end)
    end)
    return out
end

-- Round 51: where our Options rows' values go (ffrap_menu dump). Round 50 set them and applied,
-- and nothing reached us. Lists every option save object found and its entries, and the open
-- Options screen's pending changes (CPP_VM_Option.ChangingOptionSetting). Returns lines.
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


return G
