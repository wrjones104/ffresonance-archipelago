"""Fake Archipelago server for testing the FFRArchipelago mod without a real multiworld.

It plays the client's side of the file bridge: you type items, it appends them to ap_in.txt,
and it prints what the game writes to ap_out.txt (checks, story changes, applied items).

    python fake_ap.py [path to the FFRArchipelago mod folder]

Commands:
    item <id> [n] [label]   a bag item, e.g.  item 10100 1 Crimson Saber
    vision <id> [label]     e.g.  vision 13017 Amelia
    unit <id> [label]       a party member, e.g.  unit 1002
    flag <index> [0|1]      a story flag
    msg <text>              show text in game
    log                     show everything the game has written so far
    quit

Standard library only.
"""

import os
import shlex
import sys
import threading
import time

DEFAULT_MOD_DIR = (r"C:\Program Files (x86)\Steam\steamapps\common\FINAL FANTASY RESONANCE"
                   r"\FFRS\Binaries\Win64\ue4ss\Mods\FFRArchipelago")


def next_index(in_path):
    """The next item index: one past the highest item already in ap_in.txt."""
    highest = -1
    if os.path.exists(in_path):
        with open(in_path, encoding="utf-8") as f:
            for line in f:
                fields = line.rstrip("\r\n").split("\t")
                if fields[0] == "item" and len(fields) > 1 and fields[1].isdigit():
                    highest = max(highest, int(fields[1]))
    return highest + 1


def clean(text):
    return " ".join(str(text).split())


def append(in_path, *fields):
    with open(in_path, "a", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(clean(x) for x in fields) + "\n")
        f.flush()


def tail(out_path, stop):
    """Prints new ap_out.txt lines as the game writes them."""
    offset = os.path.getsize(out_path) if os.path.exists(out_path) else 0
    while not stop.is_set():
        if os.path.exists(out_path):
            size = os.path.getsize(out_path)
            if size < offset:
                offset = 0
            if size > offset:
                with open(out_path, "rb") as f:
                    f.seek(offset)
                    data = f.read()
                end = data.rfind(b"\n") + 1
                offset += end
                for line in data[:end].decode("utf-8", "replace").splitlines():
                    if line:
                        print("\n  game> " + line.replace("\t", "  "), flush=True)
        time.sleep(0.25)


def main():
    mod_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MOD_DIR
    if not os.path.isdir(mod_dir):
        sys.exit(f"Mod folder not found: {mod_dir}")
    in_path = os.path.join(mod_dir, "ap_in.txt")
    out_path = os.path.join(mod_dir, "ap_out.txt")
    index = next_index(in_path)
    print(f"Bridge: {mod_dir}\nNext item index: {index}. Type 'help' for commands.")

    stop = threading.Event()
    threading.Thread(target=tail, args=(out_path, stop), daemon=True).start()
    try:
        while True:
            try:
                words = shlex.split(input("ap> "))
            except ValueError as e:
                print(e)
                continue
            if not words:
                continue
            cmd, args = words[0].lower(), words[1:]
            try:
                if cmd in ("quit", "exit"):
                    break
                elif cmd == "help":
                    print(__doc__)
                elif cmd == "log":
                    if os.path.exists(out_path):
                        with open(out_path, encoding="utf-8") as f:
                            print(f.read().replace("\t", "  "))
                elif cmd == "msg":
                    append(in_path, "msg", " ".join(args))
                elif cmd == "item":
                    n = int(args[1]) if len(args) > 1 else 1
                    label = " ".join(args[2:]) or f"item {args[0]} x{n}"
                    append(in_path, "item", index, "item", int(args[0]), n, label)
                    index += 1
                elif cmd in ("vision", "unit"):
                    label = " ".join(args[1:]) or f"{cmd} {args[0]}"
                    append(in_path, "item", index, cmd, int(args[0]), 1, label)
                    index += 1
                elif cmd == "flag":
                    on = int(args[1]) if len(args) > 1 else 1
                    append(in_path, "item", index, "flag", int(args[0]), on, f"flag {args[0]}={on}")
                    index += 1
                else:
                    print("Unknown command. Type 'help'.")
            except (IndexError, ValueError):
                print("Missing or bad argument. Type 'help'.")
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        stop.set()


if __name__ == "__main__":
    main()
