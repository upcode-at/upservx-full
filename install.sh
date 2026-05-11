#!/usr/bin/env bash
# install.sh - Install dependencies, build frontend/backend and configure service

set -euo pipefail

APP_DIR="/opt/upservx"
SERVICE_NAME="upservx"
PACKAGES="build-essential gcc g++ make python3 python3-pip python3-venv python3-dev libpq-dev libpam0g-dev python3-certbot python3-certbot-nginx nginx certbot git lshw openssl gawk coreutils curl grep jq lxd qemu-kvm libvirt-daemon-system bridge-utils dnsmasq virt-install libvirt-clients sshfs vsftpd postgresql openvpn ftp linux-headers-$(uname -r) dkms websockify novnc fail2ban"
NODE_REQUIRED_MAJOR=20

LOG_DIR="/tmp"
LOG_FILE="${LOG_DIR}/upservx-install.log"
LAST_STEP_LOG="${LOG_DIR}/upservx-install-last.log"

INSTALL_USER="${SUDO_USER:-$USER}"
INSTALL_HOME="$(eval echo "~${INSTALL_USER}")"

TOTAL_STEPS=21
CURRENT_STEP=0

# === UI =====================================================================
if [[ -t 1 ]]; then
  BOLD="\033[1m"
  DIM="\033[2m"
  BLUE="\033[34m"
  GREEN="\033[32m"
  RED="\033[31m"
  YELLOW="\033[33m"
  NC="\033[0m"
else
  BOLD=""
  DIM=""
  BLUE=""
  GREEN=""
  RED=""
  YELLOW=""
  NC=""
fi

banner() {
  printf "\n${BOLD}${BLUE}==============================================================${NC}\n"
  printf "${BOLD}${BLUE}                 UpservX Installer (v0.5.1)                  ${NC}\n"
  printf "${BOLD}${BLUE}==============================================================${NC}\n"
  printf "${DIM}Log file: %s${NC}\n\n" "$LOG_FILE"
}

spinner() {
  local pid="$1"
  local spin='|/-\\'
  local i=0
  while kill -0 "$pid" 2>/dev/null; do
    i=$(( (i + 1) % 4 ))
    printf "\r    ${DIM}[%c] working...${NC}" "${spin:$i:1}"
    sleep 0.1
  done
  printf "\r%-40s\r" ""
}

run_step() {
  local title="$1"
  local fn="$2"

  CURRENT_STEP=$((CURRENT_STEP + 1))
  printf "${BOLD}${BLUE}[%02d/%02d]${NC} %s\n" "$CURRENT_STEP" "$TOTAL_STEPS" "$title"

  : > "$LAST_STEP_LOG"
  {
    printf "\n=== [%02d/%02d] %s ===\n" "$CURRENT_STEP" "$TOTAL_STEPS" "$title"
    "$fn"
  } >>"$LOG_FILE" 2>>"$LOG_FILE" &

  local pid=$!
  spinner "$pid"
  wait "$pid"
  local rc=$?

  if [[ $rc -eq 0 ]]; then
    printf "    ${GREEN}OK${NC}\n\n"
  else
    # Extract the last lines of this failed section for quick visibility.
    tail -n 60 "$LOG_FILE" > "$LAST_STEP_LOG" || true
    printf "    ${RED}FAILED${NC}\n"
    printf "    ${YELLOW}Last log lines:${NC}\n"
    sed 's/^/      /' "$LAST_STEP_LOG" | tail -n 20
    printf "\n${RED}Installation aborted.${NC} Full log: ${BOLD}%s${NC}\n" "$LOG_FILE"
    exit 1
  fi
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    printf "${RED}This installer must run as root.${NC}\n"
    printf "Use: ${BOLD}sudo ./install.sh${NC}\n"
    exit 1
  fi
}

# === Step actions ============================================================
step_update_codebase() {
  git pull origin main
}

step_install_system_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  for pkg in $PACKAGES; do
    apt-get install -y --ignore-missing "$pkg" || true
  done
  apt-get update
  apt-get install -y --ignore-missing zfsutils-linux || true
}

