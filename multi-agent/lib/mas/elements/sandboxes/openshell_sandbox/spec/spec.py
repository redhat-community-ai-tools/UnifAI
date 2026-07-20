from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import OpenShellSandboxConfig
from ..openshell_sandbox_factory import OpenShellSandboxFactory
from ..identifiers import Identifier, META
from ..validator import OpenShellSandboxValidator
from mas.elements.sandboxes.common.card_builder import SandboxCardBuilder


class OpenShellSandboxElementSpec(BaseElementSpec):
    """Element specification for OpenShell Sandbox."""

    category = ResourceCategory.SANDBOX
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OpenShellSandboxConfig
    factory_cls = OpenShellSandboxFactory
    tags = META.tags
    validator_cls = OpenShellSandboxValidator
    card_builder_cls = SandboxCardBuilder
