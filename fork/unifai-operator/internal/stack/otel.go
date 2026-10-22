package stack

import (
	"sort"
	"strings"
)

// otelEnv sets the OTEL_* environment read by the global_utils telemetry bootstrap (inert without an endpoint).
// Without spec.openTelemetry nothing is set, so the upstream values (if any) apply.
func otelEnv(p *Plan, v map[string]any, service string) {
	o := p.Spec.OpenTelemetry
	if o == nil {
		return
	}
	set(v, "env.UNIFAI_OTEL_ENABLED", "true")
	set(v, "env.OTEL_EXPORTER_OTLP_ENDPOINT", o.Endpoint)
	if o.Protocol != "" {
		set(v, "env.OTEL_EXPORTER_OTLP_PROTOCOL", o.Protocol)
	}
	set(v, "env.OTEL_SERVICE_NAME", service)
	if o.Sampler != "" {
		set(v, "env.OTEL_TRACES_SAMPLER", o.Sampler)
	}
	if o.SamplerArg != "" {
		set(v, "env.OTEL_TRACES_SAMPLER_ARG", o.SamplerArg)
	}
	if o.DisableMetrics {
		set(v, "env.OTEL_METRICS_EXPORTER", "none")
	}
	attrs := map[string]string{"k8s.namespace.name": p.Namespace}
	for k, val := range o.ResourceAttributes {
		attrs[k] = val
	}
	keys := make([]string, 0, len(attrs))
	for k := range attrs {
		keys = append(keys, k)
	}
	sort.Strings(keys) // stable values: no needless Helm upgrade
	pairs := make([]string, 0, len(keys))
	for _, k := range keys {
		pairs = append(pairs, k+"="+attrs[k])
	}
	set(v, "env.OTEL_RESOURCE_ATTRIBUTES", strings.Join(pairs, ","))
}
