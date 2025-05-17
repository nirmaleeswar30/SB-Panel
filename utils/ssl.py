import logging
import subprocess
import os
from datetime import datetime, timedelta
from .container import _execute_in_container, start_service, stop_service # Use specific function imports

logger = logging.getLogger(__name__)

def request_ssl_certificate(container_id, domain):
    """
    Request an SSL certificate for a domain using Let's Encrypt
    
    Args:
        container_id: Docker Container Name/ID
        domain: Domain name for the certificate
    
    Returns:
        bool: Whether the certificate was successfully issued
    """
    try:
        # Check if certbot is installed
        result = _execute_in_container(container_id, ['which', 'certbot'])
        if result.exit_code != 0:
            logger.info(f"Certbot not found in {container_id}. Installing...")
            _execute_in_container(container_id, ['apt-get', 'update', '-y'])
            # python3-certbot-nginx or python3-certbot-apache depending on webserver
            # For now, installing generic certbot and nginx plugin as an example
            install_result = _execute_in_container(container_id, ['apt-get', 'install', '-y', 'certbot', 'python3-certbot-nginx'])
            if install_result.exit_code != 0:
                logger.error(f"Failed to install certbot in {container_id}: {install_result.stderr}")
                raise Exception(f"Failed to install certbot in {container_id}")
        
        from models import SystemSetting # Assuming models.py is accessible
        email_setting = SystemSetting.query.filter_by(key='ssl_email').first()
        email = email_setting.value if email_setting and email_setting.value else ""
        
        cmd = ['certbot', 'certonly', '--standalone', '--non-interactive', 
               '--agree-tos', '-d', domain]
        
        if email:
            cmd.extend(['--email', email]) # Changed -m to --email for certbot
        else:
            cmd.append('--register-unsafely-without-email')
            
        web_server_service_name = None
        # Detect web server type (nginx or apache) to stop/start it
        # This detection is basic. A more robust way would be to check installed packages or listening ports.
        nginx_active_check = _execute_in_container(container_id, ['service', 'nginx', 'status'], ignore_failure=True)
        if nginx_active_check.exit_code == 0 and "active (running)" in nginx_active_check.stdout.lower():
             web_server_service_name = 'nginx'
        else:
            apache_active_check = _execute_in_container(container_id, ['service', 'apache2', 'status'], ignore_failure=True)
            if apache_active_check.exit_code == 0 and "active (running)" in apache_active_check.stdout.lower():
                web_server_service_name = 'apache2'
        
        if web_server_service_name:
            logger.info(f"Stopping web server {web_server_service_name} in {container_id} for SSL challenge.")
            stop_service(container_id, web_server_service_name)
        
        cert_result = None
        try:
            logger.info(f"Requesting SSL certificate for {domain} in {container_id} with command: {' '.join(cmd)}")
            cert_result = _execute_in_container(container_id, cmd)
            
            if cert_result.exit_code != 0:
                logger.error(f"Failed to obtain SSL certificate for {domain}: {cert_result.stderr} {cert_result.stdout}")
                raise Exception(f"Failed to obtain SSL certificate for {domain}: {cert_result.stderr or cert_result.stdout}")
            logger.info(f"Successfully obtained SSL certificate for {domain}.")
        finally:
            if web_server_service_name:
                logger.info(f"Starting web server {web_server_service_name} in {container_id}.")
                start_service(container_id, web_server_service_name)
        
        setup_ssl_renewal(container_id)
        
        from app import db # Assuming app.py and db are accessible
        from models import Website
        website = Website.query.filter_by(domain=domain, user_id=current_user.id).first() # Scope to current user if applicable
        if website: # Check if website exists before trying to update it
            website.ssl_expires = datetime.utcnow() + timedelta(days=89) # Let's Encrypt certs valid for 90 days, renew a bit earlier
            db.session.commit()
        
        return True
    
    except Exception as e:
        logger.error(f"Error in request_ssl_certificate for {domain}: {str(e)}")
        # If cert_result is available and has output, include it for better debugging
        if 'cert_result' in locals() and cert_result and (cert_result.stdout or cert_result.stderr):
             logger.error(f"Certbot output: STDOUT: {cert_result.stdout} STDERR: {cert_result.stderr}")
        raise
    
