"""Signed-update selection, failure propagation, and archive safety tests."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_updater():
    path = ROOT / "deploy" / "upservx-updater"
    spec = importlib.util.spec_from_loader(
        "upservx_updater",
        SourceFileLoader("upservx_updater", str(path)),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_archive_paths_and_links_fail_closed(tmp_path):
    updater = _load_updater()
    with pytest.raises(updater.UpdateError):
        updater._safe_destination(tmp_path, "../../etc/shadow")
    with pytest.raises(updater.UpdateError):
        updater._safe_destination(tmp_path, "/etc/shadow")

    archive_path = tmp_path / "release.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        link = tarfile.TarInfo("release/escape")
        link.type = tarfile.SYMTYPE
        link.linkname = "/etc"
        archive.addfile(link)
    destination = tmp_path / "destination"
    destination.mkdir()
    with pytest.raises(updater.UpdateError, match="links and special files"):
        updater._extract_release(archive_path, destination)


def test_incomplete_signed_release_is_rejected(tmp_path):
    updater = _load_updater()
    (tmp_path / "upservx").mkdir()
    (tmp_path / "upservx" / "package-lock.json").write_text("{}")
    with pytest.raises(updater.UpdateError, match="complete UpservX release"):
        updater._find_release_root(tmp_path)


def test_release_manifest_must_match_requested_version(tmp_path):
    updater = _load_updater()
    required = (
        tmp_path / "upservx/package-lock.json",
        tmp_path / "upservx-service/requirements.lock",
        tmp_path / "upservx-service/main.py",
        tmp_path / "upservx/public/novnc/vnc.html",
    )
    for path in required:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("content")
    (tmp_path / ".upservx-release.json").write_text(
        json.dumps({"format": 1, "version": "1.0.0"})
    )
    with pytest.raises(updater.UpdateError, match="does not match"):
        updater._find_release_root(tmp_path, "2.0.0")


class _Context:
    checkpoint = {"stage": "external-update-started"}

    def check_cancelled(self):
        return None

    def progress(self, *_args, **_kwargs):
        return None


def test_nonzero_external_updater_result_fails_the_job(tmp_path, monkeypatch):
    from handlers import job_tasks

    version = "2.0.0"
    (tmp_path / f"{version}.json").write_text(
        json.dumps({"status": "failed", "exit_code": 23, "error": "health check failed"})
    )
    monkeypatch.setenv("UPSERVX_UPDATE_STATE_ROOT", str(tmp_path))
    with pytest.raises(RuntimeError, match="code 23.*health check failed"):
        job_tasks._system_update({"version": version}, _Context())


def test_failure_to_start_update_unit_fails_the_job(tmp_path, monkeypatch):
    from handlers import job_tasks

    monkeypatch.setenv("UPSERVX_UPDATE_STATE_ROOT", str(tmp_path))
    context = _Context()
    context.checkpoint = {}
    result = SimpleNamespace(returncode=5, stdout="", stderr="unit refused")
    with patch.object(job_tasks, "run_privileged", return_value=result):
        with pytest.raises(RuntimeError, match="unit refused"):
            job_tasks._system_update({"version": "2.0.1"}, context)
