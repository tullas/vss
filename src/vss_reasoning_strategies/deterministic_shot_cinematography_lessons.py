from vss_movie_cinematic_lessons import ShotCinematographyLessonCandidateProviderView
from vss_reasoning_providers.deterministic_shot_cinematography_lessons import DeterministicShotCinematographyLessonCandidateProvider


class DeterministicShotCinematographyLessonCandidateStrategy:
    identity = "vss.derive-shot-cinematography-lesson-candidates.deterministic"
    version = "1.0.0"
    provider_identity = "vss.reasoning.shot-cinematography-lessons.deterministic"
    provider_version = "1.0.0"
    provider_api_version = "1"
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True

    def execute(self, view: ShotCinematographyLessonCandidateProviderView,
                provider: DeterministicShotCinematographyLessonCandidateProvider):
        if type(view) is not ShotCinematographyLessonCandidateProviderView or type(provider) is not DeterministicShotCinematographyLessonCandidateProvider:
            raise TypeError("shot lesson strategy substitution rejected")
        return provider.derive(view), 1, 1
