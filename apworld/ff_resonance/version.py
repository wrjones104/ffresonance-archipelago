"""The world's version and build, from this package's archipelago.json. pkgutil reads it from a
folder or from inside an .apworld zip alike."""
import json
import pkgutil


def manifest() -> dict:
    try:
        data = pkgutil.get_data(__package__ or "ff_resonance", "archipelago.json")
        return json.loads(data.decode("utf-8")) if data else {}
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}


def world_version() -> str:
    return str(manifest().get("world_version", "?"))


def world_build() -> str:
    """The hash tools/build_apworld.py stamps on the packaged files. The version stays the same
    between releases, so this tells test builds apart. A world run from its folder is "dev"."""
    return str(manifest().get("build", "dev"))
