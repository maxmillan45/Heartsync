from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageEnhance, ImageFilter
import os
import json
from datetime import datetime, timedelta
from functools import wraps
from authlib.integrations.flask_client import OAuth
import secrets
import re
from collections import defaultdict
import io
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


app = Flask(__name__)
app.secret_key = 'heartsync-secret-key-2024-change-this-in-production'
app.permanent_session_lifetime = timedelta(days=7)


# Google OAuth Configuration - Use environment variables for security
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("WARNING: Google OAuth credentials not found. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# Configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

# Image quality settings
AVATAR_SIZE = (500, 500)
PHOTO_SIZE = (1200, 1200)
JPEG_QUALITY = 95
PNG_QUALITY = 95

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create upload folders
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/uploads/avatars', exist_ok=True)
os.makedirs('static/uploads/photos', exist_ok=True)

# Professional Categories
CATEGORIES = {
    'student': {'name': 'Student', 'icon': '(S)', 'color': 'blue', 'description': 'Currently studying and looking for meaningful connections'},
    'gamer': {'name': 'Gamer', 'icon': '(G)', 'color': 'green', 'description': 'Passionate about gaming'},
    'professional': {'name': 'Professional', 'icon': '(P)', 'color': 'purple', 'description': 'Career-focused individual'},
    'fitness': {'name': 'Fitness Enthusiast', 'icon': '(F)', 'color': 'orange', 'description': 'Active lifestyle enthusiast'},
    'creative': {'name': 'Creative', 'icon': '(C)', 'color': 'pink', 'description': 'Artist, musician, or writer'},
    'traveler': {'name': 'Traveler', 'icon': '(T)', 'color': 'teal', 'description': 'Love exploring new places'},
    'foodie': {'name': 'Foodie', 'icon': '(Fd)', 'color': 'red', 'description': 'Passionate about food and dining'},
    'no_category': {'name': 'No Category', 'icon': '(N)', 'color': 'gray', 'description': 'Prefer not to be categorized'}
}

# Data storage
users_db = {}
user_profiles = {}
likes_db = {}
matches_db = {}
messages_db = {}
passed_users_db = {}
user_activity = {}
user_reports = {}
blocked_users = {}
verification_requests = {}
user_preferences = {}
notifications_db = {}
feedback_db = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def enhance_image_quality(image):
    """Enhance image quality with sharpening and color correction"""
    try:
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=0))
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.05)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.02)
        
        return image
    except Exception as e:
        print(f"Image enhancement error: {e}")
        return image

def process_uploaded_image(file, target_size, is_avatar=True):
    """Process uploaded image with high quality settings"""
    try:
        img = Image.open(file)
        
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        original_width, original_height = img.size
        
        if is_avatar:
            min_dim = min(original_width, original_height)
            left = (original_width - min_dim) / 2
            top = (original_height - min_dim) / 2
            right = (original_width + min_dim) / 2
            bottom = (original_height + min_dim) / 2
            img = img.crop((left, top, right, bottom))
        
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        img = enhance_image_quality(img)
        
        return img
    except Exception as e:
        print(f"Image processing error: {e}")
        return Image.open(file).resize(target_size, Image.Resampling.LANCZOS)

