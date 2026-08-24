from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts/vss-agent"
SCHEMA = json.loads((ROOT / "schemas/agent-checkpoint-v1.schema.json").read_text(encoding="utf-8"))


class AgentCoordinationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.external_directories: list[Path] = []
        self.root = Path(self.temporary.name)
        (self.root / "scripts").mkdir()
        (self.root / "schemas").mkdir()
        shutil.copy2(HELPER, self.root / "scripts/vss-agent")
        shutil.copy2(ROOT / "schemas/agent-checkpoint-v1.schema.json",
                     self.root / "schemas/agent-checkpoint-v1.schema.json")
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/example/vss.git")
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README.md", "scripts/vss-agent", "schemas/agent-checkpoint-v1.schema.json")
        self.git("commit", "-qm", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        residue = self.root / ".local/secrets/development.auto.tfvars.example"
        residue.parent.mkdir(parents=True)
        residue.write_text("protected fixture residue\n", encoding="utf-8")

    def tearDown(self) -> None:
        for directory in self.external_directories:
            shutil.rmtree(directory)
        self.temporary.cleanup()

    def git(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments], cwd=self.root, text=True, capture_output=True, check=True,
        )

    def agent(self, *arguments: str, environment: dict[str, str] | None = None,
              stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.root / "scripts/vss-agent"), *arguments], cwd=self.root,
            env=environment, input=stdin, text=True, capture_output=True, check=False,
        )

    @staticmethod
    def payload(comment: str) -> dict:
        lines = comment.splitlines()
        if len(lines) != 4 or not lines[0].startswith("<!-- vss-agent-checkpoint:v1 sha256="):
            raise AssertionError(comment)
        value = json.loads(lines[2])
        expected = hashlib.sha256(lines[2].encode()).hexdigest()
        if lines[0] != f"<!-- vss-agent-checkpoint:v1 sha256={expected} -->":
            raise AssertionError("digest mismatch")
        return value

    def checkpoint(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.agent(
            "checkpoint", "--target", "issue:90", "--type", "implementation",
            "--base", self.base, "--summary", "Implementation checkpoint.", *extra,
        )

    def test_checkpoint_is_deterministic_strict_and_protected_residue_is_not_dirtiness(self) -> None:
        first = self.checkpoint("--check", "focused-tests=passed")
        second = self.checkpoint("--check", "focused-tests=passed")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        value = self.payload(first.stdout)
        self.assertEqual(list(Draft202012Validator(SCHEMA).iter_errors(value)), [])
        self.assertFalse(value["repository"]["code_dirty"])
        self.assertEqual(value["delta"]["changed_files"], [])
        self.assertEqual(value["delta"]["changed_file_count"], 1)
        self.assertEqual(value["delta"]["omitted_path_count"], 1)
        self.assertNotIn(".local", first.stdout)
        self.assertTrue(all(authority is False for authority in value["authority"].values()))

    def test_unexpected_local_or_source_state_is_dirty_and_blocks_approval(self) -> None:
        unexpected = self.root / ".local/movie/unexpected.json"
        unexpected.parent.mkdir(parents=True)
        unexpected.write_text("{}", encoding="utf-8")
        checkpoint = self.checkpoint()
        self.assertTrue(self.payload(checkpoint.stdout)["repository"]["code_dirty"])
        self.assertNotIn("unexpected", checkpoint.stdout)
        approval = self.agent(
            "approval", "--target", "issue:90", "--scope", "merge",
            "--operation-digest", "1" * 64, "--decision", "approved",
            "--recorded-by", "human-reviewer",
        )
        self.assertEqual(approval.returncode, 2)
        self.assertEqual(approval.stderr, "vss-agent: approval requires a clean code worktree\n")

        unexpected.unlink()
        source = self.root / "new-source.py"
        source.write_text("pass\n", encoding="utf-8")
        approval = self.agent(
            "approval", "--target", "issue:90", "--scope", "merge",
            "--operation-digest", "1" * 64, "--decision", "approved",
            "--recorded-by", "human-reviewer",
        )
        self.assertEqual(approval.returncode, 2)

    def test_approval_is_metadata_only_and_becomes_stale_after_head_change(self) -> None:
        approval = self.agent(
            "approval", "--target", "issue:90", "--scope", "paid_provider_attempt",
            "--operation-digest", "2" * 64, "--decision", "approved",
            "--recorded-by", "human-reviewer",
        )
        self.assertEqual(approval.returncode, 0, approval.stderr)
        value = self.payload(approval.stdout)
        self.assertEqual(value["checkpoint_type"], "approval_record")
        self.assertEqual(value["approval"]["approved_head_sha"], self.base)
        self.assertFalse(value["approval"]["runtime_authority"])
        self.assertFalse(value["approval"]["provider_authority"])
        record = self.root / "approval.txt"
        record.write_text(approval.stdout, encoding="utf-8")
        valid = self.agent("validate", "--input", str(record), "--require-current-head")
        self.assertEqual(valid.returncode, 0, valid.stderr)

        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "change head")
        stale = self.agent("validate", "--input", str(record), "--require-current-head")
        self.assertEqual(stale.returncode, 2)
        self.assertEqual(stale.stderr, "vss-agent: checkpoint is stale for current HEAD\n")

    def test_malformed_extra_open_and_digest_substitutions_fail_closed(self) -> None:
        emitted = self.checkpoint()
        value = self.payload(emitted.stdout)
        cases = []
        cases.append({**value, "extra": True})
        cases.append({**value, "authority": {**value["authority"], "execute": True}})
        cases.append({**value, "checkpoint_type": "approval_record", "approval": None})
        cases.append({**value, "repository": {**value["repository"], "head_sha": "bad"}})
        for index, candidate in enumerate(cases):
            path = self.root / f"invalid-{index}.json"
            path.write_text(json.dumps(candidate), encoding="utf-8")
            result = self.agent("validate", "--input", str(path))
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertNotIn(str(candidate), result.stderr)

        tampered = emitted.stdout.replace("Implementation checkpoint.", "Tampered checkpoint.")
        path = self.root / "tampered.txt"
        path.write_text(tampered, encoding="utf-8")
        result = self.agent("validate", "--input", str(path))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "vss-agent: checkpoint digest does not match\n")

    def test_secret_values_diff_contents_and_sensitive_paths_never_surface(self) -> None:
        secret = "github_pat_" + "A" * 40  # pragma: allowlist secret -- synthetic rejection fixture
        (self.root / "safe-file.txt").write_text(secret + "\n", encoding="utf-8")
        sensitive_path = self.root / "credentials/token.txt"
        sensitive_path.parent.mkdir()
        sensitive_path.write_text(secret, encoding="utf-8")
        result = self.checkpoint()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(secret, result.stdout + result.stderr)
        self.assertNotIn("credentials", result.stdout + result.stderr)
        self.assertNotIn("token.txt", result.stdout + result.stderr)
        self.assertIn("safe-file.txt", result.stdout)
        bad_summary = self.agent(
            "checkpoint", "--target", "issue:90", "--type", "blocked",
            "--base", self.base, "--summary", f"token={secret}",
        )
        self.assertEqual(bad_summary.returncode, 2)
        self.assertNotIn(secret, bad_summary.stderr)

    def test_changed_paths_are_bounded_sorted_and_omissions_are_counted(self) -> None:
        for index in range(70):
            (self.root / f"file-{index:02d}.txt").write_text("x\n", encoding="utf-8")
        result = self.checkpoint()
        value = self.payload(result.stdout)
        self.assertEqual(len(value["delta"]["changed_files"]), 64)
        self.assertEqual(value["delta"]["changed_files"], sorted(value["delta"]["changed_files"]))
        self.assertEqual(value["delta"]["changed_file_count"], 71)
        self.assertEqual(value["delta"]["omitted_path_count"], 7)
        self.assertLess(len(result.stdout.encode()), 16_384)

    def test_detached_head_missing_base_and_control_text_fail_closed(self) -> None:
        self.git("checkout", "--detach", "-q")
        detached = self.checkpoint()
        self.assertEqual(detached.returncode, 2)
        self.assertEqual(detached.stderr, "vss-agent: required command failed\n")
        self.git("switch", "-q", "main")
        missing = self.agent(
            "checkpoint", "--target", "issue:90", "--type", "design",
            "--base", "f" * 40, "--summary", "Missing base.",
        )
        self.assertEqual(missing.returncode, 2)
        control = self.agent(
            "checkpoint", "--target", "issue:90", "--type", "design",
            "--base", self.base, "--summary", "line one\nline two",
        )
        self.assertEqual(control.returncode, 2)

    def _fake_gh_environment(self) -> tuple[dict[str, str], Path, Path]:
        external = Path(tempfile.mkdtemp(prefix="vss-agent-gh-"))
        self.external_directories.append(external)
        binary = external / "bin"
        binary.mkdir()
        state = external / "gh-state.json"
        log = external / "gh-log.jsonl"
        fake = binary / "gh"
        fake.write_text(
            "#!/usr/bin/env python3\n"
            "import json,os,sys\n"
            "state=os.environ['GH_STATE']; log=os.environ['GH_LOG']\n"
            "with open(log,'a',encoding='utf-8') as stream: stream.write(json.dumps(sys.argv[1:])+'\\n')\n"
            "if '--method' in sys.argv:\n"
            " body=next(value[5:] for value in sys.argv if value.startswith('body='))\n"
            " open(state,'w',encoding='utf-8').write(json.dumps([{'body':body}]))\n"
            " print('{}')\n"
            "elif '--paginate' in sys.argv:\n"
            " comments=json.loads(open(state,encoding='utf-8').read()) if os.path.exists(state) else []\n"
            " print(json.dumps([]),end='')\n"
            " print(json.dumps(comments))\n"
            "else:\n"
            " print(json.dumps({'pull_request':{}}))\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        environment = dict(os.environ)
        environment.update({"PATH": f"{binary}:{environment['PATH']}", "GH_STATE": str(state), "GH_LOG": str(log)})
        return environment, state, log

    def test_post_uses_fixed_gh_arguments_and_is_idempotent(self) -> None:
        environment, state, log = self._fake_gh_environment()
        local = self.checkpoint()
        self.assertFalse(log.exists())
        first = self.agent(
            "checkpoint", "--target", "pr:123", "--type", "implementation",
            "--base", self.base, "--summary", "Ready.", "--post", environment=environment,
        )
        second = self.agent(
            "checkpoint", "--target", "pr:123", "--type", "implementation",
            "--base", self.base, "--summary", "Ready.", "--post", environment=environment,
        )
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads(first.stdout)["status"], "posted")
        self.assertEqual(json.loads(second.stdout)["status"], "already_posted")
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(sum("POST" in call for call in calls), 1)
        self.assertTrue(all(call[0] == "api" for call in calls))
        self.assertTrue(any("--paginate" in call for call in calls))
        self.assertTrue(all("--slurp" not in call for call in calls))
        self.assertTrue(all(any(value.startswith("repos/example/vss/issues/123") for value in call) for call in calls))
        self.assertNotIn("shell", json.dumps(calls))
        self.assertTrue(state.exists())
        self.assertIn("vss-agent-checkpoint:v1", state.read_text(encoding="utf-8"))
        self.assertIn("vss-agent-checkpoint:v1", local.stdout)

    def test_post_rejects_issue_pull_request_kind_mismatch_before_comment_write(self) -> None:
        environment, _, log = self._fake_gh_environment()
        result = self.agent(
            "checkpoint", "--target", "issue:123", "--type", "implementation",
            "--base", self.base, "--summary", "Ready.", "--post", environment=environment,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "vss-agent: GitHub target kind does not match\n")
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertNotIn("POST", calls[0])

    def test_post_rejects_malformed_github_data_with_closed_diagnostic(self) -> None:
        environment, _, _ = self._fake_gh_environment()
        fake = Path(environment["PATH"].split(os.pathsep, 1)[0]) / "gh"
        fake.write_text("#!/usr/bin/env python3\nprint('not-json')\n", encoding="utf-8")
        fake.chmod(0o755)
        result = self.agent(
            "checkpoint", "--target", "issue:90", "--type", "implementation",
            "--base", self.base, "--summary", "Ready.", "--post", environment=environment,
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr, "vss-agent: GitHub response is malformed\n")

    def test_helper_has_no_runtime_provider_or_effectful_command_path(self) -> None:
        source = HELPER.read_text(encoding="utf-8")
        for forbidden in ("vss_runtime", "vss_providers", "--generate", "git push", "git merge"):
            self.assertNotIn(forbidden, source)
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertEqual(ci.count("unittest discover -s tests/agent_coordination"), 1)


if __name__ == "__main__":
    unittest.main()
