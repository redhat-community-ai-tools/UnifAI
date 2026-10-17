// Package okf reads Zuno OKF agent bundles (ADR-0564): the `agents/<name>/` tree of Markdown files with YAML
// frontmatter that zuno-demo signs with its platform key. It is Zuno-specific and fork-only: only the
// UnifaiAgentBundle controller imports it.
package okf

import (
	"bytes"
	"fmt"
	"path"
	"sort"
	"strings"

	"sigs.k8s.io/yaml"
)

// Files is a bundle tree: relative slash-separated path -> content.
type Files map[string][]byte

// Bundle is the subset of an OKF agent bundle the operator maps onto UnifAI objects.
type Bundle struct {
	Name           string
	Title          string
	Description    string
	Status         string
	GraphShape     string
	PrimaryTask    string
	Classification Level
	RAGTopK        int
	AccessGroups   []string
	Tasks          []Task
	// Unmapped lists OKF content with no UnifAI equivalent, reported in the CR status instead of being dropped.
	Unmapped []string
}

// Task is one `tasks/<name>.md` of the bundle.
type Task struct {
	Name             string
	Title            string
	Body             string
	Prompt           string
	AllowedTools     []string
	AllowedKnowledge []string
	LiveReadTool     string
	PromptExamples   []string
}

