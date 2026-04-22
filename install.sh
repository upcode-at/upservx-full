#!/usr/bin/env bash
# install.sh – Install dependencies, build Next.js, set up systemd service

set -e

APP_DIR="/opt/upservx"
SERVICE_NAME="upservx"
PACKAGES="build-essential gcc g++ make python3 python3-pip python3-venv python3-dev libpq-dev libpam0g-dev python3-certbot python3-certbot-nginx nginx certbot git lshw openssl gawk coreutils curl grep jq lxd qemu-kvm libvirt-daemon-system bridge-utils dnsmasq virt-install libvirt-clients sshfs vsftpd postgresql openvpn ftp linux-headers-$(uname -r) dkms websockify novnc"
NODE_REQUIRED_MAJOR=20

# === Colors & Spinner ========================================================
GREEN="\e[32m"
BLUE="\e[34m"
RED="\e[31m"
NC="\e[0m"

spin() {
  local pid=$1
  local delay=0.1
  local spinstr='|/-\'
  while ps -p $pid >/dev/null 2>&1; do
    local temp=${spinstr#?}
    printf " [%c]  " "$spinstr"
    spinstr=$temp${spinstr%"$temp"}
    sleep $delay
    printf "\b\b\b\b\b\b"
  done
}
step() {
  printf "${BLUE}➜${NC} %s..." "$1"
}

ok() {
  printf "${GREEN}✔${NC}\n"
}

fail() {
  printf "${RED}✖${NC}\n"
  exit 1
}
step "Update Codebase"
{
  git pull origin main
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi
# === 1. Install system dependencies ==========================================
step "Install system packages"
{
  #sed -r -i'.BAK' 's/^deb(.*)$/deb\1 contrib/g' /etc/apt/sources.list
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y $PACKAGES
  apt-get update
  apt-get install -y zfsutils-linux
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === Install Docker from official repository ================================
step "Install Docker"
{
  apt-get update &&
  apt-get install -y ca-certificates curl &&
  install -m 0755 -d /etc/apt/keyrings &&
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc &&
  chmod a+r /etc/apt/keyrings/docker.asc &&
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
    tee /etc/apt/sources.list.d/docker.list > /dev/null &&
  apt-get update &&
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === Initialize LXD ==========================================================
step "Initialize LXD"
{
  lxd init --auto
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === Initialize Kubernetes ==========================================================
step "Initialize K3s"
{
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
  curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik --disable servicelb" sh -
  
  mkdir -p ~/.kube
  cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
  chown $USER:$USER ~/.kube/config
  chmod 600 ~/.kube/config
  
  export KUBECONFIG=~/.kube/config
  echo "export KUBECONFIG=~/.kube/config" >> ~/.bashrc
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 2. Copy project files ===================================================
step "Copy project to $APP_DIR"
{
  mkdir -p "$APP_DIR" &&
  cp -R . "$APP_DIR" &&
  chown -R $USER:$USER "$APP_DIR"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 2.5. Install compatible Node.js version via nvm ========================
step "Install nvm"
{
  curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.5/install.sh | bash
  export NVM_DIR="$HOME/.nvm"
  # shellcheck source=/dev/null
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

step "Install Node.js ${NODE_REQUIRED_MAJOR} via nvm"
{
  export NVM_DIR="$HOME/.nvm"
  [ -s "$NVM_DIR/nvm.sh" ] && source "$NVM_DIR/nvm.sh"
  nvm install "${NODE_REQUIRED_MAJOR}"
  nvm use "${NODE_REQUIRED_MAJOR}"
  nvm alias default "${NODE_REQUIRED_MAJOR}"
  # Make node/npm globally available
  NODE_BIN_DIR="$(dirname "$(nvm which current)")"
  ln -sf "$NODE_BIN_DIR/node" /usr/local/bin/node
  ln -sf "$NODE_BIN_DIR/npm"  /usr/local/bin/npm
  ln -sf "$NODE_BIN_DIR/npx"  /usr/local/bin/npx
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 3. npm dependencies =====================================================
step "npm install"
{
  cd "$APP_DIR/upservx" && npm install
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 3.5. Configure Next.js environment ======================================
step "Configure Next.js environment"
{
  # Get the primary IP address of the server
  SERVER_IP=$(hostname -I | awk '{print $1}')
  
  # Create .env.local for Next.js
  cat > "$APP_DIR/upservx/.env.local" <<EOF
# API Configuration - Auto-generated by install.sh
NEXT_PUBLIC_API_BASE_URL=http://${SERVER_IP}:9500
NEXT_PUBLIC_WS_BASE_URL=ws://${SERVER_IP}:9500
EOF
  
  chmod 644 "$APP_DIR/upservx/.env.local"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 4. Next.js build ========================================================
step "npm run build"
{
  cd "$APP_DIR/upservx" && npm run build
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 5. Python dependencies ==================================================
if [ -f "$APP_DIR/upservx-service/requirements.txt" ]; then
  step "Install Python requirements"
  {
    cd "$APP_DIR/upservx-service" &&
    python3 -m venv venv &&
    source venv/bin/activate &&
    pip install -r requirements.txt
  } &>/tmp/install.log &
  spin $!
  if [ $? -eq 0 ]; then ok; else fail; fi
fi

# === 6. Start script for service ============================================
step "Generate start.sh"
cat <<'EOS' > "$APP_DIR/start.sh"
#!/usr/bin/env bash
cd "$(dirname "$0")"
( cd upservx && npm start ) &
( cd upservx-service && venv/bin/python3 main.py ) &
wait -n
EOS
chmod +x "$APP_DIR/start.sh"
ok

# === 6.3. Generate encryption key ============================================
step "Generate encryption key"
{
  cd "$APP_DIR/upservx-service" &&
  source venv/bin/activate &&
  python3 -c "from encryption import EncryptionManager; EncryptionManager.ensure_key_exists(); print('Encryption key generated')"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 6.31. Setup log file =====================================================
step "Setup log file"
{
  touch /etc/upservx.log
  chown $USER:$USER /etc/upservx.log
  chmod 640 /etc/upservx.log
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 6.4. Create ISO directory ==============================================
step "Create ISO directory"
{
  mkdir -p /var/lib/libvirt/isos
  chown libvirt-qemu:libvirt-qemu /var/lib/libvirt/isos
  chmod 755 /var/lib/libvirt/isos
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 6.5. Copy app store templates ===========================================
step "Copy app store templates"
{
  mkdir -p /opt/upservx/app-store
  cp -r "$APP_DIR/app-store-templates/"* /opt/upservx/app-store/
  chown -R $USER:$USER /opt/upservx/app-store
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 6.6. Install noVNC for VM console =======================================
step "Install noVNC"
{
  mkdir -p "$APP_DIR/upservx/public/novnc"
  cp -r /usr/share/novnc/* "$APP_DIR/upservx/public/novnc/"
  chown -R $USER:$USER "$APP_DIR/upservx/public/novnc"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 7. Install systemd service =============================================
step "Create systemd service"
tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF_SERVICE
[Unit]
Description=upservx Next.js + Python Service
After=network.target

[Service]
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/start.sh
Restart=always
User=$USER
Environment=NODE_ENV=production
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF_SERVICE
ok

# === 8. Enable service =======================================================
step "Enable and start service"
{
  systemctl daemon-reload &&
  systemctl enable "${SERVICE_NAME}" &&
  systemctl start "${SERVICE_NAME}"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 9. Install CLI =========================================================
step "Install upservx CLI – venv"
{
  cd "$APP_DIR/upservx-cli"
  python3 -m venv venv
  source venv/bin/activate
  pip install --quiet -r requirements.txt
  deactivate
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

step "Install upservx CLI – link binary"
{
  CLI_BIN="/usr/local/bin/upservx"
  rm -f "$CLI_BIN"

  # Shell wrapper: activates the CLI venv and runs the entry point
  cat > "$CLI_BIN" <<EOF_CLI
#!/usr/bin/env bash
exec "$APP_DIR/upservx-cli/venv/bin/python" "$APP_DIR/upservx-cli/upservx" "\$@"
EOF_CLI

  chmod +x "$CLI_BIN"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

printf "\n${GREEN}Installation complete!${NC}\n"
printf "Check status with: ${BLUE}systemctl status ${SERVICE_NAME}${NC}\n"
printf "CLI available:    ${BLUE}upservx --help${NC}\n"
systemctl restart ${SERVICE_NAME}