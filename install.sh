#!/usr/bin/env bash
# Reproducible, profile-based UpservX installer.
set -euo pipefail

APP_ROOT=/opt/upservx
SERVICE_USER=upservx
WEB_USER=upservx-web
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
NODE_REQUIRED_MAJOR=20
LOG_FILE=/tmp/upservx-install.log
LAST_STEP_LOG=/tmp/upservx-install-last.log

WITH_DOCKER=0
WITH_LXD=0
WITH_LIBVIRT=0
WITH_K3S=0
WITH_POSTGRESQL=0
WITH_FTP=0
WITH_OPENVPN=0
WITH_ZFS=0
UPDATES_ENABLED=0
UPDATE_PUBLIC_KEY=
RELEASE_VERSION=
RESUME_INSTALLATION=0
REINSTALL=0
REINSTALL_BACKUP_DIR=

CORE_PACKAGES=(
  build-essential gcc g++ make python3 python3-pip python3-venv python3-dev
  libpq-dev libpam0g-dev nginx certbot python3-certbot python3-certbot-nginx
  git lshw openssl gawk coreutils curl jq ca-certificates gnupg sudo
  nftables fail2ban cron openssh-client iproute2 isc-dhcp-client util-linux
  e2fsprogs xfsprogs btrfs-progs dosfstools exfatprogs ntfs-3g parted
)

usage() {
  cat <<'EOF'
Usage: sudo ./install.sh [OPTIONS]

The default core profile installs only the API, frontend, worker, nginx,
fail2ban, and their build/runtime dependencies.

Profiles:
  --profile core             No optional platform components (default)
  --profile containers       Docker and LXD
  --profile virtualization   libvirt/KVM and websockify
  --profile cluster          Docker and K3s/kubectl
  --profile full             All optional profiles

Individual options:
  --with-docker --with-lxd --with-libvirt --with-k3s
  --with-postgresql --with-ftp --with-openvpn --with-zfs
  --update-public-key PATH   Enable signed updates with this public key
  --disable-updates          Install without the update facility (default)
  --resume                   Rebuild configuration and finish an interrupted install
  --reinstall                Back up a broken installation and install from scratch
  --release-version VERSION  Override the local initial release version
  -h, --help

No keys or checksum variables are required for installation. Official HTTPS
repositories and their package signatures are used by default. For additional
pinning, set NODESOURCE_KEY_SHA256, DOCKER_GPG_SHA256, K3S_INSTALL_SHA256,
and/or KUBECTL_SHA256. Set KUBECTL_VERSION only to override the version that
K3s installs automatically.
EOF
}

enable_profile() {
  case "$1" in
    core) ;;
    containers) WITH_DOCKER=1; WITH_LXD=1 ;;
    virtualization) WITH_LIBVIRT=1 ;;
    cluster) WITH_DOCKER=1; WITH_K3S=1 ;;
    full)
      WITH_DOCKER=1; WITH_LXD=1; WITH_LIBVIRT=1; WITH_K3S=1
      WITH_POSTGRESQL=1; WITH_FTP=1; WITH_OPENVPN=1; WITH_ZFS=1
      ;;
    *) printf 'Unknown profile: %s\n' "$1" >&2; exit 2 ;;
  esac
}

primary_server_ip() {
  local address
  address=$(ip -4 route get 1.1.1.1 2>/dev/null \
    | awk '{for (index = 1; index <= NF; index++) if ($index == "src") {print $(index + 1); exit}}' \
    || true)
  if [[ $address =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ && $address != 127.* ]]; then
    printf '%s\n' "$address"
    return
  fi
  hostname -I 2>/dev/null \
    | awk '{for (index = 1; index <= NF; index++) if ($index ~ /^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$/ && $index !~ /^127\./) {print $index; exit}}' \
    || true
}

