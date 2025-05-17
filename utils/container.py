import os
import logging
import tempfile
import subprocess
import urllib.request
import uuid
from urllib.parse import urlparse
import docker
from docker.types import Mount 
from docker.errors import NotFound, APIError, ImageNotFound
from datetime import datetime
import io
import tarfile
import time # For potential sleep/retries

logger = logging.getLogger(__name__)

try:
    client = docker.from_env()
    client.ping()
    logger.info("Successfully connected to Docker daemon.")
except docker.errors.DockerException as e:
    logger.error(f"Could not connect to Docker daemon: {e}. SBPanel requires Docker to be running and accessible.")
    logger.warning("Proceeding without a live Docker client. Container operations will likely fail.")
    client = None

class ExecResult:
    def __init__(self, exit_code, stdout, stderr):
        self.exit_code = exit_code
        self.stdout = stdout.decode('utf-8', errors='replace') if stdout else ""
        self.stderr = stderr.decode('utf-8', errors='replace') if stderr else ""

def _execute_in_container(container_id_or_name, command_list, ignore_failure=False, tty_for_exec=False):
    if client is None:
        logger.error("Docker client not initialized. Cannot execute command.")
        return ExecResult(127, b"", b"Docker client not initialized")
    try:
        container_obj = client.containers.get(container_id_or_name)
        exec_output = container_obj.exec_run(command_list, tty=tty_for_exec, demux=not tty_for_exec)
        
        exit_code = exec_output.exit_code
        
        if tty_for_exec:
            stdout_bytes = exec_output.output
            stderr_bytes = b""
        else:
            stdout_bytes = exec_output.output[0]
            stderr_bytes = exec_output.output[1]
            
        result = ExecResult(exit_code, stdout_bytes, stderr_bytes)

        if not ignore_failure and result.exit_code != 0:
            log_msg = f"Command '{' '.join(command_list)}' in {container_id_or_name} failed with exit code {result.exit_code}"
            if result.stderr: log_msg += f": STDERR: {result.stderr}"
            elif tty_for_exec and result.stdout: log_msg += f": STDOUT: {result.stdout}"
            logger.error(log_msg)
        return result
    except NotFound:
        logger.error(f"Container {container_id_or_name} not found for command execution.")
        return ExecResult(126, b"", f"Container {container_id_or_name} not found".encode())
    except APIError as e:
        logger.error(f"Docker API error executing command in {container_id_or_name}: {e}")
        return ExecResult(125, b"", str(e).encode())
    except TypeError as e: 
        logger.error(f"TypeError processing exec_run output for '{' '.join(command_list)}' in {container_id_or_name}: {e}. Output was: {exec_output if 'exec_output' in locals() else 'unknown'}")
        raw_exit_code = exec_output[0] if isinstance(exec_output, tuple) and len(exec_output) > 0 else 124
        raw_output_str = str(exec_output[1]) if isinstance(exec_output, tuple) and len(exec_output) > 1 else str(e)
        return ExecResult(raw_exit_code, b"", raw_output_str.encode())

def get_container_ip(container_name):
    if client is None: return None
    try:
        container_obj = client.containers.get(container_name)
        container_obj.reload() # Refresh container attributes
        # This gets complex with multiple networks. Assuming default bridge.
        if container_obj.attrs['NetworkSettings']['Networks']:
            # Get the first network's IP address
            first_network = list(container_obj.attrs['NetworkSettings']['Networks'].keys())[0]
            return container_obj.attrs['NetworkSettings']['Networks'][first_network]['IPAddress']
    except Exception as e:
        logger.error(f"Could not get IP for container {container_name}: {e}")
    return None


