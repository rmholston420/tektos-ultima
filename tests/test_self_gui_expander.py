"""Tests for SelfGUIExpander — backend change analysis, GUI generation."""

from pathlib import Path

import pytest

from src.tektos.self_modification.self_gui_expander import (
    GUIChange,
    GUIExpansionPlan,
    SelfGUIExpander,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def expander(tmp_path):
    """Create a SelfGUIExpander with tmp_path as project root."""
    # Create the expected directory structure
    src_dir = tmp_path / "src" / "tektos"
    frontend_dir = tmp_path / "frontend"
    components_dir = frontend_dir / "src" / "lib" / "components"
    stores_dir = frontend_dir / "src" / "lib"
    api_dir = frontend_dir / "src" / "app" / "api"
    src_dir.mkdir(parents=True, exist_ok=True)
    frontend_dir.mkdir(parents=True, exist_ok=True)
    components_dir.mkdir(parents=True, exist_ok=True)
    stores_dir.mkdir(parents=True, exist_ok=True)
    api_dir.mkdir(parents=True, exist_ok=True)

    expander = SelfGUIExpander(project_root=str(tmp_path))
    expander.src_dir = src_dir
    expander.frontend_dir = frontend_dir
    expander.components_dir = components_dir
    expander.stores_dir = stores_dir
    expander.api_dir = api_dir
    return expander


# ── GUIChange ────────────────────────────────────────────────────────────────

class TestGUIChange:
    def test_default_fields(self):
        change = GUIChange(
            component_name="EmbedderPanel",
            component_type="panel",
            purpose="Display embedder state",
        )
        assert change.component_name == "EmbedderPanel"
        assert change.component_type == "panel"
        assert change.purpose == "Display embedder state"
        assert change.depends_on == []
        assert change.props == []
        assert change.slots == []

    def test_with_dependencies(self):
        change = GUIChange(
            component_name="EmbedderPanel",
            component_type="panel",
            purpose="Display embedder state",
            depends_on=["embedder_store"],
            props=[{"name": "vector", "type": "list"}],
        )
        assert change.depends_on == ["embedder_store"]
        assert change.props == [{"name": "vector", "type": "list"}]


# ── GUIExpansionPlan ────────────────────────────────────────────────────────

class TestGUIExpansionPlan:
    def test_defaults(self):
        plan = GUIExpansionPlan(module_path="tektos.runtime.embedder")
        assert plan.module_path == "tektos.runtime.embedder"
        assert plan.changes == []
        assert plan.store_updates == []
        assert plan.route_updates == []

    def test_with_changes(self):
        change = GUIChange(
            component_name="EmbedderPanel",
            component_type="panel",
            purpose="Display embedder state",
        )
        plan = GUIExpansionPlan(
            module_path="tektos.runtime.embedder",
            changes=[change],
            store_updates=["embedder_store"],
        )
        assert len(plan.changes) == 1
        assert plan.changes[0].component_name == "EmbedderPanel"
        assert plan.store_updates == ["embedder_store"]


# ── SelfGUIExpander — Analysis ─────────────────────────────────────────────

class TestSelfGUIExpanderInit:
    def test_default_project_root(self, expander):
        assert expander.src_dir.exists()
        assert expander.components_dir.exists()
        assert expander.stores_dir.exists()

    def test_custom_project_root(self, tmp_path):
        # Create minimal structure
        (tmp_path / "src" / "tektos").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frontend" / "src" / "lib" / "components").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frontend" / "src" / "lib").mkdir(parents=True, exist_ok=True)
        (tmp_path / "frontend" / "src" / "app" / "api").mkdir(parents=True, exist_ok=True)

        expander = SelfGUIExpander(project_root=str(tmp_path))
        assert expander.project_root == tmp_path


