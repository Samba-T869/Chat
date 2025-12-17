from flask import Blueprint, redirect, url_for, render_template, session, request 
import sqlite3
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os
import time
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

load_dotenv()

tusepe_bp = Blueprint('tusepe_bp', __name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

@tusepe_bp.route('/tusepe', methods=['GET', 'POST'])
def tusepe():
    if 'user' not in session:
        return redirect(url_for('load'))
    
    if request.method == 'POST':
        content = request.form.get('content')
        media_file = request.files.get('media')
        media_type = None
        media_path = None
        
        if media_file:
            # Determine media type
            if media_file.content_type.startswith('image'):
                media_type = 'image'
                resource_type = 'image'
            elif media_file.content_type.startswith('video'):
                media_type = 'video'
                resource_type = 'video'
            elif media_file.content_type.startswith('audio'):
            	media_type = 'audio'
            	resource_type = 'video'
            
            # Upload to Cloudinary instead of local storage
            try:
                # Upload the file to Cloudinary
                upload_result = cloudinary.uploader.upload(
                    media_file,
                    resource_type=resource_type,
                    folder="tusepe_media"  # Optional: organize files in a folder
                )
                
                # Get the secure URL from Cloudinary response
                media_path = upload_result['secure_url']
                
            except Exception as e:
                print(f"Cloudinary upload failed: {e}")
                # Handle upload error (you might want to flash a message to the user)
                return redirect(url_for('tusepe_bp.tusepe'))
                
        # Save post to database
        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO posts (username, content, media_type, media_path) VALUES (?, ?, ?, ?)",
                   (session['user'], content, media_type, media_path))
        conn.commit()
        conn.close()
        
        return redirect(url_for('tusepe_bp.tusepe'))
    
    # Get all posts for display
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT posts.*, CASE WHEN user.profile_pic LIKE 'static/%' THEN SUBSTR(user.profile_pic, 7) ELSE user.profile_pic END as profile_pic FROM posts JOIN user ON posts.username = user.username ORDER BY posts.timestamp DESC")
    posts = cur.fetchall()
    conn.close()
    
    return render_template('tusepe.html', posts=posts,username=session['user'])