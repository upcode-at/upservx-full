"""Long-running API routes must enqueue work instead of executing it inline."""

from __future__ import annotations

from unittest.mock import patch

import pytest


PERSISTENT_JOB = {"id": "persistent-id", "status": "queued"}


@pytest.mark.asyncio
async def test_standalone_node_has_no_replications_instead_of_forbidden_response():
    from api import cluster

    with (
        patch.object(cluster, "is_master_node", return_value=False),
        patch.object(cluster, "is_child_node", return_value=False),
    ):
        assert await cluster.get_replications() == []


@pytest.mark.asyncio
async def test_package_scan_and_upgrade_routes_enqueue_jobs():
    from api import security

    with patch.object(security, "enqueue_job", return_value=PERSISTENT_JOB) as enqueue:
        scan = await security.list_upgradeable_packages()
        upgrade = await security.upgrade_single_package("openssl")

    assert scan["persistent_job"] == PERSISTENT_JOB
    assert upgrade["persistent_job"] == PERSISTENT_JOB
    assert enqueue.call_args_list[0].args[0] == "package_scan"
    assert enqueue.call_args_list[1].args[:2] == (
        "package_upgrade",
        {"package_name": "openssl"},
    )


@pytest.mark.asyncio
async def test_system_update_route_only_enqueues(tmp_path, monkeypatch):
    from api import settings

    version = "1.2.3"
    update_dir = tmp_path / version
    update_dir.mkdir()
    for suffix in ("tar.gz", "sha256", "sig"):
        (update_dir / f"upcode-harbor-{version}.{suffix}").write_text("staged")
    monkeypatch.setattr(settings, "UPDATE_ROOT", tmp_path)
    with patch.object(settings, "enqueue_job", return_value=PERSISTENT_JOB) as enqueue:
        response = await settings.run_update(settings.UpdateRequest(version=version))

    assert response["persistent_job"] == PERSISTENT_JOB
    assert enqueue.call_args.args[0] == "system_update"
    assert enqueue.call_args.args[1] == {"version": version}


def test_vm_export_route_only_enqueues():
    from api import vms

    with patch.object(vms, "enqueue_job", return_value=PERSISTENT_JOB) as enqueue:
        response = vms.export_vm_endpoint("demo", {"format": "ova"})

    assert response["persistent_job"] == PERSISTENT_JOB
    assert enqueue.call_args.args == (
        "vm_export",
        {"name": "demo", "format": "ova"},
    )


@pytest.mark.asyncio
async def test_replication_trigger_route_only_enqueues():
    from api import cluster

    replication = {
        "id": "rule-1",
        "name": "demo",
        "origin_node": "node-a",
        "destination_node": "node-b",
    }
    with (
        patch.object(cluster, "is_master_node", return_value=True),
        patch.object(cluster, "read_replications", return_value=[replication]),
        patch.object(cluster, "enqueue_job", return_value=PERSISTENT_JOB) as enqueue,
    ):
        response = await cluster.trigger_replication("rule-1")

    assert response["persistent_job"] == PERSISTENT_JOB
    assert enqueue.call_args.args == (
        "replication",
        {"replication_id": "rule-1"},
    )
