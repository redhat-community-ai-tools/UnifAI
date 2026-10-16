package stack

import (
	"context"
	"fmt"
	"strings"

	appsv1 "k8s.io/api/apps/v1"
	corev1 "k8s.io/api/core/v1"
	apierrors "k8s.io/apimachinery/pkg/api/errors"
	"k8s.io/apimachinery/pkg/api/meta"
	"k8s.io/apimachinery/pkg/api/resource"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/apis/meta/v1/unstructured"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/types"
	"k8s.io/apimachinery/pkg/util/intstr"
	"sigs.k8s.io/controller-runtime/pkg/client"
)

// Names of the managed Keycloak objects.
const (
	KeycloakName      = "unifai-keycloak"
	KeycloakDBName    = "unifai-keycloak-db"
	RealmImportName   = "unifai-realm"
	RealmName         = "unifai"
	ClientID          = "unifai"
	OperatorGroupName = "unifai-operatorgroup"
	RHBKPackage       = "rhbk-operator"
	// LabelOwnedOLM marks the OperatorGroup/Subscription created by the stack (removed with it).
	LabelOwnedOLM = "unifai.startx.fr/olm-owned"
)

// crunchyUserSchema makes Crunchy create a schema owned by each user in its databases: PostgreSQL 15+ no longer
// lets a non-owner create tables in `public`, so Keycloak uses the `keycloak` schema.
const crunchyUserSchema = "postgres-operator.crunchydata.com/autoCreateUserSchema"

// GVKs of the external APIs used for the managed Keycloak.
var (
	GVKOperatorGroup = schema.GroupVersionKind{Group: "operators.coreos.com", Version: "v1", Kind: "OperatorGroup"}
	GVKSubscription  = schema.GroupVersionKind{Group: "operators.coreos.com", Version: "v1alpha1", Kind: "Subscription"}
	GVKCSV           = schema.GroupVersionKind{Group: "operators.coreos.com", Version: "v1alpha1", Kind: "ClusterServiceVersion"}
	GVKKeycloak      = schema.GroupVersionKind{Group: "k8s.keycloak.org", Version: "v2alpha1", Kind: "Keycloak"}
	GVKRealmImport   = schema.GroupVersionKind{Group: "k8s.keycloak.org", Version: "v2alpha1", Kind: "KeycloakRealmImport"}
	GVKPostgres      = schema.GroupVersionKind{Group: "postgres-operator.crunchydata.com", Version: "v1beta1", Kind: "PostgresCluster"}
	GVKRoute         = schema.GroupVersionKind{Group: "route.openshift.io", Version: "v1", Kind: "Route"}
)

// Keycloak manages the Keycloak of a stack.
type Keycloak struct {
	Client client.Client
	// Owner is set as controller owner of the objects that are safe to garbage-collect with the stack.
	SetOwner func(client.Object) error
}

func newU(gvk schema.GroupVersionKind, ns, name string) *unstructured.Unstructured {
	u := &unstructured.Unstructured{}
	u.SetGroupVersionKind(gvk)
	u.SetNamespace(ns)
	u.SetName(name)
	return u
}

// hasAPI reports whether the cluster serves a kind.
func (k *Keycloak) hasAPI(gvk schema.GroupVersionKind) bool {
	_, err := k.Client.RESTMapper().RESTMapping(gvk.GroupKind(), gvk.Version)
	return err == nil
}

// Ensure drives the managed Keycloak to ready; it returns "" when the realm is imported and Keycloak is ready,
// else what it is waiting for.
func (k *Keycloak) Ensure(ctx context.Context, p *Plan) (string, error) {
	spec := p.Spec.Identity.Keycloak
	if msg, err := k.ensureOperator(ctx, p, spec.InstallOperator == nil || *spec.InstallOperator, spec.Channel); msg != "" || err != nil {
		return msg, err
	}
	dbHost, userRef, passRef, msg, err := k.ensureDatabase(ctx, p)
	if msg != "" || err != nil {
		return msg, err
	}
	if err := k.ensureKeycloak(ctx, p, dbHost, userRef, passRef); err != nil {
		return "", err
	}
	if err := k.ensureRoute(ctx, p); err != nil {
		return "", err
	}
	if err := k.ensureRealm(ctx, p); err != nil {
		return "", err
	}
	kc := newU(GVKKeycloak, p.Namespace, KeycloakName)
	if err := k.Client.Get(ctx, client.ObjectKeyFromObject(kc), kc); err != nil {
		return "", err
	}
	if !conditionTrue(kc, "Ready") {
		return "waiting for Keycloak to be ready", nil
	}
	ri := newU(GVKRealmImport, p.Namespace, RealmImportName)
	if err := k.Client.Get(ctx, client.ObjectKeyFromObject(ri), ri); err != nil {
		return "", err
	}
	if conditionTrue(ri, "HasErrors") {
		return "", fmt.Errorf("realm import failed: %s", conditionMessage(ri, "HasErrors"))
	}
	if !conditionTrue(ri, "Done") {
		return "waiting for the realm import", nil
	}
	return "", nil
}

