# ============================================
# IMPORTS - Loading required libraries
# ============================================

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
# Flask: The web framework
# render_template: Renders HTML files
# request: Handles incoming data from forms and APIs
# jsonify: Converts Python dicts to JSON responses
# session: Stores user data between requests (like being logged in)
# redirect: Sends users to different pages
# url_for: Generates URLs for routes

from werkzeug.utils import secure_filename
# Secures uploaded filenames to prevent hacking

from werkzeug.security import generate_password_hash, check_password_hash
# generate_password_hash: Turns passwords into secure hashes
# check_password_hash: Verifies a password against its hash

from PIL import Image, ImageEnhance, ImageFilter
# PIL (Pillow): Handles image processing like resizing and enhancing

import os
# Operating system interface - for file paths and environment variables

import json
# Handles JSON data

from datetime import datetime, timedelta
# datetime: Gets current time
# timedelta: Calculates time differences (like "7 days from now")

from functools import wraps
# Creates decorators that wrap functions (like login_required)

from authlib.integrations.flask_client import OAuth
# Handles Google OAuth (sign in with Google)

import secrets
# Generates secure random tokens

import re
# Regular expressions - for pattern matching in text

from collections import defaultdict
# Creates dictionaries with default values

import io
# Handles binary data streams

from dotenv import load_dotenv
# Loads environment variables from .env file

# ============================================
# LOAD ENVIRONMENT VARIABLES
# ============================================

load_dotenv()  # Reads the .env file and loads variables into os.environ

# ============================================
# FLASK APP CONFIGURATION
# ============================================

app = Flask(__name__)  # Creates the Flask application
app.secret_key = 'heartsync-secret-key-2024-change-this-in-production'  # Used to encrypt session data
app.permanent_session_lifetime = timedelta(days=7)  # Users stay logged in for 7 days

# ============================================
# GOOGLE OAUTH SETUP
# ============================================

# Get Google credentials from environment variables (for security)
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')

# Check if credentials were found
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    print("WARNING: Google OAuth credentials not found. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")

oauth = OAuth(app)  # Initialize OAuth
google = oauth.register(
    name='google',  # Name for this OAuth provider
    client_id=GOOGLE_CLIENT_ID,  # Your Google app ID
    client_secret=GOOGLE_CLIENT_SECRET,  # Your Google app secret
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',  # Google's config URL
    client_kwargs={'scope': 'openid email profile'}  # What info to request from Google
)

# ============================================
# FILE UPLOAD CONFIGURATION
# ============================================

UPLOAD_FOLDER = 'static/uploads'  # Where uploaded files are stored
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tiff'}  # Allowed image types
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # Max file size: 50 Megabytes

# Image quality settings
AVATAR_SIZE = (500, 500)  # Profile pictures: 500x500 pixels
PHOTO_SIZE = (1200, 1200)  # Gallery photos: 1200x1200 pixels
JPEG_QUALITY = 95  # JPEG quality (1-100, higher is better)
PNG_QUALITY = 95  # PNG quality

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Create upload folders if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/uploads/avatars', exist_ok=True)
os.makedirs('static/uploads/photos', exist_ok=True)

# ============================================
# USER CATEGORIES
# ============================================

CATEGORIES = {
    'student': {'name': 'Student', 'icon': '(S)', 'color': 'blue', 'description': 'Currently studying'},
    'gamer': {'name': 'Gamer', 'icon': '(G)', 'color': 'green', 'description': 'Passionate about gaming'},
    'professional': {'name': 'Professional', 'icon': '(P)', 'color': 'purple', 'description': 'Career-focused'},
    'fitness': {'name': 'Fitness Enthusiast', 'icon': '(F)', 'color': 'orange', 'description': 'Active lifestyle'},
    'creative': {'name': 'Creative', 'icon': '(C)', 'color': 'pink', 'description': 'Artist or musician'},
    'traveler': {'name': 'Traveler', 'icon': '(T)', 'color': 'teal', 'description': 'Love exploring'},
    'foodie': {'name': 'Foodie', 'icon': '(Fd)', 'color': 'red', 'description': 'Passionate about food'},
    'no_category': {'name': 'No Category', 'icon': '(N)', 'color': 'gray', 'description': 'No category selected'}
}

