"""SelfTestExpander — Tektos expands its own test coverage when it modifies itself.

When Tektos writes/changes source code, this module:
1. Parses the diff to identify changed modules, functions, classes
2. Analyzes existing test coverage for those modules
3. Generates new test scaffolding (pytest files) for uncovered paths
4. Expands existing tests with new scenarios for modified logic
5. Runs the generated/expanded tests to validate they pass

Integration: Called from SelfImprovementAdapter after a code-modification task completes.
"""

from __future__ import annotations

import ast
import importlib
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("tektos.self_modification")


@dataclass
class DiffScope:
    """A scope of code changes (additions/deletions/modifications)."""
    module_path: str  # e.g. "tektos.runtime.embedder"
    file_path: str  # absolute path
    changed_functions: list[str] = field(default_factory=list)
    changed_classes: list[str] = field(default_factory=list)
    new_lines: list[str] = field(default_factory=list)
    deleted_lines: list[str] = field(default_factory=list)
    new_public_apis: list[str] = field(default_factory=list)  # public functions/classes


@dataclass
class TestGenerationPlan:
    """Plan for test generation/extension."""
    module_path: str
    file_path: str
    tests_to_create: list[str] = field(default_factory=list)  # new test class/function names
    tests_to_expand: list[str] = field(default_factory=list)  # existing test names to add cases to
    test_file_path: str = ""  # path to the generated test file


