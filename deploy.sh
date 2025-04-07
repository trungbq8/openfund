# Must allow execute this mannually: chmod +x /root/openfund/deploy.sh
# Pull the latest code
git pull origin main

# Reinstall dependencies
pip install -r requirements.txt

# Restart the app
systemctl restart openfund.service