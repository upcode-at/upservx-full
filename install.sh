#!/bin/bash

apt update
apt install -y python3 python3-pip python3-venv git nodejs npm
cd ./upservx-service

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cd ../upservx
npm install
npm run build
mv dist ../upservx-service/static
