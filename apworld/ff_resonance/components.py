from worlds.LauncherComponents import Component, Type, components, launch


def run_client(*args: str) -> None:
    from .client import launch_client

    launch(launch_client, name="Final Fantasy Resonance Client", args=args)


components.append(
    Component(
        "Final Fantasy Resonance Client",
        func=run_client,
        game_name="Final Fantasy Resonance",
        component_type=Type.CLIENT,
        supports_uri=True,
    )
)
