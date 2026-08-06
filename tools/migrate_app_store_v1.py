#!/usr/bin/env python3
"""One-time, idempotent migration of legacy App Store manifests to schema v1."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "app-store-templates"

IMAGE_PINS = {
    "registry:23": "registry:3.0.0",
    "adminer:latest": "adminer:5.5.1",
    "guacamole/guacd:latest": "guacamole/guacd:1.6.0",
    "guacamole/guacamole:latest": "guacamole/guacamole:1.6.0",
    "lscr.io/linuxserver/bookstack:latest": "lscr.io/linuxserver/bookstack:version-v25.05.2",
    "lscr.io/linuxserver/mariadb:latest": "mariadb:11.4.8",
    "crowdsecurity/crowdsec:latest": "crowdsecurity/crowdsec:v1.6.4",
    "crowdsecurity/cs-firewall-bouncer:latest": "crowdsecurity/cs-firewall-bouncer:v0.0.34",
    "joxit/docker-registry-ui:latest": "joxit/docker-registry-ui:2.5.7",
    "powerdnsadmin/pda-legacy:latest": "powerdnsadmin/pda-legacy:0.4.2",
    "lscr.io/linuxserver/emby:latest": "emby/embyserver:4.8.11.0",
    "gitea/gitea:latest": "gitea/gitea:1.24.3",
    "gitlab/gitlab-ce:latest": "gitlab/gitlab-ce:18.2.1-ce.0",
    "grafana/grafana:latest": "grafana/grafana:12.1.0",
    "lscr.io/linuxserver/heimdall:latest": "lscr.io/linuxserver/heimdall:version-2.7.6",
    "ghcr.io/home-assistant/home-assistant:stable": "ghcr.io/home-assistant/home-assistant:2025.7.4",
    "ghcr.io/immich-app/immich-server:release": "ghcr.io/immich-app/immich-server:v1.136.0",
    "ghcr.io/immich-app/immich-machine-learning:release": "ghcr.io/immich-app/immich-machine-learning:v1.136.0",
    "influxdb:latest": "influxdb:2.7.12",
    "lscr.io/linuxserver/jellyfin:latest": "jellyfin/jellyfin:10.10.7",
    "jenkins/jenkins:lts": "jenkins/jenkins:2.516.1-lts-jdk21",
    "jitsi/web:stable": "jitsi/web:stable-10184",
    "jitsi/prosody:stable": "jitsi/prosody:stable-10184",
    "jitsi/jicofo:stable": "jitsi/jicofo:stable-10184",
    "jitsi/jvb:stable": "jitsi/jvb:stable-10184",
    "jupyter/datascience-notebook:latest": "jupyter/datascience-notebook:2025-03-14",
    "quay.io/keycloak/keycloak:latest": "quay.io/keycloak/keycloak:26.3.2",
    "grafana/loki:latest": "grafana/loki:3.5.3",
    "matrixdotorg/synapse:latest": "matrixdotorg/synapse:v1.136.0",
    "vectorim/element-web:latest": "vectorim/element-web:v1.11.106",
    "mattermost/mattermost-team-edition:latest": "mattermost/mattermost-team-edition:10.10.1",
    "quay.io/minio/minio:latest": "quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z",
    "mongo:latest": "mongo:8.0.13",
    "ghcr.io/motioneye-project/motioneye:latest": "ghcr.io/motioneye-project/motioneye:0.43.1",
    "mysql:latest": "mysql:8.4.6",
    "n8nio/n8n:latest": "n8nio/n8n:1.105.4",
    "nextcloud:latest": "nextcloud:31.0.8-apache",
    "jc21/nginx-proxy-manager:latest": "jc21/nginx-proxy-manager:2.12.3",
    "octoprint/octoprint:latest": "octoprint/octoprint:1.11.2",
    "ollama/ollama:latest": "ollama/ollama:0.11.2",
    "lscr.io/linuxserver/ombi:latest": "lscr.io/linuxserver/ombi:version-v4.47.1",
    "onlyoffice/mailserver:latest": "onlyoffice/mailserver:1.6.27",
    "onlyoffice/documentserver:latest": "onlyoffice/documentserver:8.3.3",
    "onlyoffice/communityserver:latest": "onlyoffice/communityserver:12.6.0.1900",
    "ghcr.io/open-webui/open-webui:main": "ghcr.io/open-webui/open-webui:v0.6.22",
    "bitnami/openldap:latest": "osixia/openldap:1.5.0",
    "osixia/phpldapadmin:latest": "osixia/phpldapadmin:0.9.0",
    "kylemanna/openvpn:latest": "kylemanna/openvpn:2.4",
    "ghcr.io/paperless-ngx/paperless-ngx:latest": "ghcr.io/paperless-ngx/paperless-ngx:2.18.1",
    "phpmyadmin:latest": "phpmyadmin:5.2.2-apache",
    "pihole/pihole:latest": "pihole/pihole:2025.04.0",
    "lscr.io/linuxserver/plex:latest": "plexinc/pms-docker:1.42.1.10060-4e8b05daf",
    "postgres:latest": "postgres:16.10-alpine",
    "prom/prometheus:latest": "prom/prometheus:v3.5.0",
    "redis:latest": "redis:7.4.5-alpine",
    "roundcube/roundcubemail:latest": "roundcube/roundcubemail:1.6.11-apache",
    "rustdesk/rustdesk-server:latest": "rustdesk/rustdesk-server:1.1.14",
    "stirlingtools/stirling-pdf:latest": "stirlingtools/stirling-pdf:0.46.2",
    "teamspeak:latest": "teamspeak:3.13.7",
    "traefik:latest": "traefik:3.5.0",
    "ghcr.io/chrisbenincasa/tunarr:latest": "ghcr.io/chrisbenincasa/tunarr:0.22.0",
    "typo3/typo3:latest": "typo3/typo3:13.4.14",
    "louislam/uptime-kuma:1": "louislam/uptime-kuma:1.23.16",
    "vaultwarden/server:latest": "vaultwarden/server:1.34.3",
    "ghcr.io/wg-easy/wg-easy:latest": "ghcr.io/wg-easy/wg-easy:15.1.0",
    "woodpeckerci/woodpecker-server:latest": "woodpeckerci/woodpecker-server:v3.9.0",
    "woodpeckerci/woodpecker-agent:latest": "woodpeckerci/woodpecker-agent:v3.9.0",
    "wordpress:latest": "wordpress:6.8.2-php8.3-apache",
    "koenkk/zigbee2mqtt:latest": "koenkk/zigbee2mqtt:2.6.1",
    "mcuadros/ofelia:latest": "mcuadros/ofelia:0.3.19",
    "memcached:alpine": "memcached:1.6.39-alpine",
    "postgres:15-alpine": "postgres:15.13-alpine",
    "postgres:16-alpine": "postgres:16.9-alpine",
    "redis:7-alpine": "redis:7.4.5-alpine",
    "mariadb:10.11": "mariadb:10.11.13",
    "mariadb:11": "mariadb:11.4.8",
    "neo4j:5": "neo4j:5.26.9-community",
    "mysql:8.0": "mysql:8.0.43",
    "docker.io/library/redis:7": "docker.io/library/redis:7.4.5-alpine",
    "docker.io/library/postgres:16": "docker.io/library/postgres:16.9-alpine",
    "rabbitmq:4-management": "rabbitmq:4.1.3-management",
    "eclipse-mosquitto:2": "eclipse-mosquitto:2.0.22",
}

APP_VERSIONS = {
    "adminer": "5.5.1", "apache-guacamole": "1.6.0", "bookstack": "25.05.2",
    "crowdsec": "1.6.4", "docker-registry": "3.0.0", "domain-locker": "0.4.2",
    "emby": "4.8.11.0", "gitea": "1.24.3", "gitlab": "18.2.1",
    "grafana": "12.1.0", "heimdall": "2.7.6", "home-assistant": "2025.7.4",
    "immich": "1.136.0", "influxdb": "2.7.12", "jellyfin": "10.10.7",
    "jenkins": "2.516.1", "jitsi": "10184", "jupyter": "2025.03.14",
    "keycloak": "26.3.2", "loki": "3.5.3", "matrix-synapse": "1.136.0",
    "mattermost": "10.10.1", "minio": "2024.12.18", "mongodb": "8.0.13",
    "mailcow": "2025.03.31", "harbor": "2.11.0",
    "motioneye": "0.43.1", "mysql": "8.4.6", "n8n": "1.105.4",
    "nextcloud": "31.0.8", "nginx-proxy-manager": "2.12.3", "octoprint": "1.11.2",
    "ollama": "0.11.2", "ombi": "4.47.1", "onlyoffice-docs": "8.3.3",
    "open-webui": "0.6.22", "openldap": "1.5.0", "openvpn": "2.4",
    "paperless-ngx": "2.18.1", "phpmyadmin": "5.2.2", "pihole": "2025.04.0",
    "plex": "1.42.1", "postgres": "16.10", "prometheus": "3.5.0",
    "redis": "7.4.5", "roundcube": "1.6.11", "rustdesk": "1.1.14",
    "stirling-pdf": "0.46.2", "teamspeak": "3.13.7", "traefik": "3.5.0",
    "tunarr": "0.22.0", "typo3": "13.4.14", "uptime-kuma": "1.23.16",
    "vaultwarden": "1.34.3", "wireguard": "15.1.0", "woodpecker-ci": "3.9.0",
    "wordpress": "6.8.2", "zigbee2mqtt": "2.6.1",
}

ALIASES = {
    "apache-guacamole": {"POSTGRESQL_PASSWORD": "POSTGRES_PASSWORD"},
    "bookstack": {"MYSQL_PASSWORD": "DB_PASSWORD"},
    "elasticsearch": {"ELASTICSEARCH_PASSWORD": "ELASTIC_PASSWORD"},
    "harbor": {"POSTGRES_PASSWORD": "DATABASE_PASSWORD"},
    "immich": {"POSTGRES_PASSWORD": "DB_PASSWORD"},
    "keycloak": {"POSTGRES_PASSWORD": "KC_DB_PASSWORD"},
    "mailcow": {"MYSQL_ROOT_PASSWORD": "DBROOT", "MYSQL_PASSWORD": "DBPASS"},
    "neo4j": {"NEO4J_AUTH": "NEO4J_PASSWORD"},
    "onlyoffice-docs": {
        "MYSQL_PASSWORD": "MYSQL_SERVER_PASS",
        "DOCUMENT_SERVER_JWT_SECRET": "JWT_SECRET",
        "MAIL_SERVER_DB_PASS": "MYSQL_SERVER_PASS",
    },
    "paperless-ngx": {"POSTGRES_PASSWORD": "PAPERLESS_DBPASS"},
    "typo3": {"MYSQL_PASSWORD": "TYPO3_DB_PASSWORD"},
    "wordpress": {"MYSQL_PASSWORD": "WORDPRESS_DB_PASSWORD"},
}

USER_SUPPLIED_SECRETS = {"PASSWORD_HASH", "WOODPECKER_GITEA_SECRET"}
EXPLICIT_SECRETS = {
    "crowdsec": {"CROWDSEC_LAPI_KEY"},
    "mailcow": {"DBROOT"},
    "neo4j": {"NEO4J_PASSWORD"},
}
DROP_ENVIRONMENT = {
    "elasticsearch": {"discovery.type", "xpack.security.enabled"},
    "mattermost": {"MM_SQLSETTINGS_DATASOURCE"},
}
USER_SUPPLIED_SECRETS.add("CROWDSEC_LAPI_KEY")
PLACEHOLDER_VALUES = ("changeme", "password", "passw0rd", "harbor12345", "mytoken")
SECRET_EXCLUSIONS = {"SHOW_PASSWORD_HINT", "MAILCOW_PASS_SCHEME"}


def _secret(name: str) -> bool:
    upper = name.upper()
    return upper not in SECRET_EXCLUSIONS and any(
        marker in upper for marker in ("PASSWORD", "PASS", "SECRET", "TOKEN", "CREDENTIAL")
    )


def _label(name: str) -> str:
    return name.replace("_", " ").title()


def _port(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {
            "host": int(value["host"]),
            "container": int(value["container"]),
            "protocol": value.get("protocol", "tcp"),
            "description": value.get("description", ""),
        }
    host, container = str(value).split(":", 1)
    protocol = "udp" if container.endswith("/udp") else "tcp"
    container = container.removesuffix("/udp").removesuffix("/tcp")
    return {
        "host": int(host), "container": int(container), "protocol": protocol,
        "description": "",
    }


def _volume(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "host": str(value["host"]), "container": str(value["container"]),
            "mode": value.get("mode", "rw"), "description": value.get("description", ""),
        }
    parts = str(value).split(":")
    mode = "ro" if parts[-1] == "ro" else "rw"
    if parts[-1] in {"ro", "rw"}:
        parts.pop()
    return {"host": parts[0], "container": parts[1], "mode": mode, "description": ""}


def _compose_environment(compose: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for service in (compose.get("services") or {}).values():
        environment = (service or {}).get("environment") or {}
        if isinstance(environment, dict):
            for name, value in environment.items():
                result.setdefault(str(name), "" if value is None else str(value))
        elif isinstance(environment, list):
            for item in environment:
                if isinstance(item, str) and "=" in item:
                    name, value = item.split("=", 1)
                    result.setdefault(name, value)
    return result


def _legacy_environment(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    environment = manifest.get("environment", {})
    if isinstance(environment, dict):
        for name, default in environment.items():
            result[name] = {"default": str(default), "description": ""}
    else:
        for item in environment:
            result[item["name"]] = {
                "default": str(item.get("default", "")),
                "description": item.get("description", ""),
                "required": bool(item.get("required", False)),
                "secret": bool(item.get("secret", False)),
                "generate": bool(item.get("generate", False)),
                "min_length": item.get("min_length"),
                "managed": bool(item.get("managed", False)),
                "generator": item.get("generator"),
            }
    return result


def _replace_assignment(
    text: str,
    key: str,
    source: str,
    *,
    required: bool = True,
    default: str = "",
) -> str:
    expression = (
        f"${{{source}:?{source} is required}}"
        if required and not default
        else f"${{{source}:-{default}}}"
    )
    text = re.sub(
        rf"^(\s*-\s*{re.escape(key)}=).*$",
        lambda match: match.group(1) + expression,
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        rf"^(\s*{re.escape(key)}:\s*).*$",
        lambda match: match.group(1) + json.dumps(expression),
        text,
        flags=re.MULTILINE,
    )
    return text


def migrate(directory: Path) -> None:
    manifest_path = directory / "app.json"
    compose_path = directory / "docker-compose.yml"
    if not manifest_path.exists() or not compose_path.exists():
        raise RuntimeError(f"incomplete template: {directory.name}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    compose_text = compose_path.read_text(encoding="utf-8")
    compose_text = re.sub(
        r"\A(?:---\s*\n)?version:\s*['\"]?[0-9.]+['\"]?\s*\n\s*",
        "",
        compose_text,
    )
    # Repair tags produced by the legacy substring migration and keep this
    # migration idempotent on already-migrated checkouts.
    compose_text = re.sub(
        r"(jitsi/(?:web|prosody|jicofo|jvb)):stable(?:-10184)+",
        r"\1:stable-10184",
        compose_text,
    )
    compose_text = re.sub(
        r"louislam/uptime-kuma:1(?:\.23\.16)+",
        "louislam/uptime-kuma:1.23.16",
        compose_text,
    )
    compose_text = re.sub(
        r"^\s*container_name:\s*[^\n]+\n", "", compose_text, flags=re.MULTILINE
    )
    if "/opt/upcode-harbor/data" in compose_text:
        compose_text = compose_text.replace(
            "/opt/upcode-harbor/data",
            "${APP_DATA_DIR:?APP_DATA_DIR is required}",
        )
    compose = yaml.safe_load(compose_text)
    legacy_environment = _legacy_environment(manifest)
    for name in DROP_ENVIRONMENT.get(directory.name, set()):
        legacy_environment.pop(name, None)
    aliases = ALIASES.get(directory.name, {})
    for key, source in aliases.items():
        if key != source:
            legacy_environment.pop(key, None)
        legacy_environment.setdefault(source, {"default": "", "description": ""})
    for name in EXPLICIT_SECRETS.get(directory.name, set()):
        legacy_environment.setdefault(name, {"default": "", "description": ""})
    compose_values = _compose_environment(compose)
    for name, value in compose_values.items():
        if _secret(name) and name not in aliases and name not in legacy_environment:
            legacy_environment[name] = {"default": value, "description": ""}
    for match in re.finditer(
        r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}", compose_text
    ):
        name, default = match.group(1), match.group(2) or ""
        legacy_environment.setdefault(name, {"default": default, "description": ""})
    if "${APP_DATA_DIR" in compose_text:
        legacy_environment.setdefault(
            "APP_DATA_DIR",
            {
                "default": "",
                "description": "Managed per-installation data directory.",
                "required": True,
                "managed": True,
            },
        )

    environment = []
    for name, item in sorted(legacy_environment.items()):
        is_secret = (
            bool(item.get("secret"))
            or _secret(name)
            or name in EXPLICIT_SECRETS.get(directory.name, set())
        )
        default = str(item.get("default", ""))
        if is_secret:
            default = ""
        placeholder = any(
            marker in default.lower()
            for marker in ("your-", "example.com", "your server")
        )
        if placeholder:
            default = ""
        required = bool(item.get("required")) or is_secret or placeholder
        generate = (
            is_secret and name not in USER_SUPPLIED_SECRETS
            if name in EXPLICIT_SECRETS.get(directory.name, set())
            else (
                bool(item.get("generate"))
                if item.get("generate") is not None
                else is_secret and name not in USER_SUPPLIED_SECRETS
            )
        )
        environment.append({
            "name": name,
            "label": _label(name),
            "description": item.get("description", ""),
            "default": default,
            "required": required,
            "secret": is_secret,
            "generate": generate,
            **({"managed": True} if item.get("managed") else {}),
            **({"generator": item["generator"]} if item.get("generator") else {}),
            **(
                {"min_length": int(item.get("min_length") or 24)}
                if is_secret else {}
            ),
        })

    for key, source in aliases.items():
        compose_text = _replace_assignment(compose_text, key, source)
    for item in environment:
        compose_text = _replace_assignment(
            compose_text,
            item["name"],
            item["name"],
            required=item["required"],
            default=item["default"],
        )

    special_replacements = {
        "bookstack": {"-pchangeme": "-p$${DB_PASSWORD}"},
        "jupyter": {"'changeme'": "'$${JUPYTER_TOKEN}'"},
        "mailcow": {"changeme_redis_password": "$${REDISPASS}"},
        "domain-locker": {
            "postgresql://domainlocker:domainlocker@domain-locker-db/domainlocker":
                "postgresql://domainlocker:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@domain-locker-db/domainlocker"
        },
        "mattermost": {
            "postgres://mattermost:mattermost@mattermost-db/mattermost":
                "postgres://mattermost:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@mattermost-db/mattermost"
        },
        "neo4j": {
            "NEO4J_AUTH=${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}":
                "NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:?NEO4J_PASSWORD is required}"
        },
        "redis": {
            "command: redis-server --requirepass redispassword --appendonly yes":
                'command: ["redis-server", "--requirepass", "${REDIS_PASSWORD:?REDIS_PASSWORD is required}", "--appendonly", "yes"]'
        },
    }
    for old, new in special_replacements.get(directory.name, {}).items():
        compose_text = compose_text.replace(old, new)
    for old, new in IMAGE_PINS.items():
        compose_text = re.sub(
            rf"^(\s*image:\s*){re.escape(old)}\s*$",
            rf"\g<1>{new}",
            compose_text,
            flags=re.MULTILINE,
        )
    referenced = set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", compose_text))
    environment = [item for item in environment if item["name"] in referenced]

    migrated = {
        "schema_version": 1,
        "id": directory.name,
        "name": manifest["name"],
        "description": manifest["description"],
        "version": APP_VERSIONS.get(directory.name, manifest["version"]),
        "category": manifest["category"],
        "icon": manifest["icon"],
        "author": manifest["author"],
    }
    for key in ("website", "repository", "tags"):
        if key in manifest:
            migrated[key] = manifest[key]
    migrated["ports"] = [_port(value) for value in manifest["ports"]]
    migrated["volumes"] = [_volume(value) for value in manifest["volumes"]]
    migrated["environment"] = environment
    for key in ("requirements", "notes", "privileged", "network_mode"):
        if key in manifest:
            migrated[key] = manifest[key]
    migrated["update"] = manifest.get(
        "update", {"strategy": "compose-pull-recreate"}
    )
    manifest_path.write_text(json.dumps(migrated, indent=2, ensure_ascii=False) + "\n")
    compose_path.write_text(compose_text)


def main() -> int:
    for directory in sorted(path for path in TEMPLATES.iterdir() if path.is_dir()):
        migrate(directory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
