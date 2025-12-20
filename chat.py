from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_socketio import SocketIO, join_room, leave_room, emit
import os
import time
from datetime import datetime 
import sqlite3
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from public_page import public_bp
from tusepe_page import tusepe_bp
from profile_page import profile_bp
from private_page import private_bp

online_users ={}
active_connections ={}

app = Flask(__name__)
app.register_blueprint(public_bp)
app.register_blueprint(tusepe_bp)
app.register_blueprint(profile_bp)
app.register_blueprint(private_bp)

socketio = SocketIO(app)
app.secret_key = os.getenv('SECRET_KEY')

def init_db():
	conn = sqlite3.connect('users.db')
	cur = conn.cursor()
	cur.execute(''' CREATE TABLE IF NOT EXISTS
	user(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	username TEXT UNIQUE NOT NULL, email TEXT UNIQUE NOT NULL, number TEXT NOT NULL, sex TEXT,
	password TEXT NOT NULL,
	profile_pic TEXT)
	''')
	conn.execute('''
	CREATE TABLE IF NOT EXISTS
	comments(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	comment TEXT NOT NULL)
	''')
	conn.execute('''
	CREATE TABLE IF NOT EXISTS private_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_username TEXT NOT NULL,
        recipient_username TEXT NOT NULL,
        message_text TEXT,
        file_path TEXT,
        file_type TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
	''')
	conn.execute('''
	CREATE TABLE IF NOT EXISTS public_messages(
	id INTEGER PRIMARY KEY AUTOINCREMENT,
	sender_username TEXT NOT NULL, 
	recipient_username TEXT NOT NULL, 
	message_text TEXT, 
	file_path TEXT, 
	file_type TEXT, 
	timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
	''')
	conn.execute('''
    CREATE TABLE IF NOT EXISTS posts(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    content TEXT,
    media_type TEXT,
    media_path TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    likes INTEGER DEFAULT 0)
    ''')
	conn.commit()
	conn.close()
	
init_db()
	
@app.route('/')
def load():
	return render_template('loadpage.html')

@app.route('/homepage')
def homepage():
	if 'user' not in session:
		return redirect(url_for('load'))
	return render_template('homepage.html')

@app.route('/register', methods=['GET','POST'])
def register():
	if request.method =='POST':
		username = request.form['username']
		email = request.form['email']
		number = request.form['number']
		sex = request.form['sex']
		password = generate_password_hash(request.form['password'])
		
		#Handle profile picture 
		profile_pic_path = None
		if 'profile_pic' in request.files:
			file = request.files['profile_pic']
			if file and file.filename != '':
				filename = secure_filename(file.filename)
				timestamp = str(int(time.time()))
				filename = f"{timestamp}_{filename}"
				
				upload_folder = 'static/profile_pics'
				if not os.path.exists(upload_folder):
					os.makedirs(upload_folder)
				
				file_path = os.path.join(upload_folder, filename)
				file.save(file_path)
				profile_pic_path = f"profile_pics/{filename}"
		
		with sqlite3.connect('users.db') as conn:
			try:
				cur = conn.cursor()
				cur.execute("INSERT INTO user (username, email, number, sex, password, profile_pic) VALUES(?,?,?,?,?,?)", (username, email, number, sex, password, profile_pic_path))
				conn.commit()
				flash("Registered successfully, please login.")
				return redirect(url_for('login'))
			
			except sqlite3.IntegrityError:
				flash("This user already exist")
				return redirect(url_for('register'))
				
			except Exception as e:
				flash("Registration failed.")
				return redirect(url_for('register'))
		
	return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method =='POST':
		username = request.form['username']
		password = request.form['password']
		
		conn = None
		try:
			conn = sqlite3.connect('users.db')
			cur = conn.cursor()
			cur.execute("SELECT * FROM user WHERE username =?", (username,))
			user = cur.fetchone()
			conn.commit()
		finally:
			if conn:
				conn.close()
				
		if user and check_password_hash(user[5], password):
			session['user'] = username
			flash('Logged in successfully')
			return redirect(url_for('homepage'))
			
		else:
			flash('Invalid credentials')
			return redirect(url_for('login'))
			
	return render_template('login.html')

@socketio.on('connect')
def handle_connect():
    if 'user' in session:
        user_id = session['user']
        online_users[user_id] = True
        active_connections[request.sid] = user_id
        print(f"User {user_id} connected")
        
        socketio.emit('user_online', {'username': user_id})
        
