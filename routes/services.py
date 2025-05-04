import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, Service, ActivityLog
from utils.container import start_service, stop_service, restart_service

# Create blueprint
services_bp = Blueprint('services', __name__, url_prefix='/services')
logger = logging.getLogger(__name__)

@services_bp.route('/')
@login_required
def index():
    # Get all containers belonging to the user
    containers = Container.query.filter_by(user_id=current_user.id).all()
    
    # Get all services
    services = []
    for container in containers:
        container_services = Service.query.filter_by(container_id=container.id).all()
        services.extend(container_services)
    
    return render_template('dashboard/services.html', services=services, containers=containers)

@services_bp.route('/start/<int:service_id>', methods=['POST'])
@login_required
def start(service_id):
    service = Service.query.get_or_404(service_id)
    container = Container.query.get(service.container_id)
    
    # Check if user owns this container
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('services.index'))
    
    try:
        # Start the service
        start_service(container.container_id, service.name)
        service.status = 'running'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Service Started",
            details=f"Started service: {service.name} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Service {service.name} started successfully.', 'success')
    except Exception as e:
        logger.error(f"Error starting service: {str(e)}")
        flash(f'Error starting service: {str(e)}', 'danger')
    
    return redirect(url_for('services.index'))

@services_bp.route('/stop/<int:service_id>', methods=['POST'])
@login_required
def stop(service_id):
    service = Service.query.get_or_404(service_id)
    container = Container.query.get(service.container_id)
    
    # Check if user owns this container
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('services.index'))
    
    try:
        # Stop the service
        stop_service(container.container_id, service.name)
        service.status = 'stopped'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Service Stopped",
            details=f"Stopped service: {service.name} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Service {service.name} stopped successfully.', 'success')
    except Exception as e:
        logger.error(f"Error stopping service: {str(e)}")
        flash(f'Error stopping service: {str(e)}', 'danger')
    
    return redirect(url_for('services.index'))

@services_bp.route('/restart/<int:service_id>', methods=['POST'])
@login_required
def restart(service_id):
    service = Service.query.get_or_404(service_id)
    container = Container.query.get(service.container_id)
    
    # Check if user owns this container
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('services.index'))
    
    try:
        # Restart the service
        restart_service(container.container_id, service.name)
        service.status = 'running'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Service Restarted",
            details=f"Restarted service: {service.name} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Service {service.name} restarted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error restarting service: {str(e)}")
        flash(f'Error restarting service: {str(e)}', 'danger')
    
    return redirect(url_for('services.index'))

@services_bp.route('/toggle_autostart/<int:service_id>', methods=['POST'])
@login_required
def toggle_autostart(service_id):
    service = Service.query.get_or_404(service_id)
    container = Container.query.get(service.container_id)
    
    # Check if user owns this container
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('services.index'))
    
    try:
        # Toggle auto_start
        service.auto_start = not service.auto_start
        
        # Log activity
        action = "Auto-start Enabled" if service.auto_start else "Auto-start Disabled"
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            details=f"{action} for service: {service.name} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        message = f'Auto-start {"enabled" if service.auto_start else "disabled"} for {service.name}.'
        flash(message, 'success')
    except Exception as e:
        logger.error(f"Error toggling auto-start: {str(e)}")
        flash(f'Error toggling auto-start: {str(e)}', 'danger')
    
    return redirect(url_for('services.index'))
