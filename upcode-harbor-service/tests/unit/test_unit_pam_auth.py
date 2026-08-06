"""Tests for the unprivileged side of the root-owned PAM broker."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from lib import pam_auth


def test_authenticator_sends_password_only_as_helper_input():
    result = SimpleNamespace(returncode=0, stdout="", stderr="")
    authenticator = pam_auth.PrivilegedPamAuthenticator()

    with patch.object(pam_auth, "run_privileged", return_value=result) as run:
        assert authenticator.authenticate("alice", "secret", service="upcode-harbor")

    run.assert_called_once_with(
        "pam-authenticate",
        "alice",
        input_text="secret\n",
        timeout=25,
    )
    assert authenticator.code == 0
    assert authenticator.reason == "Success"


def test_authentication_rejection_uses_generic_pam_failure():
    result = SimpleNamespace(returncode=1, stdout="ignored", stderr="ignored")
    authenticator = pam_auth.PrivilegedPamAuthenticator()

    with patch.object(pam_auth, "run_privileged", return_value=result):
        assert not authenticator.authenticate("alice", "wrong", service="upcode-harbor")

    assert authenticator.code == 7
    assert authenticator.reason == "Authentication failure"


@pytest.mark.parametrize("password", ["line\nbreak", "carriage\rreturn", "nul\x00byte"])
def test_authenticator_rejects_unsafe_password_framing(password):
    authenticator = pam_auth.PrivilegedPamAuthenticator()
    with patch.object(pam_auth, "run_privileged") as run:
        assert not authenticator.authenticate("alice", password, service="upcode-harbor")
    run.assert_not_called()


def test_authenticator_handles_broker_timeout():
    authenticator = pam_auth.PrivilegedPamAuthenticator()
    with patch.object(
        pam_auth,
        "run_privileged",
        side_effect=subprocess.TimeoutExpired("pam-authenticate", 25),
    ):
        assert not authenticator.authenticate("alice", "secret", service="upcode-harbor")
    assert authenticator.reason == "PAM broker timed out"
