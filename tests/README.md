# Tests

```
python tests/run_all.py
```

The runner runs every test and prints `ok`, `FAIL` (with the last lines of output) or `skip` (with what is missing). It exits non-zero on a failure.

## What there is

| Test | What it checks |
|---|---|
| `mod/test_main.py` | `main.lua` against a stub game module. Covers the item queue, checks, sessions, save linking, the per-save item count, the skip command, the title entry, the Archipelago new game, the item feed, the chest pop-up, the `ffrap_scale` options and the `ffrap_noland` commands. Each numbered section is one feature. |
| `mod/test_game.py` | `game.lua` against fake UE4SS objects. Covers the save snapshot and `tools/snapdiff.py`, the probes, the title entry and its order, the version line and the logo, the item feed, the chest pop-up, enemy scaling and the no-landing boxes. |
| `mod/test_skip.py` | The prologue skip against a fake new-game save. |
| `tools/test_gen_from_dump.py` | `tools/gen_from_dump.py` against a small fake dump: names, class defaults, map ids, and the `--check` report. |
| `tools/dump_game` (build) | The game dump tool builds. Running it needs the game, so the tests only build it. Skipped without the .NET SDK. |
| `client/test_session_key.py` | The client's session key with Archipelago 0.6.7 (seed name from `RoomInfo`). |
| `client/test_scout.py` | Location scouting and the `scout` lines. |
| `client/test_version.py` | The client's world version, from the folder and from the built `.apworld`. |
| `apworld/ff_resonance/test/` | The world's generation tests, in Archipelago's own framework. |

The fakes stand in for the engine. They follow what the game showed in test rounds, so when the game surprises us, the fake changes too (for example, a template widget that is never drawn, round 22).

## Setup, once

**Mod tests:** these need a Python with `lupa` (Lua 5.4):

```
python -m venv .venv-tests
.venv-tests\Scripts\pip install lupa
```

The runner finds `.venv-tests` by itself. `FFRAP_LUA_PYTHON` points it at another Python.

**Client and world tests:** these need Archipelago's Python (`FFRAP_AP_PYTHON`, default `C:\Projects\archipelago\venv`) and a scratch copy of an Archipelago checkout:

```
python tests/make_aptest.py C:\Projects\archipelago
```

The copy goes to `%LOCALAPPDATA%\ffrap-aptest`, or `FFRAP_APTEST`. The tests copy the world into it each run, so your own checkout is never changed. Make the copy again after you update Archipelago.
