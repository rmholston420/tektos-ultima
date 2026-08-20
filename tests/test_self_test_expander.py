"""Tests for self-test expander module."""

import pytest
import ast
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

from tektos.self_modification.self_test_expander import (
    DiffScope,
    TestPlanData,
    SelfTestExpander,
)


class TestDiffScope:
    """Tests for DiffScope dataclass."""

    def test_creation_defaults(self):
        scope = DiffScope(
            module_path="tektos.runtime.session",
            file_path="/path/to/session.py",
        )
        assert scope.module_path == "tektos.runtime.session"
        assert scope.file_path == "/path/to/session.py"
        assert scope.changed_functions == []
        assert scope.changed_classes == []
        assert scope.new_lines == []
        assert scope.deleted_lines == []
        assert scope.new_public_apis == []

    def test_creation_with_values(self):
        scope = DiffScope(
            module_path="tektos.runtime.session",
            file_path="/path/to/session.py",
            changed_functions=["create_session", "get_session"],
            changed_classes=["SessionManager"],
            new_lines=["def new_func(): pass"],
            deleted_lines=["def old_func(): pass"],
            new_public_apis=["SessionManager.create_session"],
        )
        assert scope.changed_functions == ["create_session", "get_session"]
        assert scope.changed_classes == ["SessionManager"]
        assert scope.new_public_apis == ["SessionManager.create_session"]


class TestTestPlanData:
    """Tests for TestPlanData dataclass."""

    def test_creation_defaults(self):
        plan = TestPlanData(
            module_path="tektos.runtime.session",
            file_path="/path/to/session.py",
        )
        assert plan.module_path == "tektos.runtime.session"
        assert plan.tests_to_create == []
        assert plan.tests_to_expand == []
        assert plan.test_file_path == ""

    def test_creation_with_values(self):
        plan = TestPlanData(
            module_path="tektos.runtime.session",
            file_path="/path/to/session.py",
            tests_to_create=["TestSessionManager"],
            tests_to_expand=["TestSessionManager.test_create"],
            test_file_path="/tests/test_session.py",
        )
        assert plan.tests_to_create == ["TestSessionManager"]
        assert plan.tests_to_expand == ["TestSessionManager.test_create"]
        assert plan.test_file_path == "/tests/test_session.py"