def save_image_with_quality(img, filepath, original_filename):
    """Save image with optimal quality settings"""
    try:
        ext = original_filename.rsplit('.', 1)[1].lower()
        
        if ext in ['jpg', 'jpeg']:
            img.save(filepath, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif ext == 'png':
            img.save(filepath, 'PNG', optimize=True, compress_level=6)
        elif ext == 'webp':
            img.save(filepath, 'WEBP', quality=JPEG_QUALITY, method=6)
        else:
            img.save(filepath, quality=JPEG_QUALITY, optimize=True)
        
        thumbnail_path = filepath.replace('.', '_thumb.')
        thumbnail = img.copy()
        thumbnail.thumbnail((150, 150), Image.Resampling.LANCZOS)
        
        if ext in ['jpg', 'jpeg']:
            thumbnail.save(thumbnail_path, 'JPEG', quality=85, optimize=True)
        elif ext == 'png':
            thumbnail.save(thumbnail_path, 'PNG', optimize=True)
        else:
            thumbnail.save(thumbnail_path, 'WEBP', quality=85)
            
        return True
    except Exception as e:
        print(f"Save image error: {e}")
        return False

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        update_user_activity(session['user_id'])
        return f(*args, **kwargs)
    return decorated_function

def calculate_completion_profile(profile):
    if not profile:
        return 0
    completion = 0
    total_fields = 15
    
    if profile.get('full_name'): completion += 1
    if profile.get('age'): completion += 1
    if profile.get('location'): completion += 1
    if profile.get('occupation'): completion += 1
    if profile.get('bio') and len(profile['bio']) > 50: completion += 2
    elif profile.get('bio'): completion += 1
    if profile.get('interests') and len(profile['interests']) >= 3: completion += 2
    elif profile.get('interests'): completion += 1
    if profile.get('gender'): completion += 1
    if profile.get('looking_for'): completion += 1
    if profile.get('height'): completion += 1
    if profile.get('education'): completion += 1
    if profile.get('avatar_url') and profile['avatar_url'] != '/static/uploads/avatars/default-avatar.jpg': completion += 1
    if profile.get('verified_info'): completion += 1
    if profile.get('dating_goals'): completion += 1
    
    return int((completion / total_fields) * 100)

def get_chat_id(user1, user2):
    return '_'.join(sorted([user1, user2]))

def create_match(user1, user2):
    chat_id = get_chat_id(user1, user2)
    
    if user1 not in matches_db:
        matches_db[user1] = []
    if user2 not in matches_db:
        matches_db[user2] = []
    
    if user2 not in matches_db[user1]:
        matches_db[user1].append(user2)
    if user1 not in matches_db[user2]:
        matches_db[user2].append(user1)
    
    if chat_id not in messages_db:
        messages_db[chat_id] = []
    
    # Add notification for match
    add_notification(user1, 'match', f"You matched with {user_profiles.get(user2, {}).get('full_name', 'someone')}")
    add_notification(user2, 'match', f"You matched with {user_profiles.get(user1, {}).get('full_name', 'someone')}")
    
    return True

def calculate_compatibility(user1_profile, user2_profile):
    """Calculate compatibility score between two users with safety checks"""
    score = 0
    
    if not user1_profile or not user2_profile:
        return 0
    
    # Interest matching (30 points)
    interests1 = user1_profile.get('interests', [])
    interests2 = user2_profile.get('interests', [])
    
    if interests1 and interests2 and isinstance(interests1, list) and isinstance(interests2, list):
        set1 = set(interests1)
        set2 = set(interests2)
        common = len(set1 & set2)
        total = len(set1 | set2)
        if total > 0:
            interest_score = (common / total) * 30
            score += interest_score
    
    # Age compatibility (20 points)
    age1 = user1_profile.get('age')
    age2 = user2_profile.get('age')
    
    if age1 and age2 and isinstance(age1, (int, float)) and isinstance(age2, (int, float)):
        age_diff = abs(age1 - age2)
        if age_diff <= 3:
            score += 20
        elif age_diff <= 5:
            score += 15
        elif age_diff <= 10:
            score += 10
        elif age_diff <= 15:
            score += 5
    
    # Location compatibility (15 points)
    loc1 = user1_profile.get('location', '')
    loc2 = user2_profile.get('location', '')
    
    if loc1 and loc2:
        city1 = loc1.split(',')[0].strip().lower() if ',' in loc1 else loc1.strip().lower()
        city2 = loc2.split(',')[0].strip().lower() if ',' in loc2 else loc2.strip().lower()
        if city1 and city2 and city1 == city2:
            score += 15
        elif ',' in loc1 and ',' in loc2:
            state1 = loc1.split(',')[1].strip().lower() if len(loc1.split(',')) > 1 else ''
            state2 = loc2.split(',')[1].strip().lower() if len(loc2.split(',')) > 1 else ''
            if state1 and state2 and state1 == state2:
                score += 8
    
    # Looking for compatibility (15 points)
    looking1 = user1_profile.get('looking_for', '')
    looking2 = user2_profile.get('looking_for', '')
    
    if looking1 and looking2 and looking1 == looking2:
        score += 15
    
    # Education compatibility (10 points)
    edu1 = user1_profile.get('education', '')
    edu2 = user2_profile.get('education', '')
    
    if edu1 and edu2 and edu1 == edu2:
        score += 10
    
    # Occupation similarity (10 points)
    occ1 = user1_profile.get('occupation', '')
    occ2 = user2_profile.get('occupation', '')
    
    if occ1 and occ2:
        occ1_words = occ1.split()
        occ2_words = occ2.split()
        if occ1_words and occ2_words and occ1_words[0] == occ2_words[0]:
            score += 10
    
    return min(int(score), 100)

def update_user_activity(email):
    user_activity[email] = {
        'last_active': datetime.now().isoformat(),
        'session_count': user_activity.get(email, {}).get('session_count', 0) + 1
    }

def add_notification(user_id, notif_type, message):
    """Add a notification for a user"""
    if user_id not in notifications_db:
        notifications_db[user_id] = []
    
    notifications_db[user_id].insert(0, {
        'id': len(notifications_db[user_id]) + 1,
        'type': notif_type,
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'read': False
    })
    
    # Keep only last 50 notifications
    notifications_db[user_id] = notifications_db[user_id][:50]

def format_time_ago(timestamp):
    if not timestamp:
        return 'Just now'
    
    try:
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 7:
            return dt.strftime('%b %d')
        elif diff.days > 0:
            return f'{diff.days} days ago'
        elif diff.seconds > 3600:
            return f'{diff.seconds // 3600} hours ago'
        elif diff.seconds > 60:
            return f'{diff.seconds // 60} minutes ago'
        else:
            return 'Just now'
    except:
        return 'Recently'

# Create sample profiles
def create_sample_profiles():
    sample_users = [
        {
            'email': 'tyrone.j@example.com',
            'full_name': 'Tyrone Johnson',
            'category': 'professional',
            'age': 29,
            'location': 'Atlanta, GA',
            'occupation': 'Software Engineer',
            'bio': 'Tech enthusiast who loves coding, basketball, and community service. Looking for someone with ambition and a kind heart.',
            'interests': ['Basketball', 'Coding', 'Community Service', 'Travel', 'Music'],
            'gender': 'Male',
            'looking_for': 'Long-term relationship',
            'height': "6'2\"",
            'education': "Master's Degree",
            'avatar_url': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=500&h=500&fit=crop',
            'verified_info': True
        },
        {
            'email': 'monique.w@example.com',
            'full_name': 'Monique Williams',
            'category': 'professional',
            'age': 27,
            'location': 'Houston, TX',
            'occupation': 'Marketing Manager',
            'bio': 'Ambitious marketing professional who loves fashion, fitness, and trying new restaurants.',
            'interests': ['Fashion', 'Fitness', 'Dining Out', 'Travel', 'Photography'],
            'gender': 'Female',
            'looking_for': 'Long-term relationship',
            'height': "5'6\"",
            'education': "Bachelor's Degree",
            'avatar_url': 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=500&h=500&fit=crop',
            'verified_info': True
        },
        {
            'email': 'darnell.s@example.com',
            'full_name': 'Darnell Smith',
            'category': 'fitness',
            'age': 26,
            'location': 'Charlotte, NC',
            'occupation': 'Personal Trainer',
            'bio': 'Fitness is my passion. Looking for someone who values health and wants to grow together.',
            'interests': ['Weightlifting', 'Nutrition', 'Hiking', 'Meditation', 'Basketball'],
            'gender': 'Male',
            'looking_for': 'Casual dating',
            'height': "5'10\"",
            'education': "Certified Trainer",
            'avatar_url': 'https://images.unsplash.com/photo-1506794778202-cad84cf45f1d?w=500&h=500&fit=crop',
            'verified_info': False
        },
        {
            'email': 'keisha.b@example.com',
            'full_name': 'Keisha Brown',
            'category': 'creative',
            'age': 25,
            'location': 'Baltimore, MD',
            'occupation': 'Graphic Designer',
            'bio': 'Creative soul who loves art, music festivals, and making people smile with my designs.',
            'interests': ['Drawing', 'Music Festivals', 'Design', 'Painting', 'Dancing'],
            'gender': 'Female',
            'looking_for': 'Friendship first',
            'height': "5'4\"",
            'education': "Bachelor's Degree",
            'avatar_url': 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=500&h=500&fit=crop',
            'verified_info': True
        },
        {
            'email': 'malik.t@example.com',
            'full_name': 'Malik Thomas',
            'category': 'student',
            'age': 22,
            'location': 'Washington, DC',
            'occupation': 'Law Student',
            'bio': 'Future lawyer who loves debate, reading, and giving back to the community.',
            'interests': ['Reading', 'Debate', 'Volunteering', 'Chess', 'Running'],
            'gender': 'Male',
            'looking_for': 'Casual dating',
            'height': "5'11\"",
            'education': "Law School",
            'avatar_url': 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=500&h=500&fit=crop',
            'verified_info': False
        },
        {
            'email': 'chantel.h@example.com',
            'full_name': 'Chantel Harris',
            'category': 'foodie',
            'age': 28,
            'location': 'New Orleans, LA',
            'occupation': 'Chef',
            'bio': 'I live to eat and eat to live! Looking for someone to explore the culinary world with.',
            'interests': ['Cooking', 'Food Blogging', 'Wine Tasting', 'Travel', 'Restaurants'],
            'gender': 'Female',
            'looking_for': 'Long-term relationship',
            'height': "5'5\"",
            'education': "Culinary Degree",
            'avatar_url': 'https://images.unsplash.com/photo-1489424731084-a5d8b219a5bb?w=500&h=500&fit=crop',
            'verified_info': True
        }
    ]
    
    if not users_db:
        for sample in sample_users:
            email = sample['email']
            users_db[email] = {
                'email': email,
                'password': generate_password_hash('password123'),
                'full_name': sample['full_name'],
                'category': sample['category'],
                'profile_complete': True,
                'created_at': datetime.now().isoformat()
            }
            
            user_profiles[email] = {
                'full_name': sample['full_name'],
                'age': sample['age'],
                'location': sample['location'],
                'occupation': sample['occupation'],
                'bio': sample['bio'],
                'interests': sample['interests'],
                'gender': sample['gender'],
                'looking_for': sample['looking_for'],
                'height': sample['height'],
                'education': sample['education'],
                'avatar_url': sample['avatar_url'],
                'verified_info': sample.get('verified_info', False),
                'photos': []
            }

create_sample_profiles()

# Google OAuth Routes
@app.route('/auth/google')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)
        
        email = user_info.get('email')
        full_name = user_info.get('name', email.split('@')[0])
        google_id = user_info.get('sub')
        
        if email in users_db:
            session['user_id'] = email
            session['user_name'] = users_db[email]['full_name']
            session['category'] = users_db[email].get('category')
            session['auth_provider'] = 'google'
            
            if users_db[email].get('profile_complete'):
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('category_select'))
        else:
            users_db[email] = {
                'email': email,
                'full_name': full_name,
                'google_id': google_id,
                'auth_provider': 'google',
                'category': None,
                'profile_complete': False,
                'created_at': datetime.now().isoformat()
            }
            
            session['user_id'] = email
            session['user_name'] = full_name
            session['auth_provider'] = 'google'
            
            return redirect(url_for('category_select'))
            
    except Exception as e:
        print(f"Google auth error: {e}")
        return redirect(url_for('login'))

