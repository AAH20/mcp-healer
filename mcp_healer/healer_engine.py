"""
Autonomous Payload Healing Engine & Proxy Middleware for MCP-Healer.
Intercepts broken MCP calls and applies real-time schema mutations in <0.5ms.
"""

import time
from typing import Dict, List, Optional, Callable, Any
from .models import (
    HealingStrategy,
    SchemaPatchRule,
    HealedInvocationResult,
    HealerMetrics,
)
from .reflector import RuntimeSchemaReflector


class MCPHealerMiddleware:
    """Self-healing middleware wrapper for Model Context Protocol tools."""

    def __init__(self):
        self.tool_schemas: Dict[str, Dict[str, Any]] = {}
        self.tool_handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self.cached_patches: Dict[str, List[SchemaPatchRule]] = {}
        self.metrics = HealerMetrics()

    def register_tool(
        self,
        name: str,
        expected_schema: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any]
    ) -> None:
        """Register a destination MCP tool and its expected input JSON Schema."""
        self.tool_schemas[name] = expected_schema
        self.tool_handlers[name] = handler

    def invoke_with_healing(self, tool_name: str, received_payload: Dict[str, Any]) -> HealedInvocationResult:
        """Execute tool call with real-time heuristic schema mutation if broken."""
        start_time = time.time()
        self.metrics.total_calls_intercepted += 1

        if tool_name not in self.tool_schemas:
            return HealedInvocationResult(
                tool_name=tool_name,
                success=False,
                original_payload=received_payload,
                healed_payload=received_payload,
                error=f"Tool '{tool_name}' not registered in MCP-Healer catalog",
                latency_ms=(time.time() - start_time) * 1000.0
            )

        expected_schema = self.tool_schemas[tool_name]
        handler = self.tool_handlers[tool_name]

        # 1. Check if cached patches exist for this tool
        rules = self.cached_patches.get(tool_name)
        if rules is None:
            # Diagnose and compute healing plan
            rules = RuntimeSchemaReflector.diagnose_and_plan(expected_schema, received_payload)
            if rules:
                self.cached_patches[tool_name] = rules
                self.metrics.active_cached_patches = len(self.cached_patches)

        # 2. Mutate payload if rules exist
        healed_payload = received_payload.copy()
        was_healed = len(rules) > 0

        for rule in rules:
            if rule.strategy == HealingStrategy.STRUCTURAL_WRAP:
                healed_payload = {rule.target_field: healed_payload}
                break

            elif rule.strategy == HealingStrategy.FIELD_RENAME and rule.source_field:
                val = healed_payload.pop(rule.source_field, None)
                if val is not None:
                    healed_payload[rule.target_field] = val

            elif rule.strategy == HealingStrategy.TYPE_COERCION:
                val = healed_payload.get(rule.target_field)
                if val is not None:
                    if rule.expected_type == "integer":
                        healed_payload[rule.target_field] = int(val)
                    elif rule.expected_type == "boolean":
                        healed_payload[rule.target_field] = (str(val).lower() in ("true", "1", "yes"))

            elif rule.strategy == HealingStrategy.DEFAULT_INJECTION:
                if rule.target_field not in healed_payload:
                    healed_payload[rule.target_field] = rule.default_value

            elif rule.strategy == HealingStrategy.ENUM_NORMALIZATION:
                healed_payload[rule.target_field] = rule.default_value

        # 3. Dispatch to underlying handler
        try:
            res = handler(healed_payload)
            success = True
            error = None
            if was_healed:
                self.metrics.healed_calls += 1
            else:
                self.metrics.clean_calls += 1
        except Exception as e:
            res = None
            success = False
            error = str(e)
            self.metrics.failed_calls += 1

        duration_ms = (time.time() - start_time) * 1000.0

        return HealedInvocationResult(
            tool_name=tool_name,
            success=success,
            original_payload=received_payload,
            healed_payload=healed_payload,
            applied_rules=rules,
            execution_result=res,
            error=error,
            latency_ms=duration_ms,
            was_healed=was_healed
        )