# ============================================
# DATABASES (In-memory storage)
# ============================================

users_db = {}          # Stores user account info {email: {name, password, etc}}
user_profiles = {}     # Stores user profile details {email: {age, bio, interests, etc}}
likes_db = {}          # Stores likes {from_email: [to_email, to_email2]}
matches_db = {}        # Stores matches {email: [matched_email, matched_email2]}
messages_db = {}       # Stores messages {chat_id: [{from, to, text, timestamp}]}
passed_users_db = {}   # Stores users you passed on {email: [passed_email, passed_email2]}
user_activity = {}     # Stores last active times
user_reports = {}      # Stores user reports
blocked_users = {}     # Stores blocked users
verification_requests = {}  # Stores ID verification requests
user_preferences = {}  # Stores user settings
notifications_db = {}  # Stores notifications for each user
feedback_db = {}       # Stores user feedback

# ============================================
# HELPER FUNCTIONS
# ============================================

def allowed_file(filename):
    """Check if uploaded file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def enhance_image_quality(image):
    """Make images look better with sharpening and color correction"""
    try:
        # Convert to RGB if needed (removes transparency)
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        # Sharpen the image
        image = image.filter(ImageFilter.UnsharpMask(radius=1, percent=100, threshold=0))
        
        # Enhance colors by 5%
        enhancer = ImageEnhance.Color(image)
        image = enhancer.enhance(1.05)
        
        # Enhance contrast by 2%
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.02)
        
        return image
    except Exception as e:
        print(f"Image enhancement error: {e}")
        return image

def process_uploaded_image(file, target_size, is_avatar=True):
    """Process uploaded images: crop, resize, and enhance quality"""
    try:
        img = Image.open(file)  # Open the image file
        
        # Convert to RGB if needed
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        
        original_width, original_height = img.size
        
        # For avatars, crop to a perfect square (center crop)
        if is_avatar:
            min_dim = min(original_width, original_height)
            left = (original_width - min_dim) / 2
            top = (original_height - min_dim) / 2
            right = (original_width + min_dim) / 2
            bottom = (original_height + min_dim) / 2
            img = img.crop((left, top, right, bottom))
        
        # Resize to target dimensions using high quality algorithm
        img = img.resize(target_size, Image.Resampling.LANCZOS)
        
        # Apply quality enhancements
        img = enhance_image_quality(img)
        
        return img
    except Exception as e:
        print(f"Image processing error: {e}")
        return Image.open(file).resize(target_size, Image.Resampling.LANCZOS)

def save_image_with_quality(img, filepath, original_filename):
    """Save image with optimal quality settings for each file type"""
    try:
        # Get file extension
        ext = original_filename.rsplit('.', 1)[1].lower()
        
        # Save with format-specific quality settings
        if ext in ['jpg', 'jpeg']:
            img.save(filepath, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True)
        elif ext == 'png':
            img.save(filepath, 'PNG', optimize=True, compress_level=6)
        elif ext == 'webp':
            img.save(filepath, 'WEBP', quality=JPEG_QUALITY, method=6)
        else:
            img.save(filepath, quality=JPEG_QUALITY, optimize=True)
        
        # Create a smaller thumbnail for faster loading
        thumbnail_path = filepath.replace('.', '_thumb.')
        thumbnail = img.copy()
        thumbnail.thumbnail((150, 150), Image.Resampling.LANCZOS)
        
        # Save thumbnail
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
    """Decorator that requires users to be logged in to access a page"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If user is not logged in (no user_id in session), redirect to login
        if 'user_id' not in session:
            return redirect(url_for('login'))
        # Update their last activity time
        update_user_activity(session['user_id'])
        return f(*args, **kwargs)
    return decorated_function

def calculate_completion_profile(profile):
    """Calculate what percentage of the profile is filled out"""
    if not profile:
        return 0
    
    completion = 0
    total_fields = 15
    
    # Check each field and add points
    if profile.get('full_name'): completion += 1
    if profile.get('age'): completion += 1
    if profile.get('location'): completion += 1
    if profile.get('occupation'): completion += 1
    if profile.get('bio') and len(profile['bio']) > 50: completion += 2  # Extra points for longer bio
    elif profile.get('bio'): completion += 1
    if profile.get('interests') and len(profile['interests']) >= 3: completion += 2  # Extra for 3+ interests
    elif profile.get('interests'): completion += 1
    if profile.get('gender'): completion += 1
    if profile.get('looking_for'): completion += 1
    if profile.get('height'): completion += 1
    if profile.get('education'): completion += 1
    if profile.get('avatar_url') and profile['avatar_url'] != '/static/uploads/avatars/default-avatar.jpg': completion += 1
    if profile.get('verified_info'): completion += 1
    if profile.get('dating_goals'): completion += 1
    
    # Return percentage
    return int((completion / total_fields) * 100)