# Authentication Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = users_db.get(email)
        if user and user.get('password') and check_password_hash(user['password'], password):
            session.permanent = True
            session['user_id'] = email
            session['user_name'] = user['full_name']
            session['category'] = user.get('category')
            
            if user.get('profile_complete'):
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('category_select'))
        else:
            return render_template('login.html', error='Invalid email or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        if email in users_db:
            return render_template('register.html', error='Email already registered')
        
        users_db[email] = {
            'email': email,
            'password': generate_password_hash(password),
            'full_name': full_name,
            'category': None,
            'profile_complete': False,
            'created_at': datetime.now().isoformat()
        }
        
        session['user_id'] = email
        session['user_name'] = full_name
        
        return redirect(url_for('category_select'))
    
    return render_template('register.html')

@app.route('/category-select', methods=['GET', 'POST'])
@login_required
def category_select():
    if request.method == 'POST':
        category = request.form.get('category')
        
        if category in CATEGORIES:
            users_db[session['user_id']]['category'] = category
            return redirect(url_for('setup_profile'))
        else:
            return render_template('category_select.html', categories=CATEGORIES, error='Please select a category')
    
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
            'dating_goals': request.form.get('dating_goals'),
            'deal_breakers': request.form.get('deal_breakers'),
            'avatar_url': '/static/uploads/avatars/default-avatar.jpg',
            'verified_info': False,
            'photos': []
        }
        
        custom_interests = request.form.get('custom_interests', '')
        if custom_interests:
            custom_list = [i.strip() for i in custom_interests.split(',') if i.strip()]
            profile_data['interests'].extend(custom_list)
        
        user_profiles[session['user_id']] = profile_data
        users_db[session['user_id']]['profile_complete'] = True
        
        return redirect(url_for('dashboard'))
    
    user_category = users_db[session['user_id']].get('category', 'no_category')
    
    category_suggestions = {
        'student': ['Studying', 'Part-time job', 'Networking', 'Campus events', 'Late night coffee', 'Group projects'],
        'gamer': ['PC Gaming', 'Console Gaming', 'MMORPG', 'Esports', 'Streaming', 'Game development', 'Retro games'],
        'professional': ['Career growth', 'Networking', 'Work-life balance', 'Business travel', 'Mentorship'],
        'fitness': ['Gym workouts', 'Running', 'Yoga', 'Hiking', 'Nutrition', 'Marathon training', 'Crossfit'],
        'creative': ['Drawing', 'Painting', 'Writing', 'Music production', 'Photography', 'Video editing', 'Design'],
        'traveler': ['Backpacking', 'Road trips', 'Beach vacations', 'Mountain hiking', 'Cultural experiences'],
        'foodie': ['Cooking', 'Baking', 'Restaurant hopping', 'Wine tasting', 'Food blogging', 'International cuisine'],
        'no_category': ['Movies', 'Music', 'Reading', 'Sports', 'Technology', 'Art', 'Dancing']
    }
    
    suggested_interests = category_suggestions.get(user_category, category_suggestions['no_category'])
    
    return render_template('setup_profile.html', 
                         category=CATEGORIES.get(user_category, CATEGORIES['no_category']),
                         suggested_interests=suggested_interests)

