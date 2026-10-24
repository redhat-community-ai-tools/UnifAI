package controller

// A2A delegation (an agent calling another agent) is refused until its contract ships (zuno WP-173): the
// caller's identity, the delegation limits and the approval across hops. The CRD enum refuses new standalone A2A
// agents at admission; these checks refuse the ones stored before, and the A2A nodes of free-form blueprints
// and template drafts, which CEL cannot read.

const a2aNodeType = "a2a_agent_node"

func a2aDisabled(what string) error {
	return permanent("%s: A2A delegation is disabled until its contract ships (user identity, delegation limits and approval across hops)", what)
}

// hasA2ANode reports whether a blueprint or draft (after the library nodes are expanded) holds an A2A node.
func hasA2ANode(v any) bool {
	switch t := v.(type) {
	case map[string]any:
		if s, _ := t["type"].(string); s == a2aNodeType {
			return true
		}
		for _, e := range t {
			if hasA2ANode(e) {
				return true
			}
		}
	case []any:
		for _, e := range t {
			if hasA2ANode(e) {
				return true
			}
		}
	}
	return false
}
