from typing import Union, Annotated
from pydantic import Field
from mas.elements.tools.ssh_exec.config import SshExecToolConfig
from mas.elements.tools.mcp_proxy.config import McpProxyToolConfig
from mas.elements.tools.oc_exec.config import OcExecToolConfig
from mas.elements.tools.web_fetch.config import WebFetchToolConfig

ToolsSpec = Annotated[
    Union[
        SshExecToolConfig,
        McpProxyToolConfig,
        OcExecToolConfig,
        WebFetchToolConfig,
    ],
    Field(discriminator="type")
]
