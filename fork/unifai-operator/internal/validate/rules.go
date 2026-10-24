// Package validate holds the static rules of the UnifAI custom resources: what can be checked on an object alone
// (no other object, UnifAI, registry or Secret). The CRDs refuse them at admission (CEL rules carrying the same
// messages); the operator still reports them (condition SpecWarnings, Warning Event, metric) for objects stored
// before the rules existed and for the rules CEL cannot express (R-304).
package validate

import (
	"encoding/json"
	"fmt"
	"net/url"
	"regexp"
	"slices"
	"sort"
	"strings"
	"time"

	"k8s.io/apimachinery/pkg/api/resource"
	"k8s.io/apimachinery/pkg/runtime"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// Violation is a rule an object breaks.
type Violation struct {
	Field   string
	Message string
}

func (v Violation) String() string { return v.Field + ": " + v.Message }

// Rule is one static check. The CRD refuses it with Message (a CEL rule of api/v1alpha1), unless Refusal names the
// API server's own answer or WarnOnly says the rule is only reported (CEL cannot read the field).
type Rule struct {
	Field    string
	Message  string
	Refusal  string
	WarnOnly bool
	check    func(obj client.Object) bool // true when the object is valid
}

// Refused returns what the API server answers an object breaking the rule ("" for a reported-only rule).
func (r Rule) Refused() string {
	switch {
	case r.WarnOnly:
		return ""
	case r.Refusal != "":
		return r.Refusal
	}
	return r.Message
}

// Allowed component keys of the UnifaiStack maps.
var (
	ImageKeys    = []string{"mongodb", "qdrant", "rabbitmq", "redis", "redisInsight", "temporal", "rag", "multiagent", "backend", "identity", "ui", "docling", "embedding"}
	ResourceKeys = append(slices.Clone(ImageKeys), "ragCelery", "multiagentWorker")
	SizeKeys     = []string{"mongodb", "qdrant", "redis", "redisInsight", "temporal", "rabbitmq", "ragShared", "multiagentShared", "logging", "docling", "keycloakDb"}
)

var (
	dnsName      = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]*[a-z0-9])?$`)
	isoDuration  = regexp.MustCompile(`^P(T(\d+H)?(\d+M)?(\d+S)?|\d+D(T(\d+H)?(\d+M)?(\d+S)?)?)$`)
	cronFields   = regexp.MustCompile(`^\S+(\s+\S+){4}$`)
	iconPattern  = regexp.MustCompile(`^[a-z0-9-]+$`)
	colorPattern = regexp.MustCompile(`^(#[0-9a-fA-F]{6}|[a-z]+)$`)
	docName      = regexp.MustCompile(`(?i)\.(pdf|docx|md|pptx)$`)
	levels       = []string{"C1", "C2", "C3"}
)

func httpURL(s string) bool {
	u, err := url.Parse(s)
	return err == nil && (u.Scheme == "http" || u.Scheme == "https") && u.Host != ""
}

// isoMinutes returns the length of a simple ISO-8601 duration (days, hours, minutes, seconds).
func isoMinutes(s string) (time.Duration, bool) {
	if !isoDuration.MatchString(s) || s == "P" || s == "PT" {
		return 0, false
	}
	var d time.Duration
	num := 0
	inTime := false
	for _, c := range s[1:] {
		switch {
		case c == 'T':
			inTime = true
		case c >= '0' && c <= '9':
			num = num*10 + int(c-'0')
		default:
			unit := map[rune]time.Duration{'D': 24 * time.Hour, 'H': time.Hour, 'M': time.Minute, 'S': time.Second}[c]
			if c == 'M' && !inTime {
				return 0, false
			}
			d += time.Duration(num) * unit
			num = 0
		}
	}
	return d, true
}

// rawObject decodes a free-form JSON object (nil or empty: an empty map).
func rawObject(r *runtime.RawExtension) (map[string]any, error) {
	m := map[string]any{}
	if r == nil || len(r.Raw) == 0 {
		return m, nil
	}
	return m, json.Unmarshal(r.Raw, &m)
}

func common(obj client.Object) *unifaiv1.CommonSpec {
	if o, ok := obj.(unifaiv1.Object); ok {
		return o.GetCommon()
	}
	if b, ok := obj.(*unifaiv1.UnifaiAgentBundle); ok {
		return &b.Spec.CommonSpec
	}
	if s, ok := obj.(*unifaiv1.UnifaiRAGSource); ok {
		return &s.Spec.CommonSpec
	}
	return nil
}

