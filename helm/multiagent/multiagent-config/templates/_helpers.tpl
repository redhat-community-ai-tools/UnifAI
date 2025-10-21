{{/*
Expand the name of the chart.
*/}}
{{- define "multiagent-config.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "multiagent-config.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "multiagent-config.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "multiagent-config.labels" -}}
helm.sh/chart: {{ include "multiagent-config.chart" . }}
{{ include "multiagent-config.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "multiagent-config.selectorLabels" -}}
app.kubernetes.io/name: {{ include "multiagent-config.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "multiagent-config.serviceAccountName" -}}
{{- if .Values.serviceDiscovery.rbac.serviceAccount.create }}
{{- default (printf "%s-%s" (include "multiagent-config.fullname" .) "sa") .Values.serviceDiscovery.rbac.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceDiscovery.rbac.serviceAccount.name }}
{{- end }}
{{- end }}
