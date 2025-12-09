from typing import Dict, Any
from core.enums import ResourceCategory
from core.models import ElementCard
from core.ref.models import Ref
from session.session_registry import SessionRegistry


class ElementCardBuilder:
    """
    Single responsibility: Transform RuntimeElements into ElementCards.
    
    Located in core as it's a cross-layer composition service used by:
    - Graph layer (for StepContext building)
    - Session layer (for introspection)
    - Engine layer (for runtime card access)
    
    Core layer placement follows SOLID principles:
    - Stable dependency direction (core <- session <- graph)
    - Single responsibility (card composition only)
    - Pure transformation service (no side effects)
    
    Skill Mapping:
    - Tools/MCP Tools → "skills"
    - Retriever → "capability"
    - LLM → excluded from skills
    - A2A Agent → shows agent_card as-is
    """

    # Category to skill name mapping
    _CATEGORY_SKILL_MAPPING = {
        ResourceCategory.TOOL: 'skills',      # Tools → skills (always plural)
        ResourceCategory.RETRIEVER: 'capability',  # Retriever → capability
        # LLM is excluded - don't add to skills
        # PROVIDER is handled specially - tools extracted as skills
    }

    def __init__(self, session_registry: SessionRegistry):
        self._session_registry = session_registry

    def build_card(self, category: ResourceCategory, rid: str, uid: str = None,
                   metadata: Any = None) -> ElementCard:
        """Build element card from runtime element."""
        runtime_element = self._session_registry.get_runtime_element(category, rid)
        
        # Check if this is an A2A agent - special handling
        if self._is_a2a_agent(runtime_element):
            return self._build_a2a_agent_card(runtime_element, uid or rid, category, metadata)
        
        # Use user-defined name from resource_spec if available, otherwise fallback to spec
        name = self._get_user_defined_name(runtime_element)
        
        # Build skills from config + session registry  
        skills = self._build_skills_from_config(runtime_element.config)

        return ElementCard(
            uid=uid or rid,
            category=category,
            type_key=runtime_element.spec.type_key,
            # Use user-defined name, keep description empty
            name=name,
            description="",  # Don't use spec description - keep empty
            capabilities=getattr(runtime_element.spec, 'capability_surface', set()),
            reads=set(runtime_element.spec.reads),
            writes=set(runtime_element.spec.writes),
            # Runtime info
            instance=runtime_element.instance,
            config=runtime_element.config,
            metadata=metadata,
            # Computed skills
            skills=skills
        )
    
    def _get_user_defined_name(self, runtime_element) -> str:
        """Get user-defined name from resource_spec, fallback to spec.name."""
        if runtime_element.resource_spec and hasattr(runtime_element.resource_spec, 'name'):
            return runtime_element.resource_spec.name
        return runtime_element.spec.name
    
    def _is_a2a_agent(self, runtime_element) -> bool:
        """Check if runtime element is an A2A agent node."""
        return (hasattr(runtime_element.spec, 'type_key') and 
                runtime_element.spec.type_key == 'a2a_agent_node')
    
    def _build_a2a_agent_card(self, runtime_element, uid: str, category: ResourceCategory,
                              metadata: Any) -> ElementCard:
        """
        Build A2A agent card - extract specific fields from agent_card.
        
        For A2A agents, we extract name, description, skills, and capabilities
        from the remote agent's card.
        """
        # Default to user-defined name
        name = self._get_user_defined_name(runtime_element)
        description = ""
        skills = {}
        a2a_capabilities = set()
        
        # Get agent_card from config if available
        agent_card = getattr(runtime_element.config, 'agent_card', None)
        
        if agent_card:
            agent_card_dict = self._format_agent_card(agent_card)
            # Extract name from agent_card (fallback to user-defined name)
            name = agent_card_dict.get('name', name)
            # Extract description from agent_card
            description = agent_card_dict.get('description', "")
            # Extract skills from agent_card
            if 'skills' in agent_card_dict and agent_card_dict['skills']:
                skills['skills'] = agent_card_dict['skills']
            # Extract capabilities from agent_card
            if 'capabilities' in agent_card_dict and agent_card_dict['capabilities']:
                a2a_capabilities = set(agent_card_dict['capabilities'])
        
        # Merge capabilities from spec and agent_card
        spec_capabilities = getattr(runtime_element.spec, 'capability_surface', set())
        
        return ElementCard(
            uid=uid,
            category=category,
            type_key=runtime_element.spec.type_key,
            name=name,
            description=description,
            capabilities=spec_capabilities | a2a_capabilities,
            reads=set(runtime_element.spec.reads),
            writes=set(runtime_element.spec.writes),
            instance=runtime_element.instance,
            config=runtime_element.config,
            metadata=metadata,
            skills=skills
        )
    
    def _format_agent_card(self, agent_card) -> Dict[str, Any]:
        """Format A2A AgentCard for display."""
        if hasattr(agent_card, 'model_dump'):
            return agent_card.model_dump()
        elif hasattr(agent_card, 'dict'):
            return agent_card.dict()
        return {'raw': str(agent_card)}

    def _build_skills_from_config(self, config) -> Dict[str, Any]:
        """Build skills by resolving config references through session registry."""
        skills = {}
        
        # Generic Ref resolution - find all Ref fields and resolve them
        self._resolve_ref_skills(config, skills)
        
        # Add non-ref config attributes
        self._add_config_skills(config, skills)

        return skills
    
    def _add_config_skills(self, config, skills: Dict[str, Any]) -> None:
        """Add system_message as agent configuration."""
        # Only extract system_message for agent configuration
        system_message = getattr(config, 'system_message', None)
        if system_message:
            skills['agent_configuration'] = system_message
        
    def _resolve_ref_skills(self, config, skills: Dict[str, Any]) -> None:
        """Generically resolve all Ref fields in config to skills organized by category."""
        
        for field_name, field_value in config.__dict__.items():
            if field_value is None:
                continue
                
            # Handle single Ref
            if isinstance(field_value, Ref):
                category = field_value.get_category()
                if category:
                    # Skip LLM - don't add to skills
                    if category == ResourceCategory.LLM:
                        continue
                    
                    # Special handling for providers - extract tools as skills
                    if category == ResourceCategory.PROVIDER:
                        provider_tools = self._extract_provider_tools(field_value)
                        if provider_tools:
                            # Add provider tools to skills list
                            if 'skills' not in skills:
                                skills['skills'] = []
                            skills['skills'].extend(provider_tools)
                        continue
                    
                    ref_skill = self._resolve_single_ref(field_value, category)
                    if ref_skill:
                        # Use mapped skill name or category value
                        skill_key = self._get_skill_key(category)
                        # For tools, append to skills list
                        if skill_key == 'skills':
                            if 'skills' not in skills:
                                skills['skills'] = []
                            skills['skills'].append(ref_skill)
                        else:
                            skills[skill_key] = ref_skill
            
            # Handle List of Refs
            elif isinstance(field_value, list) and field_value and isinstance(field_value[0], Ref):
                category = field_value[0].get_category()
                if category:
                    # Skip LLM - don't add to skills
                    if category == ResourceCategory.LLM:
                        continue
                    
                    # Special handling for providers - extract tools as skills
                    if category == ResourceCategory.PROVIDER:
                        for ref in field_value:
                            provider_tools = self._extract_provider_tools(ref)
                            if provider_tools:
                                if 'skills' not in skills:
                                    skills['skills'] = []
                                skills['skills'].extend(provider_tools)
                        continue
                    
                    ref_skills = []
                    for ref in field_value:
                        ref_skill = self._resolve_single_ref(ref, category)
                        if ref_skill:
                            ref_skills.append(ref_skill)
                    if ref_skills:
                        # Use mapped skill name (pluralize for lists)
                        skill_key = self._get_skill_key(category, plural=True)
                        # For tools, append to skills list
                        if skill_key == 'skills':
                            if 'skills' not in skills:
                                skills['skills'] = []
                            skills['skills'].extend(ref_skills)
                        else:
                            skills[skill_key] = ref_skills
    
    def _extract_provider_tools(self, ref: Ref) -> list:
        """Extract tools from a provider (e.g., MCP provider) as skills."""
        try:
            runtime_element = self._session_registry.get_runtime_element(
                ResourceCategory.PROVIDER, ref.ref
            )
            provider_instance = runtime_element.instance
            
            # Check if provider has get_tools method (like MCP provider)
            if hasattr(provider_instance, 'get_tools'):
                tools = provider_instance.get_tools()
                tool_skills = []
                for tool in tools:
                    # Only extract name, no description
                    tool_skill = {
                        'name': getattr(tool, 'name', str(tool)),
                    }
                    tool_skills.append(tool_skill)
                return tool_skills
            
            return []
        except (KeyError, AttributeError):
            return []
    
    def _get_skill_key(self, category: ResourceCategory, plural: bool = False) -> str:
        """Get skill key name for category."""
        base_key = self._CATEGORY_SKILL_MAPPING.get(category, category.value)
        # Handle pluralization for capability
        if plural and base_key == 'capability':
            return 'capabilities'
        return base_key
    
    def _resolve_single_ref(self, ref: Any, category: ResourceCategory) -> Dict[str, Any]:
        """Resolve a single Ref to skill metadata."""
        try:
            runtime_element = self._session_registry.get_runtime_element(category, ref.ref)
            # Use user-defined name if available
            name = self._get_user_defined_name(runtime_element)
            return {
                'name': name,
            }
        except (KeyError, AttributeError):
            return None