// resourceType returns spec.type and spec.config of the seven UnifAI resource kinds.
func resourceType(obj client.Object) (string, map[string]any, bool) {
	var typ string
	var cfg *unifaiv1.ConfigSpec
	switch o := obj.(type) {
	case *unifaiv1.UnifaiLLM:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiProvider:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiTool:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiCondition:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiRetriever:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiSandbox:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	case *unifaiv1.UnifaiAgent:
		typ, cfg = o.Spec.Type, &o.Spec.ConfigSpec
	default:
		return "", nil, false
	}
	m, _ := rawObject(cfg.Config)
	return typ, m, true
}

func keysIn(m map[string]bool, allowed []string) bool {
	for k := range m {
		if !slices.Contains(allowed, k) {
			return false
		}
	}
	return true
}

func mapKeys[V any](m map[string]V) map[string]bool {
	out := map[string]bool{}
	for k := range m {
		out[k] = true
	}
	return out
}

// Rules is the table of the static rules, by kind.
var Rules = map[string][]Rule{
	"*": {{
		Field: "spec.teamRef", Message: "teamId and teamRef are exclusive",
		check: func(obj client.Object) bool {
			c := common(obj)
			return c == nil || c.TeamID == "" || c.TeamRef == ""
		},
	}},
	"resource": {{
		// config is free-form (preserved unknown fields): CEL cannot read config.type.
		Field: "spec.config.type", Message: "config.type, when set, must equal spec.type", WarnOnly: true,
		check: func(obj client.Object) bool {
			typ, cfg, _ := resourceType(obj)
			t, ok := cfg["type"]
			return !ok || t == typ
		},
	}},
	"UnifaiAgentBundle": {
		{Field: "spec.groupTeam", Message: "groupTeam is exclusive with teamId and teamRef",
			check: func(obj client.Object) bool {
				s := obj.(*unifaiv1.UnifaiAgentBundle).Spec
				return !s.GroupTeam || (s.TeamID == "" && s.TeamRef == "")
			}},
		{Field: "spec.classificationOverrides", Message: "classification overrides are C1, C2 or C3",
			check: func(obj client.Object) bool {
				for _, v := range obj.(*unifaiv1.UnifaiAgentBundle).Spec.ClassificationOverrides {
					if !slices.Contains(levels, v) {
						return false
					}
				}
				return true
			}},
		{Field: "spec.providers", Message: "providers are UnifaiProvider names (lower-case DNS labels)",
			check: func(obj client.Object) bool {
				for _, p := range obj.(*unifaiv1.UnifaiAgentBundle).Spec.Providers {
					if !dnsName.MatchString(p) {
						return false
					}
				}
				return true
			}},
		{Field: "spec.retriever", Message: "retriever is an UnifaiRetriever name (lower-case DNS label)",
			check: func(obj client.Object) bool {
				r := obj.(*unifaiv1.UnifaiAgentBundle).Spec.Retriever
				return r == "" || dnsName.MatchString(r)
			}},
	},
	"UnifaiRAGSource": {
		{Field: "spec.syncInterval", Message: "syncInterval is at least 10m",
			check: func(obj client.Object) bool {
				i := obj.(*unifaiv1.UnifaiRAGSource).Spec.SyncInterval
				return i == nil || i.Duration >= 10*time.Minute
			}},
		{Field: "spec.web.urls", Message: "web urls are http(s) URLs",
			check: func(obj client.Object) bool {
				w := obj.(*unifaiv1.UnifaiRAGSource).Spec.Web
				if w == nil {
					return true
				}
				for _, u := range w.URLs {
					if !httpURL(u) {
						return false
					}
				}
				return true
			}},
	},
	"UnifaiRAGPipeline": {
		{Field: "spec.documents", Message: "document names are unique", Refusal: "Duplicate value",
			check: func(obj client.Object) bool {
				seen := map[string]bool{}
				for _, d := range obj.(*unifaiv1.UnifaiRAGPipeline).Spec.Documents {
					if seen[d.Name] {
						return false
					}
					seen[d.Name] = true
				}
				return true
			}},
		{Field: "spec.documents.name", Message: "document names end in .pdf, .docx, .md or .pptx",
			check: func(obj client.Object) bool {
				for _, d := range obj.(*unifaiv1.UnifaiRAGPipeline).Spec.Documents {
					if !docName.MatchString(d.Name) {
						return false
					}
				}
				return true
			}},
		{Field: "spec.documents.source.url", Message: "document urls are http(s) URLs",
			check: func(obj client.Object) bool {
				for _, d := range obj.(*unifaiv1.UnifaiRAGPipeline).Spec.Documents {
					if d.Source.URL != "" && !httpURL(d.Source.URL) {
						return false
					}
				}
				return true
			}},
	},
	"UnifaiSchedule": {
		{Field: "spec.inputs", Message: "inputs needs user_prompt",
			check: func(obj client.Object) bool {
				_, ok := obj.(*unifaiv1.UnifaiSchedule).Spec.Inputs["user_prompt"]
				return ok
			}},
		{Field: "spec.schedule.interval", Message: "interval is an ISO-8601 duration of at least PT1M",
			check: func(obj client.Object) bool {
				i := obj.(*unifaiv1.UnifaiSchedule).Spec.Schedule.Interval
				if i == "" {
					return true
				}
				d, ok := isoMinutes(i)
				return ok && d >= time.Minute
			}},
		{Field: "spec.schedule.cron_expression", Message: "cron_expression has 5 fields",
			check: func(obj client.Object) bool {
				c := obj.(*unifaiv1.UnifaiSchedule).Spec.Schedule.CronExpression
				return c == "" || cronFields.MatchString(strings.TrimSpace(c))
			}},
		{Field: "spec.schedule.remaining_actions", Message: "remaining_actions is at least 1",
			check: func(obj client.Object) bool {
				r := obj.(*unifaiv1.UnifaiSchedule).Spec.Schedule.RemainingActions
				return r == nil || *r >= 1
			}},
		{Field: "spec.schedule.end_at", Message: "end_at is after start_at",
			check: func(obj client.Object) bool {
				s := obj.(*unifaiv1.UnifaiSchedule).Spec.Schedule
				if s.StartAt == "" || s.EndAt == "" {
					return true
				}
				a, e1 := time.Parse(time.RFC3339, s.StartAt)
				b, e2 := time.Parse(time.RFC3339, s.EndAt)
				return e1 != nil || e2 != nil || a.Before(b)
			}},
	},
	"UnifaiChat": {{
		Field: "spec.prompt", Message: "prompt is not empty",
		check: func(obj client.Object) bool { return strings.TrimSpace(obj.(*unifaiv1.UnifaiChat).Spec.Prompt) != "" },
	}},
	"UnifaiWorkflow": {
		{Field: "spec.display.icon", Message: "icon is made of lower-case letters, digits and hyphens",
			check: func(obj client.Object) bool {
				d := obj.(*unifaiv1.UnifaiWorkflow).Spec.Display
				return d == nil || d.Icon == "" || iconPattern.MatchString(d.Icon)
			}},
		{Field: "spec.display.color", Message: "color is a CSS colour keyword or #rrggbb",
			check: func(obj client.Object) bool {
				d := obj.(*unifaiv1.UnifaiWorkflow).Spec.Display
				return d == nil || d.Color == "" || colorPattern.MatchString(d.Color)
			}},
	},
	"UnifaiStack": {
		{Field: "spec.images", Message: "images keys: " + strings.Join(ImageKeys, ", "),
			check: func(obj client.Object) bool {
				return keysIn(mapKeys(obj.(*unifaiv1.UnifaiStack).Spec.Images), ImageKeys)
			}},
		{Field: "spec.resources", Message: "resources keys: " + strings.Join(ResourceKeys, ", "),
			check: func(obj client.Object) bool {
				return keysIn(mapKeys(obj.(*unifaiv1.UnifaiStack).Spec.Resources), ResourceKeys)
			}},
		{Field: "spec.storage.sizes", Message: "sizes keys: " + strings.Join(SizeKeys, ", ") + "; values are quantities",
			check: func(obj client.Object) bool {
				sizes := obj.(*unifaiv1.UnifaiStack).Spec.Storage.Sizes
				for _, v := range sizes {
					if _, err := resource.ParseQuantity(v); err != nil {
						return false
					}
				}
				return keysIn(mapKeys(sizes), SizeKeys)
			}},
		{Field: "spec.backup.schedule", Message: "backup schedule is a 5-field cron expression",
			check: func(obj client.Object) bool {
				b := obj.(*unifaiv1.UnifaiStack).Spec.Backup
				return b == nil || b.Schedule == "" || cronFields.MatchString(strings.TrimSpace(b.Schedule))
			}},
		{Field: "spec.rag.embedding.dimension", Message: "embedding dimension is not negative",
			check: func(obj client.Object) bool { return obj.(*unifaiv1.UnifaiStack).Spec.RAG.Embedding.Dimension >= 0 }},
	},
}

// kindOf returns the rule groups that apply to the object.
func kindOf(obj client.Object) []string {
	groups := []string{"*"}
	if _, _, ok := resourceType(obj); ok {
		groups = append(groups, "resource")
	}
	t := fmt.Sprintf("%T", obj)
	return append(groups, t[strings.LastIndex(t, ".")+1:])
}

// Check returns the static rules the object breaks, sorted by field.
func Check(obj client.Object) []Violation {
	var out []Violation
	for _, g := range kindOf(obj) {
		for _, r := range Rules[g] {
			if !r.check(obj) {
				out = append(out, Violation{Field: r.Field, Message: r.Message})
			}
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Field < out[j].Field })
	return out
}
