from __future__ import annotations

from typing import Any

from vss_reasoning.models import DeterministicReasoningContext
from vss_reasoning_providers.contracts import DeterministicOptionsProvider


class DeterministicGenerateOptionsStrategy:
    __slots__ = ()

    def generate(
        self,
        context: DeterministicReasoningContext,
        provider: DeterministicOptionsProvider,
    ) -> tuple[dict[str, Any], int, int]:
        candidates = provider.generate_option_primitives(context)
        constraint_ids = tuple(item["id"] for item in context.payload["constraints"])
        options = [
            {
                "id": candidate.profile_id,
                "title": candidate.title,
                "description": candidate.description,
                "benefits": list(candidate.benefits),
                "drawbacks": list(candidate.drawbacks),
                "risks": list(candidate.risks),
                # In v1, "satisfied" means structurally incorporated, never
                # verified real-world satisfaction. The result limitations
                # make that qualification explicit.
                "constraints_satisfied": list(constraint_ids),
                "constraints_not_satisfied": [],
                "evidence_references": [],
            }
            for candidate in candidates.options
        ]
        payload = {
            "option_set_id": f"option-set-{context.semantic_content_digest[:32]}",
            "objective_summary": context.payload["objective"],
            "options": options,
            "common_sections": {
                "facts": [],
                "assumptions": [
                    {
                        "id": "structural_method",
                        "statement": "The declared constraints are treated as required structural inputs.",
                    }
                ],
                "unknowns": [
                    {"id": "feasibility", "statement": "Real-world feasibility has not been established."},
                    {"id": "cost", "statement": "Real-world cost has not been measured."},
                    {"id": "timing", "statement": "A delivery timeline has not been established."},
                    {"id": "quality", "statement": "Outcome quality has not been evaluated."},
                    {
                        "id": "external_validation",
                        "statement": "No external validation has been performed.",
                    },
                ],
                "constraints": [
                    {"id": item["id"], "statement": item["statement"], "kind": "required"}
                    for item in context.payload["constraints"]
                ],
                "evidence_references": [],
                "confidence": {
                    "level": "low",
                    "basis": "A deterministic structural method produced the options without external knowledge or evidence.",
                    "qualifications": [
                        "Confidence describes the method's limited evidentiary basis and grants no authority."
                    ],
                },
                "limitations": [
                    {
                        "id": "structural_only",
                        "statement": "The options are structural alternatives, not validated recommendations or plans.",
                    },
                    {
                        "id": "no_external_analysis",
                        "statement": "No external knowledge, feasibility, cost, quality, or execution analysis was performed.",
                    },
                    {
                        "id": "constraint_semantics",
                        "statement": "A satisfied constraint reference means structurally incorporated, not proven satisfied in reality.",
                    },
                ],
            },
        }
        if context.provider_context:
            notes = context.provider_context.get("selected_notes", [])
            refs = context.provider_context.get("evidence_references", [])
            payload["common_sections"]["assumptions"].append({
                "id": "governed_context",
                "statement": f"{len(notes)} bounded governed context note(s) were supplied; their claims remain unverified.",
            })
            payload["common_sections"]["limitations"].append({
                "id": "context_qualification",
                "statement": "Context purpose, uncertainty, conflicts, and evidence references remain qualified and non-authorizing.",
            })
            if refs:
                payload["common_sections"]["limitations"].append({
                    "id": "context_evidence",
                    "statement": "Evidence identifiers are inert and were not resolved by the provider.",
                })
        return payload, candidates.provider_calls, candidates.iterations
