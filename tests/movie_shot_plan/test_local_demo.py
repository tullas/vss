import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from vss_commands.cli import main
from vss_movie_contracts import validate_scene_shot_plan_draft
from vss_movie_shot_plan import admit_shot_plan_inputs


STORY = Path(__file__).resolve().parents[1] / "fixtures/movie/story-fragment-valid.json"


class LocalMovieDemoTests(unittest.TestCase):
    def run_demo(self, *extra):
        stdout, stderr = StringIO(), StringIO()
        args = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "local.reviewer",
                "--correlation-id", "local-demo", *extra]
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_interactive_command_runs_real_story_to_draft_path(self):
        stdout, stderr = StringIO(), StringIO()
        args = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "local.reviewer",
                "--correlation-id", "interactive-demo"]
        with patch("builtins.input", return_value="2"), redirect_stdout(stdout), redirect_stderr(stderr):
            self.assertEqual(main(args), 0)
        result = json.loads(stdout.getvalue())
        self.assertIn("Production options:", stderr.getvalue())
        self.assertIn("Choose an option [1-4]:", stderr.getvalue())
        self.assertNotIn("Choose an option", stdout.getvalue())
        self.assertEqual(
            result["selected_option_id"],
            result["scene_production_option_set"]["payload"]["options"][1]["option_id"],
        )
        self.assertEqual(result["selected_option_id"], result["review_decision"]["payload"]["decisions"][0]["option_id"])
        self.assertEqual(result["review_decision"]["payload"]["decisions"][0]["outcome"], "accept")
        self.assertEqual(result["creative_decision_revision"]["status"], "accepted")
        self.assertEqual(result["canon_snapshot"]["decisions"][0]["decision_sha256"],
                         result["creative_decision_revision"]["decision_sha256"])
        self.assertEqual(result["production_canon_binding"]["canon_snapshot"]["canon_sha256"],
                         result["canon_snapshot"]["canon_sha256"])
        self.assertIn("not_runtime_authority",
                      result["production_canon_binding"]["limitations"])
        task, decision, packet, option_set, breakdown, _ = admit_shot_plan_inputs(
            result["review_decision"], result["review_packet"],
            result["scene_production_option_set"], result["scene_breakdown"],
            request_id="interactive-demo-shot-plan", correlation_id="interactive-demo",
        )
        validate_scene_shot_plan_draft(
            result["scene_shot_plan_draft"], task=task, decision=decision, packet=packet,
            option_set=option_set, breakdown=breakdown,
        )
        self.assertEqual(len(result["scene_shot_plan_draft"]["payload"]["ordered_shots"]), 3)

    def test_noninteractive_choice_is_quiet_and_deterministic(self):
        with patch("builtins.input", side_effect=AssertionError("non-interactive path prompted")):
            prepared_code, prepared_stdout, prepared_stderr = self.run_demo("--option-id", "option-802bf5f0a0d8df08c1376b91")
            repeated_code, repeated_stdout, repeated_stderr = self.run_demo("--option-id", "option-802bf5f0a0d8df08c1376b91")
        self.assertEqual((prepared_code, repeated_code), (0, 0))
        self.assertEqual((prepared_stderr, repeated_stderr), ("", ""))
        prepared = json.loads(prepared_stdout)
        repeated = json.loads(repeated_stdout)
        self.assertEqual(prepared["selected_option_id"], repeated["selected_option_id"])
        self.assertEqual(
            prepared["scene_production_option_set"]["payload"],
            repeated["scene_production_option_set"]["payload"],
        )
        self.assertEqual(
            prepared["scene_shot_plan_draft"]["payload"]["ordered_shots"],
            repeated["scene_shot_plan_draft"]["payload"]["ordered_shots"],
        )
        self.assertEqual(prepared["review_decision"]["payload"]["decisions"][0]["outcome"], "accept")

    def test_invalid_choice_files_contract_reviewer_and_environment_fail_closed(self):
        base = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "local.reviewer"]
        with patch("builtins.input", return_value="0"), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertNotEqual(main(base), 0)
        with tempfile.TemporaryDirectory() as directory:
            malformed_json = Path(directory) / "malformed.json"
            malformed_json.write_text("{", encoding="utf-8")
            malformed_story = Path(directory) / "malformed-story.json"
            malformed_story.write_text(json.dumps({"contract_identity": "story_fragment"}), encoding="utf-8")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertNotEqual(main(base + ["--option-id", "unknown-option"]), 0)
                self.assertNotEqual(main(["movie", "demo", "--story", str(STORY.parent / "missing.json"),
                                          "--reviewer-id", "local.reviewer"]), 0)
                self.assertNotEqual(main(["movie", "demo", "--story", str(malformed_json),
                                          "--reviewer-id", "local.reviewer"]), 0)
                self.assertNotEqual(main(["movie", "demo", "--story", str(malformed_story),
                                          "--reviewer-id", "local.reviewer", "--option-id",
                                          "option-802bf5f0a0d8df08c1376b91"]), 0)
                self.assertNotEqual(main([*base, "--reviewer-id", "bad reviewer", "--option-id",
                                          "option-802bf5f0a0d8df08c1376b91"]), 0)
                self.assertNotEqual(main([*base, "--environment", "production"]), 0)

    def test_eof_and_cancel_return_parseable_error_without_hanging(self):
        base = ["movie", "demo", "--story", str(STORY), "--reviewer-id", "local.reviewer"]
        for terminal_error in (EOFError(), KeyboardInterrupt()):
            stdout, stderr = StringIO(), StringIO()
            with self.subTest(error=type(terminal_error).__name__), patch("builtins.input", side_effect=terminal_error), \
                    redirect_stdout(stdout), redirect_stderr(stderr):
                self.assertNotEqual(main(base), 0)
            self.assertEqual(json.loads(stdout.getvalue()), {"error": "movie demo input or selection is invalid"})
            self.assertIn("Choose an option", stderr.getvalue())
            self.assertNotIn("Choose an option", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
