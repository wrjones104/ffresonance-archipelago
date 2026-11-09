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
--   ffrap_skip [slot] [force]    skip the prologue on a new game; with a slot, save there and reload
--   ffrap_input [fix]            probe: the player controller's input state; fix tries the engine's resets
--   ffrap_openstart [on|off|dock|air|event|at x y z|now [slot]]  test: the open world start (story 8000)
--   ffrap_chats [done]           the loaded save's Active Time Chats; done marks them all played
--   ffrap_lock [on|off|open <continent|all>|close <continent|all>]  test: the continent locks
--   ffrap_visions                the first vision's synchro keys, to the log
--   ffrap_inspect <class|path> [label]  one object's fields and functions to inspect_<name>[_label].tsv
--   ffrap_title [list|add]       the Archipelago entry on the title menu (added at start-up)
--   ffrap_notice [text]          experimental: show text with the game's quest-notice banner
--   ffrap_logo                   the Archipelago logo on the mod's title line, by hand
--   ffrap_layout <text>          the panels holding some on-screen text, to the log
--   ffrap_feed [on|off|test [plain]|check]  the item feed at the bottom right of the field HUD (on by default)
--   ffrap_find <text>            game classes, functions and fields named like the text, to find_<text>.txt
--   ffrap_blank [on|off]         chests that are Archipelago locations give 1 gil instead
--   ffrap_sync                   report every known location the save says is looted
--   ffrap_bind                   link the loaded save to the client's session (also /bind in the client)
--   ffrap_reset                  set the loaded save's applied-item count to 0 (re-grants everything to it!)
--   ffrap_gate <subcommand>      experimental: spawn conditional blockers and custom key items
--   ffrap_scale <level|low high|party n|off> [at %] [hp %] [attack %] [magic %] [power %] [boss] [follow]
--                                probe: rewrite every enemy's level and stats
--   ffrap_scale [show <id|name>] probe: the rescale in force, or one enemy's rows in every unit table
--   ffrap_noland <list|here|show|hide|lock|unlock|refresh|spawn|move|channel|shadow|cond|off>
--                                probe: the airship's no-landing boxes
--   ffrap_story <value>          probe: set the loaded save's story counter (any value; save and reload)
--   ffrap_airship [condition|off|state]  probe: the airship's spawn condition (shipped {progress:0}>=4250); state logs its save fields
--
-- Each client session belongs to its saves. A new game started from the Archipelago entry on
-- the title menu is linked to it at once and skips the prologue by itself (plain New Game stays
-- vanilla); an existing save is linked with ffrap_bind or the client's /bind. The link
-- follows the save slots the linked game is saved to. While any other save is loaded, the mod
-- grants nothing, reports nothing and leaves the chests vanilla.

local VERSION = "0.24.0"
local PROTOCOL = 1        -- the bridge protocol; the apworld's MOD_PROTOCOL

local MOD_DIR = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)Scripts/[^/]+$"))
    or "ue4ss/Mods/FFRArchipelago/"

local game = require("game")
local bridge = require("bridge")

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
local STATUS_EVERY = 10       -- ticks between status file writes

local function log(msg)
    print("[FFRAP] " .. tostring(msg) .. "\n")
end

-- Round 33: the FFR Randomizer mod was on next to this one. Every 3 seconds it writes its own
-- values back into the chest, shop and enemy rows, so it undoes our chest blanks and enemy
-- rescale. UE4SS starts a mod that has an enabled.txt, or a "name : 1" line in mods.txt.
-- The warning is logged at start and shown once, when the first save loads.
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

-- On-screen messages go to the item feed on the field HUD (IDEAS.md, idea 14) when it is on and
-- the HUD is there. Otherwise they wait in a short queue for the HUD (loading, a map change),
-- and off the field (the title screen) they go to ModSettings' Toast as before.
local FEED_QUEUE_MAX = 20
local FEED_WAIT_MAX = 10     -- seconds messages wait for the feed before they go to the Toast
-- On unless switched off: it works since 0.9.5 (round 23), and messages it cannot show go to
-- the Toast after FEED_WAIT_MAX.
local feedOn = true          -- ffrap_feed on|off; kept in ap_state.txt
local openStart = false      -- ffrap_openstart on|off: the skip goes to the open world; kept in ap_state.txt
local openArrival = nil      -- ffrap_openstart dock|air|event, kept once the user picks one
local continentLocks = nil   -- ffrap_lock on|off, kept once the user picks one; off until then
local locksFailed = nil      -- the last ContinentSync failure logged, so each one is logged once
local feedQueue = {}
local feedQueueSince = nil   -- when the oldest waiting message came
local feedShown = false      -- the feed has shown a line in this run
local feedClock = 0          -- seconds, from the tick count