def create_base_docker_container(container_name_docker, image_name, cpu, memory, disk):
    """Creates and starts the Docker container structure without software provisioning."""
    if client is None:
        raise Exception("Docker client not initialized. Cannot create container.")

    try:
        client.containers.get(container_name_docker)
        raise Exception(f"Docker container {container_name_docker} already exists.")
    except NotFound:
        pass 

    try:
        logger.info(f"Checking for Docker image: {image_name}")
        client.images.get(image_name) 
        logger.info(f"Image {image_name} found locally.")
    except ImageNotFound:
        logger.info(f"Image {image_name} not found locally. Pulling from Docker Hub...")
        try:
            client.images.pull(image_name) 
            logger.info(f"Successfully pulled image {image_name}.")
        except APIError as e:
            logger.error(f"Failed to pull image {image_name}: {e}")
            raise Exception(f"Failed to pull Docker image {image_name}: {e}")

    docker_config = {
        'name': container_name_docker,
        'image': image_name,
        'detach': True,
        'tty': True, 
        'stdin_open': True, 
        'mem_limit': f"{memory}m", 
        'nano_cpus': int(cpu * 1e9), 
    }
    
    logger.warning(f"Disk limit of {disk}MB for container {container_name_docker} is advisory and not strictly enforced by Docker in this setup.")

    try:
        container_obj = client.containers.create(**docker_config)
        container_obj.start()
        logger.info(f"Base Docker container {container_name_docker} created and started from image {image_name}.")
        return container_name_docker # Return the actual Docker container name/ID
    except APIError as e:
        logger.error(f"Failed to create base Docker container {container_name_docker}: {e}")
        raise Exception(f"Failed to create base Docker container: {e}")


def provision_container_software(container_name_docker, template):
    """Installs software in an existing, running container based on template."""
    logger.info(f"Starting software provisioning for {container_name_docker} with template {template}.")
    
    # Initial apt update
    update_result = _execute_in_container(container_name_docker, ['apt-get', 'update', '-y'], tty_for_exec=False)
    if update_result.exit_code != 0:
        logger.error(f"apt-get update failed in {container_name_docker}: {update_result.stderr}")
        raise Exception(f"Provisioning failed: apt-get update error in {container_name_docker}")

    base_packages = ['curl', 'wget', 'cron', 'procps', 'net-tools'] # net-tools for ifconfig if needed for IP
    
    if template == 'nginx':
        # Determine PHP version for nginx template, default or make it a param
        php_version_nginx = "7.4" # Example, should ideally come from template config
        template_packages = [
            'nginx', 
            f'php{php_version_nginx}-fpm', 
            f'php{php_version_nginx}-mysql', # Common PHP extensions
            f'php{php_version_nginx}-curl',
            f'php{php_version_nginx}-gd',
            f'php{php_version_nginx}-mbstring',
            f'php{php_version_nginx}-xml',
            'mysql-client'
        ]
    elif template == 'apache':
        php_version_apache = "7.4" # Example
        template_packages = [
            'apache2', 
            f'libapache2-mod-php{php_version_apache}', 
            f'php{php_version_apache}-mysql',
            'mysql-client'
        ]
    elif template == 'mixed': # Example for a mixed template
        php_version_mixed = "7.4"
        template_packages = [
            'nginx',
            f'php{php_version_mixed}-fpm',
            f'php{php_version_mixed}-mysql',
            'mariadb-server', # Example: MariaDB in mixed
            'redis-server',   # Example: Redis in mixed
            'mysql-client'
        ]
    else:
        template_packages = []
        logger.warning(f"Unknown template '{template}' for software provisioning in {container_name_docker}. Only base packages will be installed.")

    all_packages_to_install = base_packages + template_packages
    if all_packages_to_install:
        cmd = ['apt-get', 'install', '-y'] + all_packages_to_install
        install_result = _execute_in_container(container_name_docker, cmd, tty_for_exec=False)
        if install_result.exit_code != 0:
            logger.error(f"apt-get install failed for packages {' '.join(all_packages_to_install)} in {container_name_docker}: {install_result.stderr} {install_result.stdout}")
            raise Exception(f"Provisioning failed: apt-get install error in {container_name_docker}")
    
    logger.info(f"Core software provisioning completed for {container_name_docker}.")

    # Start essential services
    # For PHP-FPM, the service name includes the version.
    if template == 'nginx':
        start_service(container_name_docker, "nginx")
        if php_version_nginx: start_service(container_name_docker, f"php{php_version_nginx}-fpm")
    elif template == 'apache':
        start_service(container_name_docker, "apache2")
    elif template == 'mixed':
        start_service(container_name_docker, "nginx")
        if php_version_mixed: start_service(container_name_docker, f"php{php_version_mixed}-fpm")
        start_service(container_name_docker, "mariadb") # or 'mysql' if mysql-server was installed
        start_service(container_name_docker, "redis-server")

    start_service(container_name_docker, "cron")
    logger.info(f"Essential services started for {container_name_docker}.")


