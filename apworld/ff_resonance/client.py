"""Final Fantasy Resonance client: connects the FFRArchipelago mod to an Archipelago server.

The mod and this client talk through two text files in the mod folder (see the repo's README,
"Bridge format"). This client:
  * writes every item the server sends into ap_in.txt, numbered by its Archipelago index, after a
    `seed` line naming the seed and slot, plus `cfg blank 1` so the mod blanks vanilla chest
    rewards;
  * reads ap_out.txt and sends each `check` the mod reports as a LocationCheck, and the goal once
    a `story` report reaches the goal checkpoint. Only lines after the mod's own `seed` line for
    this seed and slot count, so checks from another seed or from before connecting are ignored.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any

import Utils
from CommonClient import (ClientCommandProcessor, CommonContext, get_base_parser, gui_enabled, handle_url_arg,
                          logger, server_loop)
from NetUtils import ClientStatus

from .data import ITEMS
from .locations import LOCATION_KEY_TO_ID

GAME = "Final Fantasy Resonance"
POLL_SECONDS = 0.5
GOAL_MESSAGE = "Goal complete!"
GOAL_MESSAGE_LINE = f"msg\t{GOAL_MESSAGE}"


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
        self.goal = 8050
        self.items_written = 0                # item lines already in ap_in.txt for this session
        self.out_offset = 0
        self.out_scope: str | None = None     # the seed key the ap_out.txt lines being read belong to
        self.max_story = 0
        self.mod_version: str | None = None
        self.goal_announced = False           # the in-game toast was sent; a reconnect re-sends only the status

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
            self.items_written = sum(1 for line in existing if line.startswith("item\t"))
            self.goal_announced = GOAL_MESSAGE_LINE in existing
        else:
            if existing:
                logger.info("ap_in.txt belonged to another seed or slot; starting it over.")
            with open(self.in_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(header + "\n")
            self.write_line("cfg", "blank", 1)
            self.items_written = 0
            self.goal_announced = False
        self.out_offset = 0
        self.out_scope = None

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
            kind = fields[0]
            if kind == "hello" and len(fields) > 1:
                self.mod_version = fields[1]
            elif kind == "seed" and len(fields) > 1:
                self.out_scope = fields[1]
            elif self.out_scope != self.session_key or self.session_key is None:
                continue
            elif kind == "check" and len(fields) > 1:
                location = LOCATION_KEY_TO_ID.get(fields[1])
                if location is not None:
                    checks.add(location)
            elif kind == "story" and len(fields) > 1 and fields[1].lstrip("-").isdigit():
                story = max(story or 0, int(fields[1]))
        return checks, story

    # -- server -----------------------------------------------------------------------------------

    async def server_auth(self, password_requested: bool = False) -> None:
        if password_requested and not self.password:
            await super().server_auth(password_requested)
        await self.get_username()
        await self.send_connect()

    def on_package(self, cmd: str, args: dict) -> None:
        if cmd == "Connected":
            slot_data = args.get("slot_data") or {}
            self.goal = int(slot_data.get("goal_story_checkpoint", 8050))
            # RoomInfo's seed name; 0.6.7+ keeps it in server_seed_name (seed_name stays None).
            seed = getattr(self, "server_seed_name", None) or self.seed_name or "unknown"
            self.session_key = f"{seed}:{self.team}:{self.slot}"
            self.max_story = 0
            self.start_session()
            logger.info(f"Goal: story checkpoint {self.goal}. Mod folder: {self.mod_folder}")
        elif cmd == "PrintJSON" and args.get("type") == "ItemSend" and self.slot is not None:
            item, receiver = args.get("item"), args.get("receiving")
            if item is not None and item.player == self.slot and receiver != self.slot:
                name = self.item_names.lookup_in_slot(item.item, receiver)
                self.write_line("msg", f"Sent {name} to {self.player_names.get(receiver, receiver)}")

    def reset_server_state(self) -> None:
        super().reset_server_state()
        self.session_key = None

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
