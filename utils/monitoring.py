import logging
import os
import platform
import psutil
from datetime import datetime
from models import User, Container, Website, Database, Service

logger = logging.getLogger(__name__)

def get_system_stats():
    """
    Get system resource usage statistics
    
    Returns:
        dict: System stats including CPU, memory, and disk usage
    """
    try:
        stats = {
            'cpu_usage': psutil.cpu_percent(interval=0.1),
            'memory_total': psutil.virtual_memory().total,
            'memory_used': psutil.virtual_memory().used,
            'memory_percent': psutil.virtual_memory().percent,
            'disk_total': psutil.disk_usage('/').total,
            'disk_used': psutil.disk_usage('/').used,
            'disk_percent': psutil.disk_usage('/').percent,
            'uptime': int((datetime.now() - datetime.fromtimestamp(psutil.boot_time())).total_seconds()),
            'os_info': f"{platform.system()} {platform.release()}",
            'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0]
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        # Return defaults if there's an error
        return {
            'cpu_usage': 0,
            'memory_total': 0,
            'memory_used': 0,
            'memory_percent': 0,
            'disk_total': 0,
            'disk_used': 0,
            'disk_percent': 0,
            'uptime': 0,
            'os_info': 'Unknown',
            'load_avg': [0, 0, 0]
        }

def get_user_resources(user_id):
    """
    Get resource usage statistics for a specific user
    
    Args:
        user_id: User ID
        
    Returns:
        dict: User resource stats including containers, websites, etc.
    """
    try:
        # Get counts of user resources
        container_count = Container.query.filter_by(user_id=user_id).count()
        website_count = Website.query.filter_by(user_id=user_id).count()
        database_count = Database.query.filter_by(user_id=user_id).count()
        
        # Get container resource allocation and usage
        containers = Container.query.filter_by(user_id=user_id).all()
        
        total_cpu_allocated = sum(c.cpu_allocated for c in containers)
        total_memory_allocated = sum(c.memory_allocated for c in containers)
        total_disk_allocated = sum(c.disk_allocated for c in containers)
        
        # Since we don't have real-time container metrics, we'll estimate usage based on allocation
        # In a real system, this would query the actual container resource usage
        
        # Calculate resource percentages
        user = User.query.get(user_id)
        cpu_percent = (total_cpu_allocated / user.cpu_limit) * 100 if user.cpu_limit > 0 else 0
        memory_percent = (total_memory_allocated / user.memory_limit) * 100 if user.memory_limit > 0 else 0
        disk_percent = (total_disk_allocated / user.disk_limit) * 100 if user.disk_limit > 0 else 0
        
        stats = {
            'container_count': container_count,
            'website_count': website_count,
            'database_count': database_count,
            'total_cpu_allocated': total_cpu_allocated,
            'total_memory_allocated': total_memory_allocated,
            'total_disk_allocated': total_disk_allocated,
            'cpu_limit': user.cpu_limit,
            'memory_limit': user.memory_limit,
            'disk_limit': user.disk_limit,
            'cpu_percent': min(cpu_percent, 100),
            'memory_percent': min(memory_percent, 100),
            'disk_percent': min(disk_percent, 100),
            'active_containers': Container.query.filter_by(user_id=user_id, status='running').count()
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting user resources: {str(e)}")
        # Return defaults if there's an error
        return {
            'container_count': 0,
            'website_count': 0,
            'database_count': 0,
            'total_cpu_allocated': 0,
            'total_memory_allocated': 0,
            'total_disk_allocated': 0,
            'cpu_limit': 0,
            'memory_limit': 0,
            'disk_limit': 0,
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_percent': 0,
            'active_containers': 0
        }

def get_containers_status():
    """
    Get status of all containers in the system
    
    Returns:
        list: Container status information
    """
    try:
        containers = Container.query.all()
        container_statuses = []
        
        for container in containers:
            # Get services in this container
            services = Service.query.filter_by(container_id=container.id).all()
            service_statuses = [{'name': s.name, 'status': s.status} for s in services]
            
            # Get user information
            user = User.query.get(container.user_id)
            username = user.username if user else 'Unknown'
            
            container_statuses.append({
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'ip_address': container.ip_address,
                'template': container.template,
                'created_at': container.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'username': username,
                'services': service_statuses,
                'cpu_allocated': container.cpu_allocated,
                'memory_allocated': container.memory_allocated,
                'disk_allocated': container.disk_allocated
            })
        
        return container_statuses
    except Exception as e:
        logger.error(f"Error getting container status: {str(e)}")
        return []

def get_system_overview():
    """
    Get a system overview with counts of users, containers, etc.
    
    Returns:
        dict: System overview statistics
    """
    try:
        stats = {
            'user_count': User.query.count(),
            'active_user_count': User.query.filter_by(active=True).count(),
            'container_count': Container.query.count(),
            'running_container_count': Container.query.filter_by(status='running').count(),
            'website_count': Website.query.count(),
            'database_count': Database.query.count(),
            'service_count': Service.query.count(),
            'running_service_count': Service.query.filter_by(status='running').count()
        }
        return stats
    except Exception as e:
        logger.error(f"Error getting system overview: {str(e)}")
        return {
            'user_count': 0,
            'active_user_count': 0,
            'container_count': 0,
            'running_container_count': 0,
            'website_count': 0,
            'database_count': 0,
            'service_count': 0,
            'running_service_count': 0
        }