def get_chat_id(user1, user2):
    """Create a unique ID for a chat between two users (sorted so it's consistent)"""
    return '_'.join(sorted([user1, user2]))

def create_match(user1, user2):
    """Create a match between two users and initialize their chat"""
    chat_id = get_chat_id(user1, user2)
    
    # Add each user to the other's matches list
    if user1 not in matches_db:
        matches_db[user1] = []
    if user2 not in matches_db:
        matches_db[user2] = []
    
    if user2 not in matches_db[user1]:
        matches_db[user1].append(user2)
    if user1 not in matches_db[user2]:
        matches_db[user2].append(user1)
    
    # Create chat room if it doesn't exist
    if chat_id not in messages_db:
        messages_db[chat_id] = []
    
    # Send notifications to both users
    add_notification(user1, 'match', f"You matched with {user_profiles.get(user2, {}).get('full_name', 'someone')}")
    add_notification(user2, 'match', f"You matched with {user_profiles.get(user1, {}).get('full_name', 'someone')}")
    
    return True

def calculate_compatibility(user1_profile, user2_profile):
    """Calculate how compatible two users are (0-100 score)"""
    score = 0
    
    if not user1_profile or not user2_profile:
        return 0
    
    # Interest matching (up to 30 points)
    interests1 = user1_profile.get('interests', [])
    interests2 = user2_profile.get('interests', [])
    
    if interests1 and interests2:
        set1 = set(interests1)
        set2 = set(interests2)
        common = len(set1 & set2)  # Interests they share
        total = len(set1 | set2)    # Total unique interests
        if total > 0:
            interest_score = (common / total) * 30  # Percentage of shared interests
            score += interest_score
    
    # Age compatibility (up to 20 points)
    age1 = user1_profile.get('age')
    age2 = user2_profile.get('age')
    
    if age1 and age2:
        age_diff = abs(age1 - age2)
        if age_diff <= 3:
            score += 20
        elif age_diff <= 5:
            score += 15
        elif age_diff <= 10:
            score += 10
        elif age_diff <= 15:
            score += 5
    
    # Location compatibility (up to 15 points)
    loc1 = user1_profile.get('location', '')
    loc2 = user2_profile.get('location', '')
    
    if loc1 and loc2:
        city1 = loc1.split(',')[0].strip().lower() if ',' in loc1 else loc1.strip().lower()
        city2 = loc2.split(',')[0].strip().lower() if ',' in loc2 else loc2.strip().lower()
        if city1 and city2 and city1 == city2:
            score += 15  # Same city
        elif ',' in loc1 and ',' in loc2:
            state1 = loc1.split(',')[1].strip().lower()
            state2 = loc2.split(',')[1].strip().lower()
            if state1 == state2:
                score += 8  # Same state
    
    # Looking for compatibility (up to 15 points)
    looking1 = user1_profile.get('looking_for', '')
    looking2 = user2_profile.get('looking_for', '')
    if looking1 and looking2 and looking1 == looking2:
        score += 15
    
    # Education compatibility (up to 10 points)
    edu1 = user1_profile.get('education', '')
    edu2 = user2_profile.get('education', '')
    if edu1 and edu2 and edu1 == edu2:
        score += 10
    
    # Occupation similarity (up to 10 points)
    occ1 = user1_profile.get('occupation', '')
    occ2 = user2_profile.get('occupation', '')
    if occ1 and occ2:
        occ1_words = occ1.split()
        occ2_words = occ2.split()
        if occ1_words and occ2_words and occ1_words[0] == occ2_words[0]:
            score += 10
    
    # Cap at 100
    return min(int(score), 100)

