package okf

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"

	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
)

// tekosDigest is what zuno-demo's `sign_okf_bundle.py digest` prints for testdata/tekos (a copy of
// agents/tekos at zuno-demo 7009a65f); testdata/tekos.sig is a real `cosign sign-blob` signature of it
// made with the throwaway key testdata/fixture-cosign.pub.
const tekosDigest = "5d12482fa2a04ef926506709a2586266864e0087a8ec52f1b0a11f321faa781c"

func loadTree(t *testing.T, root string) Files {
	t.Helper()
	files := Files{}
	err := filepath.WalkDir(root, func(p string, d fs.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return err
		}
		b, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		rel, _ := filepath.Rel(root, p)
		files[filepath.ToSlash(rel)] = b
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	return files
}

func read(t *testing.T, p string) []byte {
	t.Helper()
	b, err := os.ReadFile(p)
	if err != nil {
		t.Fatal(err)
	}
	return b
}

func TestDigestMatchesSignOkfBundlePy(t *testing.T) {
	got, err := Digest(loadTree(t, "testdata/tekos"))
	if err != nil {
		t.Fatal(err)
	}
	if got != tekosDigest {
		t.Fatalf("digest %s, want %s", got, tekosDigest)
	}
}

func TestDigestIgnoresNoiseAndSortsByComponents(t *testing.T) {
	a := Files{"a/b.md": []byte("1"), "a-b.md": []byte("2"), "x/__pycache__/c.pyc": []byte("noise")}
	b := Files{"a/b.md": []byte("1"), "a-b.md": []byte("2")}
	da, _ := Digest(a)
	db, _ := Digest(b)
	if da != db {
		t.Fatal("ignored names changed the digest")
	}
	// Python orders Path objects by components: "a/b.md" (parts a, b.md) sorts before "a-b.md".
	if got := (Files{"a-b.md": nil, "a/b.md": nil}).SortedPaths(); got[0] != "a/b.md" {
		t.Fatalf("order %v", got)
	}
}

func TestVerifyRealCosignSignature(t *testing.T) {
	pub, sig := read(t, "testdata/fixture-cosign.pub"), read(t, "testdata/tekos.sig")
	if err := VerifySignature(tekosDigest, sig, pub); err != nil {
		t.Fatalf("real cosign signature rejected: %v", err)
	}
	tampered := loadTree(t, "testdata/tekos")
	tampered["agent.okf.md"] = append(tampered["agent.okf.md"], '\n')
	d, _ := Digest(tampered)
	if err := VerifySignature(d, sig, pub); err == nil {
		t.Fatal("tampered bundle verified")
	}
	if err := VerifySignature(tekosDigest, []byte("not base64!"), pub); err == nil {
		t.Fatal("garbage signature verified")
	}
}

func TestParseTekos(t *testing.T) {
	b, err := Parse(loadTree(t, "testdata/tekos"))
	if err != nil {
		t.Fatal(err)
	}
	if b.Name != "tekos" || b.PrimaryTask != "answer-technical-question" || b.Classification != C1 ||
		b.GraphShape != ShapeRetrieveReasonRespond || len(b.Tasks) != 4 {
		t.Fatalf("unexpected bundle %+v", b)
	}
	var primary Task
	for _, tk := range b.Tasks {
		if tk.Name == b.PrimaryTask {
			primary = tk
		}
	}
	if !strings.HasPrefix(b.SystemMessage(primary), "You are Tekos") {
		t.Fatalf("primary task should use prompts/answer-technical-question.md, got %.60q", b.SystemMessage(primary))
	}
	if len(primary.AllowedKnowledge) == 0 || len(primary.AllowedTools) == 0 {
		t.Fatalf("primary task lost its tools/knowledge: %+v", primary)
	}
	joined := strings.Join(b.Unmapped, "\n")
	if b.OKFVersion != "v0.2" || len(b.AccessGroups) != 1 || len(b.DeclaredTools()) < 5 || b.DeclaredKnowledge()[0] != "knowledge.project" {
		t.Fatalf("declarations: %+v tools=%v knowledge=%v", b.AccessGroups, b.DeclaredTools(), b.DeclaredKnowledge())
	}
	for _, want := range []string{"allowed_tools", "zuno.rag.top_k"} {
		if !strings.Contains(joined, want) {
			t.Errorf("unmapped list misses %s:\n%s", want, joined)
		}
	}
}

func TestParseRejectsBrokenBundles(t *testing.T) {
	base := loadTree(t, "testdata/tekos")
	missing := Files{}
	for k, v := range base {
		missing[k] = v
	}
	delete(missing, "tasks/write-code.md")
	if _, err := Parse(missing); err == nil || !strings.Contains(err.Error(), "write-code") {
		t.Fatalf("missing task file accepted: %v", err)
	}
	if _, err := Parse(Files{"README.md": []byte("x")}); err == nil {
		t.Fatal("bundle without agent.okf.md accepted")
	}
}

func TestEffectiveClassificationOnlyRaises(t *testing.T) {
	if l, err := Effective(C2, ""); err != nil || l != C2 {
		t.Fatalf("default: %v %v", l, err)
	}
	if l, err := Effective(C1, "C3"); err != nil || l != C3 {
		t.Fatalf("raise: %v %v", l, err)
	}
	if _, err := Effective(C2, "C1"); err == nil {
		t.Fatal("lowering accepted")
	}
	if _, err := Effective(C1, "C9"); err == nil {
		t.Fatal("unknown level accepted")
	}
}

func TestSplitDigestRef(t *testing.T) {
	d := "sha256:" + strings.Repeat("a", 64)
	if repo, dg, err := SplitDigestRef("quay.io/zuno/okf-tekos:v1@" + d); err != nil || repo != "quay.io/zuno/okf-tekos" || dg != d {
		t.Fatalf("%s %s %v", repo, dg, err)
	}
	for _, bad := range []string{"quay.io/zuno/okf-tekos:latest", "quay.io/zuno/okf-tekos@sha256:abc", "quay.io/x@md5:" + strings.Repeat("a", 64)} {
		if _, _, err := SplitDigestRef(bad); err == nil {
			t.Errorf("%s accepted", bad)
		}
	}
}

func tarGz(t *testing.T, entries map[string]string, extra func(*tar.Writer)) []byte {
	t.Helper()
	var buf bytes.Buffer
	zw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(zw)
	for name, body := range entries {
		_ = tw.WriteHeader(&tar.Header{Name: name, Mode: 0o644, Size: int64(len(body)), Typeflag: tar.TypeReg})
		_, _ = tw.Write([]byte(body))
	}
	if extra != nil {
		extra(tw)
	}
	_ = tw.Close()
	_ = zw.Close()
	return buf.Bytes()
}

func TestUntarRejectsEscapesAndLinks(t *testing.T) {
	if _, err := Untar(tarGz(t, map[string]string{"../evil.md": "x"}, nil)); err == nil {
		t.Fatal("path escape accepted")
	}
	link := func(tw *tar.Writer) {
		_ = tw.WriteHeader(&tar.Header{Name: "l", Linkname: "/etc/passwd", Typeflag: tar.TypeSymlink})
	}
	if _, err := Untar(tarGz(t, map[string]string{"a.md": "x"}, link)); err == nil {
		t.Fatal("symlink accepted")
	}
	files, err := Untar(tarGz(t, map[string]string{"./tasks/a.md": "x"}, nil))
	if err != nil || string(files["tasks/a.md"]) != "x" {
		t.Fatalf("%v %v", files, err)
	}
}

func TestDecodeArtifact(t *testing.T) {
	layer := tarGz(t, map[string]string{"agent.okf.md": "x"}, nil)
	desc := ocispec.Descriptor{MediaType: LayerMediaType, Size: int64(len(layer))}
	m := ocispec.Manifest{ArtifactType: ArtifactType, Layers: []ocispec.Descriptor{desc},
		Annotations: map[string]string{SignatureAnnotation: "c2ln"}}
	mb, _ := json.Marshal(m)
	fetch := func(context.Context, ocispec.Descriptor) ([]byte, error) { return layer, nil }
	a, err := decodeArtifact(context.Background(), mb, "sha256:m", fetch)
	if err != nil || string(a.Signature) != "c2ln" || string(a.Files["agent.okf.md"]) != "x" {
		t.Fatalf("%+v %v", a, err)
	}
	delete(m.Annotations, SignatureAnnotation)
	mb, _ = json.Marshal(m)
	if _, err := decodeArtifact(context.Background(), mb, "sha256:m", fetch); err == nil {
		t.Fatal("unsigned artifact accepted")
	}
}

func TestValidateSchemas(t *testing.T) {
	files := loadTree(t, "testdata/tekos")
	if err := ValidateSchemas(files); err != nil {
		t.Fatalf("tekos should satisfy the embedded schemas: %v", err)
	}
	bad := Files{}
	for k, v := range files {
		bad[k] = v
	}
	bad["tasks/write-code.md"] = []byte(strings.Replace(string(files["tasks/write-code.md"]), "type: task", "type: task\nunexpected_field: 1", 1))
	if err := ValidateSchemas(bad); err == nil || !strings.Contains(err.Error(), "tasks/write-code.md") {
		t.Fatalf("an unknown frontmatter field passed: %v", err)
	}
	old := Files{}
	for k, v := range files {
		old[k] = v
	}
	old["agent.okf.md"] = []byte(strings.Replace(string(files["agent.okf.md"]), "okf_version: v0.2", "okf_version: v0.1", 1))
	if err := ValidateSchemas(old); err == nil || !strings.Contains(err.Error(), "okf_version") {
		t.Fatalf("an older okf_version passed: %v", err)
	}
}