local function show(msg)
    if feedOn and game.InGame() then
        if #feedQueue == 0 and game.FeedLine(msg, feedClock) then
            feedShown = true
            return
        end
        if #feedQueue == 0 then feedQueueSince = feedClock end
        if #feedQueue < FEED_QUEUE_MAX then feedQueue[#feedQueue + 1] = msg end
        return
    end
    game.Toast(msg)
end

local function notify(msg)
    log(msg)
    show(msg)
end

-- Shows what waited for the HUD. A long wait (a login with many items) shows the last few and
-- how many more there were.
local function flushFeed()
    if #feedQueue == 0 then return end
    -- Waited too long and the feed has never shown a line this run (it cannot find a HUD on
    -- screen, as in round 22): the Toast takes them, so no message is lost from the screen. Once
    -- the feed has worked, messages wait for the HUD however long a pop-up or menu is open
    -- (round 24: a chest pop-up held for 10 s sent its items to the Toast).
    if not feedShown and feedQueueSince and feedClock - feedQueueSince > FEED_WAIT_MAX then
        log("feed: no HUD on screen for " .. FEED_WAIT_MAX .. " s; " .. #feedQueue .. " message(s) go to the Toast")
        game.Toast(#feedQueue == 1 and feedQueue[1] or table.concat(feedQueue, " / "))
        feedQueue, feedQueueSince = {}, nil
        return
    end
    local lines = feedQueue
    if #lines > game.FEED_MAX then
        local more = #lines - (game.FEED_MAX - 1)
        local tail = {}
        for i = #lines - game.FEED_MAX + 2, #lines do tail[#tail + 1] = lines[i] end
        lines = tail
        table.insert(lines, 1, "and " .. more .. " more")
    end
    for i, msg in ipairs(lines) do
        if game.FeedLine(msg, feedClock) then
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
}

-- The loaded save, and whether it is the session's. Not kept across game restarts: save data
-- objects are new each run.
local save = {
    obj = nil,         -- the save data object's name (G.SaveObjectName)
    ticks = nil,       -- its timestamp when last seen
    slot = nil,        -- the slot it was loaded from, or nil for an unsaved new game
    pending = nil,     -- a timestamp the game just saved with, until its slot is known
    pendingItems = nil, -- the applied count when that save happened
    apObj = nil,       -- the save object of a new game started from the Archipelago title entry
    autoWait = 0,      -- ticks waited before the automatic prologue skip
    autoDone = false,  -- the automatic skip was tried (or given up) for this game
    ok = false,        -- true when this is the session's save
}

-- True when the loaded save is the session's. With no client session (fake_ap.py testing)
-- every save counts, as before 0.5.0.
local function sessionSave()
    return state.seed == nil or save.ok
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

-- The applied count is per save (0.7.0): each linked slot keeps how many items the save in it
-- holds, and `applied` is the loaded save's.
local function loadState()
    local f = io.open(STATE_PATH, "r")
    if not f then return end
    for line in f:lines() do
        local key, value = line:match("^(%w+)\t(.*)$")
        if key == "applied" then state.applied = tonumber(value) or 0 end
        if key == "blank" then state.blank = value == "1" end
        -- "itemfeed", written only by ffrap_feed on|off. 0.9.0 wrote "feed 1" by itself (it
        -- was on by default), and 0.9.1 took that as switched on and crashed (round 19), so the
        -- old key is ignored.
        if key == "itemfeed" then feedOn = value == "1" end
        if key == "openstart" then openStart = value == "1" end
        if key == "continentlocks" then continentLocks = value == "1" end
        if key == "openarrival" and game.OPEN_STARTS[value] then
            openArrival = value
            game.OPEN_START = game.OPEN_STARTS[value]
        end
        if key == "seed" and value ~= "" then state.seed = value end
        if key == "slots" then
            for slot in value:gmatch("%d+") do state.slots[tonumber(slot)] = true end
        end
        if key == "live" and value ~= "" then state.live = value end
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
    if openArrival then f:write("openarrival\t", openArrival, "\n") end
    if continentLocks ~= nil then f:write("continentlocks\t", continentLocks and "1" or "0", "\n") end
    f:write("seed\t", state.seed or "", "\n")
    f:write("slots\t", slotsText(), "\n")
    f:write("slotItems\t", slotsText(true), "\n")
    if save.ok and save.obj then state.live = save.obj .. "|" .. tostring(save.ticks) end
    f:write("live\t", state.live or "", "\n")
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
    state.seed, state.applied, state.items, state.reported = key, 0, {}, {}
    state.syncPending = true
    state.slots, state.slotItems, state.bindPending, state.live = {}, {}, false, nil
    state.scouts = {}
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
                state.items[index] = { kind = f[3], id = id, count = tonumber(f[5]) or 1,
                    label = (f[6] and f[6] ~= "") and f[6] or (f[3] .. " " .. f[4]) }
            else
                log("bad item line: " .. table.concat(f, " | "))
            end
        elseif f[1] == "scout" then
            -- What a location holds, for the chest pop-up (0.11.0).
            if f[2] and f[3] then
                state.scouts[f[2]] = { item = f[3], player = f[4] or "", flags = tonumber(f[5]) or 0,
                                       own = f[6] == "1" }
            end
        elseif f[1] == "client" then
            -- The client's world version, written each time it connects.
            if f[2] ~= state.clientVersion then
                state.clientVersion = f[2]
                log("client: world version " .. tostring(f[2]))
            end
        elseif f[1] == "msg" then
            -- Messages from before this game session started are old news.
            if not initial then notify(f[2] or "") end
        end
    end
end

-- Items that cannot go in yet, by index. A grant that answers "wait" goes here and the queue
-- goes on. (Until 0.20.0 a vision answered "wait" while the save owned none; it no longer needs
-- one, so nothing answers "wait" today.) These are tried again each pass. The list is rebuilt from the received visions whenever a save is
-- loaded, because an older save can lack a vision that was unlocked after it was written.
-- Only visions: they are the same item however often they are granted. A unit is not re-added,
-- as the story itself makes some leave (Fina in chapter 3).
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
            else
                notify("Could not apply " .. it.label .. ": " .. tostring(detail))
            end
        end
    end
    waiting = keep
end

local function applyItems()
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
            else
                notify("Could not apply " .. it.label .. ": " .. tostring(detail))
            end
            state.applied = state.applied + 1
            state.lastResult = it.label .. ": " .. code
            done = done + 1
            saveState()
        end
    end
    if feedOn and game.InGame() then
        -- The feed has a line per item.
        for _, name in ipairs(names) do notify("Received " .. name) end
    elseif #names == 1 then
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
local visit = { mapId = nil, scans = 0, recorded = {}, closed = {} }

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
    visit = { mapId = mapId, scans = 0, recorded = {}, closed = {} }
end

-- The chest pop-up (IDEAS.md, idea 13): the pop-up is up while the chest's check is reported,
-- so a check for a chest the client scouted asks for the pop-up to say what the chest held for
-- Archipelago. The pop-up is looked for over a few ticks, as it can come up a moment later.
local POPUP_TRIES = 8
local popup = nil   -- { text, key, tries }

local function popupText(s)
    if s.own then return "You obtained the following:\n" .. s.item end
    return "You found the following for " .. s.player .. ":\n" .. s.item
end

local function popupTick()
    pcall(game.ChestPopupRestore)
    if not popup then return end
    local ok, detail = game.ChestPopup(popup.text)
    if ok then
        log("chest pop-up for " .. popup.key .. ": " .. detail)
        popup = nil
        return
    end
    popup.tries = popup.tries - 1
    if popup.tries <= 0 then
        log("chest pop-up for " .. popup.key .. ": " .. tostring(detail))
        popup = nil
    end
end

-- `fresh`: the chest was seen closed in this map visit and is open now, so it was just opened in
-- front of the player. Its pop-up is rewritten whether or not the server has the check already
-- (round 27: after reloading an older save, chests opened again kept "1 gil", because only a
-- first report asked for the pop-up). A first report asks too, for a chest opened before the
-- map's first scan.
local function opened(key, fresh)
    if not sessionSave() then return end
    local new = report("check", key)
    if new then log("check " .. key) end
    if new or fresh then
        local s = state.scouts[key]
        if s and key:find("^chest:") then popup = { text = popupText(s), key = key, tries = POPUP_TRIES } end
    end
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
            local id = "c" .. c.uniqueId
            if c.open or game.IsChestOpenInSave(mapId, c.uniqueId) then
                local fresh = visit.closed[id] == true
                visit.closed[id] = nil
                if key then opened(key, fresh) end
            else
                visit.closed[id] = true   -- seen closed: opening it later is "in front of the player"
            end
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

local titleReady = false   -- the Archipelago title entry is in the menu's data asset

-- Decides whether a save that was just loaded (or a new game) is the session's.
local function judgeSave()
    if not state.seed then setOk(true); return end
    -- The same save the count was for, still loaded (the mod was reloaded): keep the count.
    local same = state.live ~= nil and state.live == (tostring(save.obj) .. "|" .. tostring(save.ticks))
    if save.apObj ~= nil and save.apObj == save.obj then
        -- Started from the Archipelago title entry: it joins the session even when the session
        -- has other saves already. It holds none of the session's items yet. It may have
        -- autosaved before the client connected, so its slot is linked too.
        setOk(true)
        if not same then setApplied(0, "an Archipelago new game") end
        if save.slot ~= nil then linkSlot(save.slot, state.applied) end
        saveState()
        -- Only logged: the player chose the Archipelago entry, so it says nothing new (round 24).
        log("Archipelago: this new game is linked to the seed")
    elseif save.slot ~= nil and state.slots[save.slot] then
        setOk(true)
        log("save slot " .. save.slot .. " is the session's save")
        -- A state file from before 0.7.0 has no count for the slot: keep the old one.
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
        -- A new game can carry the timestamp of the autosave slot it is about to overwrite
        -- (round 7: a new game showed up as linked slot 0). Nothing at the very start of the
        -- story is worth keeping, so a save there is always a new game.
        local story = game.StoryCounter()
        if save.slot ~= nil and story and story <= NEW_GAME_STORY then
            log("story " .. story .. ": a new game, although its timestamp matches slot " .. save.slot)
            save.slot = nil
        end
        -- The new game the Archipelago title entry started (any other load uses up the mark).
        if state.apNewGame then
            state.apNewGame = false
            if save.slot == nil and story and story <= NEW_GAME_STORY then
                save.apObj, save.autoWait, save.autoDone = obj, 0, false
                log("an Archipelago new game")
            end
        end
        log("save loaded: slot " .. tostring(save.slot) .. ", session slots [" .. slotsText(true) .. "]")
        judgeSave()
        waitingDirty = true
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
-- The Archipelago new game: the title entry and the prologue skip (IDEAS.md, ideas 2 and 6)
-- -------------------------------------------------------------------------------------------

-- The title menu's entries are ETitleFunctionType values; the Archipelago entry is type 5, a
-- copy of New Game (game.AddTitleEntry). A hook on ExecuteEntry, run before the game's own
-- code, marks the next new game as an Archipelago one and turns type 5 into New Game (round 12).
local titleHooked = false
local function hookTitle()
    if titleHooked then return true end
    local ok, err = pcall(function()
        RegisterHook("/Script/mucha.CPP_VM_Title:ExecuteEntry", function(_, inType)
            local t
            pcall(function() t = inType:get() end)
            log("title: entry " .. tostring(t) .. " chosen")
            if t == game.TITLE_ARCHIPELAGO then
                state.apNewGame = true
                pcall(function() inType:set(game.TITLE_NEW_GAME) end)
                notify(state.seed and "Archipelago: starting a new game for the seed"
                    or "Archipelago: starting a new game (connect the client to link it to a seed)")
                -- Round 35: the switch was off and the log did not say so.
                log("title: open world start is " .. (openStart and "on" or "off") .. " (ffrap_openstart)")
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
local layoutLogged = false   -- the version text's layout is logged once per run (for the logo)
local logoLogged = nil       -- the last logo failure logged, so each one is logged once
local function titleTick()
    if state.ticks ~= 1 and state.ticks % TITLE_EVERY ~= 0 then return end
    local inGame = game.InGame()
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

-- The prologue skip (see ffrap_skip). Applied again right before saving: round 8 showed the
-- opening scene can change flags and the position after a skip. Every step but the inventory
-- sets an absolute value; the inventory changes are relative, so they are made once per save.
local skipped = nil    -- the save object the skip was applied to
-- `force` (ffrap_skip <slot> force) skips before story 1005 anyway: the round 36 probe of the
-- opening's input lock, which a skip at that point is known to leave behind (round 9).
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
    local okRun, ok, report = pcall(game.SkipPrologue, { inventory = not again, openStart = openStart })
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
    if state.seed and save.ok then
        linkSlot(slot, state.applied)
        saveState()
        log("skip: slot " .. slot .. " linked before the reload: session slots [" .. slotsText(true) .. "]")
    end
    local saved, detail = game.SaveAndReload(slot, (openStart and game.OPEN_START or game.SKIP_ARRIVAL).map)
    if openStart then detail = detail .. "; open world start (" .. game.OPEN_START.name .. ", story " .. game.OPEN_START.story .. ")" end
    log("skip (" .. why .. "): " .. detail)
    -- The automatic skip is part of starting an Archipelago game, so it is only logged when it
    -- works (round 24); a failure, or a skip by command, is shown.
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
        "FFRArchipelago " .. VERSION .. "  " .. os.date("%Y-%m-%d %H:%M:%S"),
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

-- Continent locks (game.ContinentSync): while the switch is on, the world map keeps its lock
-- boxes in step with the save's flags. Round 40: the boxes go with each map change, so this puts
-- them back. Only on the field: a battle is no time to spawn actors.
local function locksTick()
    if not continentLocks or not game.OnField() then return end
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
end

local function tick()
    state.ticks = state.ticks + 1
    readInbox(false)
    titleTick()
    feedClock = state.ticks * TICK_MS / 1000
    if game.InGame() then
        pcall(flushFeed)
        pcall(game.FeedTick, feedClock)
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
            followSave()
            if state.bindPending then
                state.bindPending = false
                bindLoaded()
            end
            autoSkip()
            pcall(popupTick)
            pcall(gateTick)
            if state.ticks % STATUS_EVERY == 0 then pcall(scaleTick) end
            if state.ticks % LOCKS_EVERY == 0 then pcall(locksTick) end
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
    "CPP_BFL_Chat", "CPP_ChatSubsystem", "CPP_QuestSubsystem", "CPP_VM_QuestNotice",
}

-- ffrap_title [list|add]: the Archipelago title entry (IDEAS.md, idea 6). The mod adds it at
-- start-up; `add` does it again by hand, `list` logs what the menu shows.
command("ffrap_title", function(p)
    local what = (p and p[1]) or "list"
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

-- ffrap_logo: put the Archipelago logo on the mod's line on the title screen by hand (the mod
-- does it by itself; IDEAS.md, idea 6).
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
        -- Each step is logged before it runs: if the game crashes, the last `feed step:` line in
        -- UE4SS.log names the call. `test plain` leaves out the styling.
        local plain = p[2] == "plain"
        log("feed test" .. (plain and " (plain)" or "") .. ": starting")
        -- Each step is logged before it runs while testing: a crash in the engine ends the game
        -- before Lua can log, so the last `feed step:` line in UE4SS.log names the call (round 19).
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
    else
        notify("Item feed is " .. (feedOn and "on" or "off") .. " (ffrap_feed on|off|test)")
    end
end)

-- ffrap_openstart [on|off|dock|air|event|at <x> <y> <z>|now [slot]]: whether the prologue skip
-- goes to the open world start (game.OPEN_START) in place of the Earth Shrine. Off by default; a
-- test switch for now (round 35). `dock`, `air` and `event` choose the arrival (game.OPEN_STARTS;
-- air is the default, and a choice is kept: round 37 lost `air` at a restart). `at` moves the
-- arrival point for this run only.
-- `now` writes the open world start into the loaded save (one that has had the skip), saves it
-- to its slot (or `slot`) and reloads, with no new game.
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

-- ffrap_layout <text>: the chain of panels holding the on-screen text that holds <text>, to
-- the log (IDEAS.md, idea 14: where the item feed can go).
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

-- ffrap_notice <text>: try the game's quest-notice banner with our own text (experimental).
command("ffrap_notice", function(p)
    local text = table.concat(p or {}, " ")
    if text == "" then text = "Archipelago: test notice" end
    local ok, detail = game.QuestNotice(text)
    log("notice: " .. tostring(detail))
    if not ok then notify("Notice: " .. tostring(detail)) end
end)

-- ffrap_gate: experimental blocker and custom key-item probe (IDEAS.md, idea 16).
--   ffrap_gate spawn [combo|box|rock|pot|gate|world] [dist] [scale]
--   ffrap_gate item [id] [count]
--   ffrap_gate require <item|unit|flag|off> [id] [count]
--   ffrap_gate lock | unlock | clear | status
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
    -- The label keeps two states of one object apart (round 36: locked and normal input).
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

-- Open world probes (rounds 31 to 33, docs/open_world.md). None is saved: a game restart
-- undoes them.
--
-- ffrap_scale 30: every enemy at level 30. ffrap_scale 10 20: each enemy's own level, pulled
-- into 10 to 20. ffrap_scale party 2: pulled into 80% of the party's average level, plus or
-- minus 2 (the defaults; round 32 found "party 2 at 80" much better than "party 2").
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

-- Every rescale writes the changed rows to scale.txt (one enemy a line), so a hit seen in
-- battle can be matched with the stats behind it.
local function applyScale(mode, a, b, withBosses, knobs)
    log(string.format("scale: %s %s %s, hp %d%%, attack %d%%, magic %d%%%s: starting", mode, tostring(a), tostring(b),
        knobs.hp, knobs.attack, knobs.magic, withBosses and ", with bosses" or ""))
    local n, sample, lines, gameChanged = game.ScaleEnemies(mode, a, b, withBosses, knobs)
    if n == nil then return nil, sample end
    log("scale: " .. n .. " rows changed" .. (sample and ("; " .. sample) or ""))
    if gameChanged and gameChanged > 0 then
        log("scale: something else had changed " .. gameChanged .. " rows since our last write; their new values are the base now")
    end
    if mode == "off" then scaleLast = nil
    else
        local band = mode == "fixed" and ("every enemy at level " .. tostring(a))
            or string.format("levels %s to %s", tostring(math.max(1, a)), tostring(b))
        scaleLast = { mode = mode, a = a, b = b, withBosses = withBosses, knobs = knobs, text = band }
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
    -- No arguments: say what is in force. "show": one enemy's rows (round 33).
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
scaleTick = function()
    if not game.OnField() then return end
    -- Round 33: a battle showed a level the last rescale did not give (the FFR Randomizer mod had
    -- written the row again). If the table no longer holds what we wrote (loaded again, or written
    -- by something else), say so and write it again.
    scaleChecks = scaleChecks + 1
    if scaleLast and scaleChecks % SCALE_CHECK_EVERY == 0 then
        local checked, differ, sample, reloaded = game.ScaleCheck()
        if checked and (differ > 0 or reloaded) then
            log(string.format("scale: the table changed under us: %d of %d rows differ%s%s; writing it again", differ,
                checked, sample and (" (" .. sample .. ")") or "", reloaded and ", the table is a new object" or ""))
            local l = scaleLast
            if scaleFollow then scaleToParty(scaleFollow.range, scaleFollow.at, scaleFollow.withBosses, scaleFollow.knobs)
            else applyScale(l.mode, l.a, l.b, l.withBosses, l.knobs) end
        end
    end
    local f = scaleFollow
    if not f then return end
    local lv = game.PartyLevel()
    if not lv or lv == f.last then return end
    log("scale: party level " .. tostring(f.last) .. " -> " .. lv)
    f.last = lv
    scaleToParty(f.range, f.at, f.withBosses, f.knobs)
end

-- ffrap_noland list: every no-landing box on this map, to noland.txt.
-- ffrap_noland here: the boxes under you (seen from above).
-- ffrap_noland show [width] / hide: draw the boxes' outlines, or hide them again.
-- ffrap_noland lock <mysidia|gronoa|pharm>: that story box stops landing (its condition always
--   holds). unlock: it never holds. The box stays where the game put it. Every box with that
--   story condition is written.
-- ffrap_noland refresh: round 34 probe. The boxes we changed get their collision switched on
--   or off to match their condition now, to see if that applies them without landing.
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

-- ffrap_skip [slot]: skip the prologue on a new game (IDEAS.md, idea 2). Without a slot it only
-- changes the loaded save, so a snapshot can check it; with one it also saves to that slot and
-- reloads from it.
--
-- The skip is applied again right before saving. Round 8: the opening scene kept running after
-- a skip, turned flags 1 and 8 back on, and its autosave wrote the player's real position (the
-- prologue map) over the arrival point. Every step sets an absolute value, so applying it twice
-- is safe.
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

