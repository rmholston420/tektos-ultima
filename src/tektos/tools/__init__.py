"""Tektos-Ultima v1 — Tool Registry Package

Dynamic tool registry with MCP protocol support.

Replaces hardcoded TOOLS_SCHEMA with:
- ToolRegistry: register/unregister tools at runtime
- MCPClient: discover external tools via Model Context Protocol
- Built-in sandbox tools: bash, file_*, search
"""

from tektos.tools.registry import ToolDefinition, ToolRegistry, MCPClient

__all__ = ["ToolDefinition", "ToolRegistry", "MCPClient"]
