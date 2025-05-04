/**
 * SBPanel - Containers JavaScript
 * Handles container-specific functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation
    initFormValidation();
    
    // Set up status refresh
    setInterval(refreshContainerStatus, 30000); // Refresh every 30 seconds
});

/**
 * Initialize form validation for container creation
 */
function initFormValidation() {
    const createContainerForm = document.getElementById('createContainerForm');
    if (createContainerForm) {
        createContainerForm.addEventListener('submit', function(event) {
            const nameInput = document.getElementById('containerName');
            if (!nameInput.value.trim()) {
                event.preventDefault();
                nameInput.classList.add('is-invalid');
                return false;
            }
            
            const templateSelect = document.getElementById('containerTemplate');
            if (!templateSelect.value) {
                event.preventDefault();
                templateSelect.classList.add('is-invalid');
                return false;
            }
            
            return true;
        });
        
        // Clear validation errors on input
        const inputs = createContainerForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('is-invalid');
            });
        });
    }
}

/**
 * Refresh container status
 */
function refreshContainerStatus() {
    // Get all container rows
    const containerRows = document.querySelectorAll('[data-container-id]');
    if (containerRows.length === 0) return;
    
    // Extract container IDs
    const containerIds = Array.from(containerRows).map(row => row.getAttribute('data-container-id'));
    
    // Fetch container status
    fetch('/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            // Update container stats
            const containers = data.container_stats;
            for (const [containerId, stats] of Object.entries(containers)) {
                updateContainerRow(containerId, stats);
            }
        })
        .catch(error => {
            console.error('Error fetching container stats:', error);
        });
}

/**
 * Update container row with latest status
 * @param {string} containerId - Container ID
 * @param {Object} stats - Container stats
 */
function updateContainerRow(containerId, stats) {
    const statusElement = document.getElementById(`container-status-${containerId}`);
    if (statusElement) {
        statusElement.innerHTML = stats.status;
        
        // Update status badge color
        statusElement.className = 'badge';
        if (stats.status === 'running') {
            statusElement.classList.add('bg-success');
        } else if (stats.status === 'stopped') {
            statusElement.classList.add('bg-danger');
        } else {
            statusElement.classList.add('bg-warning');
        }
    }
    
    // Update CPU usage
    const cpuElement = document.getElementById(`container-cpu-${containerId}`);
    if (cpuElement) {
        cpuElement.innerHTML = `${stats.cpu_percent.toFixed(1)}%`;
    }
    
    // Update memory usage
    const memoryElement = document.getElementById(`container-memory-${containerId}`);
    if (memoryElement) {
        memoryElement.innerHTML = formatBytes(stats.memory_used);
    }
    
    // Update buttons based on status
    const startButton = document.getElementById(`container-start-${containerId}`);
    const stopButton = document.getElementById(`container-stop-${containerId}`);
    const restartButton = document.getElementById(`container-restart-${containerId}`);
    
    if (startButton && stopButton && restartButton) {
        if (stats.status === 'running') {
            startButton.classList.add('disabled');
            stopButton.classList.remove('disabled');
            restartButton.classList.remove('disabled');
        } else if (stats.status === 'stopped') {
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

/**
 * Show creation modal with appropriate settings
 */
function showCreateContainerModal() {
    const modal = new bootstrap.Modal(document.getElementById('createContainerModal'));
    
    // Reset form
    const form = document.getElementById('createContainerForm');
    if (form) {
        form.reset();
    }
    
    modal.show();
}
