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

-- The chain of panels holding the first on-screen TextBlock whose text holds `text`, from
-- the block up to the root, for the log: where a HUD element (the item feed) could go.
function G.LayoutOf(text)
    local tb
    local ok, all = pcall(FindAllOf, "TextBlock")
    if ok and all then
        for _, b in ipairs(all) do
            if Alive(b) then
                local t
                pcall(function() t = b:GetText():ToString() end)
                if t and t:find(text, 1, true) then tb = b break end
            end
        end
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
G.FEED_SHOW = 6.0       -- seconds a line stays fully visible
G.FEED_FADE = 1.5       -- seconds it then takes to fade out
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
local SKIP_INVENTORY = {            -- item id, change. Fina's prologue gear goes; the others' comes
    { 10100, 1 }, { 10200, 1 }, { 11000, 2 }, { 12000, 2 }, { 10699, -1 }, { 11301, -1 }, { 12029, -1 },
}
local SKIP_MAPS = { 5010, 2013, 20000, 3001 }   -- known and visited
G.SKIP_ARRIVAL = { map = 3001, x = -5775.0, y = 0.0, z = -197.85, direction = 2 }

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

-- Applies the skip to the loaded save. Saves nothing. Returns ok and a list of report lines,
-- one per step ("ok ..." or "FAIL ..."). ok is false when any step failed.
-- opts.inventory = false leaves the inventory alone. Its changes are relative, so that an
-- Archipelago item granted before the skip with the same id as a starter item is kept, and they
-- must be made once per save. Every other step sets an absolute value and can run again.
function G.SkipPrologue(opts)
    local doInventory = not (opts and opts.inventory == false)
    local report, failed = {}, false
    local function step(ok, what)
        report[#report + 1] = (ok and "ok   " or "FAIL ") .. what
        if not ok then failed = true end
    end
    local sd = G.SaveData()
    if not sd then return false, { "FAIL no save loaded" } end

    -- The story counter, as FFRSLib's ffrs_story_set writes it.
    local okStory = pcall(function() sd.Progress.Progress[1] = G.SKIP_STORY end)
    step(okStory and G.StoryCounter() == G.SKIP_STORY, "story counter -> " .. G.SKIP_STORY)

    -- Event flags: eventFlag is 0-based in the snapshots, so flag i is Lua element i + 1.
    local flags = nil
    pcall(function() flags = sd.Progress.eventFlag end)
    local bad = {}
    local function setFlag(i, on)
        local okSet = pcall(function() flags[i + 1] = on end)
        local now
        pcall(function() now = flags[i + 1] end)
        if not okSet or now ~= on then bad[#bad + 1] = i end
    end
    if flags then
        for _, i in ipairs(SKIP_FLAGS_ON) do setFlag(i, true) end
        for _, i in ipairs(SKIP_FLAGS_OFF) do setFlag(i, false) end
    end
    step(flags ~= nil and #bad == 0, "event flags: " .. #SKIP_FLAGS_ON .. " on, " .. #SKIP_FLAGS_OFF .. " off"
        .. (#bad > 0 and (" (failed: " .. table.concat(bad, " ") .. ")") or ""))
    -- Whether the game's own {flag:N} agrees with the array index, for the record.
    local libSays = G.GetFlag(SKIP_FLAGS_ON[1])
    report[#report + 1] = "     the game reads flag " .. SKIP_FLAGS_ON[1] .. " as " .. tostring(libSays)
        .. " (should be true if its numbering matches the array's)"

    -- The party: Rain and Lasswell. Reading one past the end grows the array (see UnlockVision).
    local okParty = pcall(function()
        local list = sd.Party.partyList
        for i, id in ipairs(SKIP_PARTY) do
            if #list < i then local _ = list[i] end
            list[i] = id
        end
    end)
    local partyNow = {}
    pcall(function()
        local list = sd.Party.partyList
        for i = 1, #list do partyNow[#partyNow + 1] = tostring(Int(list[i])) end
    end)
    step(okParty and table.concat(partyNow, ",") == "1001,1002", "party -> [" .. table.concat(partyNow, ", ") .. "]")

    -- Join status: Rain and Lasswell in (0), Fina out (2).
    local rain, lasswell, fina = UnitEntry(sd, 1001), UnitEntry(sd, 1002), UnitEntry(sd, 1006)
    step(rain and lasswell and fina and Put(rain, "JoinStatus", 0) and Put(lasswell, "JoinStatus", 0)
        and Put(fina, "JoinStatus", 2), "join status: Rain, Lasswell 0; Fina 2")

    -- Rain's baseParameterList[5] (0-based) goes 0 -> 3 in the prologue. Its meaning is unknown.
    local okBase = false
    if rain then pcall(function() okBase = Put(rain.baseParameterList, 6, 3) end) end
    step(okBase, "Rain baseParameterList[5] -> 3")

    -- Fina back to her chapter 1 self: level 1, her own weapon, no armor, accessories or skills.
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
    end
    step(okFina, "Fina reset: Experience 0, HP 200, MP 70, weapon 10600, no armor, accessories or skills")

    -- Inventory, through the game's call: equipped gear is counted in the bag.
    if doInventory then
        local inv = Lib("CPP_BFL_SaveDataInventory")
        local invBad = {}
        for _, e in ipairs(SKIP_INVENTORY) do
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

    -- Where the reload puts the player: in front of the Earth Shrine.
    local a = G.SKIP_ARRIVAL
    local okMap = pcall(function()
        sd.Map.mapId = a.map
        sd.Map.unitLocation.X = a.x
        sd.Map.unitLocation.Y = a.y
        sd.Map.unitLocation.Z = a.z
        sd.Map.unitDirection = a.direction
    end)
    step(okMap and G.MapId() == a.map, "arrival: map " .. a.map .. " at " .. a.x .. ", " .. a.y .. ", " .. a.z)

    return not failed, report
end

-- Writes the loaded save to a slot and starts the field from that slot, as FFRSLib's
-- ffrs_travel does. Returns ok and a detail.
function G.SaveAndReload(slot)
    local lib = Lib("CPP_BFL_SaveData")
    if not (lib and lib.SaveGameData) then return false, "CPP_BFL_SaveData not found" end
    local ok, err = pcall(function() lib:SaveGameData(slot) end)
    if not ok then return false, "SaveGameData(" .. slot .. ") raised: " .. tostring(err) end
    -- An autosave writes the player's real position over the save's map. If SaveGameData does
    -- the same, the reload would land on the prologue map again, so say so.
    local mapNow, flag1 = G.MapId(), G.GetFlag(1)
    local kept = "map " .. tostring(mapNow) .. ", flag 1 " .. tostring(flag1)
    if mapNow ~= G.SKIP_ARRIVAL.map then
        return false, "saved to slot " .. slot .. ", but the save's map is " .. tostring(mapNow)
            .. " after saving, not " .. G.SKIP_ARRIVAL.map .. " (SaveGameData wrote the real position). Not reloading"
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

return G
