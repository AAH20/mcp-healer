"""
Runtime Schema Reflector & Heuristic Mismatch Analyzer for MCP-Healer.
"""

import difflib
from typing import Dict, List, Optional, Tuple, Any
from .models import HealingStrategy, SchemaPatchRule


def _fuzzy_similarity(s1: str, s2: str) -> float:
    """Compute combined token overlap and string sequence similarity between two field names."""
    t1 = set(s1.lower().replace("-", "_").split("_"))
    t2 = set(s2.lower().replace("-", "_").split("_"))
    token_score = 0.0
    if t1 and t2:
        token_score = len(t1.intersection(t2)) / len(t1.union(t2))
    seq_score = difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    return max(token_score, seq_score)


class RuntimeSchemaReflector:
    """Reflects over expected JSON schemas and deduces healing rules."""

    @staticmethod
    def diagnose_and_plan(
        expected_schema: Dict[str, Any],
        received_payload: Dict[str, Any]
    ) -> List[SchemaPatchRule]:
        rules: List[SchemaPatchRule] = []
        properties: Dict[str, Any] = expected_schema.get("properties", {})
        required: List[str] = expected_schema.get("required", [])

        # Check for single-key root wrapper requirement
        if len(properties) == 1 and list(properties.keys())[0] not in received_payload:
            root_key = list(properties.keys())[0]
            root_prop = properties[root_key]
            if root_prop.get("type") == "object":
                inner_props = root_prop.get("properties", {})
                if any(k in inner_props for k in received_payload.keys()):
                    rules.append(SchemaPatchRule(
                        strategy=HealingStrategy.STRUCTURAL_WRAP,
                        target_field=root_key,
                        description=f"Wrap payload under expected root object '{root_key}'"
                    ))
                    return rules

        # 1. Check Missing Required Fields & Match with Provided Keys
        unmatched_received = set(received_payload.keys())

        for req_field in required:
            if req_field not in received_payload:
                # Find best fuzzy match from unmatched received keys
                best_match = None
                best_score = 0.0
                for cand in unmatched_received:
                    score = _fuzzy_similarity(cand, req_field)
                    if score > best_score:
                        best_score = score
                        best_match = cand

                if best_match and best_score >= 0.4:
                    rules.append(SchemaPatchRule(
                        strategy=HealingStrategy.FIELD_RENAME,
                        target_field=req_field,
                        source_field=best_match,
                        description=f"Remap renamed field '{best_match}' to expected '{req_field}'"
                    ))
                    unmatched_received.remove(best_match)
                else:
                    # Inject default value if schema specifies or provide safe fallback
                    field_meta = properties.get(req_field, {})
                    default_val = field_meta.get("default", "" if field_meta.get("type") == "string" else 0)
                    rules.append(SchemaPatchRule(
                        strategy=HealingStrategy.DEFAULT_INJECTION,
                        target_field=req_field,
                        default_value=default_val,
                        description=f"Inject missing required field '{req_field}' with default '{default_val}'"
                    ))

        # 2. Check Type Coercions & Enum Normalization
        for key, val in received_payload.items():
            prop_spec = properties.get(key, {})
            expected_type = prop_spec.get("type")

            if expected_type == "integer" and isinstance(val, str) and val.isdigit():
                rules.append(SchemaPatchRule(
                    strategy=HealingStrategy.TYPE_COERCION,
                    target_field=key,
                    expected_type="integer",
                    description=f"Coerce string '{val}' to integer {int(val)} for field '{key}'"
                ))
            elif expected_type == "boolean" and isinstance(val, str):
                rules.append(SchemaPatchRule(
                    strategy=HealingStrategy.TYPE_COERCION,
                    target_field=key,
                    expected_type="boolean",
                    description=f"Coerce string '{val}' to boolean for field '{key}'"
                ))

            # Enum case mismatch
            enum_vals = prop_spec.get("enum", [])
            if enum_vals and isinstance(val, str):
                for ev in enum_vals:
                    if isinstance(ev, str) and ev.lower() == val.lower() and ev != val:
                        rules.append(SchemaPatchRule(
                            strategy=HealingStrategy.ENUM_NORMALIZATION,
                            target_field=key,
                            default_value=ev,
                            description=f"Normalize enum '{val}' to canonical '{ev}' for field '{key}'"
                        ))

        return rules
