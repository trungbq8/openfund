from flask import Flask, render_template, jsonify, request, session, url_for, redirect
from web3 import Web3
import eth_account
from eth_account.messages import encode_defunct
import os
import secrets
import time
from flask_cors import CORS
import re
from werkzeug.utils import secure_filename
import psycopg2
from dotenv import load_dotenv
import hashlib

app = Flask(__name__)
CORS(app)
app.secret_key = "secretkey"

app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

load_dotenv(dotenv_path="config.env")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_db_connection():
   return psycopg2.connect(
   dbname=DB_NAME,
   user=DB_USER,
   password=DB_PASSWORD,
   host=DB_HOST,
   port=DB_PORT
   )

w3 = Web3(Web3.HTTPProvider('https://evm-rpc-arctic-1.sei-apis.com'))

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route("/upload-image", methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        unique_filename = f"{timestamp}_{filename}"
        
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        file_url = url_for('static', filename=f'uploads/{unique_filename}', _external=True)
        
        return jsonify({
            "success": True, 
            "message": "File uploaded successfully",
            "file_url": file_url
        })
    else:
        return jsonify({
            "success": False, 
            "message": f"File type not allowed"
        }), 400

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
   if 'raiser_id' in session:
      return redirect("/")
   
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
      
      if len(first_name) > 15 or len(last_name) > 15:
         return jsonify({"success": False, "message": "First name and last name must be at 15 characters maximum!"}), 400
       
      if not validate_email(email):
         return jsonify({"success": False, "message": "Invalid email format!"}), 400

      if not validate_password(password):
         return jsonify({"success": False, "message": "Password must be at least 8 characters long and include a special character!"}), 400

      nonce = session.get('nonce')
      message = f"Sign this message to verify your wallet ownership with OpenFund. Nonce: {nonce}"
      message_hash = encode_defunct(text=message)
      
      recovered_address = eth_account.Account.recover_message(message_hash, signature=signature)
      if recovered_address.lower() == wallet_address.lower():
         salt = secrets.token_bytes(20)
         combined_pw = f"{salt}{password}"
         hashed_password = hashlib.sha256(combined_pw.encode('utf-8')).hexdigest()

         try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO raiser (first_name, last_name, email, hashed_password, salt, wallet_address)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (first_name, last_name, email, hashed_password, str(salt), recovered_address.lower())
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Account created successfully!"}), 201

         except psycopg2.Error as e:
            print(e)
            return jsonify({"success": False, "message": "Email already in use!"}), 500
      else:
         return jsonify({"success": False, "message": "Signature not valid"})
   else:
      nonce = secrets.token_hex(16)
      session['nonce'] = nonce
      return render_template("signup.html", nonce=nonce)

@app.route("/")
def home():
   return render_template("index.html")

@app.route("/invest")
def invest():
   return render_template("invest.html")

@app.route("/log-in", methods=['GET', 'POST'])
def login():
   if 'raiser_id' in session:
      return redirect("/")
   
   if request.method == "POST":
      data = request.json
      email = data.get('email')
      password = data.get('password')

      if not email or not password:
         return jsonify({"success": False, "message": "Email and Password are required!"}), 400

      try:
         conn = get_db_connection()
         cur = conn.cursor()

         cur.execute("SELECT id, hashed_password, salt FROM raiser WHERE email = %s", (email,))
         user = cur.fetchone()

         cur.close()
         conn.close()

         if user:
            user_id, stored_password_hash, salt = user
            combined_pw = f"{salt}{password}"
            hashed_password = hashlib.sha256(combined_pw.encode('utf-8')).hexdigest()
            
            if stored_password_hash == hashed_password:
               session['raiser_id'] = user_id
               return jsonify({"success": True, "message": "Login successful!"}), 200
            else:
               return jsonify({"success": False, "message": "Invalid password!"}), 400
         else:
               return jsonify({"success": False, "message": "Account not found!"}), 404
         
      except psycopg2.Error as e:
         return jsonify({"success": False, "message": "An error occurs"}), 500
   else:
      return render_template("login.html")

@app.route("/edit-account", methods=['GET', 'POST'])
def edit_account():
   if 'raiser_id' not in session:
      return redirect(url_for('login'))
   
   if request.method == "POST":
      data = request.json
      first_name = data.get('first_name')
      last_name = data.get('last_name')
      email = data.get('email')
      x_link = data.get('x_link')
      website_link = data.get('website_link')
      bio_content = data.get('bio_content')
      current_password = data.get('current_password')
      new_password = data.get('new_password')
      wallet_address = data.get('wallet_address')
      user_image_url = data.get('user_image_url')
      
      try:
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT email, last_name, hashed_password, salt, wallet_address FROM raiser 
               WHERE id = %s
         """, (session['raiser_id'],))
         
         user_data = cur.fetchone()
         
         current_email, current_last_name, stored_password_hash, salt, current_wallet = user_data
         
         # Check if email is being changed, and if it's already in use by another account
         if email and email != current_email:
               if not validate_email(email):
                  return jsonify({"success": False, "message": "Invalid email format"}), 400
               
               cur.execute("SELECT id FROM raiser WHERE email = %s AND id != %s", (email, session['raiser_id']))
               if cur.fetchone():
                  cur.close()
                  conn.close()
                  return jsonify({"success": False, "message": "Email already in use"}), 400
         
         # Validate names if provided
         if len(first_name) > 15 or len(first_name) == 0:
            return jsonify({"success": False, "message": "First name must be not null and 15 characters maximum"}), 400
         
         if last_name and len(last_name) > 15:
            return jsonify({"success": False, "message": "Last name must be 15 characters maximum"}), 400
         
         # Handle password change if requested
         if current_password and new_password:
               # Verify current password
               combined_pw = f"{salt}{current_password}"
               hashed_current_password = hashlib.sha256(combined_pw.encode('utf-8')).hexdigest()
               
               if hashed_current_password != stored_password_hash:
                  cur.close()
                  conn.close()
                  return jsonify({"success": False, "message": "Current password is incorrect"}), 400
               
               # Validate new password
               if not validate_password(new_password):
                  cur.close()
                  conn.close()
                  return jsonify({"success": False, "message": "New password must be at least 8 characters long and include a special character"}), 400
               
               # Generate new password hash
               new_salt = secrets.token_bytes(20)
               combined_new_pw = f"{new_salt}{new_password}"
               hashed_new_password = hashlib.sha256(combined_new_pw.encode('utf-8')).hexdigest()
               
               # Update password
               cur.execute("""
                  UPDATE raiser SET hashed_password = %s, salt = %s WHERE id = %s
               """, (hashed_new_password, str(new_salt), session['raiser_id']))
         
         # Update user information
         update_fields = []
         params = []
         
         if first_name:
               update_fields.append("first_name = %s")
               params.append(first_name)
         
         if current_last_name != last_name:
               update_fields.append("last_name = %s")
               params.append(last_name)
         
         if email and email != current_email:
               update_fields.append("email = %s")
               params.append(email)
         
         if x_link is not None:  # Allow empty string to clear the field
               update_fields.append("x_link = %s")
               params.append(x_link)
         
         if website_link is not None:  # Allow empty string to clear the field
               update_fields.append("website_link = %s")
               params.append(website_link)
         
         if bio_content is not None:  # Allow empty string to clear the field
               update_fields.append("bio = %s")
               params.append(bio_content)
         
         if wallet_address and wallet_address.lower() != current_wallet:
               update_fields.append("wallet_address = %s")
               params.append(wallet_address.lower())
         if user_image_url:
               update_fields.append("logo_url = %s")
               params.append(user_image_url.lower())

         if update_fields:
               query = "UPDATE raiser SET " + ", ".join(update_fields) + " WHERE id = %s"
               params.append(session['raiser_id'])
               cur.execute(query, params)
         
         conn.commit()
         cur.close()
         conn.close()
         
         return jsonify({"success": True, "message": "Account updated successfully"}), 200
         
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return jsonify({"success": False, "message": "An error occurred while updating your account"}), 500
   else:
      try:
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT first_name, last_name, email, x_link, website_link, bio, wallet_address, email_confirmed, logo_url 
               FROM raiser WHERE id = %s
         """, (session['raiser_id'],))
         
         user_data = cur.fetchone()
         cur.close()
         conn.close()
         
         if not user_data:
               return redirect(url_for('login'))
         
         first_name, last_name, email, x_link, website_link, bio, wallet_address, email_verified, logo_url = user_data
         
         return render_template(
               "edit-account.html",
               user_data={
                  "first_name": first_name,
                  "last_name": last_name,
                  "email": email,
                  "x_link": x_link or "",
                  "website_link": website_link or "",
                  "bio": bio or "",
                  "wallet_address": wallet_address,
                  "email_verified": email_verified,
                  "logo_url": logo_url
               }
         )
         
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('login'))

@app.route("/send-verification-email", methods=['POST'])
def send_verification_email():
   if 'raiser_id' not in session:
      return jsonify({"success": False, "message": "Not logged in"}), 401
   
   try:
      conn = get_db_connection()
      cur = conn.cursor()
      
      # Get user email
      cur.execute("SELECT email, email_confirmed FROM raiser WHERE id = %s", (session['raiser_id'],))
      result = cur.fetchone()
      
      if not result:
         cur.close()
         conn.close()
         return jsonify({"success": False, "message": "User not found"}), 404
      
      email, email_verified = result
      
      if email_verified:
         cur.close()
         conn.close()
         return jsonify({"success": False, "message": "Email already verified"}), 400
      
      cur.close()
      conn.close()
      
      return jsonify({
         "success": True, 
         "message": "Verification email sent. Please check your inbox.",
      }), 200
      
   except psycopg2.Error as e:
      print(f"Database error: {e}")
      return jsonify({"success": False, "message": "An error occurred"}), 500

@app.route('/log-out')
def logout():
    session.pop('raiser_id', None)
    return redirect(url_for('login'))

@app.route("/test")
def test():
    return render_template("test.html")

if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5555)