package okf

import (
	"strings"
	"testing"
)

// v03Tekos is the tekos testdata moved to OKF v0.3 (ADR-0579): every document's version bumped, platform-side
// settings added to the agent and a task, and two skills (one of the agent, one corp skill embedded in the
// artifact) declared by the primary task.
func v03Tekos(t *testing.T) Files {
	t.Helper()
	files := Files{}
	for k, v := range loadTekos(t) {
		files[k] = []byte(strings.ReplaceAll(string(v), "okf_version: v0.2", "okf_version: v0.3"))
	}
	files["agent.okf.md"] = []byte(strings.Replace(string(files["agent.okf.md"]), "zuno:\n",
		"zuno:\n  models:\n    preferred: [reasoning]\n  guardrails:\n    mode: observe\n  limits:\n    max_tokens: 2048\n", 1))
	task := string(files["tasks/answer-technical-question.md"])
	files["tasks/answer-technical-question.md"] = []byte(strings.Replace(task, "zuno:\n",
		"zuno:\n  skills: [cite-sources, corp/safe-answers]\n", 1))
	files["skills/cite-sources.md"] = []byte("---\nokf_version: v0.3\ntype: skill\ntitle: Cite sources\nzuno:\n  name: cite-sources\n  allowed_tools: [search_confluence]\n---\n\nAlways cite the Confluence pages you used.\n")
	files["skills/corp/safe-answers.md"] = []byte("---\nokf_version: v0.3\ntype: skill\ntitle: Safe answers\nzuno:\n  name: safe-answers\n  allowed_knowledge: [knowledge.tech]\n---\n\nNever reveal credentials.\n")
	return files
}

func TestValidateSchemasAcceptsV03(t *testing.T) {
	if err := ValidateSchemas(v03Tekos(t)); err != nil {
		t.Fatalf("a v0.3 bundle should satisfy the embedded v0.3 schemas: %v", err)
	}
}

func TestValidateSchemasChecksEachDocumentAgainstItsOwnVersion(t *testing.T) {
	files := v03Tekos(t)
	// A v0.2 document next to v0.3 ones is checked against v0.2 and still valid.
	files["tasks/write-code.md"] = []byte(strings.ReplaceAll(string(files["tasks/write-code.md"]), "okf_version: v0.3", "okf_version: v0.2"))
	if err := ValidateSchemas(files); err != nil {
		t.Fatalf("mixed versions each valid: %v", err)
	}
	// A v0.3-only field in a v0.2 document is refused by the v0.2 schema.
	files["tasks/write-code.md"] = []byte(strings.Replace(string(files["tasks/write-code.md"]), "zuno:\n", "zuno:\n  skills: [cite-sources]\n", 1))
	if err := ValidateSchemas(files); err == nil || !strings.Contains(err.Error(), "tasks/write-code.md") {
		t.Fatalf("a v0.3 field in a v0.2 task passed: %v", err)
	}
}

func TestValidateSchemasRefusesAnUnknownVersion(t *testing.T) {
	files := v03Tekos(t)
	files["agent.okf.md"] = []byte(strings.Replace(string(files["agent.okf.md"]), "okf_version: v0.3", "okf_version: v0.4", 1))
	if err := ValidateSchemas(files); err == nil || !strings.Contains(err.Error(), "v0.4") {
		t.Fatalf("an unknown okf_version passed: %v", err)
	}
}

func TestParseV03AppendsSkillsInOrderAndReportsPlatformSettings(t *testing.T) {
	b, err := Parse(v03Tekos(t))
	if err != nil {
		t.Fatal(err)
	}
	var task Task
	for _, tk := range b.Tasks {
		if tk.Name == "answer-technical-question" {
			task = tk
		}
	}
	msg := b.SystemMessage(task)
	i, j := strings.Index(msg, "Always cite the Confluence pages"), strings.Index(msg, "Never reveal credentials")
	if i < 0 || j < 0 || i > j {
		t.Fatalf("skills must follow the task prompt in declaration order, got:\n%s", msg)
	}
	if task.Prompt != "" && !strings.HasPrefix(msg, task.Prompt) {
		t.Fatalf("the task's own prompt must come first")
	}
	joined := strings.Join(b.Unmapped, "\n")
	for _, want := range []string{"zuno.models", "zuno.guardrails", "zuno.limits"} {
		if !strings.Contains(joined, want) {
			t.Errorf("%s is not reported as unmapped:\n%s", want, joined)
		}
	}
	// What a skill declares counts as declared by the task: ceilings must cover it.
	if !containsAll(task.AllowedTools, "search_confluence") || !containsAll(task.AllowedKnowledge, "knowledge.tech") {
		t.Errorf("skill declarations missing from the task: tools=%v knowledge=%v", task.AllowedTools, task.AllowedKnowledge)
	}
}

func TestParseV03RefusesAMissingSkill(t *testing.T) {
	files := v03Tekos(t)
	delete(files, "skills/corp/safe-answers.md")
	if _, err := Parse(files); err == nil || !strings.Contains(err.Error(), "corp/safe-answers") {
		t.Fatalf("a task whose corp skill is not in the artifact must be refused: %v", err)
	}
}

func containsAll(have []string, want ...string) bool {
	seen := map[string]bool{}
	for _, h := range have {
		seen[h] = true
	}
	for _, w := range want {
		if !seen[w] {
			return false
		}
	}
	return true
}

func TestParseDelegationTargets(t *testing.T) {
	files := v03Tekos(t)
	files["agent.okf.md"] = []byte(strings.Replace(string(files["agent.okf.md"]), "zuno:\n",
		"zuno:\n  delegation:\n    targets:\n      - {agent: arkos, task: review-architecture}\n", 1))
	if err := ValidateSchemas(files); err != nil {
		t.Fatalf("zuno.delegation is part of OKF v0.3: %v", err)
	}
	b, err := Parse(files)
	if err != nil {
		t.Fatal(err)
	}
	if len(b.DelegationTargets) != 1 || b.DelegationTargets[0].String() != "arkos/review-architecture" {
		t.Fatalf("delegation targets: %v", b.DelegationTargets)
	}
}
