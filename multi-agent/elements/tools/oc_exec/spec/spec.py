from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from ..config import OcExecToolConfig
from ..oc_exec_factory import OcExecToolFactory
from ..identifiers import Identifier, META
from ..validator import OcExecToolValidator


class OcExecToolElementSpec(BaseElementSpec):
    """Element specification for OpenShift OC Exec Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OcExecToolConfig
    factory_cls = OcExecToolFactory
    tags = META.tags
    validator_cls = OcExecToolValidator
