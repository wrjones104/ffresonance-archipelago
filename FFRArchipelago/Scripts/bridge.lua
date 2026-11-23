-- bridge.lua: the file link between this mod and the Archipelago client.
--
-- UE4SS Lua can read and write files but has no sockets, so the mod and the client talk
-- through two append-only tab-separated text files in the mod folder.
--
--   ap_in.txt   client -> game
--     item <index> <kind> <id> <count> <label> [<flags> <name>]    kind: item | gil | vision | unit | flag | token (unused in game)
--                                                 flags: the item's Archipelago classification (1 progression,
--                                                 2 useful, 4 trap); name: the item's name as the label shows it
--     msg  <text>                                 shown on screen, not stored
--     client <world version> <build>              the client that wrote the file
--     cfg blank <0|1>                             chest blanking
--     cfg openworld <0|1>                         the open world start and continent locks
--     cfg party <unit,unit,...>                   the starting party, leader first
--     cfg shinies <0|1>                           shinies are locations: blank their rewards
--     cfg crystals <0|1>                          sanctum crystals are locations
--     cfg shards <0|1>                            Tablet Shard shinies are locations
--     cfg bosses <0|1>                            boss fights are locations
--     cfg chocobo <0|1>                           1: the open world save gets the Chocobo; 0: it is an item
--     cfg airship <0|1>                           1: start in the airship; 0: on foot with airship as an item (flag 1431)
--     cfg continent <name>                        the starting continent when starting on foot
--     cfg radar <0|1>                             the radar's 13 treasures are locations
--     cfg quests <0|1>                            side quests are locations: blank their rewards
--     cfg forge <0|1>                             Aileen's forge is locations: forge:1 to forge:8
--     cfg finalboss <have> <need> ...             the tower lock: characters, visions, Crystal Fragments
--     cfg goal <kind> <shards> <shards needed>    the goal (final_boss | tablet_shards), for the Archipelago page
--     cfg checks <done> <total>                   the slot's locations checked, for the Archipelago page
--     scout <base64>                              what a location holds: key, item, player, flags, own
--
--   ap_out.txt  game -> client
--     hello <mod version>                         the mod started
--     check <location key>                        e.g. chest:2031:7, boss:9079 (a battle group)
--     story <counter>                             the story counter changed
--     won <battle group>                          a victory that counts toward the goal (9056: final battle)
--     applied <index>                             item <index> was handled
--
-- The client may rewrite ap_in.txt from the start (for example after it reconnects and the
-- server resends every item). A file shorter than what was already read, or one with a new
-- first line (a new session), is read again from the top; items are kept by index, so reading
-- one twice grants nothing twice.

local B = {}

-- Round 74: the mod's version changes once per release, so its build (an FNV-1a hash of its
-- scripts) tells test installs apart. Carriage returns are skipped: a CRLF and an LF copy match.
-- tests/mod/test_main.py checks it against a Python copy of the same hash.
B.SCRIPTS = { "main.lua", "game.lua", "bridge.lua", "field_items.lua", "quests.lua", "gifts.lua" }

function B.build(dir)
    if B.buildId then return B.buildId end
    local h = 2166136261
    for _, name in ipairs(B.SCRIPTS) do
        local f = io.open(dir .. "Scripts/" .. name, "rb")
        if f then
            local text = f:read("a")
            f:close()
            for i = 1, #text do
                local c = text:byte(i)
                if c ~= 13 then h = ((h ~ c) * 16777619) & 0xffffffff end
            end
        end
    end
    B.buildId = string.format("%08x", h)
    return B.buildId
end

function B.init(dir)
    B.inPath = dir .. "ap_in.txt"
    B.outPath = dir .. "ap_out.txt"
    B.offset = 0
end

local function split(line)
    local fields = {}
    for field in (line .. "\t"):gmatch("(.-)\t") do
        fields[#fields + 1] = field
    end
    return fields
end
B.split = split

local B64 = {}
for i = 1, 64 do
    B64[("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"):byte(i)] = i - 1
end

function B.decodeBase64(s)
    local out = {}
    local buf, bits = 0, 0
    for i = 1, #s do
        local v = B64[s:byte(i)]
        if v then
            buf = (buf << 6) | v
            bits = bits + 6
            if bits >= 8 then
                bits = bits - 8
                out[#out + 1] = string.char((buf >> bits) & 0xff)
                buf = buf & ((1 << bits) - 1)
            end
        end
    end
    return table.concat(out)
end

-- New complete lines in ap_in.txt, each as a list of fields. A line still being written (no
-- newline yet) waits for the next call.
function B.readNew()
    local f = io.open(B.inPath, "rb")
    if not f then return {} end
    local size = f:seek("end")
    if size < B.offset then B.offset = 0 end
    -- The client resets the file for a new session with a new first line (the seed). Because the
    -- new file can already be longer than the old read offset, a changed first line resets reading
    -- from the top. Only a complete line with a trailing newline counts.
    f:seek("set", 0)
    local first = f:read("L")
    if first and first:sub(-1) == "\n" then
        first = first:gsub("\r?\n$", "")
        if B.first ~= nil and first ~= B.first then B.offset = 0 end
        B.first = first
    end
    f:seek("set", B.offset)
    local data = f:read("a") or ""
    f:close()
    local lastNewline = data:match(".*()\n")
    if not lastNewline then return {} end
    B.offset = B.offset + lastNewline
    local out = {}
    for line in data:sub(1, lastNewline):gmatch("([^\n]*)\n") do
        line = line:gsub("\r$", "")
        if line ~= "" then out[#out + 1] = split(line) end
    end
    return out
end

-- Appends one line to ap_out.txt. Tabs and newlines in a field would break the format, so they
-- become spaces.
function B.write(...)
    local fields = { ... }
    for i, v in ipairs(fields) do
        fields[i] = tostring(v):gsub("[\t\r\n]", " ")
    end
    local f = io.open(B.outPath, "a")
    if not f then return false end
    f:write(table.concat(fields, "\t"), "\n")
    f:close()
    return true
end

-- Every line already in ap_out.txt, so a restarted game knows what it already reported.
function B.readOut()
    local f = io.open(B.outPath, "rb")
    if not f then return {} end
    local data = f:read("a") or ""
    f:close()
    local out = {}
    for line in data:gmatch("([^\n]*)\n") do
        line = line:gsub("\r$", "")
        if line ~= "" then out[#out + 1] = split(line) end
    end
    return out
end

return B
