"""MCP security testing utilities.

Provides automated security tests for MCP servers including prompt injection
detection, capability escalation checks, resource exhaustion testing, and
schema drift analysis.
"""

from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentest.mcp_testing.server_tester import MCPServerTester


class SecurityTestResult(BaseModel):
    """Result of an MCP security test."""

    test_name: str
    category: str = Field(
        ...,
        pattern=r"^(prompt_injection|capability_escalation|resource_exhaustion|schema_drift)$",
    )
    passed: bool
    severity: str = Field(..., pattern=r"^(info|warning|critical)$")
    details: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[str] = Field(default_factory=list)


# Patterns that suggest prompt injection in tool responses.
_INJECTION_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)ignore\s+(all\s+)?previous", "instruction override attempt"),
    (r"(?i)system\s*:", "system prompt injection"),
    (r"(?i)you\s+are\b", "persona injection"),
    (r"(?i)assistant\s*:", "role injection"),
    (r"(?i)forget\s+(all\s+)?(your\s+)?instructions", "instruction override attempt"),
    (r"(?i)<\s*script\b", "HTML script injection"),
    (r"(?i)<\s*iframe\b", "HTML iframe injection"),
    (r"(?i)<\s*img\b[^>]+onerror", "HTML event handler injection"),
    (r"\[.*?\]\(javascript:", "markdown javascript injection"),
]

_COMPILED_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(pat), desc) for pat, desc in _INJECTION_PATTERNS
]


def _extract_response_text(response: dict[str, Any] | None) -> str:
    """Extract all text content from an MCP tool call response."""
    if response is None:
        return ""
    result = response.get("result", {})
    if not isinstance(result, dict):
        return str(result)
    content = result.get("content", [])
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict):
            text = item.get("text", "")
            if text:
                parts.append(str(text))
    return "\n".join(parts)


def _looks_like_base64_instruction(text: str) -> str | None:
    """Check if any base64-encoded segment decodes to instruction-like text."""
    b64_pattern = re.compile(r"[A-Za-z0-9+/]{20,}={0,2}")
    for match in b64_pattern.finditer(text):
        candidate = match.group()
        try:
            decoded = base64.b64decode(candidate).decode("utf-8", errors="ignore")
        except Exception:
            continue
        for pattern, _desc in _INJECTION_PATTERNS:
            if re.search(pattern, decoded):
                return decoded
    return None


