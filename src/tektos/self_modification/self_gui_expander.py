"""SelfGUIExpander — Tektos adds GUI elements when it modifies itself.

When Tektos changes backend logic (new state, new endpoints, new tools),
this module:
1. Analyzes the changed module for new public APIs, state fields, endpoints
2. Determines what GUI components are needed
3. Generates Svelte components, stores, and route handlers
4. Updates the frontend to integrate the new elements
5. Validates the frontend builds successfully

Integration: Called from SelfImprovementAdapter after a code-modification task
that touches backend logic, state management, or API endpoints.
"""

from __future__ import annotations

import ast
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("tektos.self_modification")


@dataclass
class GUIChange:
    """A GUI change needed due to backend modifications."""
    component_name: str  # e.g. "SessionEmbedderPanel"
    component_type: str  # "panel" | "sidebar" | "dialog" | "table" | "form" | "button"
    purpose: str  # what this component does
    depends_on: list[str] = field(default_factory=list)  # store/endpoint dependencies
    props: list[dict[str, str]] = field(default_factory=list)  # {name: type}
    slots: list[str] = field(default_factory=list)  # named slots


@dataclass
class GUIExpansionPlan:
    """Plan for GUI expansion."""
    module_path: str
    changes: list[GUIChange] = field(default_factory=list)
    store_updates: list[str] = field(default_factory=list)  # stores to update
    route_updates: list[str] = field(default_factory=list)  # routes to add/update