func conditionTrue(u *unstructured.Unstructured, typ string) bool {
	return conditionField(u, typ, "status") == "True"
}

func conditionMessage(u *unstructured.Unstructured, typ string) string { return conditionField(u, typ, "message") }

func conditionField(u *unstructured.Unstructured, typ, field string) string {
	conds, _, _ := unstructured.NestedSlice(u.Object, "status", "conditions")
	for _, c := range conds {
		m, _ := c.(map[string]any)
		if m["type"] == typ {
			v, _ := m[field].(string)
			return v
		}
	}
	return ""
}

// ensureOperator makes sure an RHBK operator serves the namespace (RHBK only supports OwnNamespace/SingleNamespace).
func (k *Keycloak) ensureOperator(ctx context.Context, p *Plan, install bool, channel string) (string, error) {
	if served, err := k.rhbkServes(ctx, p.Namespace); err != nil || served {
		return "", err
	}
	if !install {
		return "", fmt.Errorf("no Red Hat build of Keycloak operator serves namespace %s (identity.keycloak.installOperator is false)", p.Namespace)
	}
	if !k.hasAPI(GVKSubscription) {
		return "", fmt.Errorf("OLM is not available: install the RHBK operator in namespace %s by hand", p.Namespace)
	}
	ogs := &unstructured.UnstructuredList{}
	ogs.SetGroupVersionKind(GVKOperatorGroup.GroupVersion().WithKind("OperatorGroupList"))
	if err := k.Client.List(ctx, ogs, client.InNamespace(p.Namespace)); err != nil {
		return "", err
	}
	switch len(ogs.Items) {
	case 0:
		og := newU(GVKOperatorGroup, p.Namespace, OperatorGroupName)
		og.SetLabels(map[string]string{LabelOwnedOLM: "true", LabelPartOf: "unifai"})
		_ = unstructured.SetNestedStringSlice(og.Object, []string{p.Namespace}, "spec", "targetNamespaces")
		if err := k.Client.Create(ctx, og); err != nil && !apierrors.IsAlreadyExists(err) {
			return "", err
		}
	case 1:
		targets, _, _ := unstructured.NestedStringSlice(ogs.Items[0].Object, "spec", "targetNamespaces")
		if len(targets) != 1 || targets[0] != p.Namespace {
			return "", fmt.Errorf("OperatorGroup %s does not target only %s: RHBK cannot be installed by the stack", ogs.Items[0].GetName(), p.Namespace)
		}
	default:
		return "", fmt.Errorf("namespace %s has several OperatorGroups", p.Namespace)
	}
	sub := newU(GVKSubscription, p.Namespace, RHBKPackage)
	err := k.Client.Get(ctx, client.ObjectKeyFromObject(sub), sub)
	if apierrors.IsNotFound(err) {
		if channel == "" {
			channel = "stable-v26.6"
		}
		sub.SetLabels(map[string]string{LabelOwnedOLM: "true", LabelPartOf: "unifai"})
		sub.Object["spec"] = map[string]any{
			"name": RHBKPackage, "channel": channel, "source": "redhat-operators",
			"sourceNamespace": "openshift-marketplace", "installPlanApproval": "Automatic",
		}
		if err := k.Client.Create(ctx, sub); err != nil {
			return "", err
		}
	} else if err != nil {
		return "", err
	}
	return "installing the Red Hat build of Keycloak operator", nil
}

