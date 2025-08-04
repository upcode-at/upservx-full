#!/usr/bin/env bash
# install.sh – Install dependencies, build Next.js, set up systemd service

set -e

APP_DIR="/opt/upservx"
SERVICE_NAME="upservx"
PACKAGES="python3 python3-pip python3-venv git nodejs npm lshw lxd qemu-kvm libvirt-daemon-system libvirt-clients sshfs vsftpd postgresql ftp zfsutils-linux linux-headers-$(uname -r) dkms"

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

# === 1. Install system dependencies ==========================================
step "Install system packages"
{
  sudo apt update &&
  sudo apt install -y $PACKAGES
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === Install Docker from official repository ================================
step "Install Docker"
{
  sudo apt-get update &&
  sudo apt-get install -y ca-certificates curl &&
  sudo install -m 0755 -d /etc/apt/keyrings &&
  sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc &&
  sudo chmod a+r /etc/apt/keyrings/docker.asc &&
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null &&
  sudo apt-get update &&
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 2. Copy project files ===================================================
step "Copy project to $APP_DIR"
{
  sudo mkdir -p "$APP_DIR" &&
  sudo cp -R . "$APP_DIR" &&
  sudo chown -R $USER:$USER "$APP_DIR"
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
( cd upservx-service && source venv/bin/activate && python3 main.py ) &
wait -n
EOS
chmod +x "$APP_DIR/start.sh"
ok

# === 7. Install systemd service =============================================
step "Create systemd service"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<EOF_SERVICE
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
  sudo systemctl daemon-reload &&
  sudo systemctl enable "${SERVICE_NAME}" &&
  sudo systemctl start "${SERVICE_NAME}"
} &>/tmp/install.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

printf "\n${GREEN}Installation complete!${NC}\n"
printf "Check status with: ${BLUE}systemctl status ${SERVICE_NAME}${NC}\n"
