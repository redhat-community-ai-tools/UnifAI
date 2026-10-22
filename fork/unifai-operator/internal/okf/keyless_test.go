package okf

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	ocispec "github.com/opencontainers/image-spec/specs-go/v1"
)

// The fixtures are a real dev-signed zuno-demo-agents artifact (quay.io/zuno/okf-tekos): the cosign
// signature image manifest, its simple-signing payload and the public Sigstore trusted root.
const keylessDigest = "sha256:bf429d3e6173781f10c858ed81a7f7c23073d9b0ba7ddd1044651d3868fcadba"

var keylessID = KeylessIdentity{
	Issuer:        "https://token.actions.githubusercontent.com",
	SubjectRegExp: `^https://github\.com/startxfr/zuno-demo-agents/\.github/workflows/publish-dev\.yml@refs/heads/(devel|main)$`,
}

func keylessFixtures(t *testing.T) (root []byte, sigs []KeylessSignature) {
	t.Helper()
	dir := filepath.Join("testdata", "keyless")
	root, err := os.ReadFile(filepath.Join(dir, "trusted_root.json"))
	if err != nil {
		t.Fatal(err)
	}
	manifest, err := os.ReadFile(filepath.Join(dir, "sig-manifest.json"))
	if err != nil {
		t.Fatal(err)
	}
	payload, err := os.ReadFile(filepath.Join(dir, "payload.json"))
	if err != nil {
		t.Fatal(err)
	}
	sigs, err = DecodeKeylessSignatures(context.Background(), manifest, func(context.Context, ocispec.Descriptor) ([]byte, error) { return payload, nil })
	if err != nil {
		t.Fatal(err)
	}
	return root, sigs
}

func TestVerifyKeylessAcceptsARealDevSignature(t *testing.T) {
	root, sigs := keylessFixtures(t)
	subject, err := VerifyKeyless(root, keylessDigest, sigs, keylessID)
	if err != nil {
		t.Fatal(err)
	}
	if subject == "" {
		t.Fatal("no signer subject returned")
	}
	t.Log("signer:", subject)
}

func TestVerifyKeylessRefusesAWrongIdentity(t *testing.T) {
	root, sigs := keylessFixtures(t)
	for name, id := range map[string]KeylessIdentity{
		"release workflow only": {Issuer: keylessID.Issuer, SubjectRegExp: `^https://github\.com/startxfr/zuno-demo-agents/\.github/workflows/publish\.yml@refs/tags/v`},
		"another issuer":        {Issuer: "https://accounts.google.com", SubjectRegExp: keylessID.SubjectRegExp},
		"another repository":    {Issuer: keylessID.Issuer, SubjectRegExp: `^https://github\.com/someone/else/`},
	} {
		if _, err := VerifyKeyless(root, keylessDigest, sigs, id); err == nil {
			t.Errorf("%s: accepted", name)
		}
	}
}

func TestVerifyKeylessRefusesAnotherDigest(t *testing.T) {
	root, sigs := keylessFixtures(t)
	if _, err := VerifyKeyless(root, "sha256:"+string(make([]byte, 0))+"0000000000000000000000000000000000000000000000000000000000000000", sigs, keylessID); err == nil {
		t.Fatal("a signature for another artifact was accepted")
	}
}

func TestVerifyKeylessRefusesATamperedSignature(t *testing.T) {
	root, sigs := keylessFixtures(t)
	bad := make([]KeylessSignature, len(sigs))
	copy(bad, sigs)
	for i := range bad {
		var p map[string]any
		_ = json.Unmarshal(bad[i].Payload, &p)
		bad[i].Payload = append([]byte(nil), bad[i].Payload...)
		bad[i].Payload[len(bad[i].Payload)-2] ^= 1 // the payload no longer matches what was signed
	}
	if _, err := VerifyKeyless(root, keylessDigest, bad, keylessID); err == nil {
		t.Fatal("a tampered payload was accepted")
	}
}

func TestVerifyKeylessNeedsAnIdentity(t *testing.T) {
	root, sigs := keylessFixtures(t)
	if _, err := VerifyKeyless(root, keylessDigest, sigs, KeylessIdentity{}); err == nil {
		t.Fatal("an empty identity was accepted")
	}
}
