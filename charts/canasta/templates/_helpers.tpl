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
Primary public hostname. This is the single source of truth for MediaWiki,
Caddy, cache warming, and ingress-facing application identity.
*/}}
{{- define "canasta.primaryHost" -}}
{{- required "site.primaryHost must be configured" .Values.site.primaryHost -}}
{{- end }}

{{/*
All accepted public hostnames, encoded as JSON so callers can recover a list
with fromJsonArray.
*/}}
{{- define "canasta.hosts" -}}
{{- $hosts := list (include "canasta.primaryHost" .) -}}
{{- range (.Values.site.additionalHosts | default list) -}}
{{- $hosts = append $hosts . -}}
{{- end -}}
{{- $hosts | toJson -}}
{{- end }}

{{/*
Canonical public origin. Local chart users retain plain HTTP for localhost;
deployed hostnames use HTTPS.
*/}}
{{- define "canasta.siteServer" -}}
{{- $host := include "canasta.primaryHost" . -}}
{{- printf "%s://%s" (ternary "http" "https" (eq $host "localhost")) $host -}}
{{- end }}

{{/*
Caddy listener addresses for every accepted hostname.
*/}}
{{- define "canasta.caddySiteAddresses" -}}
{{- $addresses := list -}}
{{- range (include "canasta.hosts" . | fromJsonArray) -}}
{{- $addresses = append $addresses (printf "http://%s" .) -}}
{{- end -}}
{{- join ", " $addresses -}}
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
Backend service for ingress.
Defaults to caddy, but can be overridden for clusters where ingress must
reach a node-local proxy path instead of cross-node pod networking.
*/}}
{{- define "canasta.backendService" -}}
{{- .Values.ingress.backendServiceName | default "caddy" -}}
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
