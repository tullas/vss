from vss_movie_cinematic_patterns import ShotCinematographyPatternProviderView, analyze_patterns


class DeterministicShotCinematographyPatternProvider:
    identity = "vss.reasoning.shot-cinematography-patterns.deterministic"
    version = "1.0.0"
    api_version = "1"

    def analyze(self, view: ShotCinematographyPatternProviderView) -> dict:
        if type(view) is not ShotCinematographyPatternProviderView:
            raise TypeError("shot pattern provider substitution rejected")
        return analyze_patterns(view)