@app.route('/dashboard')
@login_required
def dashboard():
    user_data = users_db.get(session['user_id'], {})
    profile_data = user_profiles.get(session['user_id'], {})
    
    # Get recent matches
    recent_matches = []
    for match_email in matches_db.get(session['user_id'], [])[:5]:
        profile = user_profiles.get(match_email, {})
        recent_matches.append({
            'email': match_email,
            'name': profile.get('full_name', 'Unknown'),
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
            'location': profile.get('location', 'Unknown')
        })
    
    # Get suggestions based on compatibility
    suggestions = []
    current_profile = profile_data
    passed_users = passed_users_db.get(session['user_id'], [])
    
    for email, user in users_db.items():
        if email != session['user_id'] and user.get('profile_complete'):
            if email not in passed_users:
                profile = user_profiles.get(email, {})
                if profile:
                    compatibility = calculate_compatibility(current_profile, profile)
                    if compatibility > 60:
                        suggestions.append({
                            'email': email,
                            'name': profile.get('full_name', 'Unknown'),
                            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
                            'location': profile.get('location', 'Unknown'),
                            'compatibility': compatibility,
                            'verified': profile.get('verified_info', False)
                        })
    
    suggestions.sort(key=lambda x: x['compatibility'], reverse=True)
    
    stats = {
        'profile_views': len(likes_db.get(session['user_id'], [])),
        'likes_received': len([k for k, v in likes_db.items() if session['user_id'] in v]),
        'matches_count': len(matches_db.get(session['user_id'], []))
    }
    
    completion = calculate_completion_profile(profile_data)
    
    return render_template('dashboard.html', 
                         user=profile_data,
                         stats=stats,
                         recent_matches=recent_matches,
                         suggestions=suggestions[:5],
                         completion_percentage=completion)