-- ffrap_input [fix]: probe for the opening's input lock (round 9: a skip during the opening
-- movie came up with no menus and no movement). Logs the player controller's input switches;
-- `fix` tries the engine's own resets, logging each step before it runs.
command("ffrap_input", function(p)
    log("input: " .. game.InputState())
    if p[1] == "fix" then
        local failed = game.InputFix(function(step) log("input step: " .. step) end)
        for _, f in ipairs(failed) do log("input: failed: " .. f) end
        log("input after fix: " .. game.InputState())
    end
    notify("Input state written to the log")
end)

-- ffrap_chats [done]: the loaded save's Active Time Chats, and `done` marks them all played (the
-- open world start does this by itself: round 37).
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

-- Round 42: the locks go in as the map loads, so a save loaded in the air has no moment to land.
if RegisterLoadMapPostHook then
    local okHook, errHook = pcall(RegisterLoadMapPostHook, function(_, world)
        local okRun, placed, why = pcall(function() return game.ContinentMapLoaded(world:get(), continentLocks == true) end)
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
        saveState()
        if not continentLocks then game.ContinentClear() end
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
    local text = (continentLocks and "on" or "off") .. "; " .. game.ContinentStatus()
    log("locks: " .. text)
    notify("Continent locks: " .. text)
end)

