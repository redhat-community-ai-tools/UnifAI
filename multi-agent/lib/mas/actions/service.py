from typing import List, Dict, Any, Optional, Set
from .registry.action_registry import ActionRegistry
from .common.base_action import BaseAction
from .common.action_models import ActionType
from mas.core.enums import ResourceCategory


class ActionsService:
    """
    Service layer for action operations.
    Provides high-level interface for action discovery and execution.
    """
    
    def __init__(self, action_registry: Optional[ActionRegistry] = None):
        self._registry = action_registry or ActionRegistry()
        self._instance_overrides: Dict[str, BaseAction] = {}

    def register_instance(self, action: BaseAction) -> None:
        """Register a pre-configured action instance that will be used
        instead of creating a new one from the class."""
        self._instance_overrides[action.uid] = action

    def get_action_by_uid(self, uid: str) -> Optional[BaseAction]:
        """Get action instance by UID.
        Returns a pre-configured instance if one was registered,
        otherwise creates a new one from the discovered class."""
        if uid in self._instance_overrides:
            return self._instance_overrides[uid]
        try:
            action_cls = self._registry.get_action(uid)
            return action_cls()
        except KeyError:
            return None
    
    def execute_action_sync(self, uid: str, input_data: Dict[str, Any], 
                           context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute action synchronously by UID."""
        action = self.get_action_by_uid(uid)
        if not action:
            raise ValueError(f"Action not found: {uid}")
        
        validated_input = action.validate_input(input_data)
        result = action.execute_sync(validated_input, context)
        return result.model_dump()
    
    def get_actions_metadata(self, 
                           action_type: Optional[ActionType] = None,
                           tags: Optional[Set[str]] = None,
                           category: Optional[str] = None,
                           element_type: Optional[str] = None,
                           action_type_str: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get metadata for actions matching criteria."""
        # Convert string action_type to enum if provided
        if action_type_str:
            try:
                action_type = ActionType(action_type_str.lower())
            except ValueError:
                raise ValueError(f"Invalid action type: {action_type_str}")
        
        # Convert tags list to set if provided
        if tags and isinstance(tags, list):
            tags = set(tags)
        
        actions = self._registry.search_actions(action_type, tags, category, element_type)
        return [action.get_metadata() for action in actions]
    
    def get_all_actions_metadata(self) -> List[Dict[str, Any]]:
        """Get metadata for all registered actions."""
        actions = self._registry.list_all_actions()
        return [action.get_metadata() for action in actions]
    
    def validate_action_input(self, uid: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate action input without executing."""
        action = self.get_action_by_uid(uid)
        if not action:
            raise ValueError(f"Action not found: {uid}")
        
        validated_input = action.validate_input(input_data)
        return validated_input.model_dump()
    
    def action_exists(self, uid: str) -> bool:
        """Check if an action exists by UID."""
        return self._registry.has_action(uid)
    
    def get_actions_by_type(self, action_type: ActionType) -> List[Dict[str, Any]]:
        """Get all actions of a specific type."""
        actions = self._registry.get_actions_by_type(action_type)
        return [action.get_metadata() for action in actions]
    
    def get_actions_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """Get all actions with a specific tag."""
        actions = self._registry.get_actions_by_tag(tag)
        return [action.get_metadata() for action in actions]
    
    def get_actions_for_element(self, category: str, element_type: str) -> List[Dict[str, Any]]:
        """Get all actions compatible with an element (category, type)."""
        actions = self._registry.get_actions_for_element(category, element_type)
        return [action.get_metadata() for action in actions]
    
    def get_actions_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all actions compatible with a category."""
        actions = self._registry.get_actions_by_category(category)
        return [action.get_metadata() for action in actions]
    
    def get_registry_stats(self) -> Dict[str, int]:
        """Get action registry statistics."""
        return self._registry.get_registry_stats()
    
    def auto_discover_actions(self) -> None:
        """Auto-discover and register all available actions."""
        self._registry.auto_discover()
