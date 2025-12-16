# Google GenAI LLM Provider

This module provides integration with Google's Generative AI (Gemini) models through LangChain's `ChatGoogleGenerativeAI` wrapper.

## Thought Signatures

Gemini 3 Pro and 2.5 models use **thought signatures** - encrypted representations of the model's internal reasoning process. These signatures must be preserved and passed back to maintain reasoning context across multi-turn tool calls.

### Official Documentation
- [Google AI: Thought Signatures](https://ai.google.dev/gemini-api/docs/thought-signatures)

### Requirements by Model

| Model | Thought Signatures |
|-------|-------------------|
| **Gemini 3 Pro** | **Mandatory** - 400 error if missing |
| **Gemini 2.5** | Optional - but recommended for quality |

---

## Architecture Flow

### Complete Flow: Tool Call with Thought Signatures

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              USER REQUEST                                        │
│                         "What time is it now?"                                   │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GEMINI API RESPONSE                                    │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  Content {                                                                       │
│    role: "model",                                                                │
│    parts: [                                                                      │
│      Part {                                                                      │
│        function_call: FunctionCall {                                             │
│          name: "time.get_current_time",                                          │
│          args: {}                                                                │
│        },                                                                        │
│        thought_signature: <binary_signature>  ◄── CRITICAL: Model's reasoning   │
│      }                                                                           │
│    ]                                                                             │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LANGCHAIN-GOOGLE-GENAI (v3.2.0)                               │
│                      _parse_response_candidate()                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  • Extracts thought_signature from Part                                          │
│  • Encodes to base64 for JSON serialization                                      │
│  • Stores in additional_kwargs keyed by tool_call_id                             │
│                                                                                  │
│  AIMessage {                                                                     │
│    content: " ",                                                                 │
│    tool_calls: [                                                                 │
│      {                                                                           │
│        "id": "38eb36fc-512b-429c-bd8f-df52c31ad840",  ◄── Unique ID             │
│        "name": "time.get_current_time",                                          │
│        "args": {},                                                               │
│        "type": "tool_call"                                                       │
│      }                                                                           │
│    ],                                                                            │
│    additional_kwargs: {                                                          │
│      "__gemini_function_call_thought_signatures__": {                            │
│        "38eb36fc-512b-429c-bd8f-df52c31ad840": "EsEFCr4F..."  ◄── base64 sig    │
│      }                                                                           │
│    }                                                                             │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         YOUR CONVERTER                                           │
│                     LangChainConverter.from_lc_message()                         │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  • Converts AIMessage → ChatMessage                                              │
│  • Maps "id" → "tool_call_id"                                                    │
│  • PRESERVES additional_kwargs (including thought signatures)                    │
│                                                                                  │
│  ChatMessage {                                                                   │
│    role: Role.ASSISTANT,                                                         │
│    content: " ",                                                                 │
│    tool_calls: [                                                                 │
│      ToolCall {                                                                  │
│        name: "time.get_current_time",                                            │
│        args: {},                                                                 │
│        tool_call_id: "38eb36fc-512b-429c-bd8f-df52c31ad840"  ◄── ID preserved   │
│      }                                                                           │
│    ],                                                                            │
│    additional_kwargs: {                                                          │
│      "__gemini_function_call_thought_signatures__": {                            │
│        "38eb36fc-...": "EsEFCr4F..."  ◄── PRESERVED!                            │
│      }                                                                           │
│    }                                                                             │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         TOOL EXECUTION                                           │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  Tool: time.get_current_time()                                                   │
│  Result: {"datetime": "2025-12-09 13:47:25", "timezone": "UTC", ...}            │
│                                                                                  │
│  ChatMessage {                                                                   │
│    role: Role.TOOL,                                                              │
│    content: "{'datetime': '2025-12-09 13:47:25', ...}",                         │
│    tool_call_id: "38eb36fc-512b-429c-bd8f-df52c31ad840"  ◄── Links to call      │
│  }                                                                               │
│                                                                                  │
│  NOTE: ToolMessage does NOT need thought_signature                               │
│        (signature is on the FunctionCall, not FunctionResponse)                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         YOUR CONVERTER                                           │
│                       LangChainConverter.to_lc()                                 │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  • Converts ChatMessage → AIMessage                                              │
│  • Maps "tool_call_id" → "id"                                                    │
│  • PASSES additional_kwargs (including thought signatures)                       │
│                                                                                  │
│  AIMessage {                                                                     │
│    content: "[TOOL CALL]",                                                       │
│    tool_calls: [                                                                 │
│      {                                                                           │
│        "id": "38eb36fc-512b-429c-bd8f-df52c31ad840",  ◄── Mapped back           │
│        "name": "time.get_current_time",                                          │
│        "args": {},                                                               │
│        "type": "tool_call"                                                       │
│      }                                                                           │
│    ],                                                                            │
│    additional_kwargs: {                                                          │
│      "__gemini_function_call_thought_signatures__": {                            │
│        "38eb36fc-...": "EsEFCr4F..."  ◄── PASSED THROUGH!                       │
│      }                                                                           │
│    }                                                                             │
│  }                                                                               │
│                                                                                  │
│  ToolMessage {                                                                   │
│    content: "{'datetime': '2025-12-09 13:47:25', ...}",                         │
│    tool_call_id: "38eb36fc-512b-429c-bd8f-df52c31ad840",                        │
│    name: "time.get_current_time"                                                 │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LANGCHAIN-GOOGLE-GENAI (v3.2.0)                               │
│                        _parse_chat_history()                                     │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  1. Reads AIMessage.additional_kwargs                                            │
│  2. Looks up signature by tool_call["id"]                                        │
│  3. Attaches to FunctionCall Part                                                │
│                                                                                  │
│  function_call_sigs = message.additional_kwargs.get(                             │
│      "__gemini_function_call_thought_signatures__", {}                           │
│  )                                                                               │
│  sig = function_call_sigs.get("38eb36fc-...")  ◄── FOUND!                       │
│                                                                                  │
│  Content {                                                                       │
│    role: "model",                                                                │
│    parts: [                                                                      │
│      Part {                                                                      │
│        function_call: FunctionCall {...},                                        │
│        thought_signature: <binary_from_base64>  ◄── REAL signature attached!    │
│      }                                                                           │
│    ]                                                                             │
│  }                                                                               │
│                                                                                  │
│  Content {                                                                       │
│    role: "user",                                                                 │
│    parts: [                                                                      │
│      Part {                                                                      │
│        function_response: FunctionResponse {                                     │
│          name: "time.get_current_time",                                          │
│          response: {"datetime": "2025-12-09 13:47:25", ...}                     │
│        }                                                                         │
│      }                                                                           │
│    ]                                                                             │
│  }                                                                               │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           GEMINI API REQUEST                                     │
│ ─────────────────────────────────────────────────────────────────────────────── │
│                                                                                  │
│  ✅ FunctionCall Part has thought_signature                                      │
│  ✅ Model can continue reasoning with full context                               │
│  ✅ No 400 error (Gemini 3 Pro)                                                  │
│  ✅ No degraded performance (Gemini 2.5)                                         │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              FINAL RESPONSE                                      │
│                    "The current time is 1:47 PM UTC."                            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Key Data Structures

### Thought Signature Storage

```
AIMessage.additional_kwargs = {
    "__gemini_function_call_thought_signatures__": {
        "<tool_call_id>": "<base64_encoded_signature>"
    }
}
```

### ID Mapping

| Component | Field Name | Example Value |
|-----------|------------|---------------|
| LangChain AIMessage | `tool_calls[i]["id"]` | `"38eb36fc-512b-..."` |
| Your ToolCall | `tool_call_id` | `"38eb36fc-512b-..."` |
| LangChain ToolMessage | `tool_call_id` | `"38eb36fc-512b-..."` |
| Signature Key | `additional_kwargs[KEY][id]` | `"38eb36fc-512b-..."` |

---

## Parallel vs Sequential Tool Calls

### Parallel (Same Step)

```
Model Response:
  FC1 ("get_weather_paris")    + signature  ◄── Only first has signature
  FC2 ("get_weather_london")   (no signature)

Your Response:
  FC1 + signature + FC2 + FR1 + FR2  ◄── Keep together, not interleaved!
```

### Sequential (Multi-Step)

```
Step 1:
  FC1 ("check_flight") + signature_A
  FR1

Step 2:
  FC1 + signature_A + FR1 + FC2 ("book_taxi") + signature_B  ◄── Each step has signature
  FR2

Step 3:
  ... + FC2 + signature_B + FR2 + final_response
```

---

## Fallback Behavior

If thought signatures are missing (e.g., from older code), `langchain-google-genai` v3.1.0+ injects a **dummy signature** to prevent 400 errors:

```python
DUMMY_THOUGHT_SIGNATURE = base64.decode("ErQCCrECAdHtim8MtxgeMCRCi...")
```

⚠️ **Note:** Using dummy signatures may result in degraded reasoning quality. Always preserve real signatures when possible.

---

## Files

| File | Purpose |
|------|---------|
| `google_genai.py` | Main LLM client wrapper |
| `../common/chat/message.py` | ChatMessage with `additional_kwargs` for signatures |
| `../common/chat/converter.py` | Bidirectional LangChain ↔ ChatMessage conversion |
| `../common/chat/utils.py` | ID mapping utilities |

---

## Dependencies

- `langchain-google-genai>=3.1.0` (v3.2.0 recommended)
- `google-genai>=1.0.0`

