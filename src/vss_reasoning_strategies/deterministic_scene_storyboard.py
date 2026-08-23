from vss_movie_storyboard import StoryboardProviderView
from vss_reasoning_providers.deterministic_scene_storyboard import DeterministicSceneStoryboardProvider


class DeterministicSceneStoryboardStrategy:
    identity = "vss.create-scene-storyboard-specification.deterministic"
    version = "1.0.0"
    maximum_provider_calls = 1
    maximum_iterations = 1
    no_retry = True
    no_fallback = True

    def execute(self, view, provider):
        if type(view) is not StoryboardProviderView or type(provider) is not DeterministicSceneStoryboardProvider:
            raise TypeError("storyboard implementation substitution rejected")
        return provider.generate(view), 1, 1
