from flask import Blueprint, session, redirect, url_for, render_template
import sqlite3

profile_bp = Blueprint('profile_bp', __name__)

@profile_bp.route('/profile')
def profile():
	if 'user' not in session:
		return redirect(url_for('load'))
	
	conn = sqlite3.connect('users.db')
	cur = conn.cursor()
	cur.execute("""
        SELECT 
            CASE 
                WHEN profile_pic LIKE 'static/%' THEN SUBSTR(profile_pic, 7) 
                ELSE profile_pic 
            END as profile_pic, 
            username, email, number, sex 
        FROM user 
        WHERE username=?
    """, (session['user'],))
	user = cur.fetchone()
	conn.close()
	
	return render_template('profile.html', profile_pic =user[0], username=user[1], email=user[2], number =user[3], sex=user[4])