-- ffrap_visions: the first vision's synchro keys (round 37), for vision items on a save with none.
command("ffrap_visions", function()
    local text = game.VisionKeys()
    log("visions: " .. text)
    notify("Visions: " .. text)
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
if randomizerWarning then log(randomizerWarning) end

-- The fast check (IDEAS.md, idea 13): ten times a second, ask the chest pop-up's message widget
-- (kept once found) whether a pop-up has just come up. When one has, scan this map's chests at
-- once, so the check is reported and the pop-up rewritten within about 0.1 s, not on the next
-- one-second scan. Most passes are one widget lookup.
local function fastTick()
    if not game.InGame() or state.inGameTicks <= SETTLE_TICKS or not sessionSave() then return end
    if not game.PopupJustOpened() then return end
    local mapId = game.CurrentMap()
    if mapId and mapId == visit.mapId and visit.scans > MAP_SETTLE_SCANS then pcall(scanChests, mapId) end
    pcall(popupTick)
end

-- Both timers run on the game thread, from UE4SS's own game-thread timer (round 29). Up to 0.11.3
-- they ran from LoopAsync, whose callback runs on UE4SS's async thread. That thread ran Lua in
-- this mod's Lua state, ten times a second, while the game thread ran the queued tick in the same
-- state. Lua is not safe on two threads at once: the game crashed at random, after minutes or
-- hours, in a different place each time (a bad name, a broken Lua table, a bad object).
local function every(ms, name, fn)
    local function run()
        local ok, err = pcall(fn)
        if not ok then log(name .. " error: " .. tostring(err)) end
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
