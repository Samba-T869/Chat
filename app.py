import os
from flask import Flask, render_template
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'mimimwenyewe')
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def home():
    return render_template('index.html')

@socketio.on('message')
def handle_message(msg):
    print('Message:', msg)
    send(msg, broadcast=True)
    
@socketio.on('media')
def handle_media(data):
    socketio.emit('media', data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 9000))
    socketio.run(app, host='0.0.0.0', port=port)