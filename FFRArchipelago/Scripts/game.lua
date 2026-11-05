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

-- Adds a vision to the save's vision list and to the bag, the way FFRSLib's ffrs_vision_unlock
-- does: grow visionList by one zeroed entry, set its ID, copy the synchro-map keys (one per
-- party member, at 0) from the first entry, then AddInventory(id, 1).
-- The save must already own one vision to copy the keys from; the game hands one out early.
function G.UnlockVision(id)
    local sd = G.SaveData()
    if not sd then return "retry", "no save data" end
    local exists = VisionRowExists(id)
    if exists == nil then return "retry", "vision table not loaded" end
    if not exists then return "fail", "no DT_VisionItemData row for " .. id end

    local lib = Lib("CPP_BFL_Vision")
    local function Has()
        local ok, r = pcall(function() return lib and lib.HasVision and lib:HasVision(id) end)
        return ok and r == true
    end
    if Has() then return "ok", "already owned" end

    local list
    if not pcall(function() list = sd.visionList end) or not list then
        return "retry", "visionList unreadable"
    end
    local n = #list
    if n == 0 then return "retry", "the save owns no vision yet to copy synchro keys from" end

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
        local from, to = list[1].synchroPoints, list[n + 1].synchroPoints
        from:ForEach(function(key, _)
            to:Add(key:get(), 0)
            keys = keys + 1
        end)
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
-- full. For Archipelago we want "joined the roster", which may be a different call
-- (JoinStatus in sd.unitParameterList). Open question 1 in the README.
local function PartyVM() return Live("CPP_VM_Party") end

local function Joined(vm, id)
    local ok, r = pcall(function() return vm:IsJoinedUnit(id) end)
    return ok and r == true
end

function G.AddUnit(id)
    local vm = PartyVM()
    if not (vm and vm.AddUnit) then return "retry", "party view model not loaded" end
    if Joined(vm, id) then return "ok", "already joined" end
    local ok, r = pcall(function() return vm:AddUnit(id) end)
    if not ok then return "fail", "AddUnit raised: " .. tostring(r) end
    if Joined(vm, id) then return "ok", "AddUnit returned " .. tostring(r) end
    return "fail", "did not join (AddUnit returned " .. tostring(r) .. "; party full?)"
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
    if (Int(row.ItemId) or -1) >= SHUFFLE_ID_LIMIT then return false end
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
local saveStructs
local function SaveStructs()
    if saveStructs then return saveStructs end
    saveStructs = {}
    for _, short in ipairs(SAVE_STRUCT_NAMES) do
        pcall(function()
            local s = StaticFindObject("/Script/mucha.SaveData_" .. short)
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
function G.ListFunctions(className, out)
    local cls = StaticFindObject("/Script/mucha." .. className)
    if not (cls and cls:IsValid()) then return nil end
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
            out(className .. "." .. name .. "(" .. table.concat(params, ", ") .. ")")
        end)
    end)
    return n
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

return G
