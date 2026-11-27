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
--
-- Console commands (open the UE4SS console, ConsoleEnablerMod):
--   ffrap_status                 what the mod sees right now
--   ffrap_grant <kind> <id> [n]  grant directly, without the bridge: item, gil, vision, unit, flag
--   ffrap_dump [rows]            chest and shiny discovery dump to ffrap_dump.txt
--   ffrap_export                 every chest table row to chests.tsv
--   ffrap_snapshot [name]        every field of the loaded save to snap_<name>.tsv (tools/snapdiff.py)
--   ffrap_functions [class ...]  the functions of game classes to functions.txt (default: save-data classes)
--   ffrap_skip [slot] [force]    skip the prologue on a new game; with a slot, save there and reload
--   ffrap_input [fix]            inspect the player controller's input state; fix tries the engine's resets
--   ffrap_openstart [on|off|dock|air|event|at x y z|now [slot]]  configure or run the open world start (story 8000)
--   ffrap_newstart [on|off]      on (the default): the Archipelago new game starts with no prologue (round 109)
--   ffrap_chats [done]           the loaded save's Active Time Chats; done marks them all played
--   ffrap_lock [on|off|open <continent|all>|close <continent|all>]  toggle or set continent locks
--   ffrap_visions                the first vision's synchro keys, to the log
--   ffrap_inspect <class|path> [label]  one object's fields and functions to inspect_<name>[_label].tsv
--   ffrap_title [list|add]       the Archipelago entry on the title menu (added at start-up)
--   ffrap_notice [text]          show text with the game's quest-notice banner
--   ffrap_apmenu off|on|state|close|tree  the Archipelago page in the main menu (on by default)
--   ffrap_apmenu options|text|tabs [only|all]|mode ap|game  rounds 85-86 probe: the Options screen as the page
--   ffrap_apmenu split on|off  the page's two tabs, Settings and Seed (on), or one (off)
--   ffrap_apmenu seedrows command|heading  the Seed tab's lines as rows the cursor can take (the default) or headings
--   ffrap_logo                   place the Archipelago logo on the mod's title line manually
--   ffrap_layout <text>          log the panels holding some on-screen text
--   ffrap_feed [on|off|test [plain]|check]  the item feed at the bottom right of the field HUD
--   ffrap_find <text>            game classes, functions and fields matching the text, to find_<text>.txt
--   ffrap_blank [on|off]         chests that are Archipelago locations give nothing instead
--   ffrap_sync                   report every known location the save says is looted
--   ffrap_bind                   link the loaded save to the client's session (also /bind in the client)
--   ffrap_reset                  set the loaded save's applied-item count to 0 (re-grants everything to it!)
--   ffrap_gate <subcommand>      experimental blockers and world-map walking crossings
--   ffrap_scale <level|low high|party n|off> [at %] [hp %] [attack %] [magic %] [power %] [boss] [follow]
--                                rewrite every enemy's level and stats
--   ffrap_scale [show <id|name>] show the active rescale or one enemy's rows in every unit table
--   ffrap_noland <list|here|show|hide|lock|unlock|refresh|spawn|move|channel|shadow|cond|off>
--                                inspect or modify the airship's no-landing boxes
--   ffrap_story <value>          set the loaded save's story counter (save and reload to apply)
--   ffrap_airship [condition|off|state|home]  inspect or rewrite the airship's spawn condition, log save fields, or park at start
--
-- Each client session belongs to its saves. A new game started from the Archipelago entry on
-- the title menu is linked to it at once and skips the prologue by itself (plain New Game stays
-- vanilla); an existing save is linked with ffrap_bind or the client's /bind. The link
-- follows the save slots the linked game is saved to. While any other save is loaded, the mod
-- grants nothing, reports nothing and leaves the chests vanilla.

local VERSION = "0.62.2"
local PROTOCOL = 2        -- the bridge protocol; the apworld's MOD_PROTOCOL

local MOD_DIR = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)Scripts/[^/]+$"))
    or "ue4ss/Mods/FFRArchipelago/"

local game = require("game")
local bridge = require("bridge")
local LEVEL_SHINIES = require("field_items")

local TICK_MS = 500
local LOCKS_EVERY = 2         -- ticks between checks that the continent locks match the save
local FAST_MS = 100           -- the chest pop-up check (fastTick)
local SETTLE_TICKS = 4        -- wait this long after a save loads before granting
local MAX_GRANTS_PER_TICK = 5
local NEW_GAME_STORY = 1000   -- the story counter of a new game, until the first scene ends
local TITLE_EVERY = 6         -- ticks between checks that the title entry is still there
local AUTO_SKIP_WAIT = 4      -- ticks to wait after the first autosave before the automatic skip
local TITLE_LINE = "FFRArchipelago " .. VERSION   -- shown above the game's version on the title
local LOGO_PATH = MOD_DIR .. "Assets/archipelago_logo.png"
local CHEST_EVERY = 2         -- ticks between chest scans
local PRIME_EVERY = 4          -- ticks between searches for the dialog box, until it is found
local STATUS_EVERY = 10       -- ticks between status file writes

local function log(msg)
    print("[FFRAP] " .. tostring(msg) .. "\n")
end

-- FFRRandomizer re-writes chest, shop, and enemy tables every 3 seconds, undoing our patches.
-- UE4SS enables any mod with enabled.txt or a "name : 1" entry in mods.txt.
local function randomizerOn()
    local modsDir = MOD_DIR:match("^(.*/)[^/]+/$")
    if not modsDir then return false end
    local f = io.open(modsDir .. "FFRRandomizer/enabled.txt")
    if f then f:close() return true end
    f = io.open(modsDir .. "mods.txt")
    if not f then return false end
    local text = "\n" .. f:read("a")
    f:close()
    return text:find("\n%s*FFRRandomizer%s*:%s*1") ~= nil
end
local randomizerWarning = randomizerOn() and ("FFR Randomizer is on: it undoes Archipelago's chests and enemy " ..
    "levels. Turn it off: delete Mods/FFRRandomizer/enabled.txt") or nil

