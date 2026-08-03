from types import MappingProxyType
from vss_movie_scene_breakdown.service import break_down_scenes

IDENTITY = "vss.reasoning.deterministic-scene-breakdown"
VERSION = "1.0.0"
API_VERSION = "1"

class DeterministicSceneBreakdownProvider:
    identity=IDENTITY; version=VERSION; api_version=API_VERSION
    def generate(self, view, *, now=None):
        return break_down_scenes(view, now=now)
