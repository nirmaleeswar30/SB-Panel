import logging
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file
from flask_login import login_required, current_user
from app import db
from models import Container, ActivityLog
from werkzeug.utils import secure_filename
import tempfile

# Create blueprint
files_bp = Blueprint('files', __name__, url_prefix='/files')
logger = logging.getLogger(__name__)

@files_bp.route('/')
@login_required
def index():
    # Get all containers belonging to the user
    containers = Container.query.filter_by(user_id=current_user.id).all()
    
    # Default to first container if none specified
    container_id = request.args.get('container_id')
    
    if not container_id and containers:
        container_id = containers[0].id
    
    # Current directory
    current_dir = request.args.get('path', '/')
    
    # Files and directories in current path
    files = []
    if container_id:
        container = Container.query.get(container_id)
        if container and container.user_id == current_user.id:
            try:
                from utils.container import list_files
                files = list_files(container.container_id, current_dir)
            except Exception as e:
                logger.error(f"Error listing files: {str(e)}")
                flash(f'Error listing files: {str(e)}', 'danger')
    
    return render_template('dashboard/files.html', 
                          containers=containers, 
                          container_id=int(container_id) if container_id else None,
                          current_dir=current_dir,
                          files=files)

@files_bp.route('/view')
@login_required
def view():
    container_id = request.args.get('container_id')
    file_path = request.args.get('path')
    
    if not container_id or not file_path:
        flash('Container ID and file path are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import read_file
        content = read_file(container.container_id, file_path)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="File Viewed",
            details=f"Viewed file: {file_path} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        return render_template('dashboard/file_editor.html', 
                              container=container,
                              file_path=file_path,
                              content=content)
    except Exception as e:
        logger.error(f"Error reading file: {str(e)}")
        flash(f'Error reading file: {str(e)}', 'danger')
        return redirect(url_for('files.index', container_id=container_id, path=os.path.dirname(file_path)))

@files_bp.route('/edit', methods=['POST'])
@login_required
def edit():
    container_id = request.form.get('container_id')
    file_path = request.form.get('file_path')
    content = request.form.get('content', '')
    
    if not container_id or not file_path:
        flash('Container ID and file path are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import write_file
        write_file(container.container_id, file_path, content)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="File Edited",
            details=f"Edited file: {file_path} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'File {file_path} saved successfully.', 'success')
        return redirect(url_for('files.view', container_id=container_id, path=file_path))
    except Exception as e:
        logger.error(f"Error writing file: {str(e)}")
        flash(f'Error writing file: {str(e)}', 'danger')
        return redirect(url_for('files.view', container_id=container_id, path=file_path))

@files_bp.route('/mkdir', methods=['POST'])
@login_required
def mkdir():
    container_id = request.form.get('container_id')
    current_dir = request.form.get('current_dir')
    dir_name = request.form.get('dir_name')
    
    if not container_id or not current_dir or not dir_name:
        flash('Container ID, current directory, and directory name are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import create_directory
        dir_path = os.path.join(current_dir, dir_name)
        create_directory(container.container_id, dir_path)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Directory Created",
            details=f"Created directory: {dir_path} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'Directory {dir_name} created successfully.', 'success')
    except Exception as e:
        logger.error(f"Error creating directory: {str(e)}")
        flash(f'Error creating directory: {str(e)}', 'danger')
    
    return redirect(url_for('files.index', container_id=container_id, path=current_dir))

@files_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    container_id = request.form.get('container_id')
    current_dir = request.form.get('current_dir')
    file = request.files.get('file')
    
    if not container_id or not current_dir or not file:
        flash('Container ID, current directory, and file are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        filename = secure_filename(file.filename)
        file_path = os.path.join(current_dir, filename)
        
        # Save the file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp:
            file.save(temp.name)
            
            # Upload the file to the container
            from utils.container import upload_file
            upload_file(container.container_id, temp.name, file_path)
        
        # Remove temporary file
        os.unlink(temp.name)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="File Uploaded",
            details=f"Uploaded file: {file_path} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'File {filename} uploaded successfully.', 'success')
    except Exception as e:
        logger.error(f"Error uploading file: {str(e)}")
        flash(f'Error uploading file: {str(e)}', 'danger')
    
    return redirect(url_for('files.index', container_id=container_id, path=current_dir))

@files_bp.route('/download')
@login_required
def download():
    container_id = request.args.get('container_id')
    file_path = request.args.get('path')
    
    if not container_id or not file_path:
        flash('Container ID and file path are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import download_file
        temp_file = download_file(container.container_id, file_path)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="File Downloaded",
            details=f"Downloaded file: {file_path} from container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        return send_file(temp_file, as_attachment=True, download_name=os.path.basename(file_path))
    except Exception as e:
        logger.error(f"Error downloading file: {str(e)}")
        flash(f'Error downloading file: {str(e)}', 'danger')
        return redirect(url_for('files.index', container_id=container_id, path=os.path.dirname(file_path)))

@files_bp.route('/delete', methods=['POST'])
@login_required
def delete():
    container_id = request.form.get('container_id')
    file_path = request.form.get('file_path')
    
    if not container_id or not file_path:
        flash('Container ID and file path are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import delete_file
        delete_file(container.container_id, file_path)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="File Deleted",
            details=f"Deleted file: {file_path} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'File {os.path.basename(file_path)} deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting file: {str(e)}")
        flash(f'Error deleting file: {str(e)}', 'danger')
    
    return redirect(url_for('files.index', container_id=container_id, path=os.path.dirname(file_path)))

@files_bp.route('/download_url', methods=['POST'])
@login_required
def download_url():
    container_id = request.form.get('container_id')
    current_dir = request.form.get('current_dir')
    url = request.form.get('url')
    
    if not container_id or not current_dir or not url:
        flash('Container ID, current directory, and URL are required.', 'danger')
        return redirect(url_for('files.index'))
    
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('You do not have permission to access this container.', 'danger')
        return redirect(url_for('files.index'))
    
    try:
        from utils.container import download_url_to_container
        filename = download_url_to_container(container.container_id, url, current_dir)
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="URL Downloaded",
            details=f"Downloaded URL: {url} to {current_dir}/{filename} on container: {container.name}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash(f'URL downloaded successfully as {filename}.', 'success')
    except Exception as e:
        logger.error(f"Error downloading URL: {str(e)}")
        flash(f'Error downloading URL: {str(e)}', 'danger')
    
    return redirect(url_for('files.index', container_id=container_id, path=current_dir))
