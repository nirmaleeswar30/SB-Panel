import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_required, current_user
from app import db # Assuming app.py initializes db
from models import Container, Service, ActivityLog
# Import the two new functions and get_container_ip
from utils.container import create_base_docker_container, provision_container_software, \
                            start_container as start_docker_container, \
                            stop_container as stop_docker_container, \
                            restart_container as restart_docker_container, \
                            delete_container as delete_docker_container, \
                            get_container_ip
import threading # For background tasks

# Create blueprint
containers_bp = Blueprint('containers', __name__, url_prefix='/containers')
logger = logging.getLogger(__name__)

def _run_provisioning_in_background(app_context, container_db_id, container_docker_id, template):
    with app_context: # Need app context for db operations in thread
        try:
            logger.info(f"Background provisioning started for DB ID {container_db_id}, Docker ID {container_docker_id}")
            provision_container_software(container_docker_id, template)
            
            # Update DB record on successful provisioning
            container_to_update = Container.query.get(container_db_id)
            if container_to_update:
                container_to_update.status = 'running'
                container_to_update.ip_address = get_container_ip(container_docker_id)
                db.session.commit()
                logger.info(f"Background provisioning SUCCESS for DB ID {container_db_id}, Docker ID {container_docker_id}. Status set to running.")
            else:
                logger.error(f"Container DB record {container_db_id} not found after provisioning.")

        except Exception as e:
            logger.error(f"Background provisioning FAILED for DB ID {container_db_id}, Docker ID {container_docker_id}: {str(e)}")
            container_to_update = Container.query.get(container_db_id)
            if container_to_update:
                container_to_update.status = 'error_provisioning'
                # Optionally, try to stop/delete the partially created Docker container
                try:
                    stop_docker_container(container_docker_id) # Stop it
                    # delete_docker_container(container_docker_id) # Or delete it
                    logger.info(f"Partially provisioned Docker container {container_docker_id} stopped.")
                except Exception as docker_err:
                    logger.error(f"Could not stop/delete partially provisioned Docker container {container_docker_id}: {docker_err}")
                db.session.commit()

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
    
    if not name or not template:
        flash('Container name and template are required.', 'danger')
        return redirect(url_for('containers.index'))
    
    if Container.query.filter_by(user_id=current_user.id, name=name).first():
        flash('A container with this name already exists for your account.', 'danger')
        return redirect(url_for('containers.index'))
    
    # Resource limits (these are for the Docker container creation)
    # Using defaults from user model, can be overridden by admin later or form
    cpu_allocated = current_user.cpu_limit # Or a default specific to new containers
    memory_allocated = current_user.memory_limit 
    disk_allocated = current_user.disk_limit 
    
    # The actual Docker container name needs to be unique globally
    # The `name` from form is for user display and part of the Docker name.
    container_name_docker = f"user{current_user.id}-{name.lower().replace(' ', '-')}"


    # 1. Create placeholder DB record
    container_db_record = Container(
        name=name,
        user_id=current_user.id,
        container_id=container_name_docker, # Tentative, confirmed/updated after docker create
        template=template,
        status='creating', # Initial status
        cpu_allocated=cpu_allocated,
        memory_allocated=memory_allocated,
        disk_allocated=disk_allocated # Soft limit
    )
    db.session.add(container_db_record)
    db.session.commit() # Commit to get container_db_record.id

    try:
        # 2. Create the base Docker container (fast part)
        # Image name for ubuntu:20.04, could be dynamic based on template
        image_to_use = "ubuntu:20.04" 
        actual_docker_id = create_base_docker_container(
            container_name_docker, 
            image_to_use, 
            cpu_allocated, 
            memory_allocated, 
            disk_allocated
        )
        
        # Update DB record with actual Docker ID if it was different (shouldn't be if name is unique)
        # and potentially an initial IP.
        container_db_record.container_id = actual_docker_id # Docker container ID/Name
        container_db_record.ip_address = get_container_ip(actual_docker_id)
        db.session.commit()

        # 3. Start software provisioning in a background thread
        # Pass current_app.app_context() to use in the thread
        app_ctx = current_app.app_context()
        provisioning_thread = threading.Thread(
            target=_run_provisioning_in_background, 
            args=(app_ctx, container_db_record.id, actual_docker_id, template)
        )
        provisioning_thread.start()

        log = ActivityLog(
            user_id=current_user.id, action="Container Creation Initiated",
            details=f"Initiated creation for container: {name} (Docker ID: {actual_docker_id})",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Container {name} creation initiated. It will appear as "creating" and will be ready in a few minutes.', 'info')
    
    except Exception as e:
        db.session.rollback() # Rollback the initial DB record if base docker creation failed
        # If container_db_record was added, try to delete it or mark as error
        if container_db_record.id:
             existing_rec = Container.query.get(container_db_record.id)
             if existing_rec:
                 existing_rec.status = 'error_creating_base'
                 db.session.commit()
             else: # If somehow it was deleted or not found after rollback, try to delete any partial
                  Container.query.filter_by(name=name, user_id=current_user.id, status='creating').delete()
                  db.session.commit()


        logger.error(f"Error initiating container creation for {name}: {str(e)}")
        flash(f'Error initiating container creation: {str(e)}', 'danger')
    
    return redirect(url_for('containers.index'))


@containers_bp.route('/<int:container_db_id>/start', methods=['POST'])
@login_required
def start(container_db_id):
    container = Container.query.get_or_404(container_db_id)
    if container.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        start_docker_container(container.container_id) # container.container_id is the Docker name/ID
        container.status = 'running'
        container.ip_address = get_container_ip(container.container_id) # Refresh IP on start
        log = ActivityLog(user_id=current_user.id, action="Container Started", details=f"Started container: {container.name}", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Container {container.name} started successfully.', 'success')
    except Exception as e:
        logger.error(f"Error starting container {container.name}: {str(e)}")
        flash(f'Error starting container: {str(e)}', 'danger')
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_db_id>/stop', methods=['POST'])
@login_required
def stop(container_db_id):
    container = Container.query.get_or_404(container_db_id)
    if container.user_id != current_user.id:
        flash('You do not have permission.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        stop_docker_container(container.container_id)
        container.status = 'stopped'
        log = ActivityLog(user_id=current_user.id, action="Container Stopped", details=f"Stopped container: {container.name}", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Container {container.name} stopped successfully.', 'success')
    except Exception as e:
        logger.error(f"Error stopping container {container.name}: {str(e)}")
        flash(f'Error stopping container: {str(e)}', 'danger')
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_db_id>/restart', methods=['POST'])
@login_required
def restart(container_db_id):
    container = Container.query.get_or_404(container_db_id)
    if container.user_id != current_user.id:
        flash('You do not have permission.', 'danger')
        return redirect(url_for('containers.index'))
    
    try:
        restart_docker_container(container.container_id)
        container.status = 'running' # Assumes restart leads to running
        container.ip_address = get_container_ip(container.container_id) # Refresh IP
        log = ActivityLog(user_id=current_user.id, action="Container Restarted", details=f"Restarted container: {container.name}", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Container {container.name} restarted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error restarting container {container.name}: {str(e)}")
        flash(f'Error restarting container: {str(e)}', 'danger')
    return redirect(url_for('containers.index'))

@containers_bp.route('/<int:container_db_id>/delete', methods=['POST'])
@login_required
def delete(container_db_id):
    container = Container.query.get_or_404(container_db_id)
    if container.user_id != current_user.id:
        flash('You do not have permission.', 'danger')
        return redirect(url_for('containers.index'))
    
    # Check for associated websites, databases etc. before deleting (from models.py relationships)
    from models import Website, Database # Import here to avoid circular dependency issues
    if Website.query.filter_by(container_id=container.id).count() > 0 or \
       Database.query.filter_by(container_id=container.id).count() > 0:
        flash('Cannot delete container with associated websites or databases. Delete them first.', 'danger')
        return redirect(url_for('containers.index'))

    try:
        docker_id_to_delete = container.container_id
        container_display_name = container.name # Store for logging before deleting DB record

        # Delete services related to this container from DB first
        Service.query.filter_by(container_id=container.id).delete()
        
        # Delete the container DB record
        db.session.delete(container)
        
        # Then delete the Docker container
        delete_docker_container(docker_id_to_delete) # This will stop it if running
        
        log = ActivityLog(user_id=current_user.id, action="Container Deleted", details=f"Deleted container: {container_display_name} (Docker ID: {docker_id_to_delete})", ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Container {container_display_name} deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback() # Rollback DB changes if Docker deletion fails
        logger.error(f"Error deleting container {container.name}: {str(e)}")
        flash(f'Error deleting container: {str(e)}', 'danger')
    return redirect(url_for('containers.index'))

# (Optional) Endpoint to check provisioning status if you implement AJAX polling in JS
@containers_bp.route('/<int:container_db_id>/status_check', methods=['GET'])
@login_required
def status_check(container_db_id):
    container = Container.query.get_or_404(container_db_id)
    if container.user_id != current_user.id:
        return jsonify({'error': 'Permission denied'}), 403
    return jsonify({
        'id': container.id,
        'name': container.name,
        'status': container.status,
        'ip_address': container.ip_address
    })
