from vss_movie_cinematic_lessons import ShotCinematographyLessonCandidateProviderView, derive_lesson_candidates


class DeterministicShotCinematographyLessonCandidateProvider:
    identity = "vss.reasoning.shot-cinematography-lessons.deterministic"
    version = "1.0.0"
    api_version = "1"

    def derive(self, view: ShotCinematographyLessonCandidateProviderView) -> list[dict]:
        if type(view) is not ShotCinematographyLessonCandidateProviderView:
            raise TypeError("shot lesson provider substitution rejected")
        return derive_lesson_candidates(view)
