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
	OKFVersion     string
	Title          string
	Description    string
	Status         string
	GraphShape     string
	PrimaryTask    string
	Classification Level
	RAGTopK        int
	AccessGroups   []string
	Maintainer     string
	// UI is the tile presentation (displayName, tileDescription, color, icon); string values only.
	UI map[string]string
	// DelegationTargets are the agents this agent may delegate to over A2A (zuno.delegation.targets, ADR-0401).
	DelegationTargets []DelegationTarget
	Tasks             []Task
	// Unmapped lists OKF content with no UnifAI equivalent, reported in the CR status instead of being dropped.
	Unmapped []string
}

// DelegationTarget is one task of another agent this agent may call over A2A.
type DelegationTarget struct {
	Agent string `json:"agent"`
	Task  string `json:"task"`
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
	// Skills are the instruction bodies of the task's skills (OKF v0.3, ADR-0579), in declaration order.
	Skills []Skill
	// Platform-enforced v0.3 settings, reported as unmapped.
	Models, Limits map[string]any
}

// Skill is one `skills/<name>.md` (or `skills/corp/<name>.md` for a corp skill) a task declares.
type Skill struct {
	Name string
	Body string
}

type agentFrontmatter struct {
	OKFVersion  string `json:"okf_version"`
	Type        string `json:"type"`
	Title       string `json:"title"`
	Description string `json:"description"`
	Provenance  struct {
		Maintainer string `json:"maintainer"`
	} `json:"provenance"`
	Zuno struct {
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
		UI         map[string]any `json:"ui"`
		Delegation struct {
			Targets []DelegationTarget `json:"targets"`
		} `json:"delegation"`
		// OKF v0.3 (ADR-0579): enforced by the platform (ai-gateway, quotas), not by UnifAI.
		Models     map[string]any `json:"models"`
		Guardrails map[string]any `json:"guardrails"`
		Limits     map[string]any `json:"limits"`
	} `json:"zuno"`
}

type taskFrontmatter struct {
	Type  string `json:"type"`
	Title string `json:"title"`
	Zuno  struct {
		AllowedTools     []string       `json:"allowed_tools"`
		AllowedKnowledge []string       `json:"allowed_knowledge"`
		LiveReadTool     string         `json:"live_read_tool"`
		PromptExamples   []string       `json:"prompt_examples"`
		Skills           []string       `json:"skills"`
		Models           map[string]any `json:"models"`
		Limits           map[string]any `json:"limits"`
	} `json:"zuno"`
}

type skillFrontmatter struct {
	Type string `json:"type"`
	Zuno struct {
		AllowedTools     []string `json:"allowed_tools"`
		AllowedKnowledge []string `json:"allowed_knowledge"`
	} `json:"zuno"`
}

