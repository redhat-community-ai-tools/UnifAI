// Package unifai is a thin client for the UnifAI multiagent (MAS) and RAG REST APIs.
//
// In-cluster calls authenticate with the X-Authenticated-User header, which the services accept without a session
// from callers that also send the shared secret in X-Internal-Auth (older images ignore it; the stack restricts who
// can reach them with a NetworkPolicy).
package unifai

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

const (
	// MASPort and RAGPort are the service ports of the stack.
	MASPort = 8003
	RAGPort = 13456
)

// IdentityPort is the port of the identity Service.
const IdentityPort = 13456

// IdentityEndpoint returns the identity API base URL of the stack running in namespace (its Service: the public
// Route strips X-Internal-Auth).
func IdentityEndpoint(namespace string) string {
	return fmt.Sprintf("http://identity.%s.svc:%d", namespace, IdentityPort)
}

// Endpoints returns the MAS and RAG base URLs of the stack running in namespace.
func Endpoints(namespace string) (mas, rag string) {
	return fmt.Sprintf("http://unifai-multiagent-be.%s.svc:%d", namespace, MASPort),
		fmt.Sprintf("http://unifai-rag-server.%s.svc:%d", namespace, RAGPort)
}

// APIError is a non-2xx answer.
type APIError struct {
	Status int
	Body   string
}

func (e *APIError) Error() string { return fmt.Sprintf("HTTP %d: %s", e.Status, Truncate(e.Body, 400)) }

// IsStatus reports whether err is an APIError with one of the given statuses.
func IsStatus(err error, statuses ...int) bool {
	ae, ok := err.(*APIError)
	if !ok {
		return false
	}
	for _, s := range statuses {
		if ae.Status == s {
			return true
		}
	}
	return false
}

// Client calls one UnifAI service as one user (and optionally one team workspace).
type Client struct {
	Base   string
	User   string
	TeamID string
	// InternalAuth is the stack's INTERNAL_AUTH_SECRET, sent in X-Internal-Auth ("" = not sent).
	InternalAuth string
	HTTP         *http.Client
	// Err, when set, is returned by every call (e.g. the team workspace of the object is not resolved yet).
	Err error
}

// DefaultUser is the identity used when a spec names no owner.
const DefaultUser = "admin"

// New returns a client with a default timeout.
func New(base, user, teamID string) *Client {
	if user == "" {
		user = DefaultUser
	}
	return &Client{Base: strings.TrimRight(base, "/"), User: user, TeamID: teamID, HTTP: &http.Client{Timeout: 60 * time.Second}}
}

// Call sends a request; body is JSON-encoded when not nil; out (if not nil) receives the JSON answer.
func (c *Client) Call(ctx context.Context, method, path string, params url.Values, body, out any) error {
	if c.Err != nil {
		return c.Err
	}
	if params == nil {
		params = url.Values{}
	}
	if c.TeamID != "" && params.Get("teamId") == "" {
		params.Set("teamId", c.TeamID)
	}
	u := c.Base + path
	if len(params) > 0 {
		u += "?" + params.Encode()
	}
	var rd io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return err
		}
		rd = bytes.NewReader(b)
	}
	req, err := http.NewRequestWithContext(ctx, method, u, rd)
	if err != nil {
		return err
	}
	req.Header.Set("X-Authenticated-User", c.User)
	if c.InternalAuth != "" {
		req.Header.Set("X-Internal-Auth", c.InternalAuth)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := c.HTTP.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close() //nolint:errcheck
	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}
	if resp.StatusCode < 200 || resp.StatusCode > 299 {
		return &APIError{Status: resp.StatusCode, Body: string(data)}
	}
	if out != nil && len(data) > 0 {
		if err := json.Unmarshal(data, out); err != nil {
			return fmt.Errorf("decoding %s %s: %w", method, path, err)
		}
	}
	return nil
}

// Resource is a row of the UnifAI `resources` collection.
type Resource struct {
	RID      string         `json:"rid"`
	Name     string         `json:"name"`
	Type     string         `json:"type"`
	Category string         `json:"category"`
	Config   map[string]any `json:"cfg_dict"`
}

// ListResources lists the caller's resources of a category.
func (c *Client) ListResources(ctx context.Context, category string) ([]Resource, error) {
	var out struct {
		Resources []Resource `json:"resources"`
	}
	err := c.Call(ctx, http.MethodGet, "/api/resources/resources.list", url.Values{"category": {category}, "limit": {"200"}}, nil, &out)
	return out.Resources, err
}

// BlueprintSummary is an entry of available.blueprints.summary.get.
type BlueprintSummary struct {
	ID   string `json:"blueprint_id"`
	Name string `json:"name"`
}

// FindBlueprint returns the id of the caller's blueprint named name, or "".
func (c *Client) FindBlueprint(ctx context.Context, name string) (string, error) {
	var out []BlueprintSummary
	if err := c.Call(ctx, http.MethodGet, "/api/blueprints/available.blueprints.summary.get", nil, nil, &out); err != nil {
		return "", err
	}
	for _, b := range out {
		if b.Name == name {
			return b.ID, nil
		}
	}
	return "", nil
}

// Truncate shortens s to n bytes.
func Truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n]
}
