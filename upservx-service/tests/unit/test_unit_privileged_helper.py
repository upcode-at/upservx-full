"""Negative policy coverage for the root-owned privilege boundary."""

from __future__ import annotations

import io
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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


def test_pam_broker_passes_password_only_via_stdin(helper, monkeypatch):
    password = b"correct horse battery staple\n"
    stdin = io.TextIOWrapper(io.BytesIO(password), encoding="utf-8")
    monkeypatch.setattr(helper.sys, "stdin", stdin)
    completed = SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    with (
        patch.object(helper, "_absolute_command", return_value="/usr/bin/pamtester"),
        patch.object(helper.subprocess, "run", return_value=completed) as run,
    ):
        assert helper.authenticate_pam_user("alice") == 0

    command = run.call_args.args[0]
    assert command == [
        "/usr/bin/pamtester",
        "upservx",
        "alice",
        "authenticate",
        "acct_mgmt",
    ]
    assert password.decode().strip() not in command
    assert run.call_args.kwargs["input"] == password
    assert run.call_args.kwargs["capture_output"] is True


@pytest.mark.parametrize("password", [b"", b"unterminated", b"two\nlines\n", b"nul\x00byte\n"])
def test_pam_broker_rejects_malformed_password_input(helper, monkeypatch, password):
    stdin = io.TextIOWrapper(io.BytesIO(password), encoding="utf-8")
    monkeypatch.setattr(helper.sys, "stdin", stdin)
    with pytest.raises(helper.PolicyError, match="invalid PAM password input"):
        helper.authenticate_pam_user("alice")
