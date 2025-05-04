import logging
import subprocess
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def request_ssl_certificate(container_id, domain):
    """
    Request an SSL certificate for a domain using Let's Encrypt
    
    Args:
        container_id: Container ID
        domain: Domain name for the certificate
    
    Returns:
        bool: Whether the certificate was successfully issued
    """
    try:
        from utils.container import container
        container = container.get(container_id)
        
        # Check if certbot is installed
        result = container.execute(['which', 'certbot'])
        if result.exit_code != 0:
            # Install certbot if not already installed
            container.execute(['apt-get', 'update'])
            container.execute(['apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'])
        
        # Get settings from the database for the email
        from models import SystemSetting
        email_setting = SystemSetting.query.filter_by(key='ssl_email').first()
        email = email_setting.value if email_setting else ""
        
        # Use standalone method first to obtain certificate
        cmd = ['certbot', 'certonly', '--standalone', '--non-interactive', 
               '--agree-tos', '-d', domain]
        
        if email:
            cmd.extend(['-m', email])
        else:
            cmd.append('--register-unsafely-without-email')
            
        # Stop web server temporarily to free up port 80
        from utils.container import stop_service, start_service
        
        # Detect web server type (nginx or apache)
        nginx_result = container.execute(['systemctl', 'is-active', 'nginx'], ignore_failure=True)
        apache_result = container.execute(['systemctl', 'is-active', 'apache2'], ignore_failure=True)
        
        web_server = None
        if nginx_result.exit_code == 0:
            web_server = 'nginx'
        elif apache_result.exit_code == 0:
            web_server = 'apache2'
        
        # Stop web server temporarily
        if web_server:
            stop_service(container_id, web_server)
        
        try:
            # Request certificate
            result = container.execute(cmd)
            
            if result.exit_code != 0:
                logger.error(f"Failed to obtain SSL certificate: {result.stderr}")
                raise Exception(f"Failed to obtain SSL certificate: {result.stderr}")
        finally:
            # Restart web server
            if web_server:
                start_service(container_id, web_server)
        
        # Set up auto-renewal
        setup_ssl_renewal(container_id)
        
        # Update certificate expiry in database
        from app import db
        from models import Website
        website = Website.query.filter_by(domain=domain).first()
        if website:
            website.ssl_expires = datetime.utcnow() + timedelta(days=90)  # Let's Encrypt certs valid for 90 days
            db.session.commit()
        
        return True
    
    except Exception as e:
        logger.error(f"Error requesting SSL certificate: {str(e)}")
        raise
    
def setup_ssl_renewal(container_id):
    """
    Set up automatic SSL certificate renewal
    
    Args:
        container_id: Container ID
    """
    try:
        from utils.container import container
        container = container.get(container_id)
        
        # Check if cron is installed
        result = container.execute(['which', 'crontab'])
        if result.exit_code != 0:
            # Install cron if not already installed
            container.execute(['apt-get', 'update'])
            container.execute(['apt-get', 'install', '-y', 'cron'])
        
        # Create renewal cron job
        renewal_command = "0 0,12 * * * certbot renew --quiet"
        
        # Add to crontab if not already present
        result = container.execute(['grep', '-q', 'certbot renew', '/etc/crontab'])
        if result.exit_code != 0:
            container.execute(['bash', '-c', f'echo "{renewal_command}" >> /etc/crontab'])
    
    except Exception as e:
        logger.error(f"Error setting up SSL renewal: {str(e)}")
        raise

def check_ssl_expiry(domain, container_id):
    """
    Check if an SSL certificate is expiring soon
    
    Args:
        domain: Domain name
        container_id: Container ID
        
    Returns:
        bool: Whether the certificate needs renewal (True if expiring within 30 days)
    """
    try:
        from utils.container import container
        container = container.get(container_id)
        
        # Check certificate expiry
        result = container.execute(['certbot', 'certificates', '-d', domain])
        
        if result.exit_code != 0:
            logger.error(f"Failed to check certificate expiry: {result.stderr}")
            return False
        
        # Parse the output to get expiry date
        output = result.stdout
        expiry_date = None
        
        for line in output.splitlines():
            if "Expiry Date" in line:
                parts = line.split(':', 1)
                if len(parts) > 1:
                    expiry_date_str = parts[1].strip()
                    # Parse date format (e.g., "2023-06-15 12:00:00+00:00")
                    try:
                        # Remove timezone if present
                        if '+' in expiry_date_str:
                            expiry_date_str = expiry_date_str.split('+')[0].strip()
                        
                        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")
                        break
                    except Exception as e:
                        logger.error(f"Error parsing expiry date: {str(e)}")
        
        if not expiry_date:
            return False
        
        # Check if certificate expires within 30 days
        days_until_expiry = (expiry_date - datetime.utcnow()).days
        return days_until_expiry <= 30
    
    except Exception as e:
        logger.error(f"Error checking SSL expiry: {str(e)}")
        return False
