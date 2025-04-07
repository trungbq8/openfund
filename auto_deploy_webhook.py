from flask import Flask
import os

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    os.system("./deploy.sh")
    return "Deployed", 200

if __name__ == "__main__":
    app.run(port=5001)