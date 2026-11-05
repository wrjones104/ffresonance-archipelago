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
--   ffrap_skip [slot]            skip the prologue on a new game; with a slot, save there and reload
--   ffrap_inspect <class|path>   one object's fields and functions to inspect_<name>.tsv
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
--
-- Each client session belongs to its saves. A new game started from the Archipelago entry on
-- the title menu is linked to it at once and skips the prologue by itself (plain New Game stays
-- vanilla); an existing save is linked with ffrap_bind or the client's /bind. The link
-- follows the save slots the linked game is saved to. While any other save is loaded, the mod
-- grants nothing, reports nothing and leaves the chests vanilla.

local VERSION = "0.10.1"
local PROTOCOL = 1        -- the bridge protocol; the apworld's MOD_PROTOCOL

local MOD_DIR = (debug.getinfo(1, "S").source:gsub("^@", ""):gsub("\\", "/"):match("^(.*/)Scripts/[^/]+$"))
    or "ue4ss/Mods/FFRArchipelago/"

local game = require("game")
local bridge = require("bridge")

local TICK_MS = 500
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

-- On-screen messages go to the item feed on the field HUD (IDEAS.md, idea 14) when it is on and
-- the HUD is there. Otherwise they wait in a short queue for the HUD (loading, a map change),
-- and off the field (the title screen) they go to ModSettings' Toast as before.
local FEED_QUEUE_MAX = 20
local FEED_WAIT_MAX = 10     -- seconds messages wait for the feed before they go to the Toast
-- On unless switched off: it works since 0.9.5 (round 23), and messages it cannot show go to
-- the Toast after FEED_WAIT_MAX.
local feedOn = true          -- ffrap_feed on|off; kept in ap_state.txt
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

local function applyItems()
    local done, names = 0, {}
    while done < MAX_GRANTS_PER_TICK do
        local it = state.items[state.applied]
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
        state.applied = state.applied + 1
        state.lastResult = it.label .. ": " .. code
        done = done + 1
        saveState()
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

-- The chest pop-up ("You obtained the following:") is up while a chest's check is reported, so
-- each chest check starts a look for its text (15 s) until it has been found once in this run;
-- the panels holding it are logged once (IDEAS.md, idea 13).
local DIALOG_TEXT = "obtained"
local dialogProbe = { ticks = 0, done = false }

local function probeDialog()
    if dialogProbe.done or dialogProbe.ticks <= 0 then return end
    dialogProbe.ticks = dialogProbe.ticks - 1
    local chain = game.LayoutOf(DIALOG_TEXT)
    if chain then
        dialogProbe.done = true
        for i, line in ipairs(chain) do log("chest pop-up layout " .. i .. ": " .. line) end
    elseif dialogProbe.ticks == 0 then
        log("chest pop-up: no on-screen text holding \"" .. DIALOG_TEXT .. "\" was found; the next chest tries again")
    end
end

local function opened(key)
    if not sessionSave() then return end
    if report("check", key) then
        log("check " .. key)
        if not dialogProbe.done and dialogProbe.ticks == 0 and key:find("^chest:") then dialogProbe.ticks = 30 end
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
local function runSkip(slot, why)
    local obj, story = game.SaveObjectName(), game.StoryCounter()
    if skipped ~= obj and (not story or story > game.SKIP_FROM_MAX) then
        notify("ffrap_skip works on a new game only (story " .. tostring(story) .. ", must be "
            .. game.SKIP_FROM_MAX .. " or lower)")
        return false
    end
    if skipped ~= obj and story < game.SKIP_FROM_MIN then
        notify("Wait until you can move (story " .. game.SKIP_FROM_MIN .. ", now " .. story .. "): a skip during "
            .. "the opening movie leaves you without menus or movement")
        return false
    end
    local again = skipped == obj
    local okRun, ok, report = pcall(game.SkipPrologue, { inventory = not again })
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
    local saved, detail = game.SaveAndReload(slot)
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
        if state.inGameTicks == 1 then log("save loaded, map " .. tostring(game.CurrentMap())) end
        if state.inGameTicks > SETTLE_TICKS then
            followSave()
            if state.bindPending then
                state.bindPending = false
                bindLoaded()
            end
            autoSkip()
            pcall(probeDialog)
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

-- ffrap_inspect <class or path>: one object's fields and functions to inspect_<name>.tsv.
command("ffrap_inspect", function(p)
    local target = p and p[1]
    if not target then
        notify("Usage: ffrap_inspect <class name or object path>")
        return
    end
    local name = target:gsub("^.*[/.]", ""):gsub("[^%w_%-]", "")
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
        notify("Usage: ffrap_skip [slot]   (0 is the autosave)")
        return
    end
    if not game.InGame() then
        notify("Start a new game first")
        return
    end
    followSave()
    runSkip(slot, "command")
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
