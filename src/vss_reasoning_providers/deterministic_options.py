from __future__ import annotations

from vss_reasoning.models import CandidateOptions, DeterministicReasoningContext, OptionPrimitive


_PROFILES = (
    OptionPrimitive(
        "strict_constraints", "Strict constraints",
        "Structure the approach around every declared constraint before considering refinements.",
        ("Makes each declared constraint visible in the approach.",),
        ("May reduce flexibility when constraints compete.",),
        ("Structural inclusion does not prove real-world feasibility.",),
    ),
    OptionPrimitive(
        "required_first", "Required-first",
        "Establish the bounded requirements first, then evaluate optional refinements separately.",
        ("Keeps the initial decision focused on declared requirements.",),
        ("May defer useful refinements.",),
        ("The request does not establish which refinements are feasible.",),
    ),
    OptionPrimitive(
        "minimal_complexity", "Minimal complexity",
        "Prefer the smallest structural approach that explicitly incorporates the declared constraints.",
        ("Limits structural complexity and initial scope.",),
        ("May provide fewer optimization opportunities.",),
        ("Simplicity alone does not establish suitability.",),
    ),
    OptionPrimitive(
        "phased", "Phased adoption",
        "Organize the approach into bounded stages while retaining every declared constraint as a gate.",
        ("Supports incremental validation and controlled commitment.",),
        ("Introduces stage boundaries and coordination overhead.",),
        ("No schedule or stage feasibility has been established.",),
    ),
    OptionPrimitive(
        "conservative", "Conservative change",
        "Favor a smaller initial change and require validation before expanding its scope.",
        ("Limits initial uncertainty and blast radius.",),
        ("May reduce the pace or ambition of change.",),
        ("Lower structural ambition does not guarantee lower real-world risk.",),
    ),
    OptionPrimitive(
        "balanced", "Balanced emphasis",
        "Distribute attention across the declared constraints and evaluation dimensions without selecting a winner.",
        ("Makes explicit trade-off review easier.",),
        ("May not optimize any single dimension.",),
        ("The relative importance of dimensions is not known.",),
    ),
    OptionPrimitive(
        "efficiency_focused", "Efficiency focused",
        "Minimize avoidable resource and coordination overhead while retaining the declared constraints.",
        ("Highlights bounded resource use and avoidable work.",),
        ("Efficiency emphasis may underweight other qualities.",),
        ("No measured resource or cost evidence is available.",),
    ),
    OptionPrimitive(
        "validation_first", "Validation first",
        "Begin with the smallest testable commitment and require evidence before broader adoption.",
        ("Makes uncertainty and verification explicit.",),
        ("Delays broader commitment until validation completes.",),
        ("The required validation method and results are not yet known.",),
    ),
)


class BuiltinDeterministicOptionsProvider:
    __slots__ = ()

    def generate_option_primitives(self, context: DeterministicReasoningContext) -> CandidateOptions:
        count = context.payload["desired_option_count"]
        return CandidateOptions(_PROFILES[:count], provider_calls=1, iterations=count)
