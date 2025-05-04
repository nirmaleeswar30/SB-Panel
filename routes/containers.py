import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, Service, ActivityLog
from utils.container import create_container, start_container, stop_container, restart_container, delete_container

# Create blueprint
containers_bp = Blueprint('containers', __name__, url_prefix='/containers')
logger = logging.getLogger(__name__)

@containers_bp.route('/')
@login_required
def index():
    containers = Container.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/containers.html', containers=containers)

@containers_bp.route('/create', methods=['POST'])
@login_required
def create():
    name = request.form.get('name')
    template = request.form.get('template')
    
    # Validation
    if not name or not template:
        flash('Container name and template are required.', 'danger')
        return redirect(url_for('containers.index'))
    
    # Check if container with this name already exists
    if Container.query.filter_by(user_id=current_user.id, name=name).first():
        flash('A container with this name already exists.', 'danger')
        return redirect(url_for('containers.index'))
    
    # Check if user is within resource limits
    containers = Container.query.filter_by(user_id=current_user.id).all()
    total_cpu = sum(c.cpu_allocated for c in containers)
    total_memory = sum(c.memory_allocated for c in containers)
    total_disk = sum(c.disk_allocated for c in containers)
    
    # Default resource allocation for new container
    cpu_allocated = 1
    memory_allocated = 1024  # 1GB
    disk_allocated = 5120    # 5GB
    
    # Check if user has enough resources available
    if total_cpu + cpu_allocated > current_user.cpu_limit:
        flash('You have reached your CPU resource limit.', 'danger')
        return redirect(url_for('containers.index'))
    
    if total_memory + memory_allocated > current_user.memory_limit:
        flash('You have reached your memory resource limit.', 'danger')
        return redirect(url_for('containers.index'))
    
    if total_disk + disk_allocated > current_user.disk_limit:
        flash('You have reached your disk resource limit.', 'danger')
        return redirect(url_for('containers.index'))
    
    # Create container
    try:
        container_id = create_container(name, template, current_user.id, 
                                      cpu_allocated, memory_allocated, disk_allocated)
        
        # Create container record in database
        container = Container(
            name=name,
            user_id=current_user.id,
            container_id=container_id,
            template=template,
            status='stopped',
            cpu_allocated=cpu_allocated,
            memory_allocated=memory_allocated,
            disk_allocated=disk_allocated
        )
        db.session.add(container)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Container Created",
            details=f"Created container: {name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Container {name} created successfully.', 'success')
    except Exception as e:
        logger.error(f"Error creating container: {str(e)}")
        flash(f'Error creating container: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_id>/start', methods=['POST'])
@login_required
def start(container_id):
    container = Container.query.get_or_404(container_id)
    
    # Check if user owns this container
    if container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        start_container(container.container_id)
        container.status = 'running'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Container Started",
            details=f"Started container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Container {container.name} started successfully.', 'success')
    except Exception as e:
        logger.error(f"Error starting container: {str(e)}")
        flash(f'Error starting container: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_id>/stop', methods=['POST'])
@login_required
def stop(container_id):
    container = Container.query.get_or_404(container_id)
    
    # Check if user owns this container
    if container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        stop_container(container.container_id)
        container.status = 'stopped'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Container Stopped",
            details=f"Stopped container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Container {container.name} stopped successfully.', 'success')
    except Exception as e:
        logger.error(f"Error stopping container: {str(e)}")
        flash(f'Error stopping container: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_id>/restart', methods=['POST'])
@login_required
def restart(container_id):
    container = Container.query.get_or_404(container_id)
    
    # Check if user owns this container
    if container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        restart_container(container.container_id)
        container.status = 'running'
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Container Restarted",
            details=f"Restarted container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Container {container.name} restarted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error restarting container: {str(e)}")
        flash(f'Error restarting container: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_id>/delete', methods=['POST'])
@login_required
def delete(container_id):
    container = Container.query.get_or_404(container_id)
    
    # Check if user owns this container
    if container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        # Check if container has associated websites or databases
        from models import Website, Database
        
        websites = Website.query.filter_by(container_id=container.id).count()
        databases = Database.query.filter_by(container_id=container.id).count()
        
        if websites > 0 or databases > 0:
            flash('Cannot delete container with associated websites or databases. Delete them first.', 'danger')
            return redirect(url_for('containers.index'))
        
        container_name = container.name
        
        # Delete services
        Service.query.filter_by(container_id=container.id).delete()
        
        # Delete container in LXD
        delete_container(container.container_id)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Container Deleted",
            details=f"Deleted container: {container_name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        # Delete container from database
        db.session.delete(container)
        db.session.commit()
        
        flash(f'Container {container_name} deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting container: {str(e)}")
        flash(f'Error deleting container: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))
