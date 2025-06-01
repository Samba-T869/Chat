import os
import sqlite3
from flask import Flask, render_template, redirect, url_for, session, request, flash
from flask_session import Session
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mimimwenyewe')
socketio = SocketIO(app, cors_allowed_origins="*")

def init_db():
	conn = sqlite3.connect('users.db')
	cur = conn.cursor()
	cur.execute('''
	CREATE TABLE IF NOT EXISTS
	users(
	id INTEGER PRIMARY KEY AUTOINCREMENT, 
	username UNIQUE NOT NULL, 
	password UNIQUE NOT NULL
	)
	''')
	conn.commit()
	conn.close()
	
init_db()

@app.route('/')
def home():
	if 'user' in session:
		return redirect(url_for('chat'))
	return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
	if request.method == 'POST':
		username = request.form['username']
		password =request.form['password']
		
		conn = None
		try:
			with sqlite3.connect('users.db', timeout=20) as conn:
				cur = conn.cursor()
				cur.execute(
				"INSERT INTO users (username, password) VALUES(?,?)",
				(username, password)
				)
				conn.commit()
				flash("Account created successful")
				return redirect(url_for('login'))
		    
		except sqlite3.IntegrityError:
			flash('Username already exists.')
			return redirect(url_for('register'))
			
		except Exception as e:
			flash('Registration failed')
			return redirect(url_for('register'))
			
		if not username or not password:
			flash('Username or password can not be empty.')
			return redirect(url_for('register'))
	return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
	if request.method == 'POST':
		username =request.form['username']
		password =request.form['password']
		
		conn = None
		try:
			with sqlite3.connect('users.db', timeout =20) as conn:
				cur = conn.cursor()
				cur.execute("SELECT password FROM users WHERE username=?",
				(username,))
				user = cur.fetchone()
		finally:
			if conn:
				conn.close()
				
		if user and password:
			session['user'] = username
			flash('Logged in successfully!.')
			return redirect(url_for('chat'))
		else:
			flash('Invalid credentials')
			return redirect(url_for('login'))
	return render_template('login.html')

@app.route('/chat')
def chat():
	if 'user' in session:
		return render_template('chat.html')
	else:
		return redirect(url_for('login'))
		
@socketio.on('message')
def handle_message(msg):
    sender = session.get('user', 'unknown')
    send({'user': sender, 'msg': msg}, broadcast =True)
    print('Message:', msg)
    
@socketio.on('media')
def handle_media(data):
    socketio.emit('media', data, broadcast=True)

@app.route('/logout')
def logout():
	session.pop('user', None)
	flash('Logged out successfully!')
	return redirect(url_for('login'))
	
if __name__ == '__main__':
    app.run(port=8000, debug=True)