-- On-screen messages go to the item feed on the field HUD when enabled and visible. Otherwise
-- they queue briefly for the HUD (loading or map transitions), and off the field fall back to
-- ModSettings' Toast.
local FEED_QUEUE_MAX = 20
local FEED_WAIT_MAX = 10     -- seconds messages wait for the feed before falling back to Toast
local feedOn = true          -- ffrap_feed on|off; kept in ap_state.txt
local openStart = false      -- ffrap_openstart on|off: the skip goes to the open world; kept in ap_state.txt
local openArrival = nil      -- ffrap_openstart dock|air|event, kept once the user picks one
local continentLocks = nil   -- ffrap_lock on|off, kept once the user picks one; the seed's until then
-- What the seed says about the start (the client's cfg lines). Not saved: ap_in.txt is read again
-- at every start, and the seed that wrote it is the only thing that decides these.
-- `heard`: a seed line came in this run (ap_in.txt holds the session the client last wrote).
-- Without it the seed's settings are unknown, and state.seed may be an older seed's.
local seedCfg = { openworld = false, party = nil, shinies = false, crystals = false, shards = false, bosses = false,
                  heard = false }
local function openStartOn() return openStart or seedCfg.openworld end
-- A seed with the airship as an item (`cfg airship 0`) starts on foot on its starting continent
-- (`cfg continent`); otherwise the player starts in the airship by the Crystal Tower.
local function seedArrival()
    if seedCfg.airship == false then return game.FOOT_STARTS[seedCfg.continent or ""] or game.OPEN_START end
    return game.OPEN_START
end
local locksFailed = nil      -- the last ContinentSync failure logged, so each one is logged once
local shopSave = nil         -- the save the vision shop guard last ran on
local feedQueue = {}
local feedQueueSince = nil   -- when the oldest waiting message came
local feedShown = false      -- the feed has shown a line in this run
local feedClock = 0          -- seconds, from the tick count

-- `span` ({ text, flags }): the item's name in `msg`, which the feed can colour (round 89).
local function show(msg, span)
    if feedOn and game.InGame() then
        if #feedQueue == 0 and game.FeedLine(msg, feedClock, { span = span }) then
            feedShown = true
            return
        end
        if #feedQueue == 0 then feedQueueSince = feedClock end
        if #feedQueue < FEED_QUEUE_MAX then feedQueue[#feedQueue + 1] = { text = msg, span = span } end
        return
    end
    game.Toast(msg)
end

local function notify(msg, span)
    log(msg)
    show(msg, span)
end

-- Shows what waited for the HUD. A long wait (a login with many items) shows the last few and
-- how many more there were.
local function flushFeed()
    if #feedQueue == 0 then return end
    -- Fall back to Toast only if the feed has never succeeded this run (HUD missing). Once the feed
    -- has worked, keep queued items waiting through pop-ups and menus until the HUD returns.
    if not feedShown and feedQueueSince and feedClock - feedQueueSince > FEED_WAIT_MAX then
        log("feed: no HUD on screen for " .. FEED_WAIT_MAX .. " s; " .. #feedQueue .. " message(s) go to the Toast")
        local texts = {}
        for i, line in ipairs(feedQueue) do texts[i] = line.text end
        game.Toast(table.concat(texts, " / "))
        feedQueue, feedQueueSince = {}, nil
        return
    end
    local lines = feedQueue
    if #lines > game.FEED_MAX then
        local more = #lines - (game.FEED_MAX - 1)
        local tail = {}
        for i = #lines - game.FEED_MAX + 2, #lines do tail[#tail + 1] = lines[i] end
        lines = tail
        table.insert(lines, 1, { text = "and " .. more .. " more" })
    end
    for i, line in ipairs(lines) do
        if game.FeedLine(line.text, feedClock, { span = line.span }) then
            feedShown = true
        else
            -- The HUD went away again: keep what is left for next time.
            local rest = {}
            for j = i, #lines do rest[#rest + 1] = lines[j] end
            feedQueue = rest
            return
        end
    end
    feedQueue, feedQueueSince = {}, nil
end

-- -------------------------------------------------------------------------------------------
-- State
-- -------------------------------------------------------------------------------------------

local state = {
    applied = 0,       -- items 0 .. applied-1 are in the loaded session save
    items = {},        -- index -> { kind, id, count, label }: every item of the session, kept so
                       -- that loading an older save can grant again what it lacks
    reported = {},     -- "check|chest:2031:7" -> true: already written to ap_out.txt
    lastStory = nil,
    inGameTicks = 0,
    ticks = 0,
    lastResult = "",
    blank = false,     -- chest blanking (ffrap_blank, or the client's "cfg blank 1")
    seed = nil,        -- the client session ("<seed name>:<slot>") this state belongs to
    syncPending = false, -- report everything the save says is looted, once in game
    slots = {},        -- save slot -> true: the slots the session's save is in (empty: none yet)
    slotItems = {},    -- save slot -> how many of the session's items the save in it holds
    live = nil,        -- "<save object>|<timestamp>" of the session's save the count is for, so a
                       -- reloaded mod (the game still running) knows it is the same save
    bindPending = false, -- the client asked to link the loaded save
    scouts = {},       -- location key -> { item, player, flags, own }: what it holds (client scouts)
    apNewGame = false, -- the Archipelago title entry was just chosen: the next new game is one
    newStartOn = nil,  -- ffrap_newstart on|off (round 109); on unless set off. Kept in ap_state.txt once set
}

-- Round 77: a crash about a second after a map change, in a game-thread Lua loop (FName::ToString
-- on a freed object, as in round 71). The stack does not say which mod's loop: FFRS_QoL runs eight.
-- ap_trace.txt gets a line before each step of our loops. After a crash, a last line without its
-- "done" names the step; a "done" last means it was not this mod's loop. Round 79's crash came
-- 5 s after a load, just past the 12 ticks the trace then covered, so it now runs all the time:
-- one handle, unbuffered (the lines reach the OS before a crash), started again at each map load
-- and every TRACE_LINES lines.
state.TRACE_LINES, state.traceLines, state.traceFile = 4000, 0, nil
function state.traceStart(first)
    if state.traceFile then state.traceFile:close() end
    state.traceFile, state.traceLines = io.open(MOD_DIR .. "ap_trace.txt", "w"), 0
    if state.traceFile then state.traceFile:setvbuf("no") end
    state.mark(first)
end
function state.mark(step)
    state.perfMark(step)
    if not state.traceFile then return end
    if state.traceLines >= state.TRACE_LINES then return state.traceStart(step) end
    state.traceLines = state.traceLines + 1
    state.traceFile:write(os.date("%H:%M:%S"), " tick ", state.ticks, " ", step, "\n")
end

-- Round 116: players felt a stutter like a heartbeat, on slower PCs. The loops time each step they
-- mark and each object search (FindAllOf and FindFirstOf go through every object in the game).
-- Every `every` seconds the log gets the slowest; a run over `slow` seconds is logged at once,
-- at most once per `quiet` seconds. ffrap_perf logs the summary now.
state.perf = { every = 120, slow = 0.025, quiet = 10, steps = {}, finds = {}, loops = {}, run = {},
               since = os.clock(), loggedSlow = -math.huge }

function state.perfAdd(stats, key, dt)
    local s = stats[key]
    if not s then
        s = { n = 0, sum = 0, max = 0 }
        stats[key] = s
    end
    s.n, s.sum = s.n + 1, s.sum + dt
    if dt > s.max then s.max = dt end
end

function state.perfMark(step)
    local P, now = state.perf, os.clock()
    if P.step then
        local dt = now - P.at
        state.perfAdd(P.steps, P.step, dt)
        P.run[P.step] = (P.run[P.step] or 0) + dt
    end
    P.step, P.at = not step:find(" done$") and step or nil, now
end

function state.perfTop(stats, n)
    local keys = {}
    for k in pairs(stats) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return stats[a].sum > stats[b].sum end)
    local parts = {}
    for i = 1, math.min(n, #keys) do
        local s = stats[keys[i]]
        parts[#parts + 1] = string.format("%s %dx %.0f ms (max %.0f)", keys[i], s.n, s.sum * 1000, s.max * 1000)
    end
    return #parts > 0 and table.concat(parts, ", ") or "none"
end

function state.perfLines()
    local P = state.perf
    local lines = { string.format("perf: the last %.0f s", os.clock() - P.since) }
    for name, s in pairs(P.loops) do
        lines[#lines + 1] = string.format("perf: %s %d runs, avg %.1f ms, max %.0f ms, %d over %.0f ms",
            name, s.n, s.sum * 1000 / s.n, s.max * 1000, s.over or 0, P.slow * 1000)
    end
    lines[#lines + 1] = "perf: steps " .. state.perfTop(P.steps, 6)
    lines[#lines + 1] = "perf: searches " .. state.perfTop(P.finds, 6)
    P.steps, P.finds, P.loops, P.since = {}, {}, {}, os.clock()
    return lines
end

-- A loop's run took dt: counted, and logged with its steps when slow.
function state.perfLoop(name, dt)
    local P = state.perf
    state.perfAdd(P.loops, name, dt)
    local run = P.run
    P.run = {}
    if dt <= P.slow then return end
    P.loops[name].over = (P.loops[name].over or 0) + 1
    local now = os.clock()
    if now - P.loggedSlow < P.quiet then return end
    P.loggedSlow = now
    local parts = {}
    for step, t in pairs(run) do
        if t >= 0.002 then parts[#parts + 1] = string.format("%s %.0f", step, t * 1000) end
    end
    log(string.format("perf: a %s took %.0f ms (ms by step: %s)", name, dt * 1000, table.concat(parts, ", ")))
end

for _, name in ipairs({ "FindAllOf", "FindFirstOf" }) do
    local raw = _G[name]
    if raw then
        _G[name] = function(class)
            local t0 = os.clock()
            local found = raw(class)
            state.perfAdd(state.perf.finds, name .. " " .. tostring(class), os.clock() - t0)
            return found
        end
    end
end

-- The loaded save, and whether it is the session's. Not kept across game restarts: save data
-- objects are new each run.
local save = {
    obj = nil,         -- the save data object's name (G.SaveObjectName)
    ticks = nil,       -- its timestamp when last seen
    slot = nil,        -- the slot it was loaded from, or nil for an unsaved new game
    pending = nil,     -- a timestamp the game just saved with, until its slot is known
    pendingItems = nil, -- the applied count when that save happened
    apObj = nil,       -- the save object of a new game started from the Archipelago title entry
    apSlot = nil,      -- the slot the Archipelago new game was skipped into
    reskip = false,    -- a new session connected after this Archipelago new game was already skipped
    autoWait = 0,      -- ticks waited before the automatic prologue skip
    autoDone = false,  -- the automatic skip was tried (or given up) for this game
    ok = false,        -- true when this is the session's save
    newStart = nil,    -- the new start the title entry set up: { arrival, party, placeAt, moves }
    newStartDue = false,    -- the new start's game is in: finish it once it is judged
}

-- Keeps the save stamp (game.WriteSaveStamp) equal to the applied count. Flags written now are in
-- the next save the game makes, with the items granted in the same tick. Checked again now and
-- then, in case the game loaded its save data again under the same object.
function save.writeStamp(force)
    local want = tostring(save.obj) .. "|" .. state.applied .. "|" .. state.seed
    if save.stamped == want and not force then return end
    if state.applied > game.STAMP_MAX then
        if save.stamped ~= "full" then log("stamp: " .. state.applied .. " items is past what the stamp holds") end
        save.stamped = "full"
        return
    end
    local wrote, why = game.WriteSaveStamp(state.applied, game.SeedTag(state.seed))
    if wrote == nil then
        if save.stampWhy ~= why then log("stamp: not written (" .. tostring(why) .. ")") end
        save.stampWhy = why
        return
    end
    save.stampWhy = nil
    if wrote > 0 and not state.catchUp then log("stamp: " .. state.applied .. " items (" .. wrote .. " flags)") end
    save.stamped = want
end

-- True when the loaded save belongs to the current session. Round 100: with no session, only a new
-- game from the Archipelago title entry counts (judgeSave), so a player's own saves are left alone.
local function sessionSave()
    return save.ok
end

-- Round 84 (the user): a save of the game's own. It plays as the game made it: our settings are not
-- applied and the Archipelago page leaves the menu. /bind links it.
function save.vanilla()
    return save.obj ~= nil and not save.ok
end

-- Whether the save in play is the seed's. Between loads (the title screen, a load, before the new
-- save is judged) it is the last save's verdict, kept in ap_state.txt across runs, or a new game
-- from the Archipelago entry. For what must be in place before the map loads (round 100: the
-- airship's condition and the lock boxes were written for a new game of the game's own).
function save.seedExpected()
    if save.obj ~= nil then return save.ok end
    return state.apNewGame or state.lastOk == true
end

-- A save not linked to the seed has no locks (round 85: they were still on there). Then an
-- `ffrap_lock on|off` from this run wins. Then a seed that asks for locks: a saved "off" from an
-- old test must not quietly leave a real seed unlocked. Then the saved switch.
local lockChoice = nil
local function locksOn()
    if not save.seedExpected() then return false end
    if lockChoice ~= nil then return lockChoice end
    return seedCfg.openworld or continentLocks == true
end

local function slotsText(withItems)
    local list = {}
    for slot in pairs(state.slots) do list[#list + 1] = slot end
    table.sort(list)
    if withItems then
        for i, slot in ipairs(list) do list[i] = slot .. "=" .. tostring(state.slotItems[slot] or "?") end
    end
    return table.concat(list, ",")
end

-- The session's save is in `slot`, holding `items` of the session's items.
local function linkSlot(slot, items)
    state.slots[slot] = true
    state.slotItems[slot] = items
end

local function unlinkSlot(slot)
    state.slots[slot] = nil
    state.slotItems[slot] = nil
end

-- The loaded save holds `n` items of the session: grant from there on. Lower than before when
-- an older save is loaded, and the items it lacks are granted again.
local function setApplied(n, why)
    if n ~= state.applied then
        log("items: " .. why .. ": " .. n .. " applied (was " .. state.applied .. ")")
        state.applied = n
    end
end

local STATE_PATH = MOD_DIR .. "ap_state.txt"
local STATUS_PATH = MOD_DIR .. "ap_status.txt"

-- The applied count is tracked per save slot so loading an older slot re-grants missing items.
local function loadState()
    local f = io.open(STATE_PATH, "r")
    if not f then return end
    for line in f:lines() do
        local key, value = line:match("^(%w+)\t(.*)$")
        if key == "applied" then state.applied = tonumber(value) or 0 end
        if key == "blank" then state.blank = value == "1" end
        -- Legacy "feed" key is ignored; only explicit "itemfeed" entries written by ffrap_feed are loaded.
        if key == "itemfeed" then feedOn = value == "1" end
        if key == "openstart" then openStart = value == "1" end
        if key == "newstart" then state.newStartOn = value == "1" end
        if key == "continentlocks" then continentLocks = value == "1" end
        if key == "openarrival" and game.OPEN_STARTS[value] then
            openArrival = value
            game.OPEN_START = game.OPEN_STARTS[value]
        end
        if key == "seed" and value ~= "" then state.seed = value end
        if key == "lastok" then state.lastOk = value == "1" end
        if key == "slots" then
            for slot in value:gmatch("%d+") do state.slots[tonumber(slot)] = true end
        end
        if key == "live" and value ~= "" then state.live = value end
        if key == "walked" then
            state.walked = {}
            for map in value:gmatch("%d+") do state.walked[tonumber(map)] = true end
        end
        if key == "slotItems" then
            for slot, n in value:gmatch("(%d+)=(%d+)") do state.slotItems[tonumber(slot)] = tonumber(n) end
        end
    end
    f:close()
end

local function saveState()
    local f = io.open(STATE_PATH, "w")
    if not f then return end
    f:write("applied\t", state.applied, "\n")
    f:write("blank\t", state.blank and "1" or "0", "\n")
    f:write("itemfeed\t", feedOn and "1" or "0", "\n")
    f:write("openstart\t", openStart and "1" or "0", "\n")
    if state.newStartOn ~= nil then f:write("newstart\t", state.newStartOn and "1" or "0", "\n") end
    if openArrival then f:write("openarrival\t", openArrival, "\n") end
    if continentLocks ~= nil then f:write("continentlocks\t", continentLocks and "1" or "0", "\n") end
    f:write("seed\t", state.seed or "", "\n")
    f:write("lastok\t", state.lastOk and "1" or "0", "\n")
    f:write("slots\t", slotsText(), "\n")
    f:write("slotItems\t", slotsText(true), "\n")
    if save.ok and save.obj then state.live = save.obj .. "|" .. tostring(save.ticks) end
    f:write("live\t", state.live or "", "\n")
    if state.walked then
        local maps = {}
        for map in pairs(state.walked) do maps[#maps + 1] = map end
        table.sort(maps)
        f:write("walked\t", table.concat(maps, ","), "\n")
    end
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
    unit = function(it)
        -- Wait for the open-world start before matching party average level; in the prologue Fina is level 55.
        local level = nil
        if seedCfg.openworld and (game.StoryCounter() or 0) >= game.OPEN_START.story then level = game.PartyLevel() end
        local code, detail = game.AddUnit(it.id)
        if level and code == "ok" and detail ~= "already joined" then
            local _, how = game.SetUnitLevel(it.id, level)
            detail = tostring(detail) .. "; " .. tostring(how)
        end
        return code, detail
    end,
    flag = function(it) return game.SetFlag(it.id, it.count ~= 0) end,
    gil = function(it) return game.GrantGil(math.max(it.count, 1)) end,
    -- Crystal Fragments are tracked by the client for the Crystal Tower lock and have no in-game grant.
    token = function() return "ok", "counted by the client" end,
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
    state.seed, state.applied, state.items, state.reported = key, 0, {}, {}
    state.syncPending = true
    state.slots, state.slotItems, state.bindPending, state.live = {}, {}, false, nil
    state.scouts, state.walked, state.walkMap = {}, nil, nil
    seedCfg.party, seedCfg.finalboss, seedCfg.chocobo, seedCfg.airship, seedCfg.continent, seedCfg.radar = nil, nil, nil, nil, nil, nil
    seedCfg.quests, seedCfg.quest2, seedCfg.goal, seedCfg.checks, seedCfg.hidequests = nil, nil, nil, nil, nil
    seedCfg.forge, seedCfg.keyitems = nil, nil
    game.blankRadarParts = false
    if save.apObj ~= nil and save.apObj == save.obj and save.autoDone then save.reskip = true end
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
            seedCfg.heard = true
        elseif f[1] == "cfg" and f[2] == "blank" then
            local want = f[3] == "1"
            if want ~= state.blank then
                state.blank = want
                saveState()
                if game.InGame() then game.BlankChests(want and sessionSave()) end
                log("chest blanking " .. (want and "on" or "off") .. " (client)")
            end
        elseif f[1] == "cfg" and f[2] == "openworld" then
            seedCfg.openworld = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "shinies" then
            seedCfg.shinies = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "shards" then
            seedCfg.shards = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "crystals" then
            seedCfg.crystals = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "bosses" then
            seedCfg.bosses = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "chocobo" then
            seedCfg.chocobo = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "airship" then
            seedCfg.airship = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "radar" then
            seedCfg.radar = f[3] == "1"
            game.blankRadarParts = seedCfg.radar
        elseif f[1] == "cfg" and f[2] == "quests" then
            seedCfg.quests = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "gifts" then
            seedCfg.gifts = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "quest2" then
            seedCfg.quest2 = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "hidequests" then
            seedCfg.hidequests = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "forge" then
            seedCfg.forge = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "keyitems" then
            seedCfg.keyitems = f[3] == "1"
        elseif f[1] == "cfg" and f[2] == "continent" then
            seedCfg.continent = f[3] and f[3]:lower()
        elseif f[1] == "cfg" and f[2] == "finalboss" then
            -- Legacy clients without fragment counts leave lock thresholds unconstrained.
            seedCfg.finalboss = { characters = tonumber(f[3]) or 0, needCharacters = tonumber(f[4]) or 0,
                                  visions = tonumber(f[5]) or 0, needVisions = tonumber(f[6]) or 0,
                                  fragments = tonumber(f[7]) or 0, needFragments = tonumber(f[8]) or 0 }
        elseif f[1] == "cfg" and f[2] == "goal" then
            seedCfg.goal = { kind = f[3], shards = tonumber(f[4]) or 0, needShards = tonumber(f[5]) or 0 }
        elseif f[1] == "cfg" and f[2] == "checks" then
            seedCfg.checks = { done = tonumber(f[3]) or 0, total = tonumber(f[4]) or 0 }
        elseif f[1] == "cfg" and f[2] == "party" then
            local party = {}
            for id in (f[3] or ""):gmatch("%d+") do party[#party + 1] = tonumber(id) end
            if #party >= 1 and #party <= 4 then
                seedCfg.party = party
            else
                log("cfg party ignored: " .. tostring(f[3]))
            end
        elseif f[1] == "sync" then
            if not initial then state.syncPending = true end
        elseif f[1] == "bind" then
            -- Only a request made while the game runs: an old one would link whatever loads first.
            if not initial then state.bindPending = true end
        elseif f[1] == "item" then
            local index, id = tonumber(f[2]), tonumber(f[4])
            if index and id then
                state.items[index] = { kind = f[3], id = id, count = tonumber(f[5]) or 1,
                    label = (f[6] and f[6] ~= "") and f[6] or (f[3] .. " " .. f[4]),
                    flags = tonumber(f[7]), name = f[8] }
            else
                log("bad item line: " .. table.concat(f, " | "))
            end
        elseif f[1] == "scout" then
            -- Location scout data for chest pop-ups. Base64-encoded so ap_in.txt does not spoil
            -- the seed; plain tab-separated fields also work for manual tests.
            local key, item, player, flags, own = f[2], f[3], f[4], f[5], f[6]
            if key and not item then
                local d = bridge.split(bridge.decodeBase64(key))
                key, item, player, flags, own = d[1], d[2], d[3], d[4], d[5]
            end
            if key and item then
                state.scouts[key] = { item = item, player = player or "", flags = tonumber(flags) or 0,
                                      own = own == "1" }
            end
        elseif f[1] == "client" then
            -- The client's world version, written each time it connects.
            local client = tostring(f[2]) .. " (build " .. tostring(f[3] or "?") .. ")"
            if client ~= state.clientVersion then
                state.clientVersion = client
                log("client: world version " .. client)
            end
        elseif f[1] == "msg" then
            -- Messages from before this game session started are old news.
            -- Round 100: and a save of the game's own shows none.
            if not initial and not save.vanilla() then notify(f[2] or "", f[3] and { text = f[3], flags = tonumber(f[4]) } or nil) end
        end
    end
end

-- Items that cannot go in yet, by index. A grant returning "wait" stays queued here and is
-- retried each pass (rebuilt from received visions on save load so older saves get missed unlocks).
-- Only visions re-apply safely; party members are not re-added because the story removes some (e.g. Fina in chapter 3).
local waiting, waitingDirty = {}, true

local function rebuildWaiting()
    waiting = {}
    for i = 0, state.applied - 1 do
        local it = state.items[i]
        if it and it.kind == "vision" and game.HasVision(it.id) ~= true then waiting[#waiting + 1] = i end
    end
end

local function applyWaiting(names)
    if waitingDirty then
        rebuildWaiting()
        waitingDirty = false
    end
    local keep = {}
    for _, i in ipairs(waiting) do
        local it = state.items[i]
        local code, detail = "fail", "item gone"
        if it then code, detail = grant(it) end
        if code == "wait" or code == "retry" then
            keep[#keep + 1] = i
        elseif detail ~= "already owned" then
            log(string.format("item %d %s %d x%d (waited): %s (%s)", i, it.kind, it.id, it.count, code, tostring(detail)))
            bridge.write("applied", i, code, detail)
            if code == "ok" then
                names[#names + 1] = it.label
                names[it.label] = it.name and { text = it.name, flags = it.flags } or nil
            else
                notify("Could not apply " .. it.label .. ": " .. tostring(detail))
            end
        end
    end
    waiting = keep
end

local function applyItems()
    -- Only grant items on the field; granting during battle is overwritten when battle ends.
    if not game.OnField() then
        state.lastResult = "waiting: not on the field"
        return
    end
    -- Round 85: binding a save late in a seed brought 280 items, each with its own "Received" line.
    -- With more than this many waiting, the feed says so once and once more when they are in.
    local CATCH_UP_AFTER = 10
    if not state.catchUp and state.items[state.applied + CATCH_UP_AFTER] then
        local last = state.applied
        while state.items[last + 1] do last = last + 1 end
        state.catchUp = state.applied
        notify("Receiving " .. (last - state.applied + 1) .. " items from Archipelago")
    end
    local done, names = 0, {}
    applyWaiting(names)
    while done < MAX_GRANTS_PER_TICK do
        local it = state.items[state.applied]
        if not it then break end
        local code, detail = grant(it)
        if code == "retry" then
            state.lastResult = "waiting: " .. tostring(detail)
            break
        end
        if code == "wait" then
            log(string.format("item %d %s %d x%d: waits (%s)", state.applied, it.kind, it.id, it.count, tostring(detail)))
            waiting[#waiting + 1] = state.applied
            state.applied = state.applied + 1
            state.lastResult = it.label .. ": waits"
            done = done + 1
            saveState()
        else
            log(string.format("item %d %s %d x%d: %s (%s)", state.applied, it.kind, it.id, it.count,
                code, tostring(detail)))
            bridge.write("applied", state.applied, code, detail)
            if code == "ok" then
                names[#names + 1] = it.label
                names[it.label] = it.name and { text = it.name, flags = it.flags } or nil
            else
                notify("Could not apply " .. it.label .. ": " .. tostring(detail))
            end
            state.applied = state.applied + 1
            state.lastResult = it.label .. ": " .. code
            done = done + 1
            saveState()
        end
    end
    if state.catchUp then
        if not state.items[state.applied] then
            notify("Received " .. (state.applied - state.catchUp) .. " items")
            state.catchUp = nil
        end
    elseif feedOn and game.InGame() then
        -- The feed has a line per item.
        for _, name in ipairs(names) do notify("Received " .. name, names[name]) end
    elseif #names == 1 then
        notify("Received " .. names[1])
    elseif #names > 1 then
        notify("Received " .. #names .. " items: " .. table.concat(names, ", "))
    end
end

-- -------------------------------------------------------------------------------------------
-- Checks
-- -------------------------------------------------------------------------------------------

-- Wait a few scans after a map change so actors from the previous map finish despawning.
local MAP_SETTLE_SCANS = 3

-- This map visit: which map, how many scans it has held, and which chests and shinies were
-- already recorded.
local visit = { mapId = nil, scans = 0, recorded = {}, closed = {} }

-- Everything seen so far, across sessions: our own location list, and the map from each
-- location to the key the save knows it by. One line each in seen.tsv:
--   kind  map  uid  row  item  count  money  visible-condition
-- kind: chest (has a chest table row; row is its "mapId:ID"), xchest (no row), shiny, spot
-- (a shiny-class story or quest point with no reward). map is the current map as the save
-- keys it (CPP_MapManager:GetSameMapId) and uid is m_UniqueId.
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
        -- Legacy format stored rowless chests as "u<uid>" with row map in the row column.
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
    -- scoutShinies: the uids of the seed's shiny locations on this map, built at the first scan
    visit = { mapId = mapId, scans = 0, recorded = {}, closed = {}, disagreed = {}, scoutShinies = nil }
end

-- Chest pop-up override: when a scouted chest check is reported, look up the dialog widget
-- over a few ticks (it can appear slightly after the state change) and replace its reward text.
local POPUP_TRIES = 8
local popup = nil   -- { text, key, tries }

local function popupText(s)
    if s.own then return "You found:\n" .. s.item end
    return "You found " .. s.player .. "'s:\n" .. s.item
end

-- Round 79: Token Legacy's reward row sets its counter only after its item pop-up and the stat
-- bonus dialog have closed, so its check came too late to write the pop-up. While a quest's
-- counter still reads `before` on the map its reward rows run on, an item pop-up in an event there
-- is that quest's. state.questPopups keeps the quests written so, which the check then leaves alone.
state.questPopups = {}
-- A quest's pop-up text and span. Round 98 (the user): a quest with a second reward has a second
-- location, and its pop-up names both, one line each.
function state.questPopup(q)
    local s = state.scouts[q.key]
    if not s then return nil end
    local s2 = seedCfg.quest2 and q.key2 and state.scouts[q.key2]
    if not s2 then return popupText(s), { text = s.item, flags = s.flags } end
    local function line(x) return x.own and x.item or (x.player .. "'s " .. x.item) end
    return "You found:\n" .. line(s) .. "\n" .. line(s2),
        { { text = s.item, flags = s.flags }, { text = s2.item, flags = s2.flags } }
end
-- Whether a quest's reward rows may be running now: its counter at `before` (one value, or one of
-- several, as for each Mog Tag tier) and its `flags` on (round 88).
function state.questRewardDue(q)
    local now, due = game.ProgressValue(q.counter), false
    for _, v in ipairs(type(q.before) == "table" and q.before or { q.before }) do due = due or now == v end
    for _, f in ipairs(q.flags or {}) do due = due and game.GetFlag(f) == true end
    return due
end
-- Round 88 (the user): the Quests screen's Rewards show what each quest location holds, on the
-- seed's save; any other save gets the game's own back. Round 103: with hide_quest_rewards, each
-- shows ??? with no colour. Written again every PRIZE_EVERY ticks, in
-- case the game loads the table again.
state.PRIZE_EVERY = 60
function state.prizeTick()
    local labels, parts = {}, {}
    state.prizeSpans = {}
    if sessionSave() then
        for _, q in ipairs(game.QUESTS) do
            for _, key in ipairs({ q.key, seedCfg.quest2 and q.key2 or nil }) do
                local s = state.scouts[key]
                if s and seedCfg.hidequests then
                    labels[key] = "???"
                    parts[#parts + 1] = key .. "=???"
                elseif s then
                    labels[key] = s.own and s.item or (s.player .. "'s " .. s.item)
                    state.prizeSpans[labels[key]] = { text = s.item, flags = s.flags }
                    parts[#parts + 1] = key .. "=" .. labels[key]
                end
            end
        end
    end
    local sig = table.concat(parts, "|")
    if sig == state.prizeSig and state.ticks % state.PRIZE_EVERY ~= 0 then return end
    local written = game.QuestPrizes(labels)
    if sig ~= state.prizeSig and written > 0 then
        log("quests: " .. written .. " quest rewards " .. (#parts > 0 and "show the location's item" or "back to the game's own"))
    end
    state.prizeSig = sig
end
-- The Quests screen's Rewards with the item's name in its colour (on since round 96). Quiet but
-- for its first line coloured and any it could not colour; ffrap_quest colors on logs it all.
function state.questColorsTick()
    local Q = game.QUEST_COLORS
    if Q.instant and not Q.hooked and game.QuestColorHook(log) then log("quest colours: SetText hook registered") end
    local lines = game.QuestRewardColors(state.prizeSpans or {}, Q.trace)
    for _, line in ipairs(lines) do
        local coloured, failed = line:find("^coloured") ~= nil, line:find("^not coloured") ~= nil
        if state.questVerbose or failed or (coloured and not state.questWorked) then log("quest colours: " .. line) end
        if coloured then
            state.questWorked = true
            Q.trace = nil
        end
    end
end
function state.earlyQuestPopup()
    if not (seedCfg.quests and sessionSave()) or game.OnField() then return end
    local mapId = game.CurrentMap()
    for _, q in ipairs(game.QUESTS) do
        -- Round 89: a quest played again from an older save, its check sent already, gets its
        -- pop-up too. Written once per loaded save.
        if q.map == mapId and state.questPopups[q.key] ~= save.obj and state.questRewardDue(q) then
            local text, span = state.questPopup(q)
            if not text then return end
            local ok, detail = game.ChestPopup(text, span)
            if ok then
                state.questPopups[q.key] = save.obj
                log("chest pop-up for " .. q.key .. " before its check: " .. detail)
            end
            return
        end
    end
end

local function popupTick()
    pcall(game.ChestPopupRestore)
    if not popup then
        state.earlyQuestPopup()
        state.earlyGiftPopup()
        return
    end
    local ok, detail = game.ChestPopup(popup.text, popup.span)
    if ok then
        log("chest pop-up for " .. popup.key .. ": " .. detail)
        popup = nil
        return
    end
    -- A quest's pop-up comes at the end of its reward scene, which can run past a minute (round 78,
    -- the character quests' stat bonus): its wait counts only the time on the field.
    if not popup.scene or game.OnField() then popup.tries = popup.tries - 1 end
    if popup.tries <= 0 then
        log("chest pop-up for " .. popup.key .. ": " .. tostring(detail))
        popup = nil
    end
end

-- Where chests and shinies stand. `same`: a live shiny this close to a level shiny is that shiny
-- (round 72). `reach`: round 78 sent checks with nothing picked up, a Colosseum shard on arrival
-- and world-map shinies a continent away each time a player boarded the airship. The game still
-- had them, and the players picked them up later. A chest or shiny opens with the player at it,
-- so one read as taken farther away than this waits until the player is near it.
-- Round 99: in Waterfall Way two chests nobody opened read open on arrival, and went out once the
-- player came within 1500. A chest or shiny read as taken without being seen closed on this visit
-- is sent only when the map's own save row says taken too (the game writes it on opening).
-- `popup`: such a one gets the pop-up only with the player this close. On a save last played on
-- another computer, chests opened there were sent again on arrival (the server already had them),
-- and the last one's pop-up text went into the next chest the player opened.
local PLACE = { same = 150, reach = 1500, popup = 300 }

-- Round 85: a save bound late in a seed read 80 shinies as taken far away, a line each. They are
-- logged together, the first few by name.
PLACE.far, PLACE.unsaved = {}, {}
PLACE.FAR_NAMED = 5
function PLACE.logHeld(held, one, many)
    if #held == 0 then return end
    if #held == 1 then
        log(held[1] .. "; " .. one)
        return
    end
    local named = {}
    for i = 1, math.min(#held, PLACE.FAR_NAMED) do named[i] = held[i] end
    log(string.format("%d %s: %s%s", #held, many, table.concat(named, "; "),
        #held > PLACE.FAR_NAMED and ("; and " .. (#held - PLACE.FAR_NAMED) .. " more") or ""))
end
function PLACE.logFar()
    PLACE.logHeld(PLACE.far, "not sent until the player is near it",
        "locations read as taken far from the player, not sent until the player is near each")
    PLACE.logHeld(PLACE.unsaved, "never seen closed, and the map's save row does not say taken; not sent until it does",
        "locations read as taken but never seen closed, and the map's save rows do not say taken; not sent until they do")
    PLACE.far, PLACE.unsaved = {}, {}
end

-- How far the player stands from (x, y), or nil when the pawn cannot be read. One pose per scan.
function PLACE.distance(x, y)
    if PLACE.visit ~= visit or PLACE.at ~= visit.scans then
        PLACE.visit, PLACE.at, PLACE.pose = visit, visit.scans, game.PlayerPose()
    end
    local pose = PLACE.pose
    if not pose then return nil end
    return math.sqrt((pose.x - x) ^ 2 + (pose.y - y) ^ 2)
end

-- Round 98: a gift's check was seen only after its pop-up had closed (gift 1400: 30 s of no pop-up),
-- or it wrote the next chest's (1411, 1405). In an event on a gift's map, with its check not sent
-- yet (its flag may be on already), an item pop-up is the gift of the nearest such NPC within TALK;
-- written once per gift and loaded save, which the check then leaves alone.
state.giftPopups = {}
state.GIFT_TALK = 500
function state.earlyGiftPopup()
    if not (seedCfg.gifts and sessionSave()) or game.OnField() then return end
    local mapId, best, bestAt = game.CurrentMap(), nil, nil
    for _, g in ipairs(game.GIFTS) do
        if g.map == mapId and (seedCfg.radar or not g.radar) and state.giftPopups[g.key] ~= save.obj
            and not state.reported["check|" .. g.key] and state.scouts[g.key] then
            local d = PLACE.distance(g.x, g.y)
            if d and d <= state.GIFT_TALK and (not bestAt or d < bestAt) then best, bestAt = g, d end
        end
    end
    if not best then return end
    local s = state.scouts[best.key]
    local ok, detail = game.ChestPopup(popupText(s), { text = s.item, flags = s.flags })
    if ok then
        state.giftPopups[best.key] = save.obj
        log("chest pop-up for " .. best.key .. " before its check: " .. detail)
    end
end

-- A level shiny's place on a map: { uid, x, y }, or nil.
function PLACE.level(mapId, uid)
    for _, p in ipairs(LEVEL_SHINIES[mapId] or {}) do
        if p[1] == uid then return p end
    end
end

-- `fresh` is true when a chest transitions from closed to open in this map visit; request the pop-up
-- rewrite even if the check was already reported (e.g. after reloading an older save). One read open
-- from the first scan gets the pop-up on its first report only with the player within PLACE.popup.
-- `spot` is { x, y, why, saved }: where the location stands (x is nil when not known), what read it
-- as taken, for the log, and whether the map's own save row says taken (nil: not asked).
local function opened(key, fresh, spot)
    if not sessionSave() then return end
    local known = state.reported["check|" .. key]
    if known and not fresh then return true end
    local where, d = "", nil
    if spot then
        d = spot.x and PLACE.distance(spot.x, spot.y)
        if not fresh and spot.saved == false then
            if not visit.recorded["unsaved:" .. key] then
                visit.recorded["unsaved:" .. key] = true
                PLACE.unsaved[#PLACE.unsaved + 1] = string.format("%s reads taken (%s)%s", key, spot.why,
                    d and (", " .. math.floor(d) .. " from the player") or "")
            end
            return false
        end
        if spot.x and not (d and d <= PLACE.reach) then
            if not known and not visit.recorded["far:" .. key] then
                visit.recorded["far:" .. key] = true
                PLACE.far[#PLACE.far + 1] = string.format("%s reads taken (%s), %s", key, spot.why,
                    d and (math.floor(d) .. " from the player") or "the player's place unknown")
            end
            return false
        end
        where = " (" .. spot.why .. (d and (", " .. math.floor(d) .. " from the player") or "") .. ")"
    end
    local new = report("check", key)
    if new then log("check " .. key .. where) end
    local near = fresh or not (spot and spot.x) or (d and d <= PLACE.popup)
    if (new or fresh) and near then
        local s = state.scouts[key]
        -- Shinies use the same dialog widget to show their scouted reward.
        if s and (key:find("^chest:") or key:find("^shiny:")) then popup = { text = popupText(s), span = { text = s.item, flags = s.flags }, key = key, tries = POPUP_TRIES } end
    end
    return true
end

-- A boss check triggers on the win row's flag. Bosses with shuffled items keep their reward
-- pop-up (game.BossesPatch), which may appear after the win scene so it waits longer than a chest.
local BOSS_POPUP_TRIES = 60
local function scanBosses()
    -- A radar treasure's check triggers on its found flag.
    if seedCfg.radar and sessionSave() then
        for _, t in ipairs(game.RADAR) do
            local key = "radar:" .. t.n
            if game.GetFlag(t.flag) == true and report("check", key) then
                log("check " .. key)
                local s = state.scouts[key]
                if s then popup = { text = popupText(s), span = { text = s.item, flags = s.flags }, key = key, tries = BOSS_POPUP_TRIES } end
            end
        end
    end
    -- A side quest's check: its counter at or past the value its reward row writes. The pop-up
    -- comes with the reward row, at the end of the quest's last scene.
    if seedCfg.quests and sessionSave() then
        for _, q in ipairs(game.QUESTS) do
            local done = (game.ProgressValue(q.counter) or 0) >= q.value
            if done and seedCfg.quest2 and q.key2 and report("check", q.key2) then log("check " .. q.key2) end
            if done and report("check", q.key) then
                log("check " .. q.key)
                local text, span = state.questPopup(q)
                if text and state.questPopups[q.key] ~= save.obj then
                    popup = { text = text, span = span, key = q.key, tries = BOSS_POPUP_TRIES, scene = true }
                end
            end
        end
    end
    -- Round 97 (the user): the one-time NPC gifts, by their flags; the pop-up waits for the gift's.
    if seedCfg.gifts and sessionSave() then
        for _, g in ipairs(game.GIFTS) do
            if (seedCfg.radar or not g.radar) and game.GetFlag(g.flag) == true and report("check", g.key) then
                log("check " .. g.key)
                local s = state.scouts[g.key]
                if s and state.giftPopups[g.key] ~= save.obj then
                    popup = { text = popupText(s), span = { text = s.item, flags = s.flags }, key = g.key, tries = BOSS_POPUP_TRIES }
                end
            end
        end
    end
    if not (seedCfg.bosses and sessionSave()) then return end
    -- Round 97 (the user): every boss also gives a Crystal Fragment, a location of its own sent
    -- with the fight's (and on its own for a fight won before this build).
    for _, b in ipairs(game.BOSSES) do
        local key = "boss:" .. b.group
        local won = game.GetFlag(b.flag) == true
        if won and report("check", key) then
            log("check " .. key)
            local s = state.scouts[key]
            if s then popup = { text = popupText(s), span = { text = s.item, flags = s.flags }, key = key, tries = BOSS_POPUP_TRIES } end
        end
        if won and report("check", "fragment:" .. b.group) then log("check fragment:" .. b.group) end
    end
end

-- A chest with a table row is keyed by its row ("chest:3020:1"), because row mapIds do not always
-- match the runtime map id (e.g. 3020:* rows sit in map 2002). Rowless reward chests use map and
-- m_UniqueId ("chest:2002:u54"); rowless chests with no item or gil are story chests and ignored.
local function chestKey(mapId, c)
    if c.rowMap and c.rowId and c.rowId >= 0 then return "chest:" .. c.rowMap .. ":" .. c.rowId end
    local hasReward = (c.itemId and c.itemId >= 0) or (c.money and c.money >= 0)
    if c.uniqueId and hasReward then return "chest:" .. mapId .. ":u" .. c.uniqueId end
    return nil
end

-- Loaded chests are checked by actor state in scanChests, while ffrap_sync reads the save's map
-- rows directly (game.SaveOpenRows) by m_UniqueId. The first save lookup per session is logged to
-- confirm calls work; afterwards only discrepancies are logged.
local gameUidNoted = false
local function noteGameUid(kind, mapId, uid, actor)
    local gameUid, why = game.GameUniqueId(actor)
    local where = string.format("%s %s:%s", kind, tostring(mapId), tostring(uid))
    if not gameUidNoted then
        gameUidNoted = true
        log(where .. ": GetUniqueId " .. (gameUid and ("says " .. gameUid) or ("failed: " .. tostring(why)))
            .. " (first of the session)")
    elseif gameUid and gameUid ~= uid then
        log(where .. ": GetUniqueId says " .. gameUid)
    end
end

local function scanChests(mapId)
    local rows
    for _, c in ipairs(game.LiveChests()) do
        if c.uniqueId then
            local key = chestKey(mapId, c)
            local id = "c" .. c.uniqueId
            if not visit.recorded[id] then
                visit.recorded[id] = true
                local hasRow = c.rowId and c.rowId >= 0
                recordSeen(hasRow and "chest" or "xchest", mapId, c.uniqueId,
                    hasRow and (c.rowMap .. ":" .. c.rowId) or "", c.itemId, c.itemNum, c.money, "")
                noteGameUid("chest", mapId, c.uniqueId, c.actor)
            end
            if c.open then
                local spot = { x = c.x, y = c.y, why = "live open" }
                if key and not visit.closed[id] and not state.reported["check|" .. key] then
                    -- IsOpenTreasureBox is logged to tell whether the chest loaded open from another
                    -- map's row with the same uid (round 65's fallback).
                    rows = rows or game.SaveOpenRows(mapId)
                    spot.saved = rows[c.uniqueId] == true
                    spot.why = "live open, save row " .. tostring(spot.saved)
                    if not spot.saved then
                        spot.why = spot.why .. ", IsOpenTreasureBox " .. tostring(game.IsChestOpenInSave(mapId, c.uniqueId))
                    end
                end
                if not key or opened(key, visit.closed[id] == true, spot) then
                    visit.closed[id] = nil
                end
            else
                visit.closed[id] = true   -- seen closed: opening it later is "in front of the player"
                -- IsOpenTreasureBox falls back to other maps' rows when this map has no save rows yet,
                -- returning false positives on unvisited maps. Judge loaded chests by m_IsOpen instead.
                if key and not visit.disagreed[id] then
                    rows = rows or game.SaveOpenRows(mapId)
                    local native = game.IsChestOpenInSave(mapId, c.uniqueId)
                    if native or rows[c.uniqueId] then
                        visit.disagreed[id] = true
                        log(string.format("%s: the save says open (row %s, IsOpenTreasureBox %s), the chest says closed; not sent",
                            key, tostring(rows[c.uniqueId]), tostring(native)))
                    end
                end
            end
        end
    end
end

-- Shinies report when m_IsOpen is set or the map's save row marks them looted. Spots with neither
-- item nor money are story/quest triggers, recorded as "spot" and never reported.
-- Live shinies can report an m_UniqueId that differs from the level dump, so any level shiny
-- within PLACE.same supplies the canonical ID.
local function levelShinyUid(mapId, s)
    if not (s.x and LEVEL_SHINIES[mapId]) then return s.uid end
    local best, bestD = nil, PLACE.same
    for _, p in ipairs(LEVEL_SHINIES[mapId]) do
        local d = math.sqrt((s.x - p[2]) ^ 2 + (s.y - p[3]) ^ 2)
        if d < bestD then best, bestD = p[1], d end
    end
    if best and best ~= s.uid and not visit.recorded["fix" .. s.uid] then
        visit.recorded["fix" .. s.uid] = true
        log(string.format("shiny %d: the live one reads id %s; the level's shiny there is %d", mapId, tostring(s.uid), best))
    end
    return best or s.uid
end

local function scanShinies(mapId)
    local rows = game.SaveOpenRows(mapId)
    for _, s in ipairs(game.LiveFieldItems()) do
        s.uid = s.uid and levelShinyUid(mapId, s)
        if s.uid then
            local hasReward = (s.itemId and s.itemId >= 0) or (s.money and s.money >= 0)
            if not visit.recorded["s" .. s.uid] then
                visit.recorded["s" .. s.uid] = true
                recordSeen(hasReward and "shiny" or "spot", mapId, s.uid, s.class, s.itemId, s.itemNum, s.money, s.visible)
                noteGameUid("shiny", mapId, s.uid, s.actor)
            end
            local id = "s" .. s.uid
            if hasReward and (s.open or rows[s.uid]) then
                local why = "live " .. (s.open and "open" or "closed") .. ", save row " .. tostring(rows[s.uid] == true)
                if opened("shiny:" .. mapId .. ":" .. s.uid, visit.closed[id] == true,
                    { x = s.x, y = s.y, why = why, saved = rows[s.uid] == true }) then
                    visit.closed[id] = nil
                end
            elseif hasReward then
                visit.closed[id] = true   -- seen closed: picking it up later is "in front of the player"
            end
        end
    end
    -- Because live shiny IDs can differ from level data, also query the save directly for each
    -- of this seed's expected shiny IDs on the current map.
    if not visit.scoutShinies then
        visit.scoutShinies = {}
        local prefix = "shiny:" .. mapId .. ":"
        for key in pairs(state.scouts) do
            local uid = key:sub(1, #prefix) == prefix and tonumber(key:sub(#prefix + 1))
            if uid then visit.scoutShinies[#visit.scoutShinies + 1] = uid end
        end
    end
    for _, uid in ipairs(visit.scoutShinies) do
        local key = "shiny:" .. mapId .. ":" .. uid
        if not state.reported["check|" .. key] and rows[uid] then
            local p = PLACE.level(mapId, uid)
            opened(key, false, { x = p and p[2], y = p and p[3], why = "save row only" })
        end
    end
end

-- Re-sync from the save: every location in seen.tsv the save says is looted gets reported,
-- wherever the player is. A client would run this after a reconnect, or after ap_out.txt was
-- lost. Returns how many were new.
local function syncFromSave()
    local new = 0
    local rowsOf = {}
    for _, e in ipairs(seenList) do
        local key
        if e.kind == "chest" and e.row ~= "" then
            key = "chest:" .. e.row
        elseif e.kind == "shiny" then
            key = "shiny:" .. e.map .. ":" .. e.uid
        end
        if key then rowsOf[e.map] = rowsOf[e.map] or game.SaveOpenRows(e.map) end
        if key and rowsOf[e.map][e.uid] and report("check", key) then new = new + 1 end
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
            log("chest blanking: " .. game.BlankChests(true) .. " rows emptied")
        end
    end
    -- Blank shinies before the map settles so none can be picked up before blanking takes effect.
    if (seedCfg.shinies or seedCfg.shards) and sessionSave() then
        for _, s in ipairs(game.LiveFieldItems()) do game.BlankFieldItem(s, seedCfg.shinies, seedCfg.shards) end
    end
    visit.scans = visit.scans + 1
    if visit.scans <= MAP_SETTLE_SCANS then return end
    scanChests(mapId)
    scanShinies(mapId)
    PLACE.logFar()
end

-- Goal victory tracking: Rain vs. Sol (battle group 9056). Story reaches 8050 before the last
-- floor and 9000 after ending scenes; row C08_821_01 clears story flag 40 (set since C08_812_01)
-- after the win, so at story >= 8050 flag 40 reading false indicates victory.
local FINAL_BATTLE, FINAL_STORY, FINAL_FLAG = 9056, 8050, 40

local function watchStory()
    local n = game.StoryCounter()
    if n and n ~= state.lastStory then
        if state.lastStory then log("story " .. state.lastStory .. " -> " .. n) end
        state.lastStory = n
        report("story", n)
    end
    if n == FINAL_STORY and game.GetFlag(FINAL_FLAG) == false and report("won", FINAL_BATTLE) then
        log("the last battle is won (battle group " .. FINAL_BATTLE .. ", flag " .. FINAL_FLAG .. " off)")
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
    if state.lastOk ~= ok then
        state.lastOk = ok
        saveState()
    end
end

local titleReady = false   -- the Archipelago title entry is in the menu's data asset

-- Decides whether a save that was just loaded (or a new game) is the session's.
local function judgeSave()
    if not state.seed then setOk(save.apObj ~= nil and save.apObj == save.obj); return end
    -- The same save the count was for, still loaded (the mod was reloaded): keep the count.
    local same = state.live ~= nil and state.live == (tostring(save.obj) .. "|" .. tostring(save.ticks))
    local stampCount, stampTag = game.ReadSaveStamp()
    local ours = stampTag ~= nil and stampTag == game.SeedTag(state.seed)
    -- A save stamped by another seed is not the session's, whatever ap_state.txt says of its slot.
    local foreign = stampTag ~= nil and stampTag ~= 0 and not ours
    if save.apObj ~= nil and save.apObj == save.obj then
        -- Started from the Archipelago title entry: it joins the session even when the session
        -- has other saves already. It holds none of the session's items yet. It may have
        -- autosaved before the client connected, so its slot is linked too.
        setOk(true)
        -- Round 106: a load of the slot it was skipped into (the skip's own reload, a game over,
        -- the player's load) holds the items given before that save, as its stamp says. Taking 0
        -- there gave every item twice. Only the unsaved new game holds none.
        local held = 0
        if ours then held = stampCount elseif save.slot ~= nil then held = state.slotItems[save.slot] or 0 end
        if not same then setApplied(held, "an Archipelago new game") end
        if save.slot ~= nil then linkSlot(save.slot, state.applied) end
        saveState()
        -- Log only (no on-screen notice), since the player explicitly chose the Archipelago entry.
        log("Archipelago: this new game is linked to the seed")
    elseif ours then
        -- The stamp travels with the save: another PC, or ap_state.txt deleted on an update.
        setOk(true)
        log("save is stamped with this seed: it holds " .. stampCount .. " items")
        if not same then setApplied(stampCount, "the save's stamp") end
        if save.slot ~= nil then linkSlot(save.slot, state.applied) end
        saveState()
    elseif save.slot ~= nil and state.slots[save.slot] and not foreign then
        setOk(true)
        log("save slot " .. save.slot .. " is the session's save")
        -- Legacy state files without a per-slot count retain the previous applied count.
        local n = state.slotItems[save.slot]
        if n and not same then setApplied(n, "slot " .. save.slot .. " holds") end
    elseif save.slot == nil and next(state.slots) == nil and not titleReady then
        -- A new game that was never saved, and the session has no save yet: link it. It joins
        -- a slot the first time it is saved. It holds none of the session's items yet. Only
        -- without the Archipelago title entry: with it, plain New Game stays vanilla.
        setOk(true)
        if not same then setApplied(0, "a new game") end
        saveState()
        notify("Archipelago: this new game is linked to the seed")
    else
        setOk(false)
        notify("Archipelago is paused: this save is not linked to the seed. Load the linked save, " ..
            (titleReady and "start one from Archipelago on the title menu" or "start a new game") ..
            ", or use /bind in the client to link this one.")
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
    -- A save that was already the session's keeps its count; any other holds none of the
    -- session's items, so it gets all of them.
    if not save.ok then setApplied(0, "a newly linked save") end
    state.slots, state.slotItems = {}, {}
    if save.slot ~= nil then linkSlot(save.slot, state.applied) end
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
        -- A brand-new game inherits the autosave slot timestamp it will overwrite; story values
        -- at the very start always represent an unlinked new game.
        local story = game.StoryCounter()
        -- Round 109: the new start's game begins at its arrival's story, not 1000.
        local startStory = state.apNewGame and save.newStart and save.newStart.arrival.story
        local fresh = story and (story <= NEW_GAME_STORY or story == startStory)
        if save.slot ~= nil and fresh then
            log("story " .. story .. ": a new game, although its timestamp matches slot " .. save.slot)
            save.slot = nil
        end
        -- The new game the Archipelago title entry started (any other load uses up the mark).
        if state.apNewGame then
            state.apNewGame = false
            if save.slot == nil and fresh then
                save.apObj, save.apSlot, save.reskip, save.autoWait, save.autoDone = obj, nil, false, 0, false
                save.waitNoted = false
                log("an Archipelago new game")
                if startStory then
                    save.newStartDue = story == startStory
                    if not save.newStartDue then save.dropNewStart("the new game is at story " .. story) end
                end
            end
        elseif save.apSlot ~= nil and save.slot == save.apSlot then
            save.apObj = obj
        elseif save.apObj ~= obj then
            save.apObj, save.apSlot, save.reskip = nil, nil, false
        end
        log("save loaded: slot " .. tostring(save.slot) .. ", session slots [" .. slotsText(true) .. "]")
        judgeSave()
        waitingDirty = true
        if save.newStartDue then
            save.newStartDue = false
            save.finishNewStart()
        end
    elseif ticks ~= save.ticks then
        -- The game saved. Grants happen after this check in the same tick, so the count now is
        -- what the save holds.
        save.ticks, save.pending, save.pendingItems = ticks, ticks, state.applied
    end
    if save.pending then
        local slot = game.SlotForTicks(save.pending)   -- the summary can catch up a moment later
        if slot ~= nil then
            save.pending, save.slot = nil, slot
            if state.seed and save.ok then
                local new = not state.slots[slot]
                linkSlot(slot, save.pendingItems or state.applied)
                saveState()
                if new then log("saved to slot " .. slot .. ": session slots [" .. slotsText(true) .. "]") end
            elseif state.seed and not save.ok and state.slots[slot] then
                unlinkSlot(slot)
                saveState()
                notify("Archipelago: slot " .. slot .. " now holds another game and is no longer linked")
            end
        end
    end
end

-- -------------------------------------------------------------------------------------------
-- The Archipelago new game: the title entry and the prologue skip
-- -------------------------------------------------------------------------------------------

-- Round 109: the new start (game.NewStartPrepare). The Archipelago new game begins at the open
-- world start, with no prologue, no save and no reload, so it works with autosave off. On by
-- default since round 110 passed. ffrap_newstart off, or no seed heard yet, falls back to the
-- prologue skip, which waits for the first autosave.
function save.newStartStep(what) log("newstart: " .. what) end

-- In the title's pre-hook: the game's data starts the new game at the seed's arrival. Round 109
-- (the user): on foot by the starting continent's town for every seed, with the airship parked
-- there when the seed starts with it.
function save.armNewStart()
    local a = game.FOOT_STARTS[seedCfg.continent or ""] or seedArrival()
    local ok, report = game.NewStartPrepare({ arrival = a, party = seedCfg.party, step = save.newStartStep })
    for _, line in ipairs(report) do log("newstart: " .. line) end
    if not ok then
        log("newstart: not set up; the prologue skip takes over")
        return
    end
    save.newStart = { arrival = a, party = seedCfg.party }
    log("newstart: the new game starts at " .. a.name .. " (map " .. a.map .. ", story " .. a.story .. ")")
end

-- Puts the game's data back and forgets the new start.
function save.dropNewStart(why)
    local put = game.NewStartRestore(save.newStartStep)
    if put then log("newstart: put back (" .. why .. "): " .. put) end
    save.newStart = nil
end

-- The new start's game is in and linked: the rest of the start goes into its save.
function save.finishNewStart()
    local ns = save.newStart
    local put = game.NewStartRestore(save.newStartStep)
    log("newstart: put back " .. tostring(put))
    local ok, report = game.NewStartFinish({ arrival = ns.arrival, party = ns.party })
    for _, line in ipairs(report) do log("newstart: " .. line) end
    if not ok then notify("Archipelago: the new start had failures (see UE4SS.log)") end
    save.autoDone = true
    local _, where = game.NewStartWhere(ns.arrival)
    log("newstart: arrived: " .. where)
    ns.placeAt, ns.moves = state.ticks + 2, 0
    local ignored, why = game.HoldMove(true)
    ns.held, ns.releaseBy = ignored ~= nil, state.ticks + game.NEW_START.holdTicks
    log("newstart: move input held: ignored " .. tostring(ignored) .. (why and " (" .. why .. ")" or ""))
end

function save.releaseMove(why)
    local ns = save.newStart
    if not (ns and ns.held) then return end
    ns.held = false
    local ignored, err = game.HoldMove(false)
    log("newstart: move input given back (" .. why .. "): ignored " .. tostring(ignored)
        .. (err and " (" .. err .. ")" or "") .. "; " .. game.InputState())
end

-- After the start: the airship and the player are moved to the arrival, with move input held.
-- Round 109's MapTestStartByLoadSaveData is not a reload from memory: it loaded slot 0, another
-- game. The arrival's island may not be loaded at the move, so a player found below it is moved
-- again, once. Round 115: only below it. A second move of a player who had walked 359 away froze
-- the pawn.
function save.newStartTick()
    local ns = save.newStart
    if not ns then return end
    if ns.held and state.ticks >= ns.releaseBy then save.releaseMove("time limit") end
    if not (ns.placeAt and state.ticks >= ns.placeAt) then return end
    ns.placeAt = nil
    local a = ns.arrival
    local dist, where, z = game.NewStartWhere(a)
    if ns.moves > 0 then log("newstart: after the move: " .. where) end
    local sunk = z and z < a.z - game.NEW_START.near
    if not dist then
        log("newstart: not on the arrival's map, left there: " .. where)
    elseif (ns.moves == 0 and dist > game.NEW_START.near) or (ns.moves < 2 and sunk) then
        ns.moves = ns.moves + 1
        local _, line = game.NewStartMove(a, save.newStartStep)
        log("newstart: " .. line)
        ns.placeAt = state.ticks + 4
        return
    end
    save.releaseMove(dist and "at the arrival" or "not on the arrival's map")
    save.newStart = nil
end

-- Title menu entries use ETitleFunctionType; the Archipelago entry uses type 5 as a copy of New Game
-- (game.AddTitleEntry). The ExecuteEntry pre-hook flags the next new game and rewrites type 5 to New Game.
local titleHooked = false
local function hookTitle()
    if titleHooked then return true end
    local ok, err = pcall(function()
        RegisterHook("/Script/mucha.CPP_VM_Title:ExecuteEntry", function(_, inType)
            local t
            pcall(function() t = inType:get() end)
            log("title: entry " .. tostring(t) .. " chosen")
            -- A new start set up before and never used (the player backed out): put it back first.
            if save.newStart then save.dropNewStart("the title menu was used again") end
            if t == game.TITLE_ARCHIPELAGO and state.refuseAs ~= false then
                local session, why = bridge.readAlive(os.time())
                if not session then
                    local as = state.refuseAs or game.TITLE_LOAD_GAME
                    pcall(function() inType:set(as) end)
                    notify("Archipelago: connect the client to your slot first, then choose the entry again")
                    log("title: no new game without the client (" .. why .. "): the choice became entry " .. as)
                    return
                end
                log("title: the client is connected (" .. session .. ")")
            end
            if t == game.TITLE_ARCHIPELAGO then
                state.apNewGame = true
                pcall(function() inType:set(game.TITLE_NEW_GAME) end)
                notify((seedCfg.heard or openStart) and "Archipelago: starting a new game for the seed"
                    or "Archipelago: starting a new game. Connect the client now: the prologue skip waits for it")
                -- Log when skipped because open-world mode is off.
                log("title: open world start is " .. (openStartOn() and "on" or "off") .. " (ffrap_openstart or the seed)")
                -- The arrival and the party come from the seed, so the client must have spoken.
                if state.newStartOn ~= false and openStartOn() and (seedCfg.heard or openStart) then
                    save.armNewStart()
                elseif state.newStartOn ~= false then
                    log("newstart: not used (" .. (openStartOn() and "no seed heard yet" or "no open world start") .. ")")
                end
            end
        end)
    end)
    titleHooked = ok
    if not ok then log("title: could not hook ExecuteEntry: " .. tostring(err)) end
    return ok
end

-- Keeps the title entry in place: added at start-up, before the menu first reads the asset,
-- and checked again now and then in case the game reloads the asset. Loads the asset only
-- outside a game.
local orderLogged = nil   -- the last order result logged, so each new one is logged once
-- Keep the moogle's Vision Enhancement screen closable even when nothing can be enhanced by
-- forcing CPP_BFL_VisionUpgrade:IsVisionUpgrade to return true via a post-hook.
local visionExitHooked = false
local visionExitLast = "unset"
local function hookVisionExit()
    if visionExitHooked then return true end
    local ok, err = pcall(function()
        RegisterHook("/Script/mucha.CPP_BFL_VisionUpgrade:IsVisionUpgrade", function() end, function(_, ret)
            local was
            pcall(function() was = ret:get() end)
            if was ~= visionExitLast then
                visionExitLast = was
                log("vision screen: the game says closable is " .. tostring(was) .. (seedCfg.openworld and sessionSave() and "; answering true" or ""))
            end
            if seedCfg.openworld and sessionSave() then return true end
        end)
    end)
    visionExitHooked = ok
    if not ok then log("vision screen: could not hook IsVisionUpgrade: " .. tostring(err)) end
    return ok
end

local layoutLogged = false   -- the version text's layout is logged once per run (for the logo)
local logoLogged = nil       -- the last logo failure logged, so each one is logged once
local function titleTick()
    if state.ticks ~= 1 and state.ticks % TITLE_EVERY ~= 0 then return end
    hookVisionExit()
    local inGame = game.InGame()
    if not inGame then
        local live = bridge.readAlive(os.time()) ~= nil or state.refuseAs == false
        game.TITLE_LABEL = live and game.TITLE_LABEL_LIVE or game.TITLE_LABEL_NO_CLIENT
        if live ~= state.clientLive then log("title: client " .. (live and "connected" or "not connected")) end
        state.clientLive = live
    end
    local ok, detail = game.AddTitleEntry(not inGame)
    if ok and hookTitle() then
        if not titleReady then log("title: Archipelago entry ready (" .. tostring(detail) .. ")") end
        titleReady = true
    elseif ok and not titleReady then
        log("title: the entry is in, but the choice could not be hooked")
    end
    if ok then
        local okOrder, how = game.OrderTitleEntries()
        local text = (okOrder and "" or "could not order: ") .. tostring(how)
        if okOrder and how == "already in order" then text = nil end
        if text and text ~= orderLogged then
            log("title: entry order " .. text)
            orderLogged = text
        end
    end
    if not inGame then
        local shown, block = game.TitleVersionLine(TITLE_LINE)
        if shown == "added" then
            log("title: \"" .. TITLE_LINE .. "\" shown above the version text")
            if not layoutLogged and block then
                layoutLogged = true
                log("title: version text layout: " .. game.DescribeWidget(block))
            end
        elseif shown == "already" then
            -- A check later than the one that added the line, so the text block has been laid
            -- out with both lines and its size is right for placing the logo.
            local logo, detail = game.TitleLogo(LOGO_PATH, TITLE_LINE)
            if logo == "added" or (logo == nil and detail ~= logoLogged) then
                log("title: logo " .. tostring(logo or "not added") .. ": " .. tostring(detail))
                logoLogged = detail
            end
        end
    end
end

-- Re-apply the prologue skip right before saving because the opening scene can overwrite flags and
-- position after the initial skip. Only the inventory step is non-idempotent, so it runs once per save.
local skipped = nil    -- the save object the skip was applied to
-- `force` (ffrap_skip <slot> force) skips before story 1005 for probing the opening input lock.
local function runSkip(slot, why, force)
    local obj, story = game.SaveObjectName(), game.StoryCounter()
    if skipped ~= obj and (not story or story > game.SKIP_FROM_MAX) then
        notify("ffrap_skip works on a new game only (story " .. tostring(story) .. ", must be "
            .. game.SKIP_FROM_MAX .. " or lower)")
        return false
    end
    if force and story < game.SKIP_FROM_MIN then
        log("skip: forced at story " .. story .. " (before " .. game.SKIP_FROM_MIN .. "): expect the opening's input lock")
    elseif skipped ~= obj and story < game.SKIP_FROM_MIN then
        notify("Wait until you can move (story " .. game.SKIP_FROM_MIN .. ", now " .. story .. "): a skip during "
            .. "the opening movie leaves you without menus or movement")
        return false
    end
    local again = skipped == obj
    local okRun, ok, report = pcall(game.SkipPrologue, { inventory = not again, openStart = openStartOn(), party = seedCfg.party,
                                                         arrival = seedArrival() })
    if not okRun then
        notify("Prologue skip raised an error: " .. tostring(ok))
        return false
    end
    for _, line in ipairs(report) do log("skip" .. (again and " (again)" or "") .. ": " .. line) end
    skipped = obj
    if not slot then
        notify("Prologue skip " .. (ok and "applied" or "applied with failures (see the log)")
            .. ". Nothing saved yet: ffrap_skip <slot> saves and reloads")
        return true
    end
    if not ok then notify("Prologue skip had failures (see the log); saving anyway") end
    -- The reload makes a new save object from this slot, so a linked session must own the slot
    -- first, or the reloaded game would look like someone else's.
    if save.apObj == obj then save.apSlot = slot end
    if state.seed and save.ok then
        linkSlot(slot, state.applied)
        saveState()
        log("skip: slot " .. slot .. " linked before the reload: session slots [" .. slotsText(true) .. "]")
    end
    local arrival = openStartOn() and seedArrival() or game.SKIP_ARRIVAL
    local saved, detail = game.SaveAndReload(slot, arrival.map)
    if openStartOn() then detail = detail .. "; open world start (" .. arrival.name .. ", story " .. arrival.story .. ")" end
    log("skip (" .. why .. "): " .. detail)
    -- Log the automatic skip only on failure (success is expected as part of starting an AP game).
    if saved and why == "automatic" then
        log("Prologue skipped: " .. detail)
    else
        notify(saved and ("Prologue skipped: " .. detail) or ("Prologue skip: " .. detail))
    end
    return saved
end

-- The automatic skip on an Archipelago new game: once the player can move (story 1005) and the
-- game has made its first autosave (so the save has a slot), wait a moment and skip into that
-- slot. One try per game: if it fails, ffrap_skip is still there.
local function autoSkip()
    if save.autoDone or not save.apObj or save.apObj ~= save.obj or skipped == save.obj then return end
    local story = game.StoryCounter()
    if not story or story < game.SKIP_FROM_MIN or save.slot == nil then return end
    if story > game.SKIP_FROM_MAX then
        save.autoDone = true
        log("skip: the story is past " .. game.SKIP_FROM_MAX .. ", so the prologue is not skipped")
        return
    end
    -- Round 77: with no client this run, the skip went to chapter 1 for an older seed's session.
    -- The story holds at 1005 until the player moves on, so the skip can wait for the client.
    if not seedCfg.heard and not openStart then
        if not save.waitNoted then
            save.waitNoted = true
            notify("Archipelago: connect the client to this seed. The prologue skip waits for it")
        end
        return
    end
    save.autoWait = save.autoWait + 1
    if save.autoWait < AUTO_SKIP_WAIT then return end
    save.autoDone = true
    if not runSkip(save.slot, "automatic") then
        notify("The automatic prologue skip did not finish: ffrap_skip " .. save.slot .. " tries again")
    end
end

-- -------------------------------------------------------------------------------------------
-- Status
-- -------------------------------------------------------------------------------------------

local function queued()
    local n = 0
    for index in pairs(state.items) do if index >= state.applied then n = n + 1 end end
    return n
end

local function statusLines()
    local party = game.PartyIds()
    return {
        "FFRArchipelago " .. VERSION .. " (build " .. bridge.build(MOD_DIR) .. ")  " .. os.date("%Y-%m-%d %H:%M:%S"),
        "in game: " .. tostring(game.InGame()) .. " (" .. state.inGameTicks .. " ticks)",
        "map: " .. tostring(game.CurrentMap()) .. " (save's Map.mapId " .. tostring(game.MapId()) .. ")   story: " .. tostring(game.StoryCounter()),
        "party: " .. (party and table.concat(party, ", ") or "?"),
        "items applied: " .. state.applied .. "   queued: " .. queued(),
        "chest blanking: " .. (state.blank and "on" or "off") .. "   session: " .. tostring(state.seed),
        "save: slot " .. tostring(save.slot) .. ", session slots [" .. slotsText(true) .. "], " ..
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

-- Watches an active experimental gate (ffrap_gate). Does nothing until one is spawned.
local gateNear = false
local gateHintAt = -999

local function gateTick()
    if not (game.HasActiveGate and game.HasActiveGate()) then
        gateNear = false
        return
    end
    local info = game.PollGate()
    if not info or info.gone then
        gateNear = false
        log("gate: cleared (actor gone or map changed)")
        return
    end
    if info.changed == "unlocked" then
        gateNear = false
        notify("Gate unlocked! (" .. tostring(info.condText) .. ")")
        return
    elseif info.changed == "locked" then
        notify("Gate locked (" .. tostring(info.condText) .. ")")
    end
    if info.locked and info.condText and info.dist and info.bumpDist then
        if info.dist <= info.bumpDist then
            if not gateNear and (feedClock - gateHintAt >= 3.0) then
                gateNear = true
                gateHintAt = feedClock
                show("Gate locked: need " .. info.condText)
                log("gate: blocked player at dist " .. string.format("%.1f", info.dist) .. " (" .. info.condText .. ")")
            end
        elseif info.dist > info.bumpDist + 40.0 then
            gateNear = false
        end
    else
        gateNear = false
    end
end

local scaleTick   -- set with the ffrap_scale command, below
local settingsTick   -- the player's settings (ffrap_set), below
local menuTick       -- our rows in the Options screen, below
local seedExtrasTick -- the Chocobo and the chest icons, below
local airshipItemTick -- the airship as an item, below
local finalLockTick  -- the Crystal Tower's last climb, below
local bossTest = { group = nil }   -- ffrap_bossfight, below: the group armed, and its tick

-- Walking crossings between continents (game.CrossingSync): reads crossings.txt if present,
-- otherwise game.CROSSINGS. `ffrap_gate mark` and adjustment commands write one line per crossing:
--   <continent a> <continent b> <x> <y> <z> <yaw> <scale>
local CROSSINGS_PATH = MOD_DIR .. "crossings.txt"
local crossings = {}
local CROSSING_HINT_NEAR, CROSSING_HINT_AGAIN = 900, 1500
local crossingHinted, crossingFailed = nil, nil
-- On foot the pawn's rotation stays at 0, so compute movement heading from successive positions.
local walk = { x = nil, y = nil, heading = nil }
local WALK_MIN_STEP = 40

local function readCrossings()
    crossings = {}
    local f = io.open(CROSSINGS_PATH, "r")
    if not f then
        for _, c in ipairs(game.CROSSINGS) do
            crossings[#crossings + 1] = { a = c.a, b = c.b, x = c.x, y = c.y, z = c.z, yaw = c.yaw, scale = c.scale }
        end
        return
    end
    for line in f:lines() do
        local a, b, x, y, z, yaw, scale = line:match("^(%a+)%s+(%a+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s+(%S+)")
        if a and game.IsContinent(a) and game.IsContinent(b) and tonumber(scale) then
            crossings[#crossings + 1] = { a = a, b = b, x = tonumber(x), y = tonumber(y), z = tonumber(z),
                                          yaw = tonumber(yaw), scale = tonumber(scale) }
        elseif line:match("%S") then
            log("crossings.txt: line ignored: " .. line)
        end
    end
    f:close()
end

local function writeCrossings()
    local f = assert(io.open(CROSSINGS_PATH, "w"))
    for _, c in ipairs(crossings) do
        f:write(string.format("%s\t%s\t%.0f\t%.0f\t%.0f\t%.1f\t%.2f\n", c.a, c.b, c.x, c.y, c.z, c.yaw, c.scale))
    end
    f:close()
end

local function crossingsTick()
    local pose = game.CurrentMap() == game.WORLD_MAP and game.PlayerPose()
    if pose and walk.x and math.sqrt((pose.x - walk.x) ^ 2 + (pose.y - walk.y) ^ 2) >= WALK_MIN_STEP then
        walk.heading = math.atan(pose.y - walk.y, pose.x - walk.x)
    end
    if pose then walk.x, walk.y = pose.x, pose.y end
    local placed, removed = game.CrossingSync(crossings)
    if not placed then
        if removed ~= "not on the world map" and removed ~= "settling" and removed ~= crossingFailed then
            log("crossings: " .. tostring(removed))
            crossingFailed = removed
        end
        return
    end
    crossingFailed = nil
    if placed > 0 or removed > 0 then
        log(string.format("crossings: %d placed, %d opened (%d marked)", placed, removed, #crossings))
    end
    local near, locked, d = game.CrossingNear(crossings, CROSSING_HINT_AGAIN)
    if near and d < CROSSING_HINT_NEAR and crossingHinted ~= near then
        crossingHinted = near
        local names = {}
        for _, side in ipairs(locked) do names[#names + 1] = side:sub(1, 1):upper() .. side:sub(2) .. " Unlock" end
        notify("The way is closed. You need " .. table.concat(names, " and "))
    elseif not near then
        crossingHinted = nil
    end
end

-- Continent locks (game.ContinentSync): re-spawn world-map lock boxes after map transitions so
-- they match the save's flags. Run only on the field (never during battle).
local function locksTick()
    -- The boxes the map load placed before the save was known, and the ferry's closed ports, come
    -- off once for each such save.
    if save.vanilla() then
        if state.unlockedSave ~= save.obj then
            state.unlockedSave = save.obj
            game.ContinentClear()
            local ferry = game.FerrySync(true)
            log("locks: off for a save not linked to the seed (" .. ferry .. " ferry choices put back)")
        end
        return
    end
    state.unlockedSave = nil
    if not locksOn() or not game.OnField() then return end
    local ferry = game.FerrySync()
    if ferry > 0 then log("ferry: " .. ferry .. " port choices written") end
    local placed, removed, listed = game.ContinentSync()
    if not placed then
        -- `removed` holds why. Not being on the world map is the normal case.
        if removed ~= "not on the world map" and removed ~= locksFailed then
            log("locks: " .. tostring(removed))
            locksFailed = removed
        end
        return
    end
    locksFailed = nil
    if #placed > 0 then log("locks: boxes placed for " .. table.concat(placed, ", ")) end
    if #removed > 0 then log("locks: opened " .. table.concat(removed, ", ")) end
    if listed then log("locks: " .. listed) end
    crossingsTick()
end

local function tick()
    state.ticks = state.ticks + 1
    state.mark("inbox")
    readInbox(false)
    state.mark("title")
    titleTick()
    feedClock = state.ticks * TICK_MS / 1000
    if game.InGame() then
        state.mark("feed")
        pcall(flushFeed)
        pcall(game.FeedTick, feedClock)
    end
    state.mark("menu")
    if titleReady or game.InGame() then pcall(menuTick) end
    -- Apply the seed's airship spawn condition before a map loads so a new game starts hidden if needed.
    -- Round 100: only for the seed's save; a save of the game's own gets the game's condition back.
    if state.ticks % LOCKS_EVERY == 0 then
        local okSync, wrote = pcall(game.AirshipItemSync, seedCfg.airship == false and save.seedExpected())
        if okSync and wrote then log("airship: spawn condition " .. wrote) end
    end
    if not game.InGame() then
        if state.inGameTicks > 0 then log("left the game (title screen or loading)") end
        state.inGameTicks = 0
        state.lastStory = nil
        save.obj = nil
    else
        state.inGameTicks = state.inGameTicks + 1
        if state.inGameTicks == 1 then
            log("save loaded, map " .. tostring(game.CurrentMap()))
            if randomizerWarning then
                notify(randomizerWarning)
                randomizerWarning = nil
            end
        end
        if state.inGameTicks > SETTLE_TICKS then
            state.mark("follow save")
            followSave()
            if state.bindPending then
                state.bindPending = false
                bindLoaded()
            end
            state.mark("skip")
            autoSkip()
            pcall(save.newStartTick)
            if save.reskip and save.ok and save.slot ~= nil then
                save.reskip = false
                skipped = save.obj
                runSkip(save.slot, "automatic")
            end
            state.mark("pop-up, gates")
            pcall(popupTick)
            pcall(gateTick)
            if bossTest.group then pcall(bossTest.tick) end
            state.mark("scale, settings")
            if state.ticks % STATUS_EVERY == 0 then pcall(scaleTick) end
            pcall(state.fightTick)
            if state.ticks % STATUS_EVERY == 0 then pcall(settingsTick) end
            -- Round 117: one tick in two carried every slow step (25 to 40 ms on the user's desktop,
            -- a stutter like a heartbeat on a laptop). The extras and the table patches run on the
            -- other tick now.
            state.mark("extras")
            if state.ticks % LOCKS_EVERY == 1 then pcall(seedExtrasTick) end
            state.mark("locks")
            if state.ticks % LOCKS_EVERY == 0 then pcall(locksTick) end
            -- Round 100: Rain went to level 55 in a new game of the game's own (Fina's prologue level).
            -- Round 109: and in the seed's own save, when the prologue skip never ran (autosave off):
            -- only past the open world start's story is the party the seed's.
            state.mark("level")
            if state.ticks % STATUS_EVERY == 0 and seedCfg.openworld and sessionSave() and game.OnField()
                and (game.StoryCounter() or 0) >= game.OPEN_START.story then pcall(game.SyncSlotLevel) end
            state.mark("patches")
            if seedCfg.openworld and state.ticks % LOCKS_EVERY == 1 then
                -- Round 100: the seed's table patches are for the seed's save only. The tables stay
                -- patched until the game restarts, so a save of the game's own after one is told so.
                local ours = sessionSave()
                local newSave = ours and shopSave ~= save.obj
                local okShop, blocked, rows = pcall(game.VisionShopGuard, newSave, ours)
                if ours then
                    shopSave, state.unpatchedSave = save.obj, nil
                    if newSave then state.tablesPatched = true end
                elseif state.unpatchedSave ~= save.obj then
                    state.unpatchedSave, shopSave = save.obj, nil
                    if state.tablesPatched then
                        notify("Archipelago: restart the game before playing this save. The seed's changes to the game's data are still loaded.")
                        log("patches: not applied to a save not linked to the seed, but the seed's are loaded from earlier in this run")
                    end
                end
                if newSave and seedCfg.crystals then
                    local okCrystals, written = pcall(game.CrystalsPatch)
                    log("crystals: " .. tostring(written) .. " event rows set to skip the scene" .. (okCrystals and "" or " (failed)"))
                end
                if newSave and seedCfg.bosses then
                    local okBosses, written = pcall(game.BossesPatch)
                    log("bosses: " .. tostring(written) .. " win rows changed" .. (okBosses and "" or " (failed)"))
                end
                if newSave and seedCfg.radar then
                    local okRadar, written = pcall(game.RadarPatch)
                    log("radar: " .. tostring(written) .. " treasure rewards set to the pop-up's stand-in" .. (okRadar and "" or " (failed)"))
                end
                if newSave and seedCfg.quests then
                    local okQuests, written = pcall(game.QuestsPatch, seedCfg.quest2)
                    log("quests: " .. tostring(written) .. " reward rows without the location's item" .. (okQuests and "" or " (failed: " .. tostring(written) .. ")"))
                end
                if newSave and seedCfg.keyitems then
                    local okKey, written = pcall(game.ThroneKeyRowsPatch)
                    log("throne key: " .. tostring(written) .. " squad leader rows give the stand-in" .. (okKey and "" or " (failed)"))
                end
                if newSave and seedCfg.forge then
                    local okForge, written = pcall(game.ForgePatch)
                    log("forge: " .. tostring(written) .. " rows end the forge only with all eight weapons" .. (okForge and "" or " (failed)"))
                end
                if newSave and seedCfg.gifts then
                    local okGifts, written = pcall(game.GiftsPatch, seedCfg.radar)
                    log("gifts: " .. tostring(written) .. " NPC gift rows give the stand-in" .. (okGifts and "" or " (failed)"))
                end
                if seedCfg.quests then pcall(state.prizeTick) end
                if seedCfg.quests and game.QUEST_COLORS.on then
                    local okColors, err = pcall(state.questColorsTick)
                    if not okColors then log("quest colours: failed: " .. tostring(err)) end
                end
                if newSave then
                    local okMechabo, written = pcall(game.MechaboPatch)
                    log("mechabo: " .. tostring(written) .. " rows of Verun's first step accept its quest" .. (okMechabo and "" or " (failed)"))
                end
                -- In open-world seeds, one Antlion defeat permanently clears the sandpit path between Kol and Grandport.
                if newSave then
                    local okAntlion, written = pcall(game.AntlionPatch)
                    log("antlion: " .. tostring(written) .. " win choices set to clear the sandpit" .. (okAntlion and "" or " (failed)"))
                end
                -- Again on each way into the tower, in case the game loaded the skill table again.
                local inTower = game.CurrentMap() == game.BEHEMOTH.map
                if ours and (newSave or (inTower and not state.inTower)) then
                    local okBehemoth, written = pcall(game.BehemothPatch)
                    log("behemoth: " .. tostring(written) .. " assist hits set to 1 damage" .. (okBehemoth and "" or " (failed)"))
                end
                state.inTower = inTower
                if newSave and bossTest.group then pcall(bossTest.arm, bossTest.group, bossTest.quiet) end
                if okShop and blocked ~= nil then
                    log("vision shop " .. (blocked and "closed (no vision yet)" or "open") .. ": " .. tostring(rows) .. " rows")
                end
            end
            -- Chests and shinies are still recorded in seen.tsv for any save; scanLoot reports
            -- them only for the session's save (see opened).
            state.mark("loot")
            if state.ticks % CHEST_EVERY == 0 then scanLoot() end
            -- Crystal checks report by the flag set when their event finishes.
            if seedCfg.crystals and sessionSave() and state.ticks % CHEST_EVERY == 0 then
                for _, c in ipairs(game.CRYSTALS) do
                    if game.GetFlag(c.flag) == true and report("check", "crystal:" .. c.map) then
                        log("check crystal:" .. c.map)
                    end
                end
            end
            state.mark("bosses")
            if state.ticks % CHEST_EVERY == 0 then scanBosses() end
            if state.ticks % PRIME_EVERY == 0 then pcall(game.PrimePopup) end
            if sessionSave() then
                state.mark("items")
                applyItems()
                if state.seed and save.ok then
                    local okStamp, err = pcall(save.writeStamp, state.ticks % LOCKS_EVERY == 0)
                    if not okStamp then log("stamp: " .. tostring(err)) end
                end
                state.mark("story")
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
    if os.clock() - state.perf.since >= state.perf.every then
        for _, line in ipairs(state.perfLines()) do log(line) end
    end
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

-- Dump every field of the loaded save to snap_<name>.tsv for comparison via tools/snapdiff.py.
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

-- Dump functions of core save, event, and new-game classes to functions.txt.
local FUNCTION_CLASSES = {
    "CPP_BFL_SaveData", "CPP_BFL_SaveDataProgress", "CPP_BFL_SaveDataParty", "CPP_BFL_SaveDataUnit",
    "CPP_BFL_SaveDataInventory", "CPP_BFL_SaveDataMap", "CPP_BFL_SaveData_PerMap",
    "CPP_BFL_SaveDataPlayer", "CPP_BFL_DBG_FlagSaveData", "CPP_BFL_Scenario", "CPP_ScenarioSubsystem",
    "CPP_DM_EventShortcutData", "CPP_DM_SaveDataManager", "CPP_DM_BFL_SaveData", "CPP_Task_NewGame",
    "CPP_MuchaSaveDataManager", "CPP_MuchaGameSaveData",
    "CPP_BFL_Chat", "CPP_ChatSubsystem", "CPP_QuestSubsystem", "CPP_VM_QuestNotice",
}

-- ffrap_title [list|add|refuse <type|off>]: inspect title menu entries or manually add the
-- Archipelago entry. `refuse` sets what the entry becomes with no live client (round 116: Load
-- Game; another type is a test), or `off` lets it start with none. Not kept.
command("ffrap_title", function(p)
    local what = (p and p[1]) or "list"
    if what == "refuse" then
        if p[2] == "off" then state.refuseAs = false else state.refuseAs = tonumber(p[2]) end
        local text = state.refuseAs == false and "off: the entry starts a game with no client"
            or "becomes entry " .. tostring(state.refuseAs or game.TITLE_LOAD_GAME) .. " with no client"
        log("title: refuse " .. text)
        notify("Title entry: " .. text)
        return
    end
    if what == "add" then
        local ok, detail = game.AddTitleEntry(not game.InGame())
        log("title: add: " .. tostring(detail))
        local hooked = hookTitle()
        notify("Title entry: " .. tostring(detail) .. (hooked and "" or "; the choice hook failed (see the log)"))
    end
    local entries = game.TitleEntries()
    log("title: " .. entries)
    if what ~= "add" then notify("Title menu: " .. entries) end
end)

-- ffrap_logo: manually place the Archipelago logo on the title screen line.
command("ffrap_logo", function()
    local result, detail = game.TitleLogo(LOGO_PATH, TITLE_LINE)
    log("logo: " .. tostring(result) .. ": " .. tostring(detail))
    notify("Logo: " .. tostring(result or "not added") .. " (" .. tostring(detail) .. ")")
end)

-- ffrap_feed [on|off|test [plain]|check]: the item feed on the field HUD (on by default).
-- `test` shows three sample lines, logging each step first; `test plain` leaves out the
-- styling; `check` logs what the engine says about the feed's box and lines.
command("ffrap_feed", function(p)
    local what = p and p[1]
    if what == "on" or what == "off" then
        feedOn = what == "on"
        saveState()
        log("feed: " .. what)
        game.Toast("Item feed " .. what)
    elseif what == "test" then
        -- Log each step before running so any engine crash points to the last `feed step:` in UE4SS.log.
        local plain = p[2] == "plain"
        log("feed test" .. (plain and " (plain)" or "") .. ": starting")
        game.feedTrace = function(step) log("feed step: " .. step) end
        local results = {}
        for _, msg in ipairs({ "Received Potion from Bob", "Sent Ether to Alice", "Received Rod of Focus" }) do
            local ok, why = game.FeedLine(msg, feedClock, { plain = plain })
            results[#results + 1] = ok and "ok" or tostring(why)
        end
        game.feedTrace = nil
        log("feed test: " .. table.concat(results, ", "))
    elseif what == "check" then
        for _, line in ipairs(game.FeedReport()) do log("feed check: " .. line) end
        game.Toast("Feed check written to the log")
    elseif what == "colors" then
        -- The item's name in its Archipelago colour, on by default since round 91; `on` shows test lines.
        if p[2] == "on" or p[2] == "off" then game.feedColors = p[2] == "on" end
        log("feed: colours " .. (game.feedColors and "on" or "off"))
        if game.feedColors then
            game.feedTrace = function(step) log("feed step: " .. step) end
            local results = {}
            for _, t in ipairs({ { "Received Potion", "Potion", 0 }, { "Received Hookshot from Alice", "Hookshot", 1 },
                                 { "Sent Ether to Alice", "Ether", 2 }, { "Received Bomb Trap", "Bomb Trap", 4 } }) do
                local ok, why = game.FeedLine(t[1], feedClock, { span = { text = t[2], flags = t[3] } })
                results[#results + 1] = ok and "ok" or tostring(why)
            end
            game.feedTrace = nil
            log("feed colours test: " .. table.concat(results, ", "))
        end
    else
        notify("Item feed is " .. (feedOn and "on" or "off") .. " (ffrap_feed on|off|test|colors on|off)")
    end
end)

-- Round 91 (the user: item names in their colour in the chest pop-up and the Quests screen).
-- The pop-up's colours are on by default since round 92; the Quests screen's are a probe, off at
-- each start. `on` also logs each step of the next coloured line.
--   ffrap_popup colors on|off   the pop-up's name line as our own coloured row
--   ffrap_quest colors on|off   the Quests screen's Rewards, the same way
command("ffrap_popup", function(p)
    local P = game.POPUP_COLORS
    if p and p[1] == "colors" and (p[2] == "on" or p[2] == "off") then
        P.on = p[2] == "on"
        P.trace = P.on and function(step) log("popup step: " .. step) end or nil
        notify("Pop-up colours: " .. p[2])
    else
        notify("Usage: ffrap_popup colors on | off")
    end
end)
-- ffrap_quest colors on|off: the Quests screen's colours (on by default since round 96); `on`
-- also logs every line and the steps of the next one coloured. ffrap_quest instant on|off: colour
-- each line as the game writes it, by a hook on its SetText (on by default since round 97).
command("ffrap_quest", function(p)
    local Q = game.QUEST_COLORS
    local on = p and (p[2] == "on" or p[2] == "off") and p[2] == "on"
    if p and p[1] == "colors" and on ~= nil then
        Q.on, state.questVerbose = on, on
        Q.trace = on and function(step) log("quest step: " .. step) end or nil
        if not on then
            for _, line in ipairs(game.QuestRewardColors({})) do log("quest colours: " .. line) end
        end
        notify("Quest reward colours: " .. p[2])
    elseif p and p[1] == "instant" and on ~= nil then
        Q.instant = on
        Q.trace = on and function(step) log("quest step: " .. step) end or Q.trace
        notify("Quest reward colours at once: " .. p[2] .. (on and " (open the Quests screen)" or ""))
    else
        notify("Usage: ffrap_quest colors on | off, or ffrap_quest instant on | off")
    end
end)

-- ffrap_openstart [on|off|dock|air|event|at <x> <y> <z>|now [slot]]: configure whether prologue skip
-- jumps to the open-world start (game.OPEN_START). `dock`, `air`, and `event` select arrival points
-- (game.OPEN_STARTS; `air` is default); `at` overrides coordinates for the current run only.
-- `now` writes the open world start into the loaded save (one that has had the skip), saves it
-- to its slot (or `slot`) and reloads, with no new game.
-- ffrap_newstart [on|off]: the new start (round 109). With no argument, says whether it is on.
command("ffrap_newstart", function(p)
    local what = p and p[1]
    if what == "on" or what == "off" then
        state.newStartOn = what == "on"
        saveState()
    elseif what ~= nil then
        notify("Usage: ffrap_newstart [on|off]")
        return
    end
    local on = state.newStartOn ~= false
    notify("New start is " .. (on and "on" or "off")
        .. ": New Game (Archipelago) " .. (on and "begins at the open world start, with no prologue"
        or "plays the opening and skips the prologue after the first autosave"))
end)

command("ffrap_openstart", function(p)
    local what = p and p[1]
    if what == "now" then
        local slot = tonumber(p[2]) or save.slot
        if not game.InGame() or not slot then
            notify("Load a save first (or give a slot: ffrap_openstart now <slot>)")
            return
        end
        local ok, report = game.OpenStart()
        for _, line in ipairs(report) do log("openstart: " .. line) end
        if not ok then
            notify("Open world start failed (see the log); nothing saved")
            return
        end
        -- As in runSkip: the reload makes a new save object, so a linked session keeps the slot.
        if state.seed and save.ok then
            linkSlot(slot, state.applied)
            saveState()
        end
        local _, detail = game.SaveAndReload(slot, game.OPEN_START.map)
        notify("Open world start: " .. detail)
        return
    elseif what == "on" or what == "off" then
        openStart = what == "on"
        saveState()
    elseif game.OPEN_STARTS[what] then
        game.OPEN_START = game.OPEN_STARTS[what]
        openArrival = what
        saveState()
    elseif what == "at" then
        local x, y, z = tonumber(p[2]), tonumber(p[3]), tonumber(p[4])
        if not (x and y and z) then
            notify("Usage: ffrap_openstart at <x> <y> <z>")
            return
        end
        game.OPEN_START.x, game.OPEN_START.y, game.OPEN_START.z = x, y, z
    end
    local a = game.OPEN_START
    notify(string.format("Open world start is %s (%s): story %d, map %d at %s, %s, %s (ffrap_openstart on|off|dock|air|event|at x y z|now)",
        openStart and "on" or "off", a.name, a.story, a.map, a.x, a.y, a.z))
end)

-- ffrap_layout <text>: log the widget panel hierarchy containing <text>.
command("ffrap_layout", function(p)
    local text = table.concat(p or {}, " ")
    if text == "" then
        notify("Usage: ffrap_layout <part of some text on screen>")
        return
    end
    local chain = game.LayoutOf(text)
    if not chain then
        notify("No text on screen holds \"" .. text .. "\"")
        return
    end
    for i, line in ipairs(chain) do log("layout " .. i .. ": " .. line) end
    notify("Layout of \"" .. text .. "\": " .. #chain .. " levels in the log")
end)

-- The Archipelago page (IDEAS.md idea 38): an entry in the main menu, before System, that opens a
-- window with the seed's state. It is kept in the menu every tick (game.APMENU.Ensure), and the
-- page is filled while it is open. ffrap_apmenu:
--   off | on   stop adding the entry for this run (it stays in the menu until a restart) / add it again
--   state      the page's screens (activated, visible, opacity, open/close flags) and the menu's scene stack
--   close      when Back does nothing: ask the page to close as Back does, or pop the menu's scene
--   tree       the open page, widget by widget, to ffrap_apmenu.txt
--   options | text   round 85 probe (IDEAS.md idea 39): the entry opens the game's Options screen,
--              with the view models and input contexts the game gives it / the page again
--   tabs [only | all]   the Options screen's tabs: list them / leave out all but Gameplay / put them back
--   mode ap | game   round 86 probe: the Options screen as our page (one Archipelago tab, the game's
--              rows hidden, a heading per page line), and the main menu's SetScene calls logged / back
-- state.apMenu is the entry's state while it is on: its steps are logged until it is first in the
-- menu, and each reason it cannot be yet is logged once.
state.apMenu = {}
-- Round 87: the entry opens the Options screen, and the tables are our page only while the menu
-- is on our scene, so System > Options stays the game's own. The root entry's click calls
-- CPP_MainMenuSubsystem:SetScene(tag, option) from Blueprint: a pre-hook sees our tag before our
-- screen opens and reads the tables (round 86). The tick puts them back once the menu has left
-- our scene, or when it never showed it.
state.quietly = function() end
-- Round 88: our setting rows are in the table only while the page is open (the user: not on the
-- title screen), so they are added here, into whichever copy of the table the game has now.
state.apMenuWrite = function(say)
    local added, why = game.EnsureOptionRows(state.currentSettings())
    if added == nil then log("apmenu: setting rows: " .. tostring(why)) end
    return game.APMENU.Mode("ap", state.apMenuPage(), say)
end
state.apMenuScene = function(name)
    local m, A = state.apMenu, game.APMENU
    if state.apMenuWatch then log("apmenu: SetScene " .. tostring(name)) end
    if not m or A.screen ~= "options" then return end
    if name == A.TAG then
        local lines = state.apMenuWrite(m.modeTold and state.quietly or log)
        if not m.modeTold then log("apmenu: " .. lines[#lines]) end
        m.modeTold, m.modeAt, m.seenOurs, m.rewriteTold = true, state.ticks, false, false
    elseif A.modeSaved then
        A.Mode("game", {}, state.quietly)
    end
end
state.apMenuHook = function()
    if state.apMenuHooked ~= nil then return end
    state.apMenuHooked = pcall(RegisterHook, "/Script/mucha.CPP_MainMenuSubsystem:SetScene", function(_, tag)
        local name
        pcall(function() name = tag:get().TagName:ToString() end)
        local ok, err = pcall(state.apMenuScene, name)
        if not ok then log("apmenu: SetScene hook failed: " .. tostring(err)) end
    end)
    log("apmenu: SetScene hook " .. (state.apMenuHooked and "registered" or "could not be registered"))
end
state.apMenuBack = function(m, A)
    local MODE_GRACE_TICKS = 6   -- 3 s for the menu to show our scene after SetScene
    if not A.modeSaved then return end
    if A.SceneTop() == A.TAG then
        m.seenOurs = true
        -- Round 88: the first open showed the game's rows. The game had loaded the table again
        -- after the hook wrote it.
        if not A.Written() then
            local lines = state.apMenuWrite(state.quietly)
            if not m.rewriteTold then
                log("apmenu: the Options tables were loaded again with the page open; " .. lines[#lines])
                m.rewriteTold = true
            end
        end
    elseif m.seenOurs or state.ticks - (m.modeAt or 0) > MODE_GRACE_TICKS then
        if not m.seenOurs then log("apmenu: the main menu never showed our scene; the Options tables put back") end
        A.Mode("game", {}, state.quietly)
        m.seenOurs = false
    end
end
state.apMenuTick = function()
    local m = state.apMenu
    local A = game.APMENU
    state.apMenuHook()
    state.apMenuBack(m, A)
    if save.vanilla() then
        if A.Unlist() then log("apmenu: taken out of the menu (a save not linked to the seed)") end
        return
    end
    local done, why = A.Ensure(not m.ready and log or nil)
    if done and not m.ready then log("apmenu: " .. done) end
    if not why and done then m.ready = true end
    if why ~= m.failed then
        if why then log("apmenu: not yet: " .. why) end
        m.failed = why
    end
    local wrote, whyPage = A.Page("Archipelago", function() return table.concat(state.apMenuPage(), "\n") end, log)
    if wrote == "written" and not m.pageShown then
        log("apmenu: page shown")
        m.pageShown = true
    end
    if not wrote and whyPage ~= "not open" and whyPage ~= m.pageFailed then log("apmenu: page: " .. whyPage) end
    m.pageFailed = whyPage
    local unstuck = A.Unstick(log)
    if unstuck then log("apmenu: " .. unstuck) end
end
-- Round 84, a player: count the shards without the princess's long talk. Round 85, the user: the
-- total collected and the chests ready to open, no more. Collected: the shards the seed has sent,
-- or held plus turned in when that is more (with include_tablet_shards off the shards are the
-- game's own pick-ups; turned in is known after a visit to the palace in this run). A chest is
-- paid for by its step's shards and opened when its check is sent.
state.palaceLines = function()
    local P = game.PALACE
    local received = 0
    for i = 0, state.applied - 1 do
        local it = state.items[i]
        if it and it.kind == "item" and it.id == P.item then received = received + it.count end
    end
    local collected = math.max(received, (game.HeldCount(P.item) or 0) + (P.turned or 0))
    local paid, opened = 0, 0
    for i, need in ipairs(P.steps) do
        if collected >= need then paid = paid + 1 end
        if state.reported["check|chest:" .. P.map .. ":" .. (i - 1)] then opened = opened + 1 end
    end
    return { "Tablet Shards: " .. collected .. " collected",
             "Oblivion Palace Chests: " .. math.max(0, paid - opened) .. " ready to open" }
end
-- The Archipelago page's lines, from what the client has sent and the loaded save.
state.apMenuPage = function()
    if not seedCfg.heard then return { "No seed yet: start the Archipelago client and connect." } end
    local lines = {}
    local goal, lock = seedCfg.goal, seedCfg.finalboss
    if goal and goal.kind == "tablet_shards" then
        lines[#lines + 1] = string.format("Goal: receive %d Tablet Shards (%d so far)", goal.needShards, goal.shards)
    elseif goal and goal.kind == "final_boss" then
        lines[#lines + 1] = "Goal: win the last battle at the top of the Crystal Tower"
    elseif goal then
        lines[#lines + 1] = "Goal: " .. goal.kind
    end
    if lock and (lock.needCharacters > 0 or lock.needVisions > 0 or lock.needFragments > 0) then
        lines[#lines + 1] = string.format("Tower: party members %d/%d, Visions %d/%d, Crystal Fragments %d/%d",
            lock.characters, lock.needCharacters, lock.visions, lock.needVisions, lock.fragments, lock.needFragments)
    end
    if seedCfg.checks then
        lines[#lines + 1] = string.format("Checks: %d of %d", seedCfg.checks.done, seedCfg.checks.total)
    end
    lines[#lines + 1] = "Items received: " .. state.applied
    for _, line in ipairs(state.palaceLines()) do lines[#lines + 1] = line end
    lines[#lines + 1] = ""
    if locksOn() then
        local open, locked = {}, {}
        for _, c in ipairs(game.CONTINENTS) do
            local name = c.name:sub(1, 1):upper() .. c.name:sub(2)
            local list = game.ContinentOpen(c.name) and open or locked
            list[#list + 1] = name
        end
        lines[#lines + 1] = "Continents open: " .. (#open > 0 and table.concat(open, ", ") or "none")
        lines[#lines + 1] = "Continents locked: " .. (#locked > 0 and table.concat(locked, ", ") or "none")
    else
        lines[#lines + 1] = "Continents: no locks"
    end
    local kinds = {}
    for _, k in ipairs({ { "shinies", "shinies" }, { "shards", "Tablet Shards" }, { "crystals", "crystals" },
                         { "bosses", "bosses" }, { "radar", "radar treasures" }, { "quests", "side quests" } }) do
        if seedCfg[k[1]] then kinds[#kinds + 1] = k[2] end
    end
    lines[#lines + 1] = "Locations: chests" .. (#kinds > 0 and ", " .. table.concat(kinds, ", ") or "")
    -- Round 109: every seed starts on foot by its continent's town; the airship waits there when
    -- the seed starts with it.
    lines[#lines + 1] = "Start: on foot" .. (seedCfg.continent and
        (" on " .. seedCfg.continent:sub(1, 1):upper() .. seedCfg.continent:sub(2)) or "")
        .. (seedCfg.airship ~= false and ", the airship beside you" or "")
        .. (seedCfg.chocobo == false and "; the Chocobo is an item" or "")
    return lines
end
command("ffrap_apmenu", function(p)
    local A = game.APMENU
    local what = tostring(p and p[1] or ""):lower()
    if what == "state" then
        local lines = A.State()
        for _, line in ipairs(lines) do log("apmenu: " .. line) end
        notify("Archipelago page state: " .. #lines .. " lines in the log")
    elseif what == "close" then
        local line = A.Close(log)
        log("apmenu: " .. line)
        notify("Archipelago page: " .. line)
    elseif what == "tree" then
        local lines = A.Tree()
        if not lines then
            notify("Open the Archipelago page first")
            return
        end
        local f = io.open(MOD_DIR .. "ffrap_apmenu.txt", "w")
        if not f then return end
        for _, line in ipairs(lines) do f:write(line, "\n") end
        f:close()
        notify("Archipelago page: " .. #lines .. " widgets in ffrap_apmenu.txt")
    elseif what == "options" or what == "text" then
        for _, line in ipairs(A.Screen(what, log)) do log("apmenu: " .. line) end
        notify("Archipelago entry opens " .. (what == "options" and "the Options screen" or "the page") ..
            " (close the main menu and open it again)")
    elseif what == "tabs" then
        local mode = tostring(p[2] or "list"):lower()
        local lines = A.Tabs(mode, log)
        for _, line in ipairs(lines) do log("apmenu: " .. line) end
        notify("Options tabs (" .. mode .. "): " .. #lines .. " lines in the log")
    elseif what == "mode" then
        local kind = tostring(p[2] or ""):lower()
        if kind ~= "ap" and kind ~= "game" then
            notify("Usage: ffrap_apmenu mode ap | game")
            return
        end
        state.apMenuWatch = kind == "ap"
        state.apMenuHook()
        local lines = kind == "ap" and state.apMenuWrite(log) or A.Mode("game", {}, log)
        for _, line in ipairs(lines) do log("apmenu: " .. line) end
        notify("Archipelago page " .. lines[#lines])
    elseif what == "split" then
        local on = tostring(p[2] or ""):lower()
        if on ~= "on" and on ~= "off" then
            notify("Usage: ffrap_apmenu split on | off")
            return
        end
        A.split = on == "on"
        if A.modeSaved then A.Mode("game", {}, log) end
        notify("Archipelago page: " .. (A.split and "two tabs" or "one tab") .. " (open it again)")
    elseif what == "seedrows" then
        local kind = tostring(p[2] or ""):lower()
        if kind ~= "command" and kind ~= "heading" then
            notify("Usage: ffrap_apmenu seedrows command | heading")
            return
        end
        A.seedRows = kind
        if A.modeSaved then A.Mode("game", {}, log) end
        notify("Archipelago page: the seed's lines as " .. kind .. " rows (open it again)")
    elseif what == "off" then
        state.apMenu = nil
        notify("Archipelago page: no longer added (restart the game to take it out of the menu)")
    elseif what == "on" then
        state.apMenu = state.apMenu or {}
        state.apMenuTick()
        notify("Archipelago page: on")
    else
        notify("Usage: ffrap_apmenu off | on | state | close | tree | options | text | tabs [only | all] | mode ap | game | split on | off | seedrows command | heading")
    end
end)

-- ffrap_notice <text>: try the game's quest-notice banner with our own text (experimental).
command("ffrap_notice", function(p)
    local text = table.concat(p or {}, " ")
    if text == "" then text = "Archipelago: test notice" end
    local ok, detail = game.QuestNotice(text)
    log("notice: " .. tostring(detail))
    if not ok then notify("Notice: " .. tostring(detail)) end
end)

-- ffrap_gate: experimental blocker and world-map walking crossing commands.
--   ffrap_gate spawn [combo|box|rock|pot|gate|world] [dist] [scale]
--   ffrap_gate item [id] [count]
--   ffrap_gate require <item|unit|flag|off> [id] [count]
--   ffrap_gate lock | unlock | clear | status
--   ffrap_gate mark <continent> <continent> [scale] [dist] | unmark | crossings
--   ffrap_gate move <dx> <dy> [dz] | turn [degrees] | size <scale>: the nearest crossing
command("ffrap_gate", function(p)
    local what = (p and p[1] and p[1]:lower()) or "status"
    local function traced(fn)
        game.gateTrace = function(step) log("gate step: " .. step) end
        local okCall, a, b = pcall(fn)
        game.gateTrace = nil
        if not okCall then error(a) end
        return a, b
    end
    if what == "spawn" then
        log("gate spawn: starting")
        local ok, detail = traced(function() return game.SpawnGate(p[2], p[3], p[4]) end)
        gateNear = false
        notify("Gate: " .. tostring(detail))
    elseif what == "item" then
        local id = tonumber(p[2]) or game.TEST_KEY_ID
        local count = tonumber(p[3]) or 1
        log("gate item: injecting " .. tostring(id))
        local ok, detail = traced(function() return game.InjectValuableItem(id) end)
        log("gate item: " .. tostring(detail))
        if not ok then
            notify("Gate item: " .. tostring(detail))
            return
        end
        local code, grantDetail = game.GrantItem(id, count)
        notify(string.format("Gate item %d: %s; grant x%d -> %s (%s)",
            id, tostring(detail), count, tostring(code), tostring(grantDetail)))
    elseif what == "require" then
        local kind = p[2] and p[2]:lower()
        if kind == "off" or kind == "none" then
            local _, detail = traced(function() return game.SetGateRequirement(nil) end)
            gateNear = false
            notify("Gate: " .. tostring(detail))
            return
        end
        local id = tonumber(p[3])
        local count = tonumber(p[4]) or 1
        if not (kind and (kind == "item" or kind == "unit" or kind == "flag") and id) then
            notify("Usage: ffrap_gate require <item|unit|flag> <id> [count]  (or: require off)")
            return
        end
        local _, detail = traced(function()
            return game.SetGateRequirement({ kind = kind, id = id, count = count })
        end)
        gateNear = false
        notify("Gate: " .. tostring(detail))
    elseif what == "lock" or what == "unlock" then
        traced(function() game.SetGateRequirement(nil) end)
        local _, detail = traced(function() return game.SetGateLock(what == "lock") end)
        gateNear = false
        notify("Gate: " .. tostring(detail))
    elseif what == "clear" then
        local n = traced(function() return game.ClearGate() end)
        gateNear = false
        notify("Gate cleared (" .. tostring(n) .. " actor(s) removed)")
    elseif what == "mark" then
        -- Place a walking crossing `dist` ahead along recent heading, turned to face the player.
        local a, b = p[2] and p[2]:lower(), p[3] and p[3]:lower()
        if not (a and b and a ~= b and game.IsContinent(a) and game.IsContinent(b)) then
            notify("Usage: ffrap_gate mark <continent> <continent> [scale] [dist]  (e.g. mark grandshelt lanzelt 2)")
            return
        end
        if game.CurrentMap() ~= game.WORLD_MAP then
            notify("Gate mark: only on the world map")
            return
        end
        local pose, why = game.PlayerPose()
        if not pose then
            notify("Gate mark: " .. tostring(why))
            return
        end
        local scale, dist = tonumber(p[4]) or 2, tonumber(p[5]) or 150
        local heading = walk.heading or math.atan(pose.fy, pose.fx)
        local c = { a = a, b = b, x = pose.x + math.cos(heading) * dist, y = pose.y + math.sin(heading) * dist, z = pose.z,
                    yaw = (math.deg(heading) + 180.0) % 360.0, scale = scale }
        crossings[#crossings + 1] = c
        writeCrossings()
        crossingHinted = c
        log(string.format("gate mark %d: %s %s at (%.0f, %.0f, %.0f) yaw %.1f scale %.2f; player at (%.0f, %.0f, %.0f)%s",
            #crossings, a, b, c.x, c.y, c.z, c.yaw, scale, pose.x, pose.y, pose.z,
            walk.heading and "" or " (no walk seen: facing the pawn's way)"))
        notify(string.format("Crossing %d marked: %s-%s, scale %.1f. It shows while either side is locked.", #crossings, a, b, scale))
    elseif what == "unmark" or what == "move" or what == "turn" or what == "size" then
        -- Modify or remove the nearest crossing (+x is north).
        local pose = game.PlayerPose()
        local at, d = nil, 1500
        for i, c in ipairs(crossings) do
            local dc = pose and math.sqrt((pose.x - c.x) ^ 2 + (pose.y - c.y) ^ 2) or math.huge
            if dc < d then at, d = i, dc end
        end
        if not at then
            notify("Gate " .. what .. ": no crossing within 1500")
            return
        end
        local c = crossings[at]
        if what == "unmark" then
            table.remove(crossings, at)
        elseif what == "move" then
            c.x, c.y, c.z = c.x + (tonumber(p[2]) or 0), c.y + (tonumber(p[3]) or 0), c.z + (tonumber(p[4]) or 0)
        elseif what == "turn" then
            c.yaw = (c.yaw + (tonumber(p[2]) or 90)) % 360.0
        else
            c.scale = tonumber(p[2]) or c.scale
        end
        writeCrossings()
        game.CrossingClear()
        local line = string.format("%s %s at (%.0f, %.0f, %.0f) yaw %.1f scale %.2f, %.0f away; %d crossings",
            c.a, c.b, c.x, c.y, c.z, c.yaw, c.scale, d, #crossings)
        log("gate " .. what .. ": " .. line)
        notify("Crossing " .. (what == "unmark" and "removed: " or "changed: ") .. line)
    elseif what == "crossings" then
        local pose = game.PlayerPose()
        for i, c in ipairs(crossings) do
            local d = pose and math.sqrt((pose.x - c.x) ^ 2 + (pose.y - c.y) ^ 2) or -1
            log(string.format("crossing %d: %s %s at (%.0f, %.0f, %.0f) yaw %.1f scale %.2f, %.0f away, %s",
                i, c.a, c.b, c.x, c.y, c.z, c.yaw, c.scale, d,
                (game.ContinentOpen(c.a) and game.ContinentOpen(c.b)) and "open" or "closed"))
        end
        notify(#crossings .. " crossings marked (listed in the log)")
    else
        local pose, why = game.PlayerPose()
        if pose then
            log(string.format("gate status: map %s, pawn %s at (%.1f, %.1f, %.1f) yaw %.1f scale %.2f",
                tostring(game.CurrentMap()), pose.class, pose.x, pose.y, pose.z, pose.yaw, pose.sx))
        else
            log("gate status: no pawn (" .. tostring(why) .. ")")
        end
        local info = game.PollGate()
        if not info or info.gone then
            notify("Gate: none active (ffrap_gate spawn | item | require | lock | unlock | clear)")
            return
        end
        local msg = string.format("Gate (%s): %s at (%.0f, %.0f, %.0f), dist %.0f%s",
            tostring(info.kind), info.locked and "locked" or "unlocked",
            info.x, info.y, info.z, info.dist or -1,
            info.condText and (", req " .. info.condText) or "")
        notify(msg)
    end
end)

-- ffrap_inspect <class or path>: one object's fields and functions to inspect_<name>.tsv.
command("ffrap_inspect", function(p)
    local target = p and p[1]
    if not target then
        notify("Usage: ffrap_inspect <class name or object path> [label]")
        return
    end
    -- Optional label keeps two snapshots of the same object apart (e.g. locked vs normal input).
    local name = target:gsub("^.*[/.]", ""):gsub("[^%w_%-]", "") .. (p[2] and ("_" .. p[2]:gsub("[^%w_%-]", "")) or "")
    local f = io.open(MOD_DIR .. "inspect_" .. name .. ".tsv", "w")
    if not f then
        notify("Could not write inspect_" .. name .. ".tsv")
        return
    end
    local lines = 0
    local ok = game.Inspect(target, function(key, value)
        f:write(key, "\t", (tostring(value):gsub("[\t\r\n]", " ")), "\n")
        lines = lines + 1
    end)
    f:close()
    notify(ok and ("inspect_" .. name .. ".tsv: " .. lines .. " lines") or ("Nothing found for " .. target))
end)

-- ffrap_find <text>: every game class with a function or field whose name holds the text.
command("ffrap_find", function(p)
    local text = p and p[1]
    if not text then
        notify("Usage: ffrap_find <part of a function or field name>")
        return
    end
    local name = text:gsub("[^%w_%-]", "")
    local f = io.open(MOD_DIR .. "find_" .. name .. ".txt", "w")
    if not f then
        notify("Could not write find_" .. name .. ".txt")
        return
    end
    local n = game.FindNames(text, function(line) f:write(line, "\n") end)
    f:close()
    notify("find_" .. name .. ".txt: " .. n .. " matches")
end)

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

-- Enemy level/stat scaling commands (non-persistent; reset on game restart).
--
-- ffrap_scale 30: every enemy at level 30. ffrap_scale 10 20: each enemy's own level, clamped
-- to 10-20. ffrap_scale party 2: clamped to 80% of party average level +/- 2 (default).
-- ffrap_scale off: the game's own rows back. Options, in any order after the numbers:
--   at 70      party mode: centre the band on 70% of the party's level (default 80)
--   hp 70      enemy HP at 70% (default 100)
--   attack 60  enemy Attack (physical damage) at 60% (default 100)
--   magic 80   enemy Intelligence (magic damage) at 80% (default 100)
--   power 80   both attack and magic, unless one is given on its own
--   boss       change bosses too
--   follow     party mode: do it again whenever the party's level changes (on the field only)
local scaleFollow = nil   -- { range, at, knobs, withBosses, last } while "follow" is on
local scaleLast = nil     -- { mode, a, b, withBosses, knobs, text } of the rescale in force
local scaleByHand = false -- ffrap_scale was used in this run: it wins over the seed, for testing
local seedScaleOn = false -- the rescale in force came from the seed
local seedScaleFailed = false   -- so a failure is logged once

-- Every rescale writes the changed rows to scale.txt (one enemy a line), so a hit seen in
-- battle can be matched with the stats behind it.
local function applyScale(mode, a, b, withBosses, knobs, bossBand)
    local bosses = withBosses and ", with bosses" or ""
    if bossBand then
        bosses = string.format(", bosses %d to %d, hp %d%%, attack %d%%, magic %d%%", math.max(1, bossBand.a), bossBand.b,
            bossBand.knobs.hp, bossBand.knobs.attack, bossBand.knobs.magic)
    end
    log(string.format("scale: %s %s %s, hp %d%%, attack %d%%, magic %d%%%s: starting", mode, tostring(a), tostring(b),
        knobs.hp, knobs.attack, knobs.magic, bosses))
    local n, sample, lines, gameChanged = game.ScaleEnemies(mode, a, b, withBosses, knobs, bossBand)
    if n == nil then return nil, sample end
    log("scale: " .. n .. " rows changed" .. (sample and ("; " .. sample) or ""))
    if gameChanged and gameChanged > 0 then
        log("scale: something else had changed " .. gameChanged .. " rows since our last write; their new values are the base now")
    end
    if mode == "off" then scaleLast = nil
    else
        local band = mode == "fixed" and ("every enemy at level " .. tostring(a))
            or string.format("levels %s to %s", tostring(math.max(1, a)), tostring(b))
        scaleLast = { mode = mode, a = a, b = b, withBosses = withBosses, knobs = knobs, bossBand = bossBand, text = band }
    end
    if lines and #lines > 0 then
        local f = io.open(MOD_DIR .. "scale.txt", "w")
        if f then
            f:write(string.format("-- ffrap_scale %s %s %s, hp %d%%, attack %d%%, magic %d%%\n", mode, tostring(a),
                tostring(b), knobs.hp, knobs.attack, knobs.magic))
            for _, l in ipairs(lines) do f:write(l, "\n") end
            f:close()
        end
    end
    return n
end

local function scaleToParty(range, at, withBosses, knobs)
    local lv, detail = game.PartyLevel()
    if not lv then return nil, "party level unknown (" .. tostring(detail) .. ")" end
    local a, b, c = game.LevelBand(lv, range, at)
    log("scale: party level " .. lv .. " (" .. detail .. "), centre " .. c .. " (" .. at .. "%), range " .. range)
    local n, err = applyScale("clamp", a, b, withBosses, knobs)
    return n, err, lv, a, b
end

-- What is in force, as one line: the band, follow, and whether the table still holds it.
local function scaleStatus()
    if not scaleLast then return "no rescale in force (shipped enemies)" end
    local text = scaleLast.text .. (scaleFollow and (", follow on (party level " .. tostring(scaleFollow.last) .. ")") or ", follow off")
    local checked, differ, sample, reloaded = game.ScaleCheck()
    if checked == nil then return text .. "; check: " .. tostring(differ) end
    return string.format("%s; table check: %d rows, %d differ%s%s", text, checked, differ,
        sample and (" (" .. sample .. ")") or "", reloaded and ", the table is a new object (loaded again)" or "")
end

command("ffrap_scale", function(p)
    local withBosses, follow = false, false
    local set, at = { hp = 100 }, 80
    local args = {}
    local i = 1
    while i <= #p do
        local w = tostring(p[i]):lower()
        if w == "boss" then withBosses = true
        elseif w == "follow" then follow = true
        elseif (w == "at" or w == "hp" or w == "power" or w == "attack" or w == "magic") and tonumber(p[i + 1]) then
            local v = math.max(1, math.floor(tonumber(p[i + 1])))
            if w == "at" then at = v else set[w] = v end
            i = i + 1
        else args[#args + 1] = p[i] end
        i = i + 1
    end
    local knobs = { hp = set.hp, attack = set.attack or set.power or 100, magic = set.magic or set.power or 100 }
    local first = tostring(args[1]):lower()
    -- No arguments: show active scaling. "show": inspect one enemy's rows.
    if args[1] == nil and not follow and not withBosses then
        local line = scaleStatus()
        log("scale: " .. line)
        notify("Scale: " .. line)
        return
    end
    if first == "show" then
        local what = table.concat(args, " ", 2)
        log("scale: rows for \"" .. what .. "\": " .. scaleStatus())
        for _, l in ipairs(game.UnitRows(what)) do log("scale:   " .. l) end
        notify("Unit rows for \"" .. what .. "\" written to the log")
        return
    end
    scaleFollow = nil
    scaleByHand, seedScaleOn = true, false
    if first == "party" then
        local range = tonumber(args[2]) or 2
        local n, err, lv, lo, hi = scaleToParty(range, at, withBosses, knobs)
        if n == nil then
            notify("Scale failed: " .. tostring(err))
            return
        end
        if follow then
            scaleFollow = { range = range, at = at, knobs = knobs, withBosses = withBosses, last = lv }
            log("scale: follow on: the band moves when the party's level changes")
        end
        notify(string.format("Enemies rescaled to party level %d: levels %d to %d, %d rows changed%s", lv,
            math.max(1, lo), hi, n, follow and " (follow on)" or ""))
        return
    end
    local a, b = tonumber(args[1]), tonumber(args[2])
    local mode = (tostring(args[1]):lower() == "off") and "off" or (a and b and "clamp") or (a and "fixed") or nil
    if not mode then
        notify("Usage: ffrap_scale <level> | <low> <high> | party [range] | off  [at %] [hp %] [attack %] [magic %] [power %] [boss] [follow]")
        return
    end
    if mode == "clamp" and a > b then a, b = b, a end
    local n, err = applyScale(mode, a, b, withBosses, knobs)
    if n == nil then
        notify("Scale failed: " .. tostring(err))
        return
    end
    notify("Enemies " .. (mode == "off" and "back to normal" or ("rescaled, " .. scaleLast.text)) .. ": " .. n .. " rows changed")
end)

-- With "follow" on: when the party's level has changed, move the band. Only while the field HUD
-- is on screen, so never in a battle.
local SCALE_CHECK_EVERY = 2   -- scale ticks (of STATUS_EVERY) between table checks
local scaleChecks = 0

-- Player gameplay settings: EXP, gil, and MRP rates, random encounters, encounter rate, and
-- enemy scaling toggle/strength. These persist per player in settings.txt across all saves and
-- record only explicit changes via ffrap_set or the Options screen.
local SETTINGS_FILE = MOD_DIR .. "settings.txt"
local SETTING_DEFAULTS = { exp = 1, gil = 1, mrp = 1, encounters = true, encounterrate = 1, scaling = true, strength = 1 }
local SETTING_RANGES = { exp = { 0, 10 }, gil = { 0, 10 }, mrp = { 0, 10 }, encounterrate = { 0.1, 5 }, strength = { 0, 2 } }
-- Options row button labels match the game's difficulty preset names.
local STRENGTH_NAMES = { [0] = "casual", [1] = "normal", [2] = "expert" }
local settingsSet = {}   -- what the player has set
local function setting(key)
    if settingsSet[key] ~= nil then return settingsSet[key] end
    return SETTING_DEFAULTS[key]
end
do
    local f = io.open(SETTINGS_FILE, "r")
    if f then
        for line in f:lines() do
            local k, v = line:match("^(%w+)%s+(%S+)")
            if k and SETTING_DEFAULTS[k] ~= nil then
                if type(SETTING_DEFAULTS[k]) == "boolean" then settingsSet[k] = v == "on"
                elseif tonumber(v) then settingsSet[k] = tonumber(v) end
            end
        end
        f:close()
    end
end
local function writeSettings()
    local f = io.open(SETTINGS_FILE, "w")
    if not f then return false end
    for k in pairs(SETTING_DEFAULTS) do
        local v = settingsSet[k]
        if v ~= nil then f:write(k, " ", type(v) == "boolean" and (v and "on" or "off") or tostring(v), "\n") end
    end
    f:close()
    return true
end
local function settingsText()
    local parts = {}
    for _, k in ipairs({ "exp", "gil", "mrp", "encounters", "encounterrate", "scaling", "strength" }) do
        local v = setting(k)
        local text
        if k == "strength" then text = STRENGTH_NAMES[v] or tostring(v)
        elseif type(v) == "boolean" then text = v and "on" or "off"
        else text = "x" .. tostring(v) end
        parts[#parts + 1] = k .. " " .. text
    end
    return table.concat(parts, ", ")
end


local settingsLogged = nil
-- Re-apply player rate rows in fastTick (0.1 s) so they stay current against mods like FFRS_QoL
-- that overwrite DT_GameDifficultyParam every few seconds.
local defendedRates, defendLogged = nil, false
local function defendRates()
    if not defendedRates then return end
    if game.ApplyRates(defendedRates[1], defendedRates[2], defendedRates[3]) > 0 and not defendLogged then
        defendLogged = true
        log("settings: the rates had been changed and were written back (the game loaded its table again, or " ..
            "another mod such as FFRS_QoL writes the same rows); this is logged once")
    end
end
local menuLogged = nil
local function currentSettings()
    local current = {}
    for k in pairs(SETTING_DEFAULTS) do current[k] = setting(k) end
    return current
end
state.currentSettings = currentSettings
-- Since round 88 our Options rows are added only while the Archipelago page is open
-- (state.apMenuWrite), and kept there by its tick.
menuTick = function()
    if state.apMenu then pcall(state.apMenuTick) end
end
settingsTick = function()
    -- Choices set in the Options UI override ffrap_set values.
    local fromMenu = game.ReadOptionValues()
    if fromMenu then
        local parts = {}
        for k, v in pairs(fromMenu) do
            settingsSet[k] = v
            parts[#parts + 1] = k .. " " .. tostring(v)
        end
        table.sort(parts)
        local line = table.concat(parts, ", ")
        if #parts > 0 and line ~= menuLogged then
            log("settings: from the Options screen: " .. line)
            writeSettings()
        end
        menuLogged = line
    end
    local vanilla = save.vanilla()
    local value = vanilla and function(k) return SETTING_DEFAULTS[k] end or setting
    local rates = game.ApplyRates(value("exp"), value("gil"), value("mrp"))
    defendedRates = { value("exp"), value("gil"), value("mrp") }
    -- Re-apply encounter settings every pass since other mods (e.g. FFRS_QoL) also touch these rows.
    local rows, tables = game.ApplyEncounterTables(value("encounters"), value("encounterrate"))
    local players = game.ApplyPlayerEncounter(value("encounters"))
    if rates > 0 or rows > 0 or players > 0 then
        local line = string.format("settings: %s (%d rate rows, %d map rows in %d tables, %d players changed)",
            vanilla and "the game's own, for a save not linked to the seed" or settingsText(), rates, rows, tables, players)
        if line ~= settingsLogged then log(line) end
        settingsLogged = line
    end
end

-- Grant starting open-world extras (Chocobo Saddle 30002 unless `cfg chocobo 0` makes it an AP item)
-- once per loaded save, and keep Mobliz Shipyard's elevators active at each visit.
local CHOCOBO_SADDLE = 30002

-- Crystal Tower final boss seal (`cfg finalboss`): while characters, visions, or Crystal Fragments
-- are below threshold, keep the point of no return sealed (game.SealTowerTop) and notify on approach.
-- Seeds without a `cfg finalboss` line (e.g. shard goal) leave the tower open.
local lockLogged, lockMissLogged, lockNoticed = nil, false, false
local LOCK_NOTICE_NEAR, LOCK_NOTICE_AGAIN = 1200, 2500
finalLockTick = function()
    if game.CurrentMap() ~= game.TOWER_TOP.map then
        lockLogged, lockMissLogged, lockNoticed = nil, false, false
        return
    end
    local lock = seedCfg.finalboss
    local short = lock and sessionSave() and (lock.characters < lock.needCharacters or lock.visions < lock.needVisions
        or lock.fragments < lock.needFragments)
    local changed, why = game.SealTowerTop(short and true or false)
    local text = lock and string.format("characters %d/%d, visions %d/%d", lock.characters, lock.needCharacters,
        lock.visions, lock.needVisions) or "no lock for this seed"
    if lock and lock.needFragments > 0 then
        text = text .. string.format(", Crystal Fragments %d/%d", lock.fragments, lock.needFragments)
    end
    if changed == nil then
        -- Trigger only loads near the top climb, and reloads with collision enabled, so re-seal each tick.
        if not lockMissLogged then log("final boss lock: " .. tostring(why)) end
        lockMissLogged = true
    else
        local line = "final boss lock: " .. (short and "sealed" or "open") .. " (" .. text .. ")"
        if line ~= lockLogged then log(line) end
        lockLogged = line
    end
    if not short then return end
    local pose = game.PlayerPose()
    if not pose then return end
    local d = math.sqrt((pose.x - game.TOWER_TOP.x) ^ 2 + (pose.y - game.TOWER_TOP.y) ^ 2)
    if d < LOCK_NOTICE_NEAR and not lockNoticed then
        lockNoticed = true
        notify("The way to the top is sealed. You need " .. text)
    elseif d > LOCK_NOTICE_AGAIN then
        lockNoticed = false
    end
end
local saddleSave, shipyardLogged, storyBossLogged = nil, false, nil
local storyBossFieldTicks = 0
local STORY_BOSS_READY_TICKS = 2   -- seedExtrasTick runs every LOCKS_EVERY ticks: about 2 s
-- When the Airship is an item, keep its parked position at the seed's start so receiving it in
-- towns or constrained maps (like Grandport or Gronoa) does not place it somewhere unflyable.
-- Round 112 (the user's v0.31.1 run): an airship received on a Dirnado start came up near Zoldaad.
-- The save was parked at Dilmagia, so the actor the game spawned stood elsewhere, and leaving the
-- world map wrote its place back into the save. So the first time one is on the world map after it
-- came, one farther than AIRSHIP_HOME_NEAR from the start is moved there and the save parked again
-- (`watch`).
local airshipCall = { save = nil, was = false, watch = false }
local AIRSHIP_HOME_NEAR = 1000
local function parkAirshipAtStart(why)
    local home = game.FOOT_STARTS[seedCfg.continent or ""]
    if not (home and game.ParkAirship(home.x, home.y, home.z)) then return false end
    log(string.format("airship: parked at the start (%s), (%.0f, %.0f, %.0f)", why, home.x, home.y, home.z))
    return true
end

airshipItemTick = function()
    local on = game.GetFlag(game.AIRSHIP_FLAG) == true
    if airshipCall.save ~= save.obj then airshipCall.save, airshipCall.was, airshipCall.watch = save.obj, on, false end
    local came = on and not airshipCall.was
    airshipCall.was = on
    if came and parkAirshipAtStart("received") then
        airshipCall.watch = true
        notify("The airship will spawn where you started this seed. You may need to change maps for it to appear.")
    end
    local home = game.FOOT_STARTS[seedCfg.continent or ""]
    if not (airshipCall.watch and home and game.CurrentMap() == home.map and game.OnField()) then return end
    local count, moves = game.MoveAirships(home, AIRSHIP_HOME_NEAR, function(what) log("airship: " .. what) end)
    if count == 0 then return end
    airshipCall.watch = false
    log("airship: on the world map " .. (#moves > 0 and ("away from the start, moved there: " .. table.concat(moves, "; "))
        or "at the start") .. "; the save had " .. game.AirshipState())
    if #moves > 0 then parkAirshipAtStart("moved") end
end

-- Progressive Radar level comes from counting Magi-tenna (27006) items received, because the
-- game only stores one copy of a key item. Level 1 sets flag 702. The found count ({progress:51})
-- is held at the top of the level's band, which opens all of that tier's treasures at once; each
-- dig sets it lower again, and the next tick puts it back. The radar's step ({progress:49}) is
-- then set to the band's (game.RADAR_BANDS). Once every treasure of the level's tiers is found, the
-- count goes past the band (game.RADAR_QUIET) and the radar is quiet, as in the game, until the next
-- Progressive Radar. Keep state in one table for the 200-local limit.
local radar = { ITEM = 27006, logged = nil }
function radar.level()
    local n = 0
    for i = 0, state.applied - 1 do
        local it = state.items[i]
        if it and it.kind == "item" and it.id == radar.ITEM then n = n + 1 end
    end
    return n
end

function radar.tick()
    local level = radar.level()
    local band = game.RADAR_BANDS[math.min(level, #game.RADAR_BANDS)]
    local now = game.ProgressValue(game.RADAR_TIER_PROGRESS)
    local found = game.ProgressValue(game.RADAR_FOUND_PROGRESS)
    local quiet = band ~= nil
    for _, point in ipairs(game.RADAR) do
        if point.tier <= level and game.GetFlag(point.flag) ~= true then quiet = false end
    end
    if band then
        if game.GetFlag(game.RADAR_ON_FLAG) == false then game.SetFlag(game.RADAR_ON_FLAG, true) end
        local want = quiet and band.upTo + game.RADAR_QUIET or band.upTo
        if found ~= want then found = game.SetProgressValue(game.RADAR_FOUND_PROGRESS, want) end
        local inBand = false
        for _, step in ipairs(band.steps) do inBand = inBand or now == step end
        if not inBand then now = game.SetProgressValue(game.RADAR_TIER_PROGRESS, band.steps[1]) end
    end
    local line = string.format("radar: level %d (flag %d %s, step %s, found %s)%s", level, game.RADAR_ON_FLAG,
        tostring(game.GetFlag(game.RADAR_ON_FLAG)), tostring(now), tostring(found),
        quiet and ", every treasure it can find is dug: quiet" or "")
    if line ~= radar.logged then log(line) end
    radar.logged = line
end

-- Round 105: Aileen's forge (game.FORGE). Location n is the nth weapon forged. A forged weapon
-- stays in the bag, so the count comes from the save, on any computer. The forge's flag comes on
-- before its pop-up, so the pop-up names location `last + 1`, and the flag goes off again for the
-- next forge. The game may keep one Adamantite at most, as it does the radar's parts, so while the
-- Adamantite received outnumber the weapons forged, an empty bag gets one back.
state.forge = {}
function state.forge.tick()
    local F, me = game.FORGE, state.forge
    if me.save ~= save.obj then me.save, me.last, me.logged = save.obj, nil, nil end
    local forged = 0
    for _, id in ipairs(F.weapons) do
        if (game.HeldCount(id) or 0) >= 1 then forged = forged + 1 end
    end
    if game.GetFlag(F.flag) == true then
        game.SetFlag(F.flag, false)
        local key = me.last and me.last < #F.weapons and ("forge:" .. (me.last + 1))
        local s = key and state.scouts[key]
        if s then popup = { text = popupText(s), span = { text = s.item, flags = s.flags }, key = key, tries = BOSS_POPUP_TRIES } end
    end
    for n = 1, forged do
        if report("check", "forge:" .. n) then log("check forge:" .. n) end
    end
    me.last = forged
    local received = 0
    for i = 0, state.applied - 1 do
        local it = state.items[i]
        if it and it.kind == "item" and it.id == F.adamantite then received = received + 1 end
    end
    local held = game.HeldCount(F.adamantite)
    local line = string.format("forge: %d weapons forged, %d Adamantite received, %s held", forged, received, tostring(held))
    if line ~= me.logged then log(line) end
    me.logged = line
    if held == 0 and received > forged and game.OnField() then
        local code, detail = game.GrantItem(F.adamantite, 1)
        log("forge: an Adamantite given back (" .. tostring(code) .. ", " .. tostring(detail) .. ")")
    end
end

seedExtrasTick = function()
    local seedSave = seedCfg.openworld and sessionSave() and (game.StoryCounter() or 0) >= game.OPEN_START.story
    if seedSave and seedCfg.chocobo ~= false and saddleSave ~= save.obj and game.OnField() then
        saddleSave = save.obj
        if (game.HeldCount(CHOCOBO_SADDLE) or 0) == 0 then
            local code, detail = game.GrantItem(CHOCOBO_SADDLE, 1)
            log("chocobo: saddle given (" .. tostring(code) .. ", " .. tostring(detail) .. ")")
        end
    end
    pcall(finalLockTick)
    if seedSave and seedCfg.airship == false then pcall(airshipItemTick) end
    -- Round 117 (the user): since round 109 a seed with the airship starts beside the town with the
    -- airship parked there, and no start marks it visited, so the Map screen showed it grey.
    if seedSave and (seedCfg.airship ~= false or game.GetFlag(game.AIRSHIP_FLAG) == true) then
        local marked = game.MarkVisited(game.AIRSHIP_MAPS)
        if marked and #marked > 0 then log("airship: maps " .. table.concat(marked, ", ") .. " marked visited, for fast travel") end
    end
    state.mark("extras: travel")
    local travel = game.DungeonFastTravel(seedSave and true or false)
    if travel then log("fast travel: " .. travel) end
    state.mark("extras: radar, forge")
    if seedSave and seedCfg.radar and sessionSave() then pcall(radar.tick) end
    if seedSave and seedCfg.forge then pcall(state.forge.tick) end
    state.mark("extras: key items")
    if seedSave and seedCfg.keyitems and game.CurrentMap() == game.THRONE_KEY.map then
        local ok, n = pcall(game.ThroneKeyTriggerOff)
        if ok and n > 0 then log("throne key: the squad leader's trigger turned off (" .. n .. ")") end
    end
    if seedSave and seedCfg.keyitems and game.CurrentMap() == game.CABIN_KEY.map then
        local ok, n = pcall(game.CabinKeyManOff)
        if ok and n > 0 then log("cabin key: the man by Sian's inn no longer gives it (" .. n .. ")") end
    end
    -- Round 108: with the key items not shuffled, the game's own Dungeon Key never comes (game.DUNGEON_KEY).
    local K = game.DUNGEON_KEY
    if seedSave and seedCfg.keyitems == false and game.CurrentMap() == K.map and game.OnField()
        and game.HeldCount(K.item) == 0 then
        local code, detail = game.GrantItem(K.item, 1)
        log("dungeon key: given in Zoldaad Dungeon, as its soldier never comes (" .. tostring(code) .. ", " .. tostring(detail) .. ")")
    end
    state.mark("extras: unvisit")
    -- Round 117 (the user): a place counts for fast travel once the player stood in it with the
    -- field up for two passes (about 2 s), not when a scene took them through it. The list is the
    -- session's (ap_state.txt); a session's first pass takes what the save has visited already.
    if seedSave then
        if not state.walked then
            state.walked = {}
            local before = game.VisitedMaps()
            for _, map in ipairs(before) do state.walked[map] = true end
            log("fast travel: " .. #before .. " places visited already count as walked in")
            saveState()
        end
        local now = game.OnField() and game.CurrentMap() or nil
        if now and now == state.walkMap and game.CONTINENT_OF[now] and not state.walked[now] then
            state.walked[now] = true
            saveState()
            log("fast travel: map " .. now .. " walked in")
        end
        state.walkMap = now
        local ok, cleared = pcall(game.UnvisitLocked, state.walked)
        if ok and #cleared > 0 then
            log("fast travel: maps " .. table.concat(cleared, ", ") .. " not walked in or on locked continents, marked never seen")
        end
    end
    if seedSave and state.moogleSave ~= save.obj then
        state.moogleSave = save.obj
        for _, flag in ipairs(game.VISION_MOOGLE_FLAGS) do
            if game.GetFlag(flag) == false then
                local code, detail = game.SetFlag(flag, true)
                log("vision moogle: flag " .. flag .. " set, for Grandport's Moogle and no Grandport scene ("
                    .. tostring(code) .. ", " .. tostring(detail) .. ")")
            end
        end
    end
    if seedSave and game.ProgressValue(game.RADAR_TIER_PROGRESS) == 0 then
        game.SetProgressValue(game.RADAR_TIER_PROGRESS, game.RADAR_LID_HEARD)
        log("radar: step " .. game.RADAR_TIER_PROGRESS .. " set to " .. game.RADAR_LID_HEARD .. " (Lid's Mysidia line skipped)")
    end
    state.mark("extras: palace")
    if seedSave then
        local ok, line = pcall(game.PalaceSync)
        if ok and line then log(line) end
    end
    state.mark("extras: mechabo")
    if seedSave and game.ProgressValue(game.MECHABO.counter) == 0 then
        game.SetProgressValue(game.MECHABO.counter, game.MECHABO.start)
        log("mechabo: progress " .. game.MECHABO.counter .. " set to " .. game.MECHABO.start .. " (Verun's repair request)")
    end
    if seedSave then
        local M = game.MECHABO
        local ordered = game.OrderRequestQuests(M.requests)
        if #ordered > 0 then log("mechabo: board quests " .. table.concat(ordered, ", ") .. " ordered, so their kills count") end
        local has = game.UnitHasSkill(M.lid, M.tackle)
        local states, quests = game.RequestStates(M.requests), {}
        for _, id in ipairs(M.requests) do quests[#quests + 1] = "quest " .. id .. " " .. states[id] end
        local line = string.format("mechabo: progress %d at %s, flag %d %s, %s, board quest %d %s, Lid %s Mechabo Tackle",
            M.counter, tostring(game.ProgressValue(M.counter)), M.delivered, game.GetFlag(M.delivered) and "on" or "off",
            table.concat(quests, ", "), M.hunt, game.BoardQuest(M.hunt),
            has == nil and "not in the save, so no" or (has and "has" or "has no"))
        if line ~= state.mechaboLine then log(line) end
        state.mechaboLine = line
    end
    state.mark("extras: rides")
    if seedSave and game.CurrentMap() == game.SHIPYARD_MAP then
        local woke = game.WakeShipyardElevators()
        if woke > 0 and not shipyardLogged then log("shipyard: " .. woke .. " stopped elevators turned on") end
        shipyardLogged = shipyardLogged or woke > 0
    else
        shipyardLogged = false
    end
    -- Rounds 113 and 114: lifts and rafts back as on a first visit on the other maps, once per map;
    -- on their map, the lifts' live stops and the last raft whenever they change.
    local here = game.CurrentMap()
    if seedSave and here and (here ~= state.liftMap or save.obj ~= state.liftSave) then
        state.liftMap, state.liftSave, state.liftLine = here, save.obj, nil
        local moved = game.ResetRides(here)
        if #moved > 0 then log("rides: back as on a first visit: " .. table.concat(moved, ", ")) end
    end
    if seedSave and here and game.OnField() then
        local line = game.RideState(here)
        if line and line ~= state.liftLine then log("rides on map " .. here .. ": " .. line) end
        state.liftLine = line or state.liftLine
    end
    local KB = game.KOLOBOS_BRIDGE
    if seedSave and here and here ~= KB.map and game.GetFlag(KB.fell) == true and game.GetFlag(KB.fixed) == false then
        local code, detail = game.SetFlag(KB.fixed, true)
        log("kolobos: the fallen floor put back, flag " .. KB.fixed .. " (" .. tostring(code) .. ", " .. tostring(detail) .. ")")
    end
    state.mark("extras: story boss")
    local onBossMap = false
    if seedSave and seedCfg.bosses and game.OnField() and game.SyncStoryBossTrigger then
        local ok, detail = game.SyncStoryBossTrigger()
        if ok and detail ~= storyBossLogged then log("story boss: " .. detail) end
        storyBossLogged = ok and detail or nil
        onBossMap = ok == true
    else
        storyBossLogged = nil
    end
    -- The fight can start only after the field has been up for STORY_BOSS_READY_TICKS, so the
    -- party coming back from the fight does not set it off again before the win row runs.
    storyBossFieldTicks = onBossMap and storyBossFieldTicks + 1 or 0
    if seedSave and seedCfg.bosses then
        game.SetStoryBossReady(storyBossFieldTicks >= STORY_BOSS_READY_TICKS)
    end
end

-- ffrap_set: shows the settings. ffrap_set <exp|gil|mrp|encounterrate> <number>, ffrap_set
-- <encounters|scaling> <on|off>, ffrap_set strength <casual|normal|expert>, ffrap_set reset: all
-- back to the defaults.
command("ffrap_set", function(p)
    local key, value = tostring(p[1] or ""):lower(), tostring(p[2] or ""):lower()
    if key == "strength" then
        for n, name in pairs(STRENGTH_NAMES) do
            if value == name then value = tostring(n) end
        end
    end
    if key == "reset" then
        settingsSet = {}
        writeSettings()
    elseif key ~= "" then
        local default = SETTING_DEFAULTS[key]
        if default == nil then
            notify("Usage: ffrap_set [exp|gil|mrp|encounterrate <number>] [encounters|scaling <on|off>] [strength casual|normal|expert] [reset]")
            return
        end
        if type(default) == "boolean" then
            if value ~= "on" and value ~= "off" then
                notify(key .. " is on or off")
                return
            end
            settingsSet[key] = value == "on"
        else
            local n, range = tonumber(value), SETTING_RANGES[key]
            if not n then
                notify(key .. " is a number from " .. range[1] .. " to " .. range[2])
                return
            end
            n = math.min(range[2], math.max(range[1], n))
            if key == "strength" then n = math.floor(n + 0.5) end
            settingsSet[key] = n
        end
        writeSettings()
    end
    log("settings: " .. settingsText())
    notify("Settings: " .. settingsText())
end)

-- ffrap_menu add: insert our settings rows at the end of the Options screen's Gameplay tab.
command("ffrap_menu", function(p)
    local what = tostring(p[1] or ""):lower()
    if what == "dump" then
        for _, line in ipairs(game.OptionDump()) do log("menu dump: " .. line) end
        notify("Menu dump written to the log")
        return
    end
    if what ~= "add" then
        notify("Usage: ffrap_menu add | dump")
        return
    end
    local ok, detail = game.AddOptionRows(log, currentSettings())
    log("menu: " .. (ok and "" or "failed: ") .. tostring(detail))
    notify("Menu: " .. tostring(detail) .. ". Open Options, Gameplay now.")
end)

-- Automatic enemy scaling for open-world seeds (waits until after prologue so the prologue party
-- does not skew level, and restores vanilla enemies on non-seed saves).
-- Each pair ramps from party level 5 to 25. `at` is the enemies' level centre as a % of the party's
-- level; `hp` and `attack` (Attack and Intelligence) are % of the curve's stats. These stack with
-- the game's own difficulty multipliers. Enemies clamp [1 under, `above` over] the centre; bosses
-- stay +/- 2.
-- Round 101: every strength came down one step, and enemies lose more HP than Attack. A vanilla
-- run felt much softer than Normal: Normal's enemies sat at the party's level with 115% power,
-- and the enemies of regions ahead (half the map) at +3 with 1.5x HP. Hallway fights were long,
-- and the fights are mostly there for MRP. Expert is the old Normal with 10% less HP.
local SEED_SCALES = {
    [0] = { at = { 80, 88 }, hp = { 60, 75 }, attack = { 75, 90 }, above = 1, bossAt = { 95, 100 }, bossPower = { 90, 100 } },
    [1] = { at = { 85, 92 }, hp = { 70, 85 }, attack = { 85, 100 }, above = 1, bossAt = { 100, 103 }, bossPower = { 100, 105 } },
    [2] = { at = { 90, 100 }, hp = { 80, 105 }, attack = { 90, 115 }, above = 3, bossAt = { 105, 110 }, bossPower = { 105, 110 } },
}
-- Round 77: bosses lose `emptySlotCut` % power for each empty slot of the `slots` in the party.
-- Small parties were wiped by bosses' opening attacks and ran short of turns.
-- Round 100: above party level `slowFrom`, the level the bands are taken from grows `slowRate` of
-- a level for each party level. The enemy curve grows faster than the party: from level 40 to 60
-- a player's Attack grows x1.4, a curve enemy's x2.05, its HP x6.9. On Normal the user found
-- level 40 a slog and level 50 too hard, and at 60 lost to the final boss on Casual.
local SEED_RAMP = { below = 1, bossRange = 2, rampFrom = 5, rampTo = 25, slots = 4, emptySlotCut = 12,
                    slowFrom = 30, slowRate = 0.75 }

local function seedScale()
    return SEED_SCALES[setting("strength")] or SEED_SCALES[1]
end

local function ramp(pair, lv)
    local t = math.min(1, math.max(0, (lv - SEED_RAMP.rampFrom) / (SEED_RAMP.rampTo - SEED_RAMP.rampFrom)))
    return math.floor(pair[1] + (pair[2] - pair[1]) * t + 0.5)
end

local function seedScaleToParty()
    local lv, detail = game.PartyLevel()
    if not lv then return nil, "party level unknown (" .. tostring(detail) .. ")" end
    local s = seedScale()
    local at, hp, attack = ramp(s.at, lv), ramp(s.hp, lv), ramp(s.attack, lv)
    local bossAt, bossPower = ramp(s.bossAt, lv), ramp(s.bossPower, lv)
    local size = #(game.PartyIds() or {})
    local empty = math.max(0, SEED_RAMP.slots - size)
    bossPower = math.floor(bossPower * (100 - SEED_RAMP.emptySlotCut * empty) / 100 + 0.5)
    local counted = math.min(lv, SEED_RAMP.slowFrom + (lv - SEED_RAMP.slowFrom) * SEED_RAMP.slowRate)
    local a, b, c = game.LevelBand(counted, SEED_RAMP.below, at, s.above)
    local ba, bb, bc = game.LevelBand(counted, SEED_RAMP.bossRange, bossAt)
    -- Round 101: MRP is paid as if the band's centre were the (counted) party level. A band under
    -- the party's level would otherwise cut MRP per battle by 12% to 27%, and the grind for
    -- visions would get longer as the fights got easier.
    local _, _, even = game.LevelBand(counted, 0, 100)
    local mrpLift, bossMrpLift = math.max(0, even - c), math.max(0, even - bc)
    log(string.format("scale: party level %d (%s), counted as %g, strength %s: enemies centre %d (%d%%), %d to %d, HP %d%%, attack %d%%; bosses centre %d (%d%%), power %d%%; MRP as level %d (%d in the party)",
        lv, detail, counted, STRENGTH_NAMES[setting("strength")] or "?", c, at, math.max(1, a), b, hp, attack, bc, bossAt,
        bossPower, even, size))
    local knobs = { hp = hp, attack = attack, magic = attack, mrpLift = mrpLift }
    local bossKnobs = { hp = bossPower, attack = bossPower, magic = bossPower, mrpLift = bossMrpLift }
    local n, err = applyScale("clamp", a, b, true, knobs, { a = ba, b = bb, knobs = bossKnobs })
    return n, err, lv, size
end

-- What follow does when the party's level changes, or the table has been written over.
local function followRescale(f)
    if f.seed then return seedScaleToParty() end
    return scaleToParty(f.range, f.at, f.withBosses, f.knobs)
end

local function seedScaleTick()
    -- Round 85: an `ffrap_scale 1` from the linked save was still on in a save of the game's own.
    if save.vanilla() and scaleByHand then
        scaleByHand, seedScaleOn, scaleFollow = false, false, nil
        log("scale: ffrap_scale is off for a save not linked to the seed")
        applyScale("off", nil, nil, false, { hp = 100, attack = 100, magic = 100 })
        return
    end
    if not seedCfg.openworld or scaleByHand then return end
    if not sessionSave() or not setting("scaling") then
        if seedScaleOn then
            seedScaleOn, scaleFollow = false, nil
            applyScale("off", nil, nil, false, { hp = 100, attack = 100, magic = 100 })
        end
        return
    end
    -- A new strength from the Options screen rescales at once.
    if scaleFollow and scaleFollow.seed and scaleFollow.strength ~= setting("strength") then scaleFollow = nil end
    if scaleFollow or (game.StoryCounter() or 0) < game.OPEN_START.story then return end
    local n, err, lv, size = seedScaleToParty()
    if n == nil then
        if not seedScaleFailed then log("scale: the seed's scaling failed: " .. tostring(err)) end
        seedScaleFailed = true
        return
    end
    seedScaleOn = true
    scaleFollow = { seed = true, last = lv, size = size, strength = setting("strength") }
    log("scale: the seed's scaling is on, following the party's level")
end

-- Round 102: a line per battle won, for scaling feedback. A battle is a stretch off the field
-- that ends with the save's battles-won counter up; its length counts the transitions and the
-- results screen too. The counter includes the prologue's 3 wins.
state.fight = {}
state.fightTick = function()
    local f = state.fight
    if not (seedCfg.openworld and sessionSave() and seedScaleOn) then
        f.since, f.wins = nil, nil
        return
    end
    if not game.OnField() then
        f.since = f.since or state.ticks
        return
    end
    local wins = game.WinCount()
    if f.since and wins and f.wins and wins > f.wins then
        log(string.format("battle: won (save's win count %d), %.1f s off the field; strength %s, party level %s",
            wins, (state.ticks - f.since) * TICK_MS / 1000, STRENGTH_NAMES[setting("strength")] or "?",
            tostring(scaleFollow and scaleFollow.last)))
    end
    f.since, f.wins = nil, wins
end

scaleTick = function()
    if not game.OnField() then return end
    seedScaleTick()
    -- Re-apply scaling if the table was reloaded or overwritten by another mod (e.g. FFRRandomizer).
    scaleChecks = scaleChecks + 1
    if scaleLast and scaleChecks % SCALE_CHECK_EVERY == 0 then
        local checked, differ, sample, reloaded = game.ScaleCheck()
        if checked and (differ > 0 or reloaded) then
            log(string.format("scale: the table changed under us: %d of %d rows differ%s%s; writing it again", differ,
                checked, sample and (" (" .. sample .. ")") or "", reloaded and ", the table is a new object" or ""))
            local l = scaleLast
            if scaleFollow then followRescale(scaleFollow)
            else applyScale(l.mode, l.a, l.b, l.withBosses, l.knobs, l.bossBand) end
        end
    end
    local f = scaleFollow
    if not f then return end
    local lv = game.PartyLevel()
    -- The seed's scaling also follows the party's size (round 77).
    local size = f.seed and #(game.PartyIds() or {}) or nil
    if not lv or (lv == f.last and size == f.size) then return end
    log("scale: party level " .. tostring(f.last) .. " -> " .. lv .. (size and (", " .. size .. " in the party") or ""))
    f.last, f.size = lv, size
    followRescale(f)
end

-- ffrap_bossfight <battle group> [quiet]: turn nearby closed chests and the Chamber of Arms sword
-- pedestal into encounter triggers for that battle group and log wins. Plays the sword fight's
-- victory scene unless `quiet` is passed.
-- ffrap_bossfight trigger: rewrite the current map's story boss trigger and log each step.
-- ffrap_bossfight sword: grant the Ancient Greatsword for the pedestal (`off` removes it).
-- ffrap_bossfight watch [class ...]: hook native functions on talk/encounter classes to trace
-- arguments (rate-limited after the first call); `watch off` stops logging.
local WATCH_CLASSES = { "CPP_TalkEventManager", "CPP_BFL_TalkEvent", "CPP_MapManager", "CPP_BFL_Encount",
    "CPP_EncountManager", "CPP_BattleManager", "CPP_BFL_Battle", "CPP_BattleSystem", "CPP_MapGimmick_EventTrigger" }
local WATCH_MAX_HOOKS, WATCH_MAX_LINES, WATCH_GAP = 200, 20, 2
local watch = { on = false, hooked = {}, count = 0, calls = {} }

local function describe(param)
    local okGet, v = pcall(function() return param:get() end)
    if not okGet then return "?" end
    local t = type(v)
    if t == "number" or t == "boolean" or t == "string" then return tostring(v) end
    if t ~= "userdata" and t ~= "table" then return t end
    local okText, s = pcall(function() return v:ToString() end)        -- FName, FString, FText
    if okText and type(s) == "string" then return s end
    local okValid, valid = pcall(function() return v:IsValid() end)
    if okValid and valid then
        local okName, n = pcall(function() return v:GetFName():ToString() end)
        if okName and type(n) == "string" then return n end
    end
    return "userdata"
end

local function watchCall(path, ...)
    if not watch.on then return end
    local c = watch.calls[path]
    if not c then
        c = { n = 0, lines = 0, last = -WATCH_GAP }
        watch.calls[path] = c
    end
    c.n = c.n + 1
    local now = os.time()
    if c.lines >= WATCH_MAX_LINES or now - c.last < WATCH_GAP then return end
    c.lines, c.last = c.lines + 1, now
    local args = {}
    for i, p in ipairs({ ... }) do
        if i > 3 then break end
        args[#args + 1] = describe(p)
    end
    log("watch: " .. path:gsub("^/Script/mucha%.", "") .. " (" .. table.concat(args, ", ") .. ") call " .. c.n)
end

local function startWatch(classes)
    watch.on = true
    for _, className in ipairs(classes) do
        local paths, flagsRead = game.FunctionPaths(className)
        if not paths then
            log("watch: no class " .. className)
        else
            log("watch: " .. className .. ": " .. #paths .. " functions" .. (flagsRead and "" or " (flags unreadable: all taken)"))
            for _, path in ipairs(paths) do
                if not watch.hooked[path] and watch.count < WATCH_MAX_HOOKS then
                    log("watch: hooking " .. path)
                    local ok, err = pcall(function()
                        RegisterHook(path, function(_, ...) watchCall(path, ...) end)
                    end)
                    watch.hooked[path] = true
                    watch.count = watch.count + 1
                    if not ok then log("watch: could not hook " .. path .. ": " .. tostring(err)) end
                end
            end
        end
    end
    log("watch: on, " .. watch.count .. " hooks in all")
    return watch.count
end
bossTest.arm = function(id, quiet)
    local ok, detail = game.BossTestArm(id, log, quiet)
    log("boss test: " .. (ok and "ready, " or "failed, ") .. tostring(detail))
    bossTest.group = ok and id or nil
    bossTest.quiet = quiet
    return ok, detail
end
bossTest.tick = function()
    if game.GetFlag(game.BOSS_TEST_FLAG) ~= true then return end
    game.SetFlag(game.BOSS_TEST_FLAG, false)
    log("boss test: WIN seen for battle group " .. tostring(bossTest.group))
    notify("Boss test: win seen")
end
command("ffrap_bossfight", function(p)
    local first = tostring(p[1] or ""):lower()
    if first == "watch" then
        if tostring(p[2] or ""):lower() == "off" then
            watch.on = false
            log("watch: off")
            notify("Watch off")
            return
        end
        local classes = {}
        for i = 2, #p do classes[#classes + 1] = tostring(p[i]) end
        local n = startWatch(#classes > 0 and classes or WATCH_CLASSES)
        notify("Watch on: " .. n .. " hooks (see the log)")
        return
    end
    if first == "sword" then
        local held = game.HeldCount(game.BOSS_TEST_SWORD)
        local text = "Ancient Greatsword held " .. tostring(held) .. "; flag 901 (sword fight won) " .. tostring(game.GetFlag(901))
        if held == 0 then
            local code, detail = game.GrantItem(game.BOSS_TEST_SWORD, 1)
            text = text .. "; given: " .. tostring(code) .. ", " .. tostring(detail)
        end
        log("boss test: " .. text)
        notify("Boss test: " .. text)
        return
    end
    if first == "trigger" then
        if not game.InGame() then
            notify("Boss test: load a save first")
            return
        end
        local ok, detail = game.SyncStoryBossTrigger(log)
        log("boss test: trigger: " .. tostring(detail))
        notify("Boss trigger: " .. tostring(detail))
        return
    end
    if first == "off" then
        bossTest.group = nil
        log("boss test: off, " .. tostring(game.BossTestOff(log)) .. " rows put back")
        notify("Boss test off")
        return
    end
    local id = tonumber(first)
    if not id then
        notify("Usage: ffrap_bossfight <battle group> [quiet] | trigger | sword | off | watch [class ...] | watch off")
        return
    end
    if not game.InGame() then
        notify("Boss test: load a save first")
        return
    end
    local ok, detail = bossTest.arm(math.floor(id), tostring(p[2] or ""):lower() == "quiet")
    notify(ok and ("Boss test ready: open a closed chest, or use the Chamber of Arms sword pedestal. " .. detail) or ("Boss test failed: " .. tostring(detail)))
end)

-- ffrap_noland list: every no-landing box on this map, to noland.txt.
-- ffrap_noland here: the boxes under you (seen from above).
-- ffrap_noland show [width] / hide: draw the boxes' outlines, or hide them again.
-- ffrap_noland lock <mysidia|gronoa|pharm>: that story box stops landing (its condition always
--   holds). unlock: it never holds. The box stays where the game put it. Every box with that
--   story condition is written.
-- ffrap_noland refresh: update box collisions to match their current condition immediately.
-- ffrap_noland spawn [half]: a new box under you, `half` across each way (default 2000), at
--   the Mysidia box's height.
-- ffrap_noland move [half]: the game's own Mysidia box, moved under you, condition emptied.
-- ffrap_noland cond <text>: the condition of the spawned and moved boxes.
-- ffrap_noland off: undo all of it.
-- Every step is logged before it runs ("noland step: ...").
local function poseText(pose)
    return pose and string.format("%.0f, %.0f, %.0f", pose.x, pose.y, pose.z) or "?"
end

command("ffrap_noland", function(p)
    local what = (p[1] and p[1]:lower()) or "list"
    game.gateTrace = function(step) log("noland step: " .. step) end
    local ok, err = pcall(function()
        if what == "list" then
            local boxes = game.NoLandBoxes()
            local f = io.open(MOD_DIR .. "noland.txt", "w")
            for _, b in ipairs(boxes) do
                local line = game.NoLandLine(b)
                if f then f:write(line, "\n") end
            end
            if f then f:close() end
            log(string.format("noland: %d boxes on map %s, written to noland.txt; you are at (%s)", #boxes,
                tostring(game.CurrentMap()), poseText(game.PlayerPose())))
            notify("No-landing boxes: " .. #boxes .. " (noland.txt)")
        elseif what == "here" then
            local boxes, pose = game.NoLandHere()
            if not boxes then
                notify("No-landing: " .. tostring(pose))
                return
            end
            log(string.format("noland: you are at (%s), under %d boxes", poseText(pose), #boxes))
            for _, b in ipairs(boxes) do
                log("noland:   " .. game.NoLandLine(b))
                log("noland:     " .. game.NoLandCollision(b))
            end
            local hits, err = game.GroundUnder()
            local ground = nil
            for _, h in ipairs(hits or {}) do
                log(string.format("noland:   trace down hit %s%s at z %.0f", h.name, h.box and " (a no-landing box)" or "", h.z))
                if not h.box then ground = h.z end
            end
            if not hits then log("noland:   trace down: " .. tostring(err))
            elseif #hits == 0 then log("noland:   trace down hit nothing") end
            notify("Under " .. #boxes .. " no-landing boxes" .. (boxes[1] and (": " .. boxes[1].name) or "")
                .. (ground and string.format("; ground at z %.0f", ground) or ""))
        elseif what == "show" or what == "hide" then
            local n = game.NoLandShow(what == "show", tonumber(p[2]))
            log("noland: " .. what .. ": " .. n .. " boxes")
            notify("No-landing boxes " .. (what == "show" and "shown" or "hidden") .. ": " .. n)
        elseif what == "lock" or what == "unlock" then
            local which = (p[2] or ""):lower()
            local boxes, why = game.NoLandLock(which, what == "lock")
            for _, box in ipairs(boxes or {}) do
                log("noland: " .. what .. " " .. which .. ": " .. game.NoLandLine(box))
                log("noland:     " .. game.NoLandCollision(box))
            end
            if not boxes or why then log("noland: " .. what .. " problem: " .. tostring(why)) end
            notify("No-landing " .. which .. ": " .. (boxes and ((what == "lock" and "locked " or "unlocked ") .. #boxes .. " box(es)") or "failed")
                .. (why and (": " .. why) or ""))
        elseif what == "refresh" then
            local nOn, nOff, onType = game.NoLandRefresh()
            log(string.format("noland: refresh: collision on (%d) for %d boxes, off for %d", onType, nOn, nOff))
            notify(string.format("No-landing refresh: %d on, %d off", nOn, nOff))
        elseif what == "spawn" or what == "move" then
            local half = tonumber(p[2]) or 2000
            local box, why
            if what == "spawn" then box, why = game.NoLandSpawn(half, tonumber(p[3])) else box, why = game.NoLandMove(half) end
            if box then
                log("noland: " .. what .. ": " .. game.NoLandLine(box) .. (why and (" (" .. why .. ")") or ""))
                log("noland:     " .. game.NoLandCollision(box))
            end
            if not box or why then log("noland: " .. what .. " problem: " .. tostring(why)) end
            notify("No-landing box " .. (box and (what == "spawn" and "spawned" or "moved") or "failed") .. (why and (": " .. why) or ""))
        elseif what == "channel" then
            local ch, resp = tonumber(p[2]), tonumber(p[3])
            if not (ch and resp and resp >= 0 and resp <= 2) then
                notify("Usage: ffrap_noland channel <channel> <0 ignore|1 overlap|2 block>")
                return
            end
            local n = game.NoLandChannel(ch, resp)
            log("noland: channel " .. ch .. " -> " .. resp .. " on " .. n .. " spawned boxes")
            notify("No-landing channel " .. ch .. " set to " .. resp .. " on " .. n .. " boxes")
        elseif what == "shadow" then
            local before, after, names = game.NoLandShadow()
            if not before then
                notify("Shadow list: " .. tostring(after))
            else
                log("noland: shadow ignore list " .. before .. " -> " .. after .. " [" .. table.concat(names, ", ") .. "]")
                notify("Shadow ignore list: " .. before .. " -> " .. after)
            end
        elseif what == "cond" then
            local cond = p[2] or ""
            local n, last, e = game.NoLandCondition(cond)
            log("noland: condition \"" .. cond .. "\" written to " .. n .. " boxes" .. (e and (" (error " .. e .. ")") or "")
                .. (last and ("; read back: " .. game.NoLandLine(last)) or ""))
            notify("No-landing condition set on " .. n .. " boxes")
        elseif what == "off" then
            local n = game.NoLandOff()
            log("noland: off: " .. n .. " boxes undone")
            notify("No-landing boxes undone: " .. n)
        else
            notify("Usage: ffrap_noland <list|here|show|hide|lock <box>|unlock <box>|refresh|spawn [half] [top]|move [half]|channel <n> <0-2>|shadow|cond <text>|off>")
        end
    end)
    game.gateTrace = nil
    if not ok then error(err) end
end)

-- ffrap_story 9000: the story's cleared value (the ending sets it). Only the counter: no flags.
command("ffrap_story", function(p)
    local n = tonumber(p[1])
    if not n then
        notify("Story counter: " .. tostring(game.StoryCounter()) .. " (usage: ffrap_story <value>)")
        return
    end
    local was = game.StoryCounter()
    local now = game.SetStoryCounter(math.floor(n))
    log("story: counter " .. tostring(was) .. " -> " .. tostring(now) .. " (asked for " .. n .. ")")
    notify("Story counter " .. tostring(was) .. " -> " .. tostring(now) .. ". Save and reload to apply.")
end)

-- ffrap_airship: show the condition. ffrap_airship {progress:0}>=0: the airship from now on.
-- ffrap_airship off: the shipped condition. The text is one word, with no spaces.
command("ffrap_airship", function(p)
    local want = p[1]
    if want and want:lower() == "home" then
        -- Park the seed's airship back at its starting location.
        notify(parkAirshipAtStart("ffrap_airship home") and "Airship: parked at the start; it lands there at the next map change"
            or "Airship: no start on foot for this seed")
        return
    end
    if want and want:lower() == "state" then
        local text = game.AirshipState()
        log("airship: " .. text)
        notify("Airship: " .. text)
        return
    end
    if want and want:lower() == "off" then want = game.AIRSHIP_CONDITION end
    if want then log("airship: writing spawn condition " .. want) end
    local now, err = game.AirshipCondition(want)
    log("airship: spawn condition is " .. tostring(now) .. (err and (" (" .. err .. ")") or ""))
    notify("Airship spawn condition: " .. tostring(now))
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

-- ffrap_skip [slot]: skip the prologue on a new game. Without a slot it modifies the loaded save
-- in place; with a slot it saves there and reloads.
--
-- The skip is re-applied right before saving because the opening scene can overwrite flags and
-- position after an initial skip. Every step sets an absolute value, so running twice is safe.
command("ffrap_skip", function(p)
    local slot = p and p[1] and tonumber(p[1])
    if p and p[1] and not slot then
        notify("Usage: ffrap_skip [slot] [force]   (0 is the autosave)")
        return
    end
    if not game.InGame() then
        notify("Start a new game first")
        return
    end
    followSave()
    runSkip(slot, "command", p[2] == "force")
end)

-- ffrap_input [fix]: inspect player controller input locks (for skips during the opening movie).
-- Logs input switches; `fix` attempts the engine's reset calls.
command("ffrap_input", function(p)
    log("input: " .. game.InputState())
    if p[1] == "fix" then
        local failed = game.InputFix(function(step) log("input step: " .. step) end)
        for _, f in ipairs(failed) do log("input: failed: " .. f) end
        log("input after fix: " .. game.InputState())
    end
    notify("Input state written to the log")
end)

-- ffrap_chats [done]: list the loaded save's Active Time Chats, or mark them all played.
command("ffrap_chats", function(p)
    if p[1] == "done" then
        local ok, line = game.MarkChatsPlayed(game.SaveData())
        log("chats: " .. line)
        if not ok then notify("Active Time Chats: failed (see the log)") end
    end
    local text = game.ChatState()
    log("chats: " .. text)
    notify("Active Time Chats: " .. text)
end)

-- Re-apply continent locks on map load so saves loaded in the air cannot land prematurely.
if RegisterLoadMapPostHook then
    local okHook, errHook = pcall(RegisterLoadMapPostHook, function(_, world)
        state.traceStart("map load")
        pcall(game.ForgetObjects)
        local okRun, placed, why = pcall(function() return game.ContinentMapLoaded(world:get(), locksOn()) end)
        if not okRun then
            log("locks: the map load hook failed: " .. tostring(placed))
        elseif placed and #placed > 0 then
            log("locks: boxes placed during the map load for " .. table.concat(placed, ", "))
        elseif not placed and why ~= "locks off" and why ~= "not the world map" then
            log("locks: " .. tostring(why))
        end
    end)
    if not okHook then log("locks: could not hook map loads: " .. tostring(errHook)) end
else
    log("locks: this UE4SS has no RegisterLoadMapPostHook, so the locks go in a moment after each load")
end

-- ffrap_lock [on|off|open <continent|all>|close <continent|all>]: the continent locks, for testing
-- until a seed decides them. `on` and `off` are the switch, kept in ap_state.txt. `open` and
-- `close` write the continent's flag into the loaded save. With no word: the state, to the log.
command("ffrap_lock", function(p)
    local what, name = p and p[1], p and p[2]
    if what == "on" or what == "off" then
        continentLocks = what == "on"
        lockChoice = continentLocks
        saveState()
        if not lockChoice then game.ContinentClear() end
    elseif what == "open" or what == "close" then
        local n, why = game.SetContinentOpen(name, what == "open")
        if not n then
            notify("Usage: ffrap_lock open|close <continent|all> (" .. tostring(why) .. ")")
            return
        end
    elseif what then
        notify("Usage: ffrap_lock [on|off|open <continent|all>|close <continent|all>]")
        return
    end
    local text = (locksOn() and "on" or "off") .. "; " .. game.ContinentStatus()
    log("locks: " .. text)
    notify("Continent locks: " .. text)
end)

-- ffrap_visions: log the first vision's synchro keys for inspecting vision data.
command("ffrap_visions", function()
    local text = game.VisionKeys()
    log("visions: " .. text)
    notify("Visions: " .. text)
end)

-- ffrap_visited <map> [unvisit|unknown|restore] (round 117 probe): the map's known and visited
-- marks. unvisit marks it not visited; unknown marks it neither; restore marks it both again. Then
-- the Map screen shows whether its fast travel follows either mark.
command("ffrap_visited", function(p)
    local m, what = tonumber(p[1] or ""), tostring(p[2] or "")
    local marks = { unvisit = { true, false }, unknown = { false, false }, restore = { true, true } }
    if not m or (what ~= "" and not marks[what]) then
        notify("Usage: ffrap_visited <map> [unvisit|unknown|restore]")
        return
    end
    local mk = marks[what]
    local line = game.MapMarks(m, mk and mk[1], mk and mk[2])
    log("visited: " .. (what ~= "" and (what .. ": ") or "") .. line)
    notify(line)
end)

-- ffrap_perf: the time each loop, step and object search took since the last summary.
command("ffrap_perf", function()
    for _, line in ipairs(state.perfLines()) do log(line) end
    notify("Timings written to the log")
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
readCrossings()
for _, f in ipairs(bridge.readOut()) do
    if f[1] == "check" or f[1] == "story" then state.reported[f[1] .. "|" .. tostring(f[2])] = true end
end
bridge.write("hello", VERSION, PROTOCOL)
if state.seed then bridge.write("seed", state.seed) end
readInbox(true)
log("version " .. VERSION .. " (build " .. bridge.build(MOD_DIR) .. ") loaded from " .. MOD_DIR .. ", " .. state.applied .. " items already applied")
if randomizerWarning then log(randomizerWarning) end

-- Fast check (0.1 s): inspect the chest dialog widget and trigger an immediate scan when a pop-up
-- appears so scout text updates within ~0.1 s rather than waiting for the 1 s tick.
local function fastTick()
    pcall(defendRates)
    if not game.InGame() or state.inGameTicks <= SETTLE_TICKS or not sessionSave() then return end
    state.mark("fast: pop-up")
    if not game.PopupJustOpened() then return end
    state.mark("fast: scans")
    local mapId = game.CurrentMap()
    if mapId and mapId == visit.mapId and visit.scans > MAP_SETTLE_SCANS then
        pcall(scanChests, mapId)
        pcall(scanShinies, mapId)
    end
    pcall(scanBosses)
    pcall(popupTick)
end

-- Run both timers on UE4SS's game thread: LoopAsync invokes Lua on an async worker thread while
-- the main tick runs on the game thread, causing race-condition crashes on shared Lua state.
local function every(ms, name, fn)
    local function run()
        local t0 = os.clock()
        state.mark(name)
        local ok, err = pcall(fn)
        if not ok then log(name .. " error: " .. tostring(err)) end
        state.mark(name .. " done")
        state.perfLoop(name, os.clock() - t0)
    end
    if LoopInGameThreadWithDelay then
        LoopInGameThreadWithDelay(ms, run)
    else
        log("this UE4SS has no LoopInGameThreadWithDelay: the " .. name .. " runs from LoopAsync")
        LoopAsync(ms, function() ExecuteInGameThread(run) return false end)
    end
end

every(FAST_MS, "fast tick", fastTick)
every(TICK_MS, "tick", tick)
