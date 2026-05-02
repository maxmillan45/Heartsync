# Heartsync Dating App
A professional dating application built with Flask that helps people find meaningful connections through intelligent matching, real-time messaging, and verified profiles.

## Features

### Core Features
- **User Authentication**: Email/password registration and Google OAuth login
- **Smart Matching**: Compatibility algorithm based on interests, age, location, and preferences
- **Real-time Messaging**: Chat system with read receipts and message history
- **Profile Management**: Complete profile setup with photos, bio, and interests
- **Discovery System**: Like/Pass functionality with permanent pass tracking

### Professional Features
- **Dashboard**: User statistics, recent matches, and personalized suggestions
- **Notifications**: Real-time alerts for likes, matches, and messages
- **Verification System**: Identity verification with document upload
- **Settings**: Preferences, privacy controls, and notification management
- **Feedback System**: User feedback collection with support tickets
- **High-Quality Images**: Professional image processing (500x500 avatars, 1200x1200 photos)

### Technical Highlights
- Responsive design with Tailwind CSS
- Google OAuth integration
- High-quality image processing with Pillow
- Session management with 7-day persistence
- Compatibility scoring algorithm
- Environment variable configuration for security

## Tech Stack

- **Backend**: Flask 2.3.3
- **Database**: In-memory (ready for SQLite/PostgreSQL)
- **Authentication**: Werkzeug security + Google OAuth
- **Image Processing**: Pillow 10.0.0
- **Frontend**: Tailwind CSS + JavaScript
- **OAuth**: Authlib 1.2.1

## Installation Guide

### Prerequisites

- Python 3.8 or higher
- Git
- Google Cloud account (for OAuth)

### Step 1: Clone the Repository

```bash
git clone https://github.com/maxmillan45/Heartsync.git
cd Heartsync

### Step 2: Create Virtual Environment

bash
python -m venv venv
venv\Scripts\activate
Mac/Linux:

bash
python3 -m venv venv
source venv/bin/activate


### Step 3: Install Dependencies
bash
pip install -r requirements.txt
Required packages:

text
Flask==2.3.3
Werkzeug==2.3.7
Pillow==10.0.0
python-dotenv==1.0.0
authlib==1.2.1
requests==2.31.0