def update_user_activity(email):
    """Record when a user was last active"""
    user_activity[email] = {
        'last_active': datetime.now().isoformat(),
        'session_count': user_activity.get(email, {}).get('session_count', 0) + 1
    }

def add_notification(user_id, notif_type, message):
    """Add a notification to a user's inbox"""
    if user_id not in notifications_db:
        notifications_db[user_id] = []
    
    # Add new notification at the beginning (most recent first)
    notifications_db[user_id].insert(0, {
        'id': len(notifications_db[user_id]) + 1,
        'type': notif_type,  # 'like', 'match', 'message', 'verification'
        'message': message,
        'timestamp': datetime.now().isoformat(),
        'read': False
    })
    
    # Keep only the last 50 notifications to save memory
    notifications_db[user_id] = notifications_db[user_id][:50]

def format_time_ago(timestamp):
    """Convert a timestamp to a human-readable "time ago" string"""
    if not timestamp:
        return 'Just now'
    
    try:
        dt = datetime.fromisoformat(timestamp)
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 7:
            return dt.strftime('%b %d')  # "Jan 15"
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

# ============================================
# CREATE SAMPLE PROFILES (for testing)
# ============================================

def create_sample_profiles():
    """Create sample user profiles for testing the app"""
    sample_users = [
        {
            'email': 'tyrone.j@example.com',
            'full_name': 'Tyrone Johnson',
            'category': 'professional',
            'age': 29,
            'location': 'Atlanta, GA',
            'occupation': 'Software Engineer',
            'bio': 'Tech enthusiast who loves coding and basketball.',
            'interests': ['Basketball', 'Coding', 'Travel', 'Music'],
            'gender': 'Male',
            'looking_for': 'Long-term relationship',
            'height': "6'2\"",
            'education': "Master's Degree",
            'avatar_url': 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=500&h=500&fit=crop',
            'verified_info': True
        },
        # More sample users...
    ]
    
    # Only add sample users if database is empty
    if not users_db:
        for sample in sample_users:
            email = sample['email']
            # Add to users database
            users_db[email] = {
                'email': email,
                'password': generate_password_hash('password123'),  # Default password
                'full_name': sample['full_name'],
                'category': sample['category'],
                'profile_complete': True,
                'created_at': datetime.now().isoformat()
            }
            # Add to profiles database
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

# Call this function to create sample profiles
create_sample_profiles()

# ============================================
# GOOGLE OAUTH ROUTES
# ============================================

@app.route('/auth/google')
def google_login():
    """Send user to Google's login page"""
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/auth/google/callback')
def google_callback():
    """Handle the callback from Google after user logs in"""
    try:
        # Get user info from Google
        token = google.authorize_access_token()
        user_info = google.parse_id_token(token)
        
        email = user_info.get('email')
        full_name = user_info.get('name', email.split('@')[0])
        google_id = user_info.get('sub')
        
        # Check if user exists in our database
        if email in users_db:
            # Existing user - log them in
            session['user_id'] = email
            session['user_name'] = users_db[email]['full_name']
            session['category'] = users_db[email].get('category')
            session['auth_provider'] = 'google'
            
            if users_db[email].get('profile_complete'):
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('category_select'))
        else:
            # New user - create account
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

# ============================================
# AUTHENTICATION ROUTES
# ============================================

