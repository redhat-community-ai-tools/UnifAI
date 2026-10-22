package okf

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"fmt"
	"strings"

	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
	protocommon "github.com/sigstore/protobuf-specs/gen/pb-go/common/v1"
	protorekor "github.com/sigstore/protobuf-specs/gen/pb-go/rekor/v1"
	"github.com/sigstore/sigstore-go/pkg/bundle"
	"github.com/sigstore/sigstore-go/pkg/root"
	"github.com/sigstore/sigstore-go/pkg/verify"
	"oras.land/oras-go/v2/content"
	"oras.land/oras-go/v2/registry/remote"
	"oras.land/oras-go/v2/registry/remote/auth"
	"oras.land/oras-go/v2/registry/remote/retry"
)

// Keyless verification of a bundle published by zuno-demo-agents (ADR-0578): the cosign signature of the
// manifest digest is stored next to the artifact as the OCI image `sha256-<hex>.sig`, one layer per
// signature, each carrying the Fulcio certificate and the Rekor entry in annotations (cosign 2.x). The
// check is offline: Fulcio chain, Rekor signed entry timestamp and SCT against a trusted root the cluster
// holds, then the certificate identity (issuer and subject) against the CR.
const (
	SimpleSigningMediaType = "application/vnd.dev.cosign.simplesigning.v1+json"

	annSignature   = "dev.cosignproject.cosign/signature"
	annCertificate = "dev.sigstore.cosign/certificate"
	annBundle      = "dev.sigstore.cosign/bundle"

	maxSignatureLayers = 32
	maxPayloadBytes    = 64 << 10
)

// KeylessSignature is one cosign signature of an artifact: the simple-signing payload and its annotations.
type KeylessSignature struct {
	Payload     []byte
	Signature   string // base64, as cosign stores it
	Certificate string // PEM of the Fulcio leaf certificate
	Bundle      string // JSON of the Rekor bundle ({"SignedEntryTimestamp","Payload"})
}

// KeylessIdentity is what the CR accepts as signer.
type KeylessIdentity struct {
	Issuer        string
	SubjectRegExp string
}

// FetchKeylessSignatures pulls the cosign signature image of the artifact `repo@digest`.
func FetchKeylessSignatures(ctx context.Context, ref string, cred *Credential) ([]KeylessSignature, error) {
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
	tag := strings.Replace(dgst, ":", "-", 1) + ".sig"
	mdesc, rc, err := repo.FetchReference(ctx, tag)
	if err != nil {
		return nil, fmt.Errorf("no cosign signature for %s (tag %s): %w", ref, tag, err)
	}
	if mdesc.Size > 8*maxManifestBytes {
		_ = rc.Close()
		return nil, fmt.Errorf("signature manifest of %s is too large (%d bytes)", ref, mdesc.Size)
	}
	mb, err := content.ReadAll(rc, mdesc)
	_ = rc.Close()
	if err != nil {
		return nil, fmt.Errorf("read signature manifest: %w", err)
	}
	return DecodeKeylessSignatures(ctx, mb, func(ctx context.Context, d ocispec.Descriptor) ([]byte, error) {
		r, err := repo.Fetch(ctx, d)
		if err != nil {
			return nil, err
		}
		defer func() { _ = r.Close() }()
		return content.ReadAll(r, d)
	})
}

// DecodeKeylessSignatures reads the keyless cosign signatures out of a signature image manifest; fetch returns a
// layer blob.
func DecodeKeylessSignatures(ctx context.Context, manifest []byte,
	fetch func(context.Context, ocispec.Descriptor) ([]byte, error)) ([]KeylessSignature, error) {
	var m ocispec.Manifest
	if err := json.Unmarshal(manifest, &m); err != nil {
		return nil, fmt.Errorf("signature manifest: %w", err)
	}
	if len(m.Layers) > maxSignatureLayers {
		return nil, fmt.Errorf("signature manifest has %d layers, at most %d are read", len(m.Layers), maxSignatureLayers)
	}
	payloads := map[string][]byte{}
	out := make([]KeylessSignature, 0, len(m.Layers))
	for _, l := range m.Layers {
		if l.MediaType != SimpleSigningMediaType || l.Annotations[annSignature] == "" || l.Annotations[annCertificate] == "" {
			continue // a key-based or incomplete signature: not usable keyless
		}
		if l.Size > maxPayloadBytes {
			continue
		}
		p, ok := payloads[l.Digest.String()]
		if !ok {
			var err error
			if p, err = fetch(ctx, l); err != nil {
				return nil, fmt.Errorf("fetch signature payload: %w", err)
			}
			payloads[l.Digest.String()] = p
		}
		out = append(out, KeylessSignature{Payload: p, Signature: l.Annotations[annSignature],
			Certificate: l.Annotations[annCertificate], Bundle: l.Annotations[annBundle]})
	}
	if len(out) == 0 {
		return nil, errors.New("the signature image holds no keyless cosign signature")
	}
	return out, nil
}

