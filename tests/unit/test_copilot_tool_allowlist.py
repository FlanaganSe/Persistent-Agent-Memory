"""Tests for Copilot MCP tool allowlist generation."""

from __future__ import annotations

import json

from rkp.projection.adapters.copilot import (
    _READONLY_TOOLS,
    _READWRITE_TOOLS,
    generate_tool_allowlist,
)


class TestToolAllowlist:
    def test_default_allowlist_includes_readonly_tools(self) -> None:
        """Default allowlist includes all read-only tools."""
        allowlist = generate_tool_allowlist()
        rkp_config = allowlist["tools"]["repo-knowledge-plane"]

        for tool in _READONLY_TOOLS:
            assert tool in rkp_config["allow"], f"Missing read-only tool: {tool}"

    def test_refresh_index_explicitly_denied(self) -> None:
        """refresh_index is explicitly denied."""
        allowlist = generate_tool_allowlist()
        rkp_config = allowlist["tools"]["repo-knowledge-plane"]

        assert "refresh_index" in rkp_config["deny"]

    def test_output_is_valid_json(self) -> None:
        """Tool allowlist can be serialized to valid JSON."""
        allowlist = generate_tool_allowlist()
        json_str = json.dumps(allowlist, indent=2)
        parsed = json.loads(json_str)
        assert parsed == allowlist

    def test_no_readwrite_tools_in_allow(self) -> None:
        """No tools with readOnlyHint: false appear in the allow list."""
        allowlist = generate_tool_allowlist()
        allow_list = allowlist["tools"]["repo-knowledge-plane"]["allow"]

        for tool in _READWRITE_TOOLS:
            assert tool not in allow_list, f"Read-write tool in allow list: {tool}"

    def test_structure(self) -> None:
        """Allowlist has correct structure for Copilot MCP config."""
        allowlist = generate_tool_allowlist()

        assert "tools" in allowlist
        assert "repo-knowledge-plane" in allowlist["tools"]
        config = allowlist["tools"]["repo-knowledge-plane"]
        assert "allow" in config
        assert "deny" in config
        assert isinstance(config["allow"], list)
        assert isinstance(config["deny"], list)

    def test_known_tool_list(self) -> None:
        """Verify the known read-only tools match expected set."""
        expected_readonly = {
            "get_conventions",
            "get_module_info",
            "get_prerequisites",
            "get_validated_commands",
            "get_repo_overview",
            "get_preflight_context",
            "get_guardrails",
            "get_conflicts",
            "get_claim",
            "get_instruction_preview",
        }
        assert set(_READONLY_TOOLS) == expected_readonly
        assert set(_READWRITE_TOOLS) == {"refresh_index"}
