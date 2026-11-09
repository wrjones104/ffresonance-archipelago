from test.bases import WorldTestBase


class FFResonanceTestBase(WorldTestBase):
    game = "Final Fantasy Resonance"

    def __init_subclass__(cls, **kwargs) -> None:
        # Most tests look at the pool without the 99 shards, which the default goal brings in.
        # A test of the shard goal says so. This base class itself runs with the real defaults.
        super().__init_subclass__(**kwargs)
        cls.options = {"goal": "story_checkpoint", **cls.__dict__.get("options", {})}
