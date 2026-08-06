"""Static regression tests for the supported installation contract."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_installer_is_profile_based_and_does_not_patch_distribution_pam_or_pull_git():
    installer = (ROOT / "install.sh").read_text()
    assert "pam_lastlog" not in installer
    assert "git pull" not in installer
    assert "--profile containers" in installer
    assert "--with-postgresql" in installer
    assert "npm ci" in installer
    assert "requirements.lock" in installer
    assert "libpam-modules libpam-modules-bin libpam-runtime pamtester" in installer
    assert "NODESOURCE_KEY_SHA256" in installer
    assert "K3S_INSTALL_SHA256" in installer
    assert "DOCKER_GPG_SHA256" in installer


def test_linux_login_uses_a_dedicated_managed_pam_service():
    installer = (ROOT / "install.sh").read_text()
    auth = (ROOT / "upservx-service/api/auth.py").read_text()
    pam_client = (ROOT / "upservx-service/lib/pam_auth.py").read_text()
    privileged = (ROOT / "deploy/upservx-privileged").read_text()
    updater = (ROOT / "deploy/upservx-updater").read_text()
    pam_policy = (ROOT / "deploy/pam/upservx").read_text()

    assert (
        'install -o root -g root -m 0644 '
        '"$RELEASE_DIR/deploy/pam/upservx" /etc/pam.d/upservx'
    ) in installer
    assert "/etc/pam.d/upservx" in updater
    assert "from lib.pam_auth import PAM_SERVICE" in auth
    assert 'PAM_SERVICE = "upservx"' in pam_client
    assert "service=PAM_SERVICE" in auth
    assert 'run_privileged(\n                "pam-authenticate"' in pam_client
    assert '"authenticate",\n                "acct_mgmt",' in privileged
    assert "input=password_input" in privileged
    assert "@include common-auth" in pam_policy
    assert "@include common-account" in pam_policy


def test_installer_defaults_to_keyless_installation():
    installer = (ROOT / "install.sh").read_text()
    assert "UPDATES_ENABLED=0" in installer
    assert "UPDATE_PUBLIC_KEY=$2; UPDATES_ENABLED=1" in installer
    assert 'verify_optional_sha256 "${NODESOURCE_KEY_SHA256:-}"' in installer
    assert 'verify_optional_sha256 "${DOCKER_GPG_SHA256:-}"' in installer
    assert 'verify_optional_sha256 "${K3S_INSTALL_SHA256:-}"' in installer
    assert "if [[ -n ${KUBECTL_VERSION:-} ]]" in installer
    assert 'command -v kubectl' in installer


def test_installer_defaults_to_all_supported_platform_components():
    installer = (ROOT / "install.sh").read_text()
    smoke = (ROOT / "deploy/upservx-post-install-smoke").read_text()

    assert "INSTALL_SELECTION_MADE=0" in installer
    assert "if [[ $INSTALL_SELECTION_MADE == 0 ]]; then\n  enable_profile full" in installer
    assert "openssh-client openssh-server" in installer
    assert "systemctl enable --now ssh.service" in installer
    assert "upservx-zfs.sources" in installer
    assert "Components: contrib" in installer
    assert "Docker service is active" in smoke
    assert "LXC client is installed" in smoke
    assert "K3s service is active" in smoke
    assert "ZFS CLI is installed" in smoke


def test_iso_listing_does_not_try_to_create_a_privileged_host_directory():
    handler = (ROOT / "upservx-service/handlers/isos.py").read_text()
    assert 'ISO_DIR = os.getenv("UPSERVX_ISO_DIR", "/var/lib/libvirt/isos")' in handler
    assert "os.makedirs(iso_dir" not in handler
    assert "if not os.path.isdir(iso_dir):\n        return files" in handler


def test_installer_can_import_encryption_module_when_initializing_secrets():
    installer = (ROOT / "install.sh").read_text()
    assert 'PYTHONPATH="$RELEASE_DIR/upservx-service"' in installer
    assert "from lib.encryption import EncryptionManager" in installer
    assert "from lib.session_tokens import _get_secret" in installer
    assert "from lib.cluster_security import ensure_node_tls" in installer
    assert "EncryptionManager.ensure_key_exists(); _get_secret(); ensure_node_tls()" in installer


def test_installer_can_safely_resume_after_release_creation():
    installer = (ROOT / "install.sh").read_text()
    assert "--resume) RESUME_INSTALLATION=1" in installer
    assert "load_recorded_profile" in installer
    assert "stat -c '%U:%a'" in installer
    assert '[[ -L $APP_ROOT/current ]]' in installer
    assert 'RELEASE_DIR=$(readlink -f "$APP_ROOT/current")' in installer
    assert '[[ ${RELEASE_DIR%/*} == "$APP_ROOT/releases"' in installer
    assert "TOTAL_STEPS=7" in installer
    assert "run_step 'Configure mutable state and update trust'" in installer
    assert "run_step 'Configure the local HTTPS reverse proxy'" in installer
    assert "run_step 'Generate application, session, and cluster keys'" in installer
    assert "Installation resumed successfully" in installer


def test_installer_can_recoverably_reinstall_a_broken_installation():
    installer = (ROOT / "install.sh").read_text()
    assert "--reinstall) REINSTALL=1" in installer
    assert "--resume and --reinstall cannot be used together" in installer
    assert 'REINSTALL_BACKUP_DIR="/var/backups/upservx/$backup_id"' in installer
    assert '"$APP_ROOT"\n    /etc/upservx\n    /var/lib/upservx' in installer
    assert "/usr/local/libexec/upservx-bin" in installer
    assert "/etc/systemd/system/upservx.target" in installer
    assert 'mv -- "$source" "$REINSTALL_BACKUP_DIR/${labels[$index]}"' in installer
    assert installer.index(
        "run_step 'Validate locked source and noVNC submodule'"
    ) < installer.index("if [[ $REINSTALL == 1 ]]; then\n  backup_broken_installation")
    assert "Previous installation backup" in installer


def test_installer_does_not_create_application_login_users():
    installer = (ROOT / "install.sh").read_text()
    assert "upservx-admin" not in installer
    assert "--reset-admin" not in installer
    assert "INITIAL_ADMIN_PASSWORD" not in installer
    assert "Login with an existing Linux/PAM" in installer
    assert "TOTAL_STEPS=14" in installer


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


def test_public_access_uses_nginx_https_instead_of_internal_ports():
    installer = (ROOT / "install.sh").read_text()
    web = (ROOT / "deploy/systemd/upservx-web.service").read_text()
    nginx = (ROOT / "deploy/nginx/upservx.conf").read_text()
    assert "--hostname 127.0.0.1" in web
    assert "listen 443 ssl default_server" in nginx
    assert "proxy_pass http://127.0.0.1:9200" in nginx
    assert "Open UpservX: https://%s/" in installer
    assert "remote access uses nginx on HTTPS port 443" in installer


def test_python_lock_files_pin_every_distribution_exactly():
    for relative in (
        "upservx-service/requirements.lock",
        "upservx-cli/requirements.lock",
        "requirements-quality.lock",
    ):
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
