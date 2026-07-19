from typing import Union, Annotated

from pydantic import Field

from mas.elements.sandboxes.openshell_sandbox.config import OpenShellSandboxConfig

SandboxSpec = Annotated[
    Union[
        OpenShellSandboxConfig,
    ],
    Field(discriminator="type"),
]
