from vss_movie_character_continuity import CharacterContinuityProviderView, analyze_explicit_observations, analyze_bounded_continuity


class DeterministicCharacterContinuityProvider:
    identity = "vss.reasoning.character-continuity.deterministic"
    version = "1.0.0"
    api_version = "1"

    def analyze(self, view: CharacterContinuityProviderView) -> tuple[str, ...]:
        if type(view) is not CharacterContinuityProviderView:
            raise TypeError("provider requires exact CharacterContinuityProviderView")
        return analyze_explicit_observations(view)


class DeterministicCharacterContinuityAnalysisProvider:
    identity = "vss.reasoning.character-continuity.deterministic"
    version = "1.1.0"
    api_version = "1"

    def analyze(self, view: CharacterContinuityProviderView) -> dict:
        if type(view) is not CharacterContinuityProviderView:
            raise TypeError("provider requires exact CharacterContinuityProviderView")
        return analyze_bounded_continuity(view)
