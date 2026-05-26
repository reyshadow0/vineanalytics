from functools import wraps
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from models import get_user_by_username
from audit import registrar_evento

auth_bp = Blueprint('auth', __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if it's an API request, if so return 401 instead of redirecting
            if request.path.startswith('/interactions') or request.path.startswith('/summary') or request.path.startswith('/charts') or request.path.startswith('/export'):
                return {'status': 'error', 'message': 'No autorizado'}, 401
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('rol') != 'admin':
            return {'status': 'error', 'message': 'Acceso denegado'}, 403
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['rol'] = user['rol']
            
            registrar_evento(user['username'], user['rol'], "LOGIN_EXITOSO", None, request.remote_addr)
            
            # Redirect to next url or index
            next_url = request.args.get('next')
            if not next_url or not next_url.startswith('/'):
                next_url = url_for('home')
            return redirect(next_url)
        else:
            registrar_evento(username or 'desconocido', 'desconocido', "LOGIN_FALLIDO", None, request.remote_addr)
            flash('Usuario o contraseña incorrectos', 'error')
            
    # Redirect to index if already logged in
    if 'user_id' in session:
        return redirect(url_for('home'))
        
    return render_template('login.html')

@auth_bp.route('/logout')
def logout():
    if 'user_id' in session:
        registrar_evento(session['username'], session['rol'], "LOGOUT", None, request.remote_addr)
    session.clear()
    return redirect(url_for('auth.login'))
