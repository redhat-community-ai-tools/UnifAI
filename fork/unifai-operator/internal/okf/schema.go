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

// SchemaVersions are the OKF versions the embedded schemas describe. The files under schema/ are copies of
// zuno-demo-agents platform/okf/schema/ and must be refreshed with it: adding a schema version is an operator
// release. Every document is checked against the schema of its own okf_version.
var SchemaVersions = []string{"v0.2", "v0.3"}

//go:embed schema/*.json
var schemaFS embed.FS

// schemaFiles maps an OKF version, then a document `type`, to its schema file. The `skill` type exists
// from v0.3 (ADR-0579).
var schemaFiles = map[string]map[string]string{
	"v0.2": {
		"agent":  "zuno-okf-v0.2.schema.json",
		"task":   "zuno-okf-task-v0.2.schema.json",
		"prompt": "zuno-okf-prompt-v0.2.schema.json",
		"tool":   "zuno-okf-tool-v0.2.schema.json",
		"rag":    "zuno-okf-rag-v0.2.schema.json",
		"policy": "zuno-okf-policy-v0.2.schema.json",
	},
	"v0.3": {
		"agent":  "zuno-okf-v0.3.schema.json",
		"task":   "zuno-okf-task-v0.3.schema.json",
		"prompt": "zuno-okf-prompt-v0.3.schema.json",
		"tool":   "zuno-okf-tool-v0.3.schema.json",
		"rag":    "zuno-okf-rag-v0.3.schema.json",
		"policy": "zuno-okf-policy-v0.3.schema.json",
		"skill":  "zuno-okf-skill-v0.3.schema.json",
	},
}

var (
	schemasOnce sync.Once
	schemas     map[string]map[string]*jsonschema.Schema
	schemasErr  error
)

func compiledSchemas() (map[string]map[string]*jsonschema.Schema, error) {
	schemasOnce.Do(func() {
		c := jsonschema.NewCompiler()
		out := map[string]map[string]*jsonschema.Schema{}
		for version, byType := range schemaFiles {
			out[version] = map[string]*jsonschema.Schema{}
			for typ, file := range byType {
				s, err := compileSchemaFile(c, file)
				if err != nil {
					schemasErr = err
					return
				}
				out[version][typ] = s
			}
		}
		schemas = out
	})
	return schemas, schemasErr
}

func compileSchemaFile(c *jsonschema.Compiler, file string) (*jsonschema.Schema, error) {
	b, err := schemaFS.ReadFile("schema/" + file)
	if err != nil {
		return nil, err
	}
	doc, err := jsonschema.UnmarshalJSON(bytes.NewReader(b))
	if err != nil {
		return nil, fmt.Errorf("%s: %w", file, err)
	}
	if err := c.AddResource(file, doc); err != nil {
		return nil, fmt.Errorf("%s: %w", file, err)
	}
	s, err := c.Compile(file)
	if err != nil {
		return nil, fmt.Errorf("%s: %w", file, err)
	}
	return s, nil
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
		version, _ := m["okf_version"].(string)
		byType, known := sch[version]
		if !known {
			if _, isDoc := knownType(typ); isDoc {
				problems = append(problems, fmt.Sprintf("%s: okf_version %q, this operator embeds %s", p, version, strings.Join(SchemaVersions, ", ")))
			}
			continue
		}
		s, ok := byType[typ]
		if !ok {
			continue
		}
		if err := s.Validate(inst); err != nil {
			problems = append(problems, fmt.Sprintf("%s: %s", p, firstLine(err.Error())))
		}
	}
	if len(problems) > 0 {
		return fmt.Errorf("%d OKF documents fail schema validation: %s", len(problems), strings.Join(problems, "; "))
	}
	return nil
}

// knownType reports whether typ is an OKF document type of any embedded version.
func knownType(typ string) (string, bool) {
	for _, byType := range schemaFiles {
		if _, ok := byType[typ]; ok {
			return typ, true
		}
	}
	return "", false
}

func firstLine(s string) string {
	s = strings.TrimSpace(s)
	if i := strings.IndexByte(s, '\n'); i >= 0 {
		return s[:i] + " " + strings.TrimSpace(strings.SplitN(s[i+1:], "\n", 2)[0])
	}
	return s
}
