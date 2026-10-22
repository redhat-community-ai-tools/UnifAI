//go:build e2e

package e2e

// Per-user access to a team workspace, end to end: a user whose Keycloak token carries the team's group sees the
// team-owned objects, a user without the group is refused, and the group-bound team is listed for the first user only.
//
// It needs a stack with a managed Keycloak (RHBK) and an identity service that derives the groups from the verified
// access token (DIRECTORY_PROVIDER=oidc-claims). Slow: E2E_TEAM_ACCESS=1, on a cluster able to install RHBK
// (same requirement as TestManagedKeycloak).
//
//	E2E_TEAM_ACCESS=1 go test -tags e2e -count=1 -timeout 90m -v -run TestTeamGroupAccess ./test/e2e/
//
// Optional variables:
//
//	E2E_OIDC_JWKS_URL   JWKS URL the identity pod uses (default: the in-namespace Keycloak Service over plain HTTP)
//	E2E_KEYCLOAK_DOMAIN apps domain used to build the Keycloak host (default: spec.domain of the cluster Ingress config)
//	E2E_KEYCLOAK_ADMIN_SECRET  Secret holding the Keycloak bootstrap admin (keys username/password;
//	                    default unifai-keycloak-initial-admin, created by the RHBK operator)

import (
	"bytes"
	"context"
	"crypto/tls"
	"encoding/json"
	"fmt"
	"html"
	"io"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"regexp"
	"strings"
	"testing"
	"time"

	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

const (
	accessGroup    = "e2e-group"
	accessPassword = "e2e-Passw0rd!"
)

// keycloakAdmin is a minimal client of the Keycloak admin REST API of one realm.
type keycloakAdmin struct {
	t     *testing.T
	hc    *http.Client
	base  string // https://<keycloak host>
	realm string
	token string
}

func insecureClient() *http.Client {
	return &http.Client{Timeout: 30 * time.Second, Transport: &http.Transport{TLSClientConfig: &tls.Config{InsecureSkipVerify: true}}} //nolint:gosec
}

// newKeycloakAdmin logs in on the master realm with the bootstrap admin of the Keycloak CR.
func newKeycloakAdmin(t *testing.T, ns, base, realm string) *keycloakAdmin {
	t.Helper()
	sec := &corev1.Secret{}
	name := env("E2E_KEYCLOAK_ADMIN_SECRET", "unifai-keycloak-initial-admin")
	must(t, c.Get(ctx, client.ObjectKey{Namespace: ns, Name: name}, sec))
	a := &keycloakAdmin{t: t, hc: insecureClient(), base: strings.TrimRight(base, "/"), realm: realm}
	eventually(t, "Keycloak admin login", 3*time.Minute, func() (bool, string) {
		resp, err := a.hc.PostForm(a.base+"/realms/master/protocol/openid-connect/token", url.Values{
			"grant_type": {"password"}, "client_id": {"admin-cli"},
			"username": {string(sec.Data["username"])}, "password": {string(sec.Data["password"])}})
		if err != nil {
			return false, err.Error()
		}
		defer resp.Body.Close()
		var tok struct {
			AccessToken string `json:"access_token"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&tok)
		a.token = tok.AccessToken
		return a.token != "", resp.Status
	})
	return a
}

// do calls the admin API (path relative to /admin/realms/<realm>), decodes a JSON answer into out when given and
// returns the status code and the Location header.
func (a *keycloakAdmin) do(method, path string, body, out any) (int, string) {
	a.t.Helper()
	var rd io.Reader
	if body != nil {
		b, _ := json.Marshal(body)
		rd = bytes.NewReader(b)
	}
	req, err := http.NewRequest(method, a.base+"/admin/realms/"+a.realm+path, rd)
	must(a.t, err)
	req.Header.Set("Authorization", "Bearer "+a.token)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := a.hc.Do(req)
	must(a.t, err)
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if out != nil && resp.StatusCode < 300 {
		must(a.t, json.Unmarshal(data, out))
	}
	if resp.StatusCode >= 400 && resp.StatusCode != http.StatusConflict {
		a.t.Fatalf("keycloak %s %s: %s %s", method, path, resp.Status, strings.TrimSpace(string(data)))
	}
	return resp.StatusCode, resp.Header.Get("Location")
}

func lastSegment(location string) string { return location[strings.LastIndex(location, "/")+1:] }

// ensureGroup returns the id of the top-level group name, creating it when missing.
func (a *keycloakAdmin) ensureGroup(name string) string {
	a.t.Helper()
	var found []struct{ ID, Name string }
	a.do(http.MethodGet, "/groups?exact=true&search="+url.QueryEscape(name), nil, &found)
	for _, g := range found {
		if g.Name == name {
			return g.ID
		}
	}
	_, loc := a.do(http.MethodPost, "/groups", map[string]any{"name": name}, nil)
	return lastSegment(loc)
}

// ensureUser creates a realm user with a permanent password (and the profile attributes that keep the Keycloak 26
// user profile from asking for required actions at login) and returns its id.
func (a *keycloakAdmin) ensureUser(username string) string {
	a.t.Helper()
	status, loc := a.do(http.MethodPost, "/users", map[string]any{
		"username": username, "enabled": true, "emailVerified": true, "email": username + "@e2e.invalid",
		"firstName": username, "lastName": "E2E", "requiredActions": []string{},
		"credentials": []any{map[string]any{"type": "password", "value": accessPassword, "temporary": false}},
	}, nil)
	if status == http.StatusConflict {
		var found []struct{ ID string }
		a.do(http.MethodGet, "/users?exact=true&username="+url.QueryEscape(username), nil, &found)
		if len(found) != 1 {
			a.t.Fatalf("user %s exists but cannot be found", username)
		}
		return found[0].ID
	}
	return lastSegment(loc)
}

// ensureGroupsMapper makes the access token of the identity client carry the user's groups in the `groups` claim.
// full.path=false emits `e2e-group`; with true Keycloak emits `/e2e-group`, which the identity oidc-claims provider
// normalises to the same id (it strips a leading '/'), so either setting works.
func (a *keycloakAdmin) ensureGroupsMapper(clientID string) {
	a.t.Helper()
	var clients []struct{ ID string }
	a.do(http.MethodGet, "/clients?clientId="+url.QueryEscape(clientID), nil, &clients)
	if len(clients) != 1 {
		a.t.Fatalf("keycloak client %q not found in realm %s", clientID, a.realm)
	}
	var mappers []struct {
		ProtocolMapper string            `json:"protocolMapper"`
		Config         map[string]string `json:"config"`
	}
	a.do(http.MethodGet, "/clients/"+clients[0].ID+"/protocol-mappers/models", nil, &mappers)
	for _, m := range mappers {
		if m.ProtocolMapper == "oidc-group-membership-mapper" && m.Config["claim.name"] == "groups" && m.Config["access.token.claim"] != "false" {
			a.t.Log("groups claim mapper already present")
			return
		}
	}
	a.do(http.MethodPost, "/clients/"+clients[0].ID+"/protocol-mappers/models", map[string]any{
		"name": "e2e-groups", "protocol": "openid-connect", "protocolMapper": "oidc-group-membership-mapper",
		"config": map[string]string{"claim.name": "groups", "full.path": "false",
			"access.token.claim": "true", "id.token.claim": "true", "userinfo.token.claim": "true"},
	}, nil)
}

var formAction = regexp.MustCompile(`(?is)<form\b[^>]*\baction="([^"]+)"`)

// uiLogin logs a user in like the UI does: the authorization-code flow started on the identity service
// (<UI>/api3/auth/login), the Keycloak login form posted with the user's credentials, and the callback that makes
// identity create its session and fill the user's groups cache. The returned client carries the session cookie.
func uiLogin(t *testing.T, ui, username, password string) *http.Client {
	t.Helper()
	jar, _ := cookiejar.New(nil)
	hc := insecureClient()
	hc.Jar = jar
	resp, err := hc.Get(ui + "/api3/auth/login?state=" + url.QueryEscape("e2e"))
	must(t, err)
	page, _ := io.ReadAll(resp.Body)
	_ = resp.Body.Close()
	m := formAction.FindSubmatch(page)
	if m == nil {
		t.Fatalf("login %s: no Keycloak login form (status %s, final URL %s)", username, resp.Status, resp.Request.URL)
	}
	action, err := resp.Request.URL.Parse(html.UnescapeString(string(m[1])))
	must(t, err)
	resp, err = hc.PostForm(action.String(), url.Values{"username": {username}, "password": {password}, "credentialId": {""}})
	must(t, err)
	_, _ = io.Copy(io.Discard, resp.Body)
	_ = resp.Body.Close()
	// The callback redirected to the UI; the session cookie is in the jar.
	uiURL, _ := url.Parse(ui)
	if len(jar.Cookies(uiURL)) == 0 || resp.StatusCode != http.StatusOK {
		t.Fatalf("login %s: no session after the callback (status %s, final URL %s)", username, resp.Status, resp.Request.URL)
	}
	return hc
}

// getJSON GETs url with the session of hc and returns the status and the raw body.
func getJSON(t *testing.T, hc *http.Client, u string) (int, []byte) {
	t.Helper()
	resp, err := hc.Get(u)
	must(t, err)
	defer resp.Body.Close()
	b, _ := io.ReadAll(resp.Body)
	return resp.StatusCode, b
}

// clusterAppsDomain returns the apps domain used to build the Keycloak host the operator would choose.
func clusterAppsDomain(t *testing.T) string {
	t.Helper()
	if d := os.Getenv("E2E_KEYCLOAK_DOMAIN"); d != "" {
		return d
	}
	u := &unstructured.Unstructured{}
	u.SetAPIVersion("config.openshift.io/v1")
	u.SetKind("Ingress")
	if err := c.Get(context.Background(), client.ObjectKey{Name: "cluster"}, u); err != nil {
		t.Skipf("cannot read the apps domain (%v): set E2E_KEYCLOAK_DOMAIN", err)
	}
	d, _, _ := unstructured.NestedString(u.Object, "spec", "domain")
	if d == "" {
		t.Skip("no apps domain: set E2E_KEYCLOAK_DOMAIN")
	}
	return d
}

func containsString(list []string, s string) bool {
	for _, v := range list {
		if v == s {
			return true
		}
	}
	return false
}

func TestTeamGroupAccess(t *testing.T) {
	if os.Getenv("E2E_TEAM_ACCESS") == "" {
		t.Skip("E2E_TEAM_ACCESS=1 required (managed Keycloak, slow)")
	}
	timeout, _ := time.ParseDuration(env("E2E_TIMEOUT", "30m"))
	domain := clusterAppsDomain(t)
	n := newNamespace(t, "acc")

	// The identity service must derive the groups from the verified access token. The issuer is the public Keycloak
	// URL, so the host is fixed in the spec to know it before the stack exists; the JWKS is read through the
	// in-namespace Service. These two values (and DIRECTORY_PROVIDER) are what a stack spec must carry:
	//   spec.identity.keycloak.host: <host>
	//   spec.extraEnv.identity: DIRECTORY_PROVIDER=oidc-claims, DIRECTORY_OIDC_ISSUER=https://<host>/realms/unifai,
	//                           DIRECTORY_OIDC_JWKS_URL=<jwks url>
	kcHost := "unifai-keycloak-" + n + "." + domain
	issuer := "https://" + kcHost + "/realms/unifai"
	jwks := env("E2E_OIDC_JWKS_URL", "http://unifai-keycloak-service:8080/realms/unifai/protocol/openid-connect/certs")
	spec := stackSpec(unifaiv1.IdentitySpec{Keycloak: &unifaiv1.ManagedKeycloakSpec{Host: kcHost}})
	spec.ExtraEnv = map[string][]corev1.EnvVar{"identity": {
		{Name: "DIRECTORY_PROVIDER", Value: "oidc-claims"},
		{Name: "DIRECTORY_OIDC_ISSUER", Value: issuer},
		{Name: "DIRECTORY_OIDC_JWKS_URL", Value: jwks},
	}}
	st := &unifaiv1.UnifaiStack{ObjectMeta: accessMeta(unifaiv1.StackName, n), Spec: spec}
	create(t, st)
	// Registered after the namespace cleanup, so it runs first: the stack finalizer needs the operator and the namespace.
	t.Cleanup(func() {
		if os.Getenv("E2E_KEEP") != "" {
			return
		}
		if err := c.Delete(ctx, st); err != nil && !apierrors.IsNotFound(err) {
			t.Error(err)
			return
		}
		eventually(t, "access stack deleted", 15*time.Minute, func() (bool, string) {
			return apierrors.IsNotFound(c.Get(ctx, client.ObjectKeyFromObject(st), st)), st.Status.Phase + " " + st.Status.Message
		})
	})
	waitStackReady(t, st, timeout, nil)
	if got := st.Status.Endpoints.Keycloak; got != "https://"+kcHost {
		t.Fatalf("Keycloak endpoint %q, want https://%s", got, kcHost)
	}

	// Realm content: the group, two users (one member), and the claim in the identity client's access token.
	kc := newKeycloakAdmin(t, n, st.Status.Endpoints.Keycloak, "unifai")
	groupID := kc.ensureGroup(accessGroup)
	member, outsider := "e2e-member", "e2e-outsider"
	memberID := kc.ensureUser(member)
	kc.ensureUser(outsider)
	kc.do(http.MethodPut, "/users/"+memberID+"/groups/"+groupID, nil, nil)
	kc.ensureGroupsMapper("unifai")

	// The team is bound to the group by its normalised id (no leading '/': the oidc-claims provider strips it, and
	// the team repository matches member ids exactly).
	deployMockLLM(t, n)
	team := &unifaiv1.UnifaiTeam{ObjectMeta: accessMeta("e2e-access-team", n), Spec: unifaiv1.UnifaiTeamSpec{
		CommonSpec: unifaiv1.CommonSpec{UnifaiName: "e2e-access-team-" + n},
		Members:    []unifaiv1.TeamMember{{Type: "group", ID: accessGroup}}}}
	llm := &unifaiv1.UnifaiLLM{ObjectMeta: accessMeta("e2e-access-llm", n), Spec: unifaiv1.UnifaiLLMSpec{
		CommonSpec: unifaiv1.CommonSpec{UnifaiName: "e2e-access-llm", TeamRef: "e2e-access-team"}, Type: "openai_compatible",
		ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "mock-model", "base_url": "http://e2e-llm:8000/v1", "api_key": "EMPTY"})}}}
	create(t, team)
	create(t, llm)
	waitPhase(t, team, "Ready", 5*time.Minute)
	waitPhase(t, llm, "Ready", 5*time.Minute)
	teamID, rid := team.Status.TeamID, llm.Status.RID
	if teamID == "" || rid == "" {
		t.Fatalf("team id %q / object rid %q empty", teamID, rid)
	}

	ui := st.Status.Endpoints.UI
	memberHC := uiLogin(t, ui, member, accessPassword)
	outsiderHC := uiLogin(t, ui, outsider, accessPassword)

	t.Run("identity resolves the groups from the token", func(t *testing.T) {
		for _, tc := range []struct {
			hc   *http.Client
			user string
			want bool
		}{{memberHC, member, true}, {outsiderHC, outsider, false}} {
			code, body := getJSON(t, tc.hc, ui+"/api3/auth/user/groups?fresh=1")
			var out struct {
				Groups []string `json:"groups"`
			}
			_ = json.Unmarshal(body, &out)
			if code != http.StatusOK || containsString(out.Groups, accessGroup) != tc.want {
				t.Errorf("%s: groups %v (status %d), carries %s = %v, want %v", tc.user, out.Groups, code, accessGroup, containsString(out.Groups, accessGroup), tc.want)
			}
		}
	})

	listResources := func(hc *http.Client) (int, []string) {
		code, body := getJSON(t, hc, ui+"/api2/resources/resources.list?category=llms&teamId="+url.QueryEscape(teamID))
		var out struct {
			Resources []struct {
				RID string `json:"rid"`
			} `json:"resources"`
		}
		_ = json.Unmarshal(body, &out)
		var rids []string
		for _, r := range out.Resources {
			rids = append(rids, r.RID)
		}
		return code, rids
	}

	t.Run("a member of the group sees the team object", func(t *testing.T) {
		eventually(t, "member lists the team workspace", 2*time.Minute, func() (bool, string) {
			code, rids := listResources(memberHC)
			return code == http.StatusOK && containsString(rids, rid), fmt.Sprintf("status %d, resources %v, want %s", code, rids, rid)
		})
	})

	t.Run("a user outside the group is refused", func(t *testing.T) {
		if code, rids := listResources(outsiderHC); code != http.StatusForbidden {
			t.Errorf("outsider on the team workspace: status %d (resources %v), want 403", code, rids)
		}
		// Not leaked either through the outsider's own workspace.
		code, body := getJSON(t, outsiderHC, ui+"/api2/resources/resources.list?category=llms")
		if code == http.StatusOK && strings.Contains(string(body), rid) {
			t.Errorf("the team object %s shows in the outsider's personal workspace", rid)
		}
	})

	t.Run("the group-bound team is listed for the member only", func(t *testing.T) {
		teamsOf := func(hc *http.Client, user string) []string {
			code, body := getJSON(t, hc, ui+"/api3/teams/teams.list?userId="+url.QueryEscape(user))
			if code != http.StatusOK {
				t.Fatalf("teams.list for %s: status %d %s", user, code, body)
			}
			var out struct {
				Teams []struct {
					ID string `json:"team_id"`
				} `json:"teams"`
			}
			must(t, json.Unmarshal(body, &out))
			var ids []string
			for _, tm := range out.Teams {
				ids = append(ids, tm.ID)
			}
			return ids
		}
		if ids := teamsOf(memberHC, member); !containsString(ids, teamID) {
			t.Errorf("team %s missing from %s's teams %v", teamID, member, ids)
		}
		if ids := teamsOf(outsiderHC, outsider); containsString(ids, teamID) {
			t.Errorf("team %s listed for %s: %v", teamID, outsider, ids)
		}
	})
}

func accessMeta(name, namespace string) metav1.ObjectMeta {
	return metav1.ObjectMeta{Name: name, Namespace: namespace}
}
