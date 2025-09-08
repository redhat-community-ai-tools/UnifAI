"""
Validation components for tool execution.

This module provides argument validation using the existing validation
function from global_utils.
"""
from typing import Dict, Optional, Any, Tuple, List

from elements.tools.common.base_tool import BaseTool
from global_utils.utils.util import validate_arguments
from .interfaces import ExecutionValidator
from .exceptions import ValidationError



class ArgumentValidator(ExecutionValidator):
    """Validates tool arguments against schema using global_utils validation."""
    
    def __init__(self, strict: bool = True):
        self.strict = strict
        self.name = "ArgumentValidator"
    
    async def validate(
        self,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate arguments against tool schema."""
        try:
            if getattr(tool, "args_schema", None):
                validate_arguments(schema=tool.get_args_schema_json(), args=args)
            elif self.strict:
                return False, f"Tool {tool.name} has no argument schema"
            
            return True, None
            
        except ValueError as e:
            return False, str(e)
        except Exception as e:
            print(f"Validation error for {tool.name}: {e}")
            return False, f"Validation error: {e}"


class CompositeValidator(ExecutionValidator):
    """Combines multiple validators."""
    
    def __init__(self, validators: List[ExecutionValidator], fail_fast: bool = True):
        self.validators = validators
        self.fail_fast = fail_fast
        self.name = "CompositeValidator"
    
    async def validate(
        self,
        tool: BaseTool,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str]]:
        """Run all validators."""
        errors = []
        
        for validator in self.validators:
            try:
                is_valid, error_msg = await validator.validate(tool, args, context)
                if not is_valid:
                    if self.fail_fast:
                        return False, error_msg
                    else:
                        errors.append(f"{getattr(validator, 'name', 'Unknown')}: {error_msg}")
            except Exception as e:
                error_msg = f"Validator {getattr(validator, 'name', 'Unknown')} failed: {e}"
                if self.fail_fast:
                    return False, error_msg
                else:
                    errors.append(error_msg)
        
        if errors:
            return False, "; ".join(errors)
        
        return True, None
