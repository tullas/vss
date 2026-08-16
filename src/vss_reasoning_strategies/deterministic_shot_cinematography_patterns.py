from vss_movie_cinematic_patterns import ShotCinematographyPatternProviderView
from vss_reasoning_providers.deterministic_shot_cinematography_patterns import DeterministicShotCinematographyPatternProvider


class DeterministicShotCinematographyPatternStrategy:
    identity = "vss.analyze-shot-cinematography-patterns.deterministic"
    version = "1.0.0"
    provider_identity = "vss.reasoning.shot-cinematography-patterns.deterministic"
    provider_version = "1.0.0"
    provider_api_version = "1"
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True

    def execute(self, view: ShotCinematographyPatternProviderView, provider: DeterministicShotCinematographyPatternProvider):
        if type(view) is not ShotCinematographyPatternProviderView or type(provider) is not DeterministicShotCinematographyPatternProvider:
            raise TypeError("shot pattern strategy substitution rejected")
        return provider.analyze(view), 1, 1
