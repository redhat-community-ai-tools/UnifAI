package okf

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"path"
	"strings"

	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
	"oras.land/oras-go/v2/content"
	"oras.land/oras-go/v2/registry/remote"
	"oras.land/oras-go/v2/registry/remote/auth"
	"oras.land/oras-go/v2/registry/remote/retry"
)

// OCI layout of a published bundle (zuno-demo `make d3 sign agents` pushes it after signing):
// one gzipped tar layer holding the agents/<name>/ tree, and the cosign signature of its digest
// as a manifest annotation.
const (
	ArtifactType        = "application/vnd.zuno.okf.bundle.v1"
	LayerMediaType      = "application/vnd.zuno.okf.bundle.v1.tar+gzip"
	SignatureAnnotation = "zuno.okf.signature"
	DigestAnnotation    = "zuno.okf.digest"

	// v2 (zuno-demo-agents, ADR-0578): runtime files only, signed keyless as a whole artifact, so the
	// manifest carries no signature annotation.
	ArtifactTypeV2   = "application/vnd.zuno.okf.bundle.v2"
	LayerMediaTypeV2 = "application/vnd.zuno.okf.bundle.v2.tar+gzip"

	maxManifestBytes = 1 << 20
	maxLayerBytes    = 16 << 20
	maxBundleBytes   = 32 << 20
)

// Credential authenticates a pull (nil = anonymous).
type Credential struct {
	Username, Password string
}

// Artifact is a pulled bundle.
type Artifact struct {
	Files     Files
	Signature []byte
	// ManifestDigest is the digest the reference pinned.
	ManifestDigest string
	// V2 marks a keyless-signed artifact (no Signature): its signature is the cosign image next to it.
	V2 bool
}

// Fetcher pulls a bundle; replaceable in tests.
type Fetcher func(ctx context.Context, ref string, cred *Credential) (*Artifact, error)

// SplitDigestRef splits `registry/repo@sha256:...`, refusing tag references: a bundle is pinned by digest.
func SplitDigestRef(ref string) (repo, digest string, err error) {
	i := strings.LastIndex(ref, "@")
	if i < 0 || !strings.HasPrefix(ref[i+1:], "sha256:") || len(ref[i+1:]) != len("sha256:")+64 {
		return "", "", fmt.Errorf("reference %q is not pinned by a sha256 digest", ref)
	}
	repo = ref[:i]
	if j := strings.LastIndex(repo, ":"); j > strings.LastIndex(repo, "/") {
		repo = repo[:j] // a tag next to the digest is ignored: the digest wins
	}
	return repo, ref[i+1:], nil
}

// Fetch pulls a bundle from an OCI registry with oras-go and verifies every blob against its descriptor.
func Fetch(ctx context.Context, ref string, cred *Credential) (*Artifact, error) {
	repoName, dgst, err := SplitDigestRef(ref)
	if err != nil {
		return nil, err
	}
	repo, err := remote.NewRepository(repoName)
	if err != nil {
		return nil, fmt.Errorf("repository %s: %w", repoName, err)
	}
	client := &auth.Client{Client: retry.DefaultClient, Cache: auth.NewCache()}
	if cred != nil {
		client.Credential = auth.StaticCredential(repo.Reference.Registry, auth.Credential{Username: cred.Username, Password: cred.Password})
	}
	repo.Client = client

	mdesc, rc, err := repo.FetchReference(ctx, dgst)
	if err != nil {
		return nil, fmt.Errorf("fetch manifest %s: %w", ref, err)
	}
	if mdesc.Size > maxManifestBytes {
		_ = rc.Close()
		return nil, fmt.Errorf("manifest of %s is too large (%d bytes)", ref, mdesc.Size)
	}
	mb, err := content.ReadAll(rc, mdesc)
	_ = rc.Close()
	if err != nil {
		return nil, fmt.Errorf("read manifest %s: %w", ref, err)
	}
	return decodeArtifact(ctx, mb, mdesc.Digest.String(), func(ctx context.Context, d ocispec.Descriptor) ([]byte, error) {
		r, err := repo.Fetch(ctx, d)
		if err != nil {
			return nil, err
		}
		defer func() { _ = r.Close() }()
		return content.ReadAll(r, d)
	})
}

func decodeArtifact(ctx context.Context, manifest []byte, manifestDigest string,
	fetch func(context.Context, ocispec.Descriptor) ([]byte, error)) (*Artifact, error) {
	var m ocispec.Manifest
	if err := json.Unmarshal(manifest, &m); err != nil {
		return nil, fmt.Errorf("manifest: %w", err)
	}
	v2 := m.ArtifactType == ArtifactTypeV2 || m.Config.MediaType == ArtifactTypeV2
	if !v2 && m.ArtifactType != ArtifactType && m.Config.MediaType != ArtifactType {
		return nil, fmt.Errorf("artifact type is %q, want %s or %s", m.ArtifactType, ArtifactType, ArtifactTypeV2)
	}
	layerType := LayerMediaType
	sig := m.Annotations[SignatureAnnotation]
	if v2 {
		layerType = LayerMediaTypeV2
	} else if sig == "" {
		return nil, fmt.Errorf("manifest has no %s annotation: the bundle is unsigned", SignatureAnnotation)
	}
	var layer *ocispec.Descriptor
	for i := range m.Layers {
		if m.Layers[i].MediaType == layerType {
			if layer != nil {
				return nil, fmt.Errorf("manifest has more than one %s layer", layerType)
			}
			layer = &m.Layers[i]
		}
	}
	if layer == nil {
		return nil, fmt.Errorf("manifest has no %s layer", layerType)
	}
	if layer.Size > maxLayerBytes {
		return nil, fmt.Errorf("bundle layer is too large (%d bytes)", layer.Size)
	}
	blob, err := fetch(ctx, *layer)
	if err != nil {
		return nil, fmt.Errorf("fetch bundle layer: %w", err)
	}
	files, err := Untar(blob)
	if err != nil {
		return nil, err
	}
	return &Artifact{Files: files, Signature: []byte(sig), ManifestDigest: manifestDigest, V2: v2}, nil
}

// Untar reads a gzipped tar of regular files. Paths are normalised and must stay inside the bundle.
func Untar(blob []byte) (Files, error) {
	zr, err := gzip.NewReader(bytes.NewReader(blob))
	if err != nil {
		return nil, fmt.Errorf("bundle layer is not gzip: %w", err)
	}
	tr := tar.NewReader(zr)
	files := Files{}
	var total int64
	for {
		h, err := tr.Next()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("bundle layer: %w", err)
		}
		switch h.Typeflag {
		case tar.TypeDir:
			continue
		case tar.TypeReg:
		default:
			return nil, fmt.Errorf("bundle entry %q is not a regular file", h.Name)
		}
		p := path.Clean(strings.TrimPrefix(h.Name, "./"))
		if p == "." || strings.HasPrefix(p, "../") || p == ".." || path.IsAbs(p) {
			return nil, fmt.Errorf("bundle entry %q escapes the bundle", h.Name)
		}
		if _, dup := files[p]; dup {
			return nil, fmt.Errorf("bundle entry %q appears twice", p)
		}
		total += h.Size
		if total > maxBundleBytes {
			return nil, fmt.Errorf("bundle is larger than %d bytes", maxBundleBytes)
		}
		b, err := io.ReadAll(io.LimitReader(tr, h.Size+1))
		if err != nil {
			return nil, fmt.Errorf("bundle entry %q: %w", p, err)
		}
		files[p] = b
	}
	if len(files) == 0 {
		return nil, fmt.Errorf("bundle layer is empty")
	}
	return files, nil
}
