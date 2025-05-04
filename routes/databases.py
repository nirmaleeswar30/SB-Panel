import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, Database, ActivityLog
from utils.database import create_database, delete_database, generate_password

# Create blueprint
databases_bp = Blueprint('databases', __name__, url_prefix='/databases')
logger = logging.getLogger(__name__)

@databases_bp.route('/')
@login_required
def index():
    databases = Database.query.filter_by(user_id=current_user.id).all()
    containers = Container.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/databases.html', databases=databases, containers=containers)

@databases_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name')
    container_id = request.form.get('container_id')
    db_type = request.form.get('db_type', 'mysql')
    db_user = request.form.get('db_user')
    db_password = request.form.get('db_password')
    remote_access = 'remote_access' in request.form
    
    # Validation
    if not name or not container_id or not db_user:
        flash('Database name, container, and username are required.', 'danger')
        return redirect(url_for('databases.index'))
    
    # Check if database with this name already exists for this user
    if Database.query.filter_by(user_id=current_user.id, name=name).first():
        flash('A database with this name already exists.', 'danger')
        return redirect(url_for('databases.index'))
    
    # Check if the container exists and belongs to the user
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('Invalid container selected.', 'danger')
        return redirect(url_for('databases.index'))
    
    # Generate password if not provided
    if not db_password:
        db_password = generate_password()
    
    try:
        # Create database on the container
        create_database(
            container.container_id,
            name,
            db_type,
            db_user,
            db_password,
            remote_access
        )
        
        # Create database record in database
        database = Database(
            user_id=current_user.id,
            container_id=container.id,
            name=name,
            db_type=db_type,
            db_user=db_user,
            db_password=db_password,
            remote_access=remote_access
        )
        db.session.add(database)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Database Created",
            details=f"Created database: {name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Database {name} created successfully.', 'success')
    except Exception as e:
        logger.error(f"Error creating database: {str(e)}")
        flash(f'Error creating database: {str(e)}', 'danger')
    
    return redirect(url_for('databases.index'))

@databases_bp.route('/<int:database_id>/delete', methods=['POST'])
@login_required
def delete(database_id):
    database = Database.query.get_or_404(database_id)
    
    # Check if user owns this database
    if database.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('databases.index'))
    
    container = Container.query.get(database.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('databases.index'))
    
    try:
        # Delete database on the container
        delete_database(
            container.container_id,
            database.name,
            database.db_type,
            database.db_user
        )
        
        db_name = database.name
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Database Deleted",
            details=f"Deleted database: {db_name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        # Delete database from database
        db.session.delete(database)
        db.session.commit()
        
        flash(f'Database {db_name} deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting database: {str(e)}")
        flash(f'Error deleting database: {str(e)}', 'danger')
    
    return redirect(url_for('databases.index'))

@databases_bp.route('/<int:database_id>/toggle_remote', methods=['POST'])
@login_required
def toggle_remote(database_id):
    database = Database.query.get_or_404(database_id)
    
    # Check if user owns this database
    if database.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('databases.index'))
    
    container = Container.query.get(database.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('databases.index'))
    
    try:
        # Toggle remote access
        database.remote_access = not database.remote_access
        
        # Update database configuration
        # This would update the database server configuration to allow/disallow remote access
        # Implementation depends on the database type
        
        # Log activity
        action = "Remote Access Enabled" if database.remote_access else "Remote Access Disabled"
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            details=f"{action} for database: {database.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        message = f'Remote access {"enabled" if database.remote_access else "disabled"} for {database.name}.'
        flash(message, 'success')
    except Exception as e:
        logger.error(f"Error toggling remote access: {str(e)}")
        flash(f'Error toggling remote access: {str(e)}', 'danger')
    
    return redirect(url_for('databases.index'))
