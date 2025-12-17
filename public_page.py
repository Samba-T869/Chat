from flask import Blueprint, session, render_template, redirect, url_for

public_bp = Blueprint('public_bp', __name__)

@public_bp.route('/public')
def public():
	if 'user' not in session:
		return redirect(url_for('load'))
	return render_template('public.html')