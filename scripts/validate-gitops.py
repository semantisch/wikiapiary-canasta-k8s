#!/usr/bin/env python3
"""Validate WikiApiary's GitOps contract and hostname migration invariants."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import json
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
    hosts = [primary, *aliases]
    if any(not HOST_PATTERN.fullmatch(host) or host == "localhost" for host in aliases):
        raise RuntimeError(f"invalid site.additionalHosts: {aliases!r}")
    if len(hosts) != len(set(hosts)):
        raise RuntimeError(f"site hostnames must be unique: {hosts!r}")

    edge = values.get("ingress", {}).get("edge", {})
    tls_hosts = edge.get("tlsHosts", [])
    if not isinstance(tls_hosts, list) or not all(isinstance(host, str) for host in tls_hosts):
        raise RuntimeError("ingress.edge.tlsHosts must be a list of hostnames")
    if edge.get("tls") and primary not in tls_hosts:
        raise RuntimeError("the primary host must be covered by ingress.edge.tlsHosts")
    unknown_tls_hosts = set(tls_hosts).difference(hosts)
    if unknown_tls_hosts:
        raise RuntimeError(
            f"edge TLS hosts must also be routed site hosts: {sorted(unknown_tls_hosts)!r}"
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
        "configData.caddy.Caddyfile upstream host": (
            caddy.get("Caddyfile", ""),
            "__PRIMARY_HOST__",
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
        for marker in ("__PRIMARY_HOST__", "__SITE_SERVER__", "__CADDY_SITE_ADDRESSES__")
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
    for component in ("web", "jobrunner"):
        deployment = find_one(documents, "Deployment", f"-{component}")
        env = container_env(deployment, component)
        expected = {"MW_SITE_SERVER": server, "MW_SITE_FQDN": primary}
        actual = {name: env.get(name) for name in expected}
        if actual != expected:
            raise RuntimeError(f"{component} site environment {actual!r} != {expected!r}")

    web_config = find_one(documents, "ConfigMap", "-web-config").get("data", {})
    caddy_config = find_one(documents, "ConfigMap", "-caddy-config").get("data", {})
    checks = {
        "wikis.yaml primary URL": (web_config.get("wikis.yaml", ""), f"url: {primary}"),
        "MediaWiki canonical server": (
            web_config.get("settings--global--00LegacySite.php", ""),
            f"?: '{server}'",
        ),
        "Semantic MediaWiki host": (
            web_config.get("settings--global--04LegacyExtensions.php", ""),
            f"?: '{primary}'",
        ),
        "Caddy primary upstream host": (
            caddy_config.get("Caddyfile", ""),
            f"header_up Host {primary}",
        ),
    }
    caddyfile = caddy_config.get("Caddyfile", "")
    for host in hosts:
        checks[f"Caddy listener {host}"] = (caddyfile, f"http://{host}")
    failed = [name for name, (content, expected) in checks.items() if expected not in content]
    if failed:
        raise RuntimeError(f"rendered hostname checks failed: {', '.join(failed)}")

    cronjobs = [document for document in documents if document.get("kind") == "CronJob"]
    suspended = [job["metadata"]["name"] for job in cronjobs if job["spec"].get("suspend")]
    if suspended:
        raise RuntimeError(f"production cache CronJobs must not be suspended: {suspended!r}")


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
    primary: str,
    hosts: list[str],
    current_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aliases = [host for host in hosts if host != primary and host != CUTOVER_HOST]
    cutover_hosts = [CUTOVER_HOST, primary, *aliases]
    cutover_tls_hosts = [CUTOVER_HOST, primary]
    command = [
        "helm",
        "template",
        "canasta-wikiapiary",
        str(root / "charts/canasta"),
        "-f",
        str(root / "values/prod.yaml"),
        "--set-string",
        f"site.primaryHost={CUTOVER_HOST}",
        "--set-json",
        f"site.additionalHosts={json.dumps(cutover_hosts[1:])}",
        "--set-json",
        f"ingress.edge.tlsHosts={json.dumps(cutover_tls_hosts)}",
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
    render_cutover(root, primary, hosts, rendered_documents)
    print(
        f"GitOps validation passed: primary={primary}, hosts={','.join(hosts)}, "
        f"tested-cutover={CUTOVER_HOST}"
    )


if __name__ == "__main__":
    main()
