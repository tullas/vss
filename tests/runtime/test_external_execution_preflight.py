from __future__ import annotations

import socket
import threading
import unittest

from vss_runtime.external_preflight import (
    ExternalExecutionPreflight,
    ExternalExecutionPreflightFailure,
    ExternalExecutionPreflightSpec,
)


DIGEST = "1" * 64


def spec(**changes) -> ExternalExecutionPreflightSpec:
    values = {
        "endpoint": "https://api.openai.com/v1/images/generations",
        "credential_environment_variable": "VSS_EXPERIMENT_API_KEY",
        "provider_request_digest": DIGEST,
        "authoritative_provider_request_digest": DIGEST,
        "maximum_provider_attempts": 1,
        "maximum_estimated_cost_usd": "0.07",
        "authorized_cost_ceiling_usd": "0.07",
        "dns_timeout_seconds": 0.1,
    }
    values.update(changes)
    return ExternalExecutionPreflightSpec(**values)


class ExternalExecutionPreflightTests(unittest.TestCase):
    def test_success_uses_presence_only_and_exact_endpoint_hostname(self):
        inspected = []
        resolutions = []

        def present(name):
            inspected.append(name)
            return name == "VSS_EXPERIMENT_API_KEY"

        def resolve(hostname, port):
            resolutions.append((hostname, port))
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", port))]

        result = ExternalExecutionPreflight(
            environment_contains=present,
            resolver=resolve,
        ).run(spec())

        self.assertTrue(result.credential_available)
        self.assertTrue(result.direct_egress_environment)
        self.assertTrue(result.dns_ready)
        self.assertEqual(result.provider_call_count, 0)
        self.assertFalse(result.attempt_reserved)
        self.assertEqual(resolutions, [("api.openai.com", 443)])
        self.assertIn("VSS_EXPERIMENT_API_KEY", inspected)

    def test_missing_credential_stops_before_dns(self):
        resolutions = []
        preflight = ExternalExecutionPreflight(
            environment_contains=lambda _: False,
            resolver=lambda *args: resolutions.append(args),
        )
        with self.assertRaises(ExternalExecutionPreflightFailure) as raised:
            preflight.run(spec())
        self.assertEqual(raised.exception.preflight_diagnostic["classification"], "credential_unavailable")
        self.assertEqual(resolutions, [])

    def test_proxy_presence_fails_without_reading_values_or_resolving(self):
        inspected = []
        resolutions = []

        def present(name):
            inspected.append(name)
            return name == "HTTPS_PROXY"

        with self.assertRaises(ExternalExecutionPreflightFailure) as raised:
            ExternalExecutionPreflight(
                environment_contains=present,
                resolver=lambda *args: resolutions.append(args),
            ).run(spec())
        self.assertEqual(raised.exception.preflight_diagnostic["classification"],
                         "proxy_environment_unsupported")
        self.assertEqual(resolutions, [])
        self.assertNotIn("VSS_EXPERIMENT_API_KEY", inspected)

    def test_dns_failure_and_timeout_are_closed(self):
        for resolver, expected in (
            (lambda *_: (_ for _ in ()).throw(socket.gaierror()), "dns"),
            (lambda *_: threading.Event().wait(1), "dns_timeout"),
        ):
            with self.subTest(expected=expected), self.assertRaises(
                    ExternalExecutionPreflightFailure) as raised:
                ExternalExecutionPreflight(
                    environment_contains=lambda name: name == "VSS_EXPERIMENT_API_KEY",
                    resolver=resolver,
                ).run(spec(dns_timeout_seconds=0.1))
            self.assertEqual(raised.exception.preflight_diagnostic, {
                "classification": expected,
                "provider_call_count": 0,
                "attempt_reserved": False,
            })

    def test_invalid_binding_attempt_ceiling_and_cost_fail_before_host_checks(self):
        invalid = (
            {"authoritative_provider_request_digest": "2" * 64},
            {"maximum_provider_attempts": 2},
            {"maximum_estimated_cost_usd": "0.08"},
            {"maximum_estimated_cost_usd": "NaN"},
            {"endpoint": "http://api.openai.com/v1/images/generations"},
            {"endpoint": "https://api.openai.com:invalid/v1/images/generations"},
        )
        for changes in invalid:
            with self.subTest(changes=changes), self.assertRaises(ExternalExecutionPreflightFailure):
                spec(**changes)


if __name__ == "__main__":
    unittest.main()
