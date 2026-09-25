"""
Unit tests for MCP-Healer schema mutation and execution proxy.
"""

import unittest
from mcp_healer.models import HealingStrategy
from mcp_healer.reflector import RuntimeSchemaReflector
from mcp_healer.healer_engine import MCPHealerMiddleware


class TestMCPHealer(unittest.TestCase):

    def setUp(self):
        self.mw = MCPHealerMiddleware()

    def test_fuzzy_field_renaming(self):
        schema = {
            "type": "object",
            "properties": {
                "user_identifier": {"type": "string"}
            },
            "required": ["user_identifier"]
        }
        self.mw.register_tool("get_user", schema, lambda p: f"User:{p['user_identifier']}")

        res = self.mw.invoke_with_healing("get_user", {"user_id": "usr_99"})
        self.assertTrue(res.success)
        self.assertTrue(res.was_healed)
        self.assertEqual(res.healed_payload.get("user_identifier"), "usr_99")
        self.assertNotIn("user_id", res.healed_payload)

    def test_type_coercion_int(self):
        schema = {
            "type": "object",
            "properties": {
                "max_tokens": {"type": "integer"}
            },
            "required": ["max_tokens"]
        }
        self.mw.register_tool("set_limit", schema, lambda p: p["max_tokens"] * 2)

        res = self.mw.invoke_with_healing("set_limit", {"max_tokens": "4096"})
        self.assertTrue(res.success)
        self.assertEqual(res.healed_payload["max_tokens"], 4096)
        self.assertEqual(res.execution_result, 8192)

    def test_structural_wrap(self):
        schema = {
            "type": "object",
            "properties": {
                "auth": {
                    "type": "object",
                    "properties": {
                        "api_key": {"type": "string"},
                        "region": {"type": "string"}
                    }
                }
            },
            "required": ["auth"]
        }
        self.mw.register_tool("authenticate", schema, lambda p: p["auth"]["api_key"].upper())

        res = self.mw.invoke_with_healing("authenticate", {"api_key": "sec_123", "region": "us-east-1"})
        self.assertTrue(res.success)
        self.assertTrue(res.was_healed)
        self.assertEqual(res.healed_payload, {"auth": {"api_key": "sec_123", "region": "us-east-1"}})
        self.assertEqual(res.execution_result, "SEC_123")

    def test_enum_normalization(self):
        schema = {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["AGGRESSIVE", "PASSIVE"]}
            },
            "required": ["mode"]
        }
        self.mw.register_tool("set_mode", schema, lambda p: f"Mode:{p['mode']}")

        res = self.mw.invoke_with_healing("set_mode", {"mode": "aggressive"})
        self.assertTrue(res.success)
        self.assertEqual(res.healed_payload["mode"], "AGGRESSIVE")

    def test_cached_patch_reuse(self):
        schema = {
            "type": "object",
            "properties": {
                "target_host": {"type": "string"}
            },
            "required": ["target_host"]
        }
        self.mw.register_tool("connect_host", schema, lambda p: p["target_host"])

        res1 = self.mw.invoke_with_healing("connect_host", {"target_ip": "127.0.0.1"})
        self.assertTrue(res1.success)
        self.assertEqual(self.mw.metrics.active_cached_patches, 1)

        # Second call reuses cached rule
        res2 = self.mw.invoke_with_healing("connect_host", {"target_ip": "10.0.0.1"})
        self.assertTrue(res2.success)
        self.assertEqual(res2.healed_payload["target_host"], "10.0.0.1")

    def test_unknown_tool_fails_safely(self):
        res = self.mw.invoke_with_healing("non_existent_tool", {"foo": "bar"})
        self.assertFalse(res.success)
        self.assertIn("not registered", res.error)


if __name__ == "__main__":
    unittest.main()
