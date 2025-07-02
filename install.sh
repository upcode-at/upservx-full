#!/bin/bash

set -e

# Update package lists
apt update

# Install required packages
apt install -y \
    python3 python3-pip python3-venv git \
    nodejs npm \
    docker.io kubeadm kubectl kubelet \
    lxc qemu-kvm libvirt-daemon-system libvirt-clients \
    sshfs vsftpd postgresql ftp

# Configure PostgreSQL credentials
read -s -p "Enter postgres root password: " POSTGRES_ROOT_PASSWORD
echo
read -p "Enter backend postgres user: " POSTGRES_USER
read -s -p "Enter password for $POSTGRES_USER: " POSTGRES_USER_PASSWORD
echo

sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
ALTER USER postgres WITH PASSWORD '${POSTGRES_ROOT_PASSWORD}';
CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_USER_PASSWORD}';
CREATE DATABASE ${POSTGRES_USER} OWNER ${POSTGRES_USER};
SQL

# Setup backend Python environment
cd ./upservx-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

deactivate

# Build frontend
cd ../upservx
npm install
npm run build
mv dist ../upservx-service/static
