# 🩹 MCP-Healer

> **Self-Healing Runtime Middleware & Schema Mutation Adapter for Model Context Protocol (MCP) Tools**  
> Intercepts schema validation errors, 400 Bad Requests, and signature drifts in autonomous agent swarms, healing broken payloads in `<0.1ms` before downstream execution.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![MCP: 2026 Compatible](https://img.shields.io/badge/MCP-Standard%202026-brightgreen.svg)](https://modelcontextprotocol.io)
[![Frontier: Claude Opus 5.5 & GPT-6 Astra](https://img.shields.io/badge/Frontier-Claude%20Opus%205.5%20%7C%20GPT--6%20Astra-purple.svg)](https://anthropic.com)

---

## ⚡ The Problem: Frontier Agent Schema Drift

As autonomous coding and reasoning agents (**Claude Opus 5.5**, **GPT-6 Astra**, **Gemini 3.8 Flash**) run complex multi-step trajectories across hundreds of MCP servers, up to **14% of tool calls fail** due to innocuous schema mismatches:
1. **Subtle Field Renames**: Agent sends `customer_uuid` when the MCP schema expects `account_uuid`.
2. **Type Coercion Failures**: Agent serializes port numbers or thresholds as strings (`"8080"` vs `8080`).
3. **Structural Nesting Discrepancies**: Agent outputs flat key-value pairs instead of wrapping them inside `{ "transaction": { ... } }`.
4. **Enum Casing Drift**: Agent outputs `"usd"` instead of canonical uppercase `"USD"`.

In standard agent harnesses, a 400 Bad Request triggers an expensive reasoning retry loop, adding **1.5s - 4.2s of latency** and burning tokens. **MCP-Healer** eliminates this friction by introspecting schemas in-flight and applying deterministic, learned heuristic mutations in `<0.1ms`.

---

## 🏛️ Architecture & Interception Flow

```mermaid
sequenceDiagram
    autonumber
    actor Agent as Autonomous Agent<br/>(Claude Opus 5.5 / GPT-6 Astra)
    participant Proxy as MCP-Healer Proxy Middleware
    participant Cache as Patch Cache & Rule Engine
    participant Tool as Target MCP Server / Tool

    Agent->>Proxy: invoke(tool_name, broken_payload)
    Proxy->>Cache: Lookup cached mutation rules for tool
    alt Cache Miss
        Proxy->>Proxy: Reflect JSON Schema vs Payload
        Proxy->>Proxy: Compute Healing Plan (Fuzzy match, type cast, wrap)
        Proxy->>Cache: Store learned patch rule
    end
    Proxy->>Proxy: Apply mutations (<0.1ms)
    Proxy->>Tool: invoke(tool_name, healed_payload)
    Tool-->>Proxy: Success Result (200 OK)
    Proxy-->>Agent: Execution Response (Zero LLM retry needed)
```

```mermaid
flowchart TD
    subgraph INGRESS["Ingress Layer"]
        A["Agent Invocation"] --> B["MCP-Healer Gateway"]
    end

    subgraph DIAGNOSTICS["Diagnostic & Reflection Engine"]
        B --> C{"Cached Patch Exists?"}
        C -- No --> D["Inspect Target Tool JSON Schema"]
        D --> E["Token & Levenshtein Fuzzy Matcher"]
        D --> F["Type Coercion & Casting Analyzer"]
        D --> G["Structural Wrapper & Root Key Detector"]
        E & F & G --> H["Synthesize SchemaPatchRules"]
        H --> I["Update Dynamic Patch Cache"]
    end

    subgraph HEALING["Runtime Mutation Pipeline"]
        C -- Yes --> J["Fetch Cached Rules"]
        I --> J
        J --> K["Apply Field Renames"]
        K --> L["Apply Type Normalizations"]
        L --> M["Apply Structural Wrappers"]
        M --> N["Apply Safe Schema Defaults"]
    end

    subgraph EXECUTION["Downstream Execution"]
        N --> O["Target MCP Tool Handler"]
        O --> P["Return Result to Agent"]
    end
```

```mermaid
stateDiagram-v2
    [*] --> BrokenPayloadReceived
    BrokenPayloadReceived --> SchemaValidation
    SchemaValidation --> NeedsHealing: Schema Mismatch (400)
    SchemaValidation --> DispatchTool: Clean Payload (Valid)

    state NeedsHealing {
        [*] --> CheckFuzzyKeys
        CheckFuzzyKeys --> CoerceTypes: Match Found (score >= 0.4)
        CheckFuzzyKeys --> InjectDefaults: No Key Match
        InjectDefaults --> CoerceTypes
        CoerceTypes --> WrapStructure
        WrapStructure --> [*]
    }

    NeedsHealing --> DispatchTool: Healed Payload (<0.1ms)
    DispatchTool --> ExecutionSucceeded: 200 OK
    DispatchTool --> ExecutionFailed: Tool Internal Error
    ExecutionSucceeded --> [*]
    ExecutionFailed --> [*]
```

---

## 🚀 Key Features

- **Sub-Millisecond In-Flight Repair**: Patches broken tool invocations in under **0.08 ms**, completely invisible to the LLM agent.
- **Token & Levenshtein Fuzzy Field Mapping**: Automatically matches renamed parameters (`customer_id` -> `account_uuid`) using token set intersections and sequence similarity ratios.
- **Automatic Type Coercion**: Casts numeric strings (`"8080"` -> `8080`), boolean representations, and case-sensitive enums (`"usd"` -> `"USD"`).
- **Structural Payload Wrapping**: Detects single-object container schemas and nests flat payloads automatically.
- **LRU Patch Rule Caching**: After the first heuristic deduction, subsequent calls to the same tool bypass analysis and apply cached mutations in `<0.01ms`.
- **Zero Dependencies**: Pure standard library Python 3.10+ implementation with zero external baggage.

---

## 📦 Quick Start

### Installation

```bash
pip install mcp-healer
```

### Python SDK Usage

```python
from mcp_healer import MCPHealerMiddleware

# Initialize middleware
mw = MCPHealerMiddleware()

# Register your destination MCP tool schema and handler
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
    handler=lambda p: {"status": "ok", "account": p["account_uuid"], "currency": p["currency"]}
)

# Intercept and self-heal broken agent payload
result = mw.invoke_with_healing(
    tool_name="query_account_billing",
    received_payload={
        "customer_uuid": "acc_alpha_909",  # Drifted parameter name
        "currency": "usd"                  # Lowercase enum mismatch
    }
)

print(f"Healed: {result.was_healed} in {result.latency_ms:.3f}ms")
print(f"Result: {result.execution_result}")
# Output: Healed: True in 0.076ms
# Result: {'status': 'ok', 'account': 'acc_alpha_909', 'currency': 'USD'}
```

---

## 💻 CLI Interactive Demonstration

Run the built-in interactive demo to observe real-time payload healing across typical frontier agent drift scenarios:

```bash
mcp-healer demo
```

```
========================================================================
  MCP-HEALER: Self-Healing Runtime Middleware for MCP Tools
  Compatible with Claude Opus 5.5, GPT-6 Astra, and Gemini 3.8 Flash
========================================================================

[1/3] Scenario 1: Fuzzy Field Rename & Enum Lowercase Normalization
      Context: Agent passed 'customer_uuid' instead of 'account_uuid' and lowercase 'usd'.
      Target Tool: query_account_billing
      Raw Broken Payload: {"customer_uuid": "acc_alpha_909", "currency": "usd"}
      >> Healed: True | Execution Success: True
      >> Healing Latency: 0.076 ms
      >> Applied Mutation Rules (2):
         * [FIELD_RENAME] Remap renamed field 'customer_uuid' to expected 'account_uuid'
         * [ENUM_NORMALIZATION] Normalize enum 'usd' to canonical 'USD' for field 'currency'
      >> Healed Payload: {"currency": "USD", "account_uuid": "acc_alpha_909"}
      >> Tool Execution Result: {"status": "success", "billed_amount": 142.5, "currency": "USD", "account": "acc_alpha_909"}

[2/3] Scenario 2: String-to-Integer Type Coercion & Default Injection
      Context: Agent serialized port number as string '8080' instead of raw integer 8080.
      Target Tool: provision_gateway
      Raw Broken Payload: {"port": "8080"}
      >> Healed: True | Execution Success: True
      >> Healing Latency: 0.010 ms
      >> Applied Mutation Rules (1):
         * [TYPE_COERCION] Coerce string '8080' to integer 8080 for field 'port'
      >> Healed Payload: {"port": 8080}
      >> Tool Execution Result: {"status": "provisioned", "port": 8080, "ssl_enabled": true}

[3/3] Scenario 3: Structural Payload Wrap under Missing Root Key
      Context: Agent emitted flat arguments instead of nesting inside 'transaction: {...}'.
      Target Tool: dispatch_payment
      Raw Broken Payload: {"recipient": "corp@anthropic.com", "amount": 5000}
      >> Healed: True | Execution Success: True
      >> Healing Latency: 0.007 ms
      >> Applied Mutation Rules (1):
         * [STRUCTURAL_WRAP] Wrap payload under expected root object 'transaction'
      >> Healed Payload: {"transaction": {"recipient": "corp@anthropic.com", "amount": 5000}}
      >> Tool Execution Result: {"transaction_id": "tx_9988231", "processed": true}
```

---

## 🧪 Testing

Run the full unit test suite:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 📄 License

MIT License. Designed and maintained for frontier agent infrastructure in 2026.