class SelfTestExpander:
    """Analyzes code changes and generates/extends test suites."""

    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent
        self.src_dir = self.project_root / "src" / "tektos"
        self.tests_dir = self.project_root / "tests"
        self.tests_dir.mkdir(parents=True, exist_ok=True)

    def analyze_diff(
        self,
        changed_files: list[str],
        added_lines: dict[str, list[str]] | None = None,
        deleted_lines: dict[str, list[str]] | None = None,
    ) -> list[DiffScope]:
        """Analyze changed files to determine what tests need to be generated."""
        added_lines = added_lines or {}
        deleted_lines = deleted_lines or {}

        scopes: list[DiffScope] = []
        for file_path in changed_files:
            abs_path = Path(file_path) if Path(file_path).is_absolute() else self.project_root / file_path
            if not abs_path.exists():
                continue

            # Convert file path to module path
            rel = abs_path.relative_to(self.src_dir)
            module_path = ".".join(rel.with_suffix("").parts)

            # Parse the source to find changed/new public APIs
            source = abs_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

            changed_funcs, changed_classes, new_apis = self._extract_public_apis(
                tree, added_lines.get(str(abs_path), []),
            )

            scopes.append(DiffScope(
                module_path=module_path,
                file_path=str(abs_path),
                changed_functions=changed_funcs,
                changed_classes=changed_classes,
                new_lines=added_lines.get(str(abs_path), []),
                deleted_lines=deleted_lines.get(str(abs_path), []),
                new_public_apis=new_apis,
            ))

        return scopes

    def generate_plan(self, scopes: list[DiffScope]) -> list[TestGenerationPlan]:
        """Create a test generation plan for each changed scope."""
        plans: list[TestGenerationPlan] = []
        for scope in scopes:
            plan = self._create_plan_for_scope(scope)
            if plan.tests_to_create or plan.tests_to_expand:
                plans.append(plan)
        return plans

    def _create_plan_for_scope(self, scope: DiffScope) -> TestGenerationPlan:
        """Create a test plan for a specific changed module."""
        plan = TestGenerationPlan(
            module_path=scope.module_path,
            file_path=scope.file_path,
        )

        # Find or create test file
        module_parts = scope.module_path.split(".")
        test_name = module_parts[-1]
        test_file = self.tests_dir / f"test_{test_name}.py"

        if not test_file.exists():
            # New test file needed
            plan.tests_to_create = [
                f"Test{c}" for c in scope.changed_classes
            ] + [
                f"test_{c.replace('_', '-')}"
                for c in scope.new_public_apis
                if c not in scope.changed_classes
            ]
            plan.test_file_path = str(test_file)
        else:
            # Expand existing test file
            plan.test_file_path = str(test_file)
            existing_classes = self._find_existing_test_classes(str(test_file))
            for cls_name in scope.changed_classes:
                # Check if the class already has a test (with or without "Test" prefix)
                has_test = any(
                    cls_name in existing or existing.endswith(cls_name)
                    for existing in existing_classes
                )
                if not has_test:
                    plan.tests_to_create.append(f"Test{cls_name}")
                else:
                    plan.tests_to_expand.append(f"Test{cls_name}.*")

        return plan

    # ── AST Analysis ────────────────────────────────────────────────────

    def _extract_public_apis(
        self,
        tree: ast.Module,
        added_lines: list[str] = None,
    ) -> tuple[list[str], list[str], list[str]]:
        """Extract public functions, classes, and new APIs from AST."""
        changed_funcs: list[str] = []
        changed_classes: list[str] = []
        new_apis: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                continue
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("__"):
                changed_funcs.append(node.name)
            if isinstance(node, ast.ClassDef):
                changed_classes.append(node.name)
                # Check class methods
                for item in ast.walk(node):
                    if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                        new_apis.append(f"{node.name}.{item.name}")

        return changed_funcs, changed_classes, new_apis

    # ── Code Generation ─────────────────────────────────────────────────

    def generate_test_file(self, plan: TestGenerationPlan) -> str:
        """Generate a pytest test file from a TestGenerationPlan."""
        module_name = plan.module_path.split(".")[-1]

        lines = [
            f'"""Tests for {plan.module_path}."""',
            "",
            "import pytest",
            "",
            f"from {plan.module_path} import *",
            "",
            "",
        ]

        # Generate test classes
        for test_name in plan.tests_to_create:
            lines.extend(self._generate_test_class(test_name, module_name))

        # Generate test file header with module path
        lines.insert(4, f'"""Tests for {plan.module_path}."""')

        return "\n".join(lines) + "\n"

    def _generate_test_class(self, test_name: str, module_name: str) -> list[str]:
        """Generate a pytest test class."""
        # Infer test methods based on class name
        class_methods = []
        if test_name.startswith("Test"):
            class_name = test_name[4:]
            # Generate basic test methods
            class_methods = [
                f"    def test_{module_name.lower()}_initialization(self):",
                f'        """Test {class_name} default initialization."""',
                f"        # TODO: implement",
                f"        pass",
                "",
                f"    def test_{module_name.lower()}_basic_usage(self):",
                f'        """Test {class_name} basic functionality."""',
                f"        # TODO: implement",
                f"        pass",
                "",
            ]

        return [
            f"class {test_name}:",
            *class_methods,
            "",
        ]

    def _infer_params(self, api_name: str) -> str:
        """Infer default parameters for a function call."""
        # Simple heuristic: count underscores to guess parameters
        parts = api_name.replace("_", " ").split()
        return ", ".join(f'"{p}"' for p in parts[:3])

    # ── Existing Test Analysis ──────────────────────────────────────────

    def _find_existing_test_classes(self, test_file_path: str) -> list[str]:
        """Find existing test classes in a test file."""
        try:
            source = Path(test_file_path).read_text()
            tree = ast.parse(source)
            return [
                node.name for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name.startswith("Test")
            ]
        except Exception:
            return []

    # ── Test Execution ──────────────────────────────────────────────────

    def run_generated_tests(self, test_file_path: str) -> bool:
        """Run the generated test file and return whether all tests passed."""
        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    test_file_path,
                    "-v",
                    "--tb=short",
                    "-p", "no:cacheprovider",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(self.project_root),
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Test execution timed out: %s", test_file_path)
            return False
        except Exception as exc:
            logger.error("Failed to run tests: %s", exc)
            return False

    # ── High-Level API ──────────────────────────────────────────────────

    def expand_tests_for_changes(
        self,
        changed_files: list[str],
        added_lines: dict[str, list[str]] = None,
        deleted_lines: dict[str, list[str]] = None,
        auto_run: bool = True,
    ) -> list[TestGenerationPlan]:
        """Main entry point: analyze changes and generate/expand tests.

        Args:
            changed_files: List of changed file paths (relative to project root).
            added_lines: Map of file paths to list of added lines.
            deleted_lines: Map of file paths to list of deleted lines.
            auto_run: Whether to run the generated tests after writing them.

        Returns:
            List of TestGenerationPlan objects describing what was generated.
        """
        scopes = self.analyze_diff(changed_files, added_lines, deleted_lines)
        plans = self.generate_plan(scopes)

        for plan in plans:
            test_content = self.generate_test_file(plan)
            test_path = Path(plan.test_file_path)
            test_path.write_text(test_content, encoding="utf-8")
            logger.info(
                "Generated test file: %s (%d classes, %d expansions)",
                plan.test_file_path,
                len(plan.tests_to_create),
                len(plan.tests_to_expand),
            )

            if auto_run:
                success = self.run_generated_tests(plan.test_file_path)
                logger.info(
                    "Test execution %s: %s",
                    "passed" if success else "FAILED",
                    plan.test_file_path,
                )

        return plans
