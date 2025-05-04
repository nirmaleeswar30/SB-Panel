import logging
import random
import string

logger = logging.getLogger(__name__)

def generate_password(length=16):
    """Generate a random password"""
    characters = string.ascii_letters + string.digits + '!@#$%^&*()'
    return ''.join(random.choice(characters) for _ in range(length))

def create_database(container_id, name, db_type, db_user, db_password, remote_access):
    """
    Create a database on a container
    
    Args:
        container_id: Container ID
        name: Database name
        db_type: Database type (mysql, mariadb)
        db_user: Database user
        db_password: Database password
        remote_access: Whether to enable remote access
    """
    from utils.container import container
    container = container.get(container_id)
    
    # Install database server if not already installed
    if db_type == 'mysql':
        container.execute(['apt-get', 'update'])
        container.execute(['apt-get', 'install', '-y', 'mysql-server'])
        service_name = 'mysql'
    elif db_type == 'mariadb':
        container.execute(['apt-get', 'update'])
        container.execute(['apt-get', 'install', '-y', 'mariadb-server'])
        service_name = 'mariadb'
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    # Ensure database server is running
    from utils.container import start_service
    start_service(container_id, service_name)
    
    # Create database and user
    create_db_command = f"CREATE DATABASE IF NOT EXISTS `{name}`;"
    create_user_command = f"CREATE USER '{db_user}'@'localhost' IDENTIFIED BY '{db_password}';"
    grant_command = f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{db_user}'@'localhost';"
    
    # Add remote access if enabled
    if remote_access:
        create_remote_user_command = f"CREATE USER '{db_user}'@'%' IDENTIFIED BY '{db_password}';"
        grant_remote_command = f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{db_user}'@'%';"
    else:
        create_remote_user_command = ""
        grant_remote_command = ""
    
    flush_command = "FLUSH PRIVILEGES;"
    
    # Execute SQL commands
    sql_commands = f"{create_db_command} {create_user_command} {grant_command} {create_remote_user_command} {grant_remote_command} {flush_command}"
    container.execute(['mysql', '-e', sql_commands])
    
    # Configure remote access if enabled
    if remote_access:
        configure_remote_access(container_id, db_type)

def delete_database(container_id, name, db_type, db_user):
    """
    Delete a database from a container
    
    Args:
        container_id: Container ID
        name: Database name
        db_type: Database type (mysql, mariadb)
        db_user: Database user
    """
    from utils.container import container
    container = container.get(container_id)
    
    # Determine service name
    if db_type == 'mysql':
        service_name = 'mysql'
    elif db_type == 'mariadb':
        service_name = 'mariadb'
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    # Ensure database server is running
    from utils.container import start_service
    start_service(container_id, service_name)
    
    # Delete database and user
    drop_db_command = f"DROP DATABASE IF EXISTS `{name}`;"
    drop_user_command = f"DROP USER IF EXISTS '{db_user}'@'localhost'; DROP USER IF EXISTS '{db_user}'@'%';"
    flush_command = "FLUSH PRIVILEGES;"
    
    # Execute SQL commands
    sql_commands = f"{drop_db_command} {drop_user_command} {flush_command}"
    container.execute(['mysql', '-e', sql_commands])

def configure_remote_access(container_id, db_type):
    """
    Configure database server for remote access
    
    Args:
        container_id: Container ID
        db_type: Database type (mysql, mariadb)
    """
    from utils.container import container, write_file
    container = container.get(container_id)
    
    # Determine config file location
    if db_type == 'mysql':
        config_file = '/etc/mysql/mysql.conf.d/mysqld.cnf'
        service_name = 'mysql'
    elif db_type == 'mariadb':
        config_file = '/etc/mysql/mariadb.conf.d/50-server.cnf'
        service_name = 'mariadb'
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
    
    # Read current config
    from utils.container import read_file
    config = read_file(container_id, config_file)
    
    # Replace bind-address from 127.0.0.1 to 0.0.0.0
    updated_config = config.replace('bind-address            = 127.0.0.1', 'bind-address            = 0.0.0.0')
    
    # Write updated config
    write_file(container_id, config_file, updated_config)
    
    # Restart database server
    from utils.container import restart_service
    restart_service(container_id, service_name)