def _extract_tool_schemas(tools: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a mapping of tool name to its schema definition."""
    schemas: dict[str, Any] = {}
    for tool in tools:
        name = tool.get("name", "")
        schemas[name] = {
            "description": tool.get("description", ""),
            "inputSchema": tool.get("inputSchema", {}),
        }
    return schemas


class MCPSecurityTester:
    """Run security-focused tests against an MCP server.

    Wraps :class:`MCPServerTester` with additional checks for prompt injection,
    capability escalation, resource exhaustion, and schema drift.

    Usage::

        with MCPSecurityTester(command=["python", "-m", "my_server"]) as sec:
            results = sec.run_all()
            for r in results:
                print(r.test_name, r.passed, r.severity)
    """

    def __init__(self, command: list[str], timeout: float = 30.0) -> None:
        self._tester = MCPServerTester(command=command, timeout_seconds=timeout)

    # -- context manager --------------------------------------------------

    def __enter__(self) -> MCPSecurityTester:
        self._tester.start()
        self._tester.test_initialize()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._tester.close()

    # -- helpers ----------------------------------------------------------

    def _list_tools(self) -> list[dict[str, Any]]:
        """Return the list of tool definitions from the server."""
        result = self._tester.test_list_tools()
        if not result.passed or result.response is None:
            return []
        return result.response.get("result", {}).get("tools", [])

    # -- prompt injection -------------------------------------------------

    def test_prompt_injection(self) -> list[SecurityTestResult]:
        """Call each tool with default args and scan responses for injection patterns.

        Checks for:
        - Instruction-like text (e.g. "ignore previous", "system:", "you are")
        - Base64-encoded instructions hidden in responses
        - Markdown / HTML injection payloads
        """
        results: list[SecurityTestResult] = []
        tools = self._list_tools()

        for tool in tools:
            name = tool.get("name", "unknown")
            args = MCPServerTester._generate_default_args(tool)
            call_result = self._tester.test_tool_call(tool_name=name, arguments=args)
            text = _extract_response_text(call_result.response)

            findings: list[str] = []

            # Regex pattern scan
            for pattern, description in _COMPILED_INJECTION_PATTERNS:
                if pattern.search(text):
                    findings.append(description)

            # Base64 hidden instructions
            b64_decoded = _looks_like_base64_instruction(text)
            if b64_decoded is not None:
                findings.append(f"base64-encoded instruction: {b64_decoded!r}")

            passed = len(findings) == 0
            severity = "critical" if not passed else "info"

            recommendations: list[str] = []
            if not passed:
                recommendations.append(
                    "Sanitize tool output to remove instruction-like text before "
                    "returning it to the model."
                )
                recommendations.append("Avoid echoing untrusted user content in tool responses.")

            results.append(
                SecurityTestResult(
                    test_name=f"prompt_injection:{name}",
                    category="prompt_injection",
                    passed=passed,
                    severity=severity,
                    details={
                        "tool": name,
                        "findings": findings,
                        "response_length": len(text),
                    },
                    recommendations=recommendations,
                )
            )

        return results

    # -- capability escalation --------------------------------------------

    def test_capability_escalation(self) -> list[SecurityTestResult]:
        """Check whether calling a tool causes new tools to be registered.

        Records the initial tools/list, calls each tool, and re-checks for
        any newly appeared tool registrations.
        """
        results: list[SecurityTestResult] = []
        initial_tools = self._list_tools()
        initial_names = {t.get("name") for t in initial_tools}

        for tool in initial_tools:
            name = tool.get("name", "unknown")
            args = MCPServerTester._generate_default_args(tool)
            self._tester.test_tool_call(tool_name=name, arguments=args)

            # Re-check tool list after the call
            post_tools = self._list_tools()
            post_names = {t.get("name") for t in post_tools}
            new_tools = post_names - initial_names

            passed = len(new_tools) == 0
            severity = "critical" if not passed else "info"

            recommendations: list[str] = []
            if not passed:
                recommendations.append(
                    "Tool calls should not dynamically register new tools. "
                    "Review server-side logic for unexpected capability changes."
                )

            results.append(
                SecurityTestResult(
                    test_name=f"capability_escalation:{name}",
                    category="capability_escalation",
                    passed=passed,
                    severity=severity,
                    details={
                        "tool": name,
                        "initial_tool_count": len(initial_names),
                        "post_call_tool_count": len(post_names),
                        "new_tools": sorted(new_tools),
                    },
                    recommendations=recommendations,
                )
            )

        return results

    # -- resource exhaustion ----------------------------------------------

    def test_resource_exhaustion(self) -> list[SecurityTestResult]:
        """Test for unreasonable response sizes and timeout behaviour.

        For each tool:
        - Calls the tool with default args and measures response size.
        - Flags responses exceeding 1 MB as a warning.
        - Flags responses exceeding 10 MB as critical.
        - Checks that responses arrive within the configured timeout.
        """
        results: list[SecurityTestResult] = []
        tools = self._list_tools()

        size_warning = 1_000_000  # 1 MB
        size_critical = 10_000_000  # 10 MB

        for tool in tools:
            name = tool.get("name", "unknown")
            args = MCPServerTester._generate_default_args(tool)

            start = time.time()
            call_result = self._tester.test_tool_call(tool_name=name, arguments=args)
            elapsed_ms = (time.time() - start) * 1000

            response_text = _extract_response_text(call_result.response)
            response_size = len(response_text.encode("utf-8"))

            timed_out = call_result.error is not None and "Timeout" in (call_result.error or "")

            if timed_out:
                severity = "critical"
                passed = False
            elif response_size > size_critical:
                severity = "critical"
                passed = False
            elif response_size > size_warning:
                severity = "warning"
                passed = False
            else:
                severity = "info"
                passed = True

            recommendations: list[str] = []
            if timed_out:
                recommendations.append(
                    "Tool exceeded timeout. Implement server-side time limits "
                    "or pagination for long-running operations."
                )
            if response_size > size_warning:
                recommendations.append(
                    "Response is very large. Consider pagination or streaming "
                    "to avoid memory issues in the host application."
                )

            results.append(
                SecurityTestResult(
                    test_name=f"resource_exhaustion:{name}",
                    category="resource_exhaustion",
                    passed=passed,
                    severity=severity,
                    details={
                        "tool": name,
                        "response_size_bytes": response_size,
                        "elapsed_ms": round(elapsed_ms, 1),
                        "timed_out": timed_out,
                    },
                    recommendations=recommendations,
                )
            )

        return results

    # -- schema drift -----------------------------------------------------

    def test_schema_drift(self, baseline_path: Path | None = None) -> list[SecurityTestResult]:
        """Compare current tool schemas against a saved baseline.

        If *baseline_path* is ``None`` or the file does not exist the test
        is skipped with an informational result advising to save a baseline first.

        Detects:
        - Tools that were added or removed since the baseline
        - Changed parameter types within ``inputSchema.properties``
        - Required fields that were removed
        """
        results: list[SecurityTestResult] = []

        if baseline_path is None or not baseline_path.exists():
            results.append(
                SecurityTestResult(
                    test_name="schema_drift:no_baseline",
                    category="schema_drift",
                    passed=True,
                    severity="info",
                    details={"reason": "No baseline file provided or file not found."},
                    recommendations=[
                        "Save a baseline with save_baseline() to enable schema drift detection."
                    ],
                )
            )
            return results

        with open(baseline_path) as f:
            baseline_schemas: dict[str, Any] = json.load(f)

        current_tools = self._list_tools()
        current_schemas = _extract_tool_schemas(current_tools)

        baseline_names = set(baseline_schemas.keys())
        current_names = set(current_schemas.keys())

        added_tools = sorted(current_names - baseline_names)
        removed_tools = sorted(baseline_names - current_names)

        # Added tools
        if added_tools:
            results.append(
                SecurityTestResult(
                    test_name="schema_drift:added_tools",
                    category="schema_drift",
                    passed=False,
                    severity="warning",
                    details={"added_tools": added_tools},
                    recommendations=[
                        "New tools appeared since the baseline was saved. "
                        "Verify these additions are intentional and update the baseline."
                    ],
                )
            )

        # Removed tools
        if removed_tools:
            results.append(
                SecurityTestResult(
                    test_name="schema_drift:removed_tools",
                    category="schema_drift",
                    passed=False,
                    severity="warning",
                    details={"removed_tools": removed_tools},
                    recommendations=[
                        "Tools were removed since the baseline was saved. "
                        "Verify this is intentional and update the baseline."
                    ],
                )
            )

        # Per-tool schema comparison for tools present in both
        common_tools = sorted(baseline_names & current_names)
        for tool_name in common_tools:
            baseline_def = baseline_schemas[tool_name]
            current_def = current_schemas[tool_name]

            baseline_input = baseline_def.get("inputSchema", {})
            current_input = current_def.get("inputSchema", {})

            baseline_props = baseline_input.get("properties", {})
            current_props = current_input.get("properties", {})

            baseline_required = set(baseline_input.get("required", []))
            current_required = set(current_input.get("required", []))

            findings: list[str] = []

            # Check for type changes in existing properties
            for prop_name in set(baseline_props.keys()) & set(current_props.keys()):
                old_type = baseline_props[prop_name].get("type")
                new_type = current_props[prop_name].get("type")
                if old_type != new_type:
                    findings.append(
                        f"Property {prop_name!r} type changed: {old_type!r} -> {new_type!r}"
                    )

            # Check for removed required fields
            removed_required = sorted(baseline_required - current_required)
            if removed_required:
                findings.append(f"Required fields removed: {removed_required}")

            # Check for added / removed properties
            added_props = sorted(set(current_props.keys()) - set(baseline_props.keys()))
            removed_props = sorted(set(baseline_props.keys()) - set(current_props.keys()))
            if added_props:
                findings.append(f"Properties added: {added_props}")
            if removed_props:
                findings.append(f"Properties removed: {removed_props}")

            passed = len(findings) == 0
            severity = "warning" if not passed else "info"

            recommendations: list[str] = []
            if not passed:
                recommendations.append(
                    f"Schema for tool {tool_name!r} has drifted from the baseline. "
                    "Review the changes and update the baseline if intentional."
                )

            results.append(
                SecurityTestResult(
                    test_name=f"schema_drift:{tool_name}",
                    category="schema_drift",
                    passed=passed,
                    severity=severity,
                    details={
                        "tool": tool_name,
                        "findings": findings,
                    },
                    recommendations=recommendations,
                )
            )

        # If no drift found at all and no added/removed tools, emit a passing result
        if not results:
            results.append(
                SecurityTestResult(
                    test_name="schema_drift:all",
                    category="schema_drift",
                    passed=True,
                    severity="info",
                    details={"tool_count": len(current_names)},
                    recommendations=[],
                )
            )

        return results

    def save_baseline(self, path: Path) -> None:
        """Save the current tool schemas as a JSON baseline file.

        The baseline can later be passed to :meth:`test_schema_drift` to
        detect changes.
        """
        tools = self._list_tools()
        schemas = _extract_tool_schemas(tools)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(schemas, f, indent=2, sort_keys=True)

    # -- run all ----------------------------------------------------------

    def run_all(self) -> list[SecurityTestResult]:
        """Run all security tests and return combined results."""
        results: list[SecurityTestResult] = []
        results.extend(self.test_prompt_injection())
        results.extend(self.test_capability_escalation())
        results.extend(self.test_resource_exhaustion())
        results.extend(self.test_schema_drift())
        return results
