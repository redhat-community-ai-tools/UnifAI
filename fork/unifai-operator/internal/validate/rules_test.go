package validate

import (
	"strings"
	"testing"
)

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
