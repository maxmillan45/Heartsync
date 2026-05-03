# ============================================
# COMPLETE HEARTSYNC APP - NO EMOJIS
# ============================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from flask_session import Session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageEnhance, ImageFilter
import os
import json
from datetime import datetime, timedelta
from functools import wraps
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================
# FLASK APP CONFIGURATION
# ============================================

app = Flask(__name__)
app.secret_key = 'heartsync-secret-key-2024'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

Session(app)

# ============================================
# FILE UPLOAD CONFIGURATION
# ============================================

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024

AVATAR_SIZE = (300, 300)
PHOTO_SIZE = (800, 800)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/uploads/avatars', exist_ok=True)
os.makedirs('static/uploads/photos', exist_ok=True)

# ============================================
# USER CATEGORIES (NO EMOJIS)
# ============================================

CATEGORIES = {
    'student': {'name': 'Student', 'icon': '(S)', 'color': 'blue', 'description': 'Currently studying'},
    'gamer': {'name': 'Gamer', 'icon': '(G)', 'color': 'green', 'description': 'Passionate about gaming'},
    'professional': {'name': 'Professional', 'icon': '(P)', 'color': 'purple', 'description': 'Career-focused'},
    'fitness': {'name': 'Fitness', 'icon': '(F)', 'color': 'orange', 'description': 'Active lifestyle'},
    'creative': {'name': 'Creative', 'icon': '(C)', 'color': 'pink', 'description': 'Artist or musician'},
    'traveler': {'name': 'Traveler', 'icon': '(T)', 'color': 'teal', 'description': 'Love exploring'},
    'foodie': {'name': 'Foodie', 'icon': '(FD)', 'color': 'red', 'description': 'Passionate about food'},
    'no_category': {'name': 'No Category', 'icon': '(N)', 'color': 'gray', 'description': 'No category selected'}
}

# ============================================
# DATABASE SETUP
# ============================================

