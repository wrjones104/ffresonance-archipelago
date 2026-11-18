"""Final Fantasy Resonance client: connects the FFRArchipelago mod to an Archipelago server.

The mod and this client talk through two text files in the mod folder (see the repo's README,
"Bridge format"). This client:
  * writes every item the server sends into ap_in.txt, numbered by its Archipelago index, after a
    `seed` line naming the seed and slot, plus `cfg blank 1` so the mod blanks vanilla chest
    rewards;
  * scouts the slot's locations once per session (no hints are made) and writes a `scout` line
    for each, so the mod can say in the chest pop-up what a chest holds and for whom;
  * reads ap_out.txt and sends each `check` the mod reports as a LocationCheck. Only lines after
    the mod's own `seed` line for this seed and slot count, so checks from another seed or from
    before connecting are ignored;
  * sends the goal once enough Tablet Shards have been received, or once a `story` report reaches
    the goal checkpoint, whichever the seed asks for.
"""

from __future__ import annotations

import asyncio
import base64
import os
import re
import sys
from typing import Any

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, handle_url_arg,
                          logger, server_loop)
from NetUtils import ClientStatus, NetworkItem

from .data import FRAGMENT_ITEM, ITEMS
from .locations import LOCATION_KEY_TO_ID
from .version import world_build, world_version

LOCATION_ID_TO_KEY = {location_id: key for key, location_id in LOCATION_KEY_TO_ID.items()}

GAME = "Final Fantasy Resonance"
POLL_SECONDS = 0.5
GOAL_MESSAGE = "Goal complete!"
GOAL_MESSAGE_LINE = f"msg\t{GOAL_MESSAGE}"
SHARD_GOAL = "tablet_shards"
FINAL_GOAL = "final_boss"
FINAL_BATTLE = 9056   # Rain against Sol, reported by the mod as `won 9056`
ENDING_STORY = 9000   # the ending sets this after its scenes: the goal if the win was missed
SHARD_ITEM = next(ap_id for ap_id, info in ITEMS.items() if info["name"] == "Tablet Shard")
OUT_HEAD_BYTES = 256  # the mod's hello and seed lines open the file, well inside this


def clean(text: Any) -> str:
    return " ".join(str(text).split())


def with_count(name: str, held: int, need: int) -> str:
    """An item's name with its goal count. Past the need, only the count shows."""
    return f"{name} ({held}/{need})" if held <= need else f"{name} ({held})"


def encode_scout(key: str, name: str, player: str, flags: Any, own: int) -> str:
    raw = "\t".join(clean(x) for x in (key, name, player, flags, own))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def decode_scout(encoded: str) -> list[str]:
    return base64.b64decode(encoded.encode("ascii")).decode("utf-8").split("\t")


def out_file_head(start: bytes) -> bytes:
    """The start of ap_out.txt through its first `seed` line, or b"" if that line is not there yet.
    The mod starts the file over for a new session with its hello and seed lines, so a new head
    means a new file."""
    end = 0
    for line in start.split(b"\n")[:-1]:
        end += len(line) + 1
        if line.startswith(b"seed\t"):
            return start[:end]
    return b""


class FFResonanceCommandProcessor(ClientCommandProcessor):
    ctx: FFResonanceContext

    def _cmd_modfolder(self, path: str = "") -> bool:
        """Show the FFRArchipelago mod folder, or set it for this session."""
        if path:
            self.ctx.set_mod_folder(path)
        self.output(f"Mod folder: {self.ctx.mod_folder}")
        return True

    def _cmd_resync(self) -> bool:
        """Ask the mod to report every chest and shiny the save says is looted, and resend all checks."""
        self.ctx.write_line("sync")
        self.ctx.out_offset = 0
        self.ctx.out_scope = None
        self.ctx.out_head = b""
        self.output("Resync requested.")
        return True

    def _cmd_bind(self) -> bool:
        """Link the save that is loaded in the game to this seed. A new game is linked by itself."""
        if self.ctx.session_key is None:
            self.output("Connect to the server first.")
            return False
        self.ctx.write_line("bind")
        self.output("Asked the mod to link the loaded save to this seed. Watch for the message in game.")
        return True


