from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


class IaCContractTests(unittest.TestCase):
    def setUp(self) -> None:
        root = Path(__file__).parents[2]
        with (root / "infrastructure/contracts/capabilities.schema.json").open(encoding="utf-8") as stream:
            self.validator = Draft202012Validator(json.load(stream))

    def test_local_contract_shape_is_valid(self) -> None:
        contract = {
            "provider": "local",
            "environment": "development",
            "project": "vss",
            "capabilities": {
                "networking": True,
                "object_storage": True,
                "relational_database": False,
                "cache": False,
                "durable_messaging": False,
                "gpu_compute": False,
            },
            "services": {
                "object_storage": {
                    "endpoint": "http://127.0.0.1:9000",
                    "health_endpoint": "http://127.0.0.1:9000/minio/health/live",
                }
            },
            "resource_ids": {"network": "network-id", "volume": "volume-id", "container": "container-id"},
            "deployment": {"managed_by": "OpenTofu", "revision": "local"},
        }
        self.assertEqual(list(self.validator.iter_errors(contract)), [])

    def test_unknown_capability_is_rejected(self) -> None:
        contract = {"provider": "local", "environment": "development", "project": "vss", "capabilities": {"unknown": True}}
        errors = list(self.validator.iter_errors(contract))
        self.assertTrue(any("unknown" in error.message for error in errors))


if __name__ == "__main__":
    unittest.main()
