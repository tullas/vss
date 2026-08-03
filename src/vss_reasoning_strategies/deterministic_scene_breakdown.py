from vss_reasoning_providers.deterministic_scene_breakdown import DeterministicSceneBreakdownProvider

IDENTITY = "vss.break-down-scenes.deterministic"
VERSION = "1.0.0"
class DeterministicSceneBreakdownStrategy:
    identity=IDENTITY; version=VERSION; maximum_provider_calls=1; maximum_scenes=32
    def resolve_provider(self): return DeterministicSceneBreakdownProvider()
    def execute(self, view, *, now=None): return self.resolve_provider().generate(view, now=now)
