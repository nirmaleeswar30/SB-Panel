import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, CronJob, ActivityLog

# Create blueprint
cronjobs_bp = Blueprint('cronjobs', __name__, url_prefix='/cronjobs')
logger = logging.getLogger(__name__)

@cronjobs_bp.route('/')
@login_required
def index():
    cronjobs = CronJob.query.filter_by(user_id=current_user.id).all()
    containers = Container.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/cronjobs.html', cronjobs=cronjobs, containers=containers)

@cronjobs_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name')
    container_id = request.form.get('container_id')
    command = request.form.get('command')
    schedule = request.form.get('schedule')
    
    # Validation
    if not name or not container_id or not command or not schedule:
        flash('All fields are required.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    # Check if the container exists and belongs to the user
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('Invalid container selected.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    try:
        # Create cron job on the container
        from utils.container import create_cronjob
        create_cronjob(container.container_id, name, command, schedule)
        
        # Create cron job record in database
        cronjob = CronJob(
            user_id=current_user.id,
            container_id=container.id,
            name=name,
            command=command,
            schedule=schedule,
            active=True
        )
        db.session.add(cronjob)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Cron Job Created",
            details=f"Created cron job: {name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Cron job {name} created successfully.', 'success')
    except Exception as e:
        logger.error(f"Error creating cron job: {str(e)}")
        flash(f'Error creating cron job: {str(e)}', 'danger')
    
    return redirect(url_for('cronjobs.index'))

@cronjobs_bp.route('/<int:job_id>/toggle', methods=['POST'])
@login_required
def toggle(job_id):
    cronjob = CronJob.query.get_or_404(job_id)
    
    # Check if user owns this cron job
    if cronjob.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    container = Container.query.get(cronjob.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    try:
        # Toggle cron job
        cronjob.active = not cronjob.active
        
        # Update cron job on the container
        from utils.container import toggle_cronjob
        toggle_cronjob(container.container_id, cronjob.name, cronjob.active)
        
        # Log activity
        action = "Cron Job Enabled" if cronjob.active else "Cron Job Disabled"
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            details=f"{action}: {cronjob.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        message = f'Cron job {cronjob.name} {"enabled" if cronjob.active else "disabled"} successfully.'
        flash(message, 'success')
    except Exception as e:
        logger.error(f"Error toggling cron job: {str(e)}")
        flash(f'Error toggling cron job: {str(e)}', 'danger')
    
    return redirect(url_for('cronjobs.index'))

@cronjobs_bp.route('/<int:job_id>/delete', methods=['POST'])
@login_required
def delete(job_id):
    cronjob = CronJob.query.get_or_404(job_id)
    
    # Check if user owns this cron job
    if cronjob.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    container = Container.query.get(cronjob.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('cronjobs.index'))
    
    try:
        # Delete cron job on the container
        from utils.container import delete_cronjob
        delete_cronjob(container.container_id, cronjob.name)
        
        job_name = cronjob.name
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Cron Job Deleted",
            details=f"Deleted cron job: {job_name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        # Delete cron job from database
        db.session.delete(cronjob)
        db.session.commit()
        
        flash(f'Cron job {job_name} deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting cron job: {str(e)}")
        flash(f'Error deleting cron job: {str(e)}', 'danger')
    
    return redirect(url_for('cronjobs.index'))
