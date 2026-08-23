from vss_movie_shot_plan import ShotPlanProviderView, create_shot_cards


class DeterministicSceneShotPlanProvider:
    identity = "vss.reasoning.deterministic-scene-shot-plan"
    version = "1.0.0"
    api_version = "1"

    def generate(self, view: ShotPlanProviderView) -> tuple[dict, ...]:
        if type(view) is not ShotPlanProviderView:
            raise TypeError("provider requires the exact shot-plan provider view")
        return create_shot_cards(view)
