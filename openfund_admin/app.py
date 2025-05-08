from flask import Flask, render_template, request, session, url_for, redirect, flash
import os
import secrets
from flask_cors import CORS
import psycopg2
from dotenv import load_dotenv
import hashlib
import datetime
from functools import wraps
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
CORS(app)
app.secret_key = "secretkey"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, '..', 'config.env')
load_dotenv(dotenv_path=ENV_PATH)
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

# Authentication helper functions
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    hashed_password = hash_obj.hexdigest()
    return hashed_password, salt

def verify_password(password, hashed_password, salt):
    calculated_hash, _ = hash_password(password, salt)
    return calculated_hash == hashed_password

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Authentication routes
@app.route('/', methods=['GET'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("SELECT * FROM admin WHERE username = %s", (username,))
            admin = cur.fetchone()
            
            if admin and verify_password(password, admin['hashed_password'], admin['salt']):
                # Update last login time
                cur.execute("UPDATE admin SET last_login = CURRENT_TIMESTAMP WHERE id = %s", (admin['id'],))
                conn.commit()
                
                session['admin_id'] = admin['id']
                session['admin_username'] = admin['username']
                
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials. Please try again.', 'danger')
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
        finally:
            cur.close()
            conn.close()
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Dashboard routes
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get total pending projects
        cur.execute("SELECT COUNT(*) as count FROM project WHERE listing_status = 'pending'")
        pending_projects = cur.fetchone()['count']
        
        # Get total projects submitted this week
        cur.execute("""
            SELECT COUNT(*) as count FROM project 
            WHERE created_time >= (CURRENT_TIMESTAMP - INTERVAL '7 days')
        """)
        projects_this_week = cur.fetchone()['count']
        
        # Get total accepted projects
        cur.execute("SELECT COUNT(*) as count FROM project WHERE listing_status = 'accepted'")
        accepted_projects = cur.fetchone()['count']
        
        # Get total funding projects
        cur.execute("""
            SELECT COUNT(*) as count FROM project 
            WHERE listing_status = 'accepted' AND funding_status = 'raising'
        """)
        funding_projects = cur.fetchone()['count']
        
        # Get total raisers
        cur.execute("SELECT COUNT(*) as count FROM raiser")
        total_raisers = cur.fetchone()['count']
        
        # Get total investors
        cur.execute("SELECT COUNT(*) as count FROM investor")
        total_investors = cur.fetchone()['count']
        
        # Calculate platform fee (5% of total fundraised of completed projects in last 30 days)
        cur.execute("""
            SELECT COALESCE(SUM(fund_raised) * 0.05, 0) as platform_fee 
            FROM project 
            WHERE funding_status = 'completed' 
            AND investment_end_time >= extract(epoch from (CURRENT_TIMESTAMP - INTERVAL '30 days')) * 1000
        """)
        platform_fee = cur.fetchone()['platform_fee']
        
        # Get active users in the last 30 days
        cur.execute("""
            SELECT COUNT(DISTINCT investor_address) as active_users
            FROM transaction
            WHERE transaction_time >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
        """)
        active_users = cur.fetchone()['active_users']
        
        # Get total transaction volume in the last 30 days
        cur.execute("""
            SELECT COALESCE(SUM(amount), 0) as volume
            FROM transaction
            WHERE transaction_time >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
        """)
        transaction_volume = cur.fetchone()['volume']
        
        # Get daily transaction volume for the last 30 days
        cur.execute("""
            SELECT 
                DATE_TRUNC('day', transaction_time) as day,
                COALESCE(SUM(amount), 0) as daily_volume
            FROM 
                transaction
            WHERE 
                transaction_time >= (CURRENT_TIMESTAMP - INTERVAL '30 days')
            GROUP BY 
                DATE_TRUNC('day', transaction_time)
            ORDER BY 
                day ASC
        """)
        daily_volumes = cur.fetchall()
        
        # Format for chart data
        chart_labels = [row['day'].strftime('%Y-%m-%d') for row in daily_volumes]
        chart_data = [row['daily_volume'] for row in daily_volumes]
        
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return render_template('dashboard.html', error=str(e))
    finally:
        cur.close()
        conn.close()
        
    return render_template('dashboard.html',
                          pending_projects=pending_projects,
                          projects_this_week=projects_this_week,
                          accepted_projects=accepted_projects,
                          funding_projects=funding_projects,
                          total_raisers=total_raisers,
                          total_investors=total_investors,
                          platform_fee=platform_fee,
                          active_users=active_users,
                          transaction_volume=transaction_volume,
                          chart_labels=chart_labels,
                          chart_data=chart_data)

# Review projects routes
@app.route('/review-projects')
@login_required
def review_projects():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT p.*, r.username as raiser_name
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.listing_status = 'pending'
            ORDER BY p.created_time DESC
        """)
        projects = cur.fetchall()
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        projects = []
    finally:
        cur.close()
        conn.close()
        
    return render_template('review_projects.html', projects=projects)

@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get project details
        cur.execute("""
            SELECT p.*, r.username as raiser_name, r.email as raiser_email
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.id = %s
        """, (project_id,))
        project = cur.fetchone()
        
        if not project:
            flash('Project not found', 'warning')
            return redirect(url_for('dashboard'))
            
        # Get funding metrics if project is accepted
        if project['listing_status'] == 'accepted':
            # Get total investors
            cur.execute("""
                SELECT COUNT(DISTINCT investor_address) as total_investors
                FROM transaction
                WHERE project_id = %s AND type = 'investment'
            """, (project_id,))
            total_investors = cur.fetchone()['total_investors']
            
            # Get total votes for refund
            cur.execute("""
                SELECT COUNT(DISTINCT investor_address) as total_votes
                FROM transaction
                WHERE project_id = %s AND type = 'vote'
            """, (project_id,))
            total_votes = cur.fetchone()['total_votes']
            
            project['total_investors'] = total_investors
            project['total_votes'] = total_votes
        else:
            project['total_investors'] = 0
            project['total_votes'] = 0
            
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()
        
    template = 'funding_project.html' if project['listing_status'] == 'accepted' else 'pending_project.html'
    return render_template(template, project=project)

@app.route('/project/<int:project_id>/update', methods=['POST'])
@login_required
def update_project(project_id):
    action = request.form.get('action')
    comment = request.form.get('platform_comment', '')
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        if action == 'accept':
            cur.execute("""
                UPDATE project 
                SET listing_status = 'accepted', editable = false, platform_comment = %s
                WHERE id = %s
            """, (comment, project_id))
            flash('Project has been accepted', 'success')
        elif action == 'reject':
            cur.execute("""
                UPDATE project 
                SET listing_status = 'rejected', platform_comment = %s
                WHERE id = %s
            """, (comment, project_id))
            flash('Project has been rejected', 'success')
        elif action == 'toggle_visibility':
            cur.execute("""
                UPDATE project 
                SET hidden = NOT hidden
                WHERE id = %s
                RETURNING hidden
            """, (project_id,))
            result = cur.fetchone()
            status = 'hidden' if result[0] else 'visible'
            flash(f'Project is now {status}', 'success')
        elif action == 'claim_fee':
            cur.execute("""
                UPDATE project 
                SET fee_claimed = true
                WHERE id = %s AND funding_status = 'completed'
            """, (project_id,))
            flash('Platform fee has been marked as claimed', 'success')
        else:
            flash('Invalid action', 'danger')
            
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        cur.close()
        conn.close()
        
    return redirect(url_for('view_project', project_id=project_id))

# Manage accepted projects route
@app.route('/projects')
@login_required
def manage_projects():
    status_filter = request.args.get('status', '')
    sort_by = request.args.get('sort', 'newest')
    
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        query = """
            SELECT p.*, r.username as raiser_name
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.listing_status = 'accepted'
        """
        
        params = []
        
        # Apply status filter
        if status_filter:
            query += " AND p.funding_status = %s"
            params.append(status_filter)
            
        # Apply sorting
        if sort_by == 'oldest':
            query += " ORDER BY p.created_time ASC"
        elif sort_by == 'fund_raised':
            query += " ORDER BY p.fund_raised DESC"
        else:  # Default to newest
            query += " ORDER BY p.created_time DESC"
            
        cur.execute(query, params)
        projects = cur.fetchall()
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        projects = []
    finally:
        cur.close()
        conn.close()
        
    return render_template('manage_projects.html', 
                          projects=projects, 
                          current_status=status_filter, 
                          current_sort=sort_by)

# Search route
@app.route('/search')
@login_required
def search():
    query = request.args.get('query', '').strip()
    
    if not query:
        flash('Please enter a search query', 'warning')
        return redirect(url_for('dashboard'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT p.*, r.username as raiser_name
            FROM project p
            JOIN raiser r ON p.raiser_id = r.id
            WHERE p.name ILIKE %s OR p.token_symbol ILIKE %s
        """, (f"%{query}%", f"%{query}%"))
        projects = cur.fetchall()
        
        if not projects:
            flash(f'No projects found matching "{query}"', 'info')
            return redirect(url_for('dashboard'))
        
        # Removed the redirect for single result case
        # Always show the search results page
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('dashboard'))
    finally:
        cur.close()
        conn.close()
        
    return render_template('search_results.html', projects=projects, query=query)

