package controller

import (
	"crypto/md5" //nolint:gosec
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
)

// fakeMAS is an in-memory imitation of the UnifAI multiagent API endpoints used by the operator.
type fakeMAS struct {
	mu         sync.Mutex
	seq        int
	resources  map[string]map[string]any // rid -> resource
	blueprints map[string]map[string]any // id -> {name, spec}
	schedules  map[string]map[string]any
	templates  map[string]map[string]any
	sessions   map[string]string // id -> status
	ragFiles   map[string]string // name -> md5 of uploaded content
	ragSources map[string]map[string]any
	ragSyncs   map[string]int // source id -> embed calls (incremental syncs)
	users      []string       // X-Authenticated-User of each call
}

func newFakeMAS() (*fakeMAS, *httptest.Server) {
	f := &fakeMAS{resources: map[string]map[string]any{}, blueprints: map[string]map[string]any{},
		schedules: map[string]map[string]any{}, templates: map[string]map[string]any{}, sessions: map[string]string{},
		ragFiles: map[string]string{}, ragSources: map[string]map[string]any{}, ragSyncs: map[string]int{}}
	return f, httptest.NewServer(f)
}

func (f *fakeMAS) id(prefix string) string {
	f.seq++
	return fmt.Sprintf("%s%04d", prefix, f.seq)
}

