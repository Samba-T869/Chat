import eventlet
eventlet.monkey_patch()
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask import send_from_directory
from flask_socketio import SocketIO, emit
from flask_socketio import join_room, leave_room
from datetime import datetime
import time
import os
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import base64
import mimetypes
import mimetypes
import uuid
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from flask_session import Session

app=Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = os.environ.get('SECRET_KEY', 'fallback_secret_key')
app.config['SESSION_TYPE']='filesystem'
Session(app)

socketio = SocketIO(
    app,
    manage_session=True,
    cors_allowed_origins="*",
    cors_credentials=True,
    logger=True,
    engineio_logger=True,
    async_mode='eventlet'
)

if 'RENDER' in os.environ:
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE='None'
    )
else:
    app.config.update(
        SESSION_COOKIE_SECURE=False,
        SESSION_COOKIE_SAMESITE='Lax'
    )

users = {}
active_private_rooms = {}

UPLOAD_FOLDER =os.environ.get('UPLOAD_FOLDER', 'uploads') 
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

engine = None

def init_db():
    global engine
    db_url = os.environ.get('DATABASE_URL', 'sqlite:///users.db')
    
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    engine = create_engine(db_url)
    
    with engine.connect() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL, 
            password TEXT NOT NULL
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS messages(
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp REAL NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'text'
        )
        """))
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS private_messages (
        id SERIAL PRIMARY KEY,
        room TEXT NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        timestamp REAL NOT NULL,
        message_type VARCHAR(10) NOT NULL DEFAULT 'text'
        )
        """))
        conn.commit()

init_db()

@socketio.on_error_default
def default_error_handler(e):
    app.logger.error(f"SocketIO error: {str(e)}")
    emit('error', {'message': 'A server error occurred'})

@app.route('/')
def index():
	return redirect(url_for('home'))
	
@app.route('/home')
def home():
	if 'user' in session:
		return redirect(url_for('chat'))
	else:
		return render_template('home.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
	response = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
	#Add Mime type detection
	mime_type, _ = mimetypes.guess_type(filename)
	if mime_type:
		response.headers.set('Content-Type', mime_type)
	return response
    
@socketio.on('connect')
def handle_connect():
    if 'user' in session:
        username = session['user']
        users[request.sid] = username
        print(f'User connected: {username}')
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, username, message, timestamp, message_type 
                FROM messages ORDER BY timestamp
            """))
            messages = result.fetchall()
        
        for msg in messages:
            emit('new_message', {
                'id': msg[0],
                'username': msg[1],
                'content': msg[2],
                'timestamp': msg[3],
                'type': msg[4]
            }, room=request.sid)
        
        emit('user_joined', {'username': username}, broadcast=True)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])
        
        try:
            with engine.connect() as conn:
                   conn.execute(text("INSERT INTO users (username, email, password) VALUES (:username, :email, :password)"),
                   {'username': username, 'email': email, 'password': password})
                   conn.commit()
            flash('Registered successfully, please login')
            return redirect(url_for('login'))

        except IntegrityError:
            flash('Username or email already exists')
            return redirect(url_for('register'))
        
        except SQLAlchemyError as e:
            flash(f'Registration failed: {str(e)}')
            return redirect(url_for('register'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method =="POST":
		username = request.form['username']
		password = request.form['password']
		
		with engine.connect() as conn:
		              result = conn.execute(text("""SELECT password FROM users WHERE username = :username"""),{'username': username})
		              user = result.fetchone()
		              
		if user and check_password_hash(user[0], password):
		      session['user'] = username
		      return redirect(url_for('chat'))
		else:
		      flash('Invalid credentials')
		      return redirect(url_for('login'))
		
	return render_template('login.html')

@app.route('/chat')
def chat():
	if 'user' in session:
	    return render_template('chat.html', username=session['user'])
	else:
		return redirect(url_for('login'))

@app.route('/private')
def private():
    if 'user' in session:
        
        with engine.connect() as conn:
            users_result = conn.execute(text("SELECT username FROM users ORDER BY username ASC"))
            users_list = [row[0] for row in users_result]
            registered_count = len(users_list)
            
            #Get online users 
            online_users = set(users.values())
            online_count = len(online_users)
        return render_template('users.html', users=users_list, registered=registered_count, active=online_count)
    else:
        return redirect(url_for('login'))
		
@app.route('/private/<username>')
def private_chat(username):
    if 'user' not in session:
        return redirect(url_for('login'))
    
    current_user = session['user']
    room = '_'.join(sorted([current_user, username]))
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, sender, message, timestamp, message_type
            FROM private_messages 
            WHERE room = :room 
            ORDER BY timestamp
        """), {'room': room})
        
        messages = []
        for row in result:
            messages.append({
                'id': row[0],
                'sender': row[1],
                'content': row[2],
                'timestamp': row[3],
                'type': row[4]
            })
    
    return render_template('private.html', 
                          recipient=username,
                          messages=messages)
	
