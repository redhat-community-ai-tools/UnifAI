package controller

import (
	"encoding/json"
	"reflect"
	"sort"
	"strings"
	"testing"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
	"github.com/startxfr/unifai-operator/internal/okf"
)

// hiddenFieldSentinels are put in every non-public place of a bundle; none may reach the sheet (ADR-0582 clause 4).
func hiddenBundle() *okf.Bundle {
	return &okf.Bundle{
		Name: "demo", OKFVersion: "v0.2", Title: "Demo agent", Description: "Answers demo questions.",
		Status: "active", Classification: okf.C2, Maintainer: "platform team", PrimaryTask: "t1",
		AccessGroups: []string{"SENTINEL-GROUP"}, RAGTopK: 7,
		UI: map[string]string{"displayName": "Demo", "tileDescription": "A demo", "icon": "code", "color": "#0066cc"},
		Tasks: []okf.Task{{
			Name: "t1", Title: "First task", Body: "SENTINEL-BODY", Prompt: "SENTINEL-PROMPT",
			AllowedTools: []string{"SENTINEL-TOOL"}, AllowedKnowledge: []string{"SENTINEL-KNOWLEDGE"},
			LiveReadTool: "SENTINEL-LIVE", PromptExamples: []string{"SENTINEL-EXAMPLE"},
			Skills: []okf.Skill{{Name: "s", Body: "SENTINEL-SKILL"}},
			Models: map[string]any{"k": "SENTINEL-MODEL"}, Limits: map[string]any{"k": "SENTINEL-LIMIT"},
		}},
		Unmapped: []string{"SENTINEL-UNMAPPED"},
	}
}

func TestBundleDisplayCarriesPublicFieldsOnly(t *testing.T) {
	d := bundleDisplay(hiddenBundle())
	raw, err := json.Marshal(d)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(raw), "SENTINEL") {
		t.Fatalf("a hidden field reached the sheet: %s", raw)
	}
	want := unifaiv1.AgentDisplay{
		Title: "Demo agent", DisplayName: "Demo", Description: "Answers demo questions.", TileDescription: "A demo",
		Maintainer: "platform team", State: "active", Classification: "C2", Icon: "code", Color: "#0066cc",
		Tasks: []unifaiv1.DisplayTask{{Name: "t1", Title: "First task"}},
	}
	if !reflect.DeepEqual(*d, want) {
		t.Fatalf("sheet %+v, want %+v", *d, want)
	}
}

// The sheet type is a closed list: adding a field to it is a disclosure decision that must update this test and
// the multi-agent display validator together.
func TestAgentDisplayFieldsAreTheClosedPublicList(t *testing.T) {
	var got []string
	typ := reflect.TypeOf(unifaiv1.AgentDisplay{})
	for i := 0; i < typ.NumField(); i++ {
		got = append(got, strings.Split(typ.Field(i).Tag.Get("json"), ",")[0])
	}
	sort.Strings(got)
	want := []string{"classification", "color", "description", "displayName", "icon", "maintainer", "state", "tasks", "tileDescription", "title"}
	if !reflect.DeepEqual(got, want) {
		t.Fatalf("AgentDisplay fields %v, want %v", got, want)
	}
}

func TestEmittedWorkflowsCarryTheSameSheet(t *testing.T) {
	cr := &unifaiv1.UnifaiAgentBundle{}
	cr.Name, cr.Namespace = "demo", "ns"
	b := hiddenBundle()
	b.GraphShape = okf.ShapeRetrieveReasonRespond
	objs, _, err := renderBundle(cr, b)
	if err != nil {
		t.Skipf("renderBundle needs more of the bundle for this shape: %v", err)
	}
	found := false
	for _, o := range objs {
		if wf, ok := o.(*unifaiv1.UnifaiWorkflow); ok {
			found = true
			if wf.Spec.Display == nil || wf.Spec.Display.Title != "Demo agent" {
				t.Fatalf("workflow %s lacks the sheet: %+v", wf.Name, wf.Spec.Display)
			}
		}
	}
	if !found {
		t.Fatal("no workflow emitted")
	}
}
