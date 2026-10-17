package okf

import (
	"crypto/ecdsa"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
	"encoding/pem"
	"fmt"
	"strings"
)

// ignoredNames never affect the digest (same set as zuno-demo's platform/supply-chain/sign_okf_bundle.py).
var ignoredNames = map[string]bool{"__pycache__": true, ".DS_Store": true}

// Digest reproduces sign_okf_bundle.py's compute_digest: sorted "<relative path>:<sha256 of content>" lines,
// newline-terminated, hashed with SHA-256. Paths are ordered by their components, as Python sorts Path objects.
func Digest(files Files) (string, error) {
	kept := Files{}
	for p, c := range files {
		if ignored(p) {
			continue
		}
		kept[p] = c
	}
	if len(kept) == 0 {
		return "", fmt.Errorf("bundle contains no files to digest")
	}
	var sb strings.Builder
	for _, p := range kept.SortedPaths() {
		h := sha256.Sum256(kept[p])
		sb.WriteString(p)
		sb.WriteString(":")
		sb.WriteString(hex.EncodeToString(h[:]))
		sb.WriteString("\n")
	}
	sum := sha256.Sum256([]byte(sb.String()))
	return hex.EncodeToString(sum[:]), nil
}

func ignored(p string) bool {
	for _, part := range strings.Split(p, "/") {
		if ignoredNames[part] {
			return true
		}
	}
	return false
}

// lessByParts orders slash paths component by component (Python's PurePosixPath ordering).
func lessByParts(a, b string) bool {
	pa, pb := strings.Split(a, "/"), strings.Split(b, "/")
	for i := 0; i < len(pa) && i < len(pb); i++ {
		if pa[i] != pb[i] {
			return pa[i] < pb[i]
		}
	}
	return len(pa) < len(pb)
}

// VerifySignature checks a `cosign sign-blob` signature (base64 of an ASN.1 ECDSA signature, as written by
// --output-signature) over the blob "<digest>\n" against a PEM public key: the same check as
// `cosign verify-blob --key`, without the cosign binary or any network access.
func VerifySignature(digest string, signature []byte, publicKeyPEM []byte) error {
	block, _ := pem.Decode(publicKeyPEM)
	if block == nil {
		return fmt.Errorf("public key is not PEM")
	}
	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return fmt.Errorf("public key: %w", err)
	}
	ec, ok := pub.(*ecdsa.PublicKey)
	if !ok {
		return fmt.Errorf("public key type %T is not supported (ECDSA only)", pub)
	}
	der, err := base64.StdEncoding.DecodeString(strings.TrimSpace(string(signature)))
	if err != nil {
		return fmt.Errorf("signature is not base64: %w", err)
	}
	h := sha256.Sum256([]byte(digest + "\n"))
	if !ecdsa.VerifyASN1(ec, h[:], der) {
		return fmt.Errorf("signature does not match bundle digest %s", digest)
	}
	return nil
}
