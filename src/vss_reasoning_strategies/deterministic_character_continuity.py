from vss_movie_character_continuity import CharacterContinuityProviderView
from vss_reasoning_providers.deterministic_character_continuity import DeterministicCharacterContinuityProvider


class DeterministicCharacterContinuityStrategy:
    identity = "vss.analyze-character-continuity.deterministic"
    version = "1.0.0"
    provider_identity = "vss.reasoning.character-continuity.deterministic"
    provider_version = "1.0.0"
    provider_api_version = "1"
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True

    def execute(self, view: CharacterContinuityProviderView, provider: DeterministicCharacterContinuityProvider):
        if type(view) is not CharacterContinuityProviderView or type(provider) is not DeterministicCharacterContinuityProvider:
            raise TypeError("character continuity strategy substitution rejected")
        return provider.analyze(view), 1, 1