// VerifyKeyless accepts the artifact (manifest digest) when at least one signature verifies against the
// trusted root and was made by an accepted identity. It returns the signer's certificate subject.
func VerifyKeyless(trustedRootJSON []byte, manifestDigest string, sigs []KeylessSignature, id KeylessIdentity) (string, error) {
	if id.Issuer == "" || id.SubjectRegExp == "" {
		return "", errors.New("keyless verification needs an issuer and a subject regular expression")
	}
	tr, err := root.NewTrustedRootFromJSON(trustedRootJSON)
	if err != nil {
		return "", fmt.Errorf("trusted root: %w", err)
	}
	verifier, err := verify.NewVerifier(tr, verify.WithSignedCertificateTimestamps(1),
		verify.WithTransparencyLog(1), verify.WithObserverTimestamps(1))
	if err != nil {
		return "", fmt.Errorf("verifier: %w", err)
	}
	certID, err := verify.NewShortCertificateIdentity(id.Issuer, "", "", id.SubjectRegExp)
	if err != nil {
		return "", fmt.Errorf("certificate identity: %w", err)
	}
	var reasons []string
	for i, s := range sigs {
		if err := payloadNamesDigest(s.Payload, manifestDigest); err != nil {
			reasons = append(reasons, fmt.Sprintf("signature %d: %v", i, err))
			continue
		}
		b, err := cosignBundle(s)
		if err != nil {
			reasons = append(reasons, fmt.Sprintf("signature %d: %v", i, err))
			continue
		}
		res, err := verifier.Verify(b, verify.NewPolicy(verify.WithArtifact(bytes.NewReader(s.Payload)), verify.WithCertificateIdentity(certID)))
		if err != nil {
			reasons = append(reasons, fmt.Sprintf("signature %d: %v", i, err))
			continue
		}
		subject := ""
		if res.Signature != nil && res.Signature.Certificate != nil {
			subject = res.Signature.Certificate.SubjectAlternativeName
		}
		return subject, nil
	}
	return "", fmt.Errorf("no signature of %s verifies for issuer %q and subject %q: %s", manifestDigest, id.Issuer, id.SubjectRegExp, strings.Join(reasons, "; "))
}

// payloadNamesDigest checks the signed simple-signing payload is about this very manifest.
func payloadNamesDigest(payload []byte, manifestDigest string) error {
	var p struct {
		Critical struct {
			Image struct {
				Digest string `json:"docker-manifest-digest"`
			} `json:"image"`
			Type string `json:"type"`
		} `json:"critical"`
	}
	if err := json.Unmarshal(payload, &p); err != nil {
		return fmt.Errorf("payload: %w", err)
	}
	if p.Critical.Type != "cosign container image signature" {
		return fmt.Errorf("payload type %q is not a cosign container image signature", p.Critical.Type)
	}
	if p.Critical.Image.Digest != manifestDigest {
		return fmt.Errorf("signature is for %s, not %s", p.Critical.Image.Digest, manifestDigest)
	}
	return nil
}

// cosignBundle turns the annotations of a cosign signature layer into a Sigstore bundle (message
// signature + Fulcio certificate + Rekor entry with its signed entry timestamp).
func cosignBundle(s KeylessSignature) (*bundle.Bundle, error) {
	sig, err := base64.StdEncoding.DecodeString(s.Signature)
	if err != nil {
		return nil, fmt.Errorf("signature is not base64: %w", err)
	}
	blk, _ := pem.Decode([]byte(s.Certificate))
	if blk == nil {
		return nil, errors.New("certificate annotation is not PEM")
	}
	if s.Bundle == "" {
		return nil, errors.New("signature has no Rekor bundle: a transparency log entry is required")
	}
	var rb struct {
		SignedEntryTimestamp string `json:"SignedEntryTimestamp"`
		Payload              struct {
			Body           string `json:"body"`
			IntegratedTime int64  `json:"integratedTime"`
			LogIndex       int64  `json:"logIndex"`
			LogID          string `json:"logID"`
		} `json:"Payload"`
	}
	if err := json.Unmarshal([]byte(s.Bundle), &rb); err != nil {
		return nil, fmt.Errorf("rekor bundle: %w", err)
	}
	set, err := base64.StdEncoding.DecodeString(rb.SignedEntryTimestamp)
	if err != nil {
		return nil, fmt.Errorf("signed entry timestamp: %w", err)
	}
	body, err := base64.StdEncoding.DecodeString(rb.Payload.Body)
	if err != nil {
		return nil, fmt.Errorf("rekor body: %w", err)
	}
	logID, err := hex.DecodeString(rb.Payload.LogID)
	if err != nil {
		return nil, fmt.Errorf("rekor log id: %w", err)
	}
	var entry struct {
		APIVersion string `json:"apiVersion"`
		Kind       string `json:"kind"`
	}
	if err := json.Unmarshal(body, &entry); err != nil {
		return nil, fmt.Errorf("rekor body: %w", err)
	}
	digest := sha256.Sum256(s.Payload)
	pb := &protobundle.Bundle{
		MediaType: "application/vnd.dev.sigstore.bundle+json;version=0.1",
		VerificationMaterial: &protobundle.VerificationMaterial{
			Content: &protobundle.VerificationMaterial_X509CertificateChain{X509CertificateChain: &protocommon.X509CertificateChain{
				Certificates: []*protocommon.X509Certificate{{RawBytes: blk.Bytes}}}},
			TlogEntries: []*protorekor.TransparencyLogEntry{{
				LogIndex:          rb.Payload.LogIndex,
				LogId:             &protocommon.LogId{KeyId: logID},
				KindVersion:       &protorekor.KindVersion{Kind: entry.Kind, Version: entry.APIVersion},
				IntegratedTime:    rb.Payload.IntegratedTime,
				InclusionPromise:  &protorekor.InclusionPromise{SignedEntryTimestamp: set},
				CanonicalizedBody: body,
			}},
		},
		Content: &protobundle.Bundle_MessageSignature{MessageSignature: &protocommon.MessageSignature{
			MessageDigest: &protocommon.HashOutput{Algorithm: protocommon.HashAlgorithm_SHA2_256, Digest: digest[:]},
			Signature:     sig}},
	}
	return bundle.NewBundle(pb)
}