@app.route('/')
def index():
    """Home page - redirect to dashboard if logged in, else login"""
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - handles email/password login"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = users_db.get(email)
        # Verify password
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
    """Registration page - create new account"""
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        
        # Check if email already exists
        if email in users_db:
            return render_template('register.html', error='Email already registered')
        
        # Create new user
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
    """Page where users select their category (student, gamer, etc)"""
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
    """Profile setup wizard - collect user information"""
    if request.method == 'POST':
        # Collect all profile data from the form
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
        
        # Handle custom interests (comma-separated)
        custom_interests = request.form.get('custom_interests', '')
        if custom_interests:
            custom_list = [i.strip() for i in custom_interests.split(',') if i.strip()]
            profile_data['interests'].extend(custom_list)
        
        # Save profile
        user_profiles[session['user_id']] = profile_data
        users_db[session['user_id']]['profile_complete'] = True
        
        return redirect(url_for('dashboard'))
    
    # Get suggested interests based on user's category
    user_category = users_db[session['user_id']].get('category', 'no_category')
    
    category_suggestions = {
        'student': ['Studying', 'Part-time job', 'Networking', 'Campus events', 'Late night coffee'],
        'gamer': ['PC Gaming', 'Console Gaming', 'MMORPG', 'Esports', 'Streaming'],
        'professional': ['Career growth', 'Networking', 'Work-life balance', 'Business travel'],
        'fitness': ['Gym workouts', 'Running', 'Yoga', 'Hiking', 'Nutrition'],
        'creative': ['Drawing', 'Painting', 'Writing', 'Music production', 'Photography'],
        'traveler': ['Backpacking', 'Road trips', 'Beach vacations', 'Mountain hiking'],
        'foodie': ['Cooking', 'Baking', 'Restaurant hopping', 'Wine tasting', 'Food blogging'],
        'no_category': ['Movies', 'Music', 'Reading', 'Sports', 'Technology']
    }
    
    suggested_interests = category_suggestions.get(user_category, category_suggestions['no_category'])
    
    return render_template('setup_profile.html', 
                         category=CATEGORIES.get(user_category, CATEGORIES['no_category']),
                         suggested_interests=suggested_interests)

# ============================================
# MAIN PAGE ROUTES
# ============================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard - shows stats, recent matches, and suggestions"""
    profile_data = user_profiles.get(session['user_id'], {})
    
    # Get recent matches (last 5)
    recent_matches = []
    for match_email in matches_db.get(session['user_id'], [])[:5]:
        profile = user_profiles.get(match_email, {})
        recent_matches.append({
            'email': match_email,
            'name': profile.get('full_name', 'Unknown'),
            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
            'location': profile.get('location', 'Unknown')
        })
    
    # Get suggested users (high compatibility score)
    suggestions = []
    current_profile = profile_data
    passed_users = passed_users_db.get(session['user_id'], [])
    
    for email, user in users_db.items():
        if email != session['user_id'] and user.get('profile_complete'):
            if email not in passed_users:
                profile = user_profiles.get(email, {})
                if profile:
                    compatibility = calculate_compatibility(current_profile, profile)
                    if compatibility > 60:  # Only show high compatibility matches
                        suggestions.append({
                            'email': email,
                            'name': profile.get('full_name', 'Unknown'),
                            'avatar_url': profile.get('avatar_url', '/static/uploads/avatars/default-avatar.jpg'),
                            'location': profile.get('location', 'Unknown'),
                            'compatibility': compatibility,
                            'verified': profile.get('verified_info', False)
                        })
    
    suggestions.sort(key=lambda x: x['compatibility'], reverse=True)
    
    # Get statistics
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
    """View and edit your own profile"""
    profile_data = user_profiles.get(session['user_id'], {})
    category = users_db.get(session['user_id'], {}).get('category', 'no_category')
    
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
    """View another user's profile"""
    if email not in users_db:
        return redirect(url_for('discover'))
    
    profile_data = user_profiles.get(email, {})
    category = users_db.get(email, {}).get('category', 'no_category')
    is_match = email in matches_db.get(session['user_id'], [])
    
    return render_template('view_profile.html', 
                         user=profile_data,
                         user_email=email,
                         category=CATEGORIES.get(category, CATEGORIES['no_category']),
                         is_match=is_match)

@app.route('/discover')
@login_required
def discover():
    """Discover page - find potential matches"""
    other_users = []
    passed_users = passed_users_db.get(session['user_id'], [])
    current_user_profile = user_profiles.get(session['user_id'], {})
    
    for email, user in users_db.items():
        # Skip: current user, incomplete profiles, passed users
        if email != session['user_id'] and user.get('profile_complete') and email not in passed_users:
            profile = user_profiles.get(email, {})
            if not profile:
                continue
            
            has_liked = session['user_id'] in likes_db.get(email, [])
            is_match = email in matches_db.get(session['user_id'], [])
            
            # Calculate compatibility
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
    
    # Sort by compatibility (highest first)
    other_users.sort(key=lambda x: x.get('compatibility', 0), reverse=True)
    
    return render_template('discover.html', users=other_users)

# ============================================
# API ROUTES (For AJAX/JavaScript interactions)
# ============================================

