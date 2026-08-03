from types import MappingProxyType
from vss_movie_scene_breakdown.service import SceneBreakdownProviderView, segment_provider_view

IDENTITY = "vss.reasoning.deterministic-scene-breakdown"
VERSION = "1.0.0"
API_VERSION = "1"

class DeterministicSceneBreakdownProvider:
    identity=IDENTITY; version=VERSION; api_version=API_VERSION
    def generate(self, view, *, now=None):
        if not isinstance(view, SceneBreakdownProviderView):
            raise TypeError("scene provider requires a provider-visible view")
        return segment_provider_view(view)
