"""Runs every test: the mod tests (Lua through lupa) and the client tests (Archipelago's Python).

    python tests/run_all.py

Setup, once:
- Mod tests need a Python with lupa:  python -m venv .venv-tests  then
  .venv-tests\\Scripts\\pip install lupa  (or point FFRAP_LUA_PYTHON at a Python that has it).
- Client tests need the scratch Archipelago copy:  python tests/make_aptest.py
  and Archipelago's venv (FFRAP_AP_PYTHON, default C:/Projects/archipelago/venv).
Tests that cannot run say why and count as skipped, not passed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

HERE = Path(__file__).resolve().parent


def lua_python() -> Path | None:
    for candidate in (os.environ.get("FFRAP_LUA_PYTHON"), paths.REPO / ".venv-tests" / "Scripts" / "python.exe",
                      sys.executable):
        if candidate and Path(candidate).exists():
            ok = subprocess.run([str(candidate), "-c", "import lupa"], capture_output=True).returncode == 0
            if ok:
                return Path(candidate)
    return None


def run(python: Path, test: Path) -> bool:
    result = subprocess.run([str(python), str(test)], capture_output=True, text=True, encoding="utf-8",
                            errors="replace", cwd=str(paths.REPO))
    lines = [l for l in (result.stdout + result.stderr).splitlines()
             if l.strip() and "WARNING" not in l and "pkg_resources" not in l]
    status = "ok  " if result.returncode == 0 else "FAIL"
    print(f"{status} {test.relative_to(paths.REPO)}")
    if result.returncode != 0:
        print("\n".join("     " + l for l in lines[-25:]))
    return result.returncode == 0


def has_dotnet_sdk() -> bool:
    if not shutil.which("dotnet"):
        return False
    check = subprocess.run(["dotnet", "--list-sdks"], capture_output=True, text=True, errors="replace")
    return check.returncode == 0 and bool(check.stdout.strip())


def main() -> int:
    failed, skipped = 0, []
    py = lua_python()
    if py:
        for test in sorted((HERE / "mod").glob("test_*.py")):
            failed += not run(py, test)
    else:
        skipped.append("mod tests: no Python with lupa (python -m venv .venv-tests, then pip install lupa)")

    for test in sorted((HERE / "tools").glob("test_*.py")):
        failed += not run(Path(sys.executable), test)

    # The game dump tool only has to build: running it needs the game installed.
    if has_dotnet_sdk():
        build = subprocess.run(["dotnet", "build", "tools/dump_game", "-nologo", "-v", "q"], capture_output=True,
                               text=True, encoding="utf-8", errors="replace", cwd=str(paths.REPO))
        ok = build.returncode == 0
        print(("ok  " if ok else "FAIL") + " tools/dump_game (build)")
        if not ok:
            print("\n".join("     " + l for l in build.stdout.splitlines()[-25:]))
        failed += not ok
    else:
        skipped.append("tools/dump_game build: no dotnet SDK")

    if paths.AP_PYTHON.exists() and (paths.APTEST / "CommonClient.py").exists():
        for test in sorted((HERE / "client").glob("test_*.py")):
            failed += not run(paths.AP_PYTHON, test)
        paths.install_world()
        world = subprocess.run([str(paths.AP_PYTHON), "-m", "unittest", "worlds.ff_resonance.test"],
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               cwd=str(paths.APTEST))
        ok = world.returncode == 0
        print(("ok  " if ok else "FAIL") + " apworld/ff_resonance/test (generation)")
        if not ok:
            print("\n".join("     " + l for l in world.stderr.splitlines()[-25:]))
        failed += not ok
    else:
        skipped.append(f"client tests: need {paths.AP_PYTHON} and {paths.APTEST} (python tests/make_aptest.py)")

    for s in skipped:
        print(f"skip {s}")
    print("failed:", failed, "skipped groups:", len(skipped))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
