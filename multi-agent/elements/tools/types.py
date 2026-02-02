from typing import Union, Annotated
from pydantic import Field
from elements.tools.ssh_exec.config import SshExecToolConfig
from elements.tools.mcp_proxy.config import McpProxyToolConfig
from elements.tools.oc_exec.config import OcExecToolConfig

# Union type for backward compatibility with blueprints
ToolsSpec = Annotated[
    Union[
        SshExecToolConfig,
        McpProxyToolConfig,
        OcExecToolConfig
    ],
    Field(discriminator="type")
]
