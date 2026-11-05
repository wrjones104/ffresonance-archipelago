-- FFRArchipelago: the in-game half of the Final Fantasy Resonance Archipelago client.
--
-- What it does:
--   * Reads items from ap_in.txt and grants them in order: bag items, gil, visions, party
--     members and story flags. Each item is applied once, tracked by its Archipelago index.
--   * Reports opened chests (check chest:<mapId>:<uid>), picked-up shinies (check
--     shiny:<mapId>:<uid>) and story counter changes to ap_out.txt.
--   * Follows the client's session: a new `seed` line in ap_in.txt starts the mod's state over.
--   * Writes ap_status.txt every few seconds, so you can see what it thinks is going on.
--
-- The Archipelago client (apworld/ff_resonance/client.py) writes ap_in.txt and reads ap_out.txt.
-- What it does NOT do yet: replace shiny rewards, or stop story events giving theirs.
--
-- Console commands (open the UE4SS console, ConsoleEnablerMod):
--   ffrap_status                 what the mod sees right now
--   ffrap_grant <kind> <id> [n]  grant directly, without the bridge: item, gil, vision, unit, flag
--   ffrap_dump [rows]            chest and shiny discovery dump to ffrap_dump.txt
--   ffrap_export                 every chest table row to chests.tsv
--   ffrap_snapshot [name]        every field of the loaded save to snap_<name>.tsv (tools/snapdiff.py)
--   ffrap_functions [class ...]  the functions of game classes to functions.txt (default: save-data classes)
--   ffrap_blank [on|off]         chests that are Archipelago locations give 1 gil instead
--   ffrap_sync                   report every known location the save says is looted
--   ffrap_bind                   link the loaded save to the client's session (also /bind in the client)
--   ffrap_reset                  forget the applied-item count (re-grants everything!)
--
-- Each client session belongs to one save. A new game started during a session is linked to
-- it at once; an existing save is linked with ffrap_bind or the client's /bind. The link
-- follows the save slots the linked game is saved to. While any other save is loaded, the mod
-- grants nothing, reports nothing and leaves the chests vanilla.

local VERSION = "0.5.3"
local PROTOCOL = 1        -- the bridge protocol; the apworld's MOD_PROTOCOL

local MOD_DIR = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)Scripts/[^/]+$"))
    or "ue4ss/Mods/FFRArchipelago/"

local game = require("game")
local bridge = require("bridge")

local TICK_MS = 500
local SETTLE_TICKS = 4        -- wait this long after a save loads before granting
local MAX_GRANTS_PER_TICK = 5
local CHEST_EVERY = 2         -- ticks between chest scans
local STATUS_EVERY = 10       -- ticks between status file writes

local function log(msg)
    print("[FFRAP] " .. tostring(msg) .. "\n")
end

local function notify(msg)
    log(msg)
    game.Toast(msg)
end

-- -------------------------------------------------------------------------------------------
-- State
-- -------------------------------------------------------------------------------------------