// rhbkServes reports whether a succeeded RHBK CSV is installed in the namespace.
func (k *Keycloak) rhbkServes(ctx context.Context, ns string) (bool, error) {
	if !k.hasAPI(GVKCSV) {
		return k.hasAPI(GVKKeycloak), nil
	}
	csvs := &unstructured.UnstructuredList{}
	csvs.SetGroupVersionKind(GVKCSV.GroupVersion().WithKind("ClusterServiceVersionList"))
	if err := k.Client.List(ctx, csvs, client.InNamespace(ns)); err != nil {
		return false, err
	}
	for _, c := range csvs.Items {
		phase, _, _ := unstructured.NestedString(c.Object, "status", "phase")
		if strings.HasPrefix(c.GetName(), RHBKPackage+".") && phase == "Succeeded" {
			return true, nil
		}
	}
	return false, nil
}

// ensureDatabase returns the PostgreSQL host and the secret selectors of its credentials.
func (k *Keycloak) ensureDatabase(ctx context.Context, p *Plan) (host string, user, pass *corev1.SecretKeySelector, msg string, err error) {
	db := p.Spec.Identity.Keycloak.Database
	useCrunchy := db.Type == "crunchy" || (db.Type != "statefulset" && k.hasAPI(GVKPostgres))
	if db.Type == "crunchy" && !k.hasAPI(GVKPostgres) {
		return "", nil, nil, "", fmt.Errorf("database type crunchy requested but the Crunchy PostgresCluster API is not served")
	}
	if useCrunchy {
		return k.ensureCrunchy(ctx, p)
	}
	return k.ensurePostgresStatefulSet(ctx, p)
}

func (k *Keycloak) ensureCrunchy(ctx context.Context, p *Plan) (string, *corev1.SecretKeySelector, *corev1.SecretKeySelector, string, error) {
	pg := newU(GVKPostgres, p.Namespace, KeycloakDBName)
	err := k.Client.Get(ctx, client.ObjectKeyFromObject(pg), pg)
	if apierrors.IsNotFound(err) {
		pvc := map[string]any{"accessModes": []any{"ReadWriteOnce"}, "resources": map[string]any{"requests": map[string]any{"storage": p.size("keycloakDb", "10Gi")}}}
		if c := p.Spec.Storage.ClassName; c != "" {
			pvc["storageClassName"] = c
		}
		pg.SetLabels(map[string]string{LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "keycloak"})
		pg.SetAnnotations(map[string]string{crunchyUserSchema: "true"})
		pg.Object["spec"] = map[string]any{
			"postgresVersion": int64(16),
			"instances":       []any{map[string]any{"name": "db", "replicas": int64(1), "dataVolumeClaimSpec": pvc}},
			"users":           []any{map[string]any{"name": "keycloak", "databases": []any{"keycloak"}}},
		}
		if err := k.Client.Create(ctx, pg); err != nil {
			return "", nil, nil, "", err
		}
	} else if err != nil {
		return "", nil, nil, "", err
	} else if pg.GetAnnotations()[crunchyUserSchema] != "true" {
		a := pg.GetAnnotations()
		if a == nil {
			a = map[string]string{}
		}
		a[crunchyUserSchema] = "true"
		pg.SetAnnotations(a)
		if err := k.Client.Update(ctx, pg); err != nil {
			return "", nil, nil, "", err
		}
	}
	secretName := KeycloakDBName + "-pguser-keycloak"
	var s corev1.Secret
	if err := k.Client.Get(ctx, types.NamespacedName{Namespace: p.Namespace, Name: secretName}, &s); err != nil {
		if apierrors.IsNotFound(err) {
			return "", nil, nil, "waiting for the Keycloak PostgreSQL cluster", nil
		}
		return "", nil, nil, "", err
	}
	sel := func(key string) *corev1.SecretKeySelector {
		return &corev1.SecretKeySelector{LocalObjectReference: corev1.LocalObjectReference{Name: secretName}, Key: key}
	}
	return fmt.Sprintf("%s-primary.%s.svc", KeycloakDBName, p.Namespace), sel("user"), sel("password"), "", nil
}

