import os
import logging
import tempfile
import subprocess
import urllib.request
import uuid
from urllib.parse import urlparse
import pylxd
from datetime import datetime

logger = logging.getLogger(__name__)

# Development mode - mock LXD client
# In a production environment, this would use the real LXD client
class MockContainer:
    def __init__(self, name, config=None):
        self.name = name
        self.config = config or {}
        self.status = 'Stopped'
        self.container_id = str(uuid.uuid4())
        self._ip_address = f"192.168.0.{uuid.uuid4().int % 255}"
        
    def start(self, wait=False):
        self.status = 'Running'
        return True
        
    def stop(self, wait=False):
        self.status = 'Stopped'
        return True
        
    def restart(self, wait=False):
        self.status = 'Running'
        return True
        
    def delete(self, wait=False):
        return True
        
    def execute(self, command, ignore_failure=False):
        class ExecResult:
            def __init__(self):
                self.exit_code = 0
                self.stdout = "Mock execution output"
                self.stderr = ""
        
        # Simulate executing commands
        if command[0] == 'systemctl':
            if command[1] == 'is-active':
                if command[2] in ['nginx', 'apache2']:
                    return ExecResult()
        
        return ExecResult()
    
    class FileManager:
        def exists(self, path):
            return False
            
        def get(self, path):
            return b"Mock file content"
            
        def put(self, path, content):
            return True
    
    # Set up file manager
    files = FileManager()

class MockLXDClient:
    def __init__(self):
        self._containers = {}
    
    def containers(self):
        class ContainerList:
            def __init__(self, container_dict):
                self._containers = container_dict
                
            def all(self):
                return list(self._containers.values())
                
            def get(self, container_id):
                if container_id in self._containers:
                    return self._containers[container_id]
                
                # Create mock container if it doesn't exist
                container = MockContainer(container_id)
                self._containers[container_id] = container
                return container
            
            def create(self, config, wait=False):
                container = MockContainer(config['name'], config)
                self._containers[config['name']] = container
                return container
                
        return ContainerList(self._containers)

# Mock client for development
client = MockLXDClient()

logger.warning("Using mock LXD client for development purposes")

def create_container(name, template, user_id, cpu, memory, disk):
    """
    Create a new LXD container
    
    Args:
        name: Container name
        template: Template name (nginx, apache, etc.)
        user_id: User ID to associate with the container
        cpu: Number of CPU cores to allocate
        memory: Memory in MB to allocate
        disk: Disk space in MB to allocate
        
    Returns:
        Container ID
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    # The actual container name will include the user ID for uniqueness
    container_name = f"user{user_id}-{name}"
    
    # Check if the container already exists
    if container_name in [c.name for c in client.containers.all()]:
        raise Exception(f"Container {name} already exists")
    
    # Create container from image based on the template
    if template == 'nginx':
        source = {'type': 'image', 'alias': 'ubuntu/20.04'}
    elif template == 'apache':
        source = {'type': 'image', 'alias': 'ubuntu/20.04'}
    else:
        source = {'type': 'image', 'alias': 'ubuntu/20.04'}
    
    # Configure resource limits
    config = {
        'limits.cpu': str(cpu),
        'limits.memory': f"{memory}MB",
        'limits.disk.size': f"{disk}MB",
        # Network configuration
        'security.nesting': 'false',
        'security.privileged': 'false',
    }
    
    # Create the container
    container = client.containers.create({
        'name': container_name,
        'source': source,
        'config': config
    }, wait=True)
    
    # Start the container
    container.start(wait=True)
    
    # Install necessary software based on template
    if template == 'nginx':
        container.execute(['apt-get', 'update'])
        container.execute(['apt-get', 'install', '-y', 'nginx', 'php-fpm', 'mysql-client'])
    elif template == 'apache':
        container.execute(['apt-get', 'update'])
        container.execute(['apt-get', 'install', '-y', 'apache2', 'php', 'libapache2-mod-php', 'mysql-client'])
    
    return container_name

def start_container(container_id):
    """Start a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.start(wait=True)

def stop_container(container_id):
    """Stop a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.stop(wait=True)

def restart_container(container_id):
    """Restart a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.restart(wait=True)

def delete_container(container_id):
    """Delete a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Stop the container if it's running
    if container.status == 'Running':
        container.stop(wait=True)
    
    # Delete the container
    container.delete(wait=True)

def start_service(container_id, service_name):
    """Start a service in a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.execute(['systemctl', 'start', service_name])

def stop_service(container_id, service_name):
    """Stop a service in a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.execute(['systemctl', 'stop', service_name])

def restart_service(container_id, service_name):
    """Restart a service in a container"""
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    container.execute(['systemctl', 'restart', service_name])

def list_files(container_id, path):
    """
    List files in a container directory
    
    Args:
        container_id: Container ID
        path: Directory path
        
    Returns:
        List of files with metadata
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Execute ls -la command in the container
    result = container.execute(['ls', '-la', path])
    
    if result.exit_code != 0:
        raise Exception(f"Failed to list files: {result.stderr}")
    
    # Parse the output to get file list
    files = []
    for line in result.stdout.strip().split('\n'):
        if line.startswith('total') or not line.strip():
            continue
        
        parts = line.split()
        if len(parts) < 8:
            continue
        
        permissions = parts[0]
        size = parts[4]
        date = f"{parts[5]} {parts[6]}"
        name = ' '.join(parts[7:])
        
        # Determine if it's a directory
        is_dir = permissions.startswith('d')
        
        files.append({
            'name': name,
            'is_dir': is_dir,
            'size': size,
            'date': date,
            'permissions': permissions,
            'path': os.path.join(path, name)
        })
    
    return files