DATABASE = 'heartsync.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                email TEXT PRIMARY KEY,
                password TEXT,
                full_name TEXT,
                category TEXT,
                profile_complete BOOLEAN DEFAULT 0,
                created_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS profiles (
                email TEXT PRIMARY KEY,
                full_name TEXT,
                age INTEGER,
                location TEXT,
                occupation TEXT,
                bio TEXT,
                interests TEXT,
                gender TEXT,
                looking_for TEXT,
                height TEXT,
                education TEXT,
                avatar_url TEXT,
                photos TEXT,
                created_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS likes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_email TEXT,
                to_email TEXT,
                created_at TIMESTAMP,
                UNIQUE(from_email, to_email)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user1 TEXT,
                user2 TEXT,
                created_at TIMESTAMP,
                UNIQUE(user1, user2)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                from_email TEXT,
                to_email TEXT,
                message TEXT,
                timestamp TIMESTAMP,
                read_status BOOLEAN DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS passed_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                passed_email TEXT,
                UNIQUE(user_email, passed_email)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seen_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT,
                seen_email TEXT,
                UNIQUE(user_email, seen_email)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                type TEXT,
                message TEXT,
                timestamp TIMESTAMP,
                read_status BOOLEAN DEFAULT 0
            )
        ''')
        
        conn.commit()
        print("Database ready!")

init_db()

# ============================================
# DATABASE FUNCTIONS
# ============================================

def save_user(email, password, full_name):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (email, password, full_name, category, profile_complete, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (email, password, full_name, None, 0, datetime.now().isoformat()))
        conn.commit()

def get_user(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        row = cursor.fetchone()
        return dict(row) if row else None

def update_user_category(email, category):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET category = ? WHERE email = ?', (category, email))
        conn.commit()

def update_user_profile_complete(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET profile_complete = 1 WHERE email = ?', (email,))
        conn.commit()

def save_profile(email, profile_data):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO profiles 
            (email, full_name, age, location, occupation, bio, interests, gender, looking_for, height, education, avatar_url, photos, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (email, profile_data.get('full_name'), profile_data.get('age'),
              profile_data.get('location'), profile_data.get('occupation'),
              profile_data.get('bio'), json.dumps(profile_data.get('interests', [])),
              profile_data.get('gender'), profile_data.get('looking_for'),
              profile_data.get('height'), profile_data.get('education'),
              profile_data.get('avatar_url'), json.dumps(profile_data.get('photos', [])),
              datetime.now().isoformat()))
        conn.commit()

def get_profile(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM profiles WHERE email = ?', (email,))
        row = cursor.fetchone()
        if row:
            profile = dict(row)
            profile['interests'] = json.loads(profile['interests']) if profile['interests'] else []
            profile['photos'] = json.loads(profile['photos']) if profile['photos'] else []
            return profile
        return None

def get_all_users():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users')
        users = {}
        for row in cursor.fetchall():
            users[row['email']] = dict(row)
        return users

def add_like(from_email, to_email):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO likes (from_email, to_email, created_at) VALUES (?, ?, ?)',
                          (from_email, to_email, datetime.now().isoformat()))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def remove_like(from_email, to_email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM likes WHERE from_email = ? AND to_email = ?', (from_email, to_email))
        conn.commit()
        return cursor.rowcount > 0

def get_likes(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT to_email FROM likes WHERE from_email = ?', (email,))
        return [row['to_email'] for row in cursor.fetchall()]

def get_likes_received(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT from_email FROM likes WHERE to_email = ?', (email,))
        return [row['from_email'] for row in cursor.fetchall()]

def add_match(user1, user2):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO matches (user1, user2, created_at) VALUES (?, ?, ?)',
                          (user1, user2, datetime.now().isoformat()))
            conn.commit()
            add_notification(user1, 'match', f"You matched with {get_profile(user2).get('full_name', 'someone')}")
            add_notification(user2, 'match', f"You matched with {get_profile(user1).get('full_name', 'someone')}")
            return True
        except sqlite3.IntegrityError:
            return False

def get_matches(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user1, user2 FROM matches WHERE user1 = ? OR user2 = ?', (email, email))
        matches = []
        for row in cursor.fetchall():
            matches.append(row['user2'] if row['user1'] == email else row['user1'])
        return matches

def add_message(chat_id, from_email, to_email, message_text):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO messages (chat_id, from_email, to_email, message, timestamp)
            VALUES (?, ?, ?, ?, ?)
        ''', (chat_id, from_email, to_email, message_text, datetime.now().isoformat()))
        conn.commit()
        add_notification(to_email, 'message', f"New message from {get_profile(from_email).get('full_name', 'Someone')}")

