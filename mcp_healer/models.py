"""
Data models and mutation schemas for MCP-Healer.
Self-Healing Runtime Middleware & Schema Mutation Adapter for Model Context Protocol Tools.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import time


class HealingStrategy(str, Enum):
    FIELD_RENAME = "FIELD_RENAME"             # e.g. customer_id -> account_uuid
    TYPE_COERCION = "TYPE_COERCION"           # e.g. "8080" -> 8080
    STRUCTURAL_WRAP = "STRUCTURAL_WRAP"       # e.g. flat args -> {payment: {...}}
    DEFAULT_INJECTION = "DEFAULT_INJECTION"   # injecting missing required defaults
    ENUM_NORMALIZATION = "ENUM_NORMALIZATION" # e.g. "usd" -> "USD"


@dataclass
class SchemaPatchRule:
    strategy: HealingStrategy
    target_field: str
    source_field: Optional[str] = None
    expected_type: Optional[str] = None
    default_value: Optional[Any] = None
    description: str = ""


@dataclass
class HealedInvocationResult:
    tool_name: str
    success: bool
    original_payload: Dict[str, Any]
    healed_payload: Dict[str, Any]
    applied_rules: List[SchemaPatchRule] = field(default_factory=list)
    execution_result: Optional[Any] = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    was_healed: bool = False


@dataclass
class HealerMetrics:
    total_calls_intercepted: int = 0
    clean_calls: int = 0
    healed_calls: int = 0
    failed_calls: int = 0
    active_cached_patches: int = 0
    average_healing_latency_ms: float = 0.0
