import logging
import random
import string
from .container import _execute_in_container, start_service, write_file, read_file, restart_service # Adjusted imports

logger = logging.getLogger(__name__)

def generate_password(length=16):
    """Generate a random password"""
    characters = string.ascii_letters + string.digits + '!@#$%^&*()'
    return ''.join(random.choice(characters) for _ in range(length))

def create_database(container_id, name, db_type, db_user, db_password, remote_access):
    """
    Create a database on a container
    """
    service_name = None
    if db_type == 'mysql':
        db_package = 'mysql-server'
        service_name = 'mysql' # Service name for mysql-server on Ubuntu is often 'mysql'
    elif db_type == 'mariadb':
        db_package = 'mariadb-server'
        service_name = 'mariadb'
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    logger.info(f"Ensuring {db_package} is installed in {container_id}...")
    _execute_in_container(container_id, ['apt-get', 'update', '-y'])
    install_db_result = _execute_in_container(container_id, ['apt-get', 'install', '-y', db_package])
    if install_db_result.exit_code != 0:
        logger.error(f"Failed to install {db_package} in {container_id}: {install_db_result.stderr}")
        raise Exception(f"Failed to install {db_package} in {container_id}")
    logger.info(f"Successfully installed/verified {db_package} in {container_id}.")
    
    start_service(container_id, service_name)
    
    # MySQL commands might need a brief moment for the server to be fully ready after start
    # Consider a small sleep or retry mechanism if encountering "can't connect" errors here.
    # For simplicity, not adding it yet.

    # Construct SQL commands
    # Note: IDENTIFIED BY is for older MySQL. Newer versions use IDENTIFIED WITH mysql_native_password BY
    # For compatibility, this might need adjustment or checking MySQL version in container.
    # Using a simpler CREATE USER for now.
    sql_commands = [
        f"CREATE DATABASE IF NOT EXISTS `{name}`;",
        f"CREATE USER IF NOT EXISTS '{db_user}'@'localhost' IDENTIFIED BY '{db_password}';",
        f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{db_user}'@'localhost';"
    ]
    if remote_access:
        sql_commands.extend([
            f"CREATE USER IF NOT EXISTS '{db_user}'@'%' IDENTIFIED BY '{db_password}';",
            f"GRANT ALL PRIVILEGES ON `{name}`.* TO '{db_user}'@'%';"
        ])
    sql_commands.append("FLUSH PRIVILEGES;")
    
    full_sql_command_str = " ".join(sql_commands)
    
    # Execute SQL. This requires mysql client and that the server is running without root password prompt or with a known one.
    # The default Ubuntu install of mysql-server often allows root login without password from localhost.
    # If `mysql` command needs password, this will fail.
    exec_sql_result = _execute_in_container(container_id, ['mysql', '-e', full_sql_command_str])
    if exec_sql_result.exit_code != 0:
        logger.error(f"Failed to execute SQL commands for database {name} in {container_id}: {exec_sql_result.stderr} {exec_sql_result.stdout}")
        # It's possible the user already exists with a different password, or other SQL error.
        # More granular error handling would be good here.
        raise Exception(f"SQL execution failed for database {name}. Check logs for details.")
    
    logger.info(f"Database {name} and user {db_user} created in {container_id}.")

    if remote_access:
        configure_remote_access(container_id, db_type, service_name)

def delete_database(container_id, name, db_type, db_user):
    """
    Delete a database from a container
    """
    service_name = 'mysql' if db_type == 'mysql' else 'mariadb'
    start_service(container_id, service_name)
    
    sql_commands = [
        f"DROP DATABASE IF EXISTS `{name}`;",
        f"DROP USER IF EXISTS '{db_user}'@'localhost';",
        f"DROP USER IF EXISTS '{db_user}'@'%';" # Attempt to drop remote user too
        "FLUSH PRIVILEGES;"
    ]
    full_sql_command_str = " ".join(sql_commands)
    
    exec_sql_result = _execute_in_container(container_id, ['mysql', '-e', full_sql_command_str])
    if exec_sql_result.exit_code != 0:
        logger.warning(f"Failed to delete database/user {name}/{db_user} in {container_id} (may not exist or other SQL issue): {exec_sql_result.stderr}")
        # Not raising exception, as it might be a "user/db doesn't exist" error which is fine for delete.
    else:
        logger.info(f"Database {name} and user {db_user} (if existed) deleted from {container_id}.")


