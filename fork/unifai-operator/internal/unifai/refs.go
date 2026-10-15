package unifai

import (
	"context"
	"fmt"
	"regexp"
	"strings"
)

// KindCategory maps the reference kinds used in specs to UnifAI resource categories.
var KindCategory = map[string]string{
	"llm": "llms", "provider": "providers", "tool": "tools", "retriever": "retrievers",
	"sandbox": "sandboxes", "condition": "conditions", "agent": "nodes",
}

var refRE = regexp.MustCompile(`^\$(ref|rid):(llm|provider|tool|retriever|sandbox|condition|agent)/(.+)$`)

// NotFoundError means a referenced object does not exist (yet) in UnifAI.
type NotFoundError struct{ Kind, Name string }

func (e *NotFoundError) Error() string {
	return fmt.Sprintf("%s %q not found in UnifAI (not reconciled yet?)", e.Kind, e.Name)
}

// Resolver resolves `$ref:<kind>/<name>` to `$ref:<rid>` and `$rid:<kind>/<name>` to `<rid>`,
// caching one listing per category.
type Resolver struct {
	c     *Client
	cache map[string]map[string]Resource
}

// NewResolver returns a resolver for the client's identity.
func NewResolver(c *Client) *Resolver { return &Resolver{c: c, cache: map[string]map[string]Resource{}} }

func (r *Resolver) load(ctx context.Context, category string) (map[string]Resource, error) {
	if m, ok := r.cache[category]; ok {
		return m, nil
	}
	list, err := r.c.ListResources(ctx, category)
	if err != nil {
		return nil, err
	}
	m := map[string]Resource{}
	for _, res := range list {
		m[res.Name] = res
	}
	r.cache[category] = m
	return m, nil
}

// RID returns the id of the library resource kind/name.
func (r *Resolver) RID(ctx context.Context, kind, name string) (string, error) {
	m, err := r.load(ctx, KindCategory[kind])
	if err != nil {
		return "", err
	}
	res, ok := m[name]
	if !ok {
		return "", &NotFoundError{Kind: kind, Name: name}
	}
	return res.RID, nil
}

// Walk returns a copy of v with every reference string resolved.
func (r *Resolver) Walk(ctx context.Context, v any) (any, error) {
	switch t := v.(type) {
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, x := range t {
			y, err := r.Walk(ctx, x)
			if err != nil {
				return nil, err
			}
			out[k] = y
		}
		return out, nil
	case []any:
		out := make([]any, len(t))
		for i, x := range t {
			y, err := r.Walk(ctx, x)
			if err != nil {
				return nil, err
			}
			out[i] = y
		}
		return out, nil
	case string:
		m := refRE.FindStringSubmatch(t)
		if m == nil {
			return t, nil
		}
		rid, err := r.RID(ctx, m[2], m[3])
		if err != nil {
			return nil, err
		}
		if m[1] == "ref" {
			return "$ref:" + rid, nil
		}
		return rid, nil
	default:
		return v, nil
	}
}

// ExpandLibraryNodes fills blueprint entries `{rid: $ref:<rid>}` without config (nodes, conditions) with the library
// resource's config, which is how the UnifAI UI stores them.
func (r *Resolver) ExpandLibraryNodes(ctx context.Context, bp map[string]any) error {
	for _, cat := range []string{"nodes", "conditions"} {
		items, _ := bp[cat].([]any)
		if len(items) == 0 {
			continue
		}
		m, err := r.load(ctx, cat)
		if err != nil {
			return err
		}
		byRID := map[string]Resource{}
		for _, res := range m {
			byRID[res.RID] = res
		}
		for _, it := range items {
			item, ok := it.(map[string]any)
			if !ok {
				continue
			}
			rid, _ := item["rid"].(string)
			if !strings.HasPrefix(rid, "$ref:") || item["config"] != nil {
				continue
			}
			res, ok := byRID[strings.TrimPrefix(rid, "$ref:")]
			if !ok {
				continue
			}
			item["config"] = res.Config
			if _, ok := item["name"]; !ok {
				item["name"] = res.Name
			}
			if _, ok := item["type"]; !ok {
				item["type"] = nil
			}
		}
	}
	return nil
}

// SetPath sets value at a dotted path, creating intermediate maps.
func SetPath(m map[string]any, path string, value any) {
	parts := strings.Split(path, ".")
	for _, p := range parts[:len(parts)-1] {
		next, ok := m[p].(map[string]any)
		if !ok {
			next = map[string]any{}
			m[p] = next
		}
		m = next
	}
	m[parts[len(parts)-1]] = value
}
