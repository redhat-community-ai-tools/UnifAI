from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from ..config import SandboxExecToolConfig
from ..sandbox_exec_factory import SandboxExecToolFactory
from ..identifiers import Identifier, META
from ..validator import SandboxExecToolValidator
from mas.elements.tools.common.card_builder import ToolCardBuilder


class SandboxExecToolElementSpec(BaseElementSpec):
    """Element specification for Sandbox Exec Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = SandboxExecToolConfig
    factory_cls = SandboxExecToolFactory
    tags = META.tags
    validator_cls = SandboxExecToolValidator
    card_builder_cls = ToolCardBuilder
