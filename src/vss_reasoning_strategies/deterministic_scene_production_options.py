from typing import Any
from vss_movie_production_options import SceneProductionOptionsProviderView
from vss_reasoning_providers.deterministic_scene_production_options import DeterministicSceneProductionOptionsProvider

class DeterministicSceneProductionOptionsStrategy:
    identity = "vss.generate-scene-production-options.deterministic"
    version = "1.0.0"
    provider_identity = "vss.reasoning.deterministic-scene-production-options"
    provider_version = "1.0.0"
    provider_api_version = "1"
    maximum_options = 4
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True
    stable_order_is_not_ranking = True
    def execute(self, view: SceneProductionOptionsProviderView, binding: dict[str, Any], provider: DeterministicSceneProductionOptionsProvider) -> tuple[dict[str, Any], int, int]:
        if type(view) is not SceneProductionOptionsProviderView or type(provider) is not DeterministicSceneProductionOptionsProvider:
            raise TypeError("production strategy substitution rejected")
        return provider.generate(view, binding), 1, 1
