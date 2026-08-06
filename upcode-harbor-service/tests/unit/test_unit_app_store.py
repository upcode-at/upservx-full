"""App Store schema and transactional lifecycle regression tests."""

from __future__ import annotations

import importlib.util
import json
import shutil
import stat
import subprocess
from pathlib import Path

from dotenv import dotenv_values

from handlers import app_store as app_store_module
from lib.app_store_validation import validate_template


ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "app-store-templates"


def _store(tmp_path: Path, monkeypatch, template_ids=("adminer",)):
    from handlers import compose_manager as compose_manager_module

    template_root = tmp_path / "templates"
    compose_root = tmp_path / "compose"
    data_root = tmp_path / "data"
    template_root.mkdir()
    shutil.copy2(TEMPLATES / "app.schema.json", template_root / "app.schema.json")
    for template_id in template_ids:
        shutil.copytree(TEMPLATES / template_id, template_root / template_id)

    monkeypatch.setattr(app_store_module, "APP_STORE_DIR", str(template_root))
    monkeypatch.setattr(app_store_module, "COMPOSE_BASE_DIR", str(compose_root))
    monkeypatch.setattr(app_store_module, "APP_DATA_BASE_DIR", str(data_root))
    monkeypatch.setattr(
        compose_manager_module, "COMPOSE_BASE_DIR", str(compose_root)
    )
    monkeypatch.setattr(
        app_store_module, "APP_SCHEMA_PATH", str(template_root / "app.schema.json")
    )
    return app_store_module.AppStore(), compose_root, data_root


def _completed(command, returncode=0, stderr=""):
    return subprocess.CompletedProcess(command, returncode, "", stderr)


def test_every_template_satisfies_schema_and_structural_compose_contract():
    schema = TEMPLATES / "app.schema.json"
    directories = sorted(path for path in TEMPLATES.iterdir() if path.is_dir())

    assert len(directories) == 62
    for directory in directories:
        validate_template(directory, schema)


