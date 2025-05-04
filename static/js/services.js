/**
 * SBPanel - Services JavaScript
 * Handles service-specific functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Set up status refresh
    setInterval(refreshServiceStatus, 30000); // Refresh every 30 seconds
    
    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

/**
 * Refresh service status
 */
function refreshServiceStatus() {
    // Get all service rows
    const serviceRows = document.querySelectorAll('[data-service-id]');
    if (serviceRows.length === 0) return;
    
    // Extract service IDs
    const serviceIds = Array.from(serviceRows).map(row => row.getAttribute('data-service-id'));
    
    // For this demo, we'll just use fetch to get current status from the dashboard stats endpoint
    fetch('/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            // This endpoint doesn't actually return service status, but in a real implementation
            // you would use a dedicated endpoint for service status
            refreshServiceStatusFromServer();
        })
        .catch(error => {
            console.error('Error fetching service stats:', error);
        });
}

/**
 * Fetch service status from server and update UI
 * This is a placeholder that would be implemented in a real system
 */
function refreshServiceStatusFromServer() {
    // In a real implementation, this would make a dedicated API call to get service status
    console.log('In a real implementation, service status would be refreshed from the server');
}

/**
 * Handle service action (start, stop, restart)
 * @param {string} action - Action to perform (start, stop, restart)
 * @param {string} serviceId - Service ID
 * @param {string} serviceName - Service name for confirmation message
 */
function handleServiceAction(action, serviceId, serviceName) {
    // Confirmation for stopping or restarting services
    if (action === 'stop' || action === 'restart') {
        if (!confirm(`Are you sure you want to ${action} the ${serviceName} service?`)) {
            return;
        }
    }
    
    // Submit the form programmatically
    const form = document.getElementById(`service-${action}-form-${serviceId}`);
    if (form) {
        form.submit();
    }
}

/**
 * Toggle autostart for a service
 * @param {string} serviceId - Service ID
 */
function toggleAutostart(serviceId) {
    const form = document.getElementById(`service-toggle-autostart-form-${serviceId}`);
    if (form) {
        form.submit();
    }
}

/**
 * Update service status in UI
 * @param {string} serviceId - Service ID
 * @param {string} status - Service status (running, stopped, error)
 */
function updateServiceStatus(serviceId, status) {
    const statusElement = document.getElementById(`service-status-${serviceId}`);
    if (statusElement) {
        statusElement.innerHTML = status;
        
        // Update status badge color
        statusElement.className = 'badge';
        if (status === 'running') {
            statusElement.classList.add('bg-success');
        } else if (status === 'stopped') {
            statusElement.classList.add('bg-danger');
        } else {
            statusElement.classList.add('bg-warning');
        }
    }
    
    // Update action buttons
    const startButton = document.getElementById(`service-start-btn-${serviceId}`);
    const stopButton = document.getElementById(`service-stop-btn-${serviceId}`);
    const restartButton = document.getElementById(`service-restart-btn-${serviceId}`);
    
    if (startButton && stopButton && restartButton) {
        if (status === 'running') {
            startButton.classList.add('disabled');
            stopButton.classList.remove('disabled');
            restartButton.classList.remove('disabled');
        } else if (status === 'stopped') {
            startButton.classList.remove('disabled');
            stopButton.classList.add('disabled');
            restartButton.classList.add('disabled');
        } else {
            startButton.classList.remove('disabled');
            stopButton.classList.remove('disabled');
            restartButton.classList.remove('disabled');
        }
    }
}
