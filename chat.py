from flask import Flask, render_template, redirect, url_for, request, jsonify, session, flash
from flask_socketio import SocketIO, join_room, leave_room
import os
import time
import sqlite3
from flask_cors import CORS
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from public_page import public_bp
from tusepe_page import tusepe_bp
from profile_page import profile_bp
from private_page import private_bp

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
        print(f"User {session['user']} connected")

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

@socketio.on('private_message')
def handle_private_message(data):
    if 'user' not in session:
        return
    
    sender = session['user']
    recipient = data['recipient']
    message_text = data.get('message_text', '')
    
    # Save to database
    conn = sqlite3.connect('users.db')
    cur = conn.cursor()
    cur.execute("INSERT INTO private_messages (sender_username, recipient_username, message_text) VALUES (?, ?, ?)",
               (sender, recipient, message_text))
    conn.commit()
    
    # Get the newly created message with timestamp
    cur.execute("SELECT * FROM private_messages WHERE id = last_insert_rowid()")
    new_message = cur.fetchone()
    conn.close()
    
    # Emit only to the conversation room, not broadcast
    room_name = get_conversation_room(sender, recipient)
    socketio.emit('new_private_message', {
        'id': new_message[0],
        'sender': sender,
        'recipient': recipient,
        'message_text': message_text,
        'file_path': new_message[4],
        'file_type': new_message[5],
        'timestamp': new_message[6]
    }, room=room_name)  # Send only to the specific room

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
		
		online_users = set(user[0] for user in users)
		online = len(online_users)
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
				return redirect(url_for('login'))
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