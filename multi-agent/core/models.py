from dataclasses import dataclass
from typing import Any, Dict, Set
from core.enums import ResourceCategory


@dataclass(frozen=True)
class ElementCard:
    """
    Runtime element card: Complete view of an element for node communication.
    
    Cross-cutting data structure used by graph, session, and engine layers.
    Represents the composition of static spec info + runtime element data.
    """
    # Identity
    uid: str
    category: ResourceCategory
    type_key: str
    
    # Static info (from spec)
    name: str
    description: str
    capabilities: Set[str]
    reads: Set[str]
    writes: Set[str]
    
    # Runtime info
    instance: Any
    config: Any

    # Computed skills
    skills: Dict[str, Any]

    # StepMeta for graph context
    metadata: Any = None
    
    def __repr__(self) -> str:
        """Clean, LLM-friendly representation of the element card."""
        lines = []
        lines.append(f"Name: {self.name}")
        lines.append(f"UID: {self.uid}")
        
        # Only show description if not empty
        if self.description:
            lines.append(f"Description: {self.description}")
        
        # Capabilities
        if self.capabilities:
            lines.append(f"Capabilities: {', '.join(sorted(self.capabilities))}")
        
        # Skills (what this node can actually do)
        if self.skills:
            for skill_type, skill_data in self.skills.items():
                if skill_type == 'agent_configuration':
                    # Truncate system message and show in quotes
                    truncated = self._truncate_text(skill_data, max_length=100)
                    lines.append(f"Agent Configuration: \"{truncated}\"")
                elif skill_type == 'agent_card':
                    # Special handling for A2A agent cards - show as-is
                    lines.append(f"Agent Card: {self._format_agent_card(skill_data)}")
                elif skill_type == 'skills' and isinstance(skill_data, list):
                    # Show all skill data
                    lines.append("Skills:")
                    for skill in skill_data:
                        if isinstance(skill, dict):
                            lines.append(f"  - {self._format_skill(skill)}")
                        else:
                            lines.append(f"  - {skill}")
                elif skill_type == 'capability':
                    # Single capability
                    if isinstance(skill_data, dict) and 'name' in skill_data:
                        lines.append(f"Capability: {skill_data['name']}")
                    else:
                        lines.append(f"Capability: {skill_data}")
                elif skill_type == 'capabilities' and isinstance(skill_data, list):
                    # Multiple capabilities - just names
                    cap_names = [item.get('name', str(item)) if isinstance(item, dict) else str(item) for item in skill_data]
                    lines.append(f"Capabilities: {', '.join(cap_names)}")
        
        return "\n".join(lines)
    
    def _truncate_text(self, text: str, max_length: int = 100) -> str:
        """Truncate text to max length with ellipsis."""
        if not isinstance(text, str):
            text = str(text)
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def _format_skill(self, skill: Dict[str, Any]) -> str:
        """Format a single skill with all its data."""
        parts = []
        name = skill.get('name', 'Unknown')
        parts.append(name)
        
        # Add description if present
        description = skill.get('description', '')
        if description:
            truncated = self._truncate_text(description, max_length=150)
            parts.append(f": {truncated}")
        
        # Add other fields (excluding name and description)
        other_fields = {k: v for k, v in skill.items() if k not in ('name', 'description', 'id') and v}
        if other_fields:
            field_strs = [f"{k}={v}" for k, v in other_fields.items()]
            parts.append(f" ({', '.join(field_strs)})")
        
        return ''.join(parts)
    
    def _format_agent_card(self, agent_card: Dict[str, Any]) -> str:
        """Format agent card for display."""
        if isinstance(agent_card, dict):
            name = agent_card.get('name', 'Unknown')
            description = agent_card.get('description', '')
            skills = agent_card.get('skills', [])
            
            parts = [f"{name}"]
            if description:
                parts.append(f" - {description}")
            if skills:
                skill_names = [s.get('name', str(s)) if isinstance(s, dict) else str(s) for s in skills]
                parts.append(f" [Skills: {', '.join(skill_names)}]")
            return ''.join(parts)
        return str(agent_card)
    
    def _format_config(self, config: Dict[str, Any]) -> str:
        """Format config dict for readable display."""
        items = []
        for key, value in config.items():
            if isinstance(value, str) and len(value) > 1000:
                items.append(f"{key}='{value[:1000]}...'")
            else:
                items.append(f"{key}={repr(value)}")
        return "{" + ", ".join(items) + "}"