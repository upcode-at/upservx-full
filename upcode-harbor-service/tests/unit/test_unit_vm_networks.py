"""Unit tests for optional libvirt network discovery."""

from subprocess import CompletedProcess
from unittest.mock import patch

from handlers import vm_networks


def test_list_returns_empty_when_libvirt_is_not_installed():
    with patch("handlers.vm_networks.shutil.which", return_value=None):
        assert vm_networks.list_vm_networks() == []


def test_list_returns_empty_when_libvirt_daemon_is_unavailable():
    unavailable = CompletedProcess(
        args=["virsh", "net-list", "--all"],
        returncode=1,
        stdout="",
        stderr="failed to connect to the hypervisor",
    )
    with (
        patch("handlers.vm_networks.shutil.which", return_value="/usr/bin/virsh"),
        patch("handlers.vm_networks.subprocess.run", return_value=unavailable),
        patch("handlers.vm_networks.log_vm") as log_vm,
    ):
        assert vm_networks.list_vm_networks() == []

    log_vm.assert_called_once_with(
        "VM network listing unavailable: failed to connect to the hypervisor",
        error=True,
    )
