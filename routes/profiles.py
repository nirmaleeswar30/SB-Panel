import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from models import User, ActivityLog, SSHKey, Favorite
from werkzeug.security import check_password_hash

# Create blueprint
profiles_bp = Blueprint('profiles', __name__, url_prefix='/profile')
logger = logging.getLogger(__name__)

@profiles_bp.route('/')
@login_required
def index():
    ssh_keys = SSHKey.query.filter_by(user_id=current_user.id).all()
    favorites = Favorite.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/profile.html', ssh_keys=ssh_keys, favorites=favorites)

@profiles_bp.route('/update', methods=['POST'])
@login_required
def update():
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Update email
    if email and email != current_user.email:
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered to another account.', 'danger')
        else:
            current_user.email = email
            
            # Log activity
            log = ActivityLog(
                user_id=current_user.id,
                action="Profile Updated",
                details="Updated email address",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Email updated successfully.', 'success')
    
    # Update password
    if current_password and new_password and confirm_password:
        if not check_password_hash(current_user.password_hash, current_password):
            flash('Current password is incorrect.', 'danger')
        elif new_password != confirm_password:
            flash('New passwords do not match.', 'danger')
        else:
            current_user.set_password(new_password)
            
            # Log activity
            log = ActivityLog(
                user_id=current_user.id,
                action="Password Changed",
                details="Password was changed",
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            
            flash('Password updated successfully.', 'success')
    
    return redirect(url_for('profiles.index'))

@profiles_bp.route('/ssh/add', methods=['POST'])
@login_required
def add_ssh_key():
    name = request.form.get('name')
    public_key = request.form.get('public_key')
    
    if not name or not public_key:
        flash('Name and public key are required.', 'danger')
        return redirect(url_for('profiles.index'))
    
    # Check if SSH key with this name already exists
    if SSHKey.query.filter_by(user_id=current_user.id, name=name).first():
        flash('An SSH key with this name already exists.', 'danger')
        return redirect(url_for('profiles.index'))
    
    # Create SSH key
    ssh_key = SSHKey(
        user_id=current_user.id,
        name=name,
        public_key=public_key
    )
    db.session.add(ssh_key)
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="SSH Key Added",
        details=f"Added SSH key: {name}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash(f'SSH key {name} added successfully.', 'success')
    return redirect(url_for('profiles.index'))

@profiles_bp.route('/ssh/delete/<int:key_id>', methods=['POST'])
@login_required
def delete_ssh_key(key_id):
    ssh_key = SSHKey.query.get_or_404(key_id)
    
    # Check if user owns this SSH key
    if ssh_key.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('profiles.index'))
    
    key_name = ssh_key.name
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="SSH Key Deleted",
        details=f"Deleted SSH key: {key_name}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    # Delete SSH key
    db.session.delete(ssh_key)
    db.session.commit()
    
    flash(f'SSH key {key_name} deleted successfully.', 'success')
    return redirect(url_for('profiles.index'))

@profiles_bp.route('/favorite/add', methods=['POST'])
@login_required
def add_favorite():
    page_url = request.form.get('page_url')
    page_name = request.form.get('page_name')
    
    if not page_url or not page_name:
        flash('Page URL and name are required.', 'danger')
        return redirect(request.referrer or url_for('dashboard.index'))
    
    # Check if favorite already exists
    if Favorite.query.filter_by(user_id=current_user.id, page_url=page_url).first():
        flash('This page is already in your favorites.', 'info')
        return redirect(request.referrer or url_for('dashboard.index'))
    
    # Create favorite
    favorite = Favorite(
        user_id=current_user.id,
        page_url=page_url,
        page_name=page_name
    )
    db.session.add(favorite)
    db.session.commit()
    
    flash(f'Added {page_name} to favorites.', 'success')
    return redirect(request.referrer or url_for('dashboard.index'))

@profiles_bp.route('/favorite/delete/<int:favorite_id>', methods=['POST'])
@login_required
def delete_favorite(favorite_id):
    favorite = Favorite.query.get_or_404(favorite_id)
    
    # Check if user owns this favorite
    if favorite.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('profiles.index'))
    
    favorite_name = favorite.page_name
    
    # Delete favorite
    db.session.delete(favorite)
    db.session.commit()
    
    flash(f'Removed {favorite_name} from favorites.', 'success')
    return redirect(url_for('profiles.index'))
