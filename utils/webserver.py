import logging
import os
import tempfile

logger = logging.getLogger(__name__)

def create_website_config(container_id, domain, server_type, php_version, document_root, ssl_enabled):
    """
    Create web server configuration for a website
    
    Args:
        container_id: Container ID
        domain: Domain name
        server_type: Web server type (nginx, apache)
        php_version: PHP version
        document_root: Document root path
        ssl_enabled: Whether SSL is enabled
    """
    from utils.container import write_file
    
    # Create document root directory if it doesn't exist
    from utils.container import create_directory
    create_directory(container_id, document_root)
    
    # Create a simple index.html file
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
    index_path = os.path.join(document_root, 'index.html')
    write_file(container_id, index_path, index_content)
    
    # Create server configuration based on server type
    if server_type == 'nginx':
        create_nginx_config(container_id, domain, document_root, php_version, ssl_enabled)
    elif server_type == 'apache':
        create_apache_config(container_id, domain, document_root, php_version, ssl_enabled)
    else:
        raise ValueError(f"Unsupported server type: {server_type}")
    
    # Restart the web server
    from utils.container import restart_service
    restart_service(container_id, server_type)

def create_nginx_config(container_id, domain, document_root, php_version, ssl_enabled):
    """
    Create Nginx configuration for a website
    
    Args:
        container_id: Container ID
        domain: Domain name
        document_root: Document root path
        php_version: PHP version
        ssl_enabled: Whether SSL is enabled
    """
    from utils.container import write_file
    
    # Create PHP-FPM configuration
    if php_version:
        # Install PHP if needed
        from utils.container import container
        container = container.get(container_id)
        container.execute(['apt-get', 'update'])
        container.execute(['apt-get', 'install', '-y', f'php{php_version}-fpm'])
        
        # Restart PHP-FPM
        restart_service(container_id, f'php{php_version}-fpm')
    
    # Create Nginx configuration
    config = f"""server {{
    listen 80;
    server_name {domain};
    root {document_root};
    index index.html index.php;
    
    access_log /var/log/nginx/{domain}_access.log;
    error_log /var/log/nginx/{domain}_error.log;
    
    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}
"""
    
    # Add PHP configuration if a PHP version is specified
    if php_version:
        config += f"""
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php{php_version}-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}
"""
    
    config += """
    location ~ /\\.ht {
        deny all;
    }
}
"""
    
    # Add SSL configuration if enabled
    if ssl_enabled:
        config += f"""
server {{
    listen 443 ssl;
    server_name {domain};
    root {document_root};
    index index.html index.php;
    
    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    
    access_log /var/log/nginx/{domain}_access.log;
    error_log /var/log/nginx/{domain}_error.log;
    
    location / {{
        try_files $uri $uri/ /index.php?$args;
    }}
"""
        
        # Add PHP configuration if a PHP version is specified
        if php_version:
            config += f"""
    location ~ \\.php$ {{
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:/var/run/php/php{php_version}-fpm.sock;
        fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
        include fastcgi_params;
    }}
"""
        
        config += """
    location ~ /\\.ht {
        deny all;
    }
}
"""
    
    # Write the configuration file
    config_path = f"/etc/nginx/sites-available/{domain}"
    write_file(container_id, config_path, config)
    
    # Create symbolic link to enable the site
    from utils.container import container
    container = container.get(container_id)
    
    # Remove any existing symlink
    container.execute(['rm', '-f', f'/etc/nginx/sites-enabled/{domain}'])
    
    # Create the symlink
    container.execute(['ln', '-s', f'/etc/nginx/sites-available/{domain}', f'/etc/nginx/sites-enabled/{domain}'])

def create_apache_config(container_id, domain, document_root, php_version, ssl_enabled):
    """
    Create Apache configuration for a website
    
    Args:
        container_id: Container ID
        domain: Domain name
        document_root: Document root path
        php_version: PHP version
        ssl_enabled: Whether SSL is enabled
    """
    from utils.container import write_file
    
    # Create Apache configuration
    config = f"""<VirtualHost *:80>
    ServerName {domain}
    DocumentRoot {document_root}
    
    <Directory {document_root}>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}_access.log combined
</VirtualHost>
"""
    
    # Add SSL configuration if enabled
    if ssl_enabled:
        # Install SSL module
        from utils.container import container
        container = container.get(container_id)
        container.execute(['a2enmod', 'ssl'])
        
        config += f"""
<VirtualHost *:443>
    ServerName {domain}
    DocumentRoot {document_root}
    
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/{domain}/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/{domain}/privkey.pem
    
    <Directory {document_root}>
        Options Indexes FollowSymLinks
        AllowOverride All
        Require all granted
    </Directory>
    
    ErrorLog ${{APACHE_LOG_DIR}}/{domain}_ssl_error.log
    CustomLog ${{APACHE_LOG_DIR}}/{domain}_ssl_access.log combined
</VirtualHost>
"""
    
    # Write the configuration file
    config_path = f"/etc/apache2/sites-available/{domain}.conf"
    write_file(container_id, config_path, config)
    
    # Enable the site
    from utils.container import container
    container = container.get(container_id)
    
    # Disable any existing site with the same name
    container.execute(['a2dissite', f'{domain}.conf'], ignore_failure=True)
    
    # Enable the new site
    container.execute(['a2ensite', f'{domain}.conf'])

def delete_website_config(container_id, domain):
    """
    Delete web server configuration for a website
    
    Args:
        container_id: Container ID
        domain: Domain name
    """
    from utils.container import delete_file, container
    container = container.get(container_id)
    
    # Detect web server type
    nginx_config_path = f"/etc/nginx/sites-available/{domain}"
    apache_config_path = f"/etc/apache2/sites-available/{domain}.conf"
    
    # Check and delete Nginx configuration
    try:
        result = container.execute(['test', '-f', nginx_config_path])
        if result.exit_code == 0:
            # Disable site
            container.execute(['rm', '-f', f'/etc/nginx/sites-enabled/{domain}'])
            # Delete configuration
            delete_file(container_id, nginx_config_path)
            # Restart Nginx
            container.execute(['systemctl', 'restart', 'nginx'])
    except:
        pass
    
    # Check and delete Apache configuration
    try:
        result = container.execute(['test', '-f', apache_config_path])
        if result.exit_code == 0:
            # Disable site
            container.execute(['a2dissite', f'{domain}.conf'], ignore_failure=True)
            # Delete configuration
            delete_file(container_id, apache_config_path)
            # Restart Apache
            container.execute(['systemctl', 'restart', 'apache2'])
    except:
        pass