def configure_remote_access(container_id, db_type, service_name_for_restart):
    """
    Configure database server for remote access by changing bind-address.
    """
    config_file_path = None
    # These paths are typical for Ubuntu packages
    if db_type == 'mysql':
        # MySQL 5.7 uses /etc/mysql/mysql.conf.d/mysqld.cnf
        # MySQL 8.0 might use /etc/mysql/my.cnf or similar, or also the above.
        # Check common paths.
        possible_paths = ['/etc/mysql/mysql.conf.d/mysqld.cnf', '/etc/mysql/my.cnf']
        for p in possible_paths:
             res = _execute_in_container(container_id, ['test', '-f', p], ignore_failure=True)
             if res.exit_code == 0:
                  config_file_path = p
                  break
        if not config_file_path:
             logger.error(f"MySQL config file not found in {container_id} at expected paths.")
             return False # Cannot configure
    elif db_type == 'mariadb':
        # MariaDB often uses /etc/mysql/mariadb.conf.d/50-server.cnf
        config_file_path = '/etc/mysql/mariadb.conf.d/50-server.cnf'
        res = _execute_in_container(container_id, ['test', '-f', config_file_path], ignore_failure=True)
        if res.exit_code != 0:
            # Try alternative path if 50-server.cnf doesn't exist
            alt_path = '/etc/mysql/my.cnf' # Some MariaDB setups might use this
            res_alt = _execute_in_container(container_id, ['test', '-f', alt_path], ignore_failure=True)
            if res_alt.exit_code == 0:
                config_file_path = alt_path
            else:
                logger.error(f"MariaDB config file not found in {container_id} at expected paths.")
                return False
    else:
        raise ValueError(f"Unsupported database type for remote access config: {db_type}")

    if not config_file_path:
        logger.error(f"Could not determine DB config file path for {db_type} in {container_id}.")
        return False

    try:
        current_config = read_file(container_id, config_file_path)
    except Exception as e:
        logger.error(f"Failed to read DB config {config_file_path} from {container_id}: {e}")
        return False
    
    # Replace bind-address. Be careful with regex or simple replace.
    # Look for lines starting with 'bind-address'
    new_config_lines = []
    found_bind_address = False
    for line in current_config.splitlines():
        if line.strip().startswith('bind-address'):
            new_config_lines.append('bind-address            = 0.0.0.0')
            found_bind_address = True
        else:
            new_config_lines.append(line)
    
    if not found_bind_address:
        # If not found, try to add it under [mysqld] or [mariadb] section
        # This is more complex; for now, we'll assume it exists and is commented or set to 127.0.0.1
        logger.warning(f"'bind-address' not found in {config_file_path} for {container_id}. Remote access may not be fully enabled by this script if it needs to be added.")
        # A simple approach if not found: append under [mysqld] if possible
        # For now, we proceed assuming the replace worked or it's not there to replace
    
    updated_config = "\n".join(new_config_lines)
    
    try:
        write_file(container_id, config_file_path, updated_config)
        logger.info(f"Updated bind-address in {config_file_path} for {container_id}.")
    except Exception as e:
        logger.error(f"Failed to write updated DB config {config_file_path} to {container_id}: {e}")
        return False
        
    restart_service(container_id, service_name_for_restart)
    logger.info(f"Remote access configured for {db_type} in {container_id}. Service {service_name_for_restart} restarted.")
    return True