@app.template_filter('format_time')
def format_time_filter(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%I:%M %p')
				
@app.route('/profile')
def profile():
    if 'user' in session:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT * FROM users WHERE username = :username"), 
                                  {'username': session['user']})
            user = result.fetchone()
        return render_template('profile.html', username=user[1],email=user[2])
 
@socketio.on('join_private')
def on_join_private(data):
    if 'user' not in session:
        return
    recipient = data['recipient']
    sender = session['user']
    room = '_'.join(sorted([sender, recipient]))
    join_room(room)
    print(f"{sender} joined private room: {room}")
 
@socketio.on('private_message')
def handle_private_message(data):
    if 'user' not in session:
    	return
    sender = session['user']
    room = data.get('room')
    if not room:
    	print("Error: Room not provided in private message")
    	return
    message_content = data['content']
    message_type = data.get('type', 'text').lower()
    timestamp = time.time()
    filename = data.get('filename', '')
    print(f"Received private message for room: {room}")
    
    if message_type != 'text':
    	try:
    		header, encoded = message_content.split(',', 1)
    		file_data = base64.b64decode(encoded)
    		if len(file_data) > 30 * 1024 * 1024:
    			emit('private_message_error', {'message': 'File too large (max 30MB)'}, room=request.sid)
    			return
    		
    		ext = mimetypes.guess_extension(header.split(';')[0].split(':')[1])
    		filename = f"{uuid.uuid4()}{ext}"
    		file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    		os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    		with open(file_path, 'wb') as f:
    			f.write(file_data)
    		message_content = f"/uploads/{filename}"
    		if message_type == 'pdf':
    			orig_name = secure_filename(data.get('filename', 'document.pdf'))
    			message_content += f"?name={orig_name}"
    		
    	except Exception as e:
    	       print(f"File processing failed: {str(e)}")
    	       emit('private_message_error', 
                 {'message': 'File upload failed'}, 
                 room=request.sid)
    	       return
    else:
    	message_content = data['content']        
    try:
    	with engine.begin() as conn:
            result = conn.execute(text("""
                INSERT INTO private_messages 
                (room, sender, message, timestamp, message_type)
                VALUES (:room, :sender, :message, :timestamp, :type)
                RETURNING id
            """), {
                'room': room,
                'sender': sender,
                'message': message_content,
                'timestamp': timestamp,
                'type': message_type
            })
            message_id = result.scalar()
            
            emit('private_message', {
            'id': message_id,
            'sender': sender,
            'content': message_content,
            'timestamp': timestamp,
            'type': message_type,
            'room': room,
            'tempId': data.get('tempId')
        }, room=room)
        
    except Exception as e:
    	app.logger.error(f"Error saving message: {str(e)}", exc_info=True)
    	emit('private_message_error', 
             {'message': 'Failed to send message'}, 
             room=request.sid)								
@socketio.on('delete_private_message')
def handle_delete_private(data):
    if 'user' not in session:
        return
    
    message_id = data['id']
    room = data['room']
    
    with engine.connect() as conn:
        # Verify ownership and get message details
        result = conn.execute(text("""
            SELECT sender, message, message_type 
            FROM private_messages 
            WHERE id = :id AND room = :room
        """), {'id': message_id, 'room': room})
        msg = result.fetchone()
        
        if not msg:
            return
            
        sender, content, msg_type = msg
        
        # Verify current user is the sender
        if sender != session['user']:
            return
            
        # Delete from database
        conn.execute(text("""
            DELETE FROM private_messages 
            WHERE id = :id
        """), {'id': message_id})
        conn.commit()
        
        # Delete associated file if exists
        if msg_type != 'text':
            try:
                file_path = content.split('?')[0].replace('/uploads/', '')
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
            except Exception as e:
                print(f"Error deleting file: {str(e)}")
        
        # Notify clients
        emit('private_message_deleted', 
             {'id': message_id}, 
             room=room)																												
@socketio.on('disconnect')
def handle_disconnect(reason):
		if request.sid in users:
			username = users[request.sid]
			del users[request.sid]
			emit('user_left', {'username': username, 'timestamp': time.time()}, broadcast=True)
			print(f'Client disconnected: {request.sid}')
		for room in rooms:
			leave_room(room)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'mp3', 'mp4'}
