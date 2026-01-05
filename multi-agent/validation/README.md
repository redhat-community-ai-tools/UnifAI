# Validation System

A SOLID, clean, and professional validation framework for validating element configurations,
saved resources, and blueprints in the multi-agent system.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [Data Flow](#data-flow)
5. [Validation Scenarios](#validation-scenarios)
6. [Creating a Validator](#creating-a-validator)
7. [API Endpoints](#api-endpoints)
8. [Design Principles](#design-principles)

---

## Overview

The validation system provides:

- **Element Validation**: Each element type can define how to validate itself
- **Resource Validation**: Validate saved resources and all transitive dependencies
- **Blueprint Validation**: Validate all elements in a blueprint

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         VALIDATION SYSTEM OVERVIEW                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────────────┐ │
│   │   Resource  │    │  Blueprint  │    │       Inline Config             │ │
│   │   (saved)   │    │   (saved)   │    │      (not saved yet)            │ │
│   └──────┬──────┘    └──────┬──────┘    └────────────────┬────────────────┘ │
│          │                  │                            │                  │
│          ▼                  ▼                            ▼                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                    VALIDATION ORCHESTRATION                          │  │
│   │  ┌────────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │  │
│   │  │ResourcesService│  │   BlueprintService   │  │ Direct API Call  │  │  │
│   │  └───────┬────────┘  └──────────┬───────────┘  └────────┬─────────┘  │  │
│   │          │                      │                       │            │  │
│   │          └──────────────────────┼───────────────────────┘            │  │
│   │                                 ▼                                    │  │
│   │                   ┌─────────────────────────┐                        │  │
│   │                   │ ElementValidationService │                       │  │
│   │                   └─────────────────────────┘                        │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                     │                                       │
│                                     ▼                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │                      ELEMENT VALIDATORS                              │  │
│   │  ┌────────────────┐ ┌───────────────────┐ ┌────────────────────────┐ │  │
│   │  │McpProviderValid│ │A2AAgentNodeValid  │ │ CustomAgentNodeValid   │ │  │
│   │  │     ator       │ │      ator         │ │       ator             │ │  │
│   │  └────────────────┘ └───────────────────┘ └────────────────────────┘ │  │
│   └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture

### Module Structure

```
multi-agent/
├── elements/
│   └── common/
│       └── validator.py          # Interface, base class, and core models
│           ├── ValidationSeverity      # Enum: ERROR, WARNING, INFO
│           ├── ValidationCode          # Enum: Standard codes
│           ├── ValidationMessage       # Single validation message
│           ├── ValidatorReport         # What a validator returns
│           ├── ElementValidationResult # Final result with metadata
│           ├── ValidationContext       # Immutable context for validators
│           ├── ElementValidator        # Abstract interface
│           └── BaseElementValidator    # Base class with utilities
│
├── validation/
│   ├── __init__.py              # Public exports
│   ├── service.py               # ElementValidationService
│   ├── models.py                # Service-level models (ConfigMeta, BlueprintValidationResult)
│   └── README.md                # This file
│
├── resources/
│   ├── service.py               # ResourcesService.validate_resource()
│   └── validation/
│       └── resolver.py          # DependencyResolver (topological sort)
│
└── blueprints/
    ├── service.py               # BlueprintService.validate_blueprint()
    └── validation/
        └── collector.py         # BlueprintConfigCollector
```

### Class Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLASS HIERARCHY                                │
└─────────────────────────────────────────────────────────────────────────────┘

                       elements/common/validator.py
                    ┌──────────────────────────────────┐
                    │       ElementValidator           │  ◄─── Abstract Interface
                    │          <<abstract>>            │
                    ├──────────────────────────────────┤
                    │ + validate(config, context)      │
                    │   → ValidatorReport              │
                    └───────────────┬──────────────────┘
                                    │
                                    │ extends
                                    ▼
                    ┌──────────────────────────────────┐
                    │      BaseElementValidator        │  ◄─── Base Class
                    ├──────────────────────────────────┤
                    │ + _error(code, msg, field)       │
                    │ + _warning(code, msg, field)     │
                    │ + _info(code, msg, field)        │
                    │ + _build_report(messages, deps)  │
                    │ + _check_dependency(ctx, rid...) │
                    └───────────────┬──────────────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
               ▼                    ▼                    ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│ McpProviderValidator │ │A2AAgentNodeValidator │ │CustomAgentNodeValid. │
├──────────────────────┤ ├──────────────────────┤ ├──────────────────────┤
│ + validate()         │ │ + validate()         │ │ + validate()         │
│ + _check_connection()│ │ + _check_connection()│ │   (checks deps only) │
└──────────────────────┘ └──────────────────────┘ └──────────────────────┘
   │                        │                         │
   │ Checks:                │ Checks:                 │ Checks:
   │ - MCP server           │ - A2A endpoint          │ - LLM dependency
   │   reachability         │   reachability          │ - Tools dependencies
   │ - Can list tools       │ - Can get agent card    │ - Retriever dependency
   │                        │ - Retriever (optional)  │ - Provider dependency
```

---

## Core Components

### 1. Data Models (elements/common/validator.py)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATA MODELS                                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌───────────────────────────────┐     ┌───────────────────────────────────────┐
│      ValidationMessage        │     │         ValidationContext             │
├───────────────────────────────┤     ├───────────────────────────────────────┤
│ severity: ValidationSeverity  │     │ timeout_seconds: float = 10.0         │
│ code: str                     │     │ dependency_results: Dict[rid, Result] │
│ message: str                  │     ├───────────────────────────────────────┤
│ field: Optional[str]          │     │ + get_dependency_result(rid)          │
└───────────────────────────────┘     │ + with_dependency_results(results)    │
                                      └───────────────────────────────────────┘


┌───────────────────────────────┐     ┌───────────────────────────────────────┐
│       ValidatorReport         │     │      ElementValidationResult          │
│   (returned by validators)    │     │   (returned to API callers)           │
├───────────────────────────────┤     ├───────────────────────────────────────┤
│ messages: List[Message]       │     │ is_valid: bool                        │
│ checked_dependencies: Dict    │     │ element_rid: str                      │
├───────────────────────────────┤     │ element_type: str                     │
│ @property is_valid: bool      │     │ name: Optional[str]                   │
│ (no ERRORs = valid)           │     │ messages: List[Message]               │
└───────────────────────────────┘     │ dependency_results: Dict[rid, Result] │
        │                             ├───────────────────────────────────────┤
        │  + metadata                 │ + to_dict()                           │
        └────────────────────────────►└───────────────────────────────────────┘
```

**Key Insight**: Validators return `ValidatorReport` (pure findings). 
The service combines it with metadata to create `ElementValidationResult`.

### 2. ElementValidationService (validation/service.py)

The core orchestrator that:
- Looks up validators from `ElementRegistry`
- Calls validators with proper context
- Builds `ElementValidationResult` from `ValidatorReport` + metadata
- Handles ordered validation with dependency accumulation

```python
class ElementValidationService:
    def __init__(self, element_registry: ElementRegistry): ...
    
    def validate(self, config_meta: ConfigMeta, context: ValidationContext) 
        -> ElementValidationResult
    
    def validate_ordered(self, configs: List[ConfigMeta], context: ValidationContext) 
        -> Dict[str, ElementValidationResult]
```

### 3. ConfigMeta (validation/models.py)

Metadata about a config to be validated:

```python
@dataclass
class ConfigMeta:
    rid: str                           # Resource ID
    category: ResourceCategory         # llm, tool, provider, etc.
    element_type: str                  # openai, mcp_provider, etc.
    config: BaseModel                  # The Pydantic config model
    name: Optional[str] = None         # Human-readable name
    dependency_rids: List[str] = []    # RIDs of dependencies
```

### 4. DependencyResolver (resources/validation/resolver.py)

Resolves transitive dependencies using post-order traversal (topological sort):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DEPENDENCY RESOLUTION                                │
│                                                                             │
│   Given: Resource A depends on B, B depends on C                            │
│                                                                             │
│                          A                                                  │
│                          │                                                  │
│                          ▼                                                  │
│                          B                                                  │
│                          │                                                  │
│                          ▼                                                  │
│                          C                                                  │
│                                                                             │
│   resolve_with_deps("A") returns: ["C", "B", "A"]                           │
│                                                                             │
│   This ensures dependencies are validated BEFORE dependents.                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5. BlueprintConfigCollector (blueprints/validation/collector.py)

Collects all configs from a resolved `BlueprintSpec` for validation:

```python
class BlueprintConfigCollector:
    def collect(self, spec: BlueprintSpec) -> List[ConfigMeta]
```

Uses `RefWalker.all_rids()` to capture both external and inline references.

---

## Data Flow

### Resource Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       RESOURCE VALIDATION FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

   API Request                              
   POST /api/resources/resource.validate   
   { "resourceId": "abc123" }               
              │                             
              ▼                             
   ┌──────────────────────┐                 
   │  ResourcesService.   │                 
   │  validate_resource() │                 
   └──────────┬───────────┘                 
              │                             
              │ 1. Resolve dependencies     
              ▼                             
   ┌──────────────────────┐                 
   │  DependencyResolver. │   Returns ordered RIDs:
   │  resolve_with_deps() │   ["dep1", "dep2", "abc123"]
   └──────────┬───────────┘                 
              │                             
              │ 2. Build ConfigMeta for each RID
              │    (fetch from ResourcesRegistry)
              ▼                             
   ┌──────────────────────────────────────────────────────────┐
   │  ordered_configs = [                                     │
   │    ConfigMeta(rid="dep1", category=PROVIDER, type="mcp", │
   │               config=McpConfig(...), name="My MCP"),     │
   │    ConfigMeta(rid="dep2", category=LLM, type="openai",   │
   │               config=OpenAIConfig(...), name="GPT-4"),   │
   │    ConfigMeta(rid="abc123", category=NODE,               │
   │               type="custom_agent", config=..., name=...) │
   │  ]                                                       │
   └──────────────────────┬───────────────────────────────────┘
                          │                             
                          │ 3. Create ValidationContext
                          ▼                             
   ┌──────────────────────────────────────────────────────────┐
   │  context = ValidationContext(                            │
   │    timeout_seconds=10.0,                                 │
   │  )                                                       │
   └──────────────────────┬───────────────────────────────────┘
                          │                             
                          │ 4. Call validation service
                          ▼                             
   ┌──────────────────────────────────────────────────────────┐
   │  ElementValidationService.validate_ordered(              │
   │    configs=ordered_configs,                              │
   │    base_context=context,                                 │
   │  )                                                       │
   └──────────────────────┬───────────────────────────────────┘
                          │                             
                          │ 5. Process each config in order
                          ▼                             
   ┌──────────────────────────────────────────────────────────┐
   │  FOR each config_meta in ordered_configs:                │
   │                                                          │
   │    ┌─────────────────────────────────────────────────┐   │
   │    │ 1. Update context with accumulated results      │   │
   │    │    context = base_context.with_dependency_      │   │
   │    │              results(accumulated_results)       │   │
   │    └─────────────────────────────────────────────────┘   │
   │                          │                               │
   │                          ▼                               │
   │    ┌─────────────────────────────────────────────────┐   │
   │    │ 2. Look up validator from ElementRegistry       │   │
   │    │    spec = registry.get_spec(category, type)     │   │
   │    │    validator_cls = spec.validator_cls           │   │
   │    └─────────────────────────────────────────────────┘   │
   │                          │                               │
   │                          ▼                               │
   │    ┌─────────────────────────────────────────────────┐   │
   │    │ 3. Call validator                               │   │
   │    │    validator = validator_cls()                  │   │
   │    │    report = validator.validate(config, context) │   │
   │    └─────────────────────────────────────────────────┘   │
   │                          │                               │
   │                          ▼                               │
   │    ┌─────────────────────────────────────────────────┐   │
   │    │ 4. Build result from report + metadata          │   │
   │    │    result = ElementValidationResult(            │   │
   │    │      is_valid=report.is_valid,                  │   │
   │    │      element_rid=config_meta.rid,               │   │
   │    │      element_type=config_meta.element_type,     │   │
   │    │      name=config_meta.name,                     │   │
   │    │      messages=report.messages,                  │   │
   │    │      dependency_results=report.checked_deps,    │   │
   │    │    )                                            │   │
   │    └─────────────────────────────────────────────────┘   │
   │                          │                               │
   │                          ▼                               │
   │    ┌─────────────────────────────────────────────────┐   │
   │    │ 5. Store result for later validators            │   │
   │    │    accumulated_results[rid] = result            │   │
   │    └─────────────────────────────────────────────────┘   │
   │                                                          │
   └──────────────────────────────────────────────────────────┘
                          │                             
                          ▼                             
   ┌──────────────────────────────────────────────────────────┐
   │  Return results[requested_rid]                           │
   │  → ElementValidationResult with nested dependency_results│
   └──────────────────────────────────────────────────────────┘
```

### Blueprint Validation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       BLUEPRINT VALIDATION FLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

   API Request                              
   POST /api/blueprints/blueprint.validate   
   { "blueprintId": "bp123" }               
              │                             
              ▼                             
   ┌──────────────────────┐                 
   │  BlueprintService.   │                 
   │  validate_blueprint()│                 
   └──────────┬───────────┘                 
              │                             
              │ 1. Load and resolve blueprint
              ▼                             
   ┌──────────────────────┐                 
   │  load_resolved()     │   Returns BlueprintSpec with
   │                      │   all $refs replaced with configs
   └──────────┬───────────┘                 
              │                             
              │ 2. Collect configs from spec
              ▼                             
   ┌──────────────────────┐                 
   │BlueprintConfigCollector│  Uses RefWalker.all_rids()
   │  .collect(spec)      │   to find inline dependencies
   └──────────┬───────────┘                 
              │                             
              │ Returns List[ConfigMeta]
              ▼                             
   ┌──────────────────────┐                 
   │ElementValidationService│                
   │  .validate_ordered() │                 
   └──────────┬───────────┘                 
              │                             
              ▼                             
   ┌──────────────────────┐                 
   │BlueprintValidationResult│               
   │  blueprint_id: "bp123"  │               
   │  is_valid: bool         │               
   │  element_results: {...} │               
   └──────────────────────┘                 
```

---

## Validation Scenarios

### Scenario 1: MCP Provider Validation

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MCP PROVIDER VALIDATION                                  │
└─────────────────────────────────────────────────────────────────────────────┘

   McpProviderValidator.validate(config, context)
              │
              ▼
   ┌──────────────────────┐
   │ AsyncBridge.run(     │
   │   _check_connection()│
   │ )                    │
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ async def _test():   │
   │   async with         │
   │     McpServerClient: │
   │       get_tools()    │
   └──────────┬───────────┘
              │
              ▼
   ┌──────────────────────┐
   │ asyncio.wait_for(    │
   │   _test(),           │
   │   timeout=10.0       │
   │ )                    │
   └──────────┬───────────┘
              │
              ├───────────────────────┬───────────────────────┐
              │ Success               │ Timeout               │ Error
              ▼                       ▼                       ▼
   INFO: "CONNECTION_OK"    ERROR: "NETWORK_TIMEOUT"  ERROR: "ENDPOINT_UNREACHABLE"
   "Successfully connected" "Timed out after Xs"     "Connection failed: {e}"
```

### Scenario 2: Custom Agent Node Validation (Dependency Checking)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  CUSTOM AGENT NODE VALIDATION                               │
│                  (Dependency-based validation)                              │
└─────────────────────────────────────────────────────────────────────────────┘

   CustomAgentNodeValidator.validate(config, context)
              │
              │ For each dependency (llm, tools[], retriever, provider):
              ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │                                                                          │
   │   config.llm = Ref("$ref:llm-abc123")                                    │
   │              │                                                           │
   │              ▼                                                           │
   │   _check_dependency(context, "llm-abc123", "llm", messages, deps)        │
   │              │                                                           │
   │              │ Look up in context.dependency_results                     │
   │              ▼                                                           │
   │   ┌───────────────────────────────────────────────────────────────────┐  │
   │   │ dep_result = context.get_dependency_result("llm-abc123")          │  │
   │   └───────────────────────────────┬───────────────────────────────────┘  │
   │                                   │                                      │
   │              ┌────────────────────┼────────────────────┐                 │
   │              │ None               │ Found              │                 │
   │              ▼                    │                    │                 │
   │   WARNING: "Dependency           │                    │                 │
   │   was not validated"              │                    │                 │
   │                                   ▼                    ▼                 │
   │                        dep_result.is_valid?                              │
   │                               │                                          │
   │              ┌────────────────┴────────────────┐                         │
   │              │ False                          │ True                     │
   │              ▼                                ▼                          │
   │   ERROR: "Dependency                   (dependency OK,                   │
   │   'Name' (rid) is invalid"             add to checked_deps)              │
   │                                                                          │
   └──────────────────────────────────────────────────────────────────────────┘
              │
              │ All dependencies checked
              ▼
   ┌──────────────────────────────────────────────────────────────────────────┐
   │   if all_deps_valid:                                                     │
   │     INFO: "All N dependencies are valid"                                 │
   │   else:                                                                  │
   │     (ERROR messages already added above)                                 │
   └──────────────────────────────────────────────────────────────────────────┘
```

---

## Creating a Validator

### Step 1: Create the Validator Class

```python
# elements/your_category/your_element/validator.py

from typing import List
from elements.common.validator import (
    BaseElementValidator,
    ValidatorReport,
    ValidationContext,
    ValidationMessage,
    ValidationCode,
)
from elements.your_category.your_element.config import YourElementConfig


class YourElementValidator(BaseElementValidator):
    """
    Validates YourElement configuration.
    """

    def validate(
        self,
        config: YourElementConfig,
        context: ValidationContext,
    ) -> ValidatorReport:
        """
        Validate your element config.
        
        Returns ValidatorReport (service adds metadata).
        """
        messages: List[ValidationMessage] = []

        # 1. Check network connectivity (if applicable)
        with get_async_bridge() as bridge:
            bridge.run(self._check_connection(config, context, messages))

        # 2. Check dependencies (if applicable)
        checked_dependencies = {}
        if config.some_dependency:
            dep_rid = self._extract_rid(config.some_dependency)
            self._check_dependency(
                context, dep_rid, "some_dependency", messages, checked_dependencies
            )

        # 3. Build and return report
        return self._build_report(
            messages=messages,
            checked_dependencies=checked_dependencies,
        )
```

### Step 2: Link Validator to Element Spec

```python
# elements/your_category/your_element/spec/spec.py

from elements.your_category.your_element.validator import YourElementValidator

class YourElementSpec(BaseElementSpec):
    category = ResourceCategory.YOUR_CATEGORY
    type_key = "your_element"
    # ... other spec fields ...
    
    validator_cls = YourElementValidator  # ◄─── Link here
```

### Step 3: Validator Best Practices

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        VALIDATOR BEST PRACTICES                             │
└─────────────────────────────────────────────────────────────────────────────┘

  ✓ DO:
    • Return ValidatorReport, not ElementValidationResult
    • Use _error(), _warning(), _info() helpers for messages
    • Use _build_report() to construct the final report
    • Use _check_dependency() for dependency validation
    • Use AsyncBridge for async operations (network calls)
    • Handle timeouts with asyncio.wait_for()
    • Add INFO messages for successful checks

  ✗ DON'T:
    • Don't try to set element_rid, element_type, or name
      (the service adds these from ConfigMeta)
    • Don't make the validate() method async
      (use AsyncBridge internally instead)
    • Don't access databases or services directly
      (use context.dependency_results for pre-resolved data)
```

---

## API Endpoints

### Validate Saved Resource

```http
POST /api/resources/resource.validate
Content-Type: application/json

{
  "resourceId": "abc123",
  "timeoutSeconds": 10.0
}
```

**Response:** `ElementValidationResult`

### Validate Config (Pre-save)

Validates a resource config before saving (same fields as `resource.save`).

```http
POST /api/resources/config.validate
Content-Type: application/json

{
  "category": "provider",
  "type": "mcp_server",
  "name": "My MCP Server",
  "config": {
    "sse_endpoint": "http://localhost:8007/mcp"
  },
  "timeoutSeconds": 10.0
}
```

**Response:** `ElementValidationResult` (with `element_rid: "inline"`)

### Validate Saved Blueprint

```http
POST /api/blueprints/blueprint.validate
Content-Type: application/json

{
  "blueprintId": "bp123",
  "timeoutSeconds": 10.0
}
```

**Response:** `BlueprintValidationResult`

### Validate Draft (Pre-save Blueprint)

Validates a blueprint draft before saving.

```http
POST /api/blueprints/draft.validate
Content-Type: application/json

{
  "draft": {
    "name": "My Blueprint",
    "nodes": [...],
    "llms": [...]
  },
  "timeoutSeconds": 10.0
}
```

**Response:** `BlueprintValidationResult` (with `blueprint_id: "draft"`)

---

## Design Principles

### SOLID Principles Applied

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SOLID PRINCIPLES                                    │
└─────────────────────────────────────────────────────────────────────────────┘

  S - Single Responsibility
  ─────────────────────────
  • ElementValidationService: Only orchestrates validation
  • DependencyResolver: Only resolves dependency order
  • BlueprintConfigCollector: Only collects configs from blueprints
  • Validators: Only validate their specific element type

  O - Open/Closed
  ────────────────
  • New element types can add validators without modifying existing code
  • Just subclass BaseElementValidator and set validator_cls on spec

  L - Liskov Substitution
  ───────────────────────
  • All validators are interchangeable via ElementValidator interface
  • Service treats all validators uniformly

  I - Interface Segregation
  ─────────────────────────
  • ElementValidator has single method: validate()
  • ValidationContext is pure data, no methods that aren't needed

  D - Dependency Inversion
  ────────────────────────
  • Validators depend on abstractions (ValidationContext), not services
  • Service depends on ElementValidator interface, not concrete validators
```

### Key Design Decisions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       KEY DESIGN DECISIONS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

  1. ValidatorReport vs ElementValidationResult
     ─────────────────────────────────────────
     Validators return ValidatorReport (pure findings).
     Service adds metadata (rid, type, name) to create ElementValidationResult.
     
     WHY: Validators don't know their "identity" (rid, name).
          That metadata comes from the calling context (ResourcesService,
          BlueprintService, etc.)

  2. Synchronous validate() with internal async
     ──────────────────────────────────────────
     validate() method is synchronous.
     Validators use AsyncBridge internally for network calls.
     
     WHY: Keeps the service simple and synchronous.
          Async complexity is encapsulated in validators.

  3. Pre-resolved dependency results in context
     ──────────────────────────────────────────
     Validators receive pre-computed dependency results via context.
     They don't call back to services to validate dependencies.
     
     WHY: Avoids circular dependencies.
          Keeps validators pure and testable.
          Service controls validation order.

  4. Elements own their validation contract
     ─────────────────────────────────────
     ElementValidator interface lives in elements/common/validator.py
     
     WHY: Elements define how they validate themselves.
          validation/service.py imports from elements/, not vice versa.
          Semantically correct: elements own their behavior.
```

---

## Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              QUICK REFERENCE                                │
└─────────────────────────────────────────────────────────────────────────────┘

  To validate a saved resource:
    ResourcesService.validate_resource(rid)

  To validate a saved blueprint:
    BlueprintService.validate_blueprint(blueprint_id)

  To create a new validator:
    1. Subclass BaseElementValidator
    2. Override validate() → ValidatorReport
    3. Set validator_cls on your element's spec

  Key classes:
    • ElementValidator         - Abstract interface
    • BaseElementValidator     - Base class with utilities
    • ValidatorReport          - What validators return
    • ElementValidationResult  - Final result for API
    • ValidationContext        - Settings + dependency results
    • ElementValidationService - Orchestrator
    • ConfigMeta               - Metadata for validation

  Validation order:
    Dependencies are validated BEFORE dependents (topological sort)
    Later validators can see earlier results via context
```

