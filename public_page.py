from flask import Blueprint, session, render_template, redirect, url_for, request, jsonify
import sqlite3
import os
import time 
from datetime import datetime
from flask_socketio import emit
from werkzeug.utils import secure_filename

public_bp = Blueprint('public_bp', __name__)

@public_bp.route('/public', methods=['GET','POST'])
def public():
	if 'user' not in session:
		return redirect(url_for('load'))
	
	with sqlite3.connect('users.db') as conn:
		cur = conn.cursor()
		cur.execute('''
		SELECT sender_username,message_text,file_path,file_type,strftime('%H:%M', timestamp) as display_time, timestamp FROM public_messages ORDER BY timestamp ASC''')
		messages = cur.fetchall()
		
	return render_template('public.html', messages=messages)
	
@public_bp.route('/upload_public_media', methods=['POST'])
def upload_public_media():
    if 'user' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Create secure filename with timestamp
    filename = secure_filename(file.filename)
    timestamp = str(int(time.time()))
    filename = f"{timestamp}_{filename}"
    
    # Create upload directory if it doesn't exist
    upload_folder = 'static/public_media'
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    
    # Save file
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    
    # Determine file type
    if file.content_type.startswith('image'):
        file_type = 'image'
    elif file.content_type.startswith('video'):
        file_type = 'video'
    elif file.content_type.startswith('audio'):
        file_type = 'audio'
    elif file.content_type == 'application/pdf':
        file_type = 'pdf'
    else:
        file_type = 'file'
    
    # Return relative path for web access
    relative_path = f"public_media/{filename}"
    
    return jsonify({
        'success': True,
        'file_path': relative_path,
        'file_type': file_type,
        'filename': file.filename
    })