# Local Performance Laboratory

M3.3 measures the real M3.2 `generate_options/1 -> option_set/1` Gateway path
under bounded local concurrency. It is a development laboratory, not a
production load test. A successful run grants no execution authority,
production approval, capacity claim, availability claim, or SLO compliance.
Every request uses normal M3.1 validation, M3.2 policy and fixed implementation
resolution, independent result validation, semantic-honesty checks, and the
development audit path. The harness never calls the provider directly.

## Versioned profiles

All profiles are repository-owned, immutable, version `1`, and use workload
`reasoning.generate-options/1`, fixture
`generate-options-runtime-valid/1`, four options, and expected semantic-content
digest `74da3d2ab42310fd661832264f3169f642aa55b4ba465be945af4f9cb46869a7`.

| Profile | Warm-up | Measured | Concurrency / outstanding | Request / total timeout | Stress | Endurance |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `ci_safe` | 1 | 8 | 2 / 2 | 2 s / 30 s | none | none |
| `laptop_small` | 2 | 25 | 4 / 4 | 2 s / 120 s | 1, 2, 4, 8; 8 requests each | at most 3 s and 100 requests |
| `laptop_standard` | 5 | 100 | 8 / 8 | 2 s / 300 s | 1, 2, 4, 8, 16; 16 requests each | at most 5 s and 200 requests |

The global concurrency ceiling is 16 and the per-profile request ceiling is
500. Larger machines do not silently receive more work. There are no CLI
numeric overrides, arbitrary workload/command paths, provider/strategy
selection, network targets, or report paths. `--no-endurance` skips only the
optional bounded endurance phase.

## Lifecycle and measurement

One shared immutable built-in Gateway is the supported lifecycle under test.
The harness performs smoke, bounded warm-up, measured concurrency, optional
fixed-step stress, and optional short endurance phases. It keeps at most the
profile's `maximum_outstanding` futures live, tracks every future, uses an
explicit executor shutdown, and stops submission at the total monotonic
deadline. Warm-up is excluded from latency and throughput.

Latency wraps the complete Gateway call. Percentiles use deterministic
nearest-rank: for `N` ordered samples, percentile `P` selects
`ceil(P/100 * N)`, with a minimum rank of one. Reports contain sample count,
minimum, mean, p50, p90, p95, p99, and maximum. High percentiles are retained
for format consistency but are explicitly warned as weak evidence below 100
samples. Throughput is successful measured requests divided by measured-phase
monotonic wall duration, never the sum of individual durations.

Stress observes bounded saturation. Latency growth is not a failure by itself;
semantic mismatch, lost work, malformed audit, timeouts outside policy, or
accounting failures are. Endurance observes repeated digest stability, audit
growth, thread cleanup, and approximate process resources. It is intentionally
short and is not a soak test. Formal Runtime admission control and backpressure
remain future work; the harness's sliding submission window is not a new
production concurrency contract.

## Determinism and audit verification

Every invocation receives independently copied input and unique request and
correlation IDs. The harness requires exact request/result binding, the
expected option count, and the same semantic-content digest. Metadata variation
must not change semantic content. Dry-run is measured separately: it validates
and resolves readiness, invokes no provider, produces no `OptionSet`, and
reports no semantic-content digest.

Audit verification records the existing JSONL byte offset before the run, then
selects only the run's correlation identities from bounded appended data. It
requires exactly one terminal record per invocation and verifies request,
task, family, strategy, provider, status, event type, execution identity, and
digest semantics. A bounded pre-run anchor plus device and inode identity makes
replacement, truncation, and rotation fail closed; partial trailing records are
rejected. It never truncates developer audit state and does not place raw lines
in a report. The existing writer serializes complete bounded records with an
in-process lock and verifies every append byte. Local JSONL remains a development
facility; cross-process ordering, crash durability, tamper resistance, rotation,
and production backpressure remain unresolved.

## Reports and resource observations

Reports conform to `schemas/performance-report-v1.schema.json`, reject unknown
fields, and are limited to 256 KiB. They are written atomically with mode
`0600` beneath the ignored `.local/performance/reports/` directory. Callers
cannot choose a path; existing or symbolic-link destinations fail closed. The
report SHA-256 excludes its own digest field and provides deterministic
integrity evidence only—not a signature, authenticity, trust, approval, or
certification.

The allowlisted environment metadata is operating system, release,
architecture, Python version, logical CPU count, safely available memory, WSL
status, CI status, profile, and commit when a local loose Git ref is available.
It excludes hostname, username, IP address, home path, environment-variable
contents, cloud metadata, serial numbers, and filesystem paths. Resource
observations include process CPU time, maximum resident set size, active thread
count, Linux file-descriptor count when available, and audit counts. Memory,
descriptor, and process-wide thread observations are approximate and platform
dependent. Maximum RSS is normalized to KiB on Linux and macOS; small changes
are not fragile CI failures.

Reports and command output contain no request payload, objective, constraints,
`OptionSet`, raw audit lines, secrets, provider-native content, prompts, or
hidden reasoning. M3.3 establishes structural correctness evidence and report
format only. It stores no approved latency baseline and applies no relative
latency gate yet; future comparisons must match profile and compatible
environment classes.

## Commands

```bash
vss performance reasoning --profile ci_safe --environment development
vss performance reasoning --profile laptop_small --environment development
vss performance reasoning --profile laptop_standard --environment development
vss performance reasoning --profile ci_safe --environment development --dry-run
```

All commands preserve the VSS outer response envelope. Standard CI runs only
`ci_safe`, without network, cloud, paid service, API key, GPU, model download,
or external identity provider.

## Boundaries and limitations

Laptop evidence does not prove production throughput, multi-node scaling,
GPU/media capacity, external-provider performance, production audit durability,
or production cancellation/isolation. Built-in Python remains trusted
in-process code and cooperative deadlines are not a sandbox. This milestone
adds no AI model, prompt, external provider, Knowledge Package, retrieval,
Plan IR, approval, capability/workflow execution, autonomous behavior,
distributed worker, queue, database, cloud infrastructure, autoscaling, or
production SLO.