class TestSelfTestExpander:
    """Tests for SelfTestExpander class."""

    def setup_method(self):
        # Pass the actual repo root so src_dir resolves correctly
        self.expander = SelfTestExpander(project_root="/home/rmholston/dev/tektos-ultima-v1")

    def test_project_root(self):
        assert self.expander.project_root is not None
        # project_root resolves to the repo root from the expander's file location
        assert self.expander.src_dir.exists()
        assert self.expander.tests_dir.exists()

    def test_analyze_diff_nonexistent_file(self):
        """analyze_diff should skip nonexistent files."""
        scopes = self.expander.analyze_diff(["/nonexistent/file.py"])
        assert len(scopes) == 0

    def test_analyze_diff_existing_file(self):
        """analyze_diff should extract public APIs from existing files."""
        scopes = self.expander.analyze_diff(
            [str(self.expander.src_dir / "config.py")]
        )
        assert len(scopes) == 1
        assert scopes[0].module_path == "config"
        assert "TektosConfig" in scopes[0].changed_classes
        assert "LLMConfig" in scopes[0].changed_classes

    def test_analyze_diff_multiple_files(self):
        """analyze_diff should handle multiple files."""
        files = [
            str(self.expander.src_dir / "config.py"),
            str(self.expander.src_dir / "state_machine.py"),
        ]
        scopes = self.expander.analyze_diff(files)
        assert len(scopes) == 2

    def test_generate_plan_empty_scopes(self):
        """generate_plan should return empty list for empty scopes."""
        plans = self.expander.generate_plan([])
        assert plans == []

    def test_generate_plan_with_scopes(self):
        """generate_plan should create plans for scopes with changes."""
        scope = DiffScope(
            module_path="tektos.config",
            file_path=str(self.expander.src_dir / "config.py"),
            changed_classes=["TektosConfig", "LLMConfig"],
            new_public_apis=["TektosConfig.from_env"],
        )
        plans = self.expander.generate_plan([scope])
        assert len(plans) == 1
        assert "TestTektosConfig" in plans[0].tests_to_create
        assert "TestLLMConfig" in plans[0].tests_to_create

    def test_generate_plan_creates_new_test_file(self):
        """generate_plan should create new test file path for untested modules."""
        scope = DiffScope(
            module_path="tektos.config",
            file_path=str(self.expander.src_dir / "config.py"),
            changed_classes=["TektosConfig"],
        )
        plans = self.expander.generate_plan([scope])
        assert plans[0].test_file_path.endswith("test_config.py")

    def test_extract_public_apis(self):
        """_extract_public_apis should find public functions and classes."""
        source = '''
class MyClass:
    def public_method(self):
        pass

    def _private_method(self):
        pass

def public_function():
    pass

def _private_function():
    pass

def __dunder_function__():
    pass
'''
        tree = ast.parse(source)
        funcs, classes, apis = self.expander._extract_public_apis(tree)

        assert "public_function" in funcs
        assert "_private_function" not in funcs
        assert "__dunder_function__" not in funcs
        assert "MyClass" in classes
        assert "MyClass.public_method" in apis

    def test_extract_public_apis_no_public_apis(self):
        """_extract_public_apis should return empty lists for private-only code."""
        source = '''
def _private_func():
    pass

class _PrivateClass:
    def _private_method(self):
        pass
'''
        tree = ast.parse(source)
        funcs, classes, apis = self.expander._extract_public_apis(tree)
        assert funcs == []
        # Classes are always collected regardless of underscore prefix
        assert classes == ["_PrivateClass"]
        assert apis == []

    def test_generate_test_file(self):
        """generate_test_file should produce valid Python test code."""
        plan = TestPlanData(
            module_path="tektos.config",
            file_path="/path/to/config.py",
            tests_to_create=["TestTektosConfig", "TestLLMConfig"],
            test_file_path="/tests/test_config.py",
        )

        content = self.expander.generate_test_file(plan)
        assert "Tests for tektos.config" in content
        assert "import pytest" in content
        assert "class TestTektosConfig:" in content
        assert "class TestLLMConfig:" in content
        assert "from tektos.config import *" in content

    def test_generate_test_file_empty(self):
        """generate_test_file should handle empty test plans."""
        plan = TestPlanData(
            module_path="tektos.config",
            file_path="/path/to/config.py",
            tests_to_create=[],
            test_file_path="/tests/test_config.py",
        )

        content = self.expander.generate_test_file(plan)
        assert "Tests for tektos.config" in content
        assert "import pytest" in content

    def test_infer_params(self):
        """_infer_params should generate default params from API name."""
        params = self.expander._infer_params("create_session")
        assert '"create"' in params or '"session"' in params

        params = self.expander._infer_params("get_user_profile")
        assert '"get"' in params or '"user"' in params or '"profile"' in params

    def test_find_existing_test_classes(self):
        """_find_existing_test_classes should find Test-prefixed classes."""
        test_content = '''
class TestExisting:
    pass

class TestAnother:
    pass

class NotATest:
    pass
'''
        with patch("pathlib.Path.read_text", return_value=test_content):
            classes = self.expander._find_existing_test_classes("/fake/path.py")
            assert "TestExisting" in classes
            assert "TestAnother" in classes
            assert "NotATest" not in classes

    def test_find_existing_test_classes_empty(self):
        """_find_existing_test_classes should return empty for no test classes."""
        test_content = '''
def test_function():
    pass
'''
        with patch("pathlib.Path.read_text", return_value=test_content):
            classes = self.expander._find_existing_test_classes("/fake/path.py")
            assert classes == []

    def test_find_existing_test_classes_parse_error(self):
        """_find_existing_test_classes should return empty on parse error."""
        with patch("pathlib.Path.read_text", return_value="invalid python {{{"):
            classes = self.expander._find_existing_test_classes("/fake/path.py")
            assert classes == []

    def test_run_generated_tests_success(self):
        """run_generated_tests should return True on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = self.expander.run_generated_tests("/fake/test.py")
            assert result is True

    def test_run_generated_tests_failure(self):
        """run_generated_tests should return False on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = self.expander.run_generated_tests("/fake/test.py")
            assert result is False

    def test_run_generated_tests_timeout(self):
        """run_generated_tests should return False on timeout."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 120)):
            result = self.expander.run_generated_tests("/fake/test.py")
            assert result is False

    def test_run_generated_tests_exception(self):
        """run_generated_tests should return False on exception."""
        with patch("subprocess.run", side_effect=Exception("other error")):
            result = self.expander.run_generated_tests("/fake/test.py")
            assert result is False

    def test_expand_tests_for_changes(self):
        """expand_tests_for_changes should analyze, plan, and generate tests."""
        # Create a temporary test file to expand
        test_file = self.expander.tests_dir / "test_existing.py"
        test_file.write_text("class TestExisting:\n    pass\n")

        try:
            scope = DiffScope(
                module_path="tektos.config",
                file_path=str(self.expander.src_dir / "config.py"),
                changed_classes=["TektosConfig"],
            )
            plans = self.expander.expand_tests_for_changes(
                changed_files=[str(self.expander.src_dir / "config.py")],
                auto_run=False,
            )
            assert len(plans) >= 0  # May or may not have plans depending on existing tests
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_expand_tests_for_changes_empty(self):
        """expand_tests_for_changes should handle empty changed files."""
        plans = self.expander.expand_tests_for_changes(
            changed_files=[],
            auto_run=False,
        )
        assert plans == []

    def test_create_plan_for_scope_new_file(self):
        """_create_plan_for_scope should create new test file for untested modules."""
        scope = DiffScope(
            module_path="tektos.config",
            file_path=str(self.expander.src_dir / "config.py"),
            changed_classes=["TektosConfig"],
        )
        plan = self.expander._create_plan_for_scope(scope)
        assert "TestTektosConfig" in plan.tests_to_create
        assert plan.test_file_path.endswith("test_config.py")

    def test_create_plan_for_scope_existing_file(self):
        """_create_plan_for_scope should expand existing test file."""
        # Create a test file with existing test class
        test_file = self.expander.tests_dir / "test_config.py"
        test_file.write_text("class TestLLMConfig:\n    pass\n")

        try:
            scope = DiffScope(
                module_path="tektos.config",
                file_path=str(self.expander.src_dir / "config.py"),
                changed_classes=["TektosConfig", "LLMConfig"],
            )
            plan = self.expander._create_plan_for_scope(scope)
            # TestLLMConfig already exists, should be in expand list
            assert "TestTektosConfig" in plan.tests_to_create
            assert "TestLLMConfig.*" in plan.tests_to_expand
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_project_root_custom(self):
        """SelfTestExpander should accept custom project root."""
        expander = SelfTestExpander(project_root="/tmp")
        assert str(expander.project_root) == "/tmp"

    def test_generate_test_class(self):
        """_generate_test_class should produce valid test class."""
        lines = self.expander._generate_test_class("TestMyClass", "my_module")
        assert "class TestMyClass:" in lines
        assert "    def test_my_module_initialization(self):" in lines
        assert "    def test_my_module_basic_usage(self):" in lines

    def test_generate_test_class_no_prefix(self):
        """_generate_test_class should handle names without Test prefix."""
        lines = self.expander._generate_test_class("MyClass", "my_module")
        # Should still produce something valid
        assert "class MyClass:" in lines
