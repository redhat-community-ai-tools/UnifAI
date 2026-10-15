// Package stack deploys an UnifAI platform: the upstream Helm charts (embedded, see hack/sync-charts.sh) rendered
// with values derived from an UnifaiStack, plus the ConfigMaps/Secrets the upstream helmfile hooks used to create.
package stack

import (
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"fmt"
	"io/fs"
	"path"
	"sort"
	"strings"
	"sync"

	"helm.sh/helm/v3/pkg/chart"
	"helm.sh/helm/v3/pkg/chart/loader"
	"sigs.k8s.io/yaml"
)

//go:embed all:assets
var assets embed.FS

var (
	chartMu    sync.Mutex
	chartCache = map[string]*chart.Chart{}
	digests    = map[string]string{}
)

// loadChart loads an embedded chart by directory name (assets/charts/<name>) and returns it with a content digest.
func loadChart(name string) (*chart.Chart, string, error) {
	chartMu.Lock()
	defer chartMu.Unlock()
	if c, ok := chartCache[name]; ok {
		return c, digests[name], nil
	}
	root := path.Join("assets/charts", name)
	var files []*loader.BufferedFile
	h := sha256.New()
	err := fs.WalkDir(assets, root, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		data, err := assets.ReadFile(p)
		if err != nil {
			return err
		}
		rel := strings.TrimPrefix(p, root+"/")
		if rel == ".helmignore" {
			return nil
		}
		files = append(files, &loader.BufferedFile{Name: rel, Data: data})
		return nil
	})
	if err != nil {
		return nil, "", fmt.Errorf("chart %s: %w", name, err)
	}
	sort.Slice(files, func(i, j int) bool { return files[i].Name < files[j].Name })
	for _, f := range files {
		h.Write([]byte(f.Name))
		h.Write(f.Data)
	}
	c, err := loader.LoadFiles(files)
	if err != nil {
		return nil, "", fmt.Errorf("chart %s: %w", name, err)
	}
	chartCache[name] = c
	digests[name] = hex.EncodeToString(h.Sum(nil))[:16]
	return c, digests[name], nil
}

// valuesFile returns a section of an embedded upstream values file (assets/values/<file>); key "" = whole file.
func valuesFile(file, key string) (map[string]any, error) {
	data, err := assets.ReadFile(path.Join("assets/values", file))
	if err != nil {
		return nil, err
	}
	m := map[string]any{}
	if err := yaml.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("values %s: %w", file, err)
	}
	if key == "" {
		return m, nil
	}
	sec, _ := m[key].(map[string]any)
	if sec == nil {
		sec = map[string]any{}
	}
	return deepCopy(sec), nil
}

// UpstreamSource describes which upstream commit the embedded charts come from.
func UpstreamSource() string {
	b, _ := assets.ReadFile("assets/SOURCE")
	return strings.TrimSpace(string(b))
}

func deepCopy(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = copyValue(v)
	}
	return out
}

func copyValue(v any) any {
	switch t := v.(type) {
	case map[string]any:
		return deepCopy(t)
	case []any:
		out := make([]any, len(t))
		for i, x := range t {
			out[i] = copyValue(x)
		}
		return out
	default:
		return v
	}
}

// merge deep-merges over into base (maps merged, everything else replaced) and returns base.
func merge(base, over map[string]any) map[string]any {
	for k, v := range over {
		if vm, ok := v.(map[string]any); ok {
			if bm, ok := base[k].(map[string]any); ok {
				merge(bm, vm)
				continue
			}
			base[k] = deepCopy(vm)
			continue
		}
		base[k] = copyValue(v)
	}
	return base
}

// set assigns value at a dotted path, creating maps.
func set(m map[string]any, dotted string, value any) {
	parts := strings.Split(dotted, ".")
	for _, p := range parts[:len(parts)-1] {
		next, ok := m[p].(map[string]any)
		if !ok {
			next = map[string]any{}
			m[p] = next
		}
		m = next
	}
	m[parts[len(parts)-1]] = value
}
