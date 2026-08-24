PROVIDER_MANIFEST_SCHEMA_VERSION = "1"
PROVIDER_API_VERSION = "1"

CLOCK_PROVIDER_TYPE = "clock"
LOCAL_CLOCK_IDENTITY = "system.clock.local"
LOCAL_CLOCK_IMPLEMENTATION_IDENTITY = "vss.local-clock"

STORYBOARD_RENDER_PROVIDER_TYPE = "storyboard_render"
LOCAL_STORYBOARD_RENDER_IDENTITY = "movie.storyboard-render.local"
LOCAL_STORYBOARD_RENDER_IMPLEMENTATION_IDENTITY = "vss.local-deterministic-storyboard-svg"

PICTORIAL_FRAME_PROVIDER_TYPE = "storyboard_image_generation"
LOCAL_PICTORIAL_FRAME_IDENTITY = "movie.storyboard-image.local"
LOCAL_PICTORIAL_FRAME_IMPLEMENTATION_IDENTITY = "vss.local-deterministic-pictorial-png"

CONTROLLED_FRAME_PROVIDER_TYPE = "controlled_storyboard_image_generation"
CONTROLLED_FRAME_PROVIDER_IDENTITY = "movie.storyboard-image.openai"
CONTROLLED_FRAME_IMPLEMENTATION_IDENTITY = "vss.openai-gpt-image-2"
