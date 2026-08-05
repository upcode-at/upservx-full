"""Static regression tests for the supported installation contract."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_installer_is_profile_based_and_does_not_edit_pam_or_pull_git():
    installer = (ROOT / "install.sh").read_text()
    assert "pam_lastlog" not in installer
    assert "git pull" not in installer
    assert "--profile containers" in installer
    assert "--with-postgresql" in installer
    assert "npm ci" in installer
    assert "requirements.lock" in installer
    assert "NODESOURCE_KEY_SHA256" in installer
    assert "K3S_INSTALL_SHA256" in installer
    assert "DOCKER_GPG_SHA256" in installer


def test_frontend_api_worker_and_update_have_separate_units():
    units = ROOT / "deploy" / "systemd"
    api = (units / "upservx-api.service").read_text()
    web = (units / "upservx-web.service").read_text()
    worker = (units / "upservx-worker.service").read_text()
    updater = (units / "upservx-update@.service").read_text()
    assert "User=upservx\n" in api
    assert "User=upservx-web\n" in web
    assert "User=upservx\n" in worker
    assert "User=root\n" in updater
    assert "upservx-updater apply %i" in updater
    assert "upservx-health-check wait-api" in api
    assert "upservx-health-check wait-web" in web


def test_python_lock_files_pin_every_distribution_exactly():
    for relative in ("upservx-service/requirements.lock", "upservx-cli/requirements.lock"):
        lines = [
            line.strip() for line in (ROOT / relative).read_text().splitlines()
            if line.strip() and not line.startswith("#")
        ]
        assert lines
        assert all(re.fullmatch(r"[A-Za-z0-9_.-]+==[^=\s]+", line) for line in lines)
        names = [line.split("==", 1)[0].lower() for line in lines]
        assert len(names) == len(set(names))


def test_novnc_gitlink_has_an_explicit_official_mapping():
    mapping = (ROOT / ".gitmodules").read_text()
    assert "path = upservx/public/novnc" in mapping
    assert "url = https://github.com/novnc/noVNC.git" in mapping
    assert (ROOT / "upservx/public/novnc/vnc.html").is_file()