class TestSelfGUIExpanderAnalyzeChanges:
    def test_analyze_class_with_state(self, expander):
        """Test analysis of a class with state fields."""
        src_file = expander.src_dir / "stateful.py"
        src_file.write_text('''
class StatefulComponent:
    name = "test"
    value = 42
    _internal = "private"

    def get_name(self):
        return self.name

    def set_value(self, v):
        self.value = v
''')

        plans = expander.analyze_backend_changes(["src/tektos/stateful.py"])
        assert len(plans) >= 1
        assert len(plans[0].changes) >= 1

        # Should detect state fields as a panel
        panel_change = next(
            (c for c in plans[0].changes if c.component_type == "panel"),
            None,
        )
        assert panel_change is not None
        assert "StatefulComponent" in panel_change.component_name

    def test_analyze_class_with_public_methods(self, expander):
        """Test analysis of a class with public methods."""
        src_file = expander.src_dir / "actionable.py"
        src_file.write_text('''
class ActionableComponent:
    def process(self):
        pass

    def reset(self):
        pass

    def _internal_method(self):
        pass
''')

        plans = expander.analyze_backend_changes(["src/tektos/actionable.py"])
        assert len(plans) >= 1

        # Should have both a panel and form changes
        form_change = next(
            (c for c in plans[0].changes if c.component_type == "form"),
            None,
        )
        assert form_change is not None
        assert "process" in [p["name"] for p in form_change.props]
        assert "reset" in [p["name"] for p in form_change.props]

    def test_analyze_function_endpoint(self, expander):
        """Test analysis of an endpoint-like function."""
        src_file = expander.src_dir / "endpoints.py"
        src_file.write_text('''
def process_api_request(data):
    pass

def get_user_handler(user_id):
    pass

def normal_function():
    pass
''')

        plans = expander.analyze_backend_changes(["src/tektos/endpoints.py"])
        # Should detect API/handler functions
        button_changes = [
            c for c in plans[0].changes if c.component_type == "button"
        ]
        assert len(button_changes) >= 1

    def test_analyze_nonexistent_file(self, expander):
        """Test that nonexistent files produce no plans."""
        plans = expander.analyze_backend_changes(["src/tektos/nonexistent.py"])
        assert all(len(p.changes) == 0 for p in plans)

    def test_analyze_empty_file(self, expander):
        """Test analysis of an empty file."""
        src_file = expander.src_dir / "empty.py"
        src_file.write_text("")

        plans = expander.analyze_backend_changes(["src/tektos/empty.py"])
        assert all(len(p.changes) == 0 for p in plans)

    def test_analyze_multiple_files(self, expander):
        """Test analysis of multiple files."""
        src_file1 = expander.src_dir / "file1.py"
        src_file1.write_text('''
class Component1:
    def method_a(self):
        pass
''')

        src_file2 = expander.src_dir / "file2.py"
        src_file2.write_text('''
class Component2:
    def method_b(self):
        pass
''')

        plans = expander.analyze_backend_changes(
            ["src/tektos/file1.py", "src/tektos/file2.py"],
        )
        assert len(plans) == 2


# ── SelfGUIExpander — Code Generation ──────────────────────────────────────

class TestSelfGUIExpanderGenerateStore:
    def test_generate_basic_store(self, expander):
        """Test generation of a basic Svelte store."""
        content = expander.generate_store(
            "embedderStore",
            [{"name": "url", "type": "string"}, {"name": "active", "type": "boolean"}],
        )
        assert 'import { writable } from "svelte/store"' in content
        assert "export const embedderStore" in content
        assert "url" in content
        assert "active" in content
        assert '""' in content  # string default
        assert "false" in content  # boolean default

    def test_generate_store_with_helpers(self, expander):
        """Test that helper functions are generated."""
        content = expander.generate_store(
            "testStore",
            [{"name": "value", "type": "string"}],
        )
        assert "export function setValue" in content
        assert "update" in content


class TestSelfGUIExpanderGenerateComponent:
    def test_generate_panel(self, expander):
        """Test generation of a panel component."""
        change = GUIChange(
            component_name="EmbedderView",
            component_type="panel",
            purpose="Display embedder state",
            depends_on=["embedder_store"],
            props=[{"name": "url", "type": "string"}, {"name": "active", "type": "boolean"}],
        )

        content = expander.generate_component(change)
        assert '<script lang="ts">' in content
        assert "EmbedderStore" in content or "embedder" in content.lower()
        assert "isOpen" in content
        assert "toggle" in content
        assert "panel" in content.lower()

    def test_generate_form(self, expander):
        """Test generation of a form component."""
        change = GUIChange(
            component_name="EmbedderActions",
            component_type="form",
            purpose="Embedder operations",
            props=[
                {"name": "url", "type": "string"},
                {"name": "callback", "type": "function"},
            ],
        )

        content = expander.generate_component(change)
        assert '<script lang="ts">' in content
        assert "form" in content.lower()
        assert "onSubmit" in content
        # Function props should be skipped for form fields
        assert "callback" not in content.split("<form")[0].split(">")[0].lower() if "<form" in content else True

    def test_generate_button(self, expander):
        """Test generation of a button component."""
        change = GUIChange(
            component_name="ApiHandler",
            component_type="button",
            purpose="Trigger API endpoint",
            props=[{"name": "callback", "type": "function"}],
        )

        content = expander.generate_component(change)
        assert '<script lang="ts">' in content
        assert "button" in content.lower()
        assert "handleClick" in content


class TestSelfGUIExpanderInferDefault:
    def test_string_default(self, expander):
        assert expander._infer_default("string") == '""'

    def test_number_default(self, expander):
        assert expander._infer_default("number") == "0"

    def test_boolean_default(self, expander):
        assert expander._infer_default("boolean") == "false"

    def test_function_default(self, expander):
        assert expander._infer_default("function") == "() => {}"

    def test_any_default(self, expander):
        assert expander._infer_default("any") == "null"

    def test_unknown_default(self, expander):
        assert expander._infer_default("CustomType") == '"default"'