step_install_docker() {
  apt-get update
  apt-get install -y ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

step_init_lxd() {
  lxd init --auto
}

step_init_k3s() {
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik --disable servicelb" sh -

  mkdir -p "$INSTALL_HOME/.kube"
  cp /etc/rancher/k3s/k3s.yaml "$INSTALL_HOME/.kube/config"
  chown "$INSTALL_USER:$INSTALL_USER" "$INSTALL_HOME/.kube/config" 2>/dev/null || true
  chmod 600 "$INSTALL_HOME/.kube/config"

  if ! grep -q "KUBECONFIG=~/.kube/config" "$INSTALL_HOME/.bashrc" 2>/dev/null; then
    echo "export KUBECONFIG=~/.kube/config" >> "$INSTALL_HOME/.bashrc"
  fi
}

step_copy_project() {
  mkdir -p "$APP_DIR"
  cp -R . "$APP_DIR"
  chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR" 2>/dev/null || true
}

step_install_nvm() {
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
}

step_install_node() {
  export NVM_DIR="$HOME/.nvm"
  # shellcheck source=/dev/null
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
  nvm install "${NODE_REQUIRED_MAJOR}"
  nvm use "${NODE_REQUIRED_MAJOR}"
  nvm alias default "${NODE_REQUIRED_MAJOR}"

  local node_bin_dir
  node_bin_dir="$(dirname "$(nvm which current)")"
  ln -sf "$node_bin_dir/node" /usr/local/bin/node
  ln -sf "$node_bin_dir/npm" /usr/local/bin/npm
  ln -sf "$node_bin_dir/npx" /usr/local/bin/npx
}

step_npm_install() {
  cd "$APP_DIR/upservx"
  npm install
}

step_configure_next_env() {
  local server_ip
  server_ip="$(hostname -I | awk '{print $1}')"

  cat > "$APP_DIR/upservx/.env.local" <<EOF
# API Configuration - Auto-generated by install.sh
NEXT_PUBLIC_API_BASE_URL=http://${server_ip}:9500
NEXT_PUBLIC_WS_BASE_URL=ws://${server_ip}:9500
EOF

  chmod 644 "$APP_DIR/upservx/.env.local"
}

step_npm_build() {
  cd "$APP_DIR/upservx"
  npm run build
}

step_install_python_requirements() {
  cd "$APP_DIR/upservx-service"
  python3 -m venv --without-pip venv
  curl -fsSL https://bootstrap.pypa.io/get-pip.py | venv/bin/python3
  venv/bin/pip install -r requirements.txt
}

step_generate_start_script() {
  cat <<'EOS' > "$APP_DIR/start.sh"
#!/usr/bin/env bash
cd "$(dirname "$0")"
( cd upservx && npm start ) &
( cd upservx-service && venv/bin/python3 main.py ) &
wait -n
EOS
  chmod +x "$APP_DIR/start.sh"
}

step_generate_encryption_key() {
  cd "$APP_DIR/upservx-service"
  venv/bin/python3 -c "from encryption import EncryptionManager; EncryptionManager.ensure_key_exists(); print('Encryption key generated')"
}

step_setup_log_file() {
  touch /etc/upservx.log
  chown "$INSTALL_USER:$INSTALL_USER" /etc/upservx.log 2>/dev/null || true
  chmod 640 /etc/upservx.log
}

step_fix_pam_config() {
  for f in /etc/pam.d/login /etc/pam.d/sshd /etc/pam.d/common-session; do
    [ -f "$f" ] && sed -i '/pam_lastlog\.so/d' "$f" || true
  done
}

step_create_iso_dir() {
  mkdir -p /var/lib/libvirt/isos
  chown libvirt-qemu:libvirt-qemu /var/lib/libvirt/isos
  chmod 755 /var/lib/libvirt/isos
}

step_copy_appstore_templates() {
  mkdir -p /opt/upservx/app-store
  cp -r "$APP_DIR/app-store-templates/"* /opt/upservx/app-store/
  chown -R "$INSTALL_USER:$INSTALL_USER" /opt/upservx/app-store 2>/dev/null || true
}

step_install_novnc() {
  mkdir -p "$APP_DIR/upservx/public/novnc"
  cp -r /usr/share/novnc/* "$APP_DIR/upservx/public/novnc/"
  chown -R "$INSTALL_USER:$INSTALL_USER" "$APP_DIR/upservx/public/novnc" 2>/dev/null || true
}

step_create_systemd_service() {
  cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<EOF_SERVICE
[Unit]
Description=upservx Next.js + Python Service
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/start.sh
Restart=always
User=${INSTALL_USER}
Environment=NODE_ENV=production
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF_SERVICE
}

step_enable_service() {
  systemctl daemon-reload
  systemctl enable "$SERVICE_NAME"
  systemctl start "$SERVICE_NAME"
}

step_install_cli() {
  cd "$APP_DIR/upservx-cli"
  python3 -m venv --without-pip venv
  curl -fsSL https://bootstrap.pypa.io/get-pip.py | venv/bin/python3
  venv/bin/pip install --quiet -r requirements.txt
  pip3 install -r requirements.txt --break-system-packages

  local cli_bin="/usr/local/bin/upservx"
  rm -f "$cli_bin"
  cat > "$cli_bin" <<EOF_CLI
#!/usr/bin/env bash
exec "$APP_DIR/upservx-cli/venv/bin/python" "$APP_DIR/upservx-cli/upservx" "\$@"
EOF_CLI
  chmod +x "$cli_bin"
}

print_summary() {
  printf "${BOLD}${GREEN}Installation complete.${NC}\n"
  printf "Service status: ${BLUE}systemctl status %s${NC}\n" "$SERVICE_NAME"
  printf "CLI command:    ${BLUE}upservx --help${NC}\n"
  printf "Installer log:  ${BLUE}%s${NC}\n" "$LOG_FILE"
}

# === Main ===================================================================
require_root
banner

mkdir -p "$LOG_DIR"
: > "$LOG_FILE"

if [[ -f "./upservx-service/requirements.txt" ]]; then
  TOTAL_STEPS=22
fi

run_step "Update codebase" step_update_codebase
run_step "Install system packages" step_install_system_packages
run_step "Install Docker" step_install_docker
run_step "Initialize LXD" step_init_lxd
run_step "Initialize K3s" step_init_k3s
run_step "Copy project to $APP_DIR" step_copy_project
run_step "Install nvm" step_install_nvm
run_step "Install Node.js ${NODE_REQUIRED_MAJOR} via nvm" step_install_node
run_step "Install frontend dependencies" step_npm_install
run_step "Configure Next.js environment" step_configure_next_env
run_step "Build frontend" step_npm_build

if [[ -f "$APP_DIR/upservx-service/requirements.txt" ]]; then
  run_step "Install Python requirements" step_install_python_requirements
fi

run_step "Generate start script" step_generate_start_script
run_step "Generate encryption key" step_generate_encryption_key
run_step "Setup log file" step_setup_log_file
run_step "Fix PAM config" step_fix_pam_config
run_step "Create ISO directory" step_create_iso_dir
run_step "Copy app store templates" step_copy_appstore_templates
run_step "Install noVNC assets" step_install_novnc
run_step "Create systemd service" step_create_systemd_service
run_step "Enable and start service" step_enable_service
run_step "Install upservx CLI" step_install_cli

systemctl restart "$SERVICE_NAME" >> "$LOG_FILE" 2>&1 || true
print_summary