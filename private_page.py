from flask import Blueprint, redirect, session, url_for, render_template, request, jsonify
import sqlite3
import os
import time
from werkzeug.utils import secure_filename

private_bp = Blueprint('private_bp', __name__)

@private_bp.route('/private/<recipient>', methods=['GET', 'POST'])
def private(recipient):
    if 'user' not in session:
        return redirect(url_for('load'))
    
    current_user = session['user']
    
    if request.method == 'POST':
        # Handle message sending
        message_text = request.form.get('message_text')
        file = request.files.get('file')
        
        file_path = None
        file_type = None
        
        if file and file.filename != '':
            # Secure the filename and create upload directory if needed
            filename = secure_filename(file.filename)
            timestamp = str(int(time.time()))
            filename = f"{timestamp}_{filename}"
            
            upload_folder = 'static/private_uploads'
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
                
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
        
        # Save message to database
        conn = sqlite3.connect('users.db')
        cur = conn.cursor()
        cur.execute("INSERT INTO private_messages (sender_username, recipient_username, message_text, file_path, file_type) VALUES (?, ?, ?, ?, ?)",
                   (session['user'], recipient, message_text, file_path, file_type))
        conn.commit()
        
        # Get the newly created message with timestamp
        cur.execute("SELECT * FROM private_messages WHERE id = last_insert_rowid()")
        new_message = cur.fetchone()
        conn.close()
        
        # Emit the new message via Socket.IO
        from flask_socketio import emit
        emit('new_private_message', {
            'id': new_message[0],
            'sender': session['user'],
            'recipient': recipient,
            'message_text': new_message[3],
            'file_path': new_message[4],
            'file_type': new_message[5],
            'timestamp': new_message[6]
        }, broadcast=True, namespace='/')
        
        return jsonify(success=True)
    
    # GET request - fetch messages
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM private_messages WHERE (sender_username = ? AND recipient_username = ?) OR (recipient_username = ? AND sender_username = ?) ORDER BY timestamp",
               (current_user, recipient,current_user, recipient))
    messages = cur.fetchall()
    conn.close()
    
    return render_template('private.html', recipient=recipient, messages=messages,current_user=current_user)