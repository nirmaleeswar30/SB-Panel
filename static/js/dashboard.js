/**
 * SBPanel - Dashboard JavaScript
 * Handles dashboard-specific functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize resource usage charts
    initResourceCharts();
    
    // Fetch live stats for containers
    setInterval(fetchContainerStats, 10000); // Update every 10 seconds
    fetchContainerStats(); // Initial fetch
});

/**
 * Initialize resource usage charts
 */
function initResourceCharts() {
    // CPU Usage Chart
    const cpuCanvas = document.getElementById('cpuUsageChart');
    if (cpuCanvas) {
        const cpuUsage = parseFloat(cpuCanvas.getAttribute('data-value')) || 0;
        const cpuLimit = parseFloat(cpuCanvas.getAttribute('data-limit')) || 100;
        const cpuPercent = (cpuUsage / cpuLimit) * 100;
        
        new Chart(cpuCanvas, {
            type: 'doughnut',
            data: {
                labels: ['Used', 'Available'],
                datasets: [{
                    data: [cpuPercent, 100 - cpuPercent],
                    backgroundColor: ['#20c997', '#2c3e50']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${cpuUsage} of ${cpuLimit} cores (${cpuPercent.toFixed(1)}%)`;
                            }
                        }
                    }
                }
            }
        });
        
        // Set center text
        const cpuCenterText = document.getElementById('cpuCenterText');
        if (cpuCenterText) {
            cpuCenterText.innerHTML = `${cpuPercent.toFixed(1)}%`;
        }
    }
    
    // Memory Usage Chart
    const memoryCanvas = document.getElementById('memoryUsageChart');
    if (memoryCanvas) {
        const memoryUsage = parseFloat(memoryCanvas.getAttribute('data-value')) || 0;
        const memoryLimit = parseFloat(memoryCanvas.getAttribute('data-limit')) || 100;
        const memoryPercent = (memoryUsage / memoryLimit) * 100;
        
        new Chart(memoryCanvas, {
            type: 'doughnut',
            data: {
                labels: ['Used', 'Available'],
                datasets: [{
                    data: [memoryPercent, 100 - memoryPercent],
                    backgroundColor: ['#3498db', '#2c3e50']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${formatBytes(memoryUsage * 1024 * 1024)} of ${formatBytes(memoryLimit * 1024 * 1024)} (${memoryPercent.toFixed(1)}%)`;
                            }
                        }
                    }
                }
            }
        });
        
        // Set center text
        const memoryCenterText = document.getElementById('memoryCenterText');
        if (memoryCenterText) {
            memoryCenterText.innerHTML = `${memoryPercent.toFixed(1)}%`;
        }
    }
    
    // Disk Usage Chart
    const diskCanvas = document.getElementById('diskUsageChart');
    if (diskCanvas) {
        const diskUsage = parseFloat(diskCanvas.getAttribute('data-value')) || 0;
        const diskLimit = parseFloat(diskCanvas.getAttribute('data-limit')) || 100;
        const diskPercent = (diskUsage / diskLimit) * 100;
        
        new Chart(diskCanvas, {
            type: 'doughnut',
            data: {
                labels: ['Used', 'Available'],
                datasets: [{
                    data: [diskPercent, 100 - diskPercent],
                    backgroundColor: ['#e74c3c', '#2c3e50']
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `${formatBytes(diskUsage * 1024 * 1024)} of ${formatBytes(diskLimit *
                                1024 * 1024)} (${diskPercent.toFixed(1)}%)`;
                            }
                        }
                    }
                }
            }
        });
        
        // Set center text
        const diskCenterText = document.getElementById('diskCenterText');
        if (diskCenterText) {
            diskCenterText.innerHTML = `${diskPercent.toFixed(1)}%`;
        }
    }
}

/**
 * Fetch container stats and update the UI
 */
function fetchContainerStats() {
    fetch('/dashboard/stats')
        .then(response => response.json())
        .then(data => {
            // Update container stats
            const containers = data.container_stats;
            for (const [containerId, stats] of Object.entries(containers)) {
                updateContainerStats(containerId, stats);
            }
            
            // Update resource usage
            updateResourceUsage(data.resources);
        })
        .catch(error => {
            console.error('Error fetching container stats:', error);
        });
}

/**
 * Update container stats in the UI
 * @param {string} containerId - Container ID
 * @param {Object} stats - Container stats
 */
function updateContainerStats(containerId, stats) {
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
        
        // Update progress bar
        const cpuProgressBar = document.getElementById(`container-cpu-progress-${containerId}`);
        if (cpuProgressBar) {
            cpuProgressBar.style.width = `${stats.cpu_percent}%`;
        }
    }
    
    // Update memory usage
    const memoryElement = document.getElementById(`container-memory-${containerId}`);
    if (memoryElement) {
        memoryElement.innerHTML = formatBytes(stats.memory_used);
        
        // Update progress bar
        const memoryProgressBar = document.getElementById(`container-memory-progress-${containerId}`);
        const memoryPercent = (stats.memory_used / stats.memory_limit) * 100;
        if (memoryProgressBar) {
            memoryProgressBar.style.width = `${memoryPercent}%`;
        }
    }
}

/**
 * Update resource usage in the UI
 * @param {Object} resources - Resource usage data
 */
function updateResourceUsage(resources) {
    // Update CPU usage
    const cpuCanvas = document.getElementById('cpuUsageChart');
    const cpuCenterText = document.getElementById('cpuCenterText');
    if (cpuCanvas && resources.cpu) {
        const cpuUsage = resources.cpu.used;
        const cpuLimit = resources.cpu.limit;
        const cpuPercent = (cpuUsage / cpuLimit) * 100;
        
        const chart = Chart.getChart(cpuCanvas);
        if (chart) {
            chart.data.datasets[0].data = [cpuPercent, 100 - cpuPercent];
            chart.update();
        }
        
        if (cpuCenterText) {
            cpuCenterText.innerHTML = `${cpuPercent.toFixed(1)}%`;
        }
    }
    
    // Update memory usage
    const memoryCanvas = document.getElementById('memoryUsageChart');
    const memoryCenterText = document.getElementById('memoryCenterText');
    if (memoryCanvas && resources.memory) {
        const memoryUsage = resources.memory.used;
        const memoryLimit = resources.memory.limit;
        const memoryPercent = (memoryUsage / memoryLimit) * 100;
        
        const chart = Chart.getChart(memoryCanvas);
        if (chart) {
            chart.data.datasets[0].data = [memoryPercent, 100 - memoryPercent];
            chart.update();
        }
        
        if (memoryCenterText) {
            memoryCenterText.innerHTML = `${memoryPercent.toFixed(1)}%`;
        }
    }
    
    // Update disk usage
    const diskCanvas = document.getElementById('diskUsageChart');
    const diskCenterText = document.getElementById('diskCenterText');
    if (diskCanvas && resources.disk) {
        const diskUsage = resources.disk.used;
        const diskLimit = resources.disk.limit;
        const diskPercent = (diskUsage / diskLimit) * 100;
        
        const chart = Chart.getChart(diskCanvas);
        if (chart) {
            chart.data.datasets[0].data = [diskPercent, 100 - diskPercent];
            chart.update();
        }
        
        if (diskCenterText) {
            diskCenterText.innerHTML = `${diskPercent.toFixed(1)}%`;
        }
    }
}
