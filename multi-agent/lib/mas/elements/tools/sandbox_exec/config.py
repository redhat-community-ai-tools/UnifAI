from typing import Literal

from pydantic import Field

from mas.elements.tools.common.base_config import BaseToolConfig
from mas.core.ref.models import ToolRef
from mas.core.field_hints import RefFilterHint, SecretHint
from .identifiers import Identifier


class SandboxExecToolConfig(BaseToolConfig):
    """Configuration for the sandbox execution tool.

    References an existing ssh_exec resource for VM access.
    Optionally clones a git repo; otherwise creates plain directories.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    ssh_tool_ref: ToolRef = Field(
        ...,
        description="Reference to an existing ssh_exec resource (the VM)",
        json_schema_extra=RefFilterHint(allowed_type="ssh_exec").to_hints(),
    )
    git_repo_url: str = Field(
        "",
        description="Git repository URL to clone (leave empty for plain directory mode)",
    )
    git_token: str = Field(
        "",
        description="Git access token for private repos",
        json_schema_extra=SecretHint(
            reason="Token credential should be masked",
            allow_reveal=False,
        ).to_hints(),
    )
    workspace_path: str = Field(
        "/home/lab-user",
        description="Base workspace directory on the VM",
    )
