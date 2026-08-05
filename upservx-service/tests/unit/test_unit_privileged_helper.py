"""Negative policy coverage for the root-owned privilege boundary."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str):
    path = ROOT / "deploy" / name
    module_name = name.replace("-", "_")
    spec = importlib.util.spec_from_loader(
        module_name,
        SourceFileLoader(module_name, str(path)),
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def helper():
    return _load_script("upservx-privileged")


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("apt-get", ["install", "--only-upgrade", "-y", "--", "openssl"]),
        ("systemctl", ["restart", "nginx.service"]),
        ("nft", ["add", "table", "inet", "upservx_filter"]),
        ("fail2ban-client", ["set", "sshd", "unbanip", "192.0.2.10"]),
        ("useradd", ["-m", "-s", "/bin/bash", "alice"]),
    ],
)
def test_expected_host_operations_are_allowlisted(helper, command, arguments):
    helper._validate_exec(command, arguments)


@pytest.mark.parametrize(
    ("command", "arguments"),
    [
        ("apt-get", ["install", "--only-upgrade", "-y", "--", "openssl", "curl"]),
        ("systemctl", ["daemon-reload"]),
        ("systemctl", ["start", "../../evil.service"]),
        ("systemctl", ["start", "upservx-update@unsigned.service"]),
        ("nft", ["flush", "ruleset"]),
        ("ip", ["netns", "exec", "unsafe", "sh"]),
        ("mount", ["/dev/sdb1", "/etc"]),
        ("userdel", ["-r", "root"]),
        ("groupdel", ["docker"]),
        ("certbot", ["renew", "--deploy-hook", "sh -c id"]),
        ("bash", ["-c", "id"]),
    ],
)
def test_unsafe_or_out_of_scope_operations_are_denied(helper, command, arguments):
    with pytest.raises((helper.PolicyError, ValueError)):
        helper._validate_exec(command, arguments)


def test_update_versions_reject_unit_and_path_injection(helper):
    for value in ("../release", "release@evil", "release/name", "", "a" * 65):
        assert not helper.VERSION_RE.fullmatch(value)
