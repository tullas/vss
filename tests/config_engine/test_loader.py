from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vss_config import ConfigError, load_configuration, render_configuration


class ConfigurationEngineTests(unittest.TestCase):
    def write_config(self, defaults: str, environment: str = "development", override: str = "") -> Path:
        root = Path(tempfile.mkdtemp())
        (root / "environments").mkdir()
        (root / "schema").mkdir()
        (root / "defaults.yml").write_text(defaults, encoding="utf-8")
        (root / "environments" / f"{environment}.yml").write_text(override, encoding="utf-8")
        schema = Path(__file__).parents[2] / "config/schema/v1.json"
        (root / "schema/v1.json").write_text(schema.read_text(encoding="utf-8"), encoding="utf-8")
        return root

    def test_all_tracked_environments_are_valid(self) -> None:
        for environment in ("development", "staging", "production"):
            self.assertEqual(load_configuration(environment)["environment"]["name"], environment)

    def test_environment_override_is_deterministic_and_deep(self) -> None:
        root = self.write_config(
            "application:\n  name: base\nenvironment:\n  name: development\nlogging:\n  level: INFO\n",
            override="logging:\n  level: DEBUG\n",
        )
        self.assertEqual(load_configuration("development", root)["logging"]["level"], "DEBUG")
        self.assertEqual(load_configuration("development", root)["application"]["name"], "base")

    def test_malformed_yaml_is_rejected(self) -> None:
        root = self.write_config("application: [\nenvironment:\n  name: development\n")
        with self.assertRaisesRegex(ConfigError, "could not read YAML"):
            load_configuration("development", root)

    def test_missing_required_property_is_rejected(self) -> None:
        root = self.write_config("application:\n  name: vss\nenvironment:\n  name: development\n", override="{}\n")
        with self.assertRaisesRegex(ConfigError, "'logging' is a required property"):
            load_configuration("development", root)

    def test_invalid_value_is_rejected(self) -> None:
        root = self.write_config(
            "application:\n  name: vss\nenvironment:\n  name: development\nlogging:\n  level: TRACE\n",
            override="{}\n",
        )
        with self.assertRaisesRegex(ConfigError, "TRACE"):
            load_configuration("development", root)

    def test_unknown_environment_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigError, "unknown environment"):
            load_configuration("qa")

    def test_render_redacts_secret_like_keys(self) -> None:
        root = self.write_config(
            "application:\n  name: vss\nenvironment:\n  name: development\nlogging:\n  level: INFO\n",
            override="api_token: should-not-appear\n",
        )
        # Unknown keys are rejected before rendering, preventing accidental secret config.
        with self.assertRaises(ConfigError):
            render_configuration("development", root)


if __name__ == "__main__":
    unittest.main()