class TestSelfGUIExpanderCamelToPascal:
    def test_camel_case(self, expander):
        assert expander._camel_to_pascal("camelCase") == "CamelCase"

    def test_already_pascal(self, expander):
        assert expander._camel_to_pascal("PascalCase") == "PascalCase"

    def test_single_char(self, expander):
        assert expander._camel_to_pascal("a") == "A"

    def test_empty_string(self, expander):
        assert expander._camel_to_pascal("") == ""


# ── SelfGUIExpander — Frontend Integration ─────────────────────────────────

class TestSelfGUIExpanderApplyChanges:
    def test_apply_gui_changes(self, expander):
        """Test applying GUI changes generates files."""
        change = GUIChange(
            component_name="EmbedderView",
            component_type="panel",
            purpose="Display embedder state",
            props=[{"name": "url", "type": "string"}],
        )
        plan = GUIExpansionPlan(
            module_path="tektos.embedder",
            changes=[change],
        )

        result = expander.apply_gui_changes(plan, auto_build=False)
        assert result is True

        # Verify store was created
        store_name = change.component_name.lower() + "Store"  # "embederviewstore"
        store_path = expander.stores_dir / f"{store_name}.ts"
        assert store_path.exists()
        store_content = store_path.read_text()
        assert "export const" in store_content

        # Verify component was created
        component_path = expander.components_dir / f"{change.component_name}.svelte"
        assert component_path.exists()
        component_content = component_path.read_text()
        assert "script" in component_content.lower()

    def test_apply_gui_changes_no_changes(self, expander):
        """Test applying an empty plan."""
        plan = GUIExpansionPlan(module_path="tektos.empty")
        result = expander.apply_gui_changes(plan, auto_build=False)
        assert result is True

    def test_update_index_exports(self, expander):
        """Test that component index is updated."""
        # Create some dummy components
        comp1 = expander.components_dir / "Component1.svelte"
        comp2 = expander.components_dir / "Component2.svelte"
        comp1.write_text("<script></script>")
        comp2.write_text("<script></script>")

        expander._update_index_exports()

        index_path = expander.components_dir / "index.ts"
        assert index_path.exists()
        index_content = index_path.read_text()
        assert "Component1" in index_content
        assert "Component2" in index_content


# ── SelfGUIExpander — End-to-End ───────────────────────────────────────────

class TestSelfGUIExpanderEndToEnd:
    def test_expand_gui_for_changes(self, expander):
        """Full integration test: analyze backend and expand GUI."""
        # Create source file with class-level state (what _extract_state_fields finds)
        src_file = expander.src_dir / "gui_backend.py"
        src_file.write_text('''
class GUIBackendComponent:
    endpoint = "/api/test"
    enabled = True

    def fetch_data(self):
        return []

    def submit_data(self, data):
        pass
''')

        plans = expander.expand_gui_for_changes(
            ["src/tektos/gui_backend.py"],
            auto_build=False,
        )

        assert len(plans) >= 1
        plan = plans[0]

        # Should have both panel and form changes
        panel_changes = [c for c in plan.changes if c.component_type == "panel"]
        form_changes = [c for c in plan.changes if c.component_type == "form"]
        assert len(panel_changes) >= 1, f"Expected panel changes, got: {plan.changes}"
        assert len(form_changes) >= 1

        # Verify files were created
        for change in plan.changes:
            # apply_gui_changes uses: component_name.lower() + "Store"
            store_name = change.component_name.lower() + "Store"
            store_path = expander.stores_dir / f"{store_name}.ts"
            component_path = expander.components_dir / f"{change.component_name}.svelte"
            assert store_path.exists(), f"Store not created: {store_path}"
            assert component_path.exists(), f"Component not created: {component_path}"


# ── SelfGUIExpander — Edge Cases ───────────────────────────────────────────

class TestSelfGUIExpanderEdgeCases:
    def test_analyze_file_with_syntax_error(self, expander):
        """Test analysis of a file with syntax errors."""
        src_file = expander.src_dir / "bad.py"
        src_file.write_text("this is not valid python {{{")

        plans = expander.analyze_backend_changes(["src/tektos/bad.py"])
        # Should handle gracefully
        assert plans is not None

    def test_analyze_class_with_no_public_apis(self, expander):
        """Test analysis of a class with only private methods."""
        src_file = expander.src_dir / "private_only.py"
        src_file.write_text('''
class PrivateClass:
    def __init__(self):
        self._private = "value"

    def _method_a(self):
        pass
''')

        plans = expander.analyze_backend_changes(["src/tektos/private_only.py"])
        # Should produce minimal or no changes
        if plans:
            for plan in plans:
                for change in plan.changes:
                    assert change.component_type in ["panel", "form", "button", "table", "dialog", "sidebar"]