# ... (rest of the functions: start_container, stop_container, etc. remain largely the same)
# Ensure they use container_id (which is container_name_docker) correctly.

def start_container(container_id): # container_id is Docker name/ID
    if client is None: raise Exception("Docker client not initialized")
    try:
        container = client.containers.get(container_id)
        container.start()
        logger.info(f"Container {container_id} started.")
    except NotFound:
        raise Exception(f"Container {container_id} not found.")
    except APIError as e:
        raise Exception(f"Failed to start container {container_id}: {e}")

def stop_container(container_id):
    if client is None: raise Exception("Docker client not initialized")
    try:
        container = client.containers.get(container_id)
        container.stop()
        logger.info(f"Container {container_id} stopped.")
    except NotFound:
        raise Exception(f"Container {container_id} not found.")
    except APIError as e:
        raise Exception(f"Failed to stop container {container_id}: {e}")

def restart_container(container_id):
    if client is None: raise Exception("Docker client not initialized")
    try:
        container = client.containers.get(container_id)
        container.restart()
        logger.info(f"Container {container_id} restarted.")
    except NotFound:
        raise Exception(f"Container {container_id} not found.")
    except APIError as e:
        raise Exception(f"Failed to restart container {container_id}: {e}")

def delete_container(container_id):
    if client is None: raise Exception("Docker client not initialized")
    try:
        container = client.containers.get(container_id)
        container.remove(force=True) 
        logger.info(f"Container {container_id} deleted.")
    except NotFound:
        logger.info(f"Container {container_id} not found, presumed deleted.")
    except APIError as e:
        raise Exception(f"Failed to delete container {container_id}: {e}")

def start_service(container_id, service_name):
    logger.info(f"Attempting to start service {service_name} in container {container_id}")
    result_service = _execute_in_container(container_id, ['service', service_name, 'start'], ignore_failure=True)
    if result_service.exit_code != 0:
        logger.warning(f"'service {service_name} start' failed (code {result_service.exit_code}): {result_service.stderr}. Trying systemctl.")
        result_systemctl = _execute_in_container(container_id, ['systemctl', 'start', service_name], ignore_failure=True)
        if result_systemctl.exit_code != 0:
             logger.error(f"Both service and systemctl start {service_name} failed in {container_id}. systemctl_err: {result_systemctl.stderr}")


def stop_service(container_id, service_name):
    logger.info(f"Attempting to stop service {service_name} in container {container_id}")
    result_service = _execute_in_container(container_id, ['service', service_name, 'stop'], ignore_failure=True)
    if result_service.exit_code != 0:
        logger.warning(f"'service {service_name} stop' failed (code {result_service.exit_code}): {result_service.stderr}. Trying systemctl.")
        result_systemctl = _execute_in_container(container_id, ['systemctl', 'stop', service_name], ignore_failure=True)
        if result_systemctl.exit_code != 0:
             logger.error(f"Both service and systemctl stop {service_name} failed in {container_id}. systemctl_err: {result_systemctl.stderr}")


def restart_service(container_id, service_name):
    logger.info(f"Attempting to restart service {service_name} in container {container_id}")
    result_service = _execute_in_container(container_id, ['service', service_name, 'restart'], ignore_failure=True)
    if result_service.exit_code != 0:
        logger.warning(f"'service {service_name} restart' failed (code {result_service.exit_code}): {result_service.stderr}. Trying systemctl.")
        result_systemctl = _execute_in_container(container_id, ['systemctl', 'restart', service_name], ignore_failure=True)
        if result_systemctl.exit_code != 0:
             logger.error(f"Both service and systemctl restart {service_name} failed in {container_id}. systemctl_err: {result_systemctl.stderr}")