@app.route('/api/pass', methods=['POST'])
@login_required
def pass_user():
    """API endpoint for passing on a user (they won't appear again)"""
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
    """API endpoint for liking a user"""
    data = request.json
    liked_email = data.get('email')
    
    if not liked_email or liked_email == session['user_id']:
        return jsonify({'success': False, 'message': 'Invalid user'})
    
    # Remove from passed list if they were passed before
    if session['user_id'] in passed_users_db and liked_email in passed_users_db[session['user_id']]:
        passed_users_db[session['user_id']].remove(liked_email)
    
    if session['user_id'] not in likes_db:
        likes_db[session['user_id']] = []
    
    if liked_email not in likes_db[session['user_id']]:
        likes_db[session['user_id']].append(liked_email)
        
        # Check if it's a mutual like (match!)
        is_match = session['user_id'] in likes_db.get(liked_email, [])
        
        if is_match:
            create_match(session['user_id'], liked_email)
            return jsonify({'success': True, 'message': 'It is a match!', 'is_match': True})
        
        # Send notification to the liked user
        add_notification(liked_email, 'like', f"{user_profiles.get(session['user_id'], {}).get('full_name', 'Someone')} liked your profile")
        return jsonify({'success': True, 'message': 'Liked successfully', 'is_match': False})
    
    return jsonify({'success': False, 'message': 'Already liked this user'})

@app.route('/api/unlike', methods=['POST'])
@login_required
def unlike_user():
    """API endpoint for removing a like"""
    data = request.json
    unliked_email = data.get('email')
    
    if session['user_id'] in likes_db and unliked_email in likes_db[session['user_id']]:
        likes_db[session['user_id']].remove(unliked_email)
        return jsonify({'success': True, 'message': 'Unliked successfully'})
    
    return jsonify({'success': False, 'message': 'Not liked yet'})

@app.route('/matches')
@login_required
def matches():
    """View all your matches"""
    matches_list = []
    current_user_profile = user_profiles.get(session['user_id'], {})
    
    for match_email in matches_db.get(session['user_id'], []):
        profile = user_profiles.get(match_email, {})
        if not profile:
            continue
            
        # Get last message preview
        last_message = None
        chat_id = get_chat_id(session['user_id'], match_email)
        if chat_id in messages_db and messages_db[chat_id]:
            last_message = messages_db[chat_id][-1]
        
        # Calculate compatibility
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
    
    # Sort by compatibility
    matches_list.sort(key=lambda x: x.get('compatibility', 0), reverse=True)
    
    return render_template('matches.html', matches=matches_list)

@app.route('/messages')
@login_required
def messages():
    """Messaging page"""
    selected_match = request.args.get('match')
    matches_list = []
    current_messages = []
    
    # Get all matches for sidebar
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
    
    # Get messages for selected conversation
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
    """API endpoint for sending a message"""
    data = request.json
    to_email = data.get('to_email')
    message_text = data.get('message')
    
    if not to_email or not message_text:
        return jsonify({'success': False, 'message': 'Missing required fields'})
    
    # Verify they are matches
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
    
    # Send notification to recipient
    add_notification(to_email, 'message', f"New message from {user_profiles.get(session['user_id'], {}).get('full_name', 'Someone')}")
    
    return jsonify({'success': True, 'message': 'Message sent', 'message_data': message})

@app.route('/api/get-messages', methods=['GET'])
@login_required
def get_messages():
    """API endpoint for retrieving messages (used for polling)"""
    match_email = request.args.get('match')
    
    if not match_email or match_email not in matches_db.get(session['user_id'], []):
        return jsonify({'success': False, 'messages': []})
    
    chat_id = get_chat_id(session['user_id'], match_email)
    messages = messages_db.get(chat_id, [])
    
    return jsonify({'success': True, 'messages': messages})

