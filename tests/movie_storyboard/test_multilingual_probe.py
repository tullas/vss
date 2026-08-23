from __future__ import annotations

import copy
import json
import unicodedata
import unittest
from pathlib import Path

from vss_movie_contracts import MovieContractRegistry, validate_story_fragment
from vss_reasoning_contracts import load_json_document
from vss_movie_demo import finish_demo, prepare_demo
from vss_reasoning_contracts import canonical_digest

ROOT = Path(__file__).resolve().parents[2]
TEXT = "मीरा दीपक देखती है. Mira pauses at dawn. والباب مغلق"


class MultilingualSemanticProbe(unittest.TestCase):
    def story(self):
        value = json.loads((ROOT / "tests/fixtures/movie/story-fragment-valid.json").read_text())
        value["payload"]["fragment_text"] = TEXT
        return value

    def test_truthful_language_is_currently_blocked_and_unicode_survives_m4_to_m8(self):
        truthful = self.story(); truthful["payload"]["language"] = "mul"
        with self.assertRaises(Exception):
            validate_story_fragment(load_json_document(json.dumps(truthful, ensure_ascii=False).encode()), MovieContractRegistry.built_in())
        prepared = prepare_demo(self.story(), correlation_id="multilingual-probe")
        option_id = prepared.review_packet["payload"]["review_entries"][0]["option_id"]
        result = finish_demo(prepared, option_id=option_id, reviewer_id="probe.reviewer",
            rationale="Offline multilingual transport probe.", correlation_id="multilingual-probe",
            include_storyboard=True)
        frame = result["scene_storyboard_specification"]["payload"]["ordered_frames"][0]
        self.assertIn(TEXT, frame["action"]); self.assertIn(TEXT, frame["generation_prompt"])
        span = result["scene_breakdown"]["payload"]["ordered_scenes"][0]["source_span"]
        self.assertEqual(span, {"start": 0, "end": len(TEXT)})  # Python Unicode code-point offsets.

    def test_digest_has_byte_stability_but_no_unicode_normalization(self):
        nfc = unicodedata.normalize("NFC", "मीरा café والباب")
        nfd = unicodedata.normalize("NFD", nfc)
        self.assertNotEqual(nfc, nfd); self.assertNotEqual(canonical_digest({"text": nfc}), canonical_digest({"text": nfd}))
        self.assertEqual(canonical_digest({"text": TEXT}), canonical_digest({"text": copy.deepcopy(TEXT)}))

    def test_mixed_bidi_text_is_xml_escaped_by_real_svg_provider(self):
        from tests.movie_storyboard.test_m8_1 import M81StoryboardRenderTests
        case = M81StoryboardRenderTests(methodName="runTest"); case.setUp()
        try:
            from vss_movie_storyboard_render import admit_storyboard_render
            request = admit_storyboard_render(*case.values, case.storyboard, environment="development")
            frames = [dict(frame) for frame in request.frames]
            frames[0] = {**frames[0], "action": TEXT + " <script>&"}
            from vss_providers import StoryboardRenderRequest
            renderer = case.controller().provider_registry.initialize(case.controller().provider_registry.resolve("movie.storyboard-render.local"))
            media = renderer.render(StoryboardRenderRequest(request.project_id, request.scene_id, request.storyboard_specification_digest, tuple(frames)))
            decoded = media.content.decode("utf-8")
            self.assertIn(TEXT, decoded); self.assertNotIn("<script>", decoded); self.assertIn("&lt;script&gt;&amp;", decoded)
        finally: case.tearDown()


if __name__ == "__main__": unittest.main()