func (k *Keycloak) ensurePostgresStatefulSet(ctx context.Context, p *Plan) (string, *corev1.SecretKeySelector, *corev1.SecretKeySelector, string, error) {
	image := p.Spec.Identity.Keycloak.Database.Image
	if image == "" {
		image = "quay.io/sclorg/postgresql-16-c9s:latest"
	}
	labels := map[string]string{"app": KeycloakDBName, LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "keycloak"}
	sec := &corev1.Secret{ObjectMeta: metav1.ObjectMeta{Name: KeycloakDBName, Namespace: p.Namespace, Labels: labels}}
	if err := k.Client.Get(ctx, client.ObjectKeyFromObject(sec), sec); apierrors.IsNotFound(err) {
		sec.StringData = map[string]string{"user": "keycloak", "password": p.Secrets[KeyKeycloakDBPass], "database": "keycloak"}
		if err := k.Client.Create(ctx, sec); err != nil {
			return "", nil, nil, "", err
		}
	} else if err != nil {
		return "", nil, nil, "", err
	}
	svc := &corev1.Service{ObjectMeta: metav1.ObjectMeta{Name: KeycloakDBName, Namespace: p.Namespace, Labels: labels},
		Spec: corev1.ServiceSpec{Selector: map[string]string{"app": KeycloakDBName},
			Ports: []corev1.ServicePort{{Name: "postgres", Port: 5432, TargetPort: intstr.FromInt32(5432)}}}}
	if err := k.Client.Create(ctx, svc); err != nil && !apierrors.IsAlreadyExists(err) {
		return "", nil, nil, "", err
	}
	env := func(name, key string) corev1.EnvVar {
		return corev1.EnvVar{Name: name, ValueFrom: &corev1.EnvVarSource{SecretKeyRef: &corev1.SecretKeySelector{
			LocalObjectReference: corev1.LocalObjectReference{Name: KeycloakDBName}, Key: key}}}
	}
	pvc := corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Name: "data"}, Spec: corev1.PersistentVolumeClaimSpec{
		AccessModes: []corev1.PersistentVolumeAccessMode{corev1.ReadWriteOnce},
		Resources:   corev1.VolumeResourceRequirements{Requests: corev1.ResourceList{corev1.ResourceStorage: resource.MustParse(p.size("keycloakDb", "10Gi"))}},
	}}
	if c := p.Spec.Storage.ClassName; c != "" {
		pvc.Spec.StorageClassName = &c
	}
	one := int32(1)
	sts := &appsv1.StatefulSet{ObjectMeta: metav1.ObjectMeta{Name: KeycloakDBName, Namespace: p.Namespace, Labels: labels},
		Spec: appsv1.StatefulSetSpec{
			Replicas: &one, ServiceName: KeycloakDBName, Selector: &metav1.LabelSelector{MatchLabels: map[string]string{"app": KeycloakDBName}},
			VolumeClaimTemplates: []corev1.PersistentVolumeClaim{pvc},
			Template: corev1.PodTemplateSpec{ObjectMeta: metav1.ObjectMeta{Labels: labels}, Spec: corev1.PodSpec{
				NodeSelector: p.Spec.NodeSelector, Tolerations: p.Spec.Tolerations, ImagePullSecrets: p.Spec.ImagePullSecrets,
				Containers: []corev1.Container{{
					Name: "postgresql", Image: image,
					Env:          []corev1.EnvVar{env("POSTGRESQL_USER", "user"), env("POSTGRESQL_PASSWORD", "password"), env("POSTGRESQL_DATABASE", "database")},
					Ports:        []corev1.ContainerPort{{Name: "postgres", ContainerPort: 5432}},
					VolumeMounts: []corev1.VolumeMount{{Name: "data", MountPath: "/var/lib/pgsql/data"}},
					Resources: corev1.ResourceRequirements{
						Requests: corev1.ResourceList{corev1.ResourceCPU: resource.MustParse("50m"), corev1.ResourceMemory: resource.MustParse("256Mi")},
						Limits:   corev1.ResourceList{corev1.ResourceMemory: resource.MustParse("1Gi")},
					},
					ReadinessProbe: &corev1.Probe{ProbeHandler: corev1.ProbeHandler{Exec: &corev1.ExecAction{
						Command: []string{"/usr/libexec/check-container"}}}, InitialDelaySeconds: 5, PeriodSeconds: 10},
				}},
			}},
		}}
	if err := k.Client.Create(ctx, sts); err != nil && !apierrors.IsAlreadyExists(err) {
		return "", nil, nil, "", err
	}
	sel := func(key string) *corev1.SecretKeySelector {
		return &corev1.SecretKeySelector{LocalObjectReference: corev1.LocalObjectReference{Name: KeycloakDBName}, Key: key}
	}
	return fmt.Sprintf("%s.%s.svc", KeycloakDBName, p.Namespace), sel("user"), sel("password"), "", nil
}

