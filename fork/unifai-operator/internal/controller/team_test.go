package controller

import (
	"time"

	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"sigs.k8s.io/controller-runtime/pkg/client"

	unifaiv1 "github.com/startxfr/unifai-operator/api/v1alpha1"
)

var _ = Describe("UnifaiTeam and teamRef", func() {
	const timeout, interval = 30 * time.Second, 200 * time.Millisecond

	teamByName := func(name string) map[string]any {
		mas.mu.Lock()
		defer mas.mu.Unlock()
		for _, t := range mas.teams {
			if t["name"] == name {
				return t
			}
		}
		return nil
	}

	It("creates the team, puts teamRef objects in its workspace and deletes it last", func() {
		ns := newNamespace("team")
		llm := &unifaiv1.UnifaiLLM{ObjectMeta: metav1.ObjectMeta{Name: "llm", Namespace: ns}, Spec: unifaiv1.UnifaiLLMSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "llm-" + ns, TeamRef: "tekos"}, Type: "openai_compatible",
			ConfigSpec: unifaiv1.ConfigSpec{Config: raw(map[string]any{"model_name": "m", "base_url": "http://llm:8000/v1"})}}}
		Expect(k8sClient.Create(ctx, llm)).To(Succeed())
		Eventually(func() string {
			_ = k8sClient.Get(ctx, client.ObjectKeyFromObject(llm), llm)
			return llm.Status.Message
		}, timeout, interval).Should(ContainSubstring("teamRef tekos"))
		Expect(mas.resourceByName("llms", "llm-"+ns)).To(BeNil()) // never in the personal workspace

		team := &unifaiv1.UnifaiTeam{ObjectMeta: metav1.ObjectMeta{Name: "tekos", Namespace: ns}, Spec: unifaiv1.UnifaiTeamSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "agent-tekos-" + ns},
			Members:    []unifaiv1.TeamMember{{Type: "group", ID: "/agent_tekos"}, {Type: "user", ID: "alice"}}}}
		Expect(k8sClient.Create(ctx, team)).To(Succeed())
		Eventually(phaseOf(team), timeout, interval).Should(Equal("Ready"))
		Expect(team.Status.TeamID).NotTo(BeEmpty())
		stored := teamByName("agent-tekos-" + ns)
		Expect(stored).To(HaveKeyWithValue("created_by", "admin"))
		Expect(stored["members"]).To(ContainElement(HaveKeyWithValue("id", "agent_tekos")))

		Eventually(phaseOf(llm), timeout, interval).Should(Equal("Ready"))
		Expect(mas.resourceByName("llms", "llm-"+ns)).To(HaveKeyWithValue("team_id", team.Status.TeamID))

		By("replacing the members")
		Expect(k8sClient.Get(ctx, client.ObjectKeyFromObject(team), team)).To(Succeed())
		team.Spec.Members = []unifaiv1.TeamMember{{Type: "group", ID: "sales"}}
		Expect(k8sClient.Update(ctx, team)).To(Succeed())
		Eventually(func() any { return teamByName("agent-tekos-" + ns)["members"] }, timeout, interval).
			Should(ConsistOf(HaveKeyWithValue("id", "sales")))

		By("keeping the team while an object still uses it")
		Expect(k8sClient.Delete(ctx, team)).To(Succeed())
		Eventually(phaseOf(team), timeout, interval).Should(Equal("Deleting"))
		Expect(team.Status.Message).To(ContainSubstring("UnifaiLLM/llm"))
		Expect(teamByName("agent-tekos-" + ns)).NotTo(BeNil())
		By("deleting the object from the workspace of its Deleting team")
		Expect(k8sClient.Delete(ctx, llm)).To(Succeed())
		Eventually(func() bool { return apierrors.IsNotFound(k8sClient.Get(ctx, client.ObjectKeyFromObject(team), team)) },
			60*time.Second, interval).Should(BeTrue())
		Expect(teamByName("agent-tekos-" + ns)).To(BeNil())
		Expect(mas.resourceByName("llms", "llm-"+ns)).To(BeNil())
	})

	It("never takes over a team it did not create, and needs the adopt annotation for the owner's", func() {
		ns := newNamespace("teamtake")
		mas.mu.Lock()
		mas.teams["other-"+ns] = map[string]any{"team_id": "other-" + ns, "name": "taken-" + ns, "created_by": "bob"}
		mas.teams["mine-"+ns] = map[string]any{"team_id": "mine-" + ns, "name": "mine-" + ns, "created_by": "admin"}
		mas.mu.Unlock()
		taken := &unifaiv1.UnifaiTeam{ObjectMeta: metav1.ObjectMeta{Name: "taken", Namespace: ns}, Spec: unifaiv1.UnifaiTeamSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "taken-" + ns}}}
		Expect(k8sClient.Create(ctx, taken)).To(Succeed())
		Eventually(phaseOf(taken), timeout, interval).Should(Equal(PhaseError))
		Expect(taken.Status.Message).To(ContainSubstring("another user"))

		mine := &unifaiv1.UnifaiTeam{ObjectMeta: metav1.ObjectMeta{Name: "mine", Namespace: ns}, Spec: unifaiv1.UnifaiTeamSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "mine-" + ns}}}
		Expect(k8sClient.Create(ctx, mine)).To(Succeed())
		Eventually(phaseOf(mine), timeout, interval).Should(Equal(PhaseError))
		Expect(mine.Status.Message).To(ContainSubstring(unifaiv1.AdoptAnnotation))
		mine.Annotations = map[string]string{unifaiv1.AdoptAnnotation: "true"}
		Expect(k8sClient.Update(ctx, mine)).To(Succeed())
		Eventually(phaseOf(mine), timeout, interval).Should(Equal("Ready"))
		Expect(mine.Status.TeamID).To(Equal("mine-" + ns))
	})

	It("refuses teamId together with teamRef at admission", func() {
		ns := newNamespace("teamboth")
		tool := &unifaiv1.UnifaiTool{ObjectMeta: metav1.ObjectMeta{Name: "t", Namespace: ns}, Spec: unifaiv1.UnifaiToolSpec{
			CommonSpec: unifaiv1.CommonSpec{UnifaiName: "t-" + ns, TeamID: "x", TeamRef: "y"}, Type: "web_fetch"}}
		Expect(k8sClient.Create(ctx, tool)).To(MatchError(ContainSubstring("teamId and teamRef are exclusive")))
	})
})
