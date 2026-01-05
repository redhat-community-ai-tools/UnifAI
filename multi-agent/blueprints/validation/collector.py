"""
blueprints/validation/collector.py

BlueprintConfigCollector - collects configs from resolved blueprints.
"""

from typing import List

from blueprints.models.blueprint import BlueprintSpec
from core.enums import ResourceCategory
from core.ref import RefWalker
from core.ref.models import Ref
from validation.models import ConfigMeta


class BlueprintConfigCollector:
    """
    Collects configs from a resolved BlueprintSpec for validation.
    
    Responsible for:
    - Iterating through all categories in the blueprint
    - Extracting config metadata for each element
    - Identifying dependency rids for each config
    """

    def collect(self, spec: BlueprintSpec) -> List[ConfigMeta]:
        """
        Collect all configs from a resolved blueprint.
        
        Args:
            spec: A fully resolved BlueprintSpec
            
        Returns:
            List of ConfigMeta for all elements in the blueprint
        """
        result: List[ConfigMeta] = []

        for category in ResourceCategory:
            elements = getattr(spec, category.value, [])
            for element in elements:
                # Extract rid as string
                rid = self._extract_rid(element.rid)
                
                # Extract ALL dependency rids (external + inline) for blueprint elements
                # Blueprints can have inline refs (bare IDs) that reference other elements
                # in the same blueprint, not just external refs to saved resources
                dep_rids = list(RefWalker.all_rids(element.config))
                
                result.append(ConfigMeta(
                    rid=rid,
                    category=category,
                    element_type=element.type,
                    config=element.config,
                    name=element.name,
                    dependency_rids=dep_rids,
                ))

        return result

    @staticmethod
    def _extract_rid(rid_obj) -> str:
        """Extract rid string from Ref or string."""
        if isinstance(rid_obj, Ref):
            return rid_obj.ref
        return str(rid_obj)

