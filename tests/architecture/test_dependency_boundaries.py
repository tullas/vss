from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"


def _imports(package: str) -> list[tuple[Path, str]]:
    findings: list[tuple[Path, str]] = []
    for path in sorted((SRC / package).glob("**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                findings.extend((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                findings.append((path, node.module))
    return findings


def _top_level(module: str) -> str:
    return module.partition(".")[0]


class DependencyBoundaryTests(unittest.TestCase):
    def assert_package_avoids(self, package: str, forbidden: set[str]) -> None:
        violations = [
            f"{path.relative_to(ROOT)} imports {module}"
            for path, module in _imports(package)
            if _top_level(module) in forbidden
        ]
        self.assertEqual([], violations, "\n".join(violations))

    def test_contract_packages_do_not_depend_on_execution_or_cli_layers(self) -> None:
        forbidden = {
            "vss_capabilities",
            "vss_commands",
            "vss_reasoning",
            "vss_reasoning_providers",
            "vss_reasoning_strategies",
            "vss_runtime",
            "vss_workflows",
        }
        for package in (
            "vss_context_contracts",
            "vss_knowledge_contracts",
            "vss_movie_contracts",
            "vss_resource_contracts",
            "vss_reasoning_contracts",
        ):
            with self.subTest(package=package):
                self.assert_package_avoids(package, forbidden)

    def test_resource_admission_remains_inert(self) -> None:
        self.assert_package_avoids(
            "vss_resource_admission",
            {"vss_capabilities", "vss_commands", "vss_reasoning", "vss_reasoning_providers",
             "vss_reasoning_strategies", "vss_runtime", "vss_workflows"},
        )

    def test_semantic_implementations_do_not_depend_on_effect_or_cli_layers(self) -> None:
        forbidden = {"vss_capabilities", "vss_commands", "vss_runtime", "vss_workflows"}
        for package in ("vss_reasoning_providers", "vss_reasoning_strategies"):
            with self.subTest(package=package):
                self.assert_package_avoids(package, forbidden)

    def test_reasoning_gateway_layer_does_not_depend_on_cli_or_effect_layers(self) -> None:
        self.assert_package_avoids(
            "vss_reasoning", {"vss_capabilities", "vss_commands", "vss_workflows"}
        )

    def test_command_runner_dependency_is_quarantined_to_legacy_workflow_adapter(self) -> None:
        allowed = {Path("src/vss_workflows/operations.py")}
        actual: set[Path] = set()
        for path in sorted(SRC.glob("vss_*/**/*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom) or not node.module:
                    continue
                if node.module == "vss_commands" and any(
                    alias.name == "CommandRunner" for alias in node.names
                ):
                    actual.add(path.relative_to(ROOT))
        self.assertEqual(allowed, actual)


if __name__ == "__main__":
    unittest.main()
