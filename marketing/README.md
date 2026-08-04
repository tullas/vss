# Autonomous AI Marketing System

This directory contains the first implementation slice of the VSS autonomous growth platform.

## Design goals

- Evidence before claims: agents may not invent facts, trends, audience data, metrics, quotations, or competitor information.
- Human approval before publishing: generated assets are drafts until an explicit approval gate is satisfied.
- Provider-neutral orchestration: model calls are isolated behind an adapter so open-source or hosted models can be substituted.
- Structured outputs: every agent returns machine-validated JSON-compatible data.
- Traceability: every factual claim records its source identifier and confidence.
- Economical operation: deterministic checks run before model calls; low-cost models handle classification and formatting.

## Initial agents

1. `researcher` gathers verified audience questions, current trends, and competitor evidence.
2. `strategist` converts evidence into a campaign brief without introducing new facts.
3. `creator` drafts channel-specific content from the approved brief.
4. `fact_checker` rejects unsupported claims and unverifiable statistics.
5. `brand_guardian` checks tone, positioning, prohibited wording, and calls to action.
6. `publisher` prepares a publish package but cannot publish without approval.
7. `analyst` evaluates imported platform metrics and recommends experiments.
8. `orchestrator` controls state transitions, budgets, retries, and audit records.

## Safety gates

A content item can move to `READY_FOR_APPROVAL` only when:

- each factual claim has at least one evidence reference;
- no source is expired for a time-sensitive claim;
- the fact checker returns `pass`;
- the brand guardian returns `pass`;
- the draft contains no fabricated testimonial, performance promise, or engagement metric;
- required disclosures are present;
- a deterministic policy check succeeds.

Publishing is deliberately excluded from this first slice. The system produces auditable drafts for review.

## Run locally

```bash
python -m marketing.src.orchestrator
python -m unittest discover -s marketing/tests -p 'test_*.py'
```

## Next implementation slice

- Add model adapters for a local OpenAI-compatible endpoint and optional hosted providers.
- Add source connectors for the website, Instagram exports, Search Console, and analytics.
- Add a PostgreSQL event store and object storage for campaign artifacts.
- Add scheduled workflows and platform publishing adapters behind explicit approval policies.