def list_files(container_id, path):
    # Ensure path is absolute for 'ls' robustness, or handle relative paths carefully
    if not path.startswith('/'):
        path = '/' + path # Simple prefix, might need context (e.g. user's home) for more complex relative paths
    
    result = _execute_in_container(container_id, ['ls', '-la', '--full-time', path.rstrip('/') + '/']) # Add trailing slash for dirs
    if result.exit_code != 0:
        if "No such file or directory" in result.stderr:
            # Check if it's a file, not a directory, then list its parent
            check_file_result = _execute_in_container(container_id, ['test', '-f', path], ignore_failure=True)
            if check_file_result.exit_code == 0: # It's a file
                 parent_dir_list_result = _execute_in_container(container_id, ['ls', '-la', '--full-time', os.path.dirname(path).rstrip('/') + '/'])
                 if parent_dir_list_result.exit_code == 0:
                      result = parent_dir_list_result # Use parent dir listing
                 else: # Fallback if parent also fails
                      logger.warning(f"Path {path} and its parent not found for ls in {container_id}")
                      return[]
            else:
                logger.warning(f"Path not found for ls: {container_id}:{path}")
                return [] # Return empty if path doesn't exist
        else: # Other ls error
            raise Exception(f"Failed to list files in {container_id}:{path}: {result.stderr}")


    files = []
    lines = result.stdout.strip().split('\n')
    if not lines: return files

    for line in lines:
        if line.startswith('total') or not line.strip():
            continue
        parts = line.split(maxsplit=8) 
        if len(parts) < 9: 
            logger.warning(f"Could not parse ls output line: '{line}' in {container_id}:{path}")
            continue

        permissions = parts[0]
        size = parts[4]
        date_str = f"{parts[5]} {parts[6].split('.')[0]}" 
        name = parts[8]

        is_dir = permissions.startswith('d')
        
        if ' -> ' in name: # Handle symlinks
            name = name.split(' -> ')[0]
        
        # For '..' and '.', the path needs careful construction
        if name == '.':
            item_path = path
        elif name == '..':
            item_path = os.path.dirname(path.rstrip('/')) or '/'
        else:
            item_path = os.path.join(path.rstrip('/'), name)


        files.append({
            'name': name,
            'is_dir': is_dir,
            'size': size, 
            'date': date_str,
            'permissions': permissions,
            'path': item_path 
        })
    return files

def read_file(container_id, file_path):
    result = _execute_in_container(container_id, ['cat', file_path])
    if result.exit_code != 0:
        raise Exception(f"Failed to read file {container_id}:{file_path}: {result.stderr}")
    return result.stdout

def write_file(container_id, container_path, content_string):
    if client is None: raise Exception("Docker client not initialized")
    
    try:
        container_obj = client.containers.get(container_id)
        
        parent_dir = os.path.dirname(container_path)
        # Ensure parent_dir is not empty, '/', or '.' before trying to mkdir
        if parent_dir and parent_dir not in ['/', '.']:
            _execute_in_container(container_id, ['mkdir', '-p', parent_dir], ignore_failure=True)

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            file_bytes = content_string.encode('utf-8')
            arcname = os.path.basename(container_path) # Name of the file inside the tar
            tarinfo = tarfile.TarInfo(name=arcname)
            tarinfo.size = len(file_bytes)
            tarinfo.mtime = int(datetime.now().timestamp())
            tar.addfile(tarinfo, io.BytesIO(file_bytes))
        tar_stream.seek(0)
        
        # put_archive extracts relative to 'path'.
        # If container_path is /a/b/file.txt, parent_dir is /a/b.
        # We want to put the tar containing 'file.txt' into '/a/b/'.
        container_obj.put_archive(path=parent_dir if (parent_dir and parent_dir != '.') else '/', data=tar_stream)
        logger.info(f"File written to {container_id}:{container_path}")
    except NotFound:
        raise Exception(f"Container {container_id} not found for writing file.")
    except APIError as e:
        raise Exception(f"Failed to write file to {container_id}:{container_path}: {e}")


def create_directory(container_id, dir_path):
    result = _execute_in_container(container_id, ['mkdir', '-p', dir_path])
    if result.exit_code != 0:
        raise Exception(f"Failed to create directory {container_id}:{dir_path}: {result.stderr}")

