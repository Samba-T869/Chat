from flask import Blueprint, session, render_template, redirect, url_for
import sqlite3
from datetime import datetime
from flask_socketio import emit

public_bp = Blueprint('public_bp', __name__)

@public_bp.route('/public', methods=['GET','POST'])
def public():
	if 'user' not in session:
		return redirect(url_for('load'))
	
	with sqlite3.connect('users.db') as conn:
		cur = conn.cursor()
		cur.execute('''
		SELECT sender_username,message_text,file_path,file_type,timestamp FROM public_messages ORDER BY timestamp ASC''')
		messages = cur.fetchall()
		
	return render_template('public.html', messages=messages)
	
@public_bp.route('/send_public_message',methods=['POST'])
def send_public_message():
	if 'user' not in session:
		return jsonify({'Error': 'Not logged in'})
		
	data = request.json
	sender_username = session['user']
	message_text = data.get('message', '')
	file_path = data.get('file_path', None)
	file_type = data.get('file_type', None)
	
	with sqlite3.connect('users.db') as conn:
		cur = conn.cursor()
		cur.execute('''
		INSERT INTO public_messages (sender_username,recipient_username,message_text,file_path,file_type) VALUES(?,?,?,?,?)''', (sender_username, 'public', message_text,file_path,file_type))
		conn.commit()
		
		return jsonify({
		'success': True, 
		'message': message_text,
		'sender': sender_username,
		'timestamp': datetime.now().strftime('%H:%M')
		})