class SelfGUIExpander:
    """Analyzes backend changes and generates/updates GUI components."""

    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else Path(__file__).resolve().parent.parent.parent
        self.src_dir = self.project_root / "src" / "tektos"
        self.frontend_dir = self.project_root / "frontend"
        self.components_dir = self.frontend_dir / "src" / "lib" / "components"
        self.stores_dir = self.frontend_dir / "src" / "lib"
        self.api_dir = self.frontend_dir / "src" / "app" / "api"

        # Ensure directories exist
        for d in [self.components_dir, self.stores_dir, self.api_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def analyze_backend_changes(
        self,
        changed_files: list[str],
    ) -> list[GUIExpansionPlan]:
        """Analyze changed backend files for GUI implications.

        Args:
            changed_files: List of changed file paths (relative to project root).

        Returns:
            List of GUIExpansionPlan objects describing GUI changes needed.
        """
        plans: list[GUIExpansionPlan] = []

        for file_path in changed_files:
            abs_path = Path(file_path) if Path(file_path).is_absolute() else self.project_root / file_path
            if not abs_path.exists():
                continue

            # Convert to module path
            try:
                rel = abs_path.relative_to(self.src_dir)
                module_path = ".".join(rel.with_suffix("").parts)
            except ValueError:
                continue

            plan = self._analyze_module(module_path, str(abs_path))
            if plan.changes:
                plans.append(plan)

        return plans

    def _analyze_module(self, module_path: str, file_path: str) -> GUIExpansionPlan:
        """Analyze a single Python module for GUI implications."""
        plan = GUIExpansionPlan(module_path=module_path)

        try:
            source = Path(file_path).read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception as exc:
            logger.warning("Failed to parse %s: %s", file_path, exc)
            return plan

        # Analyze classes for state fields and APIs
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                plan.changes.extend(self._analyze_class(node))

            # Check for new endpoint-like functions
            if isinstance(node, ast.FunctionDef):
                plan.changes.extend(self._analyze_function(node))

        return plan

    def _analyze_class(self, node: ast.ClassDef) -> list[GUIChange]:
        """Analyze a class for GUI component requirements."""
        changes: list[GUIChange] = []

        # Get class name and determine component type
        class_name = node.name
        # Convert PascalCase to SentenceCase for component names
        component_name = self._camel_to_pascal(class_name) + "View"

        # Check for state fields
        state_fields = self._extract_state_fields(node)
        if state_fields:
            changes.append(GUIChange(
                component_name=component_name,
                component_type="panel",
                purpose=f"Display and manage {class_name} state",
                props=[{"name": f"field_{i}", "type": "string"} for i in range(len(state_fields))],
                depends_on=[f"{class_name.lower()}_store"],
            ))

        # Check for public methods that might be actions
        public_methods = self._extract_public_methods(node)
        if public_methods:
            changes.append(GUIChange(
                component_name=component_name + "Actions",
                component_type="form",
                purpose=f"Provide controls for {class_name} operations",
                depends_on=[f"{class_name.lower()}_store"],
                props=[{"name": method, "type": "function"} for method in public_methods],
            ))

        return changes

    def _analyze_function(self, node: ast.FunctionDef) -> list[GUIChange]:
        """Analyze a function for GUI component requirements."""
        changes: list[GUIChange] = []

        # Check for endpoint-like patterns
        if any(pattern in node.name.lower() for pattern in ["api", "endpoint", "route", "handler"]):
            component_name = self._camel_to_pascal(node.name) + "Handler"
            changes.append(GUIChange(
                component_name=component_name,
                component_type="button",
                purpose=f"Trigger {node.name} API endpoint",
                props=[{"name": "callback", "type": "function"}],
            ))

        return changes

    def _extract_state_fields(self, node: ast.ClassDef) -> list[str]:
        """Extract state-like field names from a class."""
        fields: list[str] = []
        for item in ast.walk(node):
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                fields.append(item.target.id)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and not target.id.startswith("_"):
                        fields.append(target.id)
        return fields

    def _extract_public_methods(self, node: ast.ClassDef) -> list[str]:
        """Extract public method names from a class."""
        methods: list[str] = []
        for item in ast.walk(node):
            if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                methods.append(item.name)
        return methods

    # ── Code Generation ─────────────────────────────────────────────────

    def generate_store(self, store_name: str, fields: list[dict[str, str]]) -> str:
        """Generate a Svelte store for a module's state."""
        lines = [
            'import { writable } from "svelte/store";',
            "",
            f"// Store for {store_name}",
            f"export const {store_name} = writable({{",
        ]

        for field in fields:
            field_name = field["name"]
            default_value = self._infer_default(field["type"])
            lines.append(f'  {field_name}: {default_value},')

        lines.append("});")
        lines.append("")

        # Add helper functions
        for field in fields:
            lines.extend([
                f"export function set{self._camel_to_pascal(field['name'])}(value: {field['type']}): void {{",
                f'  {store_name}.update(state => ({{ ...state, {field["name"]}: value }}));',
                "}",
                "",
            ])

        return "\n".join(lines) + "\n"

    def generate_component(self, change: GUIChange) -> str:
        """Generate a Svelte component from a GUIChange."""
        component_type = change.component_type

        if component_type == "panel":
            return self._generate_panel(change)
        elif component_type == "form":
            return self._generate_form(change)
        elif component_type == "button":
            return self._generate_button(change)
        else:
            return self._generate_generic(change)

    def _generate_panel(self, change: GUIChange) -> str:
        """Generate a panel component."""
        props_section = ""
        if change.props:
            props_section = "\n".join([
                f'  {name}: {type_};' for name, type_ in [(p["name"], p["type"]) for p in change.props]
            ])

        store_import = ""
        if change.depends_on:
            store_base = change.depends_on[0].split('.')[-1]
            store_path = change.depends_on[0].replace('.', '/')
            store_import = f'  import {{ {store_base} }} from "$lib/{store_path}"'

        panel_label = change.component_name.replace('View', 'Panel').lower()

        lines = [
            '<script lang="ts">',
            props_section,
            "",
            store_import,
            "",
            "  let isOpen = $state(false);",
            "",
            "  function toggle(): void {",
            "    isOpen = !isOpen;",
            "  }",
            "</script>",
            "",
            f'<div class="panel">',
            '  <div class="panel-header">',
            '    <h3>' + change.purpose + '</h3>',
            "    <button on:click={toggle}>{ isOpen ? 'Collapse' : 'Expand' }</button>",
            "  </div>",
            "",
            '  <div class="panel-content">',
            self._generate_panel_content(change),
            "  </div>",
            "</div>",
        ]

        return "\n".join([l for l in lines if l]) + "\n"

    def _generate_panel_content(self, change: GUIChange) -> str:
        """Generate content for a panel."""
        content = []
        for prop in change.props:
            name = prop["name"]
            content.append('<div class="panel-field">')
            content.append('  <label>{"' + name + ':"} </label>')
            content.append('  <span>{state.' + name + '}</span>')
            content.append('</div>')
        return "\n".join(content)

    def _generate_form(self, change: GUIChange) -> str:
        """Generate a form component."""
        lines = [
            '<script lang="ts">',
            "  " + ", ".join(
                f'let {p["name"]} = {self._infer_default(p["type"])}'
                for p in change.props if p["type"] != "function"
            ),
            "",
            "  function onSubmit(): void {",
            "    // TODO: implement form submission",
            "  }",
            "</script>",
            "",
            '<form class="form" on:submit|preventDefault={onSubmit}>',
        ]

        for prop in change.props:
            if prop["type"] == "function":
                continue
            name = prop["name"]
            lines.extend([
                '  <div class="form-group">',
                '    <label for="' + name + '">' + name + '</label>',
                '    <input type="text" id="' + name + '" bind:value=' + name + ' />',
                '  </div>',
            ])

        lines.extend([
            '  <button type="submit">Submit</button>',
            "</form>",
        ])

        return "\n".join(lines) + "\n"

    def _generate_button(self, change: GUIChange) -> str:
        """Generate a button component."""
        prop_name = change.props[0]["name"] if change.props else "callback"
        lines = [
            '<script lang="ts">',
            '  let ' + prop_name + ' = () => {};',
            "",
            "  function handleClick(): void {",
            "    " + prop_name + "();",
            "  }",
            "</script>",
            "",
            '<button on:click={handleClick}>',
            "  " + change.purpose,
            "</button>",
        ]
        return "\n".join(lines) + "\n"

    def _generate_generic(self, change: GUIChange) -> str:
        """Generate a generic component."""
        return f"""<script lang="ts">
  // Generic component for {change.purpose}
</script>

<div class="component">
  {change.purpose}
</div>
"""

    def _infer_default(self, type_: str) -> str:
        """Infer a default value for a TypeScript type."""
        defaults = {
            "string": '""',
            "number": "0",
            "boolean": "false",
            "function": "() => {}",
            "any": "null",
        }
        return defaults.get(type_, '"default"')

    def _camel_to_pascal(self, name: str) -> str:
        """Convert camelCase to PascalCase."""
        return name[0].upper() + name[1:] if name else ""

    # ── Frontend Integration ────────────────────────────────────────────

    def apply_gui_changes(self, plan: GUIExpansionPlan, auto_build: bool = True) -> bool:
        """Apply GUI changes and optionally build the frontend.

        Args:
            plan: GUIExpansionPlan describing the changes.
            auto_build: Whether to run a frontend build after applying changes.

        Returns:
            True if changes were applied successfully.
        """
        for change in plan.changes:
            # Generate store
            store_name = change.component_name.lower() + "Store"
            store_content = self.generate_store(
                store_name,
                change.props if change.props else [{"name": "state", "type": "any"}],
            )
            store_path = self.stores_dir / f"{store_name}.ts"
            store_path.write_text(store_content, encoding="utf-8")
            logger.info("Generated store: %s", store_path)

            # Generate component
            component_content = self.generate_component(change)
            component_path = self.components_dir / f"{change.component_name}.svelte"
            component_path.write_text(component_content, encoding="utf-8")
            logger.info("Generated component: %s", component_path)

            # Update index exports if needed
            self._update_index_exports()

        if auto_build:
            return self._build_frontend()

        return True

    def _update_index_exports(self) -> None:
        """Update the components index to export new components."""
        index_path = self.components_dir / "index.ts"
        components = [
            p.stem for p in self.components_dir.glob("*.svelte")
            if p.name != "index.ts"
        ]

        content = "\n".join([f'export * from "./{c}";' for c in components]) + "\n"
        index_path.write_text(content, encoding="utf-8")
        logger.info("Updated component exports: %s", index_path)

    def _build_frontend(self) -> bool:
        """Build the frontend and return whether it succeeded."""
        try:
            result = subprocess.run(
                ["npm", "run", "build"],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=str(self.frontend_dir),
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.error("Frontend build timed out")
            return False
        except Exception as exc:
            logger.error("Frontend build failed: %s", exc)
            return False

    # ── High-Level API ──────────────────────────────────────────────────

    def expand_gui_for_changes(
        self,
        changed_files: list[str],
        auto_build: bool = True,
    ) -> list[GUIExpansionPlan]:
        """Main entry point: analyze backend changes and expand GUI.

        Args:
            changed_files: List of changed file paths (relative to project root).
            auto_build: Whether to build the frontend after generating components.

        Returns:
            List of GUIExpansionPlan objects describing GUI changes.
        """
        plans = self.analyze_backend_changes(changed_files)

        for plan in plans:
            self.apply_gui_changes(plan, auto_build=auto_build)

        return plans
