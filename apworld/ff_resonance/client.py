"""Final Fantasy Resonance client: connects the FFRArchipelago mod to an Archipelago server.

The mod and this client talk through two text files in the mod folder (see the repo's README,
"Bridge format"). This client:
  * writes every item the server sends into ap_in.txt, numbered by its Archipelago index, after a
    `seed` line naming the seed and slot, plus `cfg blank 1` so the mod blanks vanilla chest
    rewards;
  * scouts the slot's locations once per session (no hints are made) and writes a `scout` line
    for each, so the mod can say in the chest pop-up what a chest holds and for whom;
  * reads ap_out.txt and sends each `check` the mod reports as a LocationCheck, and the goal once
    a `story` report reaches the goal checkpoint. Only lines after the mod's own `seed` line for
    this seed and slot count, so checks from another seed or from before connecting are ignored.
"""

from __future__ import annotations

import asyncio
import json
import os
import pkgutil
import sys
from typing import Any

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, handle_url_arg,
                          logger, server_loop)
from NetUtils import ClientStatus, NetworkItem

from .data import ITEMS
from .locations import LOCATION_KEY_TO_ID

LOCATION_ID_TO_KEY = {location_id: key for key, location_id in LOCATION_KEY_TO_ID.items()}

GAME = "Final Fantasy Resonance"
POLL_SECONDS = 0.5
GOAL_MESSAGE = "Goal complete!"
GOAL_MESSAGE_LINE = f"msg\t{GOAL_MESSAGE}"


def world_version() -> str:
    """The world_version from this package's archipelago.json. pkgutil reads it from a folder or
    from inside an .apworld zip alike."""
    try:
        data = pkgutil.get_data(__package__ or "ff_resonance", "archipelago.json")
        return str(json.loads(data.decode("utf-8")).get("world_version", "?")) if data else "?"
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return "?"


def clean(text: Any) -> str:
    return " ".join(str(text).split())


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
        self.room_seed_name: str | None = None  # RoomInfo's seed name, kept here because 0.6.7 does not store it
        self.goal = 8050
        self.items_written = 0                # item lines already in ap_in.txt for this session
        self.out_offset = 0
        self.out_scope: str | None = None     # the seed key the ap_out.txt lines being read belong to
        self.max_story = 0
        self.mod_version: str | None = None
        self.goal_announced = False           # the in-game toast was sent; a reconnect re-sends only the status
        self.scouts_written = False           # scout lines are in ap_in.txt for this session

    # -- files ------------------------------------------------------------------------------------

    def set_mod_folder(self, path: str) -> None:
        self.mod_folder = os.path.abspath(os.path.expanduser(path))
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
        # Which client this is, for the mod's log: round 10 ran an old client without anyone
        # noticing.
        self.write_line("client", world_version())
        self.out_offset = 0
        self.out_scope = None

    def write_config(self, slot_data: dict) -> None:
        """The seed's start settings, for the mod's next Archipelago new game. Written once."""
        if self.session_key is None or not os.path.isdir(self.mod_folder):
            return
        wanted = [("cfg", "openworld", int(bool(slot_data.get("open_world"))))]
        wanted.append(("cfg", "shinies", int(bool(slot_data.get("include_shinies")))))
        wanted.append(("cfg", "crystals", int(bool(slot_data.get("include_crystals")))))
        wanted.append(("cfg", "shards", int(bool(slot_data.get("include_tablet_shards")))))
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
        for index, item in enumerate(new, start=self.items_written):
            info = ITEMS.get(item.item)
            if info is None:
                logger.warning(f"Unknown item id {item.item}; skipped")
                self.write_line("msg", f"Unknown Archipelago item {item.item}")
                continue
            sender = self.player_names.get(item.player, f"player {item.player}")
            label = info["name"] if item.player == self.slot else f"{info['name']} from {sender}"
            self.write_line("item", index, info["kind"], info["game_id"], info["count"], label)
        self.items_written = len(self.items_received)

    def read_new_output(self) -> tuple[set[int], int | None]:
        """New checks and the highest story counter in ap_out.txt for this session."""
        checks: set[int] = set()
        story: int | None = None
        if not os.path.exists(self.out_path):
            return checks, story
        size = os.path.getsize(self.out_path)
        if size < self.out_offset:            # the mod started the file over
            self.out_offset, self.out_scope = 0, None
        with open(self.out_path, "rb") as f:
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
        return checks, story

    def write_scouts(self, items: list) -> int:
        """A `scout` line per location of this slot: what it holds and for whom.

            scout <location key> <item name> <player name> <flags> <own: 1 or 0>
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
            self.write_line("scout", key, name, player, item.flags, int(item.player == self.slot))
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
            self.goal = int(slot_data.get("goal_story_checkpoint", 8050))
            # The 0.6.7 release never stores RoomInfo's seed name (seed_name stays None), so it is
            # captured above; later versions also keep it in server_seed_name.
            seed = getattr(self, "server_seed_name", None) or self.room_seed_name or self.seed_name
            if not seed:
                # Without a seed name every seed would share one session key, and the mod would
                # skip a new seed's items as already applied. Stay off the bridge instead.
                self.session_key = None
                logger.error("The server sent no seed name, so the game is not connected. Reconnect to try again.")
                return
            self.session_key = f"{seed}:{self.team}:{self.slot}"
            self.max_story = 0
            self.start_session()
            self.write_config(slot_data)
            self.scout_locations()
            logger.info(f"Goal: story checkpoint {self.goal}. Mod folder: {self.mod_folder}")
        elif cmd == "LocationInfo":
            written = self.write_scouts(args.get("locations") or [])
            if written:
                logger.info(f"Told the game what {written} location(s) hold, for its chest pop-up")
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
                ctx.write_new_items()
                checks, story = ctx.read_new_output()
                if checks:
                    sent = await ctx.check_locations(checks)
                    if sent:
                        logger.info(f"Sent {len(sent)} check(s)")
                if story is not None and story > ctx.max_story:
                    ctx.max_story = story
                if not ctx.finished_game and ctx.max_story >= ctx.goal:
                    await ctx.send_msgs([{"cmd": "StatusUpdate", "status": ClientStatus.CLIENT_GOAL}])
                    ctx.finished_game = True
                    logger.info(f"Story checkpoint {ctx.max_story} reached: goal complete!")
                    if not ctx.goal_announced:
                        ctx.write_line("msg", GOAL_MESSAGE)
                        ctx.goal_announced = True
        except OSError as e:
            logger.warning(f"Bridge file error: {e}")
        await asyncio.sleep(POLL_SECONDS)


def default_mod_folder() -> str:
    try:
        from .world import FFResonanceWorld
        return str(FFResonanceWorld.settings.mod_folder)
    except Exception:  # settings unavailable (e.g. no host.yaml yet)
        return os.path.join(".", "FFRArchipelago")


def launch_client(*args: str) -> None:
    Utils.init_logging("FFResonanceClient", exception_logger="Client")

    async def main(parsed) -> None:
        ctx = FFResonanceContext(parsed.connect, parsed.password, parsed.modfolder or default_mod_folder())
        logger.info(f"Final Fantasy Resonance client, world version {world_version()}")
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
