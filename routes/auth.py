import logging
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from app import db
from models import User, ActivityLog

# Create blueprint
auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)

@auth_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember' in request.form
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            if not user.active:
                flash('Your account is disabled. Please contact the administrator.', 'danger')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=remember)
            
            # Update last login time
            user.last_login = datetime.utcnow()
            
            # Log activity
            log = ActivityLog(
                user_id=user.id,
                action="User Login",
                details="User logged in successfully",
                ip_address=request.remote_addr
            )
            
            db.session.add(log)
            db.session.commit()
            
            flash('Login successful!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="User Logout",
        details="User logged out",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    # Check if registration is allowed (system setting)
    from models import SystemSetting
    
    registration_allowed = True
    setting = SystemSetting.query.filter_by(key='allow_registration').first()
    if setting and setting.value.lower() == 'false':
        registration_allowed = False
    
    if not registration_allowed:
        flash('Registration is currently disabled. Please contact the administrator.', 'warning')
        return redirect(url_for('auth.login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        # Validation
        error = None
        if not username:
            error = 'Username is required.'
        elif not email:
            error = 'Email is required.'
        elif not password:
            error = 'Password is required.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif User.query.filter_by(username=username).first():
            error = 'Username already exists.'
        elif User.query.filter_by(email=email).first():
            error = 'Email already registered.'
        
        if error:
            flash(error, 'danger')
        else:
            # Create a new user with default resource limits
            user = User(
                username=username,
                email=email,
                role='user',
                cpu_limit=1,
                memory_limit=1024,  # 1GB
                disk_limit=10240   # 10GB
            )
            user.set_password(password)
            
            # Default role is 'user'
            # If this is the first user, make them an admin
            if User.query.count() == 0:
                user.role = 'admin'
            
            # Add user to the session and commit to get the user.id
            db.session.add(user)
            db.session.commit()
            
            # Now that the user has an ID, log the activity
            log = ActivityLog(
                user_id=user.id,
                action="User Registration",
                details="New user account created",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('auth.login'))
    
    return render_template('register.html')
