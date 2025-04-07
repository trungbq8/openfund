#!/bin/bash
cd /root/openfund

# Pull the latest code
git pull origin main

# Reinstall dependencies
pip install -r requirements.txt

# Restart the app using gunicorn or systemd
sudo systemctl restart openfund.service