// apply creates obj or replaces its spec, owned by the stack.
func (k *Keycloak) apply(ctx context.Context, obj *unstructured.Unstructured) error {
	if k.SetOwner != nil {
		if err := k.SetOwner(obj); err != nil {
			return err
		}
	}
	cur := obj.DeepCopy()
	err := k.Client.Get(ctx, client.ObjectKeyFromObject(obj), cur)
	if apierrors.IsNotFound(err) {
		return k.Client.Create(ctx, obj)
	}
	if err != nil {
		return err
	}
	cur.Object["spec"] = obj.Object["spec"]
	cur.SetLabels(obj.GetLabels())
	cur.SetOwnerReferences(obj.GetOwnerReferences())
	return k.Client.Update(ctx, cur)
}

func (k *Keycloak) ensureKeycloak(ctx context.Context, p *Plan, dbHost string, user, pass *corev1.SecretKeySelector) error {
	db := map[string]any{
		"vendor": "postgres", "host": dbHost, "port": int64(5432), "database": "keycloak",
		"usernameSecret": map[string]any{"name": user.Name, "key": user.Key},
		"passwordSecret": map[string]any{"name": pass.Name, "key": pass.Key},
	}
	if strings.HasPrefix(user.Name, KeycloakDBName+"-pguser-") { // Crunchy: per-user schema
		db["schema"] = "keycloak"
	}
	kc := newU(GVKKeycloak, p.Namespace, KeycloakName)
	kc.SetLabels(map[string]string{LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "keycloak"})
	spec := map[string]any{
		"instances": int64(1),
		"db":        db,
		"http":     map[string]any{"httpEnabled": true},
		"hostname": map[string]any{"hostname": "https://" + p.KeycloakHost},
		"proxy":    map[string]any{"headers": "xforwarded"},
		"ingress":  map[string]any{"enabled": false},
	}
	if p.Dev() {
		spec["resources"] = map[string]any{
			"requests": map[string]any{"cpu": "100m", "memory": "512Mi"},
			"limits":   map[string]any{"memory": "2Gi"},
		}
	}
	if len(p.Spec.NodeSelector) > 0 || len(p.Spec.Tolerations) > 0 {
		podSpec := map[string]any{}
		if len(p.Spec.NodeSelector) > 0 {
			podSpec["nodeSelector"] = toMap(p.Spec.NodeSelector)
		}
		if len(p.Spec.Tolerations) > 0 {
			var tol []any
			for _, t := range p.Spec.Tolerations {
				tol = append(tol, toMap(t))
			}
			podSpec["tolerations"] = tol
		}
		spec["unsupported"] = map[string]any{"podTemplate": map[string]any{"spec": podSpec}}
	}
	kc.Object["spec"] = spec
	return k.apply(ctx, kc)
}

func (k *Keycloak) ensureRoute(ctx context.Context, p *Plan) error {
	rt := newU(GVKRoute, p.Namespace, KeycloakName)
	rt.SetLabels(map[string]string{LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "keycloak"})
	rt.Object["spec"] = map[string]any{
		"host": p.KeycloakHost,
		"to":   map[string]any{"kind": "Service", "name": KeycloakName + "-service", "weight": int64(100)},
		"port": map[string]any{"targetPort": "http"},
		"tls":  map[string]any{"termination": "edge", "insecureEdgeTerminationPolicy": "Redirect"},
	}
	return k.apply(ctx, rt)
}

