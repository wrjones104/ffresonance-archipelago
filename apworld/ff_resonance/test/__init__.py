from test.bases import WorldTestBase

# Most tests look at a small pool: chests only. A test of shinies, crystals, shards or bosses turns
# its own option on.
CHESTS_ONLY = {"goal": "final_boss", "include_shinies": False, "include_crystals": False,
               "include_tablet_shards": False, "include_bosses": False}


class FFResonanceTestBase(WorldTestBase):
    game = "Final Fantasy Resonance"

    def __init_subclass__(cls, real_defaults: bool = False, **kwargs) -> None:
        """A test class made with real_defaults=True runs with the options a player gets."""
        super().__init_subclass__(**kwargs)
        cls.options = {**({} if real_defaults else CHESTS_ONLY), **cls.__dict__.get("options", {})}
