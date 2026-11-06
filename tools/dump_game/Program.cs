// dump_game: reads FINAL FANTASY RESONANCE's pak files and writes the game data as JSON.
//
// It reads the shipped game only (the base paks, not ~mods or LogicMods).
// The output goes to dump/ at the repo root, which git ignores: it is the game's own data.
// tools/gen_from_dump.py turns it into the data/*.tsv files that the apworld uses.
//
// Run from the repo root:
//   dotnet run --project tools/dump_game -- all
//   dotnet run --project tools/dump_game -- tables [path filter]
//   dotnet run --project tools/dump_game -- maps [path filter] [--classes <regex>]
//   dotnet run --project tools/dump_game -- assets <path prefix>
//   dotnet run --project tools/dump_game -- files | enums | text
// Options: --game <Paks dir>, --usmap <file>, --oodle <dll>, --out <dir>.
//
// It needs two files that the game does not ship:
// - Mappings.usmap: the property layout. UE4SS's UsmapDumperMod writes it to
//   FFRS/Binaries/Win64. FFR Modding Tools keeps one in workspace/mappings.
//   The newest of the two is used. Make a new one after each game patch.
// - The Oodle decompressor DLL. FFR Modding Tools has one in workspace/tools/oodle.

using System.Text.RegularExpressions;
using CUE4Parse.Compression;
using CUE4Parse.Encryption.Aes;
using CUE4Parse.FileProvider;
using CUE4Parse.MappingsProvider.Usmap;
using CUE4Parse.UE4.Assets.Exports;
using CUE4Parse.UE4.Assets.Exports.Engine;
using CUE4Parse.UE4.Localization;
using CUE4Parse.UE4.Objects.Core.Misc;
using CUE4Parse.UE4.Objects.UObject;
using CUE4Parse.UE4.Versions;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

var options = new Dictionary<string, string>();
var words = new List<string>();
for (var i = 0; i < args.Length; i++)
{
    if (args[i].StartsWith("--") && i + 1 < args.Length) options[args[i][2..]] = args[++i];
    else words.Add(args[i]);
}
var command = words.Count > 0 ? words[0] : "all";
var filter = words.Count > 1 ? words[1] : "";

var repo = FindRepo();
var steam = @"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY RESONANCE\FFRS";
var kit = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "FFR Modding Tools", "workspace");
var gameDir = options.GetValueOrDefault("game", Path.Combine(steam, "Content", "Paks"));
var outDir = options.GetValueOrDefault("out", Path.Combine(repo, "dump"));
var usmap = options.GetValueOrDefault("usmap") ?? NewestUsmap();
var oodle = options.GetValueOrDefault("oodle", Path.Combine(kit, "tools", "oodle", "oodle-data-shared.dll"));
var classes = new Regex(options.GetValueOrDefault("classes", "MapGimmick|TreasureBox|FieldItem|NPC|Npc|Door|Warp|Event|Trigger|Gate|Block|Airship|AirShip|Vehicle"));

if (usmap == null || !File.Exists(usmap)) Fail("No Mappings.usmap found. Pass --usmap, or turn on UE4SS's UsmapDumperMod and start the game once.");
if (!File.Exists(oodle)) Fail($"No Oodle DLL at {oodle}. Pass --oodle.");
Console.WriteLine($"game:  {gameDir}\nusmap: {usmap}\noodle: {oodle}\nout:   {outDir}");

OodleHelper.Initialize(oodle);
var provider = new DefaultFileProvider(gameDir, SearchOption.TopDirectoryOnly, new VersionContainer(EGame.GAME_UE5_6));
provider.MappingsContainer = new FileUsmapTypeMappingsProvider(usmap);
provider.Initialize();
provider.SubmitKey(new FGuid(), new FAesKey("0x" + new string('0', 64)));
provider.PostMount();
provider.LoadLocalization(ELanguage.English);
Console.WriteLine($"mounted {provider.Files.Count} files");

var json = new JsonSerializerSettings { Formatting = Formatting.Indented, ReferenceLoopHandling = ReferenceLoopHandling.Ignore };
var failures = new List<string>();
var classDefaults = new SortedDictionary<string, object>(StringComparer.Ordinal);

switch (command)
{
    case "all": DumpFiles(); DumpEnums(); DumpText(); DumpTables(); DumpMaps(); break;
    case "files": DumpFiles(); break;
    case "enums": DumpEnums(); break;
    case "text": DumpText(); break;
    case "tables": DumpTables(); break;
    case "maps": DumpMaps(); break;
    case "assets":
        if (filter == "") Fail("assets needs a path prefix, for example FFRS/Content/Data");
        DumpAssets(filter); break;
    default: Fail($"Unknown command {command}"); break;
}