// ensureRealm imports the UnifAI realm once (RHBK does not re-import an existing realm). Secrets are passed as
// placeholders so they never appear in the custom resource.
func (k *Keycloak) ensureRealm(ctx context.Context, p *Plan) error {
	ri := newU(GVKRealmImport, p.Namespace, RealmImportName)
	if err := k.Client.Get(ctx, client.ObjectKeyFromObject(ri), ri); err == nil {
		return nil
	} else if !apierrors.IsNotFound(err) {
		return err
	}
	adminSecret := map[string]any{"name": GeneratedSecretName, "key": KeyKeycloakAdminPass}
	if ref := p.Spec.Identity.Keycloak.AdminPassword; ref != nil {
		adminSecret = map[string]any{"name": ref.Name, "key": ref.Key}
	}
	var users []any
	for _, u := range p.AdminUsers() {
		users = append(users, map[string]any{
			"username": u, "enabled": true, "emailVerified": true, "email": u + "@unifai.invalid",
			"firstName": u, "lastName": "UnifAI",
			"credentials": []any{map[string]any{"type": "password", "value": "${ADMIN_PASSWORD}", "temporary": false}},
		})
	}
	origins := []any{"https://" + p.IdentityHost, "https://" + p.UIHost}
	ri.SetLabels(map[string]string{LabelPartOf: "unifai", LabelManagedBy: "unifai-operator", LabelComponent: "keycloak"})
	ri.Object["spec"] = map[string]any{
		"keycloakCRName": KeycloakName,
		"placeholders": map[string]any{
			"CLIENT_SECRET":  map[string]any{"secret": map[string]any{"name": GeneratedSecretName, "key": KeyClientSecret}},
			"ADMIN_PASSWORD": map[string]any{"secret": adminSecret},
		},
		"realm": map[string]any{
			"realm": RealmName, "displayName": "UnifAI", "enabled": true, "sslRequired": "external",
			"loginWithEmailAllowed": true, "registrationAllowed": false,
			"clients": []any{map[string]any{
				"clientId": ClientID, "name": "UnifAI", "enabled": true, "protocol": "openid-connect", "publicClient": false,
				"secret": "${CLIENT_SECRET}", "standardFlowEnabled": true, "directAccessGrantsEnabled": false,
				"redirectUris": []any{"https://" + p.IdentityHost + "/*", "https://" + p.UIHost + "/*"},
				"webOrigins":   origins,
			}},
			"users": users,
		},
	}
	return k.apply(ctx, ri)
}

// Delete removes the Keycloak objects; the database is removed only with removeData.
// It returns true when everything that has to go is gone.
func (k *Keycloak) Delete(ctx context.Context, ns string, removeData bool) (bool, error) {
	gone := true
	del := func(obj client.Object) error {
		err := k.Client.Delete(ctx, obj, client.PropagationPolicy(metav1.DeletePropagationBackground))
		if apierrors.IsNotFound(err) || meta.IsNoMatchError(err) {
			return nil
		}
		gone = false
		return err
	}
	for _, o := range []client.Object{newU(GVKRealmImport, ns, RealmImportName), newU(GVKKeycloak, ns, KeycloakName), newU(GVKRoute, ns, KeycloakName)} {
		if err := del(o); err != nil {
			return false, err
		}
	}
	if !gone {
		return false, nil // operators must process the Keycloak deletion before RHBK goes away
	}
	// The RHBK operator installed by the stack.
	if err := k.deleteOwnedOLM(ctx, ns, &gone); err != nil {
		return false, err
	}
	if removeData {
		for _, o := range []client.Object{
			newU(GVKPostgres, ns, KeycloakDBName),
			&appsv1.StatefulSet{ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: KeycloakDBName}},
			&corev1.Service{ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: KeycloakDBName}},
			&corev1.Secret{ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: KeycloakDBName}},
			&corev1.PersistentVolumeClaim{ObjectMeta: metav1.ObjectMeta{Namespace: ns, Name: "data-" + KeycloakDBName + "-0"}},
		} {
			if err := del(o); err != nil {
				return false, err
			}
		}
	}
	return gone, nil
}

func (k *Keycloak) deleteOwnedOLM(ctx context.Context, ns string, gone *bool) error {
	if !k.hasAPI(GVKSubscription) {
		return nil
	}
	sub := newU(GVKSubscription, ns, RHBKPackage)
	err := k.Client.Get(ctx, client.ObjectKeyFromObject(sub), sub)
	if err == nil && sub.GetLabels()[LabelOwnedOLM] == "true" {
		csv, _, _ := unstructured.NestedString(sub.Object, "status", "installedCSV")
		if err := k.Client.Delete(ctx, sub); err != nil && !apierrors.IsNotFound(err) {
			return err
		}
		if csv != "" {
			if err := k.Client.Delete(ctx, newU(GVKCSV, ns, csv)); err != nil && !apierrors.IsNotFound(err) {
				return err
			}
		}
		*gone = false
	} else if err != nil && !apierrors.IsNotFound(err) {
		return err
	}
	og := newU(GVKOperatorGroup, ns, OperatorGroupName)
	if err := k.Client.Get(ctx, client.ObjectKeyFromObject(og), og); err == nil && og.GetLabels()[LabelOwnedOLM] == "true" {
		if err := k.Client.Delete(ctx, og); err != nil && !apierrors.IsNotFound(err) {
			return err
		}
	}
	return nil
}
