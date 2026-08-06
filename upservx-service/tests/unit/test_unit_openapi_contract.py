"""Contract checks shared by backend routes and generated clients."""

import importlib.util
from pathlib import Path


def test_openapi_contains_frontend_and_cli_routes(app):
    paths = app.openapi()["paths"]
    expected = {
        "/backup/servers/{server_id}/info": {"get"},
        "/backup/instances/{instance_id}/restore": {"post"},
        "/backup/instances/{instance_id}/verify": {"post"},
        "/ssh-keys": {"get"},
        "/ssh-keys/generate": {"post"},
        "/ssh-keys/import": {"post"},
        "/ssh-keys/{key_name}": {"get", "delete"},
        "/ssh-keys/{key_name}/test": {"post"},
        "/containers/{name}": {"get"},
        "/containers/{name}/restart": {"post"},
        "/containers/app-store/apps/{app_id}/install": {"post"},
        "/containers/app-store/apps/{project_name}/update": {"post"},
        "/proxy/configs/{domain}/advanced": {"get", "put"},
    }
    for path, methods in expected.items():
        assert path in paths
        assert methods <= set(paths[path])


def test_generated_clients_do_not_put_secrets_in_query_strings():
    root = Path(__file__).resolve().parents[3]
    client = (root / "upservx" / "lib" / "api.ts").read_text()
    assert "/ssh-keys/generate?" not in client
    assert "/ssh-keys/import?" not in client
    assert "/test?" not in client
    assert "generated-api-types" in client


def test_cli_backup_payload_uses_generated_contract_type():
    root = Path(__file__).resolve().parents[3]
    command = (root / "upservx-cli" / "cli" / "commands" / "backup.py").read_text()
    assert "payload: BackupJobCreate" in command
    for field in ("name", "backup_type", "targets", "schedule", "server_id"):
        assert f'"{field}"' in command


def test_generated_request_types_match_openapi(app):
    root = Path(__file__).resolve().parents[3]
    generator_path = root / "tools" / "generate_api_contract.py"
    spec = importlib.util.spec_from_file_location("generate_api_contract", generator_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    typescript, python = module._render_types(app.openapi())
    assert (root / "upservx" / "lib" / "generated-api-types.ts").read_text() == typescript
    assert (root / "upservx-cli" / "cli" / "generated_api_types.py").read_text() == python


def test_incomplete_cluster_sync_is_not_exposed_as_working():
    root = Path(__file__).resolve().parents[3]
    sync_manager = (root / "upservx-service" / "lib" / "container_sync.py").read_text()
    workload_ui = (root / "upservx" / "components" / "workload-distribution.tsx").read_text()
    assert "/containers/deploy" not in sync_manager
    assert "/cluster/sync/execute" not in workload_ui
    assert "/cluster/sync/migrate" not in workload_ui