def get_messages(chat_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM messages WHERE chat_id = ? ORDER BY timestamp', (chat_id,))
        return [dict(row) for row in cursor.fetchall()]

def add_passed(user_email, passed_email):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO passed_users (user_email, passed_email) VALUES (?, ?)',
                          (user_email, passed_email))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_passed(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT passed_email FROM passed_users WHERE user_email = ?', (email,))
        return [row['passed_email'] for row in cursor.fetchall()]

def add_seen(user_email, seen_email):
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO seen_users (user_email, seen_email) VALUES (?, ?)',
                          (user_email, seen_email))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_seen(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT seen_email FROM seen_users WHERE user_email = ?', (email,))
        return [row['seen_email'] for row in cursor.fetchall()]

def clear_seen(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM seen_users WHERE user_email = ?', (email,))
        conn.commit()

def clear_passed(email):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM passed_users WHERE user_email = ?', (email,))
        conn.commit()

def add_notification(user_id, notif_type, message):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO notifications (user_id, type, message, timestamp)
            VALUES (?, ?, ?, ?)
        ''', (user_id, notif_type, message, datetime.now().isoformat()))
        conn.commit()

def get_notifications(user_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notifications WHERE user_id = ? ORDER BY timestamp DESC LIMIT 50', (user_id,))
        return [dict(row) for row in cursor.fetchall()]

def mark_notification_read(notif_id):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE notifications SET read_status = 1 WHERE id = ?', (notif_id,))
        conn.commit()

def get_chat_id(user1, user2):
    return '_'.join(sorted([user1, user2]))

# ============================================
# IMAGE FUNCTIONS
# ============================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_image(file, size):
    img = Image.open(file)
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')
    img.thumbnail(size, Image.Resampling.LANCZOS)
    return img

# ============================================
# HELPER FUNCTIONS
# ============================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def calculate_compatibility(profile1, profile2):
    if not profile1 or not profile2:
        return 50
    
    score = 50
    
    interests1 = set(profile1.get('interests', []))
    interests2 = set(profile2.get('interests', []))
    if interests1 and interests2:
        common = len(interests1 & interests2)
        total = len(interests1 | interests2)
        if total > 0:
            score += (common / total) * 30
    
    age1 = profile1.get('age')
    age2 = profile2.get('age')
    if age1 and age2:
        if abs(age1 - age2) <= 5:
            score += 10
    
    if profile1.get('location') == profile2.get('location'):
        score += 10
    
    return min(int(score), 100)

# ============================================
# AUTHENTICATION ROUTES
# ============================================

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember') == 'on'
        
        user = get_user(email)
        if user and user.get('password') and check_password_hash(user['password'], password):
            session.permanent = remember
            session['user_id'] = email
            session['user_name'] = user['full_name']
            flash(f'Welcome back, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')
        full_name = request.form.get('full_name')
        
        if password != confirm:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if get_user(email):
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        save_user(email, generate_password_hash(password), full_name)
        session['user_id'] = email
        session['user_name'] = full_name
        flash('Account created! Please select a category.', 'success')
        return redirect(url_for('category_select'))
    
    return render_template('register.html')

@app.route('/category-select', methods=['GET', 'POST'])
@login_required
def category_select():
    if request.method == 'POST':
        category = request.form.get('category')
        if category in CATEGORIES:
            update_user_category(session['user_id'], category)
            session['category'] = category
            return redirect(url_for('setup_profile'))
        else:
            flash('Please select a category', 'warning')
    
    return render_template('category_select.html', categories=CATEGORIES)

@app.route('/setup-profile', methods=['GET', 'POST'])
@login_required
def setup_profile():
    if request.method == 'POST':
        profile_data = {
            'full_name': request.form.get('full_name'),
            'age': int(request.form.get('age')),
            'location': request.form.get('location'),
            'occupation': request.form.get('occupation'),
            'bio': request.form.get('bio'),
            'interests': request.form.getlist('interests'),
            'gender': request.form.get('gender'),
            'looking_for': request.form.get('looking_for'),
            'height': request.form.get('height'),
            'education': request.form.get('education'),
            'avatar_url': '/static/uploads/avatars/default.jpg',
            'photos': []
        }
        
        custom = request.form.get('custom_interests', '')
        if custom:
            profile_data['interests'].extend([i.strip() for i in custom.split(',') if i.strip()])
        
        save_profile(session['user_id'], profile_data)
        update_user_profile_complete(session['user_id'])
        
        flash('Profile complete! Start discovering people!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('setup_profile.html', categories=CATEGORIES)

# ============================================
# MAIN ROUTES
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    profile = get_profile(session['user_id']) or {}
    matches = get_matches(session['user_id'])
    
    recent = []
    for match in matches[:5]:
        p = get_profile(match)
        if p:
            recent.append({'email': match, 'name': p.get('full_name'), 'avatar_url': p.get('avatar_url'), 'location': p.get('location')})
    
    passed = get_passed(session['user_id'])
    all_users = get_all_users()
    suggestions = []
    current_profile = profile
    
    for email, user_data in all_users.items():
        if email != session['user_id'] and user_data.get('profile_complete'):
            if email not in passed:
                p = get_profile(email)
                if p:
                    compatibility = calculate_compatibility(current_profile, p)
                    if compatibility > 60:
                        suggestions.append({
                            'email': email,
                            'name': p.get('full_name'),
                            'avatar_url': p.get('avatar_url'),
                            'location': p.get('location'),
                            'compatibility': compatibility,
                            'verified': False
                        })
    
    suggestions.sort(key=lambda x: x['compatibility'], reverse=True)
    
    stats = {
        'profile_views': len(get_likes(session['user_id'])),
        'likes_received': len(get_likes_received(session['user_id'])),
        'matches_count': len(matches)
    }
    
    completion = 0
    if profile:
        fields = ['full_name', 'age', 'location', 'occupation', 'bio', 'interests', 'gender', 'looking_for']
        filled = sum(1 for f in fields if profile.get(f))
        completion = int((filled / len(fields)) * 100)
    
    return render_template('dashboard.html', 
                         user=profile,
                         stats=stats,
                         recent_matches=recent,
                         suggestions=suggestions[:5],
                         completion_percentage=completion)

@app.route('/profile')
@login_required
def profile():
    profile_data = get_profile(session['user_id']) or {}
    user = get_user(session['user_id'])
    category = user.get('category', 'no_category') if user else 'no_category'
    
    stats = {
        'profile_views': len(get_likes(session['user_id'])),
        'likes_received': len(get_likes_received(session['user_id'])),
        'matches_count': len(get_matches(session['user_id']))
    }
    
    completion = 0
    if profile_data:
        fields = ['full_name', 'age', 'location', 'occupation', 'bio', 'interests', 'gender', 'looking_for']
        filled = sum(1 for f in fields if profile_data.get(f))
        completion = int((filled / len(fields)) * 100)
    
    return render_template('profile.html', 
                         user=profile_data,
                         user_email=session['user_id'],
                         category=CATEGORIES.get(category, CATEGORIES['no_category']),
                         completion_percentage=completion,
                         profile_views=stats['profile_views'],
                         likes_received=stats['likes_received'],
                         matches_count=stats['matches_count'])

@app.route('/profile/<email>')
@login_required
def view_other_profile(email):
    if email == session['user_id']:
        return redirect(url_for('profile'))
    
    profile_data = get_profile(email)
    if not profile_data:
        flash('User not found', 'danger')
        return redirect(url_for('discover'))
    
    user = get_user(email)
    category = user.get('category', 'no_category') if user else 'no_category'
    is_match = email in get_matches(session['user_id'])
    
    return render_template('view_profile.html', 
                         user=profile_data,
                         user_email=email,
                         category=CATEGORIES.get(category, CATEGORIES['no_category']),
                         is_match=is_match)

@app.route('/discover')
@login_required
def discover():
    passed = get_passed(session['user_id'])
    seen = get_seen(session['user_id'])
    current_profile = get_profile(session['user_id']) or {}
    all_users = get_all_users()
    
    users_to_show = []
    
    for email, user in all_users.items():
        if email == session['user_id']:
            continue
        if not user.get('profile_complete'):
            continue
        if email in passed:
            continue
        if email in seen:
            continue
        
        profile = get_profile(email)
        if not profile:
            continue
        
        has_liked = session['user_id'] in get_likes(email)
        is_match = email in get_matches(session['user_id'])
        compatibility = calculate_compatibility(current_profile, profile)
        
        users_to_show.append({
            'email': email,
            'name': profile.get('full_name', 'Unknown'),
            'age': profile.get('age', '?'),
            'location': profile.get('location', 'Unknown'),
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default.jpg'),
            'bio': profile.get('bio', '')[:100],
            'interests': profile.get('interests', [])[:3],
            'has_liked': has_liked,
            'is_match': is_match,
            'compatibility': compatibility
        })
    
    if not users_to_show and seen:
        clear_seen(session['user_id'])
        return redirect(url_for('discover'))
    
    users_to_show.sort(key=lambda x: x['compatibility'], reverse=True)
    return render_template('discover.html', users=users_to_show)

@app.route('/matches')
@login_required
def matches():
    matches_list = []
    for match_email in get_matches(session['user_id']):
        profile = get_profile(match_email)
        if profile:
            matches_list.append({
                'email': match_email,
                'name': profile.get('full_name', 'Unknown'),
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
        if profile:
            matches_list.append({
                'email': match_email,
                'name': profile.get('full_name', 'Unknown'),
                'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default.jpg')
            })
    
    current_messages = []
    selected_info = None
    
    if selected and selected in get_matches(session['user_id']):
        chat_id = get_chat_id(session['user_id'], selected)
        current_messages = get_messages(chat_id)
        sel_profile = get_profile(selected)
        if sel_profile:
            selected_info = {
                'email': selected,
                'name': sel_profile.get('full_name'),
                'avatar_url': sel_profile.get('avatar_url')
            }
    
    return render_template('messages.html', 
                         matches=matches_list,
                         current_messages=current_messages,
                         selected_match=selected_info,
                         user_email=session['user_id'])

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = get_notifications(session['user_id'])
    return render_template('notifications.html', notifications=user_notifications)

# ============================================
# API ROUTES
# ============================================

@app.route('/api/mark-seen', methods=['POST'])
@login_required
def mark_seen():
    data = request.json
    email = data.get('email')
    if email and email != session['user_id']:
        add_seen(session['user_id'], email)
    return jsonify({'success': True})

@app.route('/api/reset-discover', methods=['POST'])
@login_required
def reset_discover():
    clear_seen(session['user_id'])
    clear_passed(session['user_id'])
    return jsonify({'success': True})

@app.route('/api/pass', methods=['POST'])
@login_required
def pass_user():
    data = request.json
    email = data.get('email')
    if email and email != session['user_id']:
        add_passed(session['user_id'], email)
        add_seen(session['user_id'], email)
    return jsonify({'success': True})

@app.route('/api/like', methods=['POST'])
@login_required
def like_user():
    data = request.json
    liked_email = data.get('email')
    
    if not liked_email or liked_email == session['user_id']:
        return jsonify({'success': False})
    
    if add_like(session['user_id'], liked_email):
        is_match = session['user_id'] in get_likes(liked_email)
        if is_match:
            add_match(session['user_id'], liked_email)
            return jsonify({'success': True, 'is_match': True})
        return jsonify({'success': True, 'is_match': False})
    
    return jsonify({'success': False})

@app.route('/api/unlike', methods=['POST'])
@login_required
def unlike_user():
    data = request.json
    email = data.get('email')
    if email:
        remove_like(session['user_id'], email)
    return jsonify({'success': True})

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
            'full_name': data.get('full_name', profile.get('full_name')),
            'age': data.get('age', profile.get('age')),
            'location': data.get('location', profile.get('location')),
            'occupation': data.get('occupation', profile.get('occupation')),
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

@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False})
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False})
        
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"avatar_{session['user_id']}_{datetime.now().timestamp()}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', filename)
            
            img = process_image(file, AVATAR_SIZE)
            img.save(filepath, optimize=True, quality=85)
            
            profile = get_profile(session['user_id']) or {}
            profile['avatar_url'] = f'/static/uploads/avatars/{filename}'
            save_profile(session['user_id'], profile)
            
            return jsonify({'success': True, 'url': profile['avatar_url']})
        
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False})

@app.route('/api/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    try:
        if 'photo' not in request.files:
            return jsonify({'success': False})
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'success': False})
        
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"photo_{session['user_id']}_{datetime.now().timestamp()}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename)
            
            img = process_image(file, PHOTO_SIZE)
            img.save(filepath, optimize=True, quality=85)
            
            photo_url = f'/static/uploads/photos/{filename}'
            profile = get_profile(session['user_id']) or {}
            photos = profile.get('photos', [])
            photos.append(photo_url)
            profile['photos'] = photos
            save_profile(session['user_id'], profile)
            
            return jsonify({'success': True, 'url': photo_url})
        
        return jsonify({'success': False})
    except Exception as e:
        return jsonify({'success': False})

@app.route('/api/mark-notification-read', methods=['POST'])
@login_required
def mark_notification_read():
    data = request.json
    notif_id = data.get('id')
    if notif_id:
        mark_notification_read(notif_id)
    return jsonify({'success': True})

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('login'))

# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)