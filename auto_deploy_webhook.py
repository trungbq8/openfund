from flask import Flask
import subprocess

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    subprocess.Popen(["/root/openfund/deploy.sh"])
    return "Deployed", 200

if __name__ == "__main__":
    app.run(port=5001)