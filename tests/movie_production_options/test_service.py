import json, unittest
from pathlib import Path
from vss_movie_scene_breakdown import assemble_scene_context, break_down_scenes
from vss_movie_production_options import *
from vss_reasoning_contracts import load_json_document
ROOT=Path(__file__).resolve().parents[2]
class ProductionOptionsTests(unittest.TestCase):
    def setUp(self):
        story=load_json_document((ROOT/'tests/fixtures/movie/story-fragment-valid.json').read_bytes()); c=assemble_scene_context(story,request_id='r',correlation_id='c',project_id=story['project_id'],validation_time='2026-08-02T00:00:00Z'); b=break_down_scenes(c,now='2026-08-02T00:00:01Z'); s=b['payload']['ordered_scenes'][0]; self.ctx=assemble_production_options_context(b,request_id='p',correlation_id='c',project_id=story['project_id'],scene_id=s['scene_id'],scene_content_digest=s['scene_content_digest'],validation_time='2026-08-02T00:00:00Z')
    def test_options_are_stable_and_not_ranked(self):
        a=generate_production_options(self.ctx); b=generate_production_options(self.ctx); self.assertEqual(a,b); self.assertEqual([x['ordinal'] for x in a['payload']['options']],[1,2,3,4]); self.assertNotIn('recommended_option',a['payload'])
    def test_view_is_immutable_and_scene_selection_exact(self):
        view=production_provider_view(self.ctx)
        with self.assertRaises(TypeError): view['scene_id']='x'
        bad=json.loads(json.dumps(self.ctx.to_json_value())); bad['payload']['scene_id']='unknown'; bad['integrity']['complete_context_sha256']='0'*64
        with self.assertRaises(ValueError): validate_production_options_context(bad)
    def test_profile_catalogue_is_stable(self):
        a=ProductionProfileCatalogue.built_in(); b=ProductionProfileCatalogue.built_in(); self.assertEqual(a.digest,b.digest); self.assertEqual([p.identity for p in a.profiles],['minimal_stage','location_live_action','stylized_2d','stylized_3d'])