class FFResonanceContext(CommonContext):
    game = GAME
    items_handling = 0b111          # every item for this slot comes from the server, own items too
    want_slot_data = True
    command_processor = FFResonanceCommandProcessor

    def __init__(self, server_address: str | None, password: str | None, mod_folder: str) -> None:
        super().__init__(server_address, password)
        self.mod_folder = ""
        self.set_mod_folder(mod_folder)
        self.session_key: str | None = None   # "<seed name>:<team>:<slot>" once connected
        self.room_seed_name: str | None = None  # captured from RoomInfo because AP 0.6.7 does not store it
        self.goal = 8050
        self.goal_kind = "story_checkpoint"
        self.shards_needed = 99
        self.items_written = 0                # item lines already in ap_in.txt for this session
        self.slot_data: dict = {}             # the Connected packet's, to write the seed's settings again
        self.out_offset = 0
        self.out_scope: str | None = None     # the seed key the ap_out.txt lines being read belong to
        self.out_head = b""                   # out_file_head of the ap_out.txt being read
        self.max_story = 0
        self.battles_won: set[int] = set()
        self.mod_version: str | None = None
        self.goal_announced = False           # the in-game toast was sent; a reconnect re-sends only the status
        self.scouts_written = False           # scout lines are in ap_in.txt for this session
        self.starting_party: list[int] = []
        self.lock_needs = (0, 0, 0)           # the final boss lock: characters, visions, Crystal Fragments
        self.lock_written: tuple | None = None  # the last finalboss line written
        self.progress_written: dict[str, tuple] = {}  # the last goal and checks lines written

    # -- files ------------------------------------------------------------------------------------

    def set_mod_folder(self, path: str) -> None:
        self.mod_folder = resolve_mod_folder(path)
        self.in_path = os.path.join(self.mod_folder, "ap_in.txt")
        self.out_path = os.path.join(self.mod_folder, "ap_out.txt")

    def write_line(self, *fields: Any) -> None:
        with open(self.in_path, "a", encoding="utf-8", newline="\n") as f:
            f.write("\t".join(clean(x) for x in fields) + "\n")

    def start_session(self) -> None:
        """Makes ap_in.txt belong to this seed and slot. A file for another session is replaced."""
        if not os.path.isdir(self.mod_folder):
            logger.error(f"Mod folder not found: {self.mod_folder}. Set it with /modfolder <path>.")
            return
        if not is_mod_folder(self.mod_folder):
            logger.warning(f"{self.mod_folder} has no Scripts/main.lua, so the mod will not see the client. "
                           f"Point /modfolder at the FFRArchipelago folder.")
        header = f"seed\t{self.session_key}"
        existing: list[str] = []
        if os.path.exists(self.in_path):
            with open(self.in_path, encoding="utf-8") as f:
                existing = f.read().splitlines()
        if existing and existing[0] == header:
            self.items_written = 0
            self.goal_announced = False
            self.scouts_written = False
            for line in existing:
                if line.startswith("item\t"):
                    self.items_written += 1
                elif line.startswith("scout\t"):
                    self.scouts_written = True
                elif line == GOAL_MESSAGE_LINE:
                    self.goal_announced = True
        else:
            if existing:
                logger.info("ap_in.txt belonged to another seed or slot; starting it over.")
            with open(self.in_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(header + "\n")
            self.write_line("cfg", "blank", 1)
            self.items_written = 0
            self.goal_announced = False
            self.scouts_written = False
        # Record the client version for the mod's log.
        self.write_line("client", world_version(), world_build())
        self.out_offset = 0
        self.out_scope = None
        self.out_head = b""

    def restore_session_file(self) -> bool:
        """Round 77: ap_in.txt deleted while connected (the user cleared it for a new seed with the
        client open) left the mod with no seed line, and its new game started without the seed.
        Writes the session again: seed, settings, every item from index 0, and the scouts."""
        if os.path.exists(self.in_path) or not os.path.isdir(self.mod_folder):
            return False
        logger.info("ap_in.txt was deleted; writing this seed's session to it again.")
        self.start_session()
        self.write_config(self.slot_data)
        self.lock_written = None
        self.progress_written = {}
        self.scout_locations()
        return True

    def write_config(self, slot_data: dict) -> None:
        """The seed's start settings, for the mod's next Archipelago new game. Written once."""
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return
        wanted = [("cfg", "openworld", int(bool(slot_data.get("open_world"))))]
        wanted.append(("cfg", "shinies", int(bool(slot_data.get("include_shinies")))))
        wanted.append(("cfg", "crystals", int(bool(slot_data.get("include_crystals")))))
        wanted.append(("cfg", "shards", int(bool(slot_data.get("include_tablet_shards")))))
        wanted.append(("cfg", "bosses", int(bool(slot_data.get("include_bosses")))))
        # Legacy seeds without this option started with the Chocobo.
        wanted.append(("cfg", "chocobo", int(bool(slot_data.get("start_with_chocobo", True)))))
        wanted.append(("cfg", "radar", int(bool(slot_data.get("include_radar_treasures")))))
        wanted.append(("cfg", "quests", int(bool(slot_data.get("include_side_quests")))))
        # Legacy seeds without this option started in the airship.
        wanted.append(("cfg", "airship", int(bool(slot_data.get("start_with_airship", True)))))
        if slot_data.get("starting_continent"):
            wanted.append(("cfg", "continent", str(slot_data["starting_continent"]).lower()))
        party = slot_data.get("starting_party") or []
        if party:
            wanted.append(("cfg", "party", ",".join(str(unit) for unit in party)))
        with open(self.in_path, encoding="utf-8") as f:
            existing = set(f.read().splitlines())
        for fields in wanted:
            if "\t".join(clean(x) for x in fields) not in existing:
                self.write_line(*fields)

    def write_new_items(self) -> None:
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return
        # The server may resend the whole list (index 0); lines already written stay valid.
        if len(self.items_received) <= self.items_written:
            return
        new = self.items_received[self.items_written:]
        earlier = self.items_received[:self.items_written]
        shards = sum(1 for item in earlier if item.item == SHARD_ITEM)
        members, visions, fragments = self.lock_holdings(earlier)
        need_members, need_visions, need_fragments = self.lock_needs
        for index, item in enumerate(new, start=self.items_written):
            info = ITEMS.get(item.item)
            if info is None:
                logger.warning(f"Unknown item id {item.item}; skipped")
                self.write_line("msg", f"Unknown Archipelago item {item.item}")
                continue
            sender = self.player_names.get(item.player, f"player {item.player}")
            name = info["name"]
            if item.item == SHARD_ITEM and self.goal_kind == SHARD_GOAL:
                shards += 1
                name = with_count(name, shards, self.shards_needed)
            elif item.item == FRAGMENT_ITEM:
                fragments += 1
                name = with_count(name, fragments, need_fragments)
            # Party members and visions show a count only when the final boss lock asks for them.
            elif info["category"] == "party" and need_members:
                members.add(info["game_id"])
                name = with_count(name, len(members), need_members)
            elif info["category"] == "vision" and need_visions:
                visions.add(info["game_id"])
                name = with_count(name, len(visions), need_visions)
            label = name if item.player == self.slot else f"{name} from {sender}"
            self.write_line("item", index, info["kind"], info["game_id"], info["count"], label)
        self.items_written = len(self.items_received)

    def lock_holdings(self, received: list[NetworkItem]) -> tuple[set[int], set[int], int]:
        """Party members held (the starting party and every member received), the visions and the
        number of Crystal Fragments in `received`."""
        members = set(self.starting_party)
        visions = set()
        for item in received:
            info = ITEMS.get(item.item)
            if info and info["category"] == "party":
                members.add(info["game_id"])
            elif info and info["category"] == "vision":
                visions.add(info["game_id"])
        fragments = sum(1 for item in received if item.item == FRAGMENT_ITEM)
        return members, visions, fragments

    def lock_counts(self) -> tuple[int, int, int]:
        members, visions, fragments = self.lock_holdings(self.items_received)
        return len(members), len(visions), fragments

    def write_lock(self) -> None:
        """Send final-boss lock progress to the mod whenever the counts change."""
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return
        characters, visions, fragments = self.lock_counts()
        line = (characters, self.lock_needs[0], visions, self.lock_needs[1], fragments, self.lock_needs[2])
        if line != self.lock_written:
            self.write_line("cfg", "finalboss", *line)
            self.lock_written = line

    def write_progress(self) -> None:
        """The goal and the checks done, for the mod's Archipelago page, whenever they change."""
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return
        done = len(self.checked_locations)
        lines = [("cfg", "goal", self.goal_kind, self.shards_received(), self.shards_needed),
                 ("cfg", "checks", done, done + len(self.missing_locations))]
        for line in lines:
            if line != self.progress_written.get(line[1]):
                self.write_line(*line)
                self.progress_written[line[1]] = line

    def shards_received(self) -> int:
        return sum(1 for item in self.items_received if item.item == SHARD_ITEM)

    def goal_reached(self) -> bool:
        if self.goal_kind == SHARD_GOAL:
            return self.shards_received() >= self.shards_needed
        if self.goal_kind == FINAL_GOAL:
            return FINAL_BATTLE in self.battles_won or self.max_story >= ENDING_STORY
        return self.max_story >= self.goal        # legacy story-checkpoint goal

    def goal_text(self) -> str:
        if self.goal_kind == SHARD_GOAL:
            return f"{self.shards_needed} Tablet Shards ({self.shards_received()} so far)"
        if self.goal_kind == FINAL_GOAL:
            return "the last battle, Rain against Sol"
        return f"story checkpoint {self.goal}"

    def read_new_output(self) -> tuple[set[int], int | None]:
        """New checks and the highest story counter in ap_out.txt for this session."""
        checks: set[int] = set()
        story: int | None = None
        if not os.path.exists(self.out_path):
            return checks, story
        size = os.path.getsize(self.out_path)
        with open(self.out_path, "rb") as f:
            head = out_file_head(f.read(OUT_HEAD_BYTES))
            # The mod starts the file over for a new session. Round 83: a size check alone missed
            # it. The client read the old seed's short file, and the new one was longer by its
            # next poll, so the new seed line was skipped and every check after it was dropped.
            if size < self.out_offset or (self.out_head and head != self.out_head):
                self.out_offset, self.out_scope = 0, None
            self.out_head = head
            f.seek(self.out_offset)
            data = f.read()
        end = data.rfind(b"\n") + 1
        self.out_offset += end
        for raw in data[:end].decode("utf-8", "replace").splitlines():
            fields = raw.rstrip("\r").split("\t")
            if len(fields) < 2:
                continue
            kind, val = fields[0], fields[1]
            if kind == "hello":
                self.mod_version = val
            elif kind == "seed":
                self.out_scope = val
            elif self.out_scope != self.session_key or self.session_key is None:
                continue
            elif kind == "check":
                location = LOCATION_KEY_TO_ID.get(val)
                if location is not None:
                    checks.add(location)
            elif kind == "story" and val.lstrip("-").isdigit():
                story = max(story or 0, int(val))
            elif kind == "won" and val.isdigit():
                self.battles_won.add(int(val))
        return checks, story

    def write_scouts(self, items: list) -> int:
        """A Base64-encoded `scout` line per location of this slot: what it holds and for whom.

            scout <base64(location key \t item name \t player name \t flags \t own: 1 or 0)>
        """
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return 0
        written = 0
        for raw in items:
            item = raw if isinstance(raw, NetworkItem) else NetworkItem(*raw)
            key = LOCATION_ID_TO_KEY.get(item.location)
            if key is None:
                continue
            name = self.item_names.lookup_in_slot(item.item, item.player)
            player = self.player_names.get(item.player, f"player {item.player}")
            self.write_line("scout", encode_scout(key, name, player, item.flags, int(item.player == self.slot)))
            written += 1
        if written:
            self.scouts_written = True
        return written

    def scout_locations(self) -> None:
        """Ask the server what this slot's locations hold, without making hints, once per session."""
        if self.scouts_written or self.session_key is None:
            return
        locations = sorted(set(self.server_locations) & set(LOCATION_ID_TO_KEY))
        if locations:
            asyncio.create_task(self.send_msgs([{"cmd": "LocationScouts", "locations": locations,
                                                 "create_as_hint": 0}]))

    # -- server -----------------------------------------------------------------------------------

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "RoomInfo":
            self.room_seed_name = args.get("seed_name")
        elif cmd == "Connected":
            slot_data = args.get("slot_data") or {}
            self.slot_data = slot_data
            self.goal = int(slot_data.get("goal_story_checkpoint", 8050))
            self.goal_kind = str(slot_data.get("goal", "story_checkpoint"))    # default for legacy seeds without "goal"
            self.shards_needed = int(slot_data.get("tablet_shards_required", 99))
            self.starting_party = [int(unit) for unit in slot_data.get("starting_party") or []]
            self.lock_needs = (int(slot_data.get("final_boss_characters", 0)), int(slot_data.get("final_boss_visions", 0)),
                               int(slot_data.get("final_boss_fragments", 0)))
            self.lock_written = None
            self.progress_written = {}
            # Round 74: the version stays the same between releases, so a seed made with another
            # test build of the apworld is told apart by its build.
            seed_build = slot_data.get("world_build")
            if seed_build and seed_build != world_build():
                logger.warning(f"This seed was made with apworld build {seed_build}, and this client is build "
                               f"{world_build()}. Use the same .apworld for both, or generate the seed again.")
            # AP 0.6.7 leaves seed_name unset, so fall back to the captured RoomInfo name.
            seed = getattr(self, "server_seed_name", None) or self.room_seed_name or self.seed_name
            if not seed:
                # Without a seed name every seed would share one session key, and the mod would
                # skip a new seed's items as already applied. Stay off the bridge instead.
                self.session_key = None
                logger.error("The server sent no seed name, so the game is not connected. Reconnect to try again.")
                return
            self.session_key = f"{seed}:{self.team}:{self.slot}"
            self.max_story = 0
            self.battles_won = set()
            self.start_session()
            self.write_config(slot_data)
            self.scout_locations()
            logger.info(f"Goal: {self.goal_text()}. Mod folder: {self.mod_folder}")
        elif cmd == "LocationInfo":
            self.write_scouts(args.get("locations") or [])
        elif cmd == "PrintJSON" and args.get("type") == "ItemSend" and self.slot is not None:
            item, receiver = args.get("item"), args.get("receiving")
            if item is not None and item.player == self.slot and receiver != self.slot:
                name = self.item_names.lookup_in_slot(item.item, receiver)
                self.write_line("msg", f"Sent {name} to {self.player_names.get(receiver, receiver)}")

    def reset_server_state(self) -> None:
        super().reset_server_state()
        self.session_key = None
        self.room_seed_name = None

    def make_gui(self):
        ui = super().make_gui()
        ui.base_title = "Archipelago Final Fantasy Resonance Client"
        return ui


async def game_loop(ctx: FFResonanceContext) -> None:
    while not ctx.exit_event.is_set():
        try:
            if ctx.session_key is not None and ctx.slot is not None:
                ctx.restore_session_file()
                ctx.write_new_items()
                ctx.write_lock()
                ctx.write_progress()
                checks, story = ctx.read_new_output()
                if checks:
                    sent = await ctx.check_locations(checks)
                    # if sent:
                    #     logger.info(f"Sent {len(sent)} check(s)") #enable if you want check confirmation in client
                if story is not None and story > ctx.max_story:
                    ctx.max_story = story
                if not ctx.finished_game and ctx.goal_reached():
                    await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                    ctx.finished_game = True
                    logger.info(f"Goal complete: {ctx.goal_text()}")
                    if not ctx.goal_announced:
                        ctx.write_line("msg", GOAL_MESSAGE)
                        ctx.goal_announced = True
        except OSError as e:
            logger.warning(f"Bridge file error: {e}")
        await asyncio.sleep(POLL_SECONDS)


MOD_IN_LIBRARY = os.path.join("steamapps", "common", "FINAL FANTASY RESONANCE", "FFRS", "Binaries", "Win64",
                              "ue4ss", "Mods", "FFRArchipelago")


def is_mod_folder(path: str) -> bool:
    return os.path.isfile(os.path.join(path, "Scripts", "main.lua"))


def resolve_mod_folder(path: str) -> str:
    """The FFRArchipelago folder, given that folder or the UE4SS Mods folder that holds it."""
    path = os.path.abspath(os.path.expanduser(path))
    inner = os.path.join(path, "FFRArchipelago")
    if not is_mod_folder(path) and is_mod_folder(inner):
        return inner
    return path


def steam_mod_folders() -> list[str]:
    """The FFRArchipelago folder in each Steam library that has one, read from Steam's library list."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam = winreg.QueryValueEx(key, "SteamPath")[0]
        with open(os.path.join(steam, "steamapps", "libraryfolders.vdf"), encoding="utf-8") as f:
            vdf = f.read()
    except (ImportError, OSError):  # not Windows, or no Steam install
        return []
    return library_mod_folders(steam, vdf)


def library_mod_folders(steam: str, vdf: str) -> list[str]:
    # The vdf escapes backslashes: "path"		"D:\\SteamLibrary"
    libraries = [steam] + [p.replace("\\\\", "\\") for p in re.findall(r'"path"\s+"([^"]+)"', vdf)]
    # Steam's own folder is usually in the list too, spelled differently.
    unique = dict.fromkeys(os.path.normcase(os.path.normpath(lib)) for lib in libraries)
    return [folder for folder in (os.path.join(lib, MOD_IN_LIBRARY) for lib in unique) if is_mod_folder(folder)]


def default_mod_folder() -> str:
    """host.yaml's mod folder. When the mod is not there, the first Steam library that has it."""
    try:
        from .world import FFResonanceWorld
        configured = str(FFResonanceWorld.settings.mod_folder)
    except Exception:  # settings unavailable (e.g. no host.yaml yet)
        configured = os.path.join(".", "FFRArchipelago")
    if is_mod_folder(resolve_mod_folder(configured)):
        return configured
    found = steam_mod_folders()
    if found:
        logger.info(f"No mod in {configured} (host.yaml). Found it in a Steam library: {found[0]}")
        return found[0]
    return configured


def launch_client(*args: str) -> None:
    Utils.init_logging("FFResonanceClient", exception_logger="Client")

    async def main(parsed) -> None:
        ctx = FFResonanceContext(parsed.connect, parsed.password, parsed.modfolder or default_mod_folder())
        logger.info(f"Final Fantasy Resonance client, world version {world_version()} (build {world_build()})")
        if parsed.name:
            ctx.auth = parsed.name
        ctx.server_task = asyncio.create_task(server_loop(ctx), name="server loop")
        if gui_enabled and not getattr(parsed, "nogui", False):
            ctx.run_gui()
        ctx.run_cli()
        loop_task = asyncio.create_task(game_loop(ctx), name="FFResonance bridge")
        await ctx.exit_event.wait()
        ctx.server_address = None
        await loop_task
        await ctx.shutdown()

    parser = get_base_parser(description="Final Fantasy Resonance client")
    parser.add_argument("--name", default=None, help="Slot name to connect as.")
    parser.add_argument("--modfolder", default=None, help="The FFRArchipelago mod folder.")
    parser.add_argument("url", nargs="?", help="Archipelago connection url")
    parsed = handle_url_arg(parser.parse_args(args), parser=parser)

    import colorama
    colorama.just_fix_windows_console()
    asyncio.run(main(parsed))
    colorama.deinit()


if __name__ == "__main__":
    launch_client(*sys.argv[1:])