@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    if sid in active_connections:
        user_id = active_connections[sid]
        
        # Check if user has other active connections
        user_sids = [s for s, u in active_connections.items() if u == user_id]
        
        if len(user_sids) <= 1:  # This is the last connection for this user
            online_users.pop(user_id, None)
            # Broadcast user offline status
            socketio.emit('user_offline', {'username': user_id})
        
        # Remove this specific connection
        active_connections.pop(sid, None)
        print(f"User {user_id} disconnected")
        
def get_online_users():
    """Return a list of usernames that are currently online"""
    return list(online_users.keys())

@socketio.on('join_private_room')
def handle_join_private_room(data):
    if 'user' in session:
        # Users join a room specific to their conversation
        room_name = get_conversation_room(session['user'], data['recipient'])
        join_room(room_name)
        print(f"User {session['user']} joined room: {room_name}")

def get_conversation_room(user1, user2):
    """Generate a unique room name for a conversation between two users"""
    users = sorted([user1, user2])
    return f"private_{users[0]}_{users[1]}"

@socketio.on('send_public_message')
def handle_public_message(data):
    if 'user' not in session:
        return
    
    sender_username = session['user']
    message_text = data.get('message', '')
    file_path = data.get('file_path', None)
    file_type = data.get('file_type', None)
    
    # Save to database
    with sqlite3.connect('users.db') as conn:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO public_messages(sender_username, recipient_username, message_text, file_path, file_type) 
            VALUES(?,?,?,?,?)
        ''', (sender_username, 'public', message_text, file_path, file_type))
        conn.commit()
    
    # Broadcast to all connected clients
    emit('new_public_message', {
        'sender': sender_username,
        'message': message_text,
        'file_path': file_path,
        'file_type': file_type,
        'timestamp': datetime.now().strftime('%H:%M'),
        'is_current_user': False  # Frontend will adjust this per user
    }, broadcast=True, include_self=True)
    
    # Also send to sender with is_current_user flag
    emit('new_public_message', {
        'sender': sender_username,
        'message': message_text,
        'file_path': file_path,
        'file_type': file_type,
        'timestamp': datetime.now().strftime('%H:%M'),
        'is_current_user': True
    })

@socketio.on('get_public_history')
def handle_get_public_history():
    """Send message history to newly connected user"""
    if 'user' not in session:
        return
    
    with sqlite3.connect('users.db') as conn:
        cur = conn.cursor()
        cur.execute('''
            SELECT sender_username, message_text, file_path, file_type, timestamp 
            FROM public_messages 
            ORDER BY timestamp ASC 
            LIMIT 100
        ''')
        messages = cur.fetchall()
    
    emit('public_message_history', {
        'messages': messages,
        'current_user': session['user']
    })

@app.route('/users')
def users():
	if 'user' in session:
		conn = sqlite3.connect('users.db')
		cur = conn. cursor()
		cur.execute('''
		SELECT username, profile_pic FROM user ORDER BY username ASC
		''')
		users = cur.fetchall()
		registered_users = len(users)
		
		online_users = get_online_users()
		online = len(online_users)
		
		users_with_status = []
		for username, profile_pic in users:
		    is_online = username in online_users
		    users_with_status.append({
                'username': username,
                'profile_pic': profile_pic,
                'is_online': is_online
            })
		conn.close()
		
		return render_template('users.html', users=users, registered=registered_users, active=online)
	else:
		return redirect(url_for('login'))
	
@app.route('/anonymous')
def anonymous():
	if 'user' not in session:
		return redirect(url_for('load'))
	return render_template('anonymous.html', username=session['user'])

@app.route('/loner')
def loner():
	if 'user' not in session:
		return redirect(url_for('load'))
	return render_template('loner.html')

@app.route('/setting')
def setting():
	return render_template('settings.html')

@app.route('/experience', methods=['GET','POST'])
def experience():
	if 'user' not in session:
		return redirect(url_for('load'))
	if request.method=='POST':
		comment = request.form['comment']
		
		conn = None;
		with sqlite3.connect('users.db') as conn:
			try:
				cur = conn.cursor()
				cur.execute("INSERT INTO comments (comment) VALUES(?)", (comment,))
				conn.commit()
				return redirect(url_for('homepage'))
				flash('Your response has been submitted successfully.')
				
			except Exception as e:
				flash(f"Comment submission failed: {e}")
				return redirect(url_for('experience'))
				
					
	return render_template('Experience.html', username=session['user'])
	
@app.route('/policy')
def policy():
	return render_template('policy.html')
	
@app.route('/logout')
def logout():
	session.pop('user', None)
	flash('Logged out successfully')
	return redirect(url_for('homepage'))

if __name__ == '__main__':
	socketio.run(app, port=9000, debug=True)