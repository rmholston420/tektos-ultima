"""Tests for SelfTestExpander — diff analysis, test generation, and execution."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.tektos.self_modification.self_test_expander import (
    DiffScope,
    SelfTestExpander,
    TestPlanData,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def expander(tmp_path):
    """Create a SelfTestExpander with tmp_path as project root."""
    # Create the expected directory structure
    src_dir = tmp_path / "src" / "tektos"
    tests_dir = tmp_path / "tests"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)

    expander = SelfTestExpander(project_root=str(tmp_path))
    expander.src_dir = src_dir
    expander.tests_dir = tests_dir
    return expander


# ── DiffScope ────────────────────────────────────────────────────────────────

class TestDiffScope:
    def test_default_fields(self):
        scope = DiffScope(
            module_path="tektos.runtime.embedder",
            file_path="/path/to/embedder.py",
        )
        assert scope.module_path == "tektos.runtime.embedder"
        assert scope.file_path == "/path/to/embedder.py"
        assert scope.changed_functions == []
        assert scope.changed_classes == []
        assert scope.new_lines == []
        assert scope.deleted_lines == []
        assert scope.new_public_apis == []

    def test_with_changes(self):
        scope = DiffScope(
            module_path="tektos.runtime.embedder",
            file_path="/path/to/embedder.py",
            changed_functions=["embed", "similar"],
            changed_classes=["EmbedderClient"],
            new_lines=["    def new_method(self):", "        pass"],
        )
        assert "embed" in scope.changed_functions
        assert "EmbedderClient" in scope.changed_classes
        assert len(scope.new_lines) == 2


# ── TestGenerationPlan ──────────────────────────────────────────────────────

class TestTestPlanData:
    def test_defaults(self):
        plan = TestPlanData(
            module_path="tektos.existing",
            file_path="/path/to/existing.py",
            tests_to_create=["TestNewClass"],
        )
        assert plan.module_path == "tektos.existing"
        assert plan.tests_to_create == ["TestNewClass"]
        assert plan.tests_to_expand == []
        assert plan.test_file_path == ""


# ── SelfTestExpander — Analysis ────────────────────────────────────────────

class TestSelfTestExpanderInit:
    def test_default_project_root(self, expander):
        assert expander.src_dir.exists()
        assert expander.tests_dir.exists()

    def test_custom_project_root(self, tmp_path):
        expander = SelfTestExpander(project_root=str(tmp_path))
        assert expander.project_root == tmp_path


class TestSelfTestExpanderAnalyzeDiff:
    def test_analyze_simple_class(self, expander):
        """Test analysis of a file with a simple class."""
        # Create a source file
        src_file = expander.src_dir / "embedder.py"
        src_file.write_text('''
class EmbedderClient:
    def __init__(self, url):
        self.url = url

    def embed(self, text):
        return [0.1, 0.2]

    def similar(self, query, corpus):
        return []

def analyze_diff(changed_files):
    pass
''')

        scopes = expander.analyze_diff(["src/tektos/embedder.py"])
        assert len(scopes) == 1
        scope = scopes[0]
        # Module path is relative to src_dir; order doesn't matter with ast.walk
        assert "embed" in scope.changed_functions
        assert "similar" in scope.changed_functions
        assert "EmbedderClient" in scope.changed_classes

    def test_analyze_multiple_classes(self, expander):
        """Test analysis of a file with multiple classes."""
        src_file = expander.src_dir / "multi.py"
        src_file.write_text('''
class FirstClass:
    def method_a(self):
        pass

class SecondClass:
    def method_b(self):
        pass
''')

        scopes = expander.analyze_diff(["src/tektos/multi.py"])
        assert len(scopes) == 1
        assert "FirstClass" in scopes[0].changed_classes
        assert "SecondClass" in scopes[0].changed_classes

    def test_analyze_nonexistent_file(self, expander):
        """Test that nonexistent files are skipped."""
        scopes = expander.analyze_diff(["src/tektos/nonexistent.py"])
        assert scopes == []

    def test_analyze_with_added_lines(self, expander):
        """Test that added lines are tracked."""
        src_file = expander.src_dir / "with_changes.py"
        src_file.write_text('''
class MyClass:
    def existing_method(self):
        pass

    def new_method(self):
        pass
''')

        added = {str(src_file): ["    def new_method(self):", "        pass"]}
        scopes = expander.analyze_diff(
            ["src/tektos/with_changes.py"],
            added_lines=added,
        )
        assert len(scopes) == 1
        assert len(scopes[0].new_lines) == 2


# ── SelfTestExpander — Plan Generation ─────────────────────────────────────

class TestSelfTestExpanderGeneratePlan:
    def test_generate_plan_new_file(self, expander):
        """Test plan generation for a new module with no existing tests."""
        src_file = expander.src_dir / "new_module.py"
        src_file.write_text('''
class NewClass:
    def do_something(self):
        pass
''')

        scopes = expander.analyze_diff(["src/tektos/new_module.py"])
        plans = expander.generate_plan(scopes)

        assert len(plans) >= 1
        assert any("NewClass" in t for t in plans[0].tests_to_create)
        assert plans[0].test_file_path.endswith("test_new_module.py")

    def test_generate_plan_expand_existing(self, expander):
        """Test plan generation that expands existing tests."""
        # Create source file
        src_file = expander.src_dir / "existing.py"
        src_file.write_text('''
class ExistingClass:
    def method_a(self):
        pass
''')

        # Create existing test file
        test_file = expander.tests_dir / "test_existing.py"
        test_file.write_text('''
class TestExistingClass:
    def test_basic(self):
        pass
''')

        scopes = expander.analyze_diff(["src/tektos/existing.py"])
        plans = expander.generate_plan(scopes)

        # Should want to expand existing, not create new
        # cls_name is "ExistingClass", existing_classes has "TestExistingClass"
        assert any("ExistingClass" in t for t in plans[0].tests_to_expand)

    def test_generate_plan_empty_scope(self, expander):
        """Test that empty scopes produce no plans."""
        scopes = expander.analyze_diff(["src/tektos/nonexistent.py"])
        plans = expander.generate_plan(scopes)
        assert plans == []


# ── SelfTestExpander — Test Generation ─────────────────────────────────────

class TestSelfTestExpanderGenerateTestFile:
    def test_generate_basic_test_file(self, expander):
        """Test generation of a basic test file."""
        plan = TestPlanData(
            module_path="tektos.embedder",
            file_path="/path/to/embedder.py",
            tests_to_create=["TestEmbedderClient"],
        )

        content = expander.generate_test_file(plan)
        assert "Tests for tektos.embedder" in content
        assert "import pytest" in content
        assert "class TestEmbedderClient" in content

    def test_generate_multiple_test_classes(self, expander):
        """Test generation with multiple test classes."""
        plan = TestPlanData(
            module_path="tektos.embedder",
            file_path="/path/to/embedder.py",
            tests_to_create=["TestEmbedderClient", "TestEmbeddingResult"],
        )

        content = expander.generate_test_file(plan)
        assert "class TestEmbedderClient" in content
        assert "class TestEmbeddingResult" in content


# ── SelfTestExpander — Test Execution ──────────────────────────────────────

class TestSelfTestExpanderRunTests:
    def test_run_tests_pass(self, expander):
        """Test that passing tests return True."""
        test_file = expander.tests_dir / "test_pass.py"
        test_file.write_text('''
def test_pass():
    assert True
''')

        result = expander.run_generated_tests(str(test_file))
        assert result is True

    def test_run_tests_fail(self, expander):
        """Test that failing tests return False."""
        test_file = expander.tests_dir / "test_fail.py"
        test_file.write_text('''
def test_fail():
    assert False
''')

        result = expander.run_generated_tests(str(test_file))
        assert result is False

    def test_run_nonexistent_file(self, expander):
        """Test execution of a nonexistent file."""
        result = expander.run_generated_tests("/nonexistent/test.py")
        assert result is False


# ── SelfTestExpander — End-to-End ──────────────────────────────────────────

class TestSelfTestExpanderEndToEnd:
    def test_expand_tests_for_changes(self, expander):
        """Full integration test: analyze changes and generate tests."""
        # Create source file
        src_file = expander.src_dir / "e2e_module.py"
        src_file.write_text('''
class E2EClass:
    def method_a(self):
        pass

    def method_b(self):
        pass
''')

        plans = expander.expand_tests_for_changes(
            ["src/tektos/e2e_module.py"],
            auto_run=False,
        )

        assert len(plans) >= 1
        plan = plans[0]
        assert any("E2EClass" in t for t in plan.tests_to_create)
        assert plan.test_file_path.endswith("test_e2e_module.py")

        # Verify test file was created
        test_path = Path(plan.test_file_path)
        assert test_path.exists()
        content = test_path.read_text()
        assert "class TestE2EClass" in content

    def test_expand_tests_for_multiple_changes(self, expander):
        """Test expansion for multiple changed files."""
        # Create multiple source files
        src_file1 = expander.src_dir / "module1.py"
        src_file1.write_text('''
class Module1Class:
    def method_a(self):
        pass
''')

        src_file2 = expander.src_dir / "module2.py"
        src_file2.write_text('''
class Module2Class:
    def method_b(self):
        pass
''')

        plans = expander.expand_tests_for_changes(
            ["src/tektos/module1.py", "src/tektos/module2.py"],
            auto_run=False,
        )

        assert len(plans) == 2
        module_names = [p.module_path for p in plans]
        assert "module1" in module_names
        assert "module2" in module_names


# ── SelfTestExpander — Edge Cases ──────────────────────────────────────────

class TestSelfTestExpanderEdgeCases:
    def test_empty_source_file(self, expander):
        """Test analysis of an empty file."""
        src_file = expander.src_dir / "empty.py"
        src_file.write_text("")

        scopes = expander.analyze_diff(["src/tektos/empty.py"])
        assert len(scopes) == 1
        assert scopes[0].changed_functions == []
        assert scopes[0].changed_classes == []

    def test_file_with_only_private_methods(self, expander):
        """Test that private methods are excluded."""
        src_file = expander.src_dir / "private.py"
        src_file.write_text('''
class MyClass:
    def _private_method(self):
        pass

    def public_method(self):
        pass
''')

        scopes = expander.analyze_diff(["src/tektos/private.py"])
        assert "_private_method" not in scopes[0].changed_functions
        assert "public_method" in scopes[0].changed_functions

    def test_file_with_magic_methods(self, expander):
        """Test that magic methods are excluded."""
        src_file = expander.src_dir / "magic.py"
        src_file.write_text('''
class MyClass:
    def __init__(self):
        pass

    def __str__(self):
        return "MyClass"

    def public_method(self):
        pass
''')

        scopes = expander.analyze_diff(["src/tektos/magic.py"])
        assert "__init__" not in scopes[0].changed_functions
        assert "__str__" not in scopes[0].changed_functions
        assert "public_method" in scopes[0].changed_functions
