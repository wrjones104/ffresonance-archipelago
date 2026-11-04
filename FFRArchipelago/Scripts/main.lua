-- FFRArchipelago: proof of concept for an Archipelago client inside Final Fantasy Resonance.
--
-- What it does:
--   * Reads items from ap_in.txt and grants them in order: bag items, visions, party members
--     and story flags. Each item is applied once, tracked by its Archipelago index.
--   * Reports opened chests (check chest:<mapId>:<uid>) and story counter changes to ap_out.txt.
--   * Writes ap_status.txt every few seconds, so you can see what it thinks is going on.
--
-- What it does NOT do yet: talk to an Archipelago server (a Python client will do that), stop
-- chests giving their vanilla item, or stop story events giving theirs. See README.md.
--
-- Console commands (open the UE4SS console, ConsoleEnablerMod):
--   ffrap_status                 what the mod sees right now
--   ffrap_grant <kind> <id> [n]  grant directly, without the bridge: item, vision, unit, flag
--   ffrap_dump [rows]            chest discovery dump to ffrap_dump.txt
--   ffrap_reset                  forget the applied-item count (re-grants everything!)

local VERSION = "0.1.0"

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
    end
    f:close()
end

local function saveState()
    local f = io.open(STATE_PATH, "w")
    if not f then return end
    f:write("applied\t", state.applied, "\n")
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

local function scanChests()
    local mapId = game.MapId()
    if not mapId then return end
    local chests = game.LiveChests()
    local firstVisit = not seenMaps[mapId]
    seenMaps[mapId] = true
    for _, c in ipairs(chests) do
        if c.uid then
            if firstVisit then
                -- Discovery: does the actor's map id match what the save keys chests by?
                log(string.format("map %d chest %d: actor open %s, save open %s", mapId, c.uid,
                    tostring(c.open), tostring(game.IsChestOpenInSave(mapId, c.uid))))
            end
            if c.open and report("check", "chest:" .. mapId .. ":" .. c.uid) then
                log("check chest:" .. mapId .. ":" .. c.uid)
            end
        end
    end
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
        "map: " .. tostring(game.MapId()) .. "   story: " .. tostring(game.StoryCounter()),
        "party: " .. (party and table.concat(party, ", ") or "?"),
        "items applied: " .. state.applied .. "   queued: " .. queued(),
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
        if state.inGameTicks == 1 then log("save loaded, map " .. tostring(game.MapId())) end
        if state.inGameTicks > SETTLE_TICKS then
            applyItems()
            watchStory()
            if state.ticks % CHEST_EVERY == 0 then scanChests() end
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
    notify("AP: map " .. tostring(game.MapId()) .. ", story " .. tostring(game.StoryCounter())
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
    game.DumpChests(function(line) f:write(line, "\n") end, tonumber(p[1]) or 5)
    f:close()
    notify("Chest dump written to ffrap_dump.txt")
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