# ============================================
# PROFILE UPDATE & IMAGE UPLOAD ROUTES
# ============================================

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    """API endpoint for updating user profile"""
    try:
        data = request.json
        profile_data = user_profiles.get(session['user_id'], {})
        
        # Update fields with new values
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
    """API endpoint for uploading profile avatar"""
    try:
        if 'avatar' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['avatar']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if file and allowed_file(file.filename):
            # Create unique filename
            filename = f"avatar_{session['user_id']}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'avatars', filename)
            
            # Process and save high quality image
            img = process_uploaded_image(file, AVATAR_SIZE, is_avatar=True)
            save_image_with_quality(img, filepath, file.filename)
            
            # Update user profile with new avatar URL
            if session['user_id'] in user_profiles:
                user_profiles[session['user_id']]['avatar_url'] = f'/static/uploads/avatars/{filename}'
            
            return jsonify({'success': True, 'message': 'Avatar uploaded successfully', 'url': f'/static/uploads/avatars/{filename}'})
        
        return jsonify({'success': False, 'message': 'File type not allowed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/upload-photo', methods=['POST'])
@login_required
def upload_photo():
    """API endpoint for uploading gallery photos"""
    try:
        if 'photo' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['photo']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if file and allowed_file(file.filename):
            # Create unique filename
            filename = f"photo_{session['user_id']}_{datetime.now().timestamp()}.{file.filename.rsplit('.', 1)[1].lower()}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'photos', filename)
            
            # Process and save high quality image
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

# ============================================
# NOTIFICATIONS ROUTES
# ============================================

@app.route('/notifications')
@login_required
def notifications():
    """View all notifications"""
    user_notifications = notifications_db.get(session['user_id'], [])
    
    # Add human-readable time for each notification
    for notif in user_notifications:
        notif['time_ago'] = format_time_ago(notif.get('timestamp', ''))
    
    return render_template('notifications.html', notifications=user_notifications)

@app.route('/api/mark-notification-read', methods=['POST'])
@login_required
def mark_notification_read():
    """Mark a notification as read"""
    data = request.json
    notif_id = data.get('id')
    
    if session['user_id'] in notifications_db:
        for notif in notifications_db[session['user_id']]:
            if notif.get('id') == notif_id:
                notif['read'] = True
                break
    
    return jsonify({'success': True})

# ============================================
# VERIFICATION ROUTES
# ============================================

@app.route('/verification')
@login_required
def verification():
    """Identity verification page"""
    profile_data = user_profiles.get(session['user_id'], {})
    return render_template('verification.html', user=profile_data)

@app.route('/api/submit-verification', methods=['POST'])
@login_required
def submit_verification():
    """Submit ID verification request"""
    try:
        if 'id_document' not in request.files or 'selfie' not in request.files:
            return jsonify({'success': False, 'message': 'Missing required files'})
        
        id_doc = request.files['id_document']
        selfie = request.files['selfie']
        additional_info = request.form.get('additional_info', '')
        
        # Store verification request
        request_id = f"{session['user_id']}_{datetime.now().timestamp()}"
        verification_requests[request_id] = {
            'user_id': session['user_id'],
            'status': 'pending',
            'submitted_at': datetime.now().isoformat(),
            'additional_info': additional_info
        }
        
        # Send confirmation notification
        add_notification(session['user_id'], 'verification', 'Your verification request has been submitted. We will review it within 48 hours.')
        
        return jsonify({'success': True, 'message': 'Verification request submitted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ============================================
# FEEDBACK ROUTES
# ============================================

@app.route('/feedback')
@login_required
def feedback():
    """Feedback and support page"""
    return render_template('feedback.html')

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
def submit_feedback():
    """Submit user feedback"""
    try:
        feedback_type = request.form.get('type')
        subject = request.form.get('subject')
        message_text = request.form.get('message')
        contact_permission = request.form.get('contact_permission') == 'true'
        
        # Store feedback
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

# ============================================
# SETTINGS ROUTES
# ============================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """User settings page"""
    user_data = users_db.get(session['user_id'], {})
    profile_data = user_profiles.get(session['user_id'], {})
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_preferences':
            # Update discovery preferences
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
            # Update notification settings
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
            # Update privacy settings
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
            # Change password
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
            # Delete account
            email = session['user_id']
            if email in users_db:
                del users_db[email]
                if email in user_profiles:
                    del user_profiles[email]
                session.clear()
                return jsonify({'success': True, 'message': 'Account deleted', 'redirect': url_for('login')})
        
        return jsonify({'success': False, 'message': 'Invalid action'})
    
    # GET request - show settings page
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

# ============================================
# LOGOUT
# ============================================

@app.route('/logout')
def logout():
    """Log out user - clear session"""
    session.clear()
    return redirect(url_for('login'))

# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    app.run(debug=True)  # debug=True means auto-reload on code changes