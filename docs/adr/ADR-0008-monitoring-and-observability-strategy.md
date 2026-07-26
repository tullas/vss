# ADR-0008: Monitoring and Observability Strategy

## Status

Accepted

## Date

2026-07-25

## Context

As automation and deployments grow, operators need timely health signals,
performance evidence, and cross-step context for troubleshooting and
historical analysis.

## Decision

The project uses the three observability pillars:

1. **Logs** use ADR-0002's timestamped, levelled format. Operations with a
   trace include `trace_id=<id>` for correlation.
2. **Metrics** use `emit_metric name value [unit]`. They are logged in a
   parseable form and may additionally be appended to the runtime-configured
   `METRICS_FILE` for collection by the environment's agent.
3. **Traces** start with `begin_trace operation` and end with
   `end_trace operation status`, using a generated 128-bit hexadecimal ID.

`scripts/lib/observability.sh` implements these primitives. Deployment uses
them to record attempts, successes, failures, rollback attempts, and duration.

The monitoring platform is environment-owned. It must collect logs and metrics,
retain them according to operational policy, and implement the alert and
dashboard contract in `monitoring/`. Alerts must route to an owned escalation
path. Dashboard and alert configuration must never include secret values.

## Consequences

Automation gains correlated diagnostics without coupling this repository to a
specific vendor. Operators must configure a collector, storage, alert routing,
and dashboards in each environment. Metric logs are a compatibility mechanism,
not a substitute for a production metrics backend.

## Verification

Run:

```bash
bash tests/observability-test.sh
```