print_access_information() {
  local server_ip server_name
  server_ip=$(primary_server_ip)
  if [[ -n $server_ip ]]; then
    printf 'Open UpservX: https://%s/\n' "$server_ip"
  else
    server_name=$(hostname -f 2>/dev/null || hostname)
    printf 'Open UpservX: https://%s/\n' "$server_name"
  fi
  printf 'Ports 9200 and 9500 are internal loopback services; remote access uses nginx on HTTPS port 443.\n'
  printf 'The browser may require confirmation of the automatically generated certificate.\n'
  if [[ -n ${SUDO_USER:-} && $SUDO_USER != root ]]; then
    printf 'Login with an existing Linux/PAM account, for example: %s\n' "$SUDO_USER"
  else
    printf 'Login with an existing Linux/PAM username and password.\n'
  fi
}

backup_broken_installation() {
  [[ $SCRIPT_DIR != "$APP_ROOT" && $SCRIPT_DIR != "$APP_ROOT"/* ]] || {
    printf 'Run --reinstall from a separate source checkout, not from %s.\n' "$APP_ROOT" >&2
    return 1
  }
  [[ ! -L /var/backups/upservx ]] || {
    printf 'Refusing to use a symlinked reinstall backup root.\n' >&2
    return 1
  }

  local backup_id
  backup_id="reinstall-$(date -u +%Y%m%dT%H%M%SZ)-$$"
  REINSTALL_BACKUP_DIR="/var/backups/upservx/$backup_id"
  install -d -o root -g root -m 0700 /var/backups/upservx "$REINSTALL_BACKUP_DIR"

  if command -v systemctl >/dev/null 2>&1; then
    systemctl disable --now upservx.target upservx-health.timer >/dev/null 2>&1 || true
    systemctl stop upservx-api.service upservx-web.service upservx-worker.service >/dev/null 2>&1 || true
  fi

  local -a sources=(
    "$APP_ROOT"
    /etc/upservx
    /var/lib/upservx
    /var/lib/upservx-web
    /var/log/upservx
    /usr/share/upservx
    /usr/local/libexec/upservx-bin
    /usr/local/libexec/upservx-privileged
    /usr/local/libexec/upservx-command
    /usr/local/libexec/upservx-updater
    /usr/local/libexec/upservx-health-check
    /usr/local/libexec/upservx-post-install-smoke
    /usr/local/bin/upservx
    /etc/sudoers.d/upservx
    /etc/tmpfiles.d/upservx.conf
    /etc/nginx/sites-enabled/upservx
    /etc/nginx/sites-available/upservx
    /etc/systemd/system/upservx-api.service
    /etc/systemd/system/upservx-health-recover.service
    /etc/systemd/system/upservx-health.service
    /etc/systemd/system/upservx-health.timer
    /etc/systemd/system/upservx-update@.service
    /etc/systemd/system/upservx-web.service
    /etc/systemd/system/upservx-worker.service
    /etc/systemd/system/upservx.target
  )
  local -a labels=(
    app-root config state web-state logs update-trust command-links
    privileged-helper command-helper updater health-check post-install-smoke
    cli-launcher sudoers tmpfiles nginx-enabled nginx-available
    systemd-api systemd-health-recover systemd-health systemd-health-timer
    systemd-update systemd-web systemd-worker systemd-target
  )
  local backed_up=0 index source
  for index in "${!sources[@]}"; do
    source=${sources[$index]}
    if [[ -e $source || -L $source ]]; then
      mv -- "$source" "$REINSTALL_BACKUP_DIR/${labels[$index]}"
      backed_up=1
    fi
  done

  [[ $backed_up == 1 ]] || {
    printf 'No existing UpservX installation was found to reinstall.\n' >&2
    return 1
  }
  printf 'Existing UpservX installation backed up to: %s\n' "$REINSTALL_BACKUP_DIR"
}

while (($#)); do
  case "$1" in
    --profile) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; enable_profile "$2"; shift 2 ;;
    --with-docker) WITH_DOCKER=1; shift ;;
    --with-lxd) WITH_LXD=1; shift ;;
    --with-libvirt) WITH_LIBVIRT=1; shift ;;
    --with-k3s) WITH_K3S=1; shift ;;
    --with-postgresql) WITH_POSTGRESQL=1; shift ;;
    --with-ftp) WITH_FTP=1; shift ;;
    --with-openvpn) WITH_OPENVPN=1; shift ;;
    --with-zfs) WITH_ZFS=1; shift ;;
    --update-public-key) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; UPDATE_PUBLIC_KEY=$2; UPDATES_ENABLED=1; shift 2 ;;
    --disable-updates) UPDATES_ENABLED=0; shift ;;
    --resume) RESUME_INSTALLATION=1; shift ;;
    --reinstall) REINSTALL=1; shift ;;
    --release-version) [[ $# -ge 2 ]] || { usage >&2; exit 2; }; RELEASE_VERSION=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) printf 'Unknown installer option: %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  printf 'This installer must run as root. Use sudo ./install.sh.\n' >&2
  exit 1
fi
if [[ $RESUME_INSTALLATION == 1 && $REINSTALL == 1 ]]; then
  printf '%s\n' '--resume and --reinstall cannot be used together.' >&2
  exit 2
fi
if [[ $UPDATES_ENABLED == 1 ]]; then
  [[ -n $UPDATE_PUBLIC_KEY && -f $UPDATE_PUBLIC_KEY ]] || {
    printf '%s\n' '--update-public-key must reference a readable public-key file.' >&2
    exit 2
  }
fi
if [[ -z $RELEASE_VERSION ]]; then
  base_version=$(sed -n 's/^[[:space:]]*"version":[[:space:]]*"\([^"]*\)".*/\1/p' "$SCRIPT_DIR/upservx/package.json" | head -n 1)
  [[ -n $base_version ]] || base_version=0.0.0
  RELEASE_VERSION="${base_version}-local-$(date -u +%Y%m%d%H%M%S)"
fi
[[ $RELEASE_VERSION =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
  printf 'Invalid release version: %s\n' "$RELEASE_VERSION" >&2
  exit 2
}

RELEASE_DIR="$APP_ROOT/releases/$RELEASE_VERSION"
RELEASE_STAGING="$APP_ROOT/releases/.${RELEASE_VERSION}.$$"
if [[ $RESUME_INSTALLATION == 1 ]]; then
  [[ -L $APP_ROOT/current ]] || {
    printf 'No interrupted UpservX installation is available to resume.\n' >&2
    exit 1
  }
  RELEASE_DIR=$(readlink -f "$APP_ROOT/current")
  [[ ${RELEASE_DIR%/*} == "$APP_ROOT/releases" && -d $RELEASE_DIR ]] || {
    printf 'The current UpservX release link is invalid; refusing to resume.\n' >&2
    exit 1
  }
  RELEASE_VERSION=${RELEASE_DIR##*/}
  [[ $RELEASE_VERSION =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]] || {
    printf 'The current UpservX release version is invalid; refusing to resume.\n' >&2
    exit 1
  }
  [[ -x $RELEASE_DIR/upservx-service/venv/bin/python3 ]] || {
    printf 'The current UpservX backend environment is incomplete; refusing to resume.\n' >&2
    exit 1
  }
  RELEASE_STAGING=
elif [[ $REINSTALL == 0 && ( -e $APP_ROOT/current || -L $APP_ROOT/current ) ]]; then
  printf 'An UpservX installation already exists. Use the signed updater, or --resume if installation stopped after release creation.\n' >&2
  exit 1
elif [[ $REINSTALL == 0 && ( -e $RELEASE_DIR || -e $RELEASE_STAGING ) ]]; then
  printf 'Release already exists: %s\n' "$RELEASE_DIR" >&2
  exit 1
fi

CURRENT_STEP=0
TOTAL_STEPS=14
cleanup() {
  if [[ -n ${RELEASE_STAGING:-} && $RELEASE_STAGING == /opt/upservx/releases/.* && -d $RELEASE_STAGING ]]; then
    rm -rf -- "$RELEASE_STAGING"
  fi
}
trap cleanup EXIT

run_step() {
  local title=$1
  local function_name=$2
  CURRENT_STEP=$((CURRENT_STEP + 1))
  printf '[%02d/%02d] %s\n' "$CURRENT_STEP" "$TOTAL_STEPS" "$title"
  if "$function_name" >>"$LOG_FILE" 2>&1; then
    printf '    OK\n'
  else
    tail -n 60 "$LOG_FILE" >"$LAST_STEP_LOG" || true
    printf '    FAILED\n' >&2
    sed 's/^/      /' "$LAST_STEP_LOG" | tail -n 20 >&2
    exit 1
  fi
}

verify_sha256() {
  local expected=$1
  local file=$2
  [[ $expected =~ ^[0-9a-fA-F]{64}$ ]] || {
    printf 'A pinned SHA-256 value is required for %s.\n' "$file" >&2
    return 1
  }
  printf '%s  %s\n' "$expected" "$file" | sha256sum -c -
}

verify_optional_sha256() {
  local expected=$1
  local file=$2
  if [[ -n $expected ]]; then
    verify_sha256 "$expected" "$file"
  else
    printf 'No pinned SHA-256 supplied for %s; relying on HTTPS and upstream signatures.\n' "$file"
  fi
}

step_validate_source() {
  [[ -f $SCRIPT_DIR/.gitmodules ]]
  grep -Fq 'path = upservx/public/novnc' "$SCRIPT_DIR/.gitmodules"
  grep -Fq 'url = https://github.com/novnc/noVNC.git' "$SCRIPT_DIR/.gitmodules"
  [[ -f $SCRIPT_DIR/upservx/public/novnc/vnc.html ]]
  if git -C "$SCRIPT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    expected=$(git -C "$SCRIPT_DIR" ls-files -s upservx/public/novnc | awk '{print $2}')
    actual=$(git -C "$SCRIPT_DIR/upservx/public/novnc" rev-parse HEAD)
    [[ -n $expected && $expected == "$actual" ]] || {
      printf 'The noVNC submodule is missing or checked out at the wrong commit.\n' >&2
      return 1
    }
    git -C "$SCRIPT_DIR/upservx/public/novnc" diff --quiet
    git -C "$SCRIPT_DIR/upservx/public/novnc" diff --cached --quiet
  fi
  [[ -f $SCRIPT_DIR/upservx/package-lock.json ]]
  [[ -f $SCRIPT_DIR/upservx-service/requirements.lock ]]
}

step_install_core_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y "${CORE_PACKAGES[@]}"
  local packages=()
  [[ $WITH_LXD == 0 ]] || packages+=(lxd)
  [[ $WITH_LIBVIRT == 0 ]] || packages+=(qemu-kvm qemu-utils libvirt-daemon-system bridge-utils dnsmasq virt-install libvirt-clients websockify sshfs cloud-image-utils genisoimage)
  [[ $WITH_POSTGRESQL == 0 ]] || packages+=(postgresql)
  [[ $WITH_FTP == 0 ]] || packages+=(vsftpd ftp)
  [[ $WITH_OPENVPN == 0 ]] || packages+=(openvpn)
  [[ $WITH_ZFS == 0 ]] || packages+=(zfsutils-linux linux-headers-"$(uname -r)" dkms)
  ((${#packages[@]} == 0)) || apt-get install -y "${packages[@]}"
}

step_install_node() {
  local major=0
  if [[ -x /usr/bin/node ]]; then
    major=$(/usr/bin/node --version | sed 's/^v//' | cut -d. -f1)
  fi
  if ((major < NODE_REQUIRED_MAJOR)); then
    local key_tmp
    key_tmp=$(mktemp)
    curl -fsSL -o "$key_tmp" https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key
    verify_optional_sha256 "${NODESOURCE_KEY_SHA256:-}" "$key_tmp"
    install -d -m 0755 /etc/apt/keyrings
    gpg --batch --dearmor --yes -o /etc/apt/keyrings/nodesource.gpg "$key_tmp"
    rm -f -- "$key_tmp"
    chmod 0644 /etc/apt/keyrings/nodesource.gpg
    printf 'deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_%s.x nodistro main\n' "$NODE_REQUIRED_MAJOR" > /etc/apt/sources.list.d/nodesource.list
    apt-get update
    apt-get install -y nodejs
  fi
  major=$(/usr/bin/node --version | sed 's/^v//' | cut -d. -f1)
  ((major >= NODE_REQUIRED_MAJOR))
  /usr/bin/npm --version
}

step_install_optional_platforms() {
  if [[ $WITH_DOCKER == 1 ]]; then
    # shellcheck source=/dev/null
    . /etc/os-release
    [[ ${ID:-} == debian || ${ID:-} == ubuntu ]]
    [[ -n ${VERSION_CODENAME:-} ]]
    local docker_key
    docker_key=$(mktemp)
    curl -fsSL -o "$docker_key" "https://download.docker.com/linux/${ID}/gpg"
    verify_optional_sha256 "${DOCKER_GPG_SHA256:-}" "$docker_key"
    install -d -m 0755 /etc/apt/keyrings
    install -o root -g root -m 0644 "$docker_key" /etc/apt/keyrings/docker.asc
    rm -f -- "$docker_key"
    printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/%s %s stable\n' "$(dpkg --print-architecture)" "$ID" "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.list
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
  fi
  if [[ $WITH_LXD == 1 ]]; then
    lxd init --auto
  fi
  if [[ $WITH_K3S == 1 ]]; then
    local download_dir kubectl_version kubectl_sha256
    download_dir=$(mktemp -d)
    curl -fsSL -o "$download_dir/k3s-install.sh" https://get.k3s.io
    verify_optional_sha256 "${K3S_INSTALL_SHA256:-}" "$download_dir/k3s-install.sh"
    chmod 0700 "$download_dir/k3s-install.sh"
    INSTALL_K3S_EXEC='server --disable traefik --disable servicelb' sh "$download_dir/k3s-install.sh"
    if [[ -n ${KUBECTL_VERSION:-} ]]; then
      kubectl_version=$KUBECTL_VERSION
      [[ $kubectl_version =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
        printf 'Invalid kubectl version: %s\n' "$kubectl_version" >&2
        return 1
      }
      curl -fsSL -o "$download_dir/kubectl" "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl"
      if [[ -n ${KUBECTL_SHA256:-} ]]; then
        kubectl_sha256=$KUBECTL_SHA256
      else
        kubectl_sha256=$(curl -fsSL "https://dl.k8s.io/release/${kubectl_version}/bin/linux/amd64/kubectl.sha256")
      fi
      verify_sha256 "$kubectl_sha256" "$download_dir/kubectl"
      install -o root -g root -m 0755 "$download_dir/kubectl" /usr/local/bin/kubectl
    elif [[ -n ${KUBECTL_SHA256:-} ]]; then
      printf 'KUBECTL_SHA256 requires KUBECTL_VERSION.\n' >&2
      return 1
    fi
    command -v kubectl
    rm -rf -- "$download_dir"
  fi
}

step_create_service_accounts() {
  getent group "$SERVICE_USER" >/dev/null || groupadd --system "$SERVICE_USER"
  id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --gid "$SERVICE_USER" --home-dir /var/lib/upservx --shell /usr/sbin/nologin "$SERVICE_USER"
  getent group "$WEB_USER" >/dev/null || groupadd --system "$WEB_USER"
  id "$WEB_USER" >/dev/null 2>&1 || useradd --system --gid "$WEB_USER" --home-dir /var/lib/upservx-web --shell /usr/sbin/nologin "$WEB_USER"
  for group in adm; do getent group "$group" >/dev/null && usermod -aG "$group" "$SERVICE_USER"; done
  [[ $WITH_DOCKER == 0 ]] || usermod -aG docker "$SERVICE_USER"
  [[ $WITH_LXD == 0 ]] || usermod -aG lxd "$SERVICE_USER"
  if [[ $WITH_LIBVIRT == 1 ]]; then
    usermod -aG libvirt,kvm "$SERVICE_USER"
  fi
  install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 /etc/upservx
  if find /etc/upservx -xdev -type l -print -quit | grep -q .; then
    printf 'Refusing to install over symlinks below /etc/upservx.\n' >&2
    return 1
  fi
  chown -R "$SERVICE_USER:$SERVICE_USER" /etc/upservx
  find /etc/upservx -xdev -type d -exec chmod 0700 {} +
  find /etc/upservx -xdev -type f -exec chmod 0600 {} +
  install -d -o root -g root -m 0755 "$APP_ROOT" "$APP_ROOT/releases"
  install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 /var/lib/upservx
  install -d -o "$WEB_USER" -g "$WEB_USER" -m 0700 /var/lib/upservx-web
  install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 /var/log/upservx
  install -d -o root -g "$SERVICE_USER" -m 0750 /var/lib/upservx/updates /var/lib/upservx/update-state
  install -d -o root -g root -m 0700 /var/backups/upservx
  for directory in app-store compose app-data customization; do
    install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0750 "/var/lib/upservx/$directory"
  done
  for directory in ssh_keys authorized_keys; do
    install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 "/var/lib/upservx/$directory"
  done
}

step_copy_release() {
  install -d -o root -g root -m 0755 "$RELEASE_STAGING"
  tar \
    --exclude='.git' --exclude='.venv' --exclude='venv' \
    --exclude='node_modules' --exclude='.next' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='upservx/.env.local' \
    --exclude='upservx/tsconfig.tsbuildinfo' \
    --exclude='upservx-service/ssh_keys' \
    --exclude='upservx-service/authorized_keys' \
    --exclude='upservx/public/novnc/package-lock.json' \
    -C "$SCRIPT_DIR" -cf - . | tar -C "$RELEASE_STAGING" -xf -
}

step_build_release() {
  printf 'NEXT_PUBLIC_API_BASE_URL=\nNEXT_PUBLIC_WS_BASE_URL=\n' >"$RELEASE_STAGING/upservx/.env.local"
  (cd "$RELEASE_STAGING/upservx" && /usr/bin/npm ci && /usr/bin/npm run build)
  (cd "$RELEASE_STAGING/upservx-service" && python3 -m venv venv && venv/bin/pip install --no-deps -r requirements.lock)
  (cd "$RELEASE_STAGING/upservx-cli" && python3 -m venv venv && venv/bin/pip install --no-deps -r requirements.lock)
  chown -R root:root "$RELEASE_STAGING"
  find "$RELEASE_STAGING" -type d -exec chmod u=rwx,go=rx {} +
  find "$RELEASE_STAGING" -type f -perm /022 -exec chmod go-w {} +
  mv -- "$RELEASE_STAGING" "$RELEASE_DIR"
  ln -s "$RELEASE_DIR" "$APP_ROOT/.current.$$"
  mv -Tf -- "$APP_ROOT/.current.$$" "$APP_ROOT/current"
}

step_configure_mutable_state() {
  ln -sfn /var/lib/upservx/app-store "$APP_ROOT/app-store"
  ln -sfn /var/lib/upservx/compose "$APP_ROOT/compose"
  ln -sfn /var/lib/upservx/customization "$APP_ROOT/customization"
  cp -a "$RELEASE_DIR/app-store-templates/." /var/lib/upservx/app-store/
  chown -R "$SERVICE_USER:$SERVICE_USER" /var/lib/upservx/app-store
  if [[ $WITH_LIBVIRT == 1 ]]; then
    install -d -o libvirt-qemu -g libvirt-qemu -m 0755 /var/lib/libvirt/isos
  fi
  if [[ $WITH_K3S == 1 ]]; then
    install -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0600 /etc/rancher/k3s/k3s.yaml /etc/upservx/kubeconfig
  fi
  cat > /etc/upservx/service.env <<EOF
UPSERVX_COOKIE_SECURE=true
UPSERVX_COOKIE_SAMESITE=strict
UPSERVX_SESSION_TTL_SECONDS=3600
KUBECONFIG=/etc/upservx/kubeconfig
EOF
  chown "$SERVICE_USER:$SERVICE_USER" /etc/upservx/service.env
  chmod 0600 /etc/upservx/service.env
  install -o "$WEB_USER" -g "$WEB_USER" -m 0600 /dev/null /var/lib/upservx-web/web.env
  if [[ $UPDATES_ENABLED == 1 ]]; then
    install -d -o root -g root -m 0755 /usr/share/upservx
    install -o root -g root -m 0644 "$UPDATE_PUBLIC_KEY" /usr/share/upservx/update-public.pem
  fi
  cat > /var/lib/upservx/install-profile <<EOF
WITH_DOCKER=$WITH_DOCKER
WITH_LXD=$WITH_LXD
WITH_LIBVIRT=$WITH_LIBVIRT
WITH_K3S=$WITH_K3S
WITH_POSTGRESQL=$WITH_POSTGRESQL
WITH_FTP=$WITH_FTP
WITH_OPENVPN=$WITH_OPENVPN
WITH_ZFS=$WITH_ZFS
UPDATES_ENABLED=$UPDATES_ENABLED
EOF
  chown root:"$SERVICE_USER" /var/lib/upservx/install-profile
  chmod 0640 /var/lib/upservx/install-profile
}

step_install_privilege_boundary() {
  install -d -o root -g root -m 0755 /usr/local/libexec /usr/local/libexec/upservx-bin
  install -o root -g root -m 0755 "$RELEASE_DIR/deploy/upservx-privileged" /usr/local/libexec/upservx-privileged
  install -o root -g root -m 0755 "$RELEASE_DIR/deploy/upservx-command" /usr/local/libexec/upservx-command
  install -o root -g root -m 0755 "$RELEASE_DIR/deploy/upservx-updater" /usr/local/libexec/upservx-updater
  install -o root -g root -m 0755 "$RELEASE_DIR/deploy/upservx-health-check" /usr/local/libexec/upservx-health-check
  install -o root -g root -m 0755 "$RELEASE_DIR/deploy/upservx-post-install-smoke" /usr/local/libexec/upservx-post-install-smoke
  local commands=(apt-get certbot chpasswd dhclient fail2ban-client groupadd groupdel gpasswd hostnamectl ip mkfs.btrfs mkfs.exfat mkfs.ext4 mkfs.ntfs mkfs.vfat mount nft nginx openvpn systemctl timedatectl umount useradd userdel usermod zfs zpool)
  local command
  for command in "${commands[@]}"; do
    ln -sfn /usr/local/libexec/upservx-command "/usr/local/libexec/upservx-bin/$command"
  done
  install -o root -g root -m 0440 "$RELEASE_DIR/deploy/sudoers/upservx" /etc/sudoers.d/upservx
  visudo -cf /etc/sudoers.d/upservx
  install -o root -g root -m 0644 "$RELEASE_DIR/deploy/tmpfiles/upservx.conf" /etc/tmpfiles.d/upservx.conf
  systemd-tmpfiles --create /etc/tmpfiles.d/upservx.conf
}

step_install_systemd_units() {
  install -o root -g root -m 0644 "$RELEASE_DIR"/deploy/systemd/* /etc/systemd/system/
  if [[ -f /etc/systemd/system/upservx.service ]]; then
    systemctl disable --now upservx.service || true
    rm -f -- /etc/systemd/system/upservx.service
  fi
  systemctl daemon-reload
}

step_configure_https() {
  local tls_dir=/etc/upservx/tls
  local certificate=$tls_dir/server.crt
  local private_key=$tls_dir/server.key
  install -d -o "$SERVICE_USER" -g "$SERVICE_USER" -m 0700 "$tls_dir"
  if [[ -e $certificate || -e $private_key ]]; then
    [[ -f $certificate && -f $private_key && ! -L $certificate && ! -L $private_key ]] || {
      printf 'Both TLS certificate and key must be regular files.\n' >&2
      return 1
    }
  else
    local common_name server_ip san
    common_name=$(hostname -f 2>/dev/null || hostname)
    [[ $common_name =~ ^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$ ]] || common_name=localhost
    server_ip=$(primary_server_ip)
    san="DNS:${common_name},DNS:localhost,IP:127.0.0.1"
    [[ $server_ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] && san="$san,IP:$server_ip"
    openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 397 \
      -subj "/CN=$common_name" -addext "subjectAltName=$san" \
      -keyout "$private_key" -out "$certificate"
  fi
  openssl x509 -in "$certificate" -noout
  openssl pkey -in "$private_key" -check -noout
  chown "$SERVICE_USER:$SERVICE_USER" "$certificate" "$private_key"
  chmod 0600 "$certificate" "$private_key"
  install -o root -g root -m 0644 "$RELEASE_DIR/deploy/nginx/upservx.conf" /etc/nginx/sites-available/upservx
  if [[ -L /etc/nginx/sites-enabled/default ]]; then
    [[ $(readlink -f /etc/nginx/sites-enabled/default) == /etc/nginx/sites-available/default ]] || {
      printf 'Refusing to replace a custom nginx default-site link.\n' >&2
      return 1
    }
    rm -f -- /etc/nginx/sites-enabled/default
  elif [[ -e /etc/nginx/sites-enabled/default ]]; then
    printf 'Refusing to replace a custom nginx default-site file.\n' >&2
    return 1
  fi
  ln -sfn /etc/nginx/sites-available/upservx /etc/nginx/sites-enabled/upservx
  nginx -t
  systemctl enable nginx
  systemctl reload nginx
}

step_initialize_secrets() {
  cd /var/lib/upservx
  runuser -u "$SERVICE_USER" -- env HOME=/var/lib/upservx \
    PYTHONPATH="$RELEASE_DIR/upservx-service" \
    UPSERVX_LOG_FILE=/var/log/upservx/api.log \
    "$RELEASE_DIR/upservx-service/venv/bin/python3" -c \
    "from lib.cluster_security import ensure_node_tls; from lib.encryption import EncryptionManager; from lib.session_tokens import _get_secret; EncryptionManager.ensure_key_exists(); _get_secret(); ensure_node_tls()"
}

step_install_cli() {
  cat > /usr/local/bin/upservx <<'EOF'
#!/usr/bin/env bash
exec /opt/upservx/current/upservx-cli/venv/bin/python /opt/upservx/current/upservx-cli/upservx "$@"
EOF
  chown root:root /usr/local/bin/upservx
  chmod 0755 /usr/local/bin/upservx
}

step_start_and_verify() {
  systemctl enable --now upservx.target upservx-health.timer
  systemctl restart upservx-api.service upservx-web.service upservx-worker.service
  /usr/local/libexec/upservx-health-check wait-api
  /usr/local/libexec/upservx-health-check wait-web
  /usr/local/libexec/upservx-post-install-smoke
}

: >"$LOG_FILE"
printf 'UpservX installer log: %s\n' "$LOG_FILE"
if [[ $RESUME_INSTALLATION == 1 ]]; then
  TOTAL_STEPS=7
  run_step 'Configure mutable state and update trust' step_configure_mutable_state
  run_step 'Install the privileged helper boundary' step_install_privilege_boundary
  run_step 'Install separate systemd units and probes' step_install_systemd_units
  run_step 'Configure the local HTTPS reverse proxy' step_configure_https
  run_step 'Generate application, session, and cluster keys' step_initialize_secrets
  run_step 'Install the CLI launcher' step_install_cli
  run_step 'Start services and run the post-install smoke test' step_start_and_verify
  trap - EXIT
  printf 'Installation resumed successfully. Release: %s\n' "$RELEASE_VERSION"
  print_access_information
  printf 'Status: systemctl status upservx.target\n'
  printf 'Smoke test: sudo /usr/local/libexec/upservx-post-install-smoke\n'
  exit 0
fi
TOTAL_STEPS=14
run_step 'Validate locked source and noVNC submodule' step_validate_source
if [[ $REINSTALL == 1 ]]; then
  backup_broken_installation
fi
run_step 'Install minimal and selected profile packages' step_install_core_packages
run_step "Install or verify Node.js ${NODE_REQUIRED_MAJOR}" step_install_node
run_step 'Install selected optional platforms' step_install_optional_platforms
run_step 'Create dedicated service accounts and data roots' step_create_service_accounts
run_step "Copy immutable release ${RELEASE_VERSION}" step_copy_release
run_step 'Install locked dependencies and build the release' step_build_release
run_step 'Configure mutable state and update trust' step_configure_mutable_state
run_step 'Install the privileged helper boundary' step_install_privilege_boundary
run_step 'Install separate systemd units and probes' step_install_systemd_units
run_step 'Configure the local HTTPS reverse proxy' step_configure_https
run_step 'Generate application, session, and cluster keys' step_initialize_secrets
run_step 'Install the CLI launcher' step_install_cli
run_step 'Start services and run the post-install smoke test' step_start_and_verify

trap - EXIT
printf 'Installation complete. Release: %s\n' "$RELEASE_VERSION"
[[ -z $REINSTALL_BACKUP_DIR ]] || printf 'Previous installation backup: %s\n' "$REINSTALL_BACKUP_DIR"
print_access_information
printf 'Status: systemctl status upservx.target\n'
printf 'Smoke test: sudo /usr/local/libexec/upservx-post-install-smoke\n'