def read_file(container_id, file_path):
    """
    Read a file from a container
    
    Args:
        container_id: Container ID
        file_path: File path
        
    Returns:
        File content
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Execute cat command in the container
    result = container.execute(['cat', file_path])
    
    if result.exit_code != 0:
        raise Exception(f"Failed to read file: {result.stderr}")
    
    return result.stdout

def write_file(container_id, file_path, content):
    """
    Write content to a file in a container
    
    Args:
        container_id: Container ID
        file_path: File path
        content: File content
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Create a temporary file with the content
    with tempfile.NamedTemporaryFile(delete=False, mode='w') as temp:
        temp.write(content)
        temp_path = temp.name
    
    # Push the file to the container
    container.files.put(file_path, open(temp_path, 'rb').read())
    
    # Remove temporary file
    os.unlink(temp_path)

def create_directory(container_id, dir_path):
    """
    Create a directory in a container
    
    Args:
        container_id: Container ID
        dir_path: Directory path
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Execute mkdir command in the container
    result = container.execute(['mkdir', '-p', dir_path])
    
    if result.exit_code != 0:
        raise Exception(f"Failed to create directory: {result.stderr}")

def upload_file(container_id, local_path, container_path):
    """
    Upload a file to a container
    
    Args:
        container_id: Container ID
        local_path: Local file path
        container_path: Container file path
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Push the file to the container
    container.files.put(container_path, open(local_path, 'rb').read())

def download_file(container_id, file_path):
    """
    Download a file from a container
    
    Args:
        container_id: Container ID
        file_path: File path
        
    Returns:
        Temporary file path
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Pull the file from the container
    content = container.files.get(file_path)
    
    # Create a temporary file with the content
    temp = tempfile.NamedTemporaryFile(delete=False)
    temp.write(content)
    temp.close()
    
    return temp.name

def delete_file(container_id, file_path):
    """
    Delete a file in a container
    
    Args:
        container_id: Container ID
        file_path: File path
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Execute rm command in the container
    result = container.execute(['rm', '-rf', file_path])
    
    if result.exit_code != 0:
        raise Exception(f"Failed to delete file: {result.stderr}")

def download_url_to_container(container_id, url, destination_dir):
    """
    Download a file from URL directly to a container
    
    Args:
        container_id: Container ID
        url: URL to download
        destination_dir: Destination directory
        
    Returns:
        Downloaded file name
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Extract filename from URL
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = 'downloaded_file'
    
    # Destination path
    destination_path = os.path.join(destination_dir, filename)
    
    # Execute wget command in the container
    result = container.execute(['wget', '-O', destination_path, url])
    
    if result.exit_code != 0:
        raise Exception(f"Failed to download URL: {result.stderr}")
    
    return filename

def create_cronjob(container_id, name, command, schedule):
    """
    Create a cron job in a container
    
    Args:
        container_id: Container ID
        name: Cron job name
        command: Command to execute
        schedule: Cron schedule expression
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    # Create a cron file
    cron_content = f"# {name}\n{schedule} {command}\n"
    cron_file = f"/etc/cron.d/{name}"
    
    # Write the cron file
    container.files.put(cron_file, cron_content.encode())
    
    # Set proper permissions
    container.execute(['chmod', '644', cron_file])
    
    # Restart cron service
    container.execute(['systemctl', 'restart', 'cron'])

def toggle_cronjob(container_id, name, active):
    """
    Enable or disable a cron job in a container
    
    Args:
        container_id: Container ID
        name: Cron job name
        active: Whether the cron job should be active
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    cron_file = f"/etc/cron.d/{name}"
    cron_disabled_file = f"{cron_file}.disabled"
    
    if active:
        # Enable cron job
        if container.files.exists(cron_disabled_file):
            # Read the disabled file
            content = container.files.get(cron_disabled_file)
            
            # Write to the active file
            container.files.put(cron_file, content)
            
            # Delete the disabled file
            container.execute(['rm', cron_disabled_file])
    else:
        # Disable cron job
        if container.files.exists(cron_file):
            # Read the active file
            content = container.files.get(cron_file)
            
            # Write to the disabled file
            container.files.put(cron_disabled_file, content)
            
            # Delete the active file
            container.execute(['rm', cron_file])
    
    # Restart cron service
    container.execute(['systemctl', 'restart', 'cron'])

def delete_cronjob(container_id, name):
    """
    Delete a cron job in a container
    
    Args:
        container_id: Container ID
        name: Cron job name
    """
    if client is None:
        raise Exception("LXD client not initialized")
    
    container = client.containers.get(container_id)
    
    cron_file = f"/etc/cron.d/{name}"
    cron_disabled_file = f"{cron_file}.disabled"
    
    # Delete both the active and disabled files
    if container.files.exists(cron_file):
        container.execute(['rm', cron_file])
    
    if container.files.exists(cron_disabled_file):
        container.execute(['rm', cron_disabled_file])
    
    # Restart cron service
    container.execute(['systemctl', 'restart', 'cron'])