def setup_ssl_renewal(container_id):
    """
    Set up automatic SSL certificate renewal cron job in the container.
    """
    try:
        # Certbot usually sets up its own renewal mechanism (e.g., via systemd timer or cron.d file)
        # We can ensure certbot's default renewal is active.
        # Example: check for /etc/cron.d/certbot or systemd timer
        
        # Forcing a simple cron job if certbot's own isn't confirmed
        # This might be redundant if certbot's package setup includes it.
        renewal_cmd_in_cron = "certbot renew --quiet"
        cron_job_entry = f"0 */12 * * * root {renewal_cmd_in_cron}\n" # Run twice a day
        cron_file_content = f"# SBPanel managed: Certbot auto-renewal\n{cron_job_entry}"
        
        # Write to a specific file in cron.d
        from .container import write_file # Use the new write_file from utils.container
        write_file(container_id, "/etc/cron.d/sbpanel-certbot-renew", cron_file_content)
        _execute_in_container(container_id, ['chmod', '644', "/etc/cron.d/sbpanel-certbot-renew"])
        _execute_in_container(container_id, ['chown', 'root:root', "/etc/cron.d/sbpanel-certbot-renew"])
        
        logger.info(f"SSL renewal cron job ensured for container {container_id}.")
        restart_service(container_id, 'cron') # Ensure cron service re-reads configs
    
    except Exception as e:
        logger.error(f"Error setting up SSL renewal for {container_id}: {str(e)}")
        # Not raising exception here as main SSL request might have succeeded.


def check_ssl_expiry(domain, container_id):
    """
    Check SSL certificate expiry using certbot certificates.
    
    Args:
        domain: Domain name.
        container_id: Docker Container Name/ID.
        
    Returns:
        bool: True if expiring within 30 days or other issue, False otherwise.
    """
    try:
        # The command `certbot certificates` provides info for all managed certs.
        result = _execute_in_container(container_id, ['certbot', 'certificates'])
        
        if result.exit_code != 0:
            logger.error(f"Failed to execute 'certbot certificates' in {container_id}: {result.stderr}")
            return True # Assume issue, needs attention

        output = result.stdout
        cert_info_block = None
        current_cert_name = None
        
        # Parse the output for the specific domain
        # Output format can be:
        # Certificate Name: example.com
        #   Domains: example.com www.example.com
        #   Expiry Date: 2025-08-15 10:00:00+00:00 (VALID: 89 days)
        #   Certificate Path: /etc/letsencrypt/live/example.com/fullchain.pem
        #   Private Key Path: /etc/letsencrypt/live/example.com/privkey.pem
        
        lines = output.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("Certificate Name:"):
                # Check if this cert name or its domains match our target domain
                cert_name_from_output = line.split(":",1)[1].strip()
                # Look for Domains line next
                domains_line_found = False
                for j in range(i + 1, min(i + 5, len(lines))): # Check next few lines
                    if lines[j].strip().startswith("Domains:"):
                        domains_in_cert = lines[j].split(":",1)[1].strip()
                        if domain in domains_in_cert.split():
                            current_cert_name = cert_name_from_output # Found our cert block
                            domains_line_found = True
                        break
                if not domains_line_found and cert_name_from_output == domain: # If name matches domain directly
                    current_cert_name = cert_name_from_output


            if current_cert_name and line.strip().startswith("Expiry Date:"):
                expiry_date_str_full = line.split(":",1)[1].strip()
                # Example: "2025-08-15 10:00:00+00:00 (VALID: 89 days)"
                # Extract the date part before the parenthesis
                expiry_date_str = expiry_date_str_full.split("(")[0].strip()
                
                # Try to parse VALID: X days part for a quick check
                if "(VALID: " in expiry_date_str_full:
                    try:
                        days_valid_str = expiry_date_str_full.split("(VALID: ")[1].split(" days)")[0]
                        days_valid = int(days_valid_str)
                        logger.info(f"Certificate for {domain} in {container_id} is valid for {days_valid} days.")
                        return days_valid <= 30
                    except (IndexError, ValueError) as parse_err:
                        logger.warning(f"Could not parse days valid from '{expiry_date_str_full}': {parse_err}")
                
                # Fallback to parsing the date string if days valid couldn't be parsed
                try:
                    if '+' in expiry_date_str: # Handle timezone offset
                        expiry_date_str = expiry_date_str.split('+')[0].strip()
                    elif '-' in expiry_date_str.split()[-1] and len(expiry_date_str.split()[-1]) == 5 : # e.g. 10:00:00-05:00
                         expiry_date_str = expiry_date_str.rsplit('-',1)[0].strip()


                    expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d %H:%M:%S")
                    days_until_expiry = (expiry_date - datetime.utcnow()).days
                    logger.info(f"Certificate for {domain} in {container_id} expires on {expiry_date_str} ({days_until_expiry} days).")
                    return days_until_expiry <= 30
                except ValueError as e:
                    logger.error(f"Error parsing expiry date string '{expiry_date_str}' for {domain}: {e}")
                    return True # Error in parsing, assume needs renewal
                finally:
                    break # Found expiry for our domain, no need to check further
        
        logger.warning(f"Could not find SSL certificate information for domain '{domain}' in 'certbot certificates' output for {container_id}.")
        return True # Not found, assume needs renewal or setup

    except Exception as e:
        logger.error(f"Error checking SSL expiry for {domain} in {container_id}: {str(e)}")
        return True # Error occurred, better to assume renewal is needed