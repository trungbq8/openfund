# Must allow execute this mannually: chmod +x /root/openfund/deploy.sh

# Activate virtual environment
source /root/openfund/env/bin/activate

# Pull the latest code
git pull origin main

# Reinstall dependencies
pip install -r requirements.txt

deactivate

# Restart the app
systemctl restart openfund.service