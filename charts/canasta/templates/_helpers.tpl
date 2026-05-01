{{/*
Create a default fully qualified app name.
*/}}
{{- define "canasta.fullname" -}}
{{- if .Values.instance.id }}
{{- printf "canasta-%s" .Values.instance.id | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Namespace for this instance.
*/}}
{{- define "canasta.namespace" -}}
{{- printf "canasta-%s" .Values.instance.id }}
{{- end }}

{{/*
Canasta image with tag.
*/}}
{{- define "canasta.image" -}}
{{- $tag := .Values.image.tag | default .Chart.AppVersion }}
{{- printf "%s:%s" .Values.image.repository $tag }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "canasta.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Values.instance.id | default .Release.Name }}
app.kubernetes.io/part-of: canasta
{{- end }}

{{/*
Selector labels for a specific component.
*/}}
{{- define "canasta.selectorLabels" -}}
app.kubernetes.io/name: canasta
app.kubernetes.io/instance: {{ .Values.instance.id | default .Release.Name }}
{{- end }}

{{/*
DB secret name.
*/}}
{{- define "canasta.dbSecretName" -}}
{{- .Values.secrets.dbSecretName | default (printf "%s-db-credentials" .Values.instance.id) }}
{{- end }}

{{/*
MW secret name.
*/}}
{{- define "canasta.mwSecretName" -}}
{{- .Values.secrets.mwSecretName | default (printf "%s-mw-secrets" .Values.instance.id) }}
{{- end }}

{{/*
Backend service for ingress — always routes to caddy.
Caddy handles wiki farm routing, then forwards to varnish or web.
*/}}
{{- define "canasta.backendService" -}}
caddy
{{- end }}

{{/*
Caddy upstream (varnish if enabled, otherwise web).
*/}}
{{- define "canasta.caddyBackend" -}}
{{- if .Values.varnish.enabled -}}
varnish:80
{{- else -}}
web:80
{{- end -}}
{{- end }}
