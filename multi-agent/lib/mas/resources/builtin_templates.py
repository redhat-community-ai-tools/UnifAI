"""
Built-in resource definitions seeded on application startup.

Each resource uses a deterministic `rid` so re-seeding is idempotent.
Admins can manage these via the admin UI; this file provides the initial set.

User-configurable fields are determined by ReadOnlyHint annotations on
each element's Pydantic config schema. Fields with ReadOnlyHint(read_only=False)
are user-configurable; all others are read-only for end users.

Resources default to visibility="draft"; admins toggle them to public
via the admin panel when ready.
"""
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.identity import Identity
from mas.resources.models import Resource


BUILTIN_RESOURCES = [
    Resource(
        rid="builtin-llm-openai-gpt4o",
        identity=Identity.system(),
        category=ResourceCategory.LLM,
        type="openai",
        name="GPT-4o",
        ownership=ResourceOwnership.BUILTIN,
        visibility=ResourceVisibility.DRAFT,
        cfg_dict={
            "model_name": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.7,
            "max_tokens": 4096,
            "verify_ssl": True,
        },
    ),
    Resource(
        rid="builtin-mcp-github",
        identity=Identity.system(),
        category=ResourceCategory.PROVIDER,
        type="mcp_server",
        name="GitHub MCP",
        ownership=ResourceOwnership.BUILTIN,
        visibility=ResourceVisibility.DRAFT,
        cfg_dict={
            "mcp_url": "https://mcp.github.com/sse",
            "transport_type": "streamable http",
            "auth_method": "access_token",
            "tool_names": [
                "get_repo",
                "list_issues",
                "create_issue",
                "search_code",
            ],
            "additional_headers": {},
        },
    ),
    Resource(
        rid="builtin-tool-webfetch",
        identity=Identity.system(),
        category=ResourceCategory.TOOL,
        type="web_fetch",
        name="Web Fetch",
        ownership=ResourceOwnership.BUILTIN,
        visibility=ResourceVisibility.DRAFT,
        cfg_dict={},
    ),
    Resource(
        rid="builtin-node-deep-agent",
        identity=Identity.system(),
        category=ResourceCategory.NODE,
        type="deep_agent_node",
        name="Research Assistant",
        ownership=ResourceOwnership.BUILTIN,
        visibility=ResourceVisibility.DRAFT,
        cfg_dict={
            "system_message": "You are a thorough research assistant.",
            "retries": 1,
        },
    ),
]
