import logging
import os
import tempfile
from .container import _execute_in_container, write_file, create_directory, restart_service, start_service # Adjusted imports

logger = logging.getLogger(__name__)

def create_website_config(container_id, domain, server_type, php_version, document_root, ssl_enabled):
    """
    Create web server configuration for a website
    
    Args:
        container_id: Docker Container Name/ID
        domain: Domain name
        server_type: Web server type (nginx, apache)
        php_version: PHP version
        document_root: Document root path
        ssl_enabled: Whether SSL is enabled
    """
    # create_directory and write_file are already using the new _execute_in_container indirectly or directly
    create_directory(container_id, document_root)
    
    index_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Welcome to {domain}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        h1 {{ color: #2c3e50; }}
        .info {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
    </style>
</head>
<body>
    <h1>Welcome to {domain}</h1>
    <div class="info">
        <p>This website is hosted on SBPanel.</p>
        <p>To replace this page, upload your website files to the document root:</p>
        <code>{document_root}</code>
    </div>
</body>
</html>
"""
    index_path = os.path.join(document_root, 'index.html') # This is a host path representation
    # For write_file, container_path should be absolute from container's root
    container_index_path = index_path if index_path.startswith('/') else '/' + index_path
    write_file(container_id, container_index_path, index_content)
    
    if server_type == 'nginx':
        create_nginx_config(container_id, domain, document_root, php_version, ssl_enabled)
    elif server_type == 'apache':
        create_apache_config(container_id, domain, document_root, php_version, ssl_enabled)
    else:
        raise ValueError(f"Unsupported server type: {server_type}")
    
    restart_service(container_id, server_type)

def create_nginx_config(container_id, domain, document_root, php_version, ssl_enabled):
    """
    Create Nginx configuration for a website
    """
    # PHP Installation & FPM service name (e.g., php7.4-fpm)
    php_fpm_service_name = None
    if php_version:
        php_fpm_package = f'php{php_version}-fpm'
        php_fpm_service_name = f'php{php_version}-fpm' # Common naming convention
        
        logger.info(f"Ensuring PHP {php_version} and FPM are installed in {container_id}...")
        _execute_in_container(container_id, ['apt-get', 'update', '-y'])
        install_php_result = _execute_in_container(container_id, ['apt-get', 'install', '-y', php_fpm_package, f'php{php_version}-mysql']) # Add other common extensions if needed
        if install_php_result.exit_code != 0:
            logger.error(f"Failed to install {php_fpm_package} in {container_id}: {install_php_result.stderr}")
            # Decide if this is a critical failure or just a warning
        else:
            logger.info(f"Successfully installed/verified {php_fpm_package} in {container_id}.")
            start_service(container_id, php_fpm_service_name) # Use start_service which tries service then systemctl

    # Nginx configuration content
    config_parts = []
    config_parts.append(f"""server {{
    listen 80;
    server_name {domain} www.{domain}; # Also listen for www
    root {document_root};
    index index.html index.htm index.php;

    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
""")
    
    if php_version and php_fpm_service_name:
        # Use the actual PHP-FPM socket path. This can vary.
        # Common paths: /var/run/php/phpX.Y-fpm.sock or /run/php-fpm/www.sock (if using a generic pool)
        # Let's assume /var/run/php/phpX.Y-fpm.sock for now.
        php_socket_path = f"/var/run/php/php{php_version}-fpm.sock"
        config_parts.append(f"""
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:{php_socket_path};
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}
""")
    
    config_parts.append("""
    location ~ /\\.ht {
        deny all;
    }
}
""")
    
    if ssl_enabled:
        config_parts.append(f"""
server {{
    listen 443 ssl http2;
    server_name {domain} www.{domain};
    root {document_root};
    index index.html index.htm index.php;

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    # Include recommended SSL settings from certbot or Mozilla SSL Config Generator
    # For example: ssl_protocols TLSv1.2 TLSv1.3;
    # ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    # ssl_prefer_server_ciphers off;
    # Add HSTS header if desired
    # add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";

    access_log /var/log/nginx/{domain}.ssl.access.log;
    error_log /var/log/nginx/{domain}.ssl.error.log;

    location / {{
        try_files $uri $uri/ /index.php?$query_string;
    }}
""")
        if php_version and php_fpm_service_name:
            php_socket_path = f"/var/run/php/php{php_version}-fpm.sock"
            config_parts.append(f"""
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:{php_socket_path};
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}
""")
        config_parts.append("""
    location ~ /\\.ht {
        deny all;
    }
}

# Optional: Redirect HTTP to HTTPS
server {
    listen 80;
    server_name {domain} www.{domain};
    return 301 https://$host$request_uri;
}
""")
    
    full_config = "".join(config_parts)
    config_path_in_container = f"/etc/nginx/sites-available/{domain}"
    write_file(container_id, config_path_in_container, full_config)
    
    symlink_path_in_container = f"/etc/nginx/sites-enabled/{domain}"
    _execute_in_container(container_id, ['rm', '-f', symlink_path_in_container], ignore_failure=True)
    _execute_in_container(container_id, ['ln', '-s', config_path_in_container, symlink_path_in_container])

    # Test Nginx configuration
    test_nginx_result = _execute_in_container(container_id, ['nginx', '-t'])
    if test_nginx_result.exit_code != 0:
        logger.error(f"Nginx configuration test failed for {domain} in {container_id}: {test_nginx_result.stderr} {test_nginx_result.stdout}")
        # Optionally, remove the symlink or bad config to prevent Nginx from failing to restart
        _execute_in_container(container_id, ['rm', '-f', symlink_path_in_container], ignore_failure=True)
        raise Exception(f"Nginx configuration error for {domain}. Please check logs.")
    else:
        logger.info(f"Nginx configuration test for {domain} in {container_id} successful.")


def create_apache_config(container_id, domain, document_root, php_version, ssl_enabled):
    """
    Create Apache configuration for a website
    """
    # PHP and Apache module (mod_php or php-fpm via proxy_fcgi)
    if php_version:
        logger.info(f"Ensuring PHP {php_version} and Apache PHP module are set up in {container_id}...")
        _execute_in_container(container_id, ['apt-get', 'update', '-y'])
        # Example for mod_php. For FPM, setup is different (ProxyPassMatch).
        php_apache_package = f'libapache2-mod-php{php_version}' 
        install_php_result = _execute_in_container(container_id, ['apt-get', 'install', '-y', php_apache_package, f'php{php_version}-mysql'])
        if install_php_result.exit_code != 0:
            logger.error(f"Failed to install {php_apache_package} in {container_id}: {install_php_result.stderr}")
        else:
            _execute_in_container(container_id, [f'a2enmod', f'php{php_version}'], ignore_failure=True) # Enable the PHP module
            logger.info(f"PHP module for Apache (php{php_version}) ensured in {container_id}.")
            # If using PHP-FPM with Apache, you'd enable proxy_fcgi and set up FastCGIExternalServer / ProxyPassMatch

    config_parts = []
    config_parts.append(f"""<VirtualHost *:80>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot {document_root}

    <Directory {document_root}>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/{domain}.error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}.access.log combined
</VirtualHost>
""")
    
    if ssl_enabled:
        _execute_in_container(container_id, ['a2enmod', 'ssl'], ignore_failure=True)
        _execute_in_container(container_id, ['a2enmod', 'headers'], ignore_failure=True) # For HSTS if used

        config_parts.append(f"""
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerName {domain}
    ServerAlias www.{domain}
    DocumentRoot {document_root}

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/{domain}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{domain}/privkey.pem
    # SSLCertificateChainFile /etc/letsencrypt/live/{domain}/chain.pem # If needed

    # Include recommended SSL settings from certbot or Mozilla SSL Config Generator
    # SSLProtocol             all -SSLv3 -TLSv1 -TLSv1.1
    # SSLCipherSuite          ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384
    # SSLHonorCipherOrder     off
    # SSLSessionTickets       off
    # Header always set Strict-Transport-Security "max-age=63072000" # If HSTS desired

    <Directory {document_root}>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog ${{APACHE_LOG_DIR}}/{domain}.ssl.error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}.ssl.access.log combined
</VirtualHost>
</IfModule>

# Optional: Redirect HTTP to HTTPS
<VirtualHost *:80>
    ServerName {domain}
    ServerAlias www.{domain}
    Redirect permanent / https://{domain}/
</VirtualHost>
""")
    
    full_config = "".join(config_parts)
    config_path_in_container = f"/etc/apache2/sites-available/{domain}.conf"
    write_file(container_id, config_path_in_container, full_config)
    
    _execute_in_container(container_id, ['a2dissite', f'{domain}.conf'], ignore_failure=True)
    enable_result = _execute_in_container(container_id, ['a2ensite', f'{domain}.conf'])
    if enable_result.exit_code != 0:
        logger.error(f"Failed to enable Apache site {domain}.conf: {enable_result.stderr}")
        # raise Exception(...)

    # Test Apache configuration
    test_apache_result = _execute_in_container(container_id, ['apache2ctl', 'configtest'])
    if test_apache_result.exit_code != 0:
        logger.error(f"Apache configuration test failed for {domain} in {container_id}: {test_apache_result.stderr} {test_apache_result.stdout}")
        _execute_in_container(container_id, ['a2dissite', f'{domain}.conf'], ignore_failure=True) # Disable bad config
        raise Exception(f"Apache configuration error for {domain}. Please check logs.")
    else:
        logger.info(f"Apache configuration test for {domain} in {container_id} successful.")


def delete_website_config(container_id, domain):
    """
    Delete web server configuration for a website
    """
    nginx_config_path_avail = f"/etc/nginx/sites-available/{domain}"
    nginx_config_path_enabled = f"/etc/nginx/sites-enabled/{domain}"
    apache_config_path = f"/etc/apache2/sites-available/{domain}.conf"

    # Try Nginx
    # Check if enabled symlink exists first
    check_nginx_enabled = _execute_in_container(container_id, ['test', '-L', nginx_config_path_enabled], ignore_failure=True)
    if check_nginx_enabled.exit_code == 0:
        _execute_in_container(container_id, ['rm', '-f', nginx_config_path_enabled])
        _execute_in_container(container_id, ['rm', '-f', nginx_config_path_avail], ignore_failure=True)
        restart_service(container_id, 'nginx')
        logger.info(f"Nginx config for {domain} deleted from {container_id}.")
        return

    # Try Apache
    check_apache_enabled = _execute_in_container(container_id, ['a2query', '-s', f'{domain}.conf'], ignore_failure=True) # a2query tells if site is enabled
    if "enabled" in check_apache_enabled.stdout.lower(): # Heuristic check
         _execute_in_container(container_id, ['a2dissite', f'{domain}.conf'], ignore_failure=True)
    
    check_apache_avail = _execute_in_container(container_id, ['test', '-f', apache_config_path], ignore_failure=True)
    if check_apache_avail.exit_code == 0:
        _execute_in_container(container_id, ['rm', '-f', apache_config_path])
        restart_service(container_id, 'apache2')
        logger.info(f"Apache config for {domain} deleted from {container_id}.")
        return
        
    logger.warning(f"No specific Nginx or Apache config found to delete for {domain} in {container_id}.")