@app.route('/profile')
@login_required
def profile():
    user_data = users_db.get(session['user_id'], {})
    profile_data = user_profiles.get(session['user_id'], {})
    category = user_data.get('category', 'no_category')
    
    completion = calculate_completion_profile(profile_data)
    
    stats = {
        'profile_views': len(likes_db.get(session['user_id'], [])),
        'likes_received': len([k for k, v in likes_db.items() if session['user_id'] in v]),
        'matches_count': len(matches_db.get(session['user_id'], []))
    }
    
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
    if email not in users_db:
        return redirect(url_for('discover'))
    
    user_data = users_db.get(email, {})
    profile_data = user_profiles.get(email, {})
    category = user_data.get('category', 'no_category')
    
    is_match = email in matches_db.get(session['user_id'], [])
    
    return render_template('view_profile.html', 
                         user=profile_data,
                         user_email=email,
                         category=CATEGORIES.get(category, CATEGORIES['no_category']),
                         is_match=is_match)

@app.route('/discover')
@login_required
def discover():
    other_users = []
    passed_users = passed_users_db.get(session['user_id'], [])
    current_user_profile = user_profiles.get(session['user_id'], {})
    
    for email, user in users_db.items():
        if email != session['user_id'] and user.get('profile_complete') and email not in passed_users:
            profile = user_profiles.get(email, {})
            if not profile:
                continue
            
            has_liked = session['user_id'] in likes_db.get(email, [])
            is_match = email in matches_db.get(session['user_id'], [])
            
            try:
                compatibility = calculate_compatibility(current_user_profile, profile)
            except Exception:
                compatibility = 50
            
            other_users.append({
                'email': email,
                'name': profile.get('full_name', 'Unknown'),
                'age': profile.get('age', '?'),
                'location': profile.get('location', 'Unknown'),
                'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
                'bio': profile.get('bio', '')[:150] if profile.get('bio') else '',
                'interests': profile.get('interests', [])[:3],
                'category': CATEGORIES.get(user.get('category', 'no_category'), {}).get('name', 'No Category'),
                'has_liked': has_liked,
                'is_match': is_match,
                'compatibility': compatibility,
                'verified': profile.get('verified_info', False)
            })
    
    other_users.sort(key=lambda x: x.get('compatibility', 0), reverse=True)
    
    return render_template('discover.html', users=other_users)

