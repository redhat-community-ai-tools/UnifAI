package okf

import (
	"bytes"
	"embed"
	"fmt"
	"strings"
	"sync"

	"github.com/santhosh-tekuri/jsonschema/v6"
	"sigs.k8s.io/yaml"
)

// SchemaVersion is the OKF version the embedded schemas describe. The files under schema/ are copies of
// zuno-demo platform/okf/schema/ and must be refreshed with it: adding a schema version is an operator release.
const SchemaVersion = "v0.2"

//go:embed schema/*.json
var schemaFS embed.FS

// schemaFiles maps an OKF document `type` to its schema file.
var schemaFiles = map[string]string{
	"agent":  "zuno-okf-v0.2.schema.json",
	"task":   "zuno-okf-task-v0.2.schema.json",
	"prompt": "zuno-okf-prompt-v0.2.schema.json",
	"tool":   "zuno-okf-tool-v0.2.schema.json",
	"rag":    "zuno-okf-rag-v0.2.schema.json",
	"policy": "zuno-okf-policy-v0.2.schema.json",
}

var (
	schemasOnce sync.Once
	schemas     map[string]*jsonschema.Schema
	schemasErr  error
)

func compiledSchemas() (map[string]*jsonschema.Schema, error) {
	schemasOnce.Do(func() {
		c := jsonschema.NewCompiler()
		out := map[string]*jsonschema.Schema{}
		for typ, file := range schemaFiles {
			b, err := schemaFS.ReadFile("schema/" + file)
			if err != nil {
				schemasErr = err
				return
			}
			doc, err := jsonschema.UnmarshalJSON(bytes.NewReader(b))
			if err != nil {
				schemasErr = fmt.Errorf("%s: %w", file, err)
				return
			}
			if err := c.AddResource(file, doc); err != nil {
				schemasErr = fmt.Errorf("%s: %w", file, err)
				return
			}
			s, err := c.Compile(file)
			if err != nil {
				schemasErr = fmt.Errorf("%s: %w", file, err)
				return
			}
			out[typ] = s
		}
		schemas = out
	})
	return schemas, schemasErr
}

// ValidateSchemas checks the frontmatter of every Markdown file of the bundle that declares an OKF `type`
// against the embedded schema of that type. Files without frontmatter (README notes) are not OKF documents.
func ValidateSchemas(files Files) error {
	sch, err := compiledSchemas()
	if err != nil {
		return fmt.Errorf("embedded OKF schemas: %w", err)
	}
	var problems []string
	for _, p := range files.SortedPaths() {
		if !strings.HasSuffix(p, ".md") || ignored(p) {
			continue
		}
		front, _, err := SplitFrontmatter(files[p])
		if err != nil {
			continue
		}
		js, err := yaml.YAMLToJSON(front)
		if err != nil {
			problems = append(problems, fmt.Sprintf("%s: %v", p, err))
			continue
		}
		inst, err := jsonschema.UnmarshalJSON(bytes.NewReader(js))
		if err != nil {
			problems = append(problems, fmt.Sprintf("%s: %v", p, err))
			continue
		}
		m, _ := inst.(map[string]any)
		typ, _ := m["type"].(string)
		s, ok := sch[typ]
		if !ok {
			continue
		}
		if v, _ := m["okf_version"].(string); v != SchemaVersion {
			problems = append(problems, fmt.Sprintf("%s: okf_version %q, this operator embeds %s", p, v, SchemaVersion))
			continue
		}
		if err := s.Validate(inst); err != nil {
			problems = append(problems, fmt.Sprintf("%s: %s", p, firstLine(err.Error())))
		}
	}
	if len(problems) > 0 {
		return fmt.Errorf("%d OKF documents fail schema %s: %s", len(problems), SchemaVersion, strings.Join(problems, "; "))
	}
	return nil
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i] + " " + strings.TrimSpace(strings.SplitN(s[i+1:], "\n", 2)[0])
	}
	return s
}