def upload_file(container_id, local_path, container_path):
    if client is None: raise Exception("Docker client not initialized")
    try:
        container_obj = client.containers.get(container_id)

        parent_dir = os.path.dirname(container_path)
        if parent_dir and parent_dir not in ['/', '.']:
             _execute_in_container(container_id, ['mkdir', '-p', parent_dir], ignore_failure=True)

        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            arcname = os.path.basename(container_path)
            tar.add(local_path, arcname=arcname)
        tar_stream.seek(0)
        
        container_obj.put_archive(path=parent_dir if (parent_dir and parent_dir != '.') else '/', data=tar_stream)
        logger.info(f"File {local_path} uploaded to {container_id}:{container_path}")
    except NotFound:
        raise Exception(f"Container {container_id} not found for uploading file.")
    except FileNotFoundError:
        raise Exception(f"Local file {local_path} not found.")
    except APIError as e:
        raise Exception(f"Failed to upload file to {container_id}:{container_path}: {e}")


def download_file(container_id, container_path):
    if client is None: raise Exception("Docker client not initialized")
    try:
        container_obj = client.containers.get(container_id)
        
        stat_result = _execute_in_container(container_id, ['stat', '-c', '%F', container_path])
        if stat_result.exit_code != 0 or not stat_result.stdout.strip():
             raise Exception(f"Path {container_path} not found or inaccessible in {container_id}: {stat_result.stderr}")
        
        is_dir_stat = "directory" in stat_result.stdout.lower()
        if is_dir_stat:
             raise Exception(f"Path {container_path} is a directory. Direct download of directories not yet supported this way, expecting a file.")


        bits, stat_info = container_obj.get_archive(container_path) 

        temp_file_download = tempfile.NamedTemporaryFile(delete=False)
        
        with tarfile.open(fileobj=io.BytesIO(b"".join(bits)), mode='r') as tar:
            member_to_extract = None
            # The name of the file inside the tar could be just its basename, or '.' if it's the only item.
            target_filename_in_tar = os.path.basename(container_path) 
            
            members = tar.getmembers()
            if not members:
                temp_file_download.close()
                os.unlink(temp_file_download.name)
                raise Exception(f"Tar archive from {container_path} is empty.")

            # Try to find the exact basename or '.'
            for member in members:
                if member.name == target_filename_in_tar or member.name == '.':
                    member_to_extract = member
                    break
            
            if not member_to_extract and len(members) == 1 and members[0].isfile(): # Only one file, assume it's it
                member_to_extract = members[0]
            elif not member_to_extract: # Fallback to first file member if specific not found
                 for m in members:
                     if m.isfile():
                         member_to_extract = m
                         break # Take the first actual file
            
            if member_to_extract and member_to_extract.isfile():
                extracted_file_content = tar.extractfile(member_to_extract)
                if extracted_file_content:
                    temp_file_download.write(extracted_file_content.read())
                else: # Should not happen if extractfile returns non-None
                    temp_file_download.close()
                    os.unlink(temp_file_download.name)
                    raise Exception(f"Could not extract file content for {member_to_extract.name} from archive.")
            else:
                temp_file_download.close()
                os.unlink(temp_file_download.name)
                member_names = [m.name for m in members] if members else "none"
                raise Exception(f"Could not find file '{target_filename_in_tar}' or a suitable file in archive from {container_path}. Members found: {member_names}")

        temp_file_download.close()
        logger.info(f"File {container_path} from {container_id} downloaded to {temp_file_download.name}")
        return temp_file_download.name
    except NotFound:
        raise Exception(f"Container {container_id} or path {container_path} not found for download.")
    except APIError as e:
        raise Exception(f"Failed to download file from {container_id}:{container_path}: {e}")
    except Exception as e: # Catch other unexpected errors during tar processing
        if 'temp_file_download' in locals() and temp_file_download and not temp_file_download.closed:
            temp_file_download.close()
            if os.path.exists(temp_file_download.name):
                 os.unlink(temp_file_download.name)
        logger.error(f"Generic error downloading file: {e}")
        raise


