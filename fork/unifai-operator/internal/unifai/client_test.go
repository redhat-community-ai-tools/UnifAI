package unifai

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
)

// library serves resources.list for a few categories and records every request.
type library struct {
	resources map[string][]Resource
	lists     map[string]int
	last      *http.Request
}

func (l *library) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	l.last = r
	switch r.URL.Path {
	case "/api/resources/resources.list":
		cat := r.URL.Query().Get("category")
		l.lists[cat]++
		_ = json.NewEncoder(w).Encode(map[string]any{"resources": l.resources[cat]})
	case "/api/fail":
		w.WriteHeader(http.StatusConflict)
		_, _ = w.Write([]byte(strings.Repeat("x", 1000)))
	default:
		w.WriteHeader(http.StatusNotFound)
	}
}

func newLibrary(t *testing.T) (*library, *Client) {
	t.Helper()
	l := &library{lists: map[string]int{}, resources: map[string][]Resource{
		"llms":       {{RID: "r-llm", Name: "gpt", Category: "llms"}},
		"nodes":      {{RID: "r-agent", Name: "helper", Category: "nodes", Config: map[string]any{"type": "custom_agent_node"}}},
		"conditions": {{RID: "r-cond", Name: "direct", Category: "conditions", Config: map[string]any{"type": "router_direct"}}},
	}}
	srv := httptest.NewServer(l)
	t.Cleanup(srv.Close)
	return l, New(srv.URL+"/", "", "team-1")
}

func TestCallSendsIdentityAndTeam(t *testing.T) {
	l, c := newLibrary(t)
	if c.User != DefaultUser {
		t.Fatalf("default user = %q, want admin", c.User)
	}
	if _, err := c.ListResources(context.Background(), "llms"); err != nil {
		t.Fatal(err)
	}
	if got := l.last.Header.Get("X-Authenticated-User"); got != DefaultUser {
		t.Errorf("X-Authenticated-User = %q", got)
	}
	if got := l.last.URL.Query().Get("teamId"); got != "team-1" {
		t.Errorf("teamId = %q", got)
	}
	if !strings.HasPrefix(l.last.URL.Path, "/api/") {
		t.Errorf("base URL trailing slash not trimmed: %s", l.last.URL.Path)
	}
}

func TestCallReturnsTruncatedAPIError(t *testing.T) {
	_, c := newLibrary(t)
	err := c.Call(context.Background(), http.MethodPost, "/api/fail", nil, map[string]any{"a": 1}, nil)
	var ae *APIError
	if !errors.As(err, &ae) || ae.Status != http.StatusConflict {
		t.Fatalf("err = %v, want APIError 409", err)
	}
	if !IsStatus(err, http.StatusNotFound, http.StatusConflict) || IsStatus(err, http.StatusNotFound) {
		t.Errorf("IsStatus does not match the status list")
	}
	if IsStatus(errors.New("plain"), http.StatusConflict) {
		t.Errorf("IsStatus matched a non-API error")
	}
	if n := len(err.Error()); n > 420 {
		t.Errorf("error message not truncated: %d bytes", n)
	}
}

func TestResolverWalk(t *testing.T) {
	l, c := newLibrary(t)
	r := NewResolver(c)
	in := map[string]any{
		"llm":   "$ref:llm/gpt",
		"plan":  []any{map[string]any{"node": "$rid:agent/helper"}, "literal"},
		"other": 3,
	}
	out, err := r.Walk(context.Background(), in)
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]any{
		"llm":   "$ref:r-llm",
		"plan":  []any{map[string]any{"node": "r-agent"}, "literal"},
		"other": 3,
	}
	if !reflect.DeepEqual(out, want) {
		t.Errorf("Walk = %#v, want %#v", out, want)
	}
	if in["llm"] != "$ref:llm/gpt" {
		t.Errorf("Walk modified its input")
	}
	if _, err := r.RID(context.Background(), "llm", "gpt"); err != nil || l.lists["llms"] != 1 {
		t.Errorf("category listed %d times, want 1 (cached)", l.lists["llms"])
	}
	_, err = r.Walk(context.Background(), "$ref:tool/missing")
	var nf *NotFoundError
	if !errors.As(err, &nf) || nf.Kind != "tool" || nf.Name != "missing" {
		t.Errorf("err = %v, want NotFoundError tool/missing", err)
	}
	if s, _ := r.Walk(context.Background(), "$ref:unknown/x"); s != "$ref:unknown/x" {
		t.Errorf("unknown kind should be left as is, got %v", s)
	}
}

func TestExpandLibraryNodes(t *testing.T) {
	_, c := newLibrary(t)
	bp := map[string]any{
		"nodes": []any{
			map[string]any{"rid": "$ref:r-agent"},
			map[string]any{"rid": "$ref:r-agent", "name": "kept", "config": map[string]any{"x": 1}},
			map[string]any{"rid": "user_question"},
		},
		"conditions": []any{map[string]any{"rid": "$ref:r-cond"}},
	}
	if err := NewResolver(c).ExpandLibraryNodes(context.Background(), bp); err != nil {
		t.Fatal(err)
	}
	nodes := bp["nodes"].([]any)
	first := nodes[0].(map[string]any)
	if first["name"] != "helper" || first["config"].(map[string]any)["type"] != "custom_agent_node" {
		t.Errorf("library node not expanded: %#v", first)
	}
	if v, ok := first["type"]; !ok || v != nil {
		t.Errorf("expanded node should carry type=nil like the UI, got %#v", first["type"])
	}
	if second := nodes[1].(map[string]any); second["name"] != "kept" || second["config"].(map[string]any)["x"] != 1 {
		t.Errorf("node with a config was changed: %#v", second)
	}
	if third := nodes[2].(map[string]any); len(third) != 1 {
		t.Errorf("built-in node was changed: %#v", third)
	}
	if cond := bp["conditions"].([]any)[0].(map[string]any); cond["name"] != "direct" {
		t.Errorf("condition not expanded: %#v", cond)
	}
}

func TestSetPath(t *testing.T) {
	m := map[string]any{"headers": "not a map"}
	SetPath(m, "headers.token", "t")
	SetPath(m, "api_key", "k")
	want := map[string]any{"headers": map[string]any{"token": "t"}, "api_key": "k"}
	if !reflect.DeepEqual(m, want) {
		t.Errorf("SetPath = %#v, want %#v", m, want)
	}
}
