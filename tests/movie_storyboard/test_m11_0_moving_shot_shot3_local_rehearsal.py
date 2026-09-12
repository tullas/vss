from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from m11_0_moving_shot_recovery_support import (
    OPERATION, SHOT3_DIGEST, SHOT3_INPUT, SHOT3_NAMESPACE,
    MovingShotRecoveryHarness, shot3_admission,
)


@unittest.skipUnless(SHOT3_INPUT.is_file(), "requires the ignored local Shot 3 final-frame PNG")
class LocalShot3RecoveryRehearsalTests(MovingShotRecoveryHarness, unittest.TestCase):
    def test_authoritative_shot3_package_restarts_and_recovers_without_resubmission(self):
        admission = shot3_admission()
        self.assertEqual(admission.request_sha256, SHOT3_DIGEST)
        namespace = (f"{admission.request['scope']['production_id']}/"
                     f"{admission.request['scope']['shot_id']}")
        self.assertEqual(namespace, SHOT3_NAMESPACE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = self.authorize(root, admission)
            generation_submissions = []
            operation_polls = []

            def transport(url, body, _headers, _timeout, _maximum):
                if url.endswith(":predictLongRunning"):
                    generation_submissions.append(url)
                    return 200, json.dumps({"name": OPERATION}).encode()
                self.assertTrue(url.endswith(":fetchPredictOperation"))
                self.assertEqual(json.loads(body)["operationName"], OPERATION)
                operation_polls.append(url)
                if len(operation_polls) == 1:
                    raise urllib.error.URLError("offline interruption after acceptance")
                return 200, json.dumps({"done": True, "response": {"videos": [{
                    "bytesBase64Encoded": "AAAAGGZ0eXBpc29tAAACAGlzb21pc28y",
                    "mimeType": "video/mp4",
                }]}}).encode()

            with self.runtime_environment():
                _, initial_code = self.run_runtime(self.controller(root, transport), admission, "generate")
            self.assertNotEqual(initial_code, 0)
            ledger_path = state / f"{SHOT3_DIGEST}.attempt.json"
            after_interruption = json.loads(ledger_path.read_text())
            self.assertEqual(after_interruption["status"], "failed")
            self.assertEqual(after_interruption["attempts"], 1)
            self.assertEqual(after_interruption["operation_name"], OPERATION)
            self.assertEqual(after_interruption["execution_namespace"], SHOT3_NAMESPACE)

            with self.runtime_environment():
                recovered, recovery_code = self.run_runtime(self.controller(root, transport), admission, "recover")
            self.assertEqual(recovery_code, 0, recovered)
            self.assertEqual(recovered["output"]["status"], "recovered_quarantined")
            self.assertEqual(recovered["output"]["provider_call_count"], 0)
            self.assertTrue(Path(recovered["output"]["video"]).is_file())
            self.assertTrue(Path(recovered["output"]["evidence"]).is_file())
            self.assertEqual(len(generation_submissions), 1)
            self.assertEqual(len(operation_polls), 2)
            self.assertEqual(json.loads(ledger_path.read_text())["attempts"], 1)
            self.assertEqual(json.loads(ledger_path.read_text())["request_sha256"], SHOT3_DIGEST)
            self.assertEqual(json.loads(ledger_path.read_text())["execution_namespace"], SHOT3_NAMESPACE)


if __name__ == "__main__":
    unittest.main()