func reply(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

// resourceByName returns a copy of the resource of a category with that name.
func (f *fakeMAS) resourceByName(category, name string) map[string]any {
	f.mu.Lock()
	defer f.mu.Unlock()
	for _, r := range f.resources {
		if r["category"] == category && r["name"] == name {
			b, _ := json.Marshal(r)
			out := map[string]any{}
			_ = json.Unmarshal(b, &out)
			return out
		}
	}
	return nil
}

func (f *fakeMAS) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.users = append(f.users, r.Header.Get("X-Authenticated-User"))
	body := map[string]any{}
	if r.Body != nil {
		_ = json.NewDecoder(r.Body).Decode(&body)
	}
	q := r.URL.Query()
	switch r.URL.Path {
	case "/api/resources/config.validate":
		if body["type"] == "unserved" {
			reply(w, 500, map[string]any{"error": "'No spec registered for ResourceCategory.LLM/unserved'"})
			return
		}
		cfg, _ := body["config"].(map[string]any)
		if bu, ok := cfg["base_url"].(string); ok && !strings.HasPrefix(bu, "http") {
			reply(w, 400, map[string]any{"error": "Schema validation failed: base_url"})
			return
		}
		reply(w, 200, map[string]any{"is_valid": true})
	case "/api/resources/resources.list":
		var out []any
		for _, res := range f.resources {
			if res["category"] == q.Get("category") {
				out = append(out, res)
			}
		}
		reply(w, 200, map[string]any{"resources": out})
	case "/api/resources/resource.save":
		rid := f.id("rid")
		f.resources[rid] = map[string]any{"rid": rid, "name": body["name"], "type": body["type"], "category": body["category"], "cfg_dict": body["config"]}
		reply(w, 201, f.resources[rid])
	case "/api/resources/resource.update":
		res, ok := f.resources[body["resourceId"].(string)]
		if !ok {
			reply(w, 404, map[string]any{"error": "not found"})
			return
		}
		res["cfg_dict"] = body["config"]
		reply(w, 200, res)
	case "/api/resources/resource.delete":
		rid := q.Get("resourceId")
		for _, other := range f.resources {
			b, _ := json.Marshal(other["cfg_dict"])
			if strings.Contains(string(b), "$ref:"+rid) {
				reply(w, 400, map[string]any{"error": "Resource in use"})
				return
			}
		}
		delete(f.resources, rid)
		reply(w, 200, map[string]any{})
	case "/api/blueprints/available.blueprints.summary.get":
		out := []any{}
		for id, b := range f.blueprints {
			out = append(out, map[string]any{"blueprint_id": id, "name": b["name"]})
		}
		reply(w, 200, out)
	case "/api/blueprints/blueprint.save", "/api/blueprints/blueprint.update":
		spec := map[string]any{}
		_ = json.Unmarshal([]byte(body["blueprintRaw"].(string)), &spec)
		id, _ := body["blueprintId"].(string)
		if id == "" {
			id = f.id("bp")
		}
		f.blueprints[id] = map[string]any{"name": spec["name"], "spec": spec}
		reply(w, 201, map[string]any{"blueprint_id": id})
	case "/api/blueprints/remove.blueprint":
		delete(f.blueprints, q.Get("blueprintId"))
		reply(w, 200, map[string]any{})
	case "/api/schedules/schedule.create":
		id := f.id("sch")
		f.schedules[id] = body
		reply(w, 201, map[string]any{"id": id})
	case "/api/schedules/schedule.update":
		id := body["scheduleId"].(string)
		if _, ok := f.schedules[id]; !ok {
			reply(w, 404, map[string]any{"error": "not found"})
			return
		}
		f.schedules[id] = body
		reply(w, 200, map[string]any{"id": id})
	case "/api/schedules/schedule.get":
		if _, ok := f.schedules[q.Get("scheduleId")]; !ok {
			reply(w, 404, map[string]any{"error": "not found"})
			return
		}
		reply(w, 200, map[string]any{})
	case "/api/schedules/schedule.delete":
		delete(f.schedules, body["scheduleId"].(string))
		reply(w, 200, map[string]any{"deleted": true})
	case "/api/templates/template.create":
		id := f.id("tpl")
		f.templates[id] = body
		reply(w, 201, map[string]any{"template_id": id})
	case "/api/templates/template.get":
		if _, ok := f.templates[q.Get("templateId")]; !ok {
			reply(w, 404, map[string]any{"error": "not found"})
			return
		}
		reply(w, 200, map[string]any{})
	case "/api/templates/template.delete":
		delete(f.templates, q.Get("templateId"))
		reply(w, 200, map[string]any{})
	case "/api/sessions/user.session.create":
		id := f.id("sess")
		f.sessions[id] = "PENDING"
		reply(w, 200, id)
	case "/api/sessions/user.session.submit":
		f.sessions[body["sessionId"].(string)] = "COMPLETED"
		reply(w, 202, map[string]any{})
	case "/api/sessions/session.chat.get":
		reply(w, 200, map[string]any{"status": f.sessions[q.Get("sessionId")], "output": "pong"})
	case "/api/sessions/session.delete":
		delete(f.sessions, q.Get("sessionId"))
		reply(w, 200, map[string]any{})
	case "/api/docs/upload":
		for _, file := range body["files"].([]any) {
			fm := file.(map[string]any)
			raw, _ := base64.StdEncoding.DecodeString(fm["content"].(string))
			sum := md5.Sum(raw)
			f.ragFiles[fm["name"].(string)] = hex.EncodeToString(sum[:])
		}
		reply(w, 200, map[string]any{"message": "ok"})
	case "/api/pipelines/embed":
		if body["source_type"] == "confluence" {
			// Mirrors the RAG service: idempotent registration per scope, shared sources for publishers only.
			d := body["data"].([]any)[0].(map[string]any)
			if d["visibility"] == "shared" && r.Header.Get("X-Authenticated-User") != "publisher" {
				reply(w, 200, map[string]any{"registration": map[string]any{"issues": []any{map[string]any{
					"error": "may not publish shared sources", "error_type": "ACCESS_DENIED"}}}})
				return
			}
			id := fmt.Sprintf("conf-%v-%v-%v", d["baseUrl"], d["spaceKey"], d["rootTitle"])
			f.ragSyncs[id]++
			if d["spaceKey"] == "ODDBODY" {
				// Accepted, but with a body the operator cannot read: it must not retry (each call queues a sync).
				reply(w, 200, map[string]any{"pipeline_execution": map[string]any{"status": "pipeline_workflow_started"}})
				return
			}
			f.ragSources[id] = map[string]any{"source_id": id, "source_name": d["name"], "source_type": "CONFLUENCE", "status": "DONE",
				"type_data": map[string]any{"page_count": 3, "pages_changed": 1, "pages_deleted": 0}}
			reply(w, 200, map[string]any{"registration": map[string]any{
				// Same shape as rag core/registration/service.py.
				"registered_sources": []any{map[string]any{"metadata": map[string]any{"source_id": id}}}, "issues": []any{}}})
			return
		}
		var issues []any
		n := 0
		for _, d := range body["data"].([]any) {
			name := d.(map[string]any)["source_name"].(string)
			dup := false
			for _, s := range f.ragSources {
				dup = dup || s["source_name"] == name
			}
			if dup {
				issues = append(issues, map[string]any{"doc_name": name, "issue_type": "Duplicate filename"})
				continue
			}
			id := f.id("src")
			f.ragSources[id] = map[string]any{"source_id": id, "source_name": name, "status": "DONE",
				"type_data": map[string]any{"md5": f.ragFiles[name]}}
			n++
		}
		reply(w, 200, map[string]any{"registration": map[string]any{"issues": issues}, "pipeline_execution": map[string]any{"source_count": n}})
	case "/api/data_sources/data.sources.get":
		out := []any{}
		for _, s := range f.ragSources {
			// Like the RAG service, list only the requested source type (documents have no source_type here).
			if st, _ := s["source_type"].(string); st == "" || strings.EqualFold(st, r.URL.Query().Get("source_type")) {
				out = append(out, s)
			}
		}
		reply(w, 200, map[string]any{"sources": out})
	case "/api/data_sources/data.source.details.get":
		s, ok := f.ragSources[r.URL.Query().Get("source_id")]
		if !ok {
			reply(w, 404, map[string]any{"success": false})
			return
		}
		reply(w, 200, map[string]any{"success": true, "source": s})
	case "/api/data_sources/data.source.delete":
		for _, id := range body["pipeline_ids"].([]any) {
			delete(f.ragSources, id.(string))
		}
		reply(w, 200, map[string]any{})
	default:
		reply(w, 404, map[string]any{"error": "unknown path " + r.URL.Path})
	}
}

// ragSourceNames returns the names and md5 of the RAG sources.
func (f *fakeMAS) ragSourceNames() map[string]string {
	f.mu.Lock()
	defer f.mu.Unlock()
	out := map[string]string{}
	for _, s := range f.ragSources {
		if md5, ok := s["type_data"].(map[string]any)["md5"].(string); ok {
			out[s["source_name"].(string)] = md5
		}
	}
	return out
}

// ragSyncCount returns how many times a source was (re)synced.
func (f *fakeMAS) ragSyncCount(id string) int {
	f.mu.Lock()
	defer f.mu.Unlock()
	return f.ragSyncs[id]
}

func (f *fakeMAS) hasRAGSource(id string) bool {
	f.mu.Lock()
	defer f.mu.Unlock()
	_, ok := f.ragSources[id]
	return ok
}