def allowed_file(mime_type):
	allowed ={'image/png', 'image/jpeg', 'image/gif', 'application/pdf', 'audio/mpeg', 'video/mp4'}
	return mime_type in allowed
	
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@socketio.on('send_message')
def handle_message(data):
    if 'user' not in session:
        print("Error: User not authenticated")
        return
    username = session['user']
    if not username:
        return  # Ignore unauthenticated

    saved_file_path = None
    try:
        message_content = data['content']
        message_type = data.get('type', 'text')
        timestamp = time.time()
        message_id = None
        
        print(f"Received message type: {message_type}")
        print(f"Content length: {len(message_content)}")
        if message_type != 'text':
            file_path = None
            try:
                # Process data URL
                header, encoded_content = data['content'].split(',', 1)
                content = base64.b64decode(encoded_content)
                
                decoded_size = (len(encoded_content) * 3) // 4
                if decoded_size > 30 * 1024 * 1024: 
                    emit('error', {'message': 'File too large (max 30MB)'}, room=request.sid)
                    return
                
                mime_type = header.split(';')[0].split(':')[1]
                if not allowed_file(mime_type):
                    emit('error', {'message': 'File type not allowed'}, room=request.sid)
                    return
                
                ext = mimetypes.guess_extension(mime_type) or '.bin'
                filename = secure_filename(f"{uuid.uuid4()}{ext}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                with open(file_path, 'wb') as f:
                    f.write(content)
                print(f"File saved to: {file_path}")
                message_content = f"/uploads/{filename}"; 
                
                if message_type == 'pdf':
                	original_filename = secure_filename(file.filename) if hasattr(file, 'filename') else "document.pdf"
                	message_content = f"/uploads/{filename}?name={original_filename}"
                else:
                	message_content = f"/uploads/{filename}"
                saved_file_path = file_path
                
            except Exception as e:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                print(f"File processing failed: {str(e)}")
                emit('error', {'message': 'File upload failed'}, room=request.sid)
                return

        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO messages (username, message, timestamp, message_type)
                VALUES (:username, :message, :timestamp, :message_type)
                RETURNING id
            """), {
                'username': username,
                'message': message_content,
                'timestamp': timestamp,
                'message_type': message_type
            })
            message_id = result.scalar()
            conn.commit()
        
        saved_file_path = None
        
        if message_id:
            try:
                emit('new_message', {
                    'id': message_id,
                    'username': username,
                    'content': message_content,
                    'type': message_type,
                    'timestamp': timestamp
                }, broadcast=True)
            except Exception as e:
                print(f"Broadcast error: {str(e)}")
    
    except Exception as e:
        if saved_file_path and os.path.exists(saved_file_path):
            try:
                os.remove(saved_file_path)
            except Exception:
                pass
        print(f"Critical error in send_message: {str(e)}")
        emit('error', {'message': 'Failed to send message due to server error'}, room=request.sid)

@socketio.on('delete_message')
def handle_delete(message_id):
    if 'user' not in session:
    	return
    username = session['user']
    
    try:
    	with engine.connect() as conn:
    	       result = conn.execute(text("""SELECT username, message, message_type
    	       FROM messages
    	       WHERE id = :id"""), {'id': message_id})
    	       row = result.fetchone()
    	       
    	       if not row:
    	       	return
    	       message_username, message_content, message_type = row
    	       
    	       if message_username != username:
    	       	return
    	       	
    	       conn.execute(text("""DELETE FROM messages WHERE id = :id"""), {'id': message_id})
    	       conn.commit()
    	       
    	       if message_type != 'text':
    	           file_path = message_content.replace('/uploads/', '')
    	           full_path = os.path.join(app.config['UPLOAD_FOLDER'], file_path)
    	           if os.path.exists(full_path):
    	                   try:
    	                   	os.remove(full_path)
    	                   except Exception as e:
    	                   	print(f"Error deleting file: {str(e)}")
    	emit('message_deleted', message_id, broadcast=True)
    except Exception as e:
    	print(f"Delete error: {str(e)}")

def cleanup_uploads():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        return
        
    now = time.time()
    for f in os.listdir(app.config['UPLOAD_FOLDER']):
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f)
        try:
            if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 3600 * 24:
                os.remove(filepath)
        except Exception as e:
            print(f"Error deleting {filepath}: {str(e)}")
	
@app.route('/logout',  methods=['GET', 'POST'])
def logout():
	session.pop('user', None)
	flash('Logged out successfully.')
	return redirect(url_for('login'))
	
if (__name__) =='__main__':
	port = int(os.environ.get('PORT', 9000))
	os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
	socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug =True)