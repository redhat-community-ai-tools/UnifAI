package stack

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"helm.sh/helm/v3/pkg/action"
	"helm.sh/helm/v3/pkg/release"
	"helm.sh/helm/v3/pkg/storage/driver"
	"k8s.io/cli-runtime/pkg/genericclioptions"
	"k8s.io/client-go/rest"
	"sigs.k8s.io/controller-runtime/pkg/log"
)

// HashLabel is the Helm release label holding the hash of the inputs it was applied with.
const HashLabel = "unifai.startx.fr/hash"

// maxHistory bounds the Helm release secrets kept per release.
const maxHistory = 5

// Engine installs, upgrades and removes the stack's Helm releases.
type Engine struct {
	Config *rest.Config

	mu   sync.Mutex
	cfgs map[string]*action.Configuration
}

// configuration returns the Helm configuration of a namespace (cached: building one runs API discovery).
func (e *Engine) configuration(ctx context.Context, ns string) (*action.Configuration, error) {
	e.mu.Lock()
	defer e.mu.Unlock()
	if cfg, ok := e.cfgs[ns]; ok {
		return cfg, nil
	}
	flags := genericclioptions.NewConfigFlags(false)
	flags.Namespace = &ns
	cacheDir := filepath.Join(os.TempDir(), "unifai-operator-kube-cache")
	flags.CacheDir = &cacheDir
	base := rest.CopyConfig(e.Config)
	flags.WrapConfigFn = func(*rest.Config) *rest.Config { return rest.CopyConfig(base) }
	cfg := new(action.Configuration)
	logger := log.Log.WithName("helm").WithValues("namespace", ns).V(1)
	if err := cfg.Init(flags, ns, "secret", func(format string, v ...any) { logger.Info(fmt.Sprintf(format, v...)) }); err != nil {
		return nil, err
	}
	if e.cfgs == nil {
		e.cfgs = map[string]*action.Configuration{}
	}
	e.cfgs[ns] = cfg
	return cfg, nil
}

// Forget drops the cached configuration of a namespace (after the stack is deleted).
func (e *Engine) Forget(ns string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	delete(e.cfgs, ns)
}

// Rendered is a release and the hash of its inputs.
type Rendered struct {
	Release Release
	Values  map[string]any
	Hash    string
}

// Render computes the values of a release and the hash of chart + values + post-render settings.
func Render(p *Plan, r Release) (*Rendered, error) {
	vals, err := r.Values(p)
	if err != nil {
		return nil, fmt.Errorf("values of %s: %w", r.Name, err)
	}
	if p.Dev() {
		// Charts only render `replicas` when autoscaling is off: dropping the HPA alone would keep its last scale.
		set(vals, "autoscaling.enabled", false)
	}
	_, digest, err := loadChart(r.Chart)
	if err != nil {
		return nil, err
	}
	s := p.Spec
	h := hashOf(digest, vals, s.Profile, s.Resources[r.Component], s.NodeSelector, s.Tolerations, s.ImagePullSecrets,
		s.RAG.GPU, s.DeletionPolicy, s.Exposure.ExposeInternal, p.UIHost, p.IdentityHost, p.ConfigHash, postRenderVersion)
	return &Rendered{Release: r, Values: vals, Hash: h}, nil
}

// postRenderVersion changes when the post-renderer behaviour changes, forcing upgrades.
const postRenderVersion = 3

// Apply installs the release, or upgrades it; it repairs releases left pending by an interrupted operation.
func (e *Engine) Apply(ctx context.Context, p *Plan, rr *Rendered) (*release.Release, error) {
	cfg, err := e.configuration(ctx, p.Namespace)
	if err != nil {
		return nil, err
	}
	chrt, _, err := loadChart(rr.Release.Chart)
	if err != nil {
		return nil, err
	}
	post := &postRenderer{plan: p, rel: rr.Release}

	last, err := cfg.Releases.Last(rr.Release.Name)
	if err != nil && !errors.Is(err, driver.ErrReleaseNotFound) {
		return nil, err
	}
	if last != nil {
		switch {
		case last.Info.Status == release.StatusPendingInstall, last.Info.Status == release.StatusFailed && last.Version == 1,
			last.Info.Status == release.StatusUninstalling:
			// Never deployed: start over.
			if _, err := e.uninstall(cfg, rr.Release.Name); err != nil {
				return nil, err
			}
			last = nil
		case last.Info.Status.IsPending():
			rb := action.NewRollback(cfg)
			rb.MaxHistory = maxHistory
			if err := rb.Run(rr.Release.Name); err != nil {
				return nil, fmt.Errorf("rollback of interrupted %s: %w", rr.Release.Name, err)
			}
		}
	}
	if last == nil {
		in := action.NewInstall(cfg)
		in.ReleaseName, in.Namespace, in.PostRenderer = rr.Release.Name, p.Namespace, post
		in.Labels = map[string]string{HashLabel: rr.Hash}
		in.Timeout = 5 * time.Minute
		return in.RunWithContext(ctx, chrt, rr.Values)
	}
	up := action.NewUpgrade(cfg)
	up.Namespace, up.PostRenderer, up.MaxHistory = p.Namespace, post, maxHistory
	up.Labels = map[string]string{HashLabel: rr.Hash}
	up.Timeout = 5 * time.Minute
	return up.RunWithContext(ctx, rr.Release.Name, chrt, rr.Values)
}

// Get returns the deployed release, or nil.
func (e *Engine) Get(ctx context.Context, ns, name string) (*release.Release, error) {
	cfg, err := e.configuration(ctx, ns)
	if err != nil {
		return nil, err
	}
	rel, err := cfg.Releases.Last(name)
	if errors.Is(err, driver.ErrReleaseNotFound) {
		return nil, nil
	}
	return rel, err
}

// Uninstall removes a release (no error when it does not exist).
func (e *Engine) Uninstall(ctx context.Context, ns, name string) (*release.Release, error) {
	cfg, err := e.configuration(ctx, ns)
	if err != nil {
		return nil, err
	}
	return e.uninstall(cfg, name)
}

func (e *Engine) uninstall(cfg *action.Configuration, name string) (*release.Release, error) {
	un := action.NewUninstall(cfg)
	un.Timeout = 5 * time.Minute
	res, err := un.Run(name)
	if errors.Is(err, driver.ErrReleaseNotFound) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	return res.Release, nil
}