def delete_file(container_id, file_path):
    result = _execute_in_container(container_id, ['rm', '-rf', file_path])
    if result.exit_code != 0:
        raise Exception(f"Failed to delete file {container_id}:{file_path}: {result.stderr}")

def download_url_to_container(container_id, url, destination_dir):
    if client is None: raise Exception("Docker client not initialized")

    filename = os.path.basename(urlparse(url).path) or 'downloaded_file'
    safe_filename = "".join(c if c.isalnum() or c in ['.', '_', '-'] else '_' for c in filename)
    destination_path = os.path.join(destination_dir, safe_filename)
    
    create_directory(container_id, destination_dir)

    result = _execute_in_container(container_id, ['curl', '-fSL', '-o', destination_path, url]) 
    if result.exit_code != 0:
        logger.warning(f"curl failed for {url} in {container_id} (code: {result.exit_code}), trying wget. Error: {result.stderr}")
        result = _execute_in_container(container_id, ['wget', '-O', destination_path, url])
        if result.exit_code != 0:
            raise Exception(f"Failed to download URL {url} to {container_id}:{destination_path}: {result.stderr}")
    
    logger.info(f"URL {url} downloaded to {container_id}:{destination_path}")
    return safe_filename

def create_cronjob(container_id, name, command, schedule):
    cron_content = f"{schedule} {command} # SBPanel Job: {name}\n"
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
    cron_file_path = f"/etc/cron.d/{safe_name}"
    
    write_file(container_id, cron_file_path, cron_content)
    _execute_in_container(container_id, ['chmod', '0644', cron_file_path]) # More specific chmod
    _execute_in_container(container_id, ['chown', 'root:root', cron_file_path]) 
    restart_service(container_id, 'cron')

def toggle_cronjob(container_id, name, active):
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
    cron_file_path = f"/etc/cron.d/{safe_name}"
    
    try:
        content = read_file(container_id, cron_file_path)
        lines = content.splitlines()
        new_lines = []
        modified = False
        
        job_found_and_toggled = False
        for line in lines:
            stripped_line = line.strip()
            # Check if this line is the job we want to toggle (based on our comment)
            is_our_job_line = f"SBPanel Job: {name}" in line

            if is_our_job_line:
                if active: # We want to activate it
                    if stripped_line.startswith("#"):
                        new_lines.append(stripped_line[1:]) # Remove initial '#'
                        modified = True
                    else:
                        new_lines.append(line) # Already active
                else: # We want to disable it
                    if not stripped_line.startswith("#"):
                        new_lines.append(f"#{line}")
                        modified = True
                    else:
                        new_lines.append(line) # Already disabled
                job_found_and_toggled = True
            else:
                new_lines.append(line)
        
        if not job_found_and_toggled and active:
            # This case means the cron file exists but our job comment isn't there.
            # This can happen if create_cronjob failed to add the comment or it was manually edited.
            # Or, if the file is for a different job.
            logger.warning(f"Cron job '{name}' marker not found in {cron_file_path} for activation. File content might be unexpected.")
            # To be safe, don't modify if we can't find our marker.
            # If the file is empty or doesn't contain our job, and we want to activate,
            # it might imply the cron job was deleted and needs re-creation.
            # For toggle, we assume the job entry exists.

        elif modified:
            write_file(container_id, cron_file_path, "\n".join(new_lines) + "\n")
            restart_service(container_id, 'cron')
        else:
            logger.info(f"Cron job '{name}' in {container_id} state already as requested (active={active}) or no specific line found to toggle.")

    except Exception as e: # Catches if read_file fails (e.g. file not found)
        if active: 
            logger.error(f"Could not toggle cron job {name} for container {container_id} (target_active={active}): {e}. File might not exist or be readable.")
        else: 
            logger.info(f"Cron job file for {name} in {container_id} not found or error reading, presumed disabled. (target_active={active})")


def delete_cronjob(container_id, name):
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in name)
    cron_file_path = f"/etc/cron.d/{safe_name}"

    _execute_in_container(container_id, ['rm', '-f', cron_file_path], ignore_failure=True)
    restart_service(container_id, 'cron')