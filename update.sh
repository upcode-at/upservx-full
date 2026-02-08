#!/usr/bin/env bash
# update.sh – Pull latest changes, rebuild Next.js, restart service

set -e

APP_DIR="/opt/upservx"
SERVICE_NAME="upservx"

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

# === 1. Stop service =========================================================
step "Stop ${SERVICE_NAME} service"
{
  sudo systemctl stop "${SERVICE_NAME}"
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 2. Pull latest changes ==================================================
step "Pull latest changes from git"
{
  cd "$APP_DIR" && git pull origin main
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 3. Update npm dependencies ==============================================
step "Update npm dependencies"
{
  cd "$APP_DIR/upservx" && npm install
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 4. Rebuild Next.js ======================================================
step "Rebuild Next.js application"
{
  cd "$APP_DIR/upservx" && npm run build
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 5. Update Python dependencies ==========================================
if [ -f "$APP_DIR/upservx-service/requirements.txt" ]; then
  step "Update Python requirements"
  {
    cd "$APP_DIR/upservx-service" &&
    source venv/bin/activate &&
    pip install -r requirements.txt --upgrade
  } &>/tmp/update.log &
  spin $!
  if [ $? -eq 0 ]; then ok; else fail; fi
fi

# === 6. Update app store templates ==========================================
step "Update app store templates"
{
  sudo cp -r "$APP_DIR/app-store-templates/"* /opt/upservx/app-store/
  sudo chown -R $USER:$USER /opt/upservx/app-store
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 7. Start service ========================================================
step "Start ${SERVICE_NAME} service"
{
  sudo systemctl start "${SERVICE_NAME}"
} &>/tmp/update.log &
spin $!
if [ $? -eq 0 ]; then ok; else fail; fi

# === 8. Check service status =================================================
step "Verify service status"
sleep 2
if sudo systemctl is-active --quiet "${SERVICE_NAME}"; then
  ok
  printf "\n${GREEN}Update complete!${NC}\n"
  printf "Service status: ${BLUE}systemctl status ${SERVICE_NAME}${NC}\n"
  printf "View logs: ${BLUE}journalctl -u ${SERVICE_NAME} -f${NC}\n"
else
  fail
  printf "\n${RED}Service failed to start!${NC}\n"
  printf "Check logs: ${BLUE}journalctl -u ${SERVICE_NAME} -n 50${NC}\n"
  exit 1
fi
