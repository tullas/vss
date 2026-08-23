from vss_movie_storyboard import StoryboardProviderView, create_frame_specifications


class DeterministicSceneStoryboardProvider:
    identity = "vss.reasoning.deterministic-scene-storyboard"
    version = "1.0.0"
    api_version = "1"

    def generate(self, view: StoryboardProviderView):
        if type(view) is not StoryboardProviderView:
            raise TypeError("provider requires the exact storyboard provider view")
        return create_frame_specifications(view)
