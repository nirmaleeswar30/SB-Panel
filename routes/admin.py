import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import User, Container, Website, Database, Service, ActivityLog, SystemSetting

# Create blueprint
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')
logger = logging.getLogger(__name__)

# Admin access decorator
def admin_required(f):
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.role == 'admin':
            flash('You need administrator rights to access this page.', 'danger')
            return redirect(url_for('dashboard.index'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/')
@admin_required
def index():
    return redirect(url_for('admin.users'))

@admin_bp.route('/users')
@admin_required
def users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role', 'user')
    
    # Validation
    if not username or not email or not password:
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))
    
    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'danger')
        return redirect(url_for('admin.users'))
    
    if User.query.filter_by(email=email).first():
        flash('Email already registered.', 'danger')
        return redirect(url_for('admin.users'))
    
    # Create the user
    user = User(
        username=username,
        email=email,
        role=role,
        cpu_limit=int(request.form.get('cpu_limit', 1)),
        memory_limit=int(request.form.get('memory_limit', 1024)),
        disk_limit=int(request.form.get('disk_limit', 10240))
    )
    user.set_password(password)
    
    db.session.add(user)
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="Admin Created User",
        details=f"Created new user account for {username}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash(f'User {username} created successfully.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Don't allow the last admin to be changed to a normal user
    if user.role == 'admin' and request.form.get('role') != 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot change the last administrator to a normal user.', 'danger')
            return redirect(url_for('admin.users'))
    
    # Update user
    user.username = request.form.get('username', user.username)
    user.email = request.form.get('email', user.email)
    user.role = request.form.get('role', user.role)
    user.active = 'active' in request.form
    user.cpu_limit = int(request.form.get('cpu_limit', user.cpu_limit))
    user.memory_limit = int(request.form.get('memory_limit', user.memory_limit))
    user.disk_limit = int(request.form.get('disk_limit', user.disk_limit))
    
    # Update password if provided
    new_password = request.form.get('password')
    if new_password:
        user.set_password(new_password)
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="Admin Updated User",
        details=f"Updated user account for {user.username}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash(f'User {user.username} updated successfully.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Don't allow deletion of the last admin
    if user.role == 'admin':
        admin_count = User.query.filter_by(role='admin').count()
        if admin_count <= 1:
            flash('Cannot delete the last administrator.', 'danger')
            return redirect(url_for('admin.users'))
    
    # Check if the user has active containers
    containers = Container.query.filter_by(user_id=user.id).all()
    if containers:
        flash('Cannot delete user with active containers. Delete their containers first.', 'danger')
        return redirect(url_for('admin.users'))
    
    username = user.username
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="Admin Deleted User",
        details=f"Deleted user account for {username}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    # Delete the user
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} deleted successfully.', 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/system')
@admin_required
def system():
    settings = SystemSetting.query.all()
    return render_template('admin/system.html', settings=settings)

@admin_bp.route('/system/update', methods=['POST'])
@admin_required
def update_system():
    # Get all form data
    for key, value in request.form.items():
        if key.startswith('setting_'):
            setting_key = key[8:]  # Remove 'setting_' prefix
            
            # Find the setting
            setting = SystemSetting.query.filter_by(key=setting_key).first()
            
            # If setting exists, update it
            if setting:
                setting.value = value
            # Otherwise, create it
            else:
                setting = SystemSetting(key=setting_key, value=value)
                db.session.add(setting)
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="Admin Updated System Settings",
        details="Updated system configuration settings",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash('System settings updated successfully.', 'success')
    return redirect(url_for('admin.system'))

@admin_bp.route('/logs')
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    
    logs = ActivityLog.query.order_by(ActivityLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    return render_template('admin/logs.html', logs=logs)

@admin_bp.route('/logs/clear', methods=['POST'])
@admin_required
def clear_logs():
    # Delete all logs
    num_deleted = db.session.query(ActivityLog).delete()
    
    # Create a log for the deletion
    log = ActivityLog(
        user_id=current_user.id,
        action="Admin Cleared Logs",
        details=f"Cleared {num_deleted} log entries",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash('Activity logs cleared successfully.', 'success')
    return redirect(url_for('admin.logs'))
