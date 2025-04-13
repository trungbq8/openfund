from flask import Flask, render_template, jsonify, request, session
from web3 import Web3
import eth_account
from eth_account.messages import encode_defunct
import os
import secrets
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
app.secret_key = secrets.token_hex(16)

w3 = Web3(Web3.HTTPProvider('https://evm-rpc-arctic-1.sei-apis.com'))

@app.route("/")
def home():
   return render_template("index.html")

@app.route("/invest")
def invest():
   return render_template("invest.html")

@app.route("/sign-up", methods=['GET', 'POST'])
def signup():
   if request.method == "POST":
      data = request.json
      first_name = data.get('first_name')
      last_name = data.get('last_name')
      email = data.get('email')
      password = data.get('password')
      wallet_address = data.get('wallet_address')
      signature = data.get("signature")

      nonce = session.get('nonce')
      message = f"Sign this message to verify your wallet ownership with OpenFund. Nonce: {nonce}"
      message_hash = encode_defunct(text=message)
      
      recovered_address = eth_account.Account.recover_message(message_hash, signature=signature)
      if recovered_address.lower() == wallet_address.lower():
         print("=== NEW USER SIGNUP ===")
         print(f"Name: {first_name} {last_name}")
         print(f"Email: {email}")
         print(f"Password: {password}")
         print(f"Wallet Address: {wallet_address}")
         print("======================")
            
         return jsonify({"success": True, "message": "Account created successfully"})
      else:
         return jsonify({"success": False, "message": f"{nonce}"})
   else:
      nonce = secrets.token_hex(16)
      session['nonce'] = nonce
      return render_template("signup.html", nonce=nonce)

@app.route("/login")
def login():
   return render_template("login.html")

@app.route("/test")
def test():
    return render_template("test.html")

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5555)