type agentFrontmatter struct {
	Type        string `json:"type"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Zuno        struct {
		Name        string   `json:"name"`
		Status      string   `json:"status"`
		GraphShape  string   `json:"graph_shape"`
		PrimaryTask string   `json:"primary_task"`
		Tasks       []string `json:"tasks"`
		RAG         struct {
			TopK int `json:"top_k"`
		} `json:"rag"`
		Model struct {
			PreferredClassification string `json:"preferred_classification"`
		} `json:"model"`
		Access struct {
			Groups []string `json:"groups"`
		} `json:"access"`
		UI map[string]any `json:"ui"`
	} `json:"zuno"`
}

type taskFrontmatter struct {
	Type  string `json:"type"`
	Title string `json:"title"`
	Zuno  struct {
		AllowedTools     []string `json:"allowed_tools"`
		AllowedKnowledge []string `json:"allowed_knowledge"`
		LiveReadTool     string   `json:"live_read_tool"`
		PromptExamples   []string `json:"prompt_examples"`
	} `json:"zuno"`
}

// Supported graph shapes (ADR-0342) and how they are rendered.
const (
	ShapeRetrieveReasonRespond = "retrieve_reason_respond"
	ShapePlanDraftWrite        = "plan_draft_write"
)

// SplitFrontmatter returns the YAML frontmatter and the Markdown body of an OKF file.
func SplitFrontmatter(b []byte) (front, body []byte, err error) {
	s := bytes.ReplaceAll(b, []byte("\r\n"), []byte("\n"))
	if !bytes.HasPrefix(s, []byte("---\n")) {
		return nil, nil, fmt.Errorf("no YAML frontmatter")
	}
	rest := s[4:]
	end := bytes.Index(rest, []byte("\n---\n"))
	if end < 0 {
		if bytes.HasSuffix(rest, []byte("\n---")) {
			return rest[:len(rest)-4], nil, nil
		}
		return nil, nil, fmt.Errorf("unterminated YAML frontmatter")
	}
	return rest[:end], bytes.TrimSpace(rest[end+5:]), nil
}

// Parse reads the agent bundle. It fails on anything the mapping cannot honour safely: a missing
// agent.okf.md, a task named in zuno.tasks without its file, or an unknown classification.
func Parse(files Files) (*Bundle, error) {
	raw, ok := files["agent.okf.md"]
	if !ok {
		return nil, fmt.Errorf("bundle has no agent.okf.md")
	}
	front, _, err := SplitFrontmatter(raw)
	if err != nil {
		return nil, fmt.Errorf("agent.okf.md: %w", err)
	}
	var af agentFrontmatter
	if err := yaml.Unmarshal(front, &af); err != nil {
		return nil, fmt.Errorf("agent.okf.md frontmatter: %w", err)
	}
	if af.Type != "agent" {
		return nil, fmt.Errorf("agent.okf.md: type is %q, want agent", af.Type)
	}
	if af.Zuno.Name == "" {
		return nil, fmt.Errorf("agent.okf.md: zuno.name is required")
	}
	cls, err := ParseLevel(af.Zuno.Model.PreferredClassification)
	if err != nil {
		return nil, fmt.Errorf("agent.okf.md zuno.model.preferred_classification: %w", err)
	}
	b := &Bundle{
		Name: af.Zuno.Name, Title: af.Title, Description: strings.TrimSpace(af.Description),
		Status: af.Zuno.Status, GraphShape: af.Zuno.GraphShape, PrimaryTask: af.Zuno.PrimaryTask,
		Classification: cls, RAGTopK: af.Zuno.RAG.TopK, AccessGroups: af.Zuno.Access.Groups,
	}
	if b.GraphShape == "" {
		b.GraphShape = ShapeRetrieveReasonRespond
	}
	switch b.GraphShape {
	case ShapeRetrieveReasonRespond:
	case ShapePlanDraftWrite:
		b.Unmapped = append(b.Unmapped, "zuno.graph_shape plan_draft_write: rendered as one agent per task; the separate plan/draft/write stages are not reproduced")
	default:
		return nil, fmt.Errorf("agent.okf.md: unsupported zuno.graph_shape %q", b.GraphShape)
	}
	if len(af.Zuno.Tasks) == 0 {
		return nil, fmt.Errorf("agent.okf.md: zuno.tasks is empty")
	}
	if b.PrimaryTask == "" {
		b.PrimaryTask = af.Zuno.Tasks[0]
	}
	seen := map[string]bool{}
	for _, name := range af.Zuno.Tasks {
		if seen[name] {
			return nil, fmt.Errorf("agent.okf.md: task %q listed twice", name)
		}
		seen[name] = true
		t, err := parseTask(files, name)
		if err != nil {
			return nil, err
		}
		b.Tasks = append(b.Tasks, *t)
	}
	if !seen[b.PrimaryTask] {
		return nil, fmt.Errorf("agent.okf.md: primary_task %q is not in zuno.tasks", b.PrimaryTask)
	}
	if len(b.AccessGroups) > 0 {
		b.Unmapped = append(b.Unmapped, fmt.Sprintf("zuno.access.groups %v: agent entitlement is enforced by the gateways, not by UnifAI (ADR-0562)", b.AccessGroups))
	}
	if b.RAGTopK > 0 {
		b.Unmapped = append(b.Unmapped, fmt.Sprintf("zuno.rag.top_k %d: set on the referenced retriever, not per agent", b.RAGTopK))
	}
	if len(af.Zuno.UI) > 0 {
		b.Unmapped = append(b.Unmapped, "zuno.ui: tile presentation has no UnifAI equivalent")
	}
	for _, t := range b.Tasks {
		if len(t.AllowedTools) > 0 {
			b.Unmapped = append(b.Unmapped, fmt.Sprintf("tasks/%s allowed_tools %v: enforced by mcp-gateway, not filtered by UnifAI", t.Name, t.AllowedTools))
		}
		if len(t.PromptExamples) > 0 {
			b.Unmapped = append(b.Unmapped, fmt.Sprintf("tasks/%s prompt_examples: UI starters are not mapped", t.Name))
		}
	}
	return b, nil
}

func parseTask(files Files, name string) (*Task, error) {
	p := path.Join("tasks", name+".md")
	raw, ok := files[p]
	if !ok {
		return nil, fmt.Errorf("task %q is listed in zuno.tasks but %s is missing", name, p)
	}
	front, body, err := SplitFrontmatter(raw)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", p, err)
	}
	var tf taskFrontmatter
	if err := yaml.Unmarshal(front, &tf); err != nil {
		return nil, fmt.Errorf("%s frontmatter: %w", p, err)
	}
	if tf.Type != "task" {
		return nil, fmt.Errorf("%s: type is %q, want task", p, tf.Type)
	}
	t := &Task{
		Name: name, Title: tf.Title, Body: string(body),
		AllowedTools: tf.Zuno.AllowedTools, AllowedKnowledge: tf.Zuno.AllowedKnowledge,
		LiveReadTool: tf.Zuno.LiveReadTool, PromptExamples: tf.Zuno.PromptExamples,
	}
	if pr, ok := files[path.Join("prompts", name+".md")]; ok {
		_, pb, err := SplitFrontmatter(pr)
		if err != nil {
			return nil, fmt.Errorf("prompts/%s.md: %w", name, err)
		}
		t.Prompt = string(pb)
	}
	return t, nil
}

// SystemMessage is the task's system prompt: its prompts/<task>.md when present, else the agent description
// followed by the task body.
func (b *Bundle) SystemMessage(t Task) string {
	if strings.TrimSpace(t.Prompt) != "" {
		return t.Prompt
	}
	parts := []string{}
	if b.Description != "" {
		parts = append(parts, b.Description)
	}
	if t.Body != "" {
		parts = append(parts, t.Body)
	}
	return strings.Join(parts, "\n\n")
}

// SortedPaths returns the bundle paths in the order sign_okf_bundle.py hashes them.
func (f Files) SortedPaths() []string {
	ps := make([]string, 0, len(f))
	for p := range f {
		ps = append(ps, p)
	}
	sort.Slice(ps, func(i, j int) bool { return lessByParts(ps[i], ps[j]) })
	return ps
}
