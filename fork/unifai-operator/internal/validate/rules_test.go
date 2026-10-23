package validate

import (
	"encoding/json"
	"strings"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime"
	"k8s.io/utils/ptr"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

func raw(v any) *runtime.RawExtension {
	b, _ := json.Marshal(v)
	return &runtime.RawExtension{Raw: b}
}

// Fixture is an object and the fields it must be flagged on (none for a valid one).
type Fixture struct {
	Name   string
	Obj    client.Object
	Fields []string
}

// Fixtures cover every rule with a valid and an invalid object (reused by the CEL envtest of the next release).
func Fixtures() []Fixture {
	llm := func(typ string, cfg map[string]any, c unifaiv1.CommonSpec) *unifaiv1.UnifaiLLM {
		return &unifaiv1.UnifaiLLM{Spec: unifaiv1.UnifaiLLMSpec{CommonSpec: c, Type: typ, ConfigSpec: unifaiv1.ConfigSpec{Config: raw(cfg)}}}
	}
	bundle := func(mut func(*unifaiv1.UnifaiAgentBundleSpec)) *unifaiv1.UnifaiAgentBundle {
		b := &unifaiv1.UnifaiAgentBundle{}
		mut(&b.Spec)
		return b
	}
	src := func(mut func(*unifaiv1.UnifaiRAGSourceSpec)) *unifaiv1.UnifaiRAGSource {
		s := &unifaiv1.UnifaiRAGSource{Spec: unifaiv1.UnifaiRAGSourceSpec{Type: "web", Web: &unifaiv1.RAGWebSource{URLs: []string{"https://docs.example.com/"}}}}
		mut(&s.Spec)
		return s
	}
	pipeline := func(docs ...unifaiv1.RAGDocument) *unifaiv1.UnifaiRAGPipeline {
		return &unifaiv1.UnifaiRAGPipeline{Spec: unifaiv1.UnifaiRAGPipelineSpec{Documents: docs}}
	}
	sched := func(inputs map[string]string, d unifaiv1.ScheduleDefinition) *unifaiv1.UnifaiSchedule {
		return &unifaiv1.UnifaiSchedule{Spec: unifaiv1.UnifaiScheduleSpec{Workflow: "w", Inputs: inputs, Schedule: d}}
	}
	prompt := map[string]string{"user_prompt": "hi"}
	stackWith := func(mut func(*unifaiv1.UnifaiStackSpec)) *unifaiv1.UnifaiStack {
		s := &unifaiv1.UnifaiStack{}
		mut(&s.Spec)
		return s
	}
	wf := func(d *unifaiv1.AgentDisplay) *unifaiv1.UnifaiWorkflow {
		return &unifaiv1.UnifaiWorkflow{Spec: unifaiv1.UnifaiWorkflowSpec{Blueprint: *raw(map[string]any{}), Display: d}}
	}
	return []Fixture{
		{"llm valid", llm("openai_compatible", map[string]any{"model_name": "m"}, unifaiv1.CommonSpec{TeamRef: "t"}), nil},
		{"llm config.type same", llm("openai", map[string]any{"type": "openai"}, unifaiv1.CommonSpec{}), nil},
		{"llm teamId and teamRef", llm("openai", nil, unifaiv1.CommonSpec{TeamID: "x", TeamRef: "y"}), []string{"spec.teamRef"}},
		{"llm config.type differs", llm("openai", map[string]any{"type": "google_genai"}, unifaiv1.CommonSpec{}), []string{"spec.config.type"}},

		{"bundle valid", bundle(func(s *unifaiv1.UnifaiAgentBundleSpec) {
			s.GroupTeam, s.Providers, s.Retriever = true, []string{"mcp-gateway"}, "knowledge-tekos"
			s.ClassificationOverrides = map[string]string{"answer": "C2"}
		}), nil},
		{"bundle groupTeam with teamRef", bundle(func(s *unifaiv1.UnifaiAgentBundleSpec) { s.GroupTeam, s.TeamRef = true, "t" }), []string{"spec.groupTeam"}},
		{"bundle bad overrides and names", bundle(func(s *unifaiv1.UnifaiAgentBundleSpec) {
			s.ClassificationOverrides = map[string]string{"answer": "C4"}
			s.Providers, s.Retriever = []string{"MCP_Gateway"}, "Knowledge"
		}), []string{"spec.classificationOverrides", "spec.providers", "spec.retriever"}},

		{"web source valid", src(func(s *unifaiv1.UnifaiRAGSourceSpec) { s.SyncInterval = &metav1.Duration{Duration: time.Hour} }), nil},
		{"web source short interval and bad url", src(func(s *unifaiv1.UnifaiRAGSourceSpec) {
			s.SyncInterval = &metav1.Duration{Duration: time.Minute}
			s.Web.URLs = []string{"ftp://x", "not a url"}
		}), []string{"spec.syncInterval", "spec.web.urls"}},

		{"pipeline valid", pipeline(unifaiv1.RAGDocument{Name: "a.md", Source: unifaiv1.DocumentSource{Inline: "x"}},
			unifaiv1.RAGDocument{Name: "b.PDF", Source: unifaiv1.DocumentSource{URL: "https://x/b.pdf"}}), nil},
		{"pipeline duplicate name and bad url", pipeline(unifaiv1.RAGDocument{Name: "a.md", Source: unifaiv1.DocumentSource{Inline: "x"}},
			unifaiv1.RAGDocument{Name: "a.md", Source: unifaiv1.DocumentSource{URL: "file:///etc/passwd"}}),
			[]string{"spec.documents", "spec.documents.source.url"}},
		{"pipeline bad extension", pipeline(unifaiv1.RAGDocument{Name: "a.exe", Source: unifaiv1.DocumentSource{Inline: "x"}}), []string{"spec.documents"}},

		{"schedule interval valid", sched(prompt, unifaiv1.ScheduleDefinition{Interval: "PT30M", RemainingActions: ptr.To(3)}), nil},
		{"schedule cron valid", sched(prompt, unifaiv1.ScheduleDefinition{CronExpression: "0 2 * * 1-5",
			StartAt: "2026-10-01T00:00:00Z", EndAt: "2026-12-01T00:00:00Z"}), nil},
		{"schedule invalid", sched(map[string]string{"other": "x"}, unifaiv1.ScheduleDefinition{Interval: "PT30S",
			CronExpression: "0 2 *", RemainingActions: ptr.To(0), StartAt: "2026-12-01T00:00:00Z", EndAt: "2026-10-01T00:00:00Z"}),
			[]string{"spec.inputs", "spec.schedule.cron_expression", "spec.schedule.end_at", "spec.schedule.interval", "spec.schedule.remaining_actions"}},
		{"schedule interval not ISO", sched(prompt, unifaiv1.ScheduleDefinition{Interval: "30m"}), []string{"spec.schedule.interval"}},

		{"chat valid", &unifaiv1.UnifaiChat{Spec: unifaiv1.UnifaiChatSpec{Workflow: "w", Prompt: "ping"}}, nil},
		{"chat empty prompt", &unifaiv1.UnifaiChat{Spec: unifaiv1.UnifaiChatSpec{Workflow: "w", Prompt: "  "}}, []string{"spec.prompt"}},

		{"workflow display valid", wf(&unifaiv1.AgentDisplay{Icon: "robot-2", Color: "#1a2B3c"}), nil},
		{"workflow display keyword colour", wf(&unifaiv1.AgentDisplay{Color: "teal"}), nil},
		{"workflow display invalid", wf(&unifaiv1.AgentDisplay{Icon: "Robot!", Color: "rgb(1,2,3)"}), []string{"spec.display.color", "spec.display.icon"}},

		{"stack valid", stackWith(func(s *unifaiv1.UnifaiStackSpec) {
			s.Images = map[string]string{"rag": "quay.io/x/rag:1"}
			s.Storage.Sizes = map[string]string{"mongodb": "20Gi"}
			s.Backup = &unifaiv1.BackupSpec{Schedule: "0 2 * * *"}
		}), nil},
		{"stack invalid", stackWith(func(s *unifaiv1.UnifaiStackSpec) {
			s.Images = map[string]string{"mas": "x"}
			s.Resources = map[string]corev1.ResourceRequirements{"ragcelery": {}}
			s.Storage.Sizes = map[string]string{"mongodb": "twenty"}
			s.Backup = &unifaiv1.BackupSpec{Schedule: "daily"}
			s.RAG.Embedding.Dimension = -1
		}), []string{"spec.backup.schedule", "spec.images", "spec.rag.embedding.dimension", "spec.resources", "spec.storage.sizes"}},

		{"team (no common rule beyond its own)", &unifaiv1.UnifaiTeam{}, nil},
	}
}

func TestRules(t *testing.T) {
	for _, f := range Fixtures() {
		var got []string
		for _, v := range Check(f.Obj) {
			got = append(got, v.Field)
		}
		if strings.Join(got, ",") != strings.Join(f.Fields, ",") {
			t.Errorf("%s: flagged %v, want %v", f.Name, got, f.Fields)
		}
	}
}

func TestEveryRuleHasAnInvalidFixture(t *testing.T) {
	flagged := map[string]bool{}
	for _, f := range Fixtures() {
		for _, fl := range f.Fields {
			flagged[fl] = true
		}
	}
	for group, rules := range Rules {
		for _, r := range rules {
			if !flagged[r.Field] {
				t.Errorf("%s rule %s has no invalid fixture", group, r.Field)
			}
		}
	}
}
