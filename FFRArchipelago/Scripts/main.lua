-- FFRArchipelago: proof of concept for an Archipelago client inside Final Fantasy Resonance.
--
-- What it does:
--   * Reads items from ap_in.txt and grants them in order: bag items, visions, party members
--     and story flags. Each item is applied once, tracked by its Archipelago index.
--   * Reports opened chests (check chest:<mapId>:<uid>), picked-up shinies (check
--     shiny:<mapId>:<uid>) and story counter changes to ap_out.txt.
--   * Writes ap_status.txt every few seconds, so you can see what it thinks is going on.
--
-- What it does NOT do yet: talk to an Archipelago server (a Python client will do that), stop
-- chests giving their vanilla item, or stop story events giving theirs. See README.md.
--
-- Console commands (open the UE4SS console, ConsoleEnablerMod):
--   ffrap_status                 what the mod sees right now
--   ffrap_grant <kind> <id> [n]  grant directly, without the bridge: item, vision, unit, flag
--   ffrap_dump [rows]            chest and shiny discovery dump to ffrap_dump.txt
--   ffrap_export                 every chest table row to chests.tsv
--   ffrap_blank [on|off]         experiment: every non-trap chest gives 1 gil instead
--   ffrap_savecheck              ask the save about every check reported so far
--   ffrap_reset                  forget the applied-item count (re-grants everything!)

local VERSION = "0.3.0"

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
    blank = false,     -- chest blanking experiment (ffrap_blank)
}

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
    end
    f:close()
end

local function saveState()
    local f = io.open(STATE_PATH, "w")
    if not f then return end
    f:write("applied\t", state.applied, "\n")
    f:write("blank\t", state.blank and "1" or "0", "\n")
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
}

local function grant(it)
    local fn = GRANTS[it.kind]
    if not fn then return "fail", "unknown kind " .. tostring(it.kind) end
    local ok, code, detail = pcall(fn, it)
    if not ok then return "fail", "error: " .. tostring(code) end
    return code, detail
end

local function readInbox(initial)
    for _, f in ipairs(bridge.readNew()) do
        if f[1] == "item" then
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

local seenMaps = {}   -- map id -> true once its chests were logged against the save

-- After the map changes, actors from the map you left can still be alive for a moment, and
-- round 2 showed them being counted under the new map's id. So nothing is judged until the map
-- id has held for this many scans.
local MAP_SETTLE_SCANS = 3

-- This map visit: which map, how many scans it has held, what was opened during it (for the
-- save-timing log), and which shinies were already logged.
local visit = { mapId = nil, scans = 0, opened = {}, shinies = {} }

-- Shinies and odd chests seen so far, across sessions: the start of our own location list.
-- One line each in seen.tsv: kind, map, id, class, item, count, money, visible condition.
local SEEN_PATH = MOD_DIR .. "seen.tsv"
local seen = {}

local function loadSeen()
    local f = io.open(SEEN_PATH, "r")
    if not f then return end
    for line in f:lines() do
        local kind, map, id = line:match("^(%w+)\t(%d+)\t(%-?%w+)\t")
        if kind then seen[kind .. ":" .. map .. ":" .. id] = true end
    end
    f:close()
end

local function recordSeen(kind, mapId, id, class, itemId, itemNum, money, visible)
    local key = kind .. ":" .. mapId .. ":" .. id
    if seen[key] then return end
    seen[key] = true
    local f = io.open(SEEN_PATH, "a")
    if not f then return end
    local cells = { kind, mapId, id, class or "", itemId or "", itemNum or "", money or "", visible or "" }
    for i, v in ipairs(cells) do cells[i] = tostring(v):gsub("[\t\r\n]", " ") end
    f:write(table.concat(cells, "\t"), "\n")
    f:close()
end

-- Save-timing discovery: when the map changes, ask the save again about everything opened during
-- the visit that just ended, under every candidate key.
local function checkSaveAfterVisit(v)
    for _, o in ipairs(v.opened) do
        if o.kind == "chest" then
            log(string.format("save check after leaving map %d: %s %s", v.mapId, o.key, game.ChestSaveKeys(v.mapId, o.c)))
        else
            log(string.format("save check after leaving map %d: %s save open %s", v.mapId, o.key,
                tostring(game.IsChestOpenInSave(v.mapId, o.uid))))
        end
    end
