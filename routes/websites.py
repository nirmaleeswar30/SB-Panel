import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, Website, ActivityLog, DNSRecord
from utils.webserver import create_website_config, delete_website_config
from utils.ssl import request_ssl_certificate

# Create blueprint
websites_bp = Blueprint('websites', __name__, url_prefix='/websites')
logger = logging.getLogger(__name__)

@websites_bp.route('/')
@login_required
def index():
    websites = Website.query.filter_by(user_id=current_user.id).all()
    containers = Container.query.filter_by(user_id=current_user.id).all()
    return render_template('dashboard/websites.html', websites=websites, containers=containers)

@websites_bp.route('/create', methods=['POST'])
@login_required
def create():
    domain = request.form.get('domain')
    container_id = request.form.get('container_id')
    server_type = request.form.get('server_type')
    php_version = request.form.get('php_version')
    document_root = request.form.get('document_root', '/var/www/html')
    ssl_enabled = 'ssl_enabled' in request.form
    
    # Validation
    if not domain or not container_id or not server_type:
        flash('Domain, container, and server type are required.', 'danger')
        return redirect(url_for('websites.index'))
    
    # Check if website with this domain already exists
    if Website.query.filter_by(domain=domain).first():
        flash('A website with this domain already exists.', 'danger')
        return redirect(url_for('websites.index'))
    
    # Check if the container exists and belongs to the user
    container = Container.query.get(container_id)
    if not container or container.user_id != current_user.id:
        flash('Invalid container selected.', 'danger')
        return redirect(url_for('websites.index'))
    
    try:
        # Create website configuration on the container
        create_website_config(
            container.container_id,
            domain,
            server_type,
            php_version,
            document_root,
            ssl_enabled
        )
        
        # Create website record in database
        website = Website(
            user_id=current_user.id,
            container_id=container.id,
            domain=domain,
            server_type=server_type,
            php_version=php_version,
            document_root=document_root,
            ssl_enabled=ssl_enabled
        )
        db.session.add(website)
        
        # If SSL is enabled, request certificate
        if ssl_enabled:
            try:
                request_ssl_certificate(container.container_id, domain)
            except Exception as e:
                logger.error(f"Error requesting SSL certificate: {str(e)}")
                flash(f'Website created, but SSL certificate request failed: {str(e)}', 'warning')
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Website Created",
            details=f"Created website: {domain}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        flash(f'Website {domain} created successfully.', 'success')
    except Exception as e:
        logger.error(f"Error creating website: {str(e)}")
        flash(f'Error creating website: {str(e)}', 'danger')
    
    return redirect(url_for('websites.index'))

@websites_bp.route('/<int:website_id>/delete', methods=['POST'])
@login_required
def delete(website_id):
    website = Website.query.get_or_404(website_id)
    
    # Check if user owns this website
    if website.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('websites.index'))
    
    container = Container.query.get(website.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('websites.index'))
    
    try:
        # Delete website configuration on the container
        delete_website_config(container.container_id, website.domain)
        
        domain = website.domain
        
        # Delete DNS records
        DNSRecord.query.filter_by(website_id=website.id).delete()
        
        # Log activity
        log = ActivityLog(
            user_id=current_user.id,
            action="Website Deleted",
            details=f"Deleted website: {domain}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        # Delete website from database
        db.session.delete(website)
        db.session.commit()
        
        flash(f'Website {domain} deleted successfully.', 'success')
    except Exception as e:
        logger.error(f"Error deleting website: {str(e)}")
        flash(f'Error deleting website: {str(e)}', 'danger')
    
    return redirect(url_for('websites.index'))

@websites_bp.route('/<int:website_id>/toggle_ssl', methods=['POST'])
@login_required
def toggle_ssl(website_id):
    website = Website.query.get_or_404(website_id)
    
    # Check if user owns this website
    if website.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('websites.index'))
    
    container = Container.query.get(website.container_id)
    if not container:
        flash('Associated container not found.', 'danger')
        return redirect(url_for('websites.index'))
    
    try:
        # Toggle SSL
        website.ssl_enabled = not website.ssl_enabled
        
        # Update website configuration
        create_website_config(
            container.container_id,
            website.domain,
            website.server_type,
            website.php_version,
            website.document_root,
            website.ssl_enabled
        )
        
        # If enabling SSL, request certificate
        if website.ssl_enabled:
            try:
                request_ssl_certificate(container.container_id, website.domain)
            except Exception as e:
                logger.error(f"Error requesting SSL certificate: {str(e)}")
                flash(f'SSL toggled, but certificate request failed: {str(e)}', 'warning')
        
        # Log activity
        action = "SSL Enabled" if website.ssl_enabled else "SSL Disabled"
        log = ActivityLog(
            user_id=current_user.id,
            action=action,
            details=f"{action} for website: {website.domain}",
            ip_address=request.remote_addr
        )
        db.session.add(log)
        
        db.session.commit()
        
        message = f'SSL {"enabled" if website.ssl_enabled else "disabled"} for {website.domain}.'
        flash(message, 'success')
    except Exception as e:
        logger.error(f"Error toggling SSL: {str(e)}")
        flash(f'Error toggling SSL: {str(e)}', 'danger')
    
    return redirect(url_for('websites.index'))

@websites_bp.route('/<int:website_id>/dns')
@login_required
def dns(website_id):
    website = Website.query.get_or_404(website_id)
    
    # Check if user owns this website
    if website.user_id != current_user.id:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('websites.index'))
    
    dns_records = DNSRecord.query.filter_by(website_id=website.id).all()
    
    return render_template('dashboard/dns.html', website=website, dns_records=dns_records)

@websites_bp.route('/<int:website_id>/dns/add', methods=['POST'])
@login_required
def add_dns(website_id):
    website = Website.query.get_or_404(website_id)
    
    # Check if user owns this website
    if website.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('websites.index'))
    
    record_type = request.form.get('record_type')
    name = request.form.get('name')
    value = request.form.get('value')
    ttl = request.form.get('ttl', 3600)
    priority = request.form.get('priority')
    comment = request.form.get('comment')
    
    # Validation
    if not record_type or not name or not value:
        flash('Record type, name, and value are required.', 'danger')
        return redirect(url_for('websites.dns', website_id=website.id))
    
    # Create DNS record
    dns_record = DNSRecord(
        website_id=website.id,
        record_type=record_type,
        name=name,
        value=value,
        ttl=ttl,
        priority=priority,
        comment=comment
    )
    db.session.add(dns_record)
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="DNS Record Added",
        details=f"Added {record_type} record for {website.domain}: {name}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    db.session.commit()
    
    flash(f'DNS record added successfully.', 'success')
    return redirect(url_for('websites.dns', website_id=website.id))

@websites_bp.route('/dns/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_dns(record_id):
    dns_record = DNSRecord.query.get_or_404(record_id)
    website = Website.query.get(dns_record.website_id)
    
    # Check if user owns this website
    if website.user_id != current_user.id:
        flash('You do not have permission to perform this action.', 'danger')
        return redirect(url_for('websites.index'))
    
    record_type = dns_record.record_type
    name = dns_record.name
    
    # Log activity
    log = ActivityLog(
        user_id=current_user.id,
        action="DNS Record Deleted",
        details=f"Deleted {record_type} record for {website.domain}: {name}",
        ip_address=request.remote_addr
    )
    db.session.add(log)
    
    # Delete record
    db.session.delete(dns_record)
    db.session.commit()
    
    flash(f'DNS record deleted successfully.', 'success')
    return redirect(url_for('websites.dns', website_id=website.id))
