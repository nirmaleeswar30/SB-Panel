import logging
from flask import Blueprint, render_template, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app import db
from models import Container, Website, Database, Service, CronJob, ActivityLog
from utils.monitoring import get_system_stats, get_user_resources

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')
logger = logging.getLogger(__name__)

@dashboard_bp.route('/')
@login_required
def index():
    # Get user's containers
    containers = Container.query.filter_by(user_id=current_user.id).all()
    
    # Get resource usage statistics
    resources = get_user_resources(current_user.id)
    
    # Count websites, databases, and services
    website_count = Website.query.filter_by(user_id=current_user.id).count()
    database_count = Database.query.filter_by(user_id=current_user.id).count()
    service_count = Service.query.join(Container).filter(Container.user_id == current_user.id).count()
    
    # Recent activity logs
    recent_logs = ActivityLog.query.filter_by(user_id=current_user.id)\
        .order_by(ActivityLog.created_at.desc()).limit(10).all()
    
    return render_template('dashboard/index.html', 
                          containers=containers,
                          resources=resources,
                          website_count=website_count,
                          database_count=database_count,
                          service_count=service_count,
                          recent_logs=recent_logs)

@dashboard_bp.route('/stats')
@login_required
def stats():
    """Return JSON stats for the dashboard"""
    # Get user's containers
    containers = Container.query.filter_by(user_id=current_user.id).all()
    
    # For now, we'll use the same system stats for all containers
    # In a real implementation, we would query each container's actual stats
    system_stats = get_system_stats()
    
    # Get system stats for all containers
    container_stats = {}
    for container in containers:
        # Apply container-specific stats here (in a real implementation)
        container_stats[container.id] = {
            'cpu_usage': system_stats['cpu_usage'] / max(len(containers), 1),
            'memory_used': int(system_stats['memory_used'] / max(len(containers), 1)),
            'disk_used': int(system_stats['disk_used'] / max(len(containers), 1)),
            'status': container.status
        }
    
    # Get resource usage
    resources = get_user_resources(current_user.id)
    
    return jsonify({
        'container_stats': container_stats,
        'resources': resources
    })