@app.route('/api/pass', methods=['POST'])
@login_required
def pass_user():
    data = request.json
    passed_email = data.get('email')
    
    if not passed_email or passed_email == session['user_id']:
        return jsonify({'success': False, 'message': 'Invalid user'})
    
    if session['user_id'] not in passed_users_db:
        passed_users_db[session['user_id']] = []
    
    if passed_email not in passed_users_db[session['user_id']]:
        passed_users_db[session['user_id']].append(passed_email)
        return jsonify({'success': True, 'message': 'User passed'})
    
    return jsonify({'success': False, 'message': 'Already passed this user'})

@app.route('/api/like', methods=['POST'])
@login_required
def like_user():
    data = request.json
    liked_email = data.get('email')
    
    if not liked_email or liked_email == session['user_id']:
        return jsonify({'success': False, 'message': 'Invalid user'})
    
    if session['user_id'] in passed_users_db and liked_email in passed_users_db[session['user_id']]:
        passed_users_db[session['user_id']].remove(liked_email)
    
    if session['user_id'] not in likes_db:
        likes_db[session['user_id']] = []
    
    if liked_email not in likes_db[session['user_id']]:
        likes_db[session['user_id']].append(liked_email)
        
        is_match = session['user_id'] in likes_db.get(liked_email, [])
        
        if is_match:
            create_match(session['user_id'], liked_email)
            return jsonify({'success': True, 'message': 'It is a match!', 'is_match': True})
        
        add_notification(liked_email, 'like', f"{user_profiles.get(session['user_id'], {}).get('full_name', 'Someone')} liked your profile")
        return jsonify({'success': True, 'message': 'Liked successfully', 'is_match': False})
    
    return jsonify({'success': False, 'message': 'Already liked this user'})

@app.route('/api/unlike', methods=['POST'])
@login_required
def unlike_user():
    data = request.json
    unliked_email = data.get('email')
    
    if session['user_id'] in likes_db and unliked_email in likes_db[session['user_id']]:
        likes_db[session['user_id']].remove(unliked_email)
        return jsonify({'success': True, 'message': 'Unliked successfully'})
    
    return jsonify({'success': False, 'message': 'Not liked yet'})

@app.route('/matches')
@login_required
def matches():
    matches_list = []
    current_user_profile = user_profiles.get(session['user_id'], {})
    
    for match_email in matches_db.get(session['user_id'], []):
        profile = user_profiles.get(match_email, {})
        if not profile:
            continue
            
        last_message = None
        
        chat_id = get_chat_id(session['user_id'], match_email)
        if chat_id in messages_db and messages_db[chat_id]:
            last_message = messages_db[chat_id][-1]
        
        try:
            compatibility = calculate_compatibility(current_user_profile, profile)
        except Exception:
            compatibility = 50
        
        matches_list.append({
            'email': match_email,
            'name': profile.get('full_name', 'Unknown'),
            'age': profile.get('age', '?'),
            'location': profile.get('location', 'Unknown'),
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
            'last_message': last_message,
            'compatibility': compatibility,
            'verified': profile.get('verified_info', False)
        })
    
    matches_list.sort(key=lambda x: x.get('compatibility', 0), reverse=True)
    
    return render_template('matches.html', matches=matches_list)

@app.route('/messages')
@login_required
def messages():
    selected_match = request.args.get('match')
    matches_list = []
    current_messages = []
    
    for match_email in matches_db.get(session['user_id'], []):
        profile = user_profiles.get(match_email, {})
        last_message = None
        
        chat_id = get_chat_id(session['user_id'], match_email)
        if chat_id in messages_db and messages_db[chat_id]:
            last_message = messages_db[chat_id][-1]
        
        matches_list.append({
            'email': match_email,
            'name': profile.get('full_name', 'Unknown'),
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
            'last_message': last_message,
            'verified': profile.get('verified_info', False)
        })
    
    if selected_match and selected_match in matches_db.get(session['user_id'], []):
        chat_id = get_chat_id(session['user_id'], selected_match)
        if chat_id in messages_db:
            current_messages = messages_db[chat_id]
        
        selected_profile = user_profiles.get(selected_match, {})
        selected_match_info = {
            'email': selected_match,
            'name': selected_profile.get('full_name', 'Unknown'),
            'avatar_url': selected_profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
            'verified': selected_profile.get('verified_info', False)
        }
    else:
        selected_match_info = None
    
    return render_template('messages.html', 
                         matches=matches_list, 
                         current_messages=current_messages,
                         selected_match=selected_match_info,
                         user_email=session['user_id'])

