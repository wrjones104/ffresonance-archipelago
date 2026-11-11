-- bridge.lua: the file link between this mod and the Archipelago client.
--
-- UE4SS Lua can read and write files but has no sockets, so the mod and the client (a Python
-- program, the fake server in tools/ for now) talk through two append-only text files in the
-- mod folder. Each line is tab-separated fields.
--
--   ap_in.txt   client -> game
--     item <index> <kind> <id> <count> <label>    kind: item | vision | unit | flag
--     msg  <text>                                 shown on screen, not stored
--     client <world version>                      the client that wrote the file (0.7.1)
--     cfg blank <0|1>                             chest blanking
--     cfg openworld <0|1>                         the open world start and continent locks (0.25.0)
--     cfg party <unit,unit,...>                   the starting party, leader first (0.25.0)
--     cfg shinies <0|1>                           shinies are locations: blank their rewards (0.29.0)
--     cfg crystals <0|1>                          sanctum crystals are locations (0.29.0)
--     cfg shards <0|1>                            Tablet Shard shinies are locations (0.30.0)
--     cfg chesticons <0|1|2>                      mini-map chest icons: off, on, with the Chest Radar (0.46.0)
--     scout <base64>                              what a location holds: key, item, player, flags, own (0.11.0)
--
--   ap_out.txt  game -> client
--     hello <mod version>                         the mod started
--     check <location key>                        e.g. chest:2031:7
--     story <counter>                             the story counter changed
--     won <battle group>                          a battle that matters was won: 9056, the last one (0.45.0)
--     applied <index>                             item <index> was handled
--
-- The client may rewrite ap_in.txt from the start (for example after it reconnects and the
-- server resends every item). A file shorter than what was already read, or one with a new
-- first line (a new session), is read again from the top; items are kept by index, so reading
-- one twice grants nothing twice.

local B = {}

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
    -- The client starts the file over for a new session with a new first line (the seed). The
    -- new file can already be longer than what was read of the old one, so a change of first
    -- line also means reading from the top (0.7.0).
    -- Only a complete first line counts: one still being written has no newline after it yet.
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