File.WriteAllText(Path.Combine(outDir, "manifest.json"), JsonConvert.SerializeObject(new
{
    tool = "tools/dump_game",
    command, filter,
    usmap = Path.GetFileName(usmap),
    utocSize = new FileInfo(Path.Combine(gameDir, "FFRS-Windows.utoc")).Length,
    utocTime = File.GetLastWriteTimeUtc(Path.Combine(gameDir, "FFRS-Windows.utoc")).ToString("o"),
    failures,
}, json));
if (failures.Count > 0) Console.WriteLine($"{failures.Count} packages failed; see manifest.json");
return failures.Count > 0 ? 2 : 0;

// Every mounted path, one per line.
void DumpFiles()
{
    Write("files.txt", string.Join("\n", provider.Files.Keys.OrderBy(k => k, StringComparer.Ordinal)) + "\n");
    Console.WriteLine($"files: {provider.Files.Count}");
}

// Every enum in the mappings (native and Blueprint), as {name: {value: member}}.
// UE4SS hands enums back as numbers, so this is how the numbers get names.
void DumpEnums()
{
    var enums = new SortedDictionary<string, SortedDictionary<long, string>>(StringComparer.Ordinal);
    foreach (var (name, members) in provider.MappingsForGame!.Enums)
    {
        var map = new SortedDictionary<long, string>();
        foreach (var (value, member) in members) map[value] = member;
        enums[name] = map;
    }
    Write("enums.json", JsonConvert.SerializeObject(enums, json));
    Console.WriteLine($"enums: {enums.Count}");
}

// The English string table of the game, as {namespace: {key: text}}.
void DumpText()
{
    var count = 0;
    foreach (var path in provider.Files.Keys.Where(k => k.EndsWith(".locres") && k.Contains("/en/") && k.StartsWith("FFRS/")))
    {
        var resource = new FTextLocalizationResource(provider.CreateReader(path));
        var table = new SortedDictionary<string, SortedDictionary<string, string>>(StringComparer.Ordinal);
        foreach (var (ns, entries) in resource.Entries)
        {
            var inner = table[ns.Str] = new SortedDictionary<string, string>(StringComparer.Ordinal);
            foreach (var (key, entry) in entries) { inner[key.Str] = entry.LocalizedString; count++; }
        }
        Write(Path.Combine("text", Path.GetFileNameWithoutExtension(path) + ".json"), JsonConvert.SerializeObject(table, json));
    }
    Console.WriteLine($"text: {count} strings");
}

// Every DataTable in the game (CompositeDataTables too), one JSON file each.
void DumpTables()
{
    var paths = provider.Files.Keys
        .Where(k => k.StartsWith("FFRS/") && k.EndsWith(".uasset"))
        .Where(k => k.Contains("/Datatable/") || Regex.IsMatch(Path.GetFileName(k), "^C?DT_"))
        .Where(k => k.Contains(filter, StringComparison.OrdinalIgnoreCase))
        .OrderBy(k => k, StringComparer.Ordinal).ToList();
    var index = new List<object>();
    foreach (var path in paths)
    {
        var exports = Load(path);
        if (exports == null) continue;
        foreach (var table in exports.OfType<UDataTable>())
        {
            var rel = Path.ChangeExtension(path, ".json");
            Write(Path.Combine("tables", rel), JsonConvert.SerializeObject(table, json));
            index.Add(new { path = rel, @class = table.ExportType, rowStruct = table.RowStructName, rows = table.RowMap.Count });
        }
    }
    Write("tables/index.json", JsonConvert.SerializeObject(index, json));
    Console.WriteLine($"tables: {index.Count} of {paths.Count} packages");
}