local state = {
    applied = 0,       -- items 0 .. applied-1 are handled
    queue = {},        -- index -> { kind, id, count, label }
    reported = {},     -- "check|chest:2031:7" -> true: already written to ap_out.txt
    lastStory = nil,
    inGameTicks = 0,
    ticks = 0,
    lastResult = "",
    blank = false,     -- chest blanking (ffrap_blank, or the client's "cfg blank 1")
    seed = nil,        -- the client session ("<seed name>:<slot>") this state belongs to
    syncPending = false, -- report everything the save says is looted, once in game
    slots = {},        -- save slot -> true: the slots the session's save is in (empty: none yet)
    bindPending = false, -- the client asked to link the loaded save
}

-- The loaded save, and whether it is the session's. Not kept across game restarts: save data
-- objects are new each run.
local save = {
    obj = nil,         -- the save data object's name (G.SaveObjectName)
    ticks = nil,       -- its timestamp when last seen
    slot = nil,        -- the slot it was loaded from, or nil for an unsaved new game
    pending = nil,     -- a timestamp the game just saved with, until its slot is known
    ok = false,        -- true when this is the session's save
}

-- True when the loaded save is the session's. With no client session (fake_ap.py testing)
-- every save counts, as before 0.5.0.
local function sessionSave()
    return state.seed == nil or save.ok
end

local function slotsText()
    local list = {}
    for slot in pairs(state.slots) do list[#list + 1] = slot end
    table.sort(list)
    return table.concat(list, ",")
end

local STATE_PATH = MOD_DIR .. "ap_state.txt"
local STATUS_PATH = MOD_DIR .. "ap_status.txt"

-- POC: one counter for the whole install. The real mod must keep it per save (Archipelago
-- resends items by index, and loading an older save must re-grant what that save lacks).
-- Open question 4 in the README.
local function loadState()
    local f = io.open(STATE_PATH, "r")
    if not f then return end
    for line in f:lines() do
        local key, value = line:match("^(%w+)\t(.*)$")
        if key == "applied" then state.applied = tonumber(value) or 0 end
        if key == "blank" then state.blank = value == "1" end
        if key == "seed" and value ~= "" then state.seed = value end
        if key == "slots" then
            for slot in value:gmatch("%d+") do state.slots[tonumber(slot)] = true end
        end
    end
    f:close()
end

local function saveState()
    local f = io.open(STATE_PATH, "w")
    if not f then return end
    f:write("applied\t", state.applied, "\n")
    f:write("blank\t", state.blank and "1" or "0", "\n")
    f:write("seed\t", state.seed or "", "\n")
    f:write("slots\t", slotsText(), "\n")
    f:close()
end

local function report(kind, value)
    local key = kind .. "|" .. tostring(value)
    if state.reported[key] then return false end
    state.reported[key] = true
    bridge.write(kind, value)
    return true
end

-- -------------------------------------------------------------------------------------------
-- Items
-- -------------------------------------------------------------------------------------------

local GRANTS = {
    item = function(it) return game.GrantItem(it.id, math.max(it.count, 1)) end,
    vision = function(it) return game.UnlockVision(it.id) end,
    unit = function(it) return game.AddUnit(it.id) end,
    flag = function(it) return game.SetFlag(it.id, it.count ~= 0) end,
    gil = function(it) return game.GrantGil(math.max(it.count, 1)) end,
}

local function grant(it)
    local fn = GRANTS[it.kind]
    if not fn then return "fail", "unknown kind " .. tostring(it.kind) end
    local ok, code, detail = pcall(fn, it)
    if not ok then return "fail", "error: " .. tostring(code) end
    return code, detail
end

-- A new client session (another seed, or another slot) starts everything over: no item of the
-- old session is applied, no old check is kept, and ap_out.txt is emptied so the client never
-- sends an old seed's checks. Then everything the save already has is reported once in game.
local function newSession(key)
    log("new session " .. key .. (state.seed and (" (was " .. state.seed .. ")") or ""))
    state.seed, state.applied, state.queue, state.reported = key, 0, {}, {}
    state.syncPending = true
    state.slots, state.bindPending = {}, false
    save.obj = nil     -- judge the loaded save again for this session
    saveState()
    local f = io.open(bridge.outPath, "w")
    if f then f:close() end
    bridge.write("hello", VERSION, PROTOCOL)
    bridge.write("seed", key)
end

local function readInbox(initial)
    for _, f in ipairs(bridge.readNew()) do
        if f[1] == "seed" and f[2] and f[2] ~= "" then
            if f[2] ~= state.seed then newSession(f[2]) end
        elseif f[1] == "cfg" and f[2] == "blank" then
            local want = f[3] == "1"
            if want ~= state.blank then
                state.blank = want
                saveState()
                if game.InGame() then game.BlankChests(want and sessionSave()) end
                log("chest blanking " .. (want and "on" or "off") .. " (client)")
            end
        elseif f[1] == "sync" then
            if not initial then state.syncPending = true end
        elseif f[1] == "bind" then
            -- Only a request made while the game runs: an old one would link whatever loads first.
            if not initial then state.bindPending = true end
        elseif f[1] == "item" then
            local index, id = tonumber(f[2]), tonumber(f[4])
            if index and id then
                if index >= state.applied then state.queue[index] = { kind = f[3], id = id, count = tonumber(f[5]) or 1,
                    label = (f[6] and f[6] ~= "") and f[6] or (f[3] .. " " .. f[4]) } end
            else
                log("bad item line: " .. table.concat(f, " | "))
            end
        elseif f[1] == "msg" then
            -- Messages from before this game session started are old news.
            if not initial then notify(f[2] or "") end
        end
    end
end

local function applyItems()
    local done, names = 0, {}
    while done < MAX_GRANTS_PER_TICK do
        local it = state.queue[state.applied]
        if not it then break end
        local code, detail = grant(it)
        if code == "retry" then
            state.lastResult = "waiting: " .. tostring(detail)
            break
        end
        log(string.format("item %d %s %d x%d: %s (%s)", state.applied, it.kind, it.id, it.count,
            code, tostring(detail)))
        bridge.write("applied", state.applied, code, detail)
        if code == "ok" then
            names[#names + 1] = it.label
        else
            notify("Could not apply " .. it.label .. ": " .. tostring(detail))
        end
        state.queue[state.applied] = nil
        state.applied = state.applied + 1
        state.lastResult = it.label .. ": " .. code
        done = done + 1
        saveState()
    end
    if #names == 1 then
        notify("Received " .. names[1])
    elseif #names > 1 then
        notify("Received " .. #names .. " items: " .. table.concat(names, ", "))
    end
end

-- -------------------------------------------------------------------------------------------
-- Checks
-- -------------------------------------------------------------------------------------------

-- After the map changes, actors from the map you left can still be alive for a moment, and
-- round 2 showed them being counted under the new map's id. So nothing is judged until the map
-- id has held for this many scans.
local MAP_SETTLE_SCANS = 3

-- This map visit: which map, how many scans it has held, and which chests and shinies were
-- already recorded.
local visit = { mapId = nil, scans = 0, recorded = {} }

-- Everything seen so far, across sessions: our own location list, and the map from each
-- location to the key the save knows it by. One line each in seen.tsv:
--   kind  map  uid  row  item  count  money  visible-condition
-- kind: chest (has a chest table row; row is its "mapId:ID"), xchest (no row), shiny, spot
-- (a shiny-class story or quest point with no reward). map is the current map as the save
-- keys it (CPP_MapManager:GetSameMapId) and uid is m_UniqueId: IsOpenTreasureBox(map, uid)
-- answers for that location from anywhere in the game (round 3).
local SEEN_PATH = MOD_DIR .. "seen.tsv"
local seen = {}       -- "kind:map:uid" -> true
local seenList = {}   -- the parsed lines, for ffrap_sync

local function split(line)
    local cells = {}
    for cell in (line .. "\t"):gmatch("(.-)\t") do cells[#cells + 1] = cell end
    return cells
end

local function addSeen(cells)
    local key = cells[1] .. ":" .. cells[2] .. ":" .. cells[3]
    if seen[key] then return false end
    seen[key] = true
    seenList[#seenList + 1] = { kind = cells[1], map = tonumber(cells[2]), uid = tonumber(cells[3]), row = cells[4] or "" }
    return true
end

local function loadSeen()
    local f = io.open(SEEN_PATH, "r")
    if not f then return end
    for line in f:lines() do
        local cells = split((line:gsub("\r$", "")))
        -- 0.3.0 wrote rowless chests as "u<uid>", with the row map in the row column.
        if cells[1] == "xchest" and cells[3] and cells[3]:sub(1, 1) == "u" then
            cells[3], cells[4] = cells[3]:sub(2), ""
        end
        if #cells >= 3 and tonumber(cells[2]) and tonumber(cells[3]) then addSeen(cells) end
    end
    f:close()
end

local function recordSeen(kind, mapId, uid, row, itemId, itemNum, money, visible)
    local cells = { kind, mapId, uid, row or "", itemId or "", itemNum or "", money or "", visible or "" }
    for i, v in ipairs(cells) do cells[i] = (tostring(v):gsub("[\t\r\n]", " ")) end
    if not addSeen(cells) then return end
    local f = io.open(SEEN_PATH, "a")
    if not f then return end
    f:write(table.concat(cells, "\t"), "\n")
    f:close()
end

local function newVisit(mapId)
    visit = { mapId = mapId, scans = 0, recorded = {} }
end

local function opened(key)
    if not sessionSave() then return end
    if report("check", key) then log("check " .. key) end
end

-- The location key of a chest. A chest with a table row is keyed by the row ("chest:3020:1"),
-- which is stable and matches data/chests.tsv. Round 3 showed rows and maps do not line up
-- (rows 3020:* sit in map 2002), so the row key never depends on the current map.
-- A rowless chest with a reward is keyed by map and m_UniqueId ("chest:2002:u54"). Round 3's
-- rowless chests had no item and no money and were already open: story chests, it seems.
-- Those have no key: they are recorded but never reported.
local function chestKey(mapId, c)
    if c.rowMap and c.rowId and c.rowId >= 0 then return "chest:" .. c.rowMap .. ":" .. c.rowId end
    local hasReward = (c.itemId and c.itemId >= 0) or (c.money and c.money >= 0)
    if c.uniqueId and hasReward then return "chest:" .. mapId .. ":u" .. c.uniqueId end
    return nil
end

-- Chests are reported when the actor says open or the save does. The save's key is the current
-- map and m_UniqueId (round 3: true for every opened chest, false for every closed one).
local function scanChests(mapId)
    for _, c in ipairs(game.LiveChests()) do
        if c.uniqueId then
            local key = chestKey(mapId, c)
            if not visit.recorded["c" .. c.uniqueId] then
                visit.recorded["c" .. c.uniqueId] = true
                local hasRow = c.rowId and c.rowId >= 0
                recordSeen(hasRow and "chest" or "xchest", mapId, c.uniqueId,
                    hasRow and (c.rowMap .. ":" .. c.rowId) or "", c.itemId, c.itemNum, c.money, "")
            end
            if key and (c.open or game.IsChestOpenInSave(mapId, c.uniqueId)) then opened(key) end
        end
    end
end

-- Shinies are reported when the actor's m_IsOpen is set or the save says looted; round 2 showed
-- the save answering true the moment one is picked up. Spots without an item or money are
-- story or quest points, not pick-ups: they are recorded as "spot" but never reported.
local function scanShinies(mapId)
    for _, s in ipairs(game.LiveFieldItems()) do
        if s.uid then
            local hasReward = (s.itemId and s.itemId >= 0) or (s.money and s.money >= 0)
            if not visit.recorded["s" .. s.uid] then
                visit.recorded["s" .. s.uid] = true
                recordSeen(hasReward and "shiny" or "spot", mapId, s.uid, s.class, s.itemId, s.itemNum, s.money, s.visible)
            end
            if hasReward and (s.open or game.IsChestOpenInSave(mapId, s.uid)) then
                opened("shiny:" .. mapId .. ":" .. s.uid)
            end
        end
    end
end

-- Re-sync from the save: every location in seen.tsv the save says is looted gets reported,
-- wherever the player is. A client would run this after a reconnect, or after ap_out.txt was
-- lost. Returns how many were new.
local function syncFromSave()
    local new = 0
    for _, e in ipairs(seenList) do
        local key
        if e.kind == "chest" and e.row ~= "" then
            key = "chest:" .. e.row
        elseif e.kind == "shiny" then
            key = "shiny:" .. e.map .. ":" .. e.uid
        end
        if key and game.IsChestOpenInSave(e.map, e.uid) and report("check", key) then
            log("sync: check " .. key)
            new = new + 1
        end
    end
    return new
end

local function scanLoot()
    local mapId = game.CurrentMap()
    if not mapId then return end
    if mapId ~= visit.mapId then
        log("map " .. tostring(visit.mapId) .. " -> " .. mapId .. " (save's Map.mapId " .. tostring(game.MapId()) .. ")")
        newVisit(mapId)
        if state.blank and sessionSave() then
            log("chest blanking: " .. game.BlankChests(true) .. " rows set to 1 gil")
        end
    end
    visit.scans = visit.scans + 1
    if visit.scans <= MAP_SETTLE_SCANS then return end
    scanChests(mapId)
    scanShinies(mapId)
end

local function watchStory()
    local n = game.StoryCounter()
    if n and n ~= state.lastStory then
        if state.lastStory then log("story " .. state.lastStory .. " -> " .. n) end
        state.lastStory = n
        report("story", n)
    end
end

-- -------------------------------------------------------------------------------------------
-- The session's save
-- -------------------------------------------------------------------------------------------

-- Turns chest blanking on or off when the loaded save stops or starts being the session's.
local function setOk(ok)
    local was = save.ok
    save.ok = ok
    if state.blank and was ~= ok then
        log("chest blanking " .. (ok and "on" or "off") .. " for this save: " .. game.BlankChests(ok) .. " rows changed")
    end
end

-- Decides whether a save that was just loaded (or a new game) is the session's.
local function judgeSave()
    if not state.seed then setOk(true); return end
    if save.slot ~= nil and state.slots[save.slot] then
        setOk(true)
        log("save slot " .. save.slot .. " is the session's save")
    elseif save.slot == nil and next(state.slots) == nil then
        -- A new game that was never saved, and the session has no save yet: link it. It joins
        -- a slot the first time it is saved.
        setOk(true)
        notify("Archipelago: this new game is linked to the seed")
    else
        setOk(false)
        notify("Archipelago is paused: this save is not linked to the seed. Load the linked save, " ..
            "start a new game, or use /bind in the client to link this one.")
    end
end

-- Links the loaded save to the session, in place of any earlier one.
local function bindLoaded()
    if not state.seed then
        notify("No Archipelago session: connect the client first")
        return
    end
    if not save.obj then
        notify("Load a save first, then link it")
        return
    end
    state.slots = {}
    if save.slot ~= nil then state.slots[save.slot] = true end
    saveState()
    setOk(true)
    state.syncPending = true   -- whatever this save has already looted counts
    notify("Archipelago: this save is linked to the seed" .. (save.slot and (" (slot " .. save.slot .. ")") or ""))
end

-- Follows the loaded save: a new save object is a load or a new game, and a new timestamp on
-- the same object means the game just saved. A save by the session's game adds its slot to the
-- session; a save by any other game takes that slot away, because it now holds another game.
local function followSave()
    local obj, ticks = game.SaveObjectName(), game.SavedTicks()
    if not obj then return end
    if obj ~= save.obj then
        save.obj, save.ticks, save.pending = obj, ticks, nil
        save.slot = game.SlotForTicks(ticks)
        log("save loaded: slot " .. tostring(save.slot) .. ", session slots [" .. slotsText() .. "]")
        judgeSave()
    elseif ticks ~= save.ticks then
        save.ticks, save.pending = ticks, ticks
    end
    if save.pending then
        local slot = game.SlotForTicks(save.pending)   -- the summary can catch up a moment later
        if slot ~= nil then
            save.pending, save.slot = nil, slot
            if state.seed and save.ok and not state.slots[slot] then
                state.slots[slot] = true
                saveState()
                log("saved to slot " .. slot .. ": session slots [" .. slotsText() .. "]")
            elseif state.seed and not save.ok and state.slots[slot] then
                state.slots[slot] = nil
                saveState()
                notify("Archipelago: slot " .. slot .. " now holds another game and is no longer linked")
            end
        end
    end
end

-- -------------------------------------------------------------------------------------------
-- Status
-- -------------------------------------------------------------------------------------------

local function queued()
    local n = 0
    for _ in pairs(state.queue) do n = n + 1 end
    return n
end

local function statusLines()
    local party = game.PartyIds()
    return {
        "FFRArchipelago " .. VERSION .. "  " .. os.date("%Y-%m-%d %H:%M:%S"),
        "in game: " .. tostring(game.InGame()) .. " (" .. state.inGameTicks .. " ticks)",
        "map: " .. tostring(game.CurrentMap()) .. " (save's Map.mapId " .. tostring(game.MapId()) .. ")   story: " .. tostring(game.StoryCounter()),
        "party: " .. (party and table.concat(party, ", ") or "?"),
        "items applied: " .. state.applied .. "   queued: " .. queued(),
        "chest blanking: " .. (state.blank and "on" or "off") .. "   session: " .. tostring(state.seed),
        "save: slot " .. tostring(save.slot) .. ", session slots [" .. slotsText() .. "], " ..
            (sessionSave() and "linked" or "not linked (paused)"),
        "last: " .. state.lastResult,
    }
end

local function writeStatus()
    local f = io.open(STATUS_PATH, "w")
    if not f then return end
    f:write(table.concat(statusLines(), "\n"), "\n")
    f:close()
end

-- -------------------------------------------------------------------------------------------
-- Tick
-- -------------------------------------------------------------------------------------------

local function tick()
    state.ticks = state.ticks + 1
    readInbox(false)
    if not game.InGame() then
        if state.inGameTicks > 0 then log("left the game (title screen or loading)") end
        state.inGameTicks = 0
        state.lastStory = nil
        save.obj = nil
    else
        state.inGameTicks = state.inGameTicks + 1
        if state.inGameTicks == 1 then log("save loaded, map " .. tostring(game.CurrentMap())) end
        if state.inGameTicks > SETTLE_TICKS then
            followSave()
            if state.bindPending then
                state.bindPending = false
                bindLoaded()
            end
            -- Chests and shinies are still recorded in seen.tsv for any save; scanLoot reports
            -- them only for the session's save (see opened).
            if state.ticks % CHEST_EVERY == 0 then scanLoot() end
            if sessionSave() then
                applyItems()
                watchStory()
                if state.syncPending then
                    state.syncPending = false
                    log("sync from save: " .. syncFromSave() .. " new checks")
                end
                -- The tables can be rebuilt while the game runs, so blanking is applied again
                -- now and then; rows already blank are skipped.
                if state.blank and state.ticks % STATUS_EVERY == 0 then game.BlankChests(true) end
            else
                state.lastStory = nil   -- report the story again once the session's save is back
            end
        end
    end
    if state.ticks % STATUS_EVERY == 0 then writeStatus() end
end

-- -------------------------------------------------------------------------------------------
-- Console commands
-- -------------------------------------------------------------------------------------------

local function command(name, fn)
    local ok, err = pcall(RegisterConsoleCommandGlobalHandler, name, function(_, params)
        local okRun, errRun = pcall(fn, params or {})
        if not okRun then log(name .. " failed: " .. tostring(errRun)) end
        return true
    end)
    if not ok then log("could not register " .. name .. ": " .. tostring(err)) end
end

command("ffrap_status", function()
    for _, line in ipairs(statusLines()) do log(line) end
    notify("AP: map " .. tostring(game.CurrentMap()) .. ", story " .. tostring(game.StoryCounter())
        .. ", " .. state.applied .. " items applied")
end)

command("ffrap_grant", function(p)
    local kind, id, n = p[1], tonumber(p[2]), tonumber(p[3]) or 1
    if not (kind and id) then
        notify("usage: ffrap_grant <item|gil|vision|unit|flag> <id> [n]")
        return
    end
    local code, detail = grant({ kind = kind, id = id, count = n })
    notify(kind .. " " .. id .. ": " .. tostring(code) .. " (" .. tostring(detail) .. ")")
end)

command("ffrap_dump", function(p)
    local path = MOD_DIR .. "ffrap_dump.txt"
    local f = io.open(path, "w")
    if not f then return end
    local function out(line) f:write(line, "\n") end
    game.DumpChests(out, tonumber(p[1]) or 5)
    out("")
    game.DumpFieldItems(out)
    f:close()
    notify("Chest and shiny dump written to ffrap_dump.txt")
end)

-- Every field of the loaded save to snap_<name>.tsv, to compare two points in the game with
-- tools/snapdiff.py (the prologue investigation, IDEAS.md idea 2).
command("ffrap_snapshot", function(p)
    local name = tostring(p[1] or os.date("%H%M%S")):gsub("[^%w_%-]", "")
    if name == "" then name = os.date("%H%M%S") end
    local path = MOD_DIR .. "snap_" .. name .. ".tsv"
    local f = io.open(path, "w")
    if not f then
        notify("Could not write snap_" .. name .. ".tsv")
        return
    end
    local lines = 0
    local ok = game.Snapshot(function(key, value)
        f:write(key, "\t", (tostring(value):gsub("[\t\r\n]", " ")), "\n")
        lines = lines + 1
    end)
    f:close()
    if ok then
        notify("Snapshot snap_" .. name .. ".tsv: " .. lines .. " lines")
    else
        notify("No save loaded: nothing to snapshot")
    end
end)

-- Classes worth knowing for the prologue skip (IDEAS.md, idea 2): the save-data libraries, the
-- debug event shortcuts and the new-game task.
local FUNCTION_CLASSES = {
    "CPP_BFL_SaveData", "CPP_BFL_SaveDataProgress", "CPP_BFL_SaveDataParty", "CPP_BFL_SaveDataUnit",
    "CPP_BFL_SaveDataInventory", "CPP_BFL_SaveDataMap", "CPP_BFL_SaveData_PerMap",
    "CPP_BFL_SaveDataPlayer", "CPP_BFL_DBG_FlagSaveData", "CPP_BFL_Scenario", "CPP_ScenarioSubsystem",
    "CPP_DM_EventShortcutData", "CPP_DM_SaveDataManager", "CPP_DM_BFL_SaveData", "CPP_Task_NewGame",
    "CPP_MuchaSaveDataManager", "CPP_MuchaGameSaveData",
}

command("ffrap_functions", function(p)
    local classes = (p and p[1]) and p or FUNCTION_CLASSES
    local f = io.open(MOD_DIR .. "functions.txt", "w")
    if not f then
        notify("Could not write functions.txt")
        return
    end
    local found, total = 0, 0
    for _, className in ipairs(classes) do
        local n = game.ListFunctions(tostring(className), function(line) f:write(line, "\n") end)
        if n then found, total = found + 1, total + n else f:write("-- not found: ", tostring(className), "\n") end
    end
    f:close()
    notify("functions.txt: " .. total .. " functions from " .. found .. " of " .. #classes .. " classes")
end)

command("ffrap_export", function()
    local ok, detail = game.ExportChests(MOD_DIR .. "chests.tsv")
    notify(ok and ("Chest table exported to chests.tsv: " .. detail) or ("Export failed: " .. detail))
end)

command("ffrap_blank", function(p)
    local want = p[1] == "on" or (p[1] == nil and not state.blank)
    if p[1] == "off" then want = false end
    state.blank = want
    saveState()
    local n = game.BlankChests(want)
    notify("Chest blanking " .. (want and "on" or "off") .. ": " .. n .. " rows changed")
end)

-- Reports every location in seen.tsv that the save says is looted (see syncFromSave).
command("ffrap_sync", function()
    if not sessionSave() then
        notify("Not synced: this save is not linked to the seed (ffrap_bind links it)")
        return
    end
    local new = syncFromSave()
    notify("Sync from save: " .. new .. " new checks from " .. #seenList .. " known locations")
end)

command("ffrap_bind", function()
    if not game.InGame() then
        notify("Load a save first, then link it")
        return
    end
    followSave()
    bindLoaded()
end)

command("ffrap_reset", function()
    state.applied = 0
    saveState()
    bridge.offset = 0
    notify("Applied-item count reset; every item in ap_in.txt will be granted again")
end)

-- -------------------------------------------------------------------------------------------
-- Start
-- -------------------------------------------------------------------------------------------

bridge.init(MOD_DIR)
loadState()
loadSeen()
for _, f in ipairs(bridge.readOut()) do
    if f[1] == "check" or f[1] == "story" then state.reported[f[1] .. "|" .. tostring(f[2])] = true end
end
bridge.write("hello", VERSION, PROTOCOL)
if state.seed then bridge.write("seed", state.seed) end
readInbox(true)
log("version " .. VERSION .. " loaded from " .. MOD_DIR .. ", " .. state.applied .. " items already applied")

LoopAsync(TICK_MS, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(tick)
        if not ok then log("tick error: " .. tostring(err)) end
    end)
    return false
end)