def test_migration_is_idempotent_for_previously_corrupted_tags(tmp_path):
    migration_path = ROOT / "tools" / "migrate_app_store_v1.py"
    spec = importlib.util.spec_from_file_location("app_store_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    copied = tmp_path / "jitsi"
    shutil.copytree(TEMPLATES / "jitsi", copied)

    migration.migrate(copied)
    first = (copied / "docker-compose.yml").read_bytes()
    migration.migrate(copied)

    assert (copied / "docker-compose.yml").read_bytes() == first
    assert first.count(b"-10184") == 4


def test_install_validates_pulls_waits_and_tracks_custom_project(
    tmp_path, monkeypatch
):
    from handlers.compose_manager import compose_manager

    store, compose_root, _data_root = _store(tmp_path, monkeypatch)
    calls = []

    def run(command, project_dir, timeout=0):
        calls.append(command)
        return _completed(command)

    monkeypatch.setattr(store, "_run", run)
    result = store.install_app(
        "adminer",
        "Customer Adminer",
        {"ADMINER_DEFAULT_SERVER": "database"},
    )

    assert result["success"] is True
    assert result["project_name"] == "customer-adminer"
    project = compose_root / "customer-adminer"
    assert project.is_dir()
    assert stat.S_IMODE((project / ".env").stat().st_mode) == 0o600
    assert dotenv_values(project / ".env")["ADMINER_DEFAULT_SERVER"] == "database"
    metadata = json.loads((project / ".upcode-harbor-installation.json").read_text())
    assert metadata["template_id"] == "adminer"
    assert metadata["project_name"] == "customer-adminer"
    assert calls[0][-2:] == ["config", "--quiet"]
    assert calls[1][-1:] == ["pull"]
    assert calls[2][-5:] == [
        "up", "-d", "--wait", "--wait-timeout", "900"
    ]
    monkeypatch.setattr(
        compose_manager, "_get_project_status", lambda name, directory: "running"
    )
    listed = store.list_apps()[0]
    assert listed["installed"] is True
    assert listed["installations"][0]["project_name"] == "customer-adminer"
    assert listed["installations"][0]["status"] == "running"


def test_install_generates_secret_without_returning_it(tmp_path, monkeypatch):
    store, compose_root, _data_root = _store(
        tmp_path, monkeypatch, ("apache-kafka",)
    )
    monkeypatch.setattr(
        store, "_run", lambda command, project_dir, timeout=0: _completed(command)
    )

    result = store.install_app("apache-kafka")

    assert result["success"] is True
    generated = dotenv_values(compose_root / "apache-kafka" / ".env")
    assert len(generated["KAFKA_CLUSTER_ID"]) >= 22
    assert "KAFKA_CLUSTER_ID" not in json.dumps(result)
    assert str(tmp_path / "data" / "apache-kafka") == generated["APP_DATA_DIR"]


def test_failed_start_rolls_back_project_and_bind_data(tmp_path, monkeypatch):
    store, compose_root, data_root = _store(tmp_path, monkeypatch)

    def run(command, project_dir, timeout=0):
        if "up" in command:
            (data_root / "adminer").mkdir(parents=True)
            return _completed(command, returncode=1, stderr="health check failed")
        return _completed(command)

    monkeypatch.setattr(store, "_run", run)
    result = store.install_app("adminer")

    assert result["success"] is False
    assert "health check failed" in result["message"]
    assert not (compose_root / "adminer").exists()
    assert not (data_root / "adminer").exists()


def test_update_preserves_managed_values_and_generates_new_secret(
    tmp_path, monkeypatch
):
    store, compose_root, _data_root = _store(
        tmp_path, monkeypatch, ("apache-kafka",)
    )
    monkeypatch.setattr(
        store, "_run", lambda command, project_dir, timeout=0: _completed(command)
    )
    assert store.install_app("apache-kafka")["success"] is True
    env_path = compose_root / "apache-kafka" / ".env"
    before = dotenv_values(env_path)

    result = store.update_app("apache-kafka")

    assert result["success"] is True
    after = dotenv_values(env_path)
    assert after["APP_DATA_DIR"] == before["APP_DATA_DIR"]
    assert after["KAFKA_CLUSTER_ID"] == before["KAFKA_CLUSTER_ID"]


def test_failed_update_restores_previous_template(tmp_path, monkeypatch):
    store, compose_root, _data_root = _store(tmp_path, monkeypatch)
    failing = False

    def run(command, project_dir, timeout=0):
        if failing and command[-1] == "pull":
            return _completed(command, returncode=1, stderr="pull failed")
        return _completed(command)

    monkeypatch.setattr(store, "_run", run)
    assert store.install_app("adminer")["success"] is True
    installed_compose = compose_root / "adminer" / "docker-compose.yml"
    previous = installed_compose.read_bytes()
    template_compose = tmp_path / "templates" / "adminer" / "docker-compose.yml"
    template_compose.write_text(template_compose.read_text() + "\n# update candidate\n")
    failing = True

    result = store.update_app("adminer")

    assert result["success"] is False
    assert "Update rolled back" in result["message"]
    assert installed_compose.read_bytes() == previous


def test_install_rejects_unknown_and_managed_environment_values(
    tmp_path, monkeypatch
):
    store, _compose_root, _data_root = _store(
        tmp_path, monkeypatch, ("apache-kafka",)
    )

    unknown = store.install_app("apache-kafka", environment={"UNKNOWN": "value"})
    managed = store.install_app(
        "apache-kafka", environment={"APP_DATA_DIR": "/tmp/not-allowed"}
    )

    assert unknown["success"] is False
    assert "Unknown environment variables" in unknown["message"]
    assert managed["success"] is False
    assert "Managed environment variables" in managed["message"]


def test_uninstall_removes_managed_bind_data(tmp_path, monkeypatch):
    from handlers.compose_manager import compose_manager

    store, _compose_root, data_root = _store(tmp_path, monkeypatch)
    application_data = data_root / "customer-adminer"
    application_data.mkdir(parents=True)
    (application_data / "state.db").write_text("state")
    monkeypatch.setattr(
        compose_manager,
        "delete_project",
        lambda project_name, remove_volumes: {
            "success": True,
            "message": "Project deleted",
        },
    )

    result = store.uninstall_app("Customer Adminer")

    assert result["success"] is True
    assert result["data_removed"] is True
    assert not application_data.exists()
