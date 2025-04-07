from flask import Flask
import os

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    os.system("chmod +x deploy.sh")
    os.system("/root/openfund/deploy.sh")
    return "Deployed", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)