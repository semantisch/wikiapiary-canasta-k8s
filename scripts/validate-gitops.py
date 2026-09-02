#!/usr/bin/env python3
"""Validate WikiApiary's GitOps contract and hostname migration invariants."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any

import yaml


HOST_PATTERN = re.compile(
    r"^(localhost|[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+)$"
)
CUTOVER_HOST = "wikiapiary.com"


class UniqueKeyLoader(yaml.SafeLoader):
    """Safe YAML loader that rejects duplicate mapping keys."""


def construct_unique_mapping(
    loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            mark = key_node.start_mark
            raise ValueError(
                f"duplicate YAML key {key!r} at line {mark.line + 1}, "
                f"column {mark.column + 1}"
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
)


def load_documents(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8") as stream:
            loaded = list(yaml.load_all(stream, Loader=UniqueKeyLoader))
    except (yaml.YAMLError, ValueError) as error:
        raise RuntimeError(f"invalid YAML in {path}: {error}") from error
    return [document for document in loaded if isinstance(document, dict)]


def load_one(path: Path) -> dict[str, Any]:
    documents = load_documents(path)
    if len(documents) != 1:
        raise RuntimeError(f"expected one YAML document in {path}, found {len(documents)}")
    return documents[0]


def validate_source_yaml(root: Path) -> None:
    paths = [
        *root.glob("*.yaml"),
        *root.glob("*.yml"),
        *root.glob("argocd/**/*.yaml"),
        *root.glob("bootstrap/**/*.yaml"),
        root / "charts/canasta/values.yaml",
        *root.glob(".github/**/*.yaml"),
        *root.glob(".github/**/*.yml"),
    ]
    for path in sorted(set(paths)):
        load_documents(path)


def validate_site_values(values: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    if "domains" in values:
        raise RuntimeError("deprecated top-level 'domains' is not allowed; use 'site'")
    site = values.get("site")
    if not isinstance(site, dict):
        raise RuntimeError("site must be a mapping")
    primary = site.get("primaryHost")
    aliases = site.get("additionalHosts", [])
    if not isinstance(primary, str) or not HOST_PATTERN.fullmatch(primary):
        raise RuntimeError(f"invalid site.primaryHost: {primary!r}")
    if not isinstance(aliases, list) or not all(isinstance(host, str) for host in aliases):
        raise RuntimeError("site.additionalHosts must be a list of hostnames")
    site_hosts = [primary, *aliases]
    if any(not HOST_PATTERN.fullmatch(host) or host == "localhost" for host in aliases):
        raise RuntimeError(f"invalid site.additionalHosts: {aliases!r}")
    if len(site_hosts) != len(set(site_hosts)):
        raise RuntimeError(f"site hostnames must be unique: {site_hosts!r}")

    edge = values.get("ingress", {}).get("edge", {})
    configured_tls_hosts = edge.get("tlsHosts", [])
    if not isinstance(configured_tls_hosts, list) or not all(
        isinstance(host, str) for host in configured_tls_hosts
    ):
        raise RuntimeError("ingress.edge.tlsHosts must be a list of hostnames")
    if any(
        not HOST_PATTERN.fullmatch(host) or host == "localhost"
        for host in configured_tls_hosts
    ):
        raise RuntimeError(f"invalid ingress.edge.tlsHosts: {configured_tls_hosts!r}")
    if len(configured_tls_hosts) != len(set(configured_tls_hosts)):
        raise RuntimeError(
            f"ingress.edge.tlsHosts must be unique: {configured_tls_hosts!r}"
        )

    # Mirrors are routed and certificate-covered automatically. Explicit edge
    # TLS hosts double as retained routing aliases, so a primaryHost-only
    # cutover keeps the former canonical hostname reachable.
    hosts = list(dict.fromkeys([*site_hosts, *configured_tls_hosts]))
    tls_hosts = (
        list(dict.fromkeys([*site_hosts, *configured_tls_hosts]))
        if edge.get("tls")
        else []
    )

    config_data = values.get("configData", {})
    web = config_data.get("web", {})
    caddy = config_data.get("caddy", {})
    required_markers = {
        "configData.web.wikis.yaml": (web.get("wikis.yaml", ""), "__PRIMARY_HOST__"),
        "configData.web.settings--global--00LegacySite.php": (
            web.get("settings--global--00LegacySite.php", ""),
            "__SITE_SERVER__",
        ),
        "configData.web.settings--wikis--main--00MirrorOrigin.php accepted hosts": (
            web.get("settings--wikis--main--00MirrorOrigin.php", ""),
            "__SITE_HOSTS_CSV__",
        ),
        "configData.web.settings--wikis--main--00MirrorOrigin.php canonical server": (
            web.get("settings--wikis--main--00MirrorOrigin.php", ""),
            "__SITE_SERVER__",
        ),
        "configData.web.settings--global--04LegacyExtensions.php": (
            web.get("settings--global--04LegacyExtensions.php", ""),
            "__PRIMARY_HOST__",
        ),
        "configData.web.settings--global--05Footer.php": (
            web.get("settings--global--05Footer.php", ""),
            "__SITE_SERVER__",
        ),
        "configData.caddy.Caddyfile listeners": (
            caddy.get("Caddyfile", ""),
            "__CADDY_SITE_ADDRESSES__",
        ),
    }
    missing = [name for name, (content, marker) in required_markers.items() if marker not in content]
    if missing:
        raise RuntimeError(f"hostname placeholders missing from: {', '.join(missing)}")
    return primary, hosts, tls_hosts


def find_one(
    documents: Iterable[dict[str, Any]], kind: str, name_suffix: str
) -> dict[str, Any]:
    matches = [
        document
        for document in documents
        if document.get("kind") == kind
        and str(document.get("metadata", {}).get("name", "")).endswith(name_suffix)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {kind} ending in {name_suffix!r}, found {len(matches)}"
        )
    return matches[0]


def container_env(workload: dict[str, Any], container_name: str) -> dict[str, str]:
    containers = workload["spec"]["template"]["spec"]["containers"]
    matches = [container for container in containers if container.get("name") == container_name]
    if len(matches) != 1:
        raise RuntimeError(f"expected one {container_name!r} container")
    return {
        item["name"]: str(item["value"])
        for item in matches[0].get("env", [])
        if "name" in item and "value" in item
    }


def validate_rendered(
    documents: list[dict[str, Any]], primary: str, hosts: list[str], tls_hosts: list[str]
) -> None:
    unresolved = [
        marker
        for marker in (
            "__PRIMARY_HOST__",
            "__SITE_SERVER__",
            "__SITE_HOSTS_CSV__",
            "__CADDY_SITE_ADDRESSES__",
        )
        if any(marker in str(document) for document in documents)
    ]
    if unresolved:
        raise RuntimeError(f"rendered manifests contain unresolved markers: {unresolved!r}")

    expected_hosts = set(hosts)
    ingresses = [document for document in documents if document.get("kind") == "Ingress"]
    if len(ingresses) != 2:
        raise RuntimeError(f"expected the internal and edge ingresses, found {len(ingresses)}")
    for ingress in ingresses:
        actual_hosts = {rule.get("host") for rule in ingress["spec"].get("rules", [])}
        if actual_hosts != expected_hosts:
            name = ingress["metadata"]["name"]
            raise RuntimeError(f"Ingress/{name} hosts {actual_hosts!r} != {expected_hosts!r}")

    internal = next(
        ingress
        for ingress in ingresses
        if ingress["metadata"].get("namespace") != "bunkerweb"
    )
    if internal["metadata"].get("annotations", {}).get(
        "bunkerweb.io/USE_LIMIT_CONN"
    ) != "no":
        raise RuntimeError(
            "production must disable per-IP BunkerWeb connection limiting "
            "while the upstream load balancer presents a shared source IP"
        )

    edge = next(
        ingress for ingress in ingresses if ingress["metadata"].get("namespace") == "bunkerweb"
    )
    rendered_tls_hosts = {
        host
        for tls_entry in edge["spec"].get("tls", [])
        for host in tls_entry.get("hosts", [])
    }
    if rendered_tls_hosts != set(tls_hosts):
        raise RuntimeError(
            f"edge TLS hosts {rendered_tls_hosts!r} != configured {set(tls_hosts)!r}"
        )

    server = f"http://{primary}" if primary == "localhost" else f"https://{primary}"
    hosts_csv = ",".join(hosts)
    for component in ("web", "jobrunner"):
        deployment = find_one(documents, "Deployment", f"-{component}")
        env = container_env(deployment, component)
        expected = {
            "MW_SITE_SERVER": server,
            "MW_SITE_FQDN": primary,
            "MW_SITE_HOSTS": hosts_csv,
        }
        actual = {name: env.get(name) for name in expected}
        if actual != expected:
            raise RuntimeError(f"{component} site environment {actual!r} != {expected!r}")

    varnish = find_one(documents, "Deployment", "-varnish")
    varnish_env = container_env(varnish, "varnish")
    if varnish_env.get("VARNISH_SIZE") != "4G":
        raise RuntimeError(
            f"production Varnish cache is not 4G: {varnish_env.get('VARNISH_SIZE')!r}"
        )
    varnish_container = next(
        container
        for container in varnish["spec"]["template"]["spec"]["containers"]
        if container.get("name") == "varnish"
    )
    varnish_image = str(varnish_container.get("image", ""))
    if not varnish_image.startswith("docker.io/library/varnish:") or "@sha256:" not in varnish_image:
        raise RuntimeError(f"Varnish image is not digest-pinned: {varnish_image!r}")
    varnish_resources = varnish_container.get("resources", {})
    if varnish_resources.get("requests", {}).get("memory") != "4Gi" or (
        varnish_resources.get("limits", {}).get("memory") != "5Gi"
    ):
        raise RuntimeError(
            f"Varnish memory does not safely contain its 4G cache: {varnish_resources!r}"
        )
    for component, deployment in (
        ("Varnish", varnish),
        ("Caddy", find_one(documents, "Deployment", "-caddy")),
    ):
        rolling = deployment.get("spec", {}).get("strategy", {}).get("rollingUpdate", {})
        if rolling != {"maxUnavailable": 1, "maxSurge": 0}:
            raise RuntimeError(f"{component} rollout does not preserve strict spreading: {rolling!r}")
        anti_affinity = (
            deployment["spec"]["template"]["spec"]
            .get("affinity", {})
            .get("podAntiAffinity", {})
            .get("requiredDuringSchedulingIgnoredDuringExecution", [])
        )
        if not anti_affinity:
            raise RuntimeError(f"{component} replicas do not require distinct nodes")

    web_config = find_one(documents, "ConfigMap", "-web-config").get("data", {})
    caddy_config = find_one(documents, "ConfigMap", "-caddy-config").get("data", {})
    varnish_config = find_one(documents, "ConfigMap", "-varnish-config").get("data", {})
    foreground_config = find_one(documents, "ConfigMap", "-foreground-modern").get("data", {})
    foreground_css = foreground_config.get("wikiapiary-modern.css", "")
    foreground_js = foreground_config.get("wikiapiary-modern.js", "")
    for name, content in web_config.items():
        if not name.endswith(".php"):
            continue
        with tempfile.NamedTemporaryFile(
            mode="w+", suffix=".php", encoding="utf-8"
        ) as php_file:
            php_file.write(content)
            php_file.flush()
            lint = subprocess.run(
                ["php", "-l", php_file.name],
                check=False,
                text=True,
                capture_output=True,
            )
        if lint.returncode != 0:
            raise RuntimeError(
                f"rendered PHP setting {name} failed syntax validation:\n"
                f"{lint.stdout}{lint.stderr}"
            )
    with tempfile.NamedTemporaryFile(
        mode="w+", suffix=".js", encoding="utf-8"
    ) as js_file:
        js_file.write(foreground_js)
        js_file.flush()
        lint = subprocess.run(
            ["node", "--check", js_file.name],
            check=False,
            text=True,
            capture_output=True,
        )
    if lint.returncode != 0:
        raise RuntimeError(
            "rendered Foreground enhancement JavaScript failed syntax validation:\n"
            f"{lint.stdout}{lint.stderr}"
        )

    foreground_markers = {
        "brand palette": "--wa-brand: #f5b700",
        "Main Page translation notice removal": ".mw-pt-translate-header",
        "Main Page stats card": "table tr:first-child th",
        "keyboard focus": ":focus-visible",
        "responsive layout": "@media only screen and (max-width: 40em)",
    }
    missing_foreground = [
        name for name, marker in foreground_markers.items() if marker not in foreground_css
    ]
    if missing_foreground:
        raise RuntimeError(
            f"Foreground enhancement checks failed: {', '.join(missing_foreground)}"
        )
    if "aria-label" not in foreground_js or "aria-haspopup" not in foreground_js:
        raise RuntimeError("Foreground navigation enhancement must retain accessible labels")

    web_deployment = find_one(documents, "Deployment", "-web")
    web_pod_spec = web_deployment["spec"]["template"]["spec"]
    web_container = next(
        container for container in web_pod_spec["containers"] if container.get("name") == "web"
    )
    mounted_subpaths = {
        mount.get("subPath") for mount in web_container.get("volumeMounts", [])
    }
    required_foreground_mounts = {"wikiapiary-modern.css", "wikiapiary-modern.js"}
    if not required_foreground_mounts.issubset(mounted_subpaths):
        raise RuntimeError("web deployment does not mount both Foreground enhancement assets")
    checks = {
        "wikis.yaml primary URL": (web_config.get("wikis.yaml", ""), f"url: {primary}"),
        "MediaWiki canonical server": (
            web_config.get("settings--global--00LegacySite.php", ""),
            f"?: '{server}'",
        ),
        "MediaWiki accepted hosts": (
            web_config.get("settings--wikis--main--00MirrorOrigin.php", ""),
            f"?: '{hosts_csv}'",
        ),
        "MediaWiki trusted request-host handoff": (
            web_config.get("settings--wikis--main--00MirrorOrigin.php", ""),
            "HTTP_X_WIKIAPIARY_REQUEST_HOST",
        ),
        "Semantic MediaWiki host": (
            web_config.get("settings--global--04LegacyExtensions.php", ""),
            f"?: '{primary}'",
        ),
        "Foreground ResourceLoader styles": (
            web_config.get("settings--global--03Foreground.php", ""),
            "addModuleStyles( 'skins.foreground.wikiapiary' )",
        ),
        "Foreground ResourceLoader scripts": (
            web_config.get("settings--global--03Foreground.php", ""),
            "addModules( 'skins.foreground.wikiapiary' )",
        ),
        "Varnish requested-host handoff": (
            varnish_config.get("default.vcl", ""),
            "set bereq.http.X-WikiApiary-Request-Host = bereq.http.Host;",
        ),
        "Varnish canonical Canasta backend host": (
            varnish_config.get("default.vcl", ""),
            f'set bereq.http.Host = "{primary}";',
        ),
        "Varnish error responses are uncacheable": (
            varnish_config.get("default.vcl", ""),
            "if (beresp.status >= 400)",
        ),
        "Varnish internal refresh bypass": (
            varnish_config.get("default.vcl", ""),
            "set req.hash_always_miss = true;",
        ),
        "Varnish dedicated refresh listener": (
            varnish_config.get("default.vcl", ""),
            'local.socket == "cache-admin"',
        ),
        "Caddy cache-health route": (
            caddy_config.get("Caddyfile.site", ""),
            "@cache_health path /healthz/cache",
        ),
    }
    caddyfile = caddy_config.get("Caddyfile", "")
    for host in hosts:
        checks[f"Caddy listener {host}"] = (caddyfile, f"http://{host}")
    failed = [name for name, (content, expected) in checks.items() if expected not in content]
    if failed:
        raise RuntimeError(f"rendered hostname checks failed: {', '.join(failed)}")
    if "header_up Host" in caddyfile:
        raise RuntimeError("Caddy must preserve each accepted request Host")

    cronjobs = [document for document in documents if document.get("kind") == "CronJob"]
    suspended = [job["metadata"]["name"] for job in cronjobs if job["spec"].get("suspend")]
    if suspended:
        raise RuntimeError(f"production cache CronJobs must not be suspended: {suspended!r}")
    for cronjob in cronjobs:
        pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
        container = pod_spec["containers"][0]
        image = str(container.get("image", ""))
        if not image.startswith("docker.io/library/php:") or "@sha256:" not in image:
            raise RuntimeError(f"cache CronJob runtime is not digest-pinned: {image!r}")
        if pod_spec.get("nodeSelector") != {"wikiapiary-role": "worker"}:
            raise RuntimeError("cache CronJobs must target the NFS-capable worker pool")

    rewarm = find_one(documents, "Deployment", "-cache-rewarm-worker")
    rewarm_spec = rewarm["spec"]["template"]["spec"]
    rewarm_container = rewarm_spec["containers"][0]
    if not rewarm_container.get("livenessProbe", {}).get("exec", {}).get("command"):
        raise RuntimeError("cache rewarm worker must have a heartbeat liveness probe")
    if rewarm_spec.get("nodeSelector") != {"wikiapiary-role": "worker"}:
        raise RuntimeError("cache rewarm worker must target the NFS-capable worker pool")

    varnish_headless = find_one(documents, "Service", "varnish-headless")
    if varnish_headless.get("spec", {}).get("publishNotReadyAddresses"):
        raise RuntimeError("cache warming must not target unready Varnish replicas")


def validate_argocd(application: dict[str, Any]) -> None:
    source = application.get("spec", {}).get("source", {})
    expected = {
        "repoURL": "https://github.com/semantisch/wikiapiary-canasta-k8s.git",
        "targetRevision": "main",
        "path": "charts/canasta",
    }
    actual = {name: source.get(name) for name in expected}
    if actual != expected:
        raise RuntimeError(f"Argo CD source {actual!r} != {expected!r}")
    value_files = source.get("helm", {}).get("valueFiles", [])
    if value_files != ["../../values/prod.yaml"]:
        raise RuntimeError(f"unexpected Argo CD valueFiles: {value_files!r}")
    automated = application.get("spec", {}).get("syncPolicy", {}).get("automated", {})
    if automated.get("prune") is not True or automated.get("selfHeal") is not True:
        raise RuntimeError("Argo CD must keep prune and selfHeal enabled")


def render_cutover(
    root: Path,
    hosts: list[str],
    tls_hosts: list[str],
    current_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    # The helper orders the new primary first, then site mirrors, then retained
    # TLS aliases (including the former primary).
    cutover_hosts = list(dict.fromkeys([CUTOVER_HOST, *hosts[1:], hosts[0]]))
    cutover_tls_hosts = list(
        dict.fromkeys([CUTOVER_HOST, *tls_hosts[1:], tls_hosts[0]])
    )
    command = [
        "helm",
        "template",
        "canasta-wikiapiary",
        str(root / "charts/canasta"),
        "-f",
        str(root / "values/prod.yaml"),
        "--set-string",
        f"site.primaryHost={CUTOVER_HOST}",
    ]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"cutover render failed:\n{result.stdout}\n{result.stderr}")
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml", encoding="utf-8") as rendered:
        rendered.write(result.stdout)
        rendered.flush()
        documents = load_documents(Path(rendered.name))
    validate_rendered(documents, CUTOVER_HOST, cutover_hosts, cutover_tls_hosts)
    current_caddy = find_one(current_documents, "Deployment", "-caddy")
    cutover_caddy = find_one(documents, "Deployment", "-caddy")
    current_checksum = current_caddy["spec"]["template"]["metadata"]["annotations"].get(
        "checksum/caddy-config"
    )
    cutover_checksum = cutover_caddy["spec"]["template"]["metadata"]["annotations"].get(
        "checksum/caddy-config"
    )
    if not current_checksum or current_checksum == cutover_checksum:
        raise RuntimeError("hostname cutover must change the Caddy pod checksum")
    for component in ("web", "jobrunner"):
        current_workload = find_one(current_documents, "Deployment", f"-{component}")
        cutover_workload = find_one(documents, "Deployment", f"-{component}")
        current_site_checksum = current_workload["spec"]["template"]["metadata"][
            "annotations"
        ].get("checksum/site-hosts")
        cutover_site_checksum = cutover_workload["spec"]["template"]["metadata"][
            "annotations"
        ].get("checksum/site-hosts")
        if not current_site_checksum or current_site_checksum == cutover_site_checksum:
            raise RuntimeError(
                f"hostname cutover must change the {component} site-host checksum"
            )
    current_varnish = find_one(current_documents, "Deployment", "-varnish")
    cutover_varnish = find_one(documents, "Deployment", "-varnish")
    current_varnish_checksum = current_varnish["spec"]["template"]["metadata"][
        "annotations"
    ].get("checksum/varnish-config")
    cutover_varnish_checksum = cutover_varnish["spec"]["template"]["metadata"][
        "annotations"
    ].get("checksum/varnish-config")
    if not current_varnish_checksum or current_varnish_checksum == cutover_varnish_checksum:
        raise RuntimeError("hostname cutover must change the Varnish pod checksum")
    return documents


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("rendered", type=Path, help="path to helm template output")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    root = args.root.resolve()
    validate_source_yaml(root)
    values = load_one(root / "values/prod.yaml")
    primary, hosts, tls_hosts = validate_site_values(values)
    validate_argocd(load_one(root / "argocd/wikiapiary.yaml"))
    rendered_documents = load_documents(args.rendered)
    validate_rendered(rendered_documents, primary, hosts, tls_hosts)
    render_cutover(root, hosts, tls_hosts, rendered_documents)
    print(
        f"GitOps validation passed: primary={primary}, hosts={','.join(hosts)}, "
        f"tested-primaryHost-only-cutover={CUTOVER_HOST}"
    )


if __name__ == "__main__":
    main()
