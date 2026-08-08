from vss_movie_production_options import SceneProductionOptionsProviderView, create_production_option_candidates

class DeterministicSceneProductionOptionsProvider:
    identity = "vss.reasoning.deterministic-scene-production-options"
    version = "1.0.0"
    api_version = "1"
    def generate(self, view: SceneProductionOptionsProviderView) -> tuple[dict, ...]:
        if type(view) is not SceneProductionOptionsProviderView:
            raise TypeError("provider requires the exact production-options provider view")
        return create_production_option_candidates(view)
