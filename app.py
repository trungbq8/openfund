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
import random
from unidecode import unidecode

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
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def validate_password(password):
    """Check if the password has at least 8 characters and includes a special character"""
    if len(password) < 8:
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def validate_username(username):
    return re.fullmatch(r'^[a-zA-Z0-9_.]+$', username) is not None

def validate_name(name):
   return re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ'\- ]+", name) is not None

def capitalize_name(name):
    return ' '.join(word.capitalize() for word in name.strip().split())

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

      if not first_name or not email or not password or not wallet_address:
         return jsonify({"success": False, "message": "All fields are required!"}), 400
      
      if len(first_name) > 15 or len(last_name) > 15:
         return jsonify({"success": False, "message": "First name and last name must be at 15 characters maximum!"}), 400
       
      if not validate_email(email):
         return jsonify({"success": False, "message": "Invalid email format!"}), 400
      
      if not validate_name(first_name):
         return jsonify({"success": False, "message": "Invalid first name!"}), 400
      
      if last_name and not validate_name(last_name):
         return jsonify({"success": False, "message": "Invalid last name!"}), 400

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
            first = unidecode(first_name).lower().replace(' ', '')
            last = unidecode(last_name).lower().replace(' ', '')
            base_username = f"{first}.{last}"           
            while True:
               random_suffix = random.randint(10000, 99999)
               username = f"{base_username}{random_suffix}"

               cur.execute("SELECT id FROM raiser WHERE username = %s", (username,))
               if not cur.fetchone():
                  break
                
            cur.execute(
                """
                INSERT INTO raiser (username, first_name, last_name, email, hashed_password, salt, wallet_address)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (username, capitalize_name(first_name), capitalize_name(last_name), email, hashed_password, str(salt), recovered_address.lower())
            )
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Account created successfully!"}), 201

         except psycopg2.Error as e:
            print(e)
            return jsonify({"success": False, "message": "Email or wallet address already in use!"}), 500
      else:
         return jsonify({"success": False, "message": "Signature not valid"})
   else:
      nonce = secrets.token_hex(16)
      session['nonce'] = nonce
      return render_template("signup.html", nonce=nonce)

@app.route("/")
def home():
   nonce = secrets.token_hex(16)
   session['nonce'] = nonce
   if 'investor_wallet_address' in session:
      investor_connected = True
      investor_wallet_address = session.get('investor_wallet_address')
   else:
      investor_connected = False
      investor_wallet_address = ""

   if 'raiser_id' in session:
      raiser_logged_in = True
      raiser_id = session.get('raiser_id')
   else:
      raiser_logged_in = False
      raiser_id = ""
   return render_template("index.html", nonce=nonce, investor_connected=investor_connected, investor_wallet_address=investor_wallet_address, raiser_logged_in=raiser_logged_in, raiser_id = raiser_id)

@app.route("/invest")
def invest():
   nonce = secrets.token_hex(16)
   session['nonce'] = nonce
   if 'investor_wallet_address' in session:
      investor_connected = True
      investor_wallet_address = session.get('investor_wallet_address')
   else:
      investor_connected = False
      investor_wallet_address = ""

   if 'raiser_id' in session:
      raiser_logged_in = True
      raiser_id = session.get('raiser_id')
   else:
      raiser_logged_in = False
      raiser_id = ""
   return render_template("invest.html", nonce=nonce, investor_connected=investor_connected, investor_wallet_address=investor_wallet_address, raiser_logged_in=raiser_logged_in, raiser_id = raiser_id)

@app.route("/api/get-projects")
def get_projects():
   investor_wallet_address = session.get('investor_wallet_address')
   page = request.args.get('page', 1, type=int)
   per_page = request.args.get('per_page', 5, type=int)
   project_type = request.args.get('type', "active", type=str)  # active, completed, invested
   offset = (page - 1) * per_page
   
   if project_type == 'invested' and not investor_wallet_address:
      return jsonify({"success": False, "message": "Investor not connected"}), 401
   
   try:
      conn = get_db_connection()
      cur = conn.cursor()
      
      projects = []
      total_count = 0
      
      if project_type == 'invested':
         cur.execute("""
            SELECT COUNT(DISTINCT p.id) 
            FROM project p
            JOIN investment i ON p.id = i.project_id
            WHERE i.investor_address = %s
         """, (investor_wallet_address,))
         total_count = cur.fetchone()[0]
         
         cur.execute("""
            SELECT DISTINCT p.id, p.name, p.funding_status, 
                   p.fund_raised, p.investment_end_time,
                   CONCAT(r.first_name, ' ', r.last_name) AS raiser_name, 
                   p.created_time
            FROM project p
            JOIN investment i ON p.id = i.project_id
            JOIN raiser r ON p.raiser_id = r.id
            WHERE i.investor_address = %s
            ORDER BY p.created_time DESC
            LIMIT %s OFFSET %s
         """, (investor_wallet_address, per_page, offset))
      
      elif project_type == 'active':
         cur.execute("""
               SELECT COUNT(*) FROM project 
               WHERE funding_status IN ('raising', 'voting')
               AND listing_status = 'accepted'
               AND hidden = FALSE
            """)
         total_count = cur.fetchone()[0]
         
         cur.execute("""
            SELECT p.id, p.name, p.funding_status, 
                  p.fund_raised, p.investment_end_time,
                  CONCAT(r.first_name, ' ', r.last_name) AS raiser_name
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.funding_status IN ('raising', 'voting')
            AND p.listing_status = 'accepted'
            AND p.hidden = FALSE
            ORDER BY p.created_time DESC
            LIMIT %s OFFSET %s
         """, (per_page, offset))
      
      elif project_type == 'completed':
         cur.execute("""
               SELECT COUNT(*) FROM project 
               WHERE funding_status = 'completed'
               AND listing_status = 'accepted'
               AND hidden = FALSE
            """)
         total_count = cur.fetchone()[0]
         
         cur.execute("""
            SELECT p.id, p.name, p.funding_status, 
                  p.fund_raised, p.investment_end_time,
                  CONCAT(r.first_name, ' ', r.last_name) AS raiser_name
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.funding_status = 'completed'
            AND p.listing_status = 'accepted'
            AND p.hidden = FALSE
            ORDER BY p.created_time DESC
            LIMIT %s OFFSET %s
         """, (per_page, offset))
      else:
         return jsonify({"success": False, "message": "Invalid project type"}), 400
      
      for row in cur.fetchall():
         project_data = {
            "id": row[0],
            "name": row[1],
            "funding_status": row[2],
            "fund_raised": row[3],
            "investment_end_time": row[4],
            "raiser_name": row[5]
         }
         
         projects.append(project_data)
      
      total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0
      
      cur.close()
      conn.close()
      
      return jsonify({
         "success": True,
         "projects": projects,
         "pagination": {
            "total_count": total_count,
            "total_pages": total_pages,
            "current_page": page,
            "per_page": per_page
         }
      })
      
   except psycopg2.Error as e:
      print(f"Database error: {e}")
      return jsonify({"success": False, "message": "Database error"}), 500
   
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
      username = data.get('username')
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
      signature = data.get("signature")
      
      try:
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT email, username, last_name, hashed_password, salt, wallet_address FROM raiser 
               WHERE id = %s
         """, (session['raiser_id'],))
         
         user_data = cur.fetchone()
         
         current_email, current_username, current_last_name, stored_password_hash, salt, current_wallet = user_data
         
         if wallet_address and wallet_address != current_wallet:
            cur.execute("SELECT id FROM raiser WHERE wallet_address = %s AND id != %s", (wallet_address, session['raiser_id']))
            if cur.fetchone():
               cur.close()
               conn.close()
               return jsonify({"success": False, "message": "Wallet address linked to a different account"}), 400
            
         if email and email != current_email:
            if not validate_email(email):
               return jsonify({"success": False, "message": "Invalid email format"}), 400
            
            cur.execute("SELECT id FROM raiser WHERE email = %s AND id != %s", (email, session['raiser_id']))
            if cur.fetchone():
               cur.close()
               conn.close()
               return jsonify({"success": False, "message": "Email already in use"}), 400
         
         if username and username.lower() != current_username:
            if not validate_username(username):
               return jsonify({"success": False, "message": "Username must not include special characters"}), 400
            
            cur.execute("SELECT id FROM raiser WHERE username = %s AND id != %s", (username, session['raiser_id']))
            if cur.fetchone():
               cur.close()
               conn.close()
               return jsonify({"success": False, "message": "Username already in use"}), 400
         
         if len(username) > 50 or len(username) < 6:
            return jsonify({"success": False, "message": "Username must not be from 10-50 characters"}), 400
         
         if first_name and validate_name(first_name) == False:
            return jsonify({"success": False, "message": "Invalid first name!"}), 400
         
         if last_name and validate_name(last_name) == False:
            return jsonify({"success": False, "message": "Invalid last name!"}), 400
         
         if len(first_name) > 15:
            return jsonify({"success": False, "message": "First name must be 15 characters maximum"}), 400
         
         if len(first_name) == 0:
            return jsonify({"success": False, "message": "First name must not be null"}), 400
         
         if last_name and len(last_name) > 15:
            return jsonify({"success": False, "message": "Last name must be 15 characters maximum"}), 400
         
         if x_link and (not x_link.startswith("https://x.com/") or "." not in x_link or len(x_link) > 100):
            return jsonify({"success": False, "message": "Please provide a valid X url"}), 400

         if website_link and (not website_link.startswith("https://") or "." not in website_link or len(website_link) > 100):
            return jsonify({"success": False, "message": "Please provide a valid website url"}), 400
                  
         if current_password and new_password:
               combined_pw = f"{salt}{current_password}"
               hashed_current_password = hashlib.sha256(combined_pw.encode('utf-8')).hexdigest()
               
               if hashed_current_password != stored_password_hash:
                  cur.close()
                  conn.close()
                  return jsonify({"success": False, "message": "Current password is incorrect"}), 400
               
               if not validate_password(new_password):
                  cur.close()
                  conn.close()
                  return jsonify({"success": False, "message": "New password must be at least 8 characters long and include a special character"}), 400
               
               new_salt = secrets.token_bytes(20)
               combined_new_pw = f"{new_salt}{new_password}"
               hashed_new_password = hashlib.sha256(combined_new_pw.encode('utf-8')).hexdigest()
               
               cur.execute("""
                  UPDATE raiser SET hashed_password = %s, salt = %s WHERE id = %s
               """, (hashed_new_password, str(new_salt), session['raiser_id']))
         
         update_fields = []
         params = []
         
         if first_name:
            update_fields.append("first_name = %s")
            params.append(capitalize_name(first_name))
         
         if current_last_name != last_name:
            update_fields.append("last_name = %s")
            params.append(capitalize_name(last_name))
         
         if email and email != current_email:
            update_fields.append("email = %s")
            params.append(email)
         
         if x_link is not None:
            update_fields.append("x_link = %s")
            params.append(x_link)
         
         if website_link is not None:
            update_fields.append("website_link = %s")
            params.append(website_link)
         
         if bio_content is not None:
            update_fields.append("bio = %s")
            params.append(bio_content)
         
         if wallet_address and wallet_address.lower() != current_wallet:
            nonce = session.get('nonce')
            message = f"Sign this message to verify your wallet ownership with OpenFund. Nonce: {nonce}"
            message_hash = encode_defunct(text=message)
            
            recovered_address = eth_account.Account.recover_message(message_hash, signature=signature)
            if recovered_address.lower() == wallet_address.lower():
               update_fields.append("wallet_address = %s")
               params.append(wallet_address.lower())
            else:
               return jsonify({"success": False, "message": "Connect signature not valid"})
               
         if user_image_url:
            update_fields.append("logo_url = %s")
            params.append(user_image_url.lower())

         if username and username != current_username:
            update_fields.append("username = %s")
            params.append(username.lower())

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
         nonce = secrets.token_hex(16)
         session['nonce'] = nonce
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT first_name, last_name, username, email, x_link, website_link, bio, wallet_address, email_confirmed, logo_url 
               FROM raiser WHERE id = %s
         """, (session['raiser_id'],))
         
         user_data = cur.fetchone()
         cur.close()
         conn.close()
         
         if not user_data:
               return redirect(url_for('login'))
         
         first_name, last_name, username, email, x_link, website_link, bio, wallet_address, email_verified, logo_url = user_data
         
         return render_template(
               "edit-account.html",
               user_data={
                  "first_name": first_name,
                  "last_name": last_name,
                  "username": username,
                  "email": email,
                  "x_link": x_link or "",
                  "website_link": website_link or "",
                  "bio": bio or "",
                  "wallet_address": wallet_address,
                  "email_verified": email_verified,
                  "logo_url": logo_url
               },
               nonce=nonce,
               raiser_id = session.get('raiser_id')
         )
         
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('login'))

@app.route("/send-verification-email", methods=['POST'])
def send_verification_email():
   if 'raiser_id' not in session:
      return jsonify({"success": False, "message": "Not logged in"}), 401
   data = request.json
   email = data.get("email")
   try:
      conn = get_db_connection()
      cur = conn.cursor()
      
      cur.execute("SELECT id FROM raiser WHERE email = %s AND id != %s", (email, session['raiser_id']))
      if cur.fetchone():
         cur.close()
         conn.close()
         return jsonify({"success": False, "message": "Email already in use"}), 400
      
      cur.execute("SELECT email_confirmed FROM raiser WHERE email = %s AND id = %s", (email, session['raiser_id']))
      result = cur.fetchone()
      if result:
         email_verified = result[0]
         print(email_verified)
      else:
         email_verified = False
      
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

@app.route('/investor-connect', methods=["POST"])
def investor_connect():
   data = request.json
   wallet_address = data.get('wallet_address')
   signature = data.get("signature")
   nonce = session.get('nonce')
   message = f"Sign this message to verify your wallet ownership with OpenFund. Nonce: {nonce}"
   message_hash = encode_defunct(text=message)
   
   recovered_address = eth_account.Account.recover_message(message_hash, signature=signature)
   if recovered_address.lower() == wallet_address.lower():
      session['investor_wallet_address'] = wallet_address.lower()
      try:
         conn = get_db_connection()
         cur = conn.cursor()

         cur.execute("SELECT id FROM investor WHERE wallet_address = %s", (session['investor_wallet_address'],))
         exist = cur.fetchone()
         if not exist:
            cur.execute("INSERT INTO investor(wallet_address) VALUES (%s)", (session['investor_wallet_address'],))
            conn.commit()
            cur.close()
            conn.close()
         return jsonify({"success": True, "message": "Connect wallet successfully!"}), 200
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('home'))
   return jsonify({"success": False, "message": "Signature not valid"}), 500

@app.route('/log-out')
def logout():
    session.pop('raiser_id', None)
    return redirect(url_for('login'))

@app.route('/raiser-profile/<raiser_id_param>')
def profile(raiser_id_param):
   if not raiser_id_param:
      return redirect(url_for('home'))
   
   nonce = secrets.token_hex(16)
   session['nonce'] = nonce
   if 'investor_wallet_address' in session:
      investor_connected = True
      investor_wallet_address = session.get('investor_wallet_address')
   else:
      investor_connected = False
      investor_wallet_address = ""

   if 'raiser_id' in session:
      raiser_logged_in = True
      raiser_id = session.get('raiser_id')
   else:
      raiser_logged_in = False
      raiser_id = ""
   try:
      conn = get_db_connection()
      cur = conn.cursor()
      
      if '-' not in raiser_id_param:
         cur.execute("SELECT id FROM raiser WHERE username = %s", (raiser_id_param,))
         user_data = cur.fetchone()
         if not user_data:
            cur.close()
            conn.close()
            return redirect(url_for('not_found'))
         raiser_id_param = user_data[0]
      else:
         cur.execute("SELECT username FROM raiser WHERE id = %s", (raiser_id_param,))
         user_data = cur.fetchone()
         if not user_data:
            cur.close()
            conn.close()
            return redirect(url_for('not_found'))
         return redirect(f'/raiser-profile/{user_data[0]}')
      
      cur.execute("""
            SELECT first_name, last_name, email, x_link, website_link, bio, wallet_address, logo_url 
            FROM raiser 
            WHERE id = %s
            """, (raiser_id_param,))
      user_data = cur.fetchone()
      
      first_name, last_name, email, x_link, website_link, bio, wallet_address, logo_url = user_data

      cur.execute("""
         SELECT COUNT(*) FROM project 
         WHERE raiser_id = %s AND listing_status = 'accepted'
      """, (raiser_id_param,))
      number_projects = cur.fetchone()[0]

      cur.close()
      conn.close()
      
      return render_template(
         "raiser-profile.html",
         user_data={
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "x_link": x_link or "",
            "website_link": website_link or "",
            "bio": bio or "",
            "wallet_address": wallet_address,
            "logo_url": logo_url,
            "number_projects": number_projects
         },
         nonce=nonce, 
         investor_connected=investor_connected, 
         investor_wallet_address=investor_wallet_address, 
         raiser_logged_in=raiser_logged_in,
         raiser_id = raiser_id
      )
   
   except psycopg2.Error as e:
      print(f"Database error: {e}")
      return redirect(url_for('home'))

@app.route('/disconnect')
def disconnect():
    session.pop('investor_wallet_address', None)
    return redirect(request.referrer)

@app.errorhandler(404)
@app.route("/not-found")
def not_found(e=None):
    return render_template("404.html")

@app.route("/project")
def project():
    return render_template("project.html")

def validate_project_submit(token_decimal, project_name, project_end_time, project_x_link, project_website_link, project_telegram_link, project_whitepaper_link, token_name, symbol, token_logo_url, token_total_supply, token_amount_to_sell, token_price, token_contract_address, project_description):
   if not project_name or not project_end_time or not project_x_link or not project_website_link or not project_telegram_link or not project_whitepaper_link or not token_name or not symbol or not token_logo_url or not token_total_supply or not token_amount_to_sell or not token_price or not token_contract_address or not project_description:
         return jsonify({"success": False, "message": "All fields are required!"}), 400
   if len(project_name) > 50:
      return jsonify({"success": False, "message": "Project name must be at 50 characters maximum!"}), 400
   if len(token_name) > 50:
      return jsonify({"success": False, "message": "Token name must be at 50 characters maximum!"}), 400
   if len(symbol) > 10:
      return jsonify({"success": False, "message": "Token must be at 10 characters maximum!"}), 400
   if (not project_x_link.startswith("https://x.com/") or "." not in project_x_link or len(project_x_link) > 100):
         return jsonify({"success": False, "message": "Please provide a valid X url"}), 400
   if (not project_website_link.startswith("https://") or "." not in project_website_link or len(project_website_link) > 100):
      return jsonify({"success": False, "message": "Please provide a valid website url"}), 400
   if (not project_telegram_link.startswith("https://t.me/") or "." not in project_telegram_link or len(project_telegram_link) > 100):
      return jsonify({"success": False, "message": "Please provide a valid telegram url"}), 400
   if (not project_whitepaper_link.startswith("https://") or "." not in project_whitepaper_link or len(project_whitepaper_link) > 100):
      return jsonify({"success": False, "message": "Please provide a valid whitepaper url"}), 400
   if int(token_total_supply) < 10:
      return jsonify({"success": False, "message": "Invalid token total supply"}), 400
   if int(token_decimal) < 1:
      return jsonify({"success": False, "message": "Invalid token decimal"}), 400
   if int(token_amount_to_sell) < 10 or int(token_amount_to_sell) > int(token_total_supply):
      return jsonify({"success": False, "message": "Invalid token amount to sell"}), 400
   if float(token_price) not in [0.1, 0.01, 0.001, 0.0001, 0.00001, 0.000001, 0.5, 1, 5, 10, 0.05, 0.005, 0.0005, 0.00005, 0.000005]:
      return jsonify({"success": False, "message": "Invalid token price. Must be a common fractional value in (10, 5, 1, 0.5, 0.1, 0.05, 0.01, ... , 0.000001"}), 400
   if not w3.is_address(token_contract_address):
      return jsonify({"success": False, "message": "Invalid token contract address."}), 400
   now = int(time.time())
   if not isinstance(project_end_time, (int, float)) or project_end_time < now + 3 * 24 * 3600:
      return jsonify({"success": False, "message": "End time must be at least 3 days from now."}), 400
   
@app.route("/new-project", methods=["GET", "POST"])
def new_project():
   if 'raiser_id' not in session:
      return redirect(url_for('login'))
   if request.method == "POST":
      data = request.json
      project_name = data.get("project_name")
      project_end_time =  data.get("project_end_time")
      project_x_link =  data.get("project_x_link")
      project_website_link =  data.get("project_website_link")
      project_telegram_link =  data.get("project_telegram_link")
      project_whitepaper_link =  data.get("project_whitepaper_link")
      token_name =  data.get("token_name")
      symbol =  data.get("symbol")
      token_logo_url =  data.get("token_logo_url")
      token_decimal = data.get("token_decimal")
      token_total_supply =  data.get("token_total_supply")
      token_amount_to_sell =  data.get("token_amount_to_sell")
      token_price =  data.get("token_price")
      token_contract_address =  data.get("token_contract_address")
      project_description =  data.get("project_description")

      validate_project_submit(token_decimal, project_name, project_end_time, project_x_link, project_website_link, project_telegram_link, project_whitepaper_link, token_name, symbol, token_logo_url, token_total_supply, token_amount_to_sell, token_price, token_contract_address, project_description)
      
      try:
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT wallet_address FROM raiser 
               WHERE id = %s
         """, (session['raiser_id'],))
         
         user_data = cur.fetchone()
         funding_wallet = user_data[0]

         cur.execute(
            """
            INSERT INTO project (raiser_id, funding_address, name, logo_url, investment_end_time, token_name, token_symbol, total_token_supply, token_to_sell, token_price, token_address, fund_raised, token_sold, decimal, vote_for_refund, vote_for_refund_count, investors_count, x_link, website_link, telegram_link, whitepaper_link, description, platform_comment)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (session['raiser_id'], funding_wallet, project_name, token_logo_url, project_end_time, token_name ,symbol.upper(), token_total_supply, token_amount_to_sell, token_price, token_contract_address, '0', '0', token_decimal, '0', '0', '0', project_x_link, project_website_link, project_telegram_link, project_whitepaper_link, project_description, "Reviewing")
         )
         conn.commit()
         cur.close()
         conn.close()
         return jsonify({"success": True, "message": "Submit project successfully!"}), 201
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return jsonify({"success": False, "message": "An error occurred while updating your account"}), 500
   else:
      return render_template("new-project.html")

@app.route("/edit-project/<project_id_param>", methods=["GET", "POST"])
def edit_project(project_id_param):
   if 'raiser_id' not in session:
      return redirect(url_for('login'))
   if request.method == "POST":
      data = request.json
      remove_project = data.get("remove")
      project_name = data.get("project_name")
      project_end_time =  data.get("project_end_time")
      project_x_link =  data.get("project_x_link")
      project_website_link =  data.get("project_website_link")
      project_telegram_link =  data.get("project_telegram_link")
      project_whitepaper_link =  data.get("project_whitepaper_link")
      token_name =  data.get("token_name")
      symbol =  data.get("symbol")
      token_logo_url =  data.get("token_logo_url")
      token_decimal = data.get("token_decimal")
      token_total_supply =  data.get("token_total_supply")
      token_amount_to_sell =  data.get("token_amount_to_sell")
      token_price =  data.get("token_price")
      token_contract_address =  data.get("token_contract_address")
      project_description =  data.get("project_description")

      validate_project_submit(token_decimal, project_name, project_end_time, project_x_link, project_website_link, project_telegram_link, project_whitepaper_link, token_name, symbol, token_logo_url, token_total_supply, token_amount_to_sell, token_price, token_contract_address, project_description)
      
      try:
         conn = get_db_connection()
         cur = conn.cursor()

         cur.execute("SELECT id FROM project WHERE id = %s", (project_id_param,))
         project_data = cur.fetchone()
         if not project_data:
            cur.close()
            conn.close()
            return redirect(url_for('not_found'))
         if remove_project == True:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("DELETE FROM project WHERE id = %s", (project_id_param,))

            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Project delete successfully!"}), 201
      
         cur.execute(
            """
            UPDATE project 
            SET name = %s, logo_url = %s, investment_end_time = %s, token_name = %s, token_symbol = %s, total_token_supply = %s, token_to_sell = %s, token_price = %s, token_address = %s, decimal = %s, x_link = %s, website_link = %s, telegram_link = %s, whitepaper_link = %s, description = %s
            WHERE id = %s
            """,
            (project_name, token_logo_url, project_end_time, token_name ,symbol.upper(), token_total_supply, token_amount_to_sell, token_price, token_contract_address, token_decimal, project_x_link, project_website_link, project_telegram_link, project_whitepaper_link, project_description, project_id_param)
         )
         conn.commit()
         cur.close()
         conn.close()
         return jsonify({"success": True, "message": "Edit project successfully!"}), 201
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return jsonify({"success": False, "message": "An error occurred while updating your project"}), 500
   else:
      try:
         conn = get_db_connection()
         cur = conn.cursor()
         
         cur.execute("""
               SELECT name, logo_url, investment_end_time, token_name, token_symbol, total_token_supply, token_to_sell, token_price, token_address, decimal, x_link, website_link, telegram_link, whitepaper_link, description
               FROM project WHERE id = %s
         """, (project_id_param,))
         
         project_data = cur.fetchone()
         cur.close()
         conn.close()
         
         if not project_data:
               return redirect(url_for('not_found'))
         
         name, logo_url, investment_end_time, token_name, token_symbol, total_token_supply, token_to_sell, token_price, token_address, decimal, x_link, website_link, telegram_link, whitepaper_link, description = project_data
         
         return render_template(
               "edit-project.html",
               project_data={
                  "name" : name, 
                  "logo_url" : logo_url, 
                  "investment_end_time" : investment_end_time, 
                  "token_name" : token_name, 
                  "token_symbol" : token_symbol, 
                  "total_token_supply" : total_token_supply, 
                  "token_to_sell" : token_to_sell, 
                  "token_price" : token_price, 
                  "token_address" : token_address, 
                  "decimal" : decimal, 
                  "x_link" : x_link, 
                  "website_link" : website_link, 
                  "telegram_link" : telegram_link, 
                  "whitepaper_link" : whitepaper_link, 
                  "description" : description
               },
         )
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('home'))
      
@app.route("/submitted-project")
def submitted_project():
   if 'raiser_id' not in session:
      return redirect(url_for('login'))
   return render_template("submitted-projects.html")

@app.route("/api/submitted-projects")
def api_submitted_projects():
   if 'raiser_id' not in session:
      return jsonify({"success": False, "message": "Not logged in"}), 401
   
   page = request.args.get('page', 1, type=int)
   per_page = request.args.get('per_page', 5, type=int)
   offset = (page - 1) * per_page
   
   try:
      conn = get_db_connection()
      cur = conn.cursor()
      
      cur.execute("SELECT COUNT(*) FROM project WHERE raiser_id = %s", 
                  (session['raiser_id'],))
      total_count = cur.fetchone()[0]
      total_pages = (total_count + per_page - 1) // per_page
      
      cur.execute("""
         SELECT id, name, listing_status, funding_status, platform_comment, logo_url
         FROM project 
         WHERE raiser_id = %s
         ORDER BY created_time DESC
         LIMIT %s OFFSET %s
      """, (session['raiser_id'], per_page, offset))
      
      projects = []
      for row in cur.fetchall():
         project_id, name, listing_status, funding_status, platform_comment, logo_url = row
         projects.append({
               "id": project_id,
               "name": name,
               "listing_status": listing_status,
               "funding_status": funding_status,
               "platform_comment": platform_comment,
               "logo_url": logo_url
         })
      
      cur.close()
      conn.close()
      
      return jsonify({
         "success": True,
         "projects": projects,
         "pagination": {
               "total_count": total_count,
               "total_pages": total_pages,
               "current_page": page,
               "per_page": per_page
         }
      })
      
   except psycopg2.Error as e:
      print(f"Database error: {e}")
      return jsonify({"success": False, "message": "Database error"}), 500
   
@app.route('/edit-profile', methods=["GET", "POST"])
def edit_profile():
   if 'investor_wallet_address' not in session:
      return redirect(url_for('home'))
   if request.method == 'POST':
      data = request.json
      logo_url = data.get("logo_url")
      username = data.get("username")
      if not validate_username(username):
         return jsonify({"success": False, "message": "Username must not be null or include special characters"}), 400
      if len(username) > 50 or len(username) < 6:
         return jsonify({"success": False, "message": "Username must be from 10-50 characters"}), 400
      if not logo_url:
         logo_url = ""
      try:
         conn = get_db_connection()
         cur = conn.cursor()

         cur.execute("SELECT id FROM investor WHERE username = %s AND wallet_address != %s", (username, session['investor_wallet_address']))
         investor_data = cur.fetchone()
         if investor_data:
            cur.close()
            conn.close()
            return jsonify({"success": False, "message": "Username in use"}), 500
         else:
            cur.execute("UPDATE investor SET username = %s, logo_url = %s WHERE wallet_address = %s", (username, logo_url, session['investor_wallet_address']))
            conn.commit()
            cur.close()
            conn.close()
            return jsonify({"success": True, "message": "Profile update successfully!"}), 201
         
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('home'))
   else:
      try:
         conn = get_db_connection()
         cur = conn.cursor()

         cur.execute("SELECT username, logo_url FROM investor WHERE wallet_address = %s", (session['investor_wallet_address'],))
         investor_data = cur.fetchone()
         if investor_data:
            username, logo_url = investor_data
         else:
            username = ""
            logo_url = ""
         cur.close()
         conn.close()
         return render_template("edit-profile.html", user_data={"logo_url": logo_url, "username": username})
      
      except psycopg2.Error as e:
         print(f"Database error: {e}")
         return redirect(url_for('home'))
      
if __name__ == "__main__":
   app.run(host="0.0.0.0", port=5555)