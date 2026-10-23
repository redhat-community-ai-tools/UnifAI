//go:build e2e

package e2e

import (
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	"k8s.io/apimachinery/pkg/api/meta"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

// A real OKF artifact signed keyless by the zuno-demo-agents release workflow (public, anonymous pull), and the
// public Sigstore trusted root the operator unit tests use (internal/okf/testdata/keyless).
const (
	keylessArtifact = "quay.io/zuno/okf-tekos@sha256:bf429d3e6173781f10c858ed81a7f7c23073d9b0ba7ddd1044651d3868fcadba"
	keylessIssuer   = "https://token.actions.githubusercontent.com"
	keylessSubject  = `^https://github\.com/startxfr/zuno-demo-agents/\.github/workflows/publish\.yml@refs/tags/v`
	trustedRootFile = "../../internal/okf/testdata/keyless/trusted_root.json"
)

// keylessBundle is an UnifaiAgentBundle of keylessArtifact checked against subject.
func keylessBundle(ns, name, subject string) *unifaiv1.UnifaiAgentBundle {
	return &unifaiv1.UnifaiAgentBundle{ObjectMeta: metav1.ObjectMeta{Name: name, Namespace: ns}, Spec: unifaiv1.UnifaiAgentBundleSpec{
		Source: unifaiv1.BundleSource{OCI: unifaiv1.OCIBundleSource{Reference: keylessArtifact}},
		Verify: unifaiv1.BundleVerify{Keyless: &unifaiv1.KeylessVerify{Issuer: keylessIssuer, SubjectRegExp: subject,
			TrustedRootRef: unifaiv1.SecretKeySelector{Name: "e2e-sigstore-trusted-root", Key: "trusted_root.json"}}},
		Ceilings:    unifaiv1.BundleCeilings{MinClassification: "C1"},
		Entitlement: "GatewayOnly",
		LLM: unifaiv1.BundleLLM{ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{
			"model_name": "mock-model", "base_url": "http://e2e-llm:8000/v1", "api_key": "EMPTY"})}},
	}}
}

// checkAgentBundleKeyless pulls keylessArtifact through two UnifaiAgentBundles: the release identity verifies it
// (Fulcio chain, SCT, Rekor entry, issuer and subject, offline against the trusted root), another workflow
// identity is refused before anything is parsed or emitted.
func checkAgentBundleKeyless(t *testing.T, ns string) {
	t.Helper()
	root, err := os.ReadFile(trustedRootFile)
	must(t, err)
	create(t, &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: "e2e-sigstore-trusted-root", Namespace: ns},
		Data: map[string][]byte{"trusted_root.json": root}})

	verified := func(b *unifaiv1.UnifaiAgentBundle) *metav1.Condition {
		var c *metav1.Condition
		eventually(t, b.Name+" verification", 5*time.Minute, func() (bool, string) {
			if err := getObj(b); err != nil {
				return false, err.Error()
			}
			c = meta.FindStatusCondition(b.Status.Conditions, "Verified")
			return c != nil, b.Status.Phase + " " + b.Status.Message
		})
		return c
	}

	good := keylessBundle(ns, "e2e-keyless", keylessSubject)
	create(t, good)
	if c := verified(good); c.Status != metav1.ConditionTrue {
		t.Fatalf("release-signed artifact not verified: %s", c.Message)
	}
	if !regexp.MustCompile(keylessSubject).MatchString(good.Status.Signer) || good.Status.ResolvedDigest == "" ||
		good.Status.OKFVersion == "" {
		t.Errorf("verified bundle status: signer %q, digest %q, okf %q", good.Status.Signer, good.Status.ResolvedDigest,
			good.Status.OKFVersion)
	}
	// Verified, then refused by the empty spec.ceilings: the checks after the signature run on its content.
	if good.Status.Phase != "Error" || !strings.Contains(good.Status.Message, "ceilings") || len(good.Status.Children) > 0 {
		t.Errorf("verified bundle beyond its ceilings: phase %s %q, children %v", good.Status.Phase, good.Status.Message,
			good.Status.Children)
	}

	// The artifact also carries a publish-dev.yml signature: only another repository is a wrong signer.
	bad := keylessBundle(ns, "e2e-keyless-wrong-signer", `^https://github\.com/startxfr/another-repository/`)
	create(t, bad)
	if c := verified(bad); c.Status != metav1.ConditionFalse {
		t.Fatalf("artifact accepted for another workflow identity: %s", c.Message)
	}
	if bad.Status.Phase != "Error" || bad.Status.Verified || len(bad.Status.Children) > 0 || bad.Status.OKFVersion != "" {
		t.Errorf("refused bundle: phase %s, verified %v, children %v, okf %q (nothing may be parsed or emitted)",
			bad.Status.Phase, bad.Status.Verified, bad.Status.Children, bad.Status.OKFVersion)
	}
}

func getObj(o client.Object) error { return c.Get(ctx, client.ObjectKeyFromObject(o), o) }