@app.route('/api/send-message', methods=['POST'])
@login_required
def send_message():
    data = request.json
    to_email = data.get('to_email')
    message_text = data.get('message')
    
    if not to_email or not message_text:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    if to_email not in matches_db.get(session['user_id'], []):
        return jsonify({'success': False, 'message': 'You can only message your matches'})
    
    chat_id = get_chat_id(session['user_id'], to_email)
    
    if chat_id not in messages_db:
        messages_db[chat_id] = []
    
    message = {
        'from': session['user_id'],
        'to': to_email,
        'text': message_text,
        'timestamp': datetime.now().isoformat(),
        'read': False
    }
    
    messages_db[chat_id].append(message)
    add_notification(to_email, 'message', f"New message from {user_profiles.get(session['user_id'], {}).get('full_name', 'Someone')}")
    
    return jsonify({'success': True, 'message': 'Message sent', 'message_data': message})

@app.route('/api/get-messages', methods=['GET'])
@login_required
def get_messages():
    match_email = request.args.get('match')
    
    if not match_email or match_email not in matches_db.get(session['user_id'], []):
        return jsonify({'success': False, 'messages': []})
    
    chat_id = get_chat_id(session['user_id'], match_email)
    messages = messages_db.get(chat_id, [])
    
    return jsonify({'success': True, 'messages': messages})

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    try:
        data = request.json
        profile_data = user_profiles.get(session['user_id'], {})
        
        profile_data.update({
            'full_name': data.get('full_name', profile_data.get('full_name')),
            'age': data.get('age', profile_data.get('age')),
            'location': data.get('location', profile_data.get('location')),
            'occupation': data.get('occupation', profile_data.get('occupation')),
            'bio': data.get('bio', profile_data.get('bio')),
            'interests': data.get('interests', profile_data.get('interests', [])),
            'gender': data.get('gender', profile_data.get('gender')),
            'looking_for': data.get('looking_for', profile_data.get('looking_for')),
            'height': data.get('height', profile_data.get('height')),
            'education': data.get('education', profile_data.get('education'))
        })
        
        user_profiles[session['user_id']] = profile_data
        return jsonify({'success': True, 'message': 'Profile updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

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
            filename = f"avatar_{session['user_id']}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', filename)
            
            img = process_uploaded_image(file, AVATAR_SIZE, is_avatar=True)
            save_image_with_quality(img, filepath, file.filename)
            
            if session['user_id'] in user_profiles:
                user_profiles[session['user_id']]['avatar_url'] = f'/static/uploads/avatars/{filename}'
            
            return jsonify({'success': True, 'message': 'Avatar uploaded successfully', 'url': f'/static/uploads/avatars/{filename}'})
        
        return jsonify({'success': False, 'message': 'File type not allowed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    try:
        if 'photo' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if file and allowed_file(file.filename):
            filename = f"photo_{session['user_id']}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename)
            
            img = process_uploaded_image(file, PHOTO_SIZE, is_avatar=False)
            save_image_with_quality(img, filepath, file.filename)
            
            photo_url = f'/static/uploads/photos/{filename}'
            if session['user_id'] in user_profiles:
                if 'photos' not in user_profiles[session['user_id']]:
                    user_profiles[session['user_id']]['photos'] = []
                user_profiles[session['user_id']]['photos'].append(photo_url)
            
            return jsonify({'success': True, 'message': 'Photo uploaded successfully', 'url': photo_url})
        
        return jsonify({'success': False, 'message': 'File type not allowed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/notifications')
@login_required
def notifications():
    user_notifications = notifications_db.get(session['user_id'], [])
    
    for notif in user_notifications:
        notif['time_ago'] = format_time_ago(notif.get('timestamp', ''))
    
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/api/mark-notification-read', methods=['POST'])
@login_required
def mark_notification_read():
    data = request.json
    notif_id = data.get('id')
    
    if session['user_id'] in notifications_db:
        for notif in notifications_db[session['user_id']]:
            if notif.get('id') == notif_id:
                notif['read'] = True
                break
    
    return jsonify({'success': True})

@app.route('/verification')
@login_required
def verification():
    profile_data = user_profiles.get(session['user_id'], {})
    return render_template('verification.html', user=profile_data)

@app.route('/api/submit-verification', methods=['POST'])
@login_required
def submit_verification():
    try:
        if 'id_document' not in request.files or 'selfie' not in request.files:
            return jsonify({'success': False, 'message': 'Missing required files'})
        
        id_doc = request.files['id_document']
        selfie = request.files['selfie']
        additional_info = request.form.get('additional_info', '')
        
        request_id = f"{session['user_id']}_{datetime.now().timestamp()}"
        verification_requests[request_id] = {
            'user_id': session['user_id'],
            'status': 'pending',
            'submitted_at': datetime.now().isoformat(),
            'additional_info': additional_info
        }
        
        add_notification(session['user_id'], 'verification', 'Your verification request has been submitted. We will review it within 48 hours.')
        
        return jsonify({'success': True, 'message': 'Verification request submitted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/feedback')
@login_required
def feedback():
    return render_template('feedback.html')

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
def submit_feedback():
    try:
        feedback_type = request.form.get('type')
        subject = request.form.get('subject')
        message_text = request.form.get('message')
        contact_permission = request.form.get('contact_permission') == 'true'
        
        feedback_id = f"{session['user_id']}_{datetime.now().timestamp()}"
        feedback_db[feedback_id] = {
            'user_id': session['user_id'],
            'type': feedback_type,
            'subject': subject,
            'message': message_text,
            'contact_permission': contact_permission,
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify({'success': True, 'message': 'Feedback submitted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    user_data = users_db.get(session['user_id'], {})
    profile_data = user_profiles.get(session['user_id'], {})
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_preferences':
            preferences = {
                'age_min': int(request.form.get('age_min', 18)),
                'age_max': int(request.form.get('age_max', 100)),
                'distance_max': int(request.form.get('distance_max', 50)),
                'looking_for': request.form.get('looking_for_pref', ''),
                'show_me': request.form.get('show_me', 'Everyone')
            }
            
            if 'preferences' not in user_data:
                user_data['preferences'] = {}
            user_data['preferences'].update(preferences)
            users_db[session['user_id']] = user_data
            
            return jsonify({'success': True, 'message': 'Preferences updated'})
            
        elif action == 'update_notifications':
            notifications = {
                'email_likes': 'email_likes' in request.form,
                'email_messages': 'email_messages' in request.form,
                'email_matches': 'email_matches' in request.form,
                'push_likes': 'push_likes' in request.form,
                'push_messages': 'push_messages' in request.form,
                'push_matches': 'push_matches' in request.form
            }
            
            if 'notifications' not in user_data:
                user_data['notifications'] = {}
            user_data['notifications'].update(notifications)
            users_db[session['user_id']] = user_data
            
            return jsonify({'success': True, 'message': 'Notification settings updated'})
            
        elif action == 'update_privacy':
            privacy = {
                'show_age': 'show_age' in request.form,
                'show_distance': 'show_distance' in request.form,
                'show_online_status': 'show_online_status' in request.form,
                'allow_messages_from_matches': 'allow_messages_from_matches' in request.form
            }
            
            if 'privacy' not in user_data:
                user_data['privacy'] = {}
            user_data['privacy'].update(privacy)
            users_db[session['user_id']] = user_data
            
            return jsonify({'success': True, 'message': 'Privacy settings updated'})
            
        elif action == 'change_password':
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if user_data.get('password') and check_password_hash(user_data['password'], current_password):
                if new_password == confirm_password:
                    user_data['password'] = generate_password_hash(new_password)
                    users_db[session['user_id']] = user_data
                    return jsonify({'success': True, 'message': 'Password changed successfully'})
                else:
                    return jsonify({'success': False, 'message': 'New passwords do not match'})
            else:
                return jsonify({'success': False, 'message': 'Current password is incorrect'})
        
        elif action == 'delete_account':
            email = session['user_id']
            if email in users_db:
                del users_db[email]
                if email in user_profiles:
                    del user_profiles[email]
                session.clear()
                return jsonify({'success': True, 'message': 'Account deleted', 'redirect': url_for('login')})
        
        return jsonify({'success': False, 'message': 'Invalid action'})
    
    preferences = user_data.get('preferences', {
        'age_min': 18,
        'age_max': 60,
        'distance_max': 50,
        'looking_for': '',
        'show_me': 'Everyone'
    })
    
    notifications_setting = user_data.get('notifications', {
        'email_likes': True,
        'email_messages': True,
        'email_matches': True,
        'push_likes': True,
        'push_messages': True,
        'push_matches': True
    })
    
    privacy = user_data.get('privacy', {
        'show_age': True,
        'show_distance': True,
        'show_online_status': True,
        'allow_messages_from_matches': True
    })
    
    return render_template('settings.html', 
                         user=profile_data,
                         user_email=session['user_id'],
                         preferences=preferences,
                         notifications=notifications_setting,
                         privacy=privacy)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)