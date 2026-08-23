from vss_movie_shot_plan import ShotPlanProviderView
from vss_reasoning_providers.deterministic_scene_shot_plan import DeterministicSceneShotPlanProvider


class DeterministicSceneShotPlanStrategy:
    identity = "vss.create-scene-shot-plan-draft.deterministic"
    version = "1.0.0"
    provider_identity = "vss.reasoning.deterministic-scene-shot-plan"
    provider_version = "1.0.0"
    provider_api_version = "1"
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True
    stable_order_is_not_ranking = True

    def execute(self, view: ShotPlanProviderView,
                provider: DeterministicSceneShotPlanProvider):
        if type(view) is not ShotPlanProviderView or type(provider) is not DeterministicSceneShotPlanProvider:
            raise TypeError("shot-plan implementation substitution rejected")
        return provider.generate(view), 1, 1
