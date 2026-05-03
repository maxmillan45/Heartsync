# ============================================
# HEARTSYNC - COMPLETE STABLE VERSION (NO PILLOW)
# ============================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_session import Session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import json
import os
from datetime import datetime, timedelta
from functools import wraps

# ============================================
# CONFIG
# ============================================

app = Flask(__name__)
app.secret_key = 'super-secret-key'

app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

Session(app)

# Create upload folders
os.makedirs('static/uploads/avatars', exist_ok=True)

# ============================================
# DATABASE
# ============================================

DATABASE = 'heartsync.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        c = conn.cursor()

        c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            password TEXT,
            full_name TEXT,
            profile_complete INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            email TEXT PRIMARY KEY,
            age INTEGER,
            location TEXT,
            bio TEXT,
            interests TEXT,
            avatar_url TEXT,
            gender TEXT,
            looking_for TEXT,
            occupation TEXT,
            education TEXT,
            height TEXT,
            created_at TIMESTAMP
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_email TEXT,
            to_email TEXT,
            created_at TIMESTAMP,
            UNIQUE(from_email, to_email)
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user1 TEXT,
            user2 TEXT,
            created_at TIMESTAMP,
            UNIQUE(user1, user2)
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            from_email TEXT,
            to_email TEXT,
            message TEXT,
            timestamp TEXT,
            read_status INTEGER DEFAULT 0
        )
        ''')

        c.execute('''
        CREATE TABLE IF NOT EXISTS passed_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT,
            passed_email TEXT,
            UNIQUE(user_email, passed_email)
        )
        ''')

        conn.commit()
        print("Database ready!")

init_db()

# ============================================
# HELPERS
# ============================================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def safe_int(val):
    try:
        return int(val)
    except:
        return None

def get_chat_id(u1, u2):
    return '_'.join(sorted([u1, u2]))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ============================================
# DATABASE FUNCTIONS
# ============================================

def get_user(email):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        return dict(row) if row else None

def save_user(email, password, name):
    with get_db() as conn:
        conn.execute("INSERT INTO users (email, password, full_name, created_at) VALUES (?, ?, ?, ?)",
                     (email, password, name, datetime.now().isoformat()))
        conn.commit()

def save_profile(email, data):
    with get_db() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO profiles (email, age, location, bio, interests, avatar_url, gender, looking_for, occupation, education, height, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            email,
            data.get('age'),
            data.get('location'),
            data.get('bio'),
            json.dumps(data.get('interests', [])),
            data.get('avatar_url', '/static/uploads/avatars/default.jpg'),
            data.get('gender'),
            data.get('looking_for'),
            data.get('occupation'),
            data.get('education'),
            data.get('height'),
            datetime.now().isoformat()
        ))
        conn.execute("UPDATE users SET profile_complete=1 WHERE email=?", (email,))
        conn.commit()

def get_profile(email):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE email=?", (email,)).fetchone()
        if row:
            d = dict(row)
            d['interests'] = json.loads(d['interests']) if d['interests'] else []
            return d
        return None

def get_all_users():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users WHERE profile_complete=1").fetchall()
        return [dict(r) for r in rows]

def add_like(a, b):
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO likes (from_email, to_email, created_at) VALUES (?, ?, ?)",
                        (a, b, datetime.now().isoformat()))
            conn.commit()
            return True
    except:
        return False

def get_likes(email):
    with get_db() as conn:
        rows = conn.execute("SELECT to_email FROM likes WHERE from_email=?", (email,)).fetchall()
        return [r['to_email'] for r in rows]

def get_likes_received(email):
    with get_db() as conn:
        rows = conn.execute("SELECT from_email FROM likes WHERE to_email=?", (email,)).fetchall()
        return [r['from_email'] for r in rows]

def add_match(a, b):
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO matches (user1, user2, created_at) VALUES (?, ?, ?)", 
                        (a, b, datetime.now().isoformat()))
            conn.commit()
            return True
    except:
        return False

def get_matches(email):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM matches WHERE user1=? OR user2=?", (email, email)).fetchall()
        result = []
        for r in rows:
            result.append(r['user2'] if r['user1'] == email else r['user1'])
        return result

def add_message(chat_id, a, b, msg):
    with get_db() as conn:
        conn.execute("INSERT INTO messages (chat_id, from_email, to_email, message, timestamp) VALUES (?,?,?,?,?)",
                     (chat_id, a, b, msg, datetime.now().isoformat()))
        conn.commit()

def get_messages(chat_id):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM messages WHERE chat_id=? ORDER BY timestamp", (chat_id,)).fetchall()
        return [dict(r) for r in rows]

def add_passed(user_email, passed_email):
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO passed_users (user_email, passed_email) VALUES (?, ?)", 
                        (user_email, passed_email))
            conn.commit()
            return True
    except:
        return False

def get_passed(email):
    with get_db() as conn:
        rows = conn.execute("SELECT passed_email FROM passed_users WHERE user_email=?", (email,)).fetchall()
        return [r['passed_email'] for r in rows]

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    return redirect(url_for('login'))

# ---------- AUTH ----------

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = get_user(email)
        if user and check_password_hash(user['password'], password):
            session.permanent = remember
            session['user_id'] = user['email']
            session['user_name'] = user['full_name']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        flash("Invalid email or password", 'danger')
    return render_template('login.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        
        if password != confirm:
            flash("Passwords do not match", 'danger')
            return redirect(url_for('register'))
            
        if get_user(email):
            flash("Email already registered", 'danger')
            return redirect(url_for('register'))

        save_user(email, generate_password_hash(password), full_name)
        session['user_id'] = email
        session['user_name'] = full_name
        flash(f'Welcome to Heartsync, {full_name}! Please complete your profile.', 'success')
        return redirect(url_for('setup_profile'))

    return render_template('register.html')

# ---------- PROFILE ----------

@app.route('/setup-profile', methods=['GET','POST'])
@login_required
def setup_profile():
    if request.method == 'POST':
        avatar_url = request.form.get('avatar_url', '/static/uploads/avatars/default.jpg')
        
        data = {
            'age': safe_int(request.form.get('age')),
            'location': request.form.get('location'),
            'bio': request.form.get('bio'),
            'interests': request.form.getlist('interests'),
            'avatar_url': avatar_url,
            'gender': request.form.get('gender'),
            'looking_for': request.form.get('looking_for'),
            'occupation': request.form.get('occupation'),
            'education': request.form.get('education'),
            'height': request.form.get('height')
        }
        
        custom = request.form.get('custom_interests', '')
        if custom:
            data['interests'].extend([i.strip() for i in custom.split(',') if i.strip()])
        
        save_profile(session['user_id'], data)
        flash('Profile complete! Start discovering people!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('setup_profile.html')

@app.route('/profile')
@login_required
def profile():
    profile_data = get_profile(session['user_id']) or {}
    return render_template('profile.html', user=profile_data, user_email=session['user_id'])

@app.route('/profile/<email>')
@login_required
def view_other_profile(email):
    if email == session['user_id']:
        return redirect(url_for('profile'))
    
    profile_data = get_profile(email)
    if not profile_data:
        flash('User not found', 'danger')
        return redirect(url_for('discover'))
    
    is_match = email in get_matches(session['user_id'])
    return render_template('view_profile.html', user=profile_data, is_match=is_match)

# ---------- UPLOAD AVATAR (Without Pillow) ----------

@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"avatar_{session['user_id']}_{datetime.now().timestamp()}.{ext}"
            filepath = os.path.join('static/uploads/avatars', filename)
            
            # Save the file directly without processing
            file.save(filepath)
            
            avatar_url = f'/static/uploads/avatars/{filename}'
            
            # Update profile
            profile = get_profile(session['user_id'])
            if profile:
                with get_db() as conn:
                    conn.execute("UPDATE profiles SET avatar_url = ? WHERE email = ?", 
                                (avatar_url, session['user_id']))
                    conn.commit()
            
            return jsonify({'success': True, 'url': avatar_url})
        
        return jsonify({'success': False, 'message': 'File type not allowed'})
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'success': False, 'message': str(e)})

# ---------- MAIN ----------

@app.route('/dashboard')
@login_required
def dashboard():
    profile = get_profile(session['user_id']) or {}
    matches = get_matches(session['user_id'])
    
    recent = []
    for match in matches[:5]:
        p = get_profile(match)
        u = get_user(match)
        if p and u:
            recent.append({
                'email': match,
                'name': u.get('full_name', 'Unknown'),
                'avatar_url': p.get('avatar_url', '/static/uploads/avatars/default.jpg'),
                'location': p.get('location', 'Unknown')
            })
    
    stats = {
        'likes_sent': len(get_likes(session['user_id'])),
        'likes_received': len(get_likes_received(session['user_id'])),
        'matches': len(matches)
    }
    
    completion = 0
    if profile:
        fields = ['age', 'location', 'bio', 'interests']
        filled = sum(1 for f in fields if profile.get(f))
        completion = int((filled / len(fields)) * 100)
    
    return render_template('dashboard.html', 
                         user=profile,
                         stats=stats,
                         recent_matches=recent,
                         completion_percentage=completion)

@app.route('/discover')
@login_required
def discover():
    current = session['user_id']
    passed = get_passed(current)
    matches = get_matches(current)
    users_to_show = []

    for u in get_all_users():
        if u['email'] == current:
            continue
        if u['email'] in passed:
            continue
        if u['email'] in matches:
            continue

        profile = get_profile(u['email'])
        if not profile:
            continue

        users_to_show.append({
            'email': u['email'],
            'name': u.get('full_name', 'Unknown'),
            'age': profile.get('age'),
            'location': profile.get('location'),
            'bio': profile.get('bio', '')[:100],
            'interests': profile.get('interests', [])[:3],
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default.jpg'),
            'compatibility': 70
        })

    return render_template('discover.html', users=users_to_show)

# ---------- API ----------

@app.route('/api/like', methods=['POST'])
@login_required
def like():
    email = request.json.get('email')
    me = session['user_id']

    if add_like(me, email):
        if me in get_likes_received(email):
            add_match(me, email)
            return jsonify({'success': True, 'is_match': True})
        return jsonify({'success': True, 'is_match': False})

    return jsonify({'success': False})

@app.route('/api/pass', methods=['POST'])
@login_required
def pass_user():
    email = request.json.get('email')
    if email and email != session['user_id']:
        add_passed(session['user_id'], email)
    return jsonify({'success': True})

@app.route('/matches')
@login_required
def matches():
    matches_list = []
    for match_email in get_matches(session['user_id']):
        profile = get_profile(match_email)
        user = get_user(match_email)
        if profile and user:
            matches_list.append({
                'email': match_email,
                'name': user.get('full_name', 'Unknown'),
                'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default.jpg'),
                'age': profile.get('age', '?'),
                'location': profile.get('location', 'Unknown')
            })
    return render_template('matches.html', matches=matches_list)

@app.route('/messages')
@login_required
def messages():
    selected = request.args.get('match')
    matches_list = []
    
    for match_email in get_matches(session['user_id']):
        profile = get_profile(match_email)
        user = get_user(match_email)
        if profile and user:
            matches_list.append({
                'email': match_email,
                'name': user.get('full_name', 'Unknown'),
                'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default.jpg')
            })
    
    current_messages = []
    selected_info = None
    
    if selected and selected in get_matches(session['user_id']):
        chat_id = get_chat_id(session['user_id'], selected)
        current_messages = get_messages(chat_id)
        sel_profile = get_profile(selected)
        sel_user = get_user(selected)
        if sel_profile and sel_user:
            selected_info = {
                'email': selected,
                'name': sel_user.get('full_name', 'Unknown'),
                'avatar_url': sel_profile.get('avatar_url', '/static/uploads/avatars/default.jpg')
            }
    
    return render_template('messages.html', 
                         matches=matches_list,
                         current_messages=current_messages,
                         selected_match=selected_info,
                         user_email=session['user_id'])

@app.route('/api/send-message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    to_email = data.get('to_email')
    message = data.get('message')
    
    if not to_email or not message:
        return jsonify({'success': False})
    
    if to_email not in get_matches(session['user_id']):
        return jsonify({'success': False})
    
    chat_id = get_chat_id(session['user_id'], to_email)
    add_message(chat_id, session['user_id'], to_email, message)
    return jsonify({'success': True})

@app.route('/api/get-messages', methods=['GET'])
@login_required
def get_messages_api():
    match_email = request.args.get('match')
    if not match_email or match_email not in get_matches(session['user_id']):
        return jsonify({'messages': []})
    
    chat_id = get_chat_id(session['user_id'], match_email)
    messages = get_messages(chat_id)
    return jsonify({'messages': messages})

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.json
        profile = get_profile(session['user_id']) or {}
        profile.update({
            'age': data.get('age', profile.get('age')),
            'location': data.get('location', profile.get('location')),
            'bio': data.get('bio', profile.get('bio')),
            'interests': data.get('interests', profile.get('interests', [])),
            'gender': data.get('gender', profile.get('gender')),
            'looking_for': data.get('looking_for', profile.get('looking_for')),
            'height': data.get('height', profile.get('height')),
            'education': data.get('education', profile.get('education'))
        })
        save_profile(session['user_id'], profile)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/settings')
@login_required
def settings():
    profile_data = get_profile(session['user_id']) or {}
    return render_template('settings.html', user=profile_data, user_email=session['user_id'])

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)