# Posts management routes
@app.route('/posts')
@login_required
def manage_posts():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cur.execute("""
            SELECT * FROM post
            ORDER BY created_time DESC
        """)
        posts = cur.fetchall()
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')
        posts = []
    finally:
        cur.close()
        conn.close()
        
    return render_template('manage_posts.html', posts=posts)

@app.route('/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        thumbnail_url = request.form.get('thumbnail_url')
        status = request.form.get('status', 'draft')
        
        if not title or not content or not thumbnail_url:
            flash('All fields are required', 'danger')
            return render_template('edit_post.html', post=request.form)
            
        conn = get_db_connection()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                INSERT INTO post (title, content, thumbnail_url, status)
                VALUES (%s, %s, %s, %s)
            """, (title, content, thumbnail_url, status))
            conn.commit()
            flash('Post created successfully', 'success')
            return redirect(url_for('manage_posts'))
        except Exception as e:
            conn.rollback()
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('manage_posts'))
        finally:
            cur.close()
            conn.close()
            
    return render_template('edit_post.html', post=None)

@app.route('/post/<post_id>', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'delete':
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                cur.execute("DELETE FROM post WHERE id = %s", (post_id,))
                conn.commit()
                flash('Post deleted successfully', 'success')
                return redirect(url_for('manage_posts'))
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'danger')
            finally:
                cur.close()
                conn.close()
        else:
            title = request.form.get('title')
            content = request.form.get('content')
            thumbnail_url = request.form.get('thumbnail_url')
            status = request.form.get('status', 'draft')
            
            if not title or not content or not thumbnail_url:
                flash('All fields are required', 'danger')
                return redirect(url_for('edit_post', post_id=post_id))
                
            conn = get_db_connection()
            cur = conn.cursor()
            
            try:
                cur.execute("""
                    UPDATE post
                    SET title = %s, content = %s, thumbnail_url = %s, status = %s
                    WHERE id = %s
                """, (title, content, thumbnail_url, status, post_id))
                conn.commit()
                flash('Post updated successfully', 'success')
                return redirect(url_for('manage_posts'))
            except Exception as e:
                conn.rollback()
                flash(f'Error: {str(e)}', 'danger')
                return redirect(url_for('manage_posts'))
            finally:
                cur.close()
                conn.close()
    else:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        try:
            cur.execute("SELECT * FROM post WHERE id = %s", (post_id,))
            post = cur.fetchone()
            
            if not post:
                flash('Post not found', 'warning')
                return redirect(url_for('manage_posts'))
        except Exception as e:
            flash(f'Error: {str(e)}', 'danger')
            return redirect(url_for('manage_posts'))
        finally:
            cur.close()
            conn.close()
            
        return render_template('edit_post.html', post=post)

# Custom template filters
@app.template_filter('datetime')
def datetime_format(value, format='%Y-%m-%d %H:%M'):
    if isinstance(value, (int, float)):
        # Assume timestamp in seconds
        dt = datetime.datetime.fromtimestamp(value)
        return dt.strftime(format)
    return value

# Main run function
if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5002)