end

local function newVisit(mapId)
    if visit.mapId and #visit.opened > 0 then checkSaveAfterVisit(visit) end
    visit = { mapId = mapId, scans = 0, opened = {}, shinies = {} }
end

local function opened(key, entry)
    if report("check", key) then
        log("check " .. key)
        entry.key = key
        visit.opened[#visit.opened + 1] = entry
    end
end

-- A chest's location key comes from the chest table row it carries, so it does not depend on
-- which map the game reports. A chest with no row (ID -1; round 2 found four) is keyed by the
-- current map and its m_UniqueId, and recorded in seen.tsv to find out what it is.
local function scanChests(mapId)
    local firstVisit = not seenMaps[mapId]
    seenMaps[mapId] = true
    for _, c in ipairs(game.LiveChests()) do
        local key
        if c.rowMap and c.rowId and c.rowId >= 0 then
            key = "chest:" .. c.rowMap .. ":" .. c.rowId
        elseif c.uniqueId then
            key = "chest:" .. mapId .. ":u" .. c.uniqueId
            recordSeen("xchest", mapId, "u" .. c.uniqueId, "rowmap " .. tostring(c.rowMap), c.itemId, c.itemNum, c.money, "")
        end
        if key then
            if firstVisit then
                log(string.format("map %d %s: open %s; save: %s", mapId, key, tostring(c.open), game.ChestSaveKeys(mapId, c)))
            end
            if c.open then opened(key, { kind = "chest", c = c }) end
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
            local saveOpen = game.IsChestOpenInSave(mapId, s.uid)
            if not visit.shinies[s.uid] then
                visit.shinies[s.uid] = true
                recordSeen(hasReward and "shiny" or "spot", mapId, s.uid, s.class, s.itemId, s.itemNum, s.money, s.visible)
            end
            if hasReward and (s.open or saveOpen) then
                opened("shiny:" .. mapId .. ":" .. s.uid, { kind = "shiny", uid = s.uid })
            end
        end
    end
end

local function scanLoot()
    local mapId = game.CurrentMap()
    if not mapId then return end
    if mapId ~= visit.mapId then
        log("map " .. tostring(visit.mapId) .. " -> " .. mapId .. " (save's Map.mapId " .. tostring(game.MapId()) .. ")")
        newVisit(mapId)
        if state.blank then
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
        "chest blanking: " .. (state.blank and "on" or "off"),
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
    else
        state.inGameTicks = state.inGameTicks + 1
        if state.inGameTicks == 1 then log("save loaded, map " .. tostring(game.CurrentMap())) end
        if state.inGameTicks > SETTLE_TICKS then
            applyItems()
            watchStory()
            if state.ticks % CHEST_EVERY == 0 then scanLoot() end
            -- The tables can be rebuilt while the game runs, so blanking is applied again now
            -- and then; rows already blank are skipped.
            if state.blank and state.ticks % STATUS_EVERY == 0 then game.BlankChests(true) end
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
        notify("usage: ffrap_grant <item|vision|unit|flag> <id> [n]")
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

-- Asks the save about every chest and shiny reported so far: run it after saving, or after
-- leaving and re-entering a map, to see when the save catches up.
command("ffrap_savecheck", function()
    local yes, no = 0, 0
    for key in pairs(state.reported) do
        local kind, mapId, uid = key:match("^check|(%a+):(%d+):(%d+)$")
        if kind then
            local open = game.IsChestOpenInSave(tonumber(mapId), tonumber(uid))
            log(string.format("savecheck %s:%s:%s save open %s", kind, mapId, uid, tostring(open)))
            if open then yes = yes + 1 else no = no + 1 end
        end
    end
    notify("Save check: " .. yes .. " reported checks are in the save, " .. no .. " are not (see UE4SS.log)")
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
readInbox(true)
bridge.write("hello", VERSION)
log("version " .. VERSION .. " loaded from " .. MOD_DIR .. ", " .. state.applied .. " items already applied")

LoopAsync(TICK_MS, function()
    ExecuteInGameThread(function()
        local ok, err = pcall(tick)
        if not ok then log("tick error: " .. tostring(err)) end
    end)
    return false
end)
