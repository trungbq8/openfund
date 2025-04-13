from flask import Flask, render_template, jsonify, request, session
from web3 import Web3
import eth_account
from eth_account.messages import encode_defunct
import os
import secrets
import time
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)
app.secret_key = "secretkey"

w3 = Web3(Web3.HTTPProvider('https://evm-rpc-arctic-1.sei-apis.com'))

@app.route("/")
def home():
   return render_template("index.html")

@app.route("/invest")
def invest():
   return render_template("invest.html")

def validate_email(email):
    """Validate email format"""
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def validate_password(password):
    """Check if the password has at least 8 characters and includes a special character"""
    if len(password) < 8:
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

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

      if not first_name or not last_name or not email or not password or not wallet_address:
         return jsonify({"success": False, "message": "All fields are required!"}), 400

      if not validate_email(email):
         return jsonify({"success": False, "message": "Invalid email format!"}), 400

      if not validate_password(password):
         return jsonify({"success": False, "message": "Password must be at least 8 characters long and include a special character!"}), 400

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
         return jsonify({"success": False, "message": "Signature not valid"})
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