// Graph shapes (ADR-0342). Only retrieve_reason_respond has a blueprint template today.
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
		Name: af.Zuno.Name, OKFVersion: af.OKFVersion, Title: af.Title, Description: strings.TrimSpace(af.Description),
		Status: af.Zuno.Status, GraphShape: af.Zuno.GraphShape, PrimaryTask: af.Zuno.PrimaryTask,
		Classification: cls, RAGTopK: af.Zuno.RAG.TopK, AccessGroups: af.Zuno.Access.Groups,
		Maintainer: strings.TrimSpace(af.Provenance.Maintainer), UI: stringValues(af.Zuno.UI),
		DelegationTargets: af.Zuno.Delegation.Targets,
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
	if b.RAGTopK > 0 {
		b.Unmapped = append(b.Unmapped, fmt.Sprintf("zuno.rag.top_k %d: set on the referenced retriever, not per agent", b.RAGTopK))
	}
	if len(af.Zuno.UI) > 0 {
		b.Unmapped = append(b.Unmapped, "zuno.ui: tile presentation is carried as the public sheet (status.display), not as a UnifAI tile")
	}
	if b.GraphShape == ShapePlanDraftWrite {
		b.Unmapped = append(b.Unmapped, "graph_shape plan_draft_write: three chained agents (plan, draft, write); the plan and write stages run without tools, the draft stage carries the retriever and the tools")
	}
	for _, kv := range []struct {
		field string
		v     map[string]any
	}{{"zuno.models", af.Zuno.Models}, {"zuno.guardrails", af.Zuno.Guardrails}, {"zuno.limits", af.Zuno.Limits}} {
		if len(kv.v) > 0 {
			b.Unmapped = append(b.Unmapped, kv.field+": enforced platform-side (ai-gateway, quotas), not by UnifAI")
		}
	}
	for _, t := range b.Tasks {
		if len(t.Models) > 0 || len(t.Limits) > 0 {
			b.Unmapped = append(b.Unmapped, fmt.Sprintf("tasks/%s models/limits: enforced platform-side (ai-gateway, quotas), not by UnifAI", t.Name))
		}
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
		Models: tf.Zuno.Models, Limits: tf.Zuno.Limits,
	}
	for _, ref := range tf.Zuno.Skills {
		sk, tools, knowledge, err := parseSkill(files, ref)
		if err != nil {
			return nil, fmt.Errorf("task %q: %w", name, err)
		}
		t.Skills = append(t.Skills, *sk)
		// What a skill declares is declared by the task that uses it: the ceilings must cover it.
		t.AllowedTools = appendMissing(t.AllowedTools, tools...)
		t.AllowedKnowledge = appendMissing(t.AllowedKnowledge, knowledge...)
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

// skillPath maps a task's skill reference to its file in the bundle: `<name>` is skills/<name>.md, `corp/<name>`
// is skills/corp/<name>.md (the corp skill is embedded in the agent artifact when it is built).
func skillPath(ref string) string { return path.Join("skills", ref+".md") }

func parseSkill(files Files, ref string) (*Skill, []string, []string, error) {
	p := skillPath(ref)
	raw, ok := files[p]
	if !ok {
		return nil, nil, nil, fmt.Errorf("skill %q is declared but %s is missing from the bundle", ref, p)
	}
	front, body, err := SplitFrontmatter(raw)
	if err != nil {
		return nil, nil, nil, fmt.Errorf("%s: %w", p, err)
	}
	var sf skillFrontmatter
	if err := yaml.Unmarshal(front, &sf); err != nil {
		return nil, nil, nil, fmt.Errorf("%s frontmatter: %w", p, err)
	}
	if sf.Type != "skill" {
		return nil, nil, nil, fmt.Errorf("%s: type is %q, want skill", p, sf.Type)
	}
	return &Skill{Name: ref, Body: string(body)}, sf.Zuno.AllowedTools, sf.Zuno.AllowedKnowledge, nil
}

func appendMissing(have []string, add ...string) []string {
	seen := map[string]bool{}
	for _, v := range have {
		seen[v] = true
	}
	for _, v := range add {
		if !seen[v] {
			seen[v] = true
			have = append(have, v)
		}
	}
	return have
}

// SystemMessage is the task's system prompt: its prompts/<task>.md when present, else the agent description
// followed by the task body.
func (b *Bundle) SystemMessage(t Task) string {
	var parts []string
	if strings.TrimSpace(t.Prompt) != "" {
		parts = append(parts, t.Prompt)
	} else {
		if b.Description != "" {
			parts = append(parts, b.Description)
		}
		if t.Body != "" {
			parts = append(parts, t.Body)
		}
	}
	// ADR-0579: skill instructions are appended to the task's system prompt, in the order the task declares them.
	for _, sk := range t.Skills {
		if strings.TrimSpace(sk.Body) != "" {
			parts = append(parts, sk.Body)
		}
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

// DeclaredTools is the union of every task's allowed_tools.
func (b *Bundle) DeclaredTools() []string {
	return union(b.Tasks, func(t Task) []string { return t.AllowedTools })
}

// DeclaredKnowledge is the union of every task's allowed_knowledge.
func (b *Bundle) DeclaredKnowledge() []string {
	return union(b.Tasks, func(t Task) []string { return t.AllowedKnowledge })
}

func union(tasks []Task, f func(Task) []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, t := range tasks {
		for _, v := range f(t) {
			if !seen[v] {
				seen[v] = true
				out = append(out, v)
			}
		}
	}
	sort.Strings(out)
	return out
}

// stringValues keeps the string-valued entries of an OKF map (the tile presentation is all strings).
func stringValues(m map[string]any) map[string]string {
	out := map[string]string{}
	for k, v := range m {
		if sv, ok := v.(string); ok {
			out[k] = strings.TrimSpace(sv)
		}
	}
	return out
}

func (d DelegationTarget) String() string { return d.Agent + "/" + d.Task }
