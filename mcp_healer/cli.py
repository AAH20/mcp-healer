"""
CLI interface and interactive demonstration runner for MCP-Healer.
"""

import sys
import json
import argparse
from typing import Dict, Any

from .models import HealingStrategy
from .healer_engine import MCPHealerMiddleware


def create_demo_middleware() -> MCPHealerMiddleware:
    """Sets up an MCPHealerMiddleware instance with sample tools."""
    mw = MCPHealerMiddleware()

    # Tool 1: Billing Query (requires account_uuid, period, currency)
    def billing_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        if "account_uuid" not in payload:
            raise ValueError("Missing mandatory field: account_uuid")
        if not isinstance(payload.get("currency"), str) or payload["currency"] not in ["USD", "EUR", "GBP"]:
            raise ValueError(f"Invalid currency: {payload.get('currency')}")
        return {
            "status": "success",
            "billed_amount": 142.50,
            "currency": payload["currency"],
            "account": payload["account_uuid"],
            "timestamp": "2026-09-25T23:59:00Z"
        }

    mw.register_tool(
        name="query_account_billing",
        expected_schema={
            "type": "object",
            "properties": {
                "account_uuid": {"type": "string"},
                "currency": {"type": "string", "enum": ["USD", "EUR", "GBP"]}
            },
            "required": ["account_uuid", "currency"]
        },
        handler=billing_handler
    )

    # Tool 2: Server Provisioner (requires port: int, debug: bool)
    def provision_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        port = payload.get("port")
        if not isinstance(port, int):
            raise TypeError(f"Port must be integer, got {type(port).__name__} ({port})")
        return {
            "status": "provisioned",
            "port": port,
            "ssl_enabled": True
        }

    mw.register_tool(
        name="provision_gateway",
        expected_schema={
            "type": "object",
            "properties": {
                "port": {"type": "integer"},
                "subdomain": {"type": "string", "default": "api"}
            },
            "required": ["port"]
        },
        handler=provision_handler
    )

    # Tool 3: Payment Dispatcher (requires nested 'transaction' object)
    def payment_handler(payload: Dict[str, Any]) -> Dict[str, Any]:
        if "transaction" not in payload or not isinstance(payload["transaction"], dict):
            raise ValueError("Root key 'transaction' missing or not an object")
        tx = payload["transaction"]
        return {
            "transaction_id": "tx_9988231",
            "processed": True,
            "recipient": tx.get("recipient"),
            "amount": tx.get("amount")
        }

    mw.register_tool(
        name="dispatch_payment",
        expected_schema={
            "type": "object",
            "properties": {
                "transaction": {
                    "type": "object",
                    "properties": {
                        "recipient": {"type": "string"},
                        "amount": {"type": "integer"}
                    },
                    "required": ["recipient", "amount"]
                }
            },
            "required": ["transaction"]
        },
        handler=payment_handler
    )

    return mw


def run_demo():
    print("=" * 72)
    print("  MCP-HEALER: Self-Healing Runtime Middleware for MCP Tools")
    print("  Compatible with Claude Opus 5.5, GPT-6 Astra, and Gemini 3.8 Flash")
    print("=" * 72)

    mw = create_demo_middleware()

    scenarios = [
        {
            "name": "Scenario 1: Fuzzy Field Rename & Enum Lowercase Normalization",
            "tool": "query_account_billing",
            "broken_payload": {
                "customer_uuid": "acc_alpha_909",  # Should be account_uuid
                "currency": "usd"                 # Should be USD
            },
            "description": "Agent passed 'customer_uuid' instead of 'account_uuid' and lowercase 'usd'."
        },
        {
            "name": "Scenario 2: String-to-Integer Type Coercion & Default Injection",
            "tool": "provision_gateway",
            "broken_payload": {
                "port": "8080"  # Sent as string instead of int
            },
            "description": "Agent serialized port number as string '8080' instead of raw integer 8080."
        },
        {
            "name": "Scenario 3: Structural Payload Wrap under Missing Root Key",
            "tool": "dispatch_payment",
            "broken_payload": {
                "recipient": "corp@anthropic.com",
                "amount": 5000
            },
            "description": "Agent emitted flat arguments instead of nesting inside 'transaction: {...}'."
        }
    ]

    for idx, sc in enumerate(scenarios, 1):
        print(f"\n[{idx}/3] {sc['name']}")
        print(f"      Context: {sc['description']}")
        print(f"      Target Tool: {sc['tool']}")
        print(f"      Raw Broken Payload: {json.dumps(sc['broken_payload'])}")

        res = mw.invoke_with_healing(sc["tool"], sc["broken_payload"])

        print(f"      >> Healed: {res.was_healed} | Execution Success: {res.success}")
        print(f"      >> Healing Latency: {res.latency_ms:.3f} ms")
        print(f"      >> Applied Mutation Rules ({len(res.applied_rules)}):")
        for rule in res.applied_rules:
            print(f"         * [{rule.strategy.value}] {rule.description}")
        print(f"      >> Healed Payload: {json.dumps(res.healed_payload)}")
        print(f"      >> Tool Execution Result: {json.dumps(res.execution_result)}")

    print("\n" + "=" * 72)
    print("  MCP-HEALER RUNTIME METRICS SUMMARY")
    print(f"  Total Calls Intercepted : {mw.metrics.total_calls_intercepted}")
    print(f"  Clean Calls             : {mw.metrics.clean_calls}")
    print(f"  Self-Healed Calls       : {mw.metrics.healed_calls}")
    print(f"  Failed Invocations      : {mw.metrics.failed_calls}")
    print(f"  Cached Schema Patches   : {mw.metrics.active_cached_patches}")
    print("=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="mcp-healer: Self-Healing Runtime Middleware & Schema Mutation Adapter for MCP Tools"
    )
    subparsers = parser.add_subparsers(dest="command")

    demo_parser = subparsers.add_parser("demo", help="Run interactive self-healing demonstration scenarios")
    inspect_parser = subparsers.add_parser("inspect", help="Inspect active schema healing rules")

    args = parser.parse_args()

    if args.command == "demo" or len(sys.argv) == 1:
        run_demo()
    elif args.command == "inspect":
        print("MCP-Healer Engine Ready. Run 'mcp-healer demo' for live scenarios.")


if __name__ == "__main__":
    main()