// The actors on every map whose class matches --classes (chests, field items, NPCs, doors...).
// One JSON file per map, with each actor's properties and its root component's location.
void DumpMaps()
{
    var paths = provider.Files.Keys
        .Where(k => k.StartsWith("FFRS/") && k.EndsWith(".umap") && k.Contains(filter, StringComparison.OrdinalIgnoreCase))
        .OrderBy(k => k, StringComparer.Ordinal).ToList();
    var index = new List<object>();
    foreach (var path in paths)
    {
        var exports = Load(path);
        if (exports == null) continue;
        var actors = new JArray();
        foreach (var export in exports)
        {
            var cls = export.Class?.Name.Text ?? export.ExportType;
            if (!classes.IsMatch(cls) || export.Outer?.Name.Text != "PersistentLevel") continue;
            var actor = JObject.Parse(JsonConvert.SerializeObject(export, json));
            try { AddClassDefaults(export.Class?.Load() as UStruct); }
            catch (Exception e) { failures.Add($"{path}: class {cls}: {e.GetType().Name}: {e.Message}"); }
            if (export.TryGetValue(out UObject root, "RootComponent"))
                actor["RootLocation"] = JToken.Parse(JsonConvert.SerializeObject(root.GetOrDefault<object>("RelativeLocation"), json));
            actors.Add(actor);
        }
        if (actors.Count == 0) continue;
        var rel = Path.ChangeExtension(path, ".json");
        Write(Path.Combine("maps", rel), actors.ToString(Formatting.Indented));
        index.Add(new { path = rel, actors = actors.Count });
    }
    Write("maps/index.json", JsonConvert.SerializeObject(index, json));
    Write("maps/classes.json", JsonConvert.SerializeObject(classDefaults, json));
    Console.WriteLine($"maps: {index.Count} of {paths.Count} have matching actors, {classDefaults.Count} classes");
}

// A placed actor only stores what differs from its class, so the class defaults
// (and its parents', up to the native class) are kept too: {class: {super, defaults}}.
void AddClassDefaults(UStruct? cls)
{
    while (cls != null && !classDefaults.ContainsKey(cls.Name))
    {
        object? defaults = null;
        string? super = null;
        UStruct? next = null;
        try
        {
            if (cls is UClass c && c.ClassDefaultObject != null && c.ClassDefaultObject.TryLoad(out UObject cdo))
                defaults = JToken.Parse(JsonConvert.SerializeObject(cdo, json))["Properties"];
        }
        catch (Exception e) { defaults = $"unreadable: {e.GetType().Name}"; }
        try
        {
            super = cls.SuperStruct?.Name;
            next = cls.SuperStruct?.Load<UStruct>();
        }
        catch (Exception) { next = null; }
        classDefaults[cls.Name] = new { super, defaults };
        cls = next;
    }
}

// Any packages under a path prefix, all exports, one JSON file each.
void DumpAssets(string prefix)
{
    var paths = provider.Files.Keys
        .Where(k => k.StartsWith(prefix, StringComparison.OrdinalIgnoreCase) && (k.EndsWith(".uasset") || k.EndsWith(".umap")))
        .OrderBy(k => k, StringComparer.Ordinal).ToList();
    var written = 0;
    foreach (var path in paths)
    {
        var exports = Load(path);
        if (exports == null) continue;
        Write(Path.Combine("assets", Path.ChangeExtension(path, ".json")), JsonConvert.SerializeObject(exports, json));
        written++;
    }
    Console.WriteLine($"assets: {written} of {paths.Count}");
}

List<UObject>? Load(string path)
{
    try { return provider.LoadPackage(path).GetExports().ToList(); }
    catch (Exception e)
    {
        failures.Add($"{path}: {e.GetType().Name}: {e.Message}");
        return null;
    }
}

void Write(string rel, string text)
{
    var full = Path.Combine(outDir, rel);
    Directory.CreateDirectory(Path.GetDirectoryName(full)!);
    File.WriteAllText(full, text);
}

string? NewestUsmap()
{
    var candidates = new List<string>();
    var kitMappings = Path.Combine(kit, "mappings");
    if (Directory.Exists(kitMappings)) candidates.AddRange(Directory.GetFiles(kitMappings, "*.usmap"));
    var dumped = Path.Combine(steam, "Binaries", "Win64", "Mappings.usmap");
    if (File.Exists(dumped)) candidates.Add(dumped);
    return candidates.OrderByDescending(File.GetLastWriteTimeUtc).FirstOrDefault();
}

static string FindRepo()
{
    for (var dir = new DirectoryInfo(Directory.GetCurrentDirectory()); dir != null; dir = dir.Parent)
        if (File.Exists(Path.Combine(dir.FullName, "CLAUDE.md")) && Directory.Exists(Path.Combine(dir.FullName, "apworld")))
            return dir.FullName;
    return Directory.GetCurrentDirectory();
}

static void Fail(string message)
{
    Console.Error.WriteLine(message);
    Environment.Exit(1);
}
