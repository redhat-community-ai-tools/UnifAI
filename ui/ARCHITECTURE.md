# UnifAI UI Architecture & Convention Documentation

## Table of Contents
1. [Overview](#overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Architecture Patterns](#architecture-patterns)
5. [Agentic AI System](#agentic-ai-system)
6. [Code Conventions](#code-conventions)
7. [API Integration](#api-integration)
8. [State Management](#state-management)
9. [Component Patterns](#component-patterns)
10. [Build & Deployment](#build--deployment)

---

## Overview

UnifAI UI is a modern React-based web application focused on **Agentic AI workflows**. The system allows users to create, configure, and execute multi-agent workflows using a visual graph builder interface with real-time streaming execution capabilities.

**Core Features:**
- Visual workflow builder with drag-and-drop graph canvas
- Real-time agent execution with streaming responses
- Chat-based interaction with AI agents
- Workspace resource management (nodes, LLMs, tools, providers, conditions)
- Multi-backend architecture (Data Pipeline Hub, Multi-Agent System, SSO)

---

## Technology Stack

### Core Framework
- **React 18.3.1** - UI framework
- **TypeScript 5.6.3** - Type safety
- **Vite 5.4.14** - Build tool and dev server
- **Wouter 3.3.5** - Lightweight routing (not React Router)

### UI Component Libraries
- **Radix UI** - Headless component primitives (dialogs, dropdowns, accordions, etc.)
- **shadcn/ui** - Pre-built accessible components built on Radix
- **Tailwind CSS 3.4.17** - Utility-first styling
- **Framer Motion 11.18.2** - Animation library

### State & Data Management
- **TanStack React Query 5.60.5** - Server state management
- **Zustand 4.5.4** - Client state management (pagination stores)
- **React Context API** - Global contexts (Auth, Theme, Notifications, Project, Shared)

### Graph & Visualization
- **ReactFlow 11.11.4** - Flow/graph visualization library for workflow builder
- **Recharts 2.15.2** - Chart library for dashboard visualizations

### Data Handling
- **Axios 1.9.0** - HTTP client
- **Oboe 2.1.7** - Streaming JSON parsing
- **js-yaml 4.1.0** - YAML parsing/generation for blueprints

### Form Management
- **React Hook Form 7.55.0** - Form state management
- **Zod 3.24.2** - Schema validation
- **@hookform/resolvers 3.10.0** - Form validation integration

### Package Management
- **PNPM 10.13.1** - Fast, disk-efficient package manager with lockfile (`pnpm-lock.yaml`)

---

## Project Structure

```
ui/
├── client/                          # Main application source
│   ├── public/                      # Static assets
│   │   └── guides/                  # Documentation guides
│   │       └── agentic-inventory/   # Agent inventory guides
│   ├── src/
│   │   ├── api/                     # API layer (dedicated modules per domain)
│   │   │   ├── activity.ts          # Activity feed API
│   │   │   ├── docs.ts              # Document management API
│   │   │   ├── pipelines.ts         # Pipeline operations API
│   │   │   ├── shares.ts            # Sharing/notification API
│   │   │   └── slack.ts             # Slack integration API
│   │   ├── components/              # React components
│   │   │   ├── agentic-ai/          # ⭐ CORE: Agentic AI system
│   │   │   │   ├── chat/            # Chat interface & streaming
│   │   │   │   ├── graphs/          # Graph builder components
│   │   │   │   ├── workspace/       # Workspace resource management
│   │   │   │   ├── AgentFlowGraph.tsx
│   │   │   │   ├── AvailableFlows.tsx
│   │   │   │   ├── ExecutionStream.tsx
│   │   │   │   ├── ExecutionTab.tsx
│   │   │   │   └── StreamingDataContext.tsx
│   │   │   ├── auth/                # Authentication components
│   │   │   ├── dashboard/           # Dashboard widgets
│   │   │   ├── guides/              # Guide renderer
│   │   │   ├── layout/              # Layout components (Header, Sidebar, StatusBar)
│   │   │   ├── shared/              # Shared/reusable components
│   │   │   │   └── stream/          # Streaming utilities
│   │   │   └── ui/                  # shadcn/ui primitives (40+ components)
│   │   ├── constants/               # Application constants
│   │   ├── contexts/                # React contexts (5 providers)
│   │   │   ├── AuthContext.tsx      # Authentication state
│   │   │   ├── NotificationContext.tsx  # Share notifications
│   │   │   ├── ProjectContext.tsx   # Project selection
│   │   │   ├── SharedContext.tsx    # Shared panel state
│   │   │   └── ThemeContext.tsx     # Theme management
│   │   ├── features/                # Feature-specific modules
│   │   │   ├── docs/                # Document upload/management
│   │   │   └── slack/               # Slack integration
│   │   ├── hooks/                   # Custom React hooks
│   │   │   ├── use-graph-logic.ts   # ⭐ Graph builder logic
│   │   │   ├── use-mobile.tsx       # Mobile detection
│   │   │   ├── use-toast.ts         # Toast notifications
│   │   │   └── use-workspace-data.ts  # ⭐ Workspace data management
│   │   ├── http/                    # HTTP clients
│   │   │   ├── authClient.ts        # API3 (SSO) client
│   │   │   ├── axiosAgentConfig.ts  # API2 (Multi-Agent) client
│   │   │   └── queryClient.ts       # TanStack Query config
│   │   ├── lib/                     # Utility libraries
│   │   │   └── utils.ts             # cn() helper for Tailwind
│   │   ├── pages/                   # Page components (routes)
│   │   │   ├── AgenticAI.tsx        # ⭐ Workflow configuration page
│   │   │   ├── AgenticChats.tsx     # ⭐ Chat/execution page
│   │   │   ├── AgentRepository.tsx  # Agent inventory
│   │   │   ├── Configuration.tsx    # Settings
│   │   │   ├── Dashboard.tsx        # Main dashboard
│   │   │   ├── JiraIntegration.tsx  # Jira setup
│   │   │   ├── SlackIntegration.tsx # Slack setup
│   │   │   └── not-found.tsx        # 404 page
│   │   ├── stores/                  # Zustand stores
│   │   │   └── usePaginationStore.tsx
│   │   ├── types/                   # TypeScript type definitions
│   │   │   ├── graph.ts             # Graph/workflow types
│   │   │   ├── index.ts             # General types
│   │   │   └── workspace.ts         # Workspace resource types
│   │   ├── utils/                   # Utility functions
│   │   ├── workspace/               # Workspace UI components
│   │   │   ├── BuildingBlocksSidebar.tsx
│   │   │   ├── NewGraph.tsx         # ⭐ Graph builder container
│   │   │   └── ResourceDetailsModal.tsx
│   │   ├── App.tsx                  # Root component with routing
│   │   ├── main.tsx                 # Application entry point
│   │   └── index.css                # Global styles
│   └── index.html                   # HTML entry point
├── deployment/                      # Docker & Nginx configs
├── node_modules/                    # Dependencies (gitignored)
├── package.json                     # Dependencies & scripts
├── pnpm-lock.yaml                   # ⚠️ CRITICAL: Lock file (must commit)
├── tsconfig.json                    # TypeScript configuration
├── tailwind.config.ts               # Tailwind configuration
├── vite.config.ts                   # Vite build & proxy config
├── postcss.config.js                # PostCSS config
└── theme.json                       # Theme customization
```

---

## Architecture Patterns

### 1. **Multi-Provider Context Architecture**

The application uses a **nested provider pattern** to manage global state:

```typescript
<ThemeProvider>
  <AuthProvider>
    <NotificationProvider>
      <SharedProvider>
        <ProjectProvider>
          <ProtectedRoute>
            {/* Application routes */}
          </ProtectedRoute>
        </ProjectProvider>
      </SharedProvider>
    </NotificationProvider>
  </AuthProvider>
</ThemeProvider>
```

**Context Responsibilities:**
- **ThemeProvider**: Dark/light mode management
- **AuthProvider**: User authentication, session handling
- **NotificationProvider**: Share invites, periodic polling (30s), notification counts
- **SharedProvider**: Shared panel visibility state
- **ProjectContext**: Current project selection (not fully implemented)

### 2. **Multi-Backend API Architecture**

The system communicates with **3 separate backends** via Vite proxy configuration:

| Proxy Path | Backend Service | Purpose | Port |
|------------|----------------|---------|----------|
| `/api1` | Data Pipeline Hub | Document/Slack pipelines, embeddings | Port 13457 |
| `/api2` | Multi-Agent System | Agentic workflows, sessions, blueprints | Port 8002 |
| `/api3` | SSO/Auth Service | Authentication, user management | Port 13456 |

**HTTP Client Configuration:**
```typescript
// api1 - RAG System (main application backend)
const axiosBEConfig = axios.create({
  baseURL: '/api1',
  timeout: 20000, // 20 seconds
  withCredentials: true, // Important: This ensures cookies are sent with requests
});

// api2 - Multi-Agent System (main agentic AI backend)
const axiosAgentConfig = axios.create({
  baseURL: '/api2',
  timeout: 300000  // 5 minutes for long-running workflows
});

// api3 - SSO Service
const authClient = axios.create({
  baseURL: '/api3',
  timeout: 20000,
  withCredentials: true  // Cookie-based auth
});
```

### 3. **Streaming Data Pattern**

Real-time execution streaming uses a **shared ref pattern** with forced updates:

```typescript
// StreamingDataContext.tsx
const StreamingDataProvider = ({ children }) => {
  const nodeListRef = useRef<Map<string, NodeEntry>>(new Map());
  const [, setTick] = useState(0);
  
  const forceUpdate = () => setTick(t => t + 1);
  const clearStream = () => {
    nodeListRef.current.clear();
    forceUpdate();
  };
  
  return <StreamingDataContext.Provider value={{ nodeListRef, forceUpdate, clearStream }}>
    {children}
  </StreamingDataContext.Provider>;
};
```

**Why this pattern?**
- Streaming data updates frequently (hundreds of updates/second)
- Using state would cause excessive re-renders
- Ref holds mutable data; `forceUpdate()` triggers UI refresh on demand

---

## Agentic AI System

### Overview

The **Agentic AI system** is the core feature, enabling users to build, validate, and execute multi-agent workflows.

### Key Components

#### 1. **Workflow Configuration (`AgenticAI.tsx` page)**

**Route:** `/agentic-ai` (also root `/`)

**Features:**
- Select pre-built workflows from available blueprints
- Load workflow into a new session
- Build custom workflows with graph builder

**Key Actions:**
```typescript
// Load workflow → creates session → redirects to AgenticChats
handleLoadFlow() {
  const session = await axios.post("/sessions/user.session.create", {
    blueprintId: selectedFlow.id,
    userId: user.username
  });
  window.location.href = "/agentic-chats";
}

// Build workflow → shows graph builder
handleBuildGraph() {
  setShowGraphBuilder(true);  // Renders <NewGraph />
}
```

#### 2. **Graph Builder (`NewGraph.tsx` + `use-graph-logic.ts`)**

**Architecture:** 3-panel layout
1. **Left Panel:** Building blocks sidebar (nodes, conditions)
2. **Center Panel:** ReactFlow canvas for visual workflow design
3. **Right Panel:** Real-time validation panel

**Core Hook: `use-graph-logic.ts`** (~1250 lines)

This custom hook manages the entire graph builder state machine:

**State Management:**
```typescript
const {
  nodes, edges,                    // ReactFlow state
  yamlFlow,                        // YAML representation (source of truth)
  buildingBlocksData,              // Available nodes (category=nodes)
  conditionsData,                  // Available conditions (category=conditions)
  allBlocksData,                   // All workspace resources
  isGraphValid,                    // Validation status
  validationResult,                // Validation errors/warnings
  
  // Actions
  onDrop,                          // Drag-and-drop handler
  onConnect,                       // Edge creation handler
  attachConditionToNode,           // Attach condition to node
  removeConditionFromNode,         // Remove condition
  saveGraph,                       // Save blueprint as YAML
  validateGraph,                   // Trigger validation
  clearGraph,                      // Reset to default nodes
  deleteEdge, deleteNode,          // Deletion handlers
} = useGraphLogic();
```

**Default Nodes:**
Every graph starts with 2 required nodes:
```typescript
const defaulYmlState = {
  nodes: [
    { rid: "user_question", name: "User Question Node", type: "user_question_node" },
    { rid: "final_answer", name: "Final Answer Node", type: "final_answer_node" }
  ],
  plan: [
    { uid: "user_input", node: "user_question" },
    { uid: "finalize", node: "final_answer" }
  ]
};
```

**YAML Flow Structure:**
```yaml
name: "Blueprint Name"
description: "Description"
nodes:
  - rid: $ref:resource_id      # Reference to workspace resource
    name: "Node Name"
    config: { ... }
conditions:                     # Optional conditional routers
  - rid: $ref:condition_id
    name: "Condition Name"
    type: router_boolean | router_direct
    config: { ... }
plan:                           # Execution plan (DAG)
  - uid: step_1                 # Unique step identifier
    node: resource_id           # Reference to node
    after: step_0               # Dependencies (string | string[] | null)
    exit_condition: condition_id  # Optional condition
    branches:                   # Conditional branches
      true: step_2
      false: step_3
```

**Node Categories:**
- **nodes**: Executable agent nodes (LLM agents, tools, etc.)
- **conditions**: Routing logic (boolean, direct routing)
- **llms**, **retrievers**, **tools**, **providers**: Supporting resources (referenced via `$ref`)

**Graph Validation:**

Real-time validation runs on every YAML flow change (debounced 100ms):

```typescript
const validateGraph = async () => {
  const yamlString = yaml.dump(yamlFlow);
  const response = await axios.post("/graph/validation/all.validate", yamlString, {
    headers: { "Content-Type": "text/plain" }
  });
  
  setValidationResult(response.data.validation_result);
  setIsGraphValid(response.data.validation_result?.is_valid || false);
};
```

**Validation prevents:**
- Orphaned nodes
- Circular dependencies
- Missing required connections
- Invalid condition configurations
- Type mismatches

**Save Workflow:**

Only valid graphs can be saved:

```typescript
const saveGraph = async (name, description) => {
  if (!isGraphValid) {
    toast({ title: "Cannot Save Invalid Graph", variant: "destructive" });
    return;
  }
  
  const yamlString = yaml.dump({ ...yamlFlow, name, description });
  await axios.post("/blueprints/blueprint.save", {
    blueprintRaw: yamlString,
    userId: USER_ID
  });
  
  window.location.href = "/agentic-ai";  // Force refresh
};
```

#### 3. **Execution & Chat (`AgenticChats.tsx` + `ExecutionTab.tsx`)**

**Route:** `/agentic-chats`

**Architecture:** Multi-panel interface with session management

**Features:**
- Chat-based interaction with agents
- Real-time streaming execution visualization
- Session history with persistence
- Blueprint graph visualization
- Work plan tracking (task delegation, execution status)

**Session Management:**

```typescript
// Create session (from blueprint)
POST /sessions/user.session.create
{ blueprintId, userId }
→ returns sessionId

// Load existing session
GET /sessions/session.state.get?sessionId={id}
→ returns { messages[], final_output, metadata }

// Execute session with streaming
POST /sessions/session.stream.run
{ sessionId, inputs: { user_prompt }, stream: true }
→ Server-Sent Events (SSE) stream
```

**Streaming Protocol:**

The system uses **SSE (Server-Sent Events)** with JSON chunks:

```typescript
interface StreamChunk {
  node: string;              // Node identifier
  display_name: string;      // Human-readable name
  type: 'llm_token' | 'complete' | 'tool_calling' | 'tool_result' | 'workplan_snapshot';
  chunk?: string;            // LLM token (for llm_token)
  tool?: string;             // Tool name
  args?: Record<string, any>; // Tool arguments
  output?: string;           // Tool result
  call_id?: string;          // Tool invocation ID
  
  // WorkPlan fields
  action?: 'loaded' | 'saved' | 'deleted';
  plan_id?: string;
  workplan?: WorkPlan;       // Full work plan structure
}
```

**Stream Processing:**

Custom `EnhancedStreamReader` (based on Oboe.js) parses JSON streaming:

```typescript
const reader = new EnhancedStreamReader(
  response.body,
  (chunk: StreamChunk) => {
    switch (chunk.type) {
      case 'llm_token':
        // Append token to current message
        appendToken(chunk.node, chunk.chunk);
        break;
      case 'tool_calling':
        // Register tool invocation
        registerTool(chunk.node, chunk.tool, chunk.args);
        break;
      case 'tool_result':
        // Update tool with result
        updateToolResult(chunk.call_id, chunk.output);
        break;
      case 'workplan_snapshot':
        // Update work plan
        updateWorkPlan(chunk.workplan);
        break;
      case 'complete':
        // Node execution complete
        markNodeComplete(chunk.node);
        break;
    }
  }
);
```

**Chat Interface Component:**

```typescript
<ChatInterface
  runId={currentSessionId}
  triggerExecution={handleExecute}
  initialMessages={sessionMessages}
  blueprintExists={true}
/>
```

**Key Features:**
- Markdown rendering (ReactMarkdown + remark-gfm + remark-breaks)
- Expandable stream logs (per-node execution details)
- Work plan visualization (task hierarchy, delegation chains)
- Auto-scroll to latest message
- Session persistence (messages saved in backend)

#### 4. **Workspace Resource Management**

**Hook: `use-workspace-data.ts`** (~410 lines)

Manages all workspace resources (nodes, conditions, LLMs, tools, etc.):

```typescript
const {
  categories,                  // Available element categories
  elementInstances,            // Instances of selected type
  elementSchema,               // JSON schema for forms
  
  // Fetchers
  fetchCategories,             // Get all categories
  fetchElementInstances,       // Get instances by category/type
  fetchElementSchema,          // Get schema for form generation
  fetchResourcesForCategory,   // Get resources for $ref dropdowns
  fetchResourceById,           // Get single resource details
  
  // Mutators
  saveElement,                 // Create/update resource
  deleteElement,               // Delete resource
} = useWorkspaceData();
```

**Resource API Pattern:**

All workspace resources use a unified Resources API:

```typescript
// List resources
GET /resources/resources.list?userId={id}&category={cat}&type={type}
→ { resources: ResourceInstance[], pagination: {...} }

// Get single resource
GET /resources/resource.get?resourceId={rid}
→ ResourceInstance

// Create resource
POST /resources/resource.save
{ userId, category, type, name, config }
→ { rid, version, created }

// Update resource
PUT /resources/resource.update
{ resourceId, name, config }
→ { rid, version, updated }

// Delete resource
DELETE /resources/resource.delete?resourceId={rid}
```

**Resource Schema Pattern:**

Dynamic form generation uses JSON Schema from catalog:

```typescript
GET /catalog/element.spec.get?category={cat}&type={type}
→ {
  category, type, description, tags,
  config_schema: {
    type: "object",
    properties: { ... },
    required: [ ... ],
    $defs: { ... }
  }
}
```

**Field Types:**
- **Primitives:** string, number, boolean
- **Enums:** Select dropdowns
- **$ref:** References to other resources (category-based lookup)
- **Arrays:** Multi-value inputs
- **Objects:** Nested field groups

**Element Categories Visibility:**

Elements can be marked as hidden using hints:

```typescript
interface ElementType {
  category: string;
  type: string;
  hints?: Array<{
    hint_type: string;  // "hidden"
    reason?: string;
  }>;
}

// Filter out hidden elements
const visibleElements = elements.filter(
  element => !element.hints?.some(hint => hint.hint_type === "hidden")
);
```

#### 5. **Conditional Routing**

**Condition Types:**
- **router_boolean**: True/false branching
- **router_direct**: Named output routing

**Attachment Pattern:**

Conditions are **attached to nodes**, not standalone:

```typescript
// Drag condition onto a node
onDrop(event) {
  const targetNode = findNodeAtPosition(position);
  if (targetNode) {
    attachConditionToNode(targetNode.id, conditionBlock);
  }
}

// Updates YAML flow
setYamlFlow(prev => ({
  ...prev,
  conditions: [...prev.conditions, { rid: `$ref:${conditionId}`, ... }],
  plan: prev.plan.map(step => 
    step.uid === nodeId 
      ? { ...step, exit_condition: conditionId }
      : step
  )
}));
```

**Conditional Edge Creation:**

When connecting from a node with a condition, modal prompts for branch selection:

```typescript
<ConditionalEdgeModal
  conditionType="router_boolean"
  existingBranches={["true"]}
  onConfirm={(branchConfig) => {
    createEdge({ branch: "false", target: targetNode });
  }}
/>
```

**Branch Mapping in YAML:**

```yaml
plan:
  - uid: decision_node
    node: some_agent
    exit_condition: boolean_router_rid
    branches:
      true: success_path_uid
      false: failure_path_uid
```

---

## Code Conventions

### File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Components | PascalCase.tsx | `AgentFlowGraph.tsx` |
| Hooks | camelCase.ts with `use-` prefix | `use-graph-logic.ts` |
| Contexts | PascalCase.tsx with `Context` suffix | `AuthContext.tsx` |
| Types | camelCase.ts | `graph.ts`, `workspace.ts` |
| Utils | camelCase.ts | `guideLoader.ts` |
| API modules | camelCase.ts | `activity.ts`, `pipelines.ts` |
| UI components (shadcn) | kebab-case.tsx | `alert-dialog.tsx`, `dropdown-menu.tsx` |

### Component Structure

**Standard component pattern:**

```typescript
import React, { useState, useEffect, useCallback } from "react";
import { ComponentProps } from "@/types";
import { useCustomHook } from "@/hooks/useCustomHook";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface MyComponentProps {
  title: string;
  onAction?: () => void;
  variant?: "default" | "destructive";
}

export default function MyComponent({ 
  title, 
  onAction, 
  variant = "default" 
}: MyComponentProps) {
  const [state, setState] = useState<StateType>(initialState);
  const { data, isLoading } = useCustomHook();
  
  const handleClick = useCallback(() => {
    // Handler logic
    onAction?.();
  }, [onAction]);
  
  useEffect(() => {
    // Side effects
  }, [dependencies]);
  
  if (isLoading) return <LoadingSpinner />;
  
  return (
    <div className={cn("base-classes", variant === "destructive" && "error-classes")}>
      <h1>{title}</h1>
      <Button onClick={handleClick}>Action</Button>
    </div>
  );
}
```

### Import Order

**Consistent import ordering:**

```typescript
// 1. React imports
import React, { useState, useEffect } from "react";

// 2. Third-party libraries
import { motion } from "framer-motion";
import axios from "axios";

// 3. Internal absolute imports (using @/ alias)
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { GraphNode } from "@/types/graph";

// 4. Relative imports
import { helper } from "./helpers";
import styles from "./styles.module.css";
```

### TypeScript Conventions

**Interface over Type for objects:**

```typescript
// ✅ Preferred for component props and data structures
interface UserProfile {
  id: string;
  name: string;
  email: string;
}

// ✅ Use type for unions, intersections, primitives
type Status = 'idle' | 'loading' | 'success' | 'error';
type ExtendedProfile = UserProfile & { permissions: string[] };
```

**Strict typing for API responses:**

```typescript
// Define backend response shape
interface SessionResponse {
  session_id: string;
  metadata: Record<string, any>;
  started_at: string;
}

// Transform to frontend type
interface SessionData {
  id: string;
  metadata: Record<string, any>;
  startedAt: Date;
}

const transformSession = (res: SessionResponse): SessionData => ({
  id: res.session_id,
  metadata: res.metadata,
  startedAt: new Date(res.started_at)
});
```

**Prop drilling avoidance:**

Use contexts for deeply nested shared state:

```typescript
// ❌ Avoid prop drilling
<Parent>
  <Child data={data} onUpdate={onUpdate}>
    <GrandChild data={data} onUpdate={onUpdate}>
      <GreatGrandChild data={data} onUpdate={onUpdate} />
    </GrandChild>
  </Child>
</Parent>

// ✅ Use context for shared state
const DataProvider = ({ children }) => {
  const [data, setData] = useState();
  return <DataContext.Provider value={{ data, setData }}>{children}</DataContext.Provider>;
};

<DataProvider>
  <Parent>
    <Child>
      <GrandChild>
        <GreatGrandChild />  {/* Uses useDataContext() internally */}
      </GrandChild>
    </Child>
  </Parent>
</DataProvider>
```

### Styling Conventions

**Tailwind utility classes:**

```typescript
// Use cn() helper for conditional classes
import { cn } from "@/lib/utils";

<div className={cn(
  "base-class",
  "another-base-class",
  isActive && "active-class",
  variant === "primary" && "primary-variant",
  className  // Allow external className override
)} />
```

**Custom Tailwind utilities:**

Defined in `tailwind.config.ts`:

```typescript
// Dark theme input styling
<input className="input-dark-theme" />

// Dark theme select styling
<select className="select-dark-theme" />

// Text color enforcement on focus
<input className="input-dark-theme-text-white" />
```

**Design tokens (CSS variables):**

```css
/* Defined in index.css */
:root {
  --background: ...;
  --foreground: ...;
  --primary: ...;
  --radius: 0.5rem;
}

/* Use in Tailwind */
bg-background
text-foreground
border-primary
rounded-lg  /* Uses var(--radius) */
```

### Error Handling

**Toast notifications for user feedback:**

```typescript
import { useToast } from "@/hooks/use-toast";

const { toast } = useToast();

try {
  await saveData();
  toast({
    title: "✅ Success",
    description: "Data saved successfully",
    variant: "default"
  });
} catch (error) {
  toast({
    title: "❌ Error",
    description: error.message || "Failed to save data",
    variant: "destructive"
  });
}
```

**Graceful degradation:**

```typescript
// Show loading state
if (isLoading) return <PageLoader />;

// Show error state with retry
if (error) return (
  <div>
    <p>Failed to load data</p>
    <Button onClick={retry}>Retry</Button>
  </div>
);

// Show empty state
if (data.length === 0) return <EmptyState />;

// Render data
return <DataList items={data} />;
```

---

## API Integration

### API Layer Structure

**Dedicated modules per domain in `/src/api/`:**

```
api/
├── activity.ts      # Activity feed
├── docs.ts          # Document management
├── pipelines.ts     # Pipeline operations
├── shares.ts        # Share invites
└── slack.ts         # Slack integration
```

**Pattern:**

```typescript
// api/pipelines.ts
import { api } from '@/http/queryClient';  // axios instance for api1

export interface ActivePipeline {
  id: string;
  source_name: string;
  status: string;
  // ...
}

export async function fetchActivePipelines(): Promise<ActivePipeline[]> {
  const [slackResponse, docsResponse] = await Promise.all([
    api.get("data_sources/data.sources.get", { params: { source_type: "slack" } }),
    api.get("data_sources/data.sources.get", { params: { source_type: "document" } })
  ]);
  
  return [...slackResponse.data.sources, ...docsResponse.data.sources];
}
```

### HTTP Client Selection

| Client | Import | Base URL | Use Case |
|--------|--------|----------|----------|
| `api` | `@/http/queryClient` | `/api1` (Data Pipeline) | Document/Slack pipelines |
| `axios` | `@/http/axiosAgentConfig` | `/api2` (Multi-Agent) | Agentic workflows, sessions |
| `api`/`apiAuth` | `@/http/authClient` | `/api3` (SSO) | Auth, user management |

**Client configuration differences:**

```typescript
// authClient (api3) - Cookie-based auth
api.interceptors.request.use((config) => {
  config.withCredentials = true;  // Send cookies
  return config;
});

api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      window.location.href = `${api.defaults.baseURL}/auth/login`;
    }
    return Promise.reject(error);
  }
);

// axiosAgentConfig (api2) - Long timeout for streaming
const axiosAgentConfig = axios.create({
  baseURL: '/api2',
  timeout: 300000  // 5 minutes (streaming can be slow)
});
```

### Endpoint Naming Convention

**Backend uses dot-notation:**

```
/resources/resources.list
/sessions/user.session.create
/blueprints/blueprint.save
/graph/validation/all.validate
/catalog/element.spec.get
```

### Request/Response Patterns

**GET with query params:**

```typescript
GET /resources/resources.list?userId={id}&category={cat}&type={type}
```

**POST with JSON body:**

```typescript
POST /sessions/user.session.create
{
  "blueprintId": "bp-123",
  "userId": "user-456"
}
```

**PUT for updates:**

```typescript
PUT /resources/resource.update
{
  "resourceId": "rid-789",
  "name": "Updated Name",
  "config": { ... }
}
```

**DELETE with query params:**

```typescript
DELETE /resources/resource.delete?resourceId={rid}
```

**Streaming endpoints:**

```typescript
POST /sessions/session.stream.run
{
  "sessionId": "sess-123",
  "inputs": { "user_prompt": "Hello" },
  "stream": true
}

→ Content-Type: text/event-stream
→ SSE format with JSON chunks
```

---

## State Management

### Context API (Global State)

**5 global contexts:**

1. **AuthContext** - User authentication
   ```typescript
   const { user, isAuthenticated, login, logout } = useAuth();
   ```

2. **ThemeContext** - Theme management
   ```typescript
   const { theme, setTheme } = useTheme();  // "dark" | "light" | "system"
   ```

3. **NotificationContext** - Share notifications
   ```typescript
   const { 
     receivedNotifications, 
     sentNotifications, 
     pendingNotificationsCount,
     sendNotification,
     acceptNotification,
     declineNotification 
   } = useNotifications();
   ```

4. **ProjectContext** - Project selection
   ```typescript
   const { currentProject, setCurrentProject, projects } = useProject();
   ```

5. **SharedContext** - Shared panel visibility
   ```typescript
   const { isSharedPanelOpen, toggleSharedPanel } = useShared();
   ```

### TanStack Query (Server State)

**Not currently used extensively**, but configured in `http/queryClient.ts` for future use.

**Potential usage:**

```typescript
import { useQuery } from '@tanstack/react-query';

const { data, isLoading, error } = useQuery({
  queryKey: ['blueprints', userId],
  queryFn: () => fetchBlueprints(userId),
  staleTime: 5 * 60 * 1000,  // 5 minutes
  refetchOnWindowFocus: false
});
```

### Zustand (Client State)

**Lightweight state management for specific features:**

```typescript
// stores/usePaginationStore.tsx
export const usePaginationStore = create<PaginationState>((set) => ({
  currentPage: 1,
  itemsPerPage: 10,
  setCurrentPage: (page) => set({ currentPage: page }),
  setItemsPerPage: (count) => set({ itemsPerPage: count })
}));

// Usage
const { currentPage, setCurrentPage } = usePaginationStore();
```

### Custom Hooks (Encapsulated Logic)

**Major custom hooks:**

1. **`use-graph-logic.ts`** - Graph builder state machine (~1250 lines)
2. **`use-workspace-data.ts`** - Workspace resource management (~410 lines)
3. **`use-toast.ts`** - Toast notification system
4. **`use-mobile.tsx`** - Mobile detection

**Hook pattern:**

```typescript
export const useCustomFeature = () => {
  const [state, setState] = useState();
  const { user } = useAuth();
  
  const fetchData = useCallback(async () => {
    const response = await axios.get(`/endpoint?userId=${user.id}`);
    setState(response.data);
  }, [user.id]);
  
  useEffect(() => {
    fetchData();
  }, [fetchData]);
  
  return { state, refetch: fetchData };
};
```

---

## Component Patterns

### UI Component Library (shadcn/ui)

**40+ pre-built components in `/components/ui/`:**

| Category | Components |
|----------|-----------|
| **Feedback** | alert, alert-dialog, toast, toaster, progress, skeleton |
| **Overlays** | dialog, drawer, sheet, popover, hover-card, tooltip |
| **Forms** | input, textarea, select, checkbox, radio-group, switch, slider, calendar, form |
| **Data Display** | table, card, badge, avatar, separator, accordion, tabs |
| **Navigation** | breadcrumb, menubar, navigation-menu, dropdown-menu, context-menu, command |
| **Layout** | resizable, scroll-area, sidebar, aspect-ratio, collapsible |
| **Charts** | chart (Recharts wrapper) |

**Usage pattern:**

```typescript
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>
    <p>Content</p>
    <Button variant="destructive" size="sm">Delete</Button>
  </CardContent>
</Card>
```

**Customization via variants:**

Components use `class-variance-authority` (CVA) for variant props:

```typescript
// button.tsx
const buttonVariants = cva(
  "base-classes",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        destructive: "bg-destructive text-destructive-foreground",
        outline: "border border-input bg-background",
        ghost: "hover:bg-accent hover:text-accent-foreground"
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 px-3",
        lg: "h-11 px-8"
      }
    },
    defaultVariants: {
      variant: "default",
      size: "default"
    }
  }
);
```

### Animation Patterns (Framer Motion)

**Page transitions:**

```typescript
<motion.div
  initial={{ opacity: 0, y: 10 }}
  animate={{ opacity: 1, y: 0 }}
  transition={{ duration: 0.3 }}
>
  {/* Page content */}
</motion.div>
```

**List animations:**

```typescript
<AnimatePresence mode="wait">
  {items.map(item => (
    <motion.div
      key={item.id}
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.2 }}
    >
      {item.content}
    </motion.div>
  ))}
</AnimatePresence>
```

### Modal/Dialog Pattern

**Alert dialog for confirmations:**

```typescript
import { AlertDialog, AlertDialogTrigger, AlertDialogContent, AlertDialogHeader, AlertDialogTitle, AlertDialogDescription, AlertDialogFooter, AlertDialogCancel, AlertDialogAction } from "@/components/ui/alert-dialog";

<AlertDialog open={isOpen} onOpenChange={setIsOpen}>
  <AlertDialogContent>
    <AlertDialogHeader>
      <AlertDialogTitle>Are you sure?</AlertDialogTitle>
      <AlertDialogDescription>
        This action cannot be undone.
      </AlertDialogDescription>
    </AlertDialogHeader>
    <AlertDialogFooter>
      <AlertDialogCancel>Cancel</AlertDialogCancel>
      <AlertDialogAction onClick={handleConfirm}>Confirm</AlertDialogAction>
    </AlertDialogFooter>
  </AlertDialogContent>
</AlertDialog>
```

**Controlled dialog for forms:**

```typescript
<Dialog open={isOpen} onOpenChange={setIsOpen}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Edit Resource</DialogTitle>
    </DialogHeader>
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>
          Cancel
        </Button>
        <Button type="submit">Save</Button>
      </DialogFooter>
    </form>
  </DialogContent>
</Dialog>
```

### Table Pattern

**Using `@tanstack/react-table`:**

```typescript
import { useReactTable, getCoreRowModel, flexRender } from '@tanstack/react-table';

const table = useReactTable({
  data,
  columns,
  getCoreRowModel: getCoreRowModel(),
});

<table>
  <thead>
    {table.getHeaderGroups().map(headerGroup => (
      <tr key={headerGroup.id}>
        {headerGroup.headers.map(header => (
          <th key={header.id}>
            {flexRender(header.column.columnDef.header, header.getContext())}
          </th>
        ))}
      </tr>
    ))}
  </thead>
  <tbody>
    {table.getRowModel().rows.map(row => (
      <tr key={row.id}>
        {row.getVisibleCells().map(cell => (
          <td key={cell.id}>
            {flexRender(cell.column.columnDef.cell, cell.getContext())}
          </td>
        ))}
      </tr>
    ))}
  </tbody>
</table>
```

---

## Build & Deployment

### Development

**Prerequisites:**
```bash
# Install PNPM via corepack
npm install -g corepack
corepack enable
corepack prepare pnpm@latest --activate
```

**Install dependencies:**
```bash
pnpm install --frozen-lockfile
```

**Run dev server:**
```bash
pnpm start
# or
NODE_ENV=development vite serve
```

**Dev server runs on:** `http://localhost:5000`

**Vite proxy rewrites:**
- `/api1` → `http://127.0.0.1:13457/api` (Data Pipeline Hub)
- `/api2` → `http://10.46.254.131:8002/api` (Multi-Agent System)
- `/api3` → `http://127.0.0.1:13456/api` (SSO Service)

### Production Build

**Build:**
```bash
pnpm build
# or
NODE_ENV=production vite build
```

**Output:** `ui/build/`

**Build optimizations:**
- Code splitting (React vendor chunk, general vendor chunk, app code)
- Tree shaking (Vite/Rollup)
- Minification (esbuild)
- CSS extraction (Tailwind)

**Manual chunk configuration:**

```typescript
// vite.config.ts
build: {
  rollupOptions: {
    output: {
      manualChunks(id) {
        if (id.includes('node_modules') && id.includes('react')) {
          return 'react-vendor';
        }
        if (id.includes('node_modules')) {
          return 'vendor';
        }
      }
    }
  }
}
```

### Docker Deployment

**Dockerfile:** `deployment/Dockerfile`

**Nginx configuration:** `deployment/nginx.conf.template`

**Proxy mapping:**
```nginx
location /api1/ {
  proxy_pass http://datapipeline_backend:port/api/;
}

location /api2/ {
  proxy_pass http://multiagent_backend:port/api/;
}

location /api3/ {
  proxy_pass http://sso_backend:port/api/;
}

location / {
  root /usr/share/nginx/html;
  try_files $uri $uri/ /index.html;
}
```

### Lock File Management

**⚠️ CRITICAL RULE:**

The `pnpm-lock.yaml` file **MUST** be committed to version control.

**Workflow:**

1. **Adding new package:**
   ```bash
   # Update package.json
   pnpm add package-name
   
   # Verify build works
   pnpm build
   
   # Commit BOTH files
   git add package.json pnpm-lock.yaml
   git commit -m "Add package-name"
   ```

2. **Updating packages:**
   ```bash
   # Remove lock file
   rm pnpm-lock.yaml
   
   # Reinstall (generates new lock)
   pnpm install
   
   # Test thoroughly
   pnpm build
   
   # Commit updated lock file
   git add pnpm-lock.yaml
   git commit -m "Update dependencies"
   ```

3. **CI/CD builds:**
   ```bash
   # Always use frozen lockfile
   pnpm install --frozen-lockfile
   pnpm build
   ```

### Build Analysis

**Enable bundle analyzer (dev only):**

```bash
NODE_ENV=development pnpm build
```

This generates `bundle-report.html` with:
- Chunk sizes (raw, gzip, brotli)
- Dependency tree visualization
- Size optimization opportunities

---

## Path Aliases

**Configured in `tsconfig.json` and `vite.config.ts`:**

```typescript
"@/*": ["./client/src/*"]
"@shared/*": ["./shared/*"]
"@assets/*": ["./attached_assets/*"]
```

**Usage:**

```typescript
// ❌ Avoid relative imports
import { Button } from "../../../components/ui/button";

// ✅ Use path aliases
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { GraphNode } from "@/types/graph";
```

---

## Code Review Checklist

When reviewing PRs for the UI:

### General
- [ ] TypeScript types defined (no `any` unless justified)
- [ ] Import order follows convention (React → libraries → internal → relative)
- [ ] Path aliases used (`@/` instead of relative paths)
- [ ] Error handling with toast notifications
- [ ] Loading/empty states handled

### Components
- [ ] Props interface defined
- [ ] Default props provided where applicable
- [ ] Memoization used for expensive computations (`useMemo`, `useCallback`)
- [ ] Effects have dependency arrays
- [ ] Cleanup functions in effects (if needed)

### Styling
- [ ] Tailwind classes used (no inline styles unless dynamic)
- [ ] `cn()` helper used for conditional classes
- [ ] Responsive design considered (mobile, tablet, desktop)
- [ ] Dark mode support (uses CSS variables)

### Agentic AI Specific
- [ ] YAML flow updates maintain structure integrity
- [ ] Graph validation triggered on changes
- [ ] Streaming data uses `StreamingDataContext`
- [ ] Resources use workspace API (`useWorkspaceData`)
- [ ] Session management follows SSE pattern
- [ ] Conditions properly attached to nodes (not standalone)

### API Integration
- [ ] Correct HTTP client used (api1/api2/api3)
- [ ] Response types defined
- [ ] Error responses handled
- [ ] Loading states managed
- [ ] Timeouts appropriate for endpoint

### State Management
- [ ] Context used for global state (not prop drilling)
- [ ] Local state used for component-specific state
- [ ] Refs used for streaming/high-frequency updates
- [ ] State updates batched where possible

### Performance
- [ ] Large lists virtualized (if applicable)
- [ ] Images lazy-loaded
- [ ] Debouncing/throttling for rapid events
- [ ] Expensive computations memoized

### Accessibility
- [ ] Keyboard navigation supported
- [ ] ARIA labels on interactive elements
- [ ] Focus management in modals
- [ ] Color contrast meets standards

### Lock File
- [ ] If dependencies changed, `pnpm-lock.yaml` updated and committed
- [ ] Build verified after dependency changes

---

## Common Pitfalls & Solutions

### 1. **Proxy Configuration Issues**

**Problem:** API calls fail with CORS errors

**Solution:** Ensure Vite proxy is configured correctly in `vite.config.ts`:

```typescript
server: {
  proxy: {
    '/api2': {
      target: 'http://backend:8002',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api2/, '/api')
    }
  }
}
```

### 2. **Streaming Data Not Updating**

**Problem:** Stream data updates but UI doesn't re-render

**Solution:** Use `forceUpdate()` from `StreamingDataContext`:

```typescript
const { nodeListRef, forceUpdate } = useStreamingData();

nodeListRef.current.set(key, value);
forceUpdate();  // Trigger re-render
```

### 3. **Graph Validation Constantly Failing**

**Problem:** Graph appears valid but validation fails

**Solution:** Check YAML structure matches backend expectations:
- All nodes in `plan` have corresponding entries in `nodes` section
- `after` dependencies reference existing `uid` values
- Conditional branches reference valid step `uid` values
- `$ref:` prefix used for all resource references

### 4. **Lock File Conflicts**

**Problem:** Merge conflicts in `pnpm-lock.yaml`

**Solution:**
```bash
# Accept incoming changes
git checkout --theirs pnpm-lock.yaml

# Reinstall to regenerate
rm pnpm-lock.yaml
pnpm install

# Test build
pnpm build

# Commit new lock file
git add pnpm-lock.yaml
git commit -m "Resolve lock file conflicts"
```

### 5. **Condition Nodes Not Appearing**

**Problem:** Dragged condition doesn't attach to node

**Solution:** Ensure condition is dropped **directly on a node**, not on empty canvas:

```typescript
// Condition drop validation
if (isConditionNode) {
  const targetNode = findNodeAtPosition(dropPosition);
  if (!targetNode) {
    toast({ 
      title: "Invalid Drop", 
      description: "Drop condition onto an existing node" 
    });
    return;
  }
  attachConditionToNode(targetNode.id, condition);
}
```

---

## Future Enhancements (Reference for PRs)

### Planned Features

1. **TanStack Query Integration**
   - Replace manual API calls with React Query
   - Automatic caching, refetching, optimistic updates
   - Centralized loading/error states

2. **Graph Undo/Redo**
   - Command pattern for graph operations
   - History stack in `use-graph-logic`
   - Keyboard shortcuts (Ctrl+Z, Ctrl+Y)

3. **Collaborative Editing**
   - WebSocket-based real-time sync
   - Operational transformation for conflict resolution
   - User cursors and presence indicators

4. **Advanced Validation**
   - Client-side validation before backend call
   - Visual indicators on canvas for errors
   - Auto-fix suggestions (one-click apply)

5. **Blueprint Versioning**
   - Git-like version control for blueprints
   - Diff visualization
   - Rollback to previous versions

---

## Glossary

| Term | Definition |
|------|------------|
| **Blueprint** | A saved workflow definition (YAML format) that can be loaded and executed |
| **Session** | An active execution instance of a blueprint with chat history |
| **Resource** | A workspace entity (node, LLM, tool, retriever, provider, condition) |
| **RID** | Resource ID - unique identifier for workspace resources |
| **UID** | Unique step identifier in execution plan |
| **Condition** | Routing logic attached to nodes (router_boolean, router_direct) |
| **Plan** | Execution DAG (directed acyclic graph) defining step order and dependencies |
| **SSE** | Server-Sent Events - streaming protocol for real-time updates |
| **$ref** | Reference syntax in YAML for linking to resources (`$ref:resource_id`) |
| **WorkPlan** | Task hierarchy for agent delegation and execution tracking |

---

## Contact & Support

For questions about this architecture document or UI conventions:

1. **Architecture questions**: Review this document, check `README.md` in `/ui`
2. **Component usage**: Check shadcn/ui docs + `/components/ui` source
3. **API endpoints**: Review `/client/src/api` modules and backend API docs
4. **Build issues**: Check `vite.config.ts`, `package.json`, ensure lock file is current

---

**Document Version:** 1.0  
**Last Updated:** November 23, 2025  
**Maintainer:** UnifAI Development Team


