from .category_builder import CategoryBuilder, BlueprintSpec
from mas.core.enums import ResourceCategory


class SandboxBuilder(CategoryBuilder):
    """Builds sandbox instances from blueprint specs."""

    category = ResourceCategory.SANDBOX

    def _iter_specs(self, bp: BlueprintSpec):
        return bp.sandboxes
