/**
 * SBPanel - Main JavaScript File
 * Contains common functions used across the application
 */

// Toggle sidebar collapse on mobile
document.addEventListener('DOMContentLoaded', function() {
    // Sidebar toggle
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            document.body.classList.toggle('sidebar-collapsed');
        });
    }

    // Add active class to current nav item
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');
    
    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        if (linkPath && (currentPath === linkPath || 
            (linkPath !== '/' && currentPath.startsWith(linkPath)))) {
            link.classList.add('active');
            // If inside a collapse, expand it
            const parentCollapse = link.closest('.collapse');
            if (parentCollapse) {
                parentCollapse.classList.add('show');
                const parentCollapseToggle = document.querySelector(`[data-bs-target="#${parentCollapse.id}"]`);
                if (parentCollapseToggle) {
                    parentCollapseToggle.classList.remove('collapsed');
                    parentCollapseToggle.setAttribute('aria-expanded', 'true');
                }
            }
        }
    });

    // Initialize tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Setup confirmation dialogs
    setupConfirmationDialogs();

    // Setup favorite functionality
    setupFavorites();
});

/**
 * Sets up confirmation dialogs for dangerous actions
 */
function setupConfirmationDialogs() {
    // Find all elements with data-confirm attribute
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    
    confirmButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            if (!confirm(this.getAttribute('data-confirm'))) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Sets up favorite functionality
 */
function setupFavorites() {
    const favoriteForm = document.getElementById('addFavoriteForm');
    if (favoriteForm) {
        const currentUrl = window.location.pathname;
        const pageTitle = document.title.split(' - ')[0]; // Get page title without the app name
        
        // Set form values
        document.getElementById('favoritePageUrl').value = currentUrl;
        document.getElementById('favoritePageName').value = pageTitle;
    }
}

/**
 * Shows an alert message
 * @param {string} message - The message to display
 * @param {string} type - The type of alert (success, danger, warning, info)
 */
function showAlert(message, type = 'info') {
    const alertsContainer = document.getElementById('alertsContainer');
    if (!alertsContainer) return;
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.role = 'alert';
    
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    alertsContainer.appendChild(alert);
    
    // Auto-dismiss after 5 seconds
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
    }, 5000);
}

/**
 * Copies text to clipboard
 * @param {string} text - The text to copy
 * @param {HTMLElement} button - The button that was clicked
 */
function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text).then(function() {
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fa fa-check"></i> Copied!';
        
        setTimeout(() => {
            button.innerHTML = originalText;
        }, 2000);
    }, function() {
        showAlert('Failed to copy text', 'danger');
    });
}

/**
 * Format bytes to human-readable format
 * @param {number} bytes - Bytes to format
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted size
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

/**
 * Load content via AJAX
 * @param {string} url - URL to load
 * @param {string} targetId - ID of the element to update
 * @param {Function} callback - Optional callback after content is loaded
 */
function loadContent(url, targetId, callback) {
    const target = document.getElementById(targetId);
    if (!target) return;
    
    // Show loading spinner
    target.innerHTML = '<div class="text-center p-5"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>';
    
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.text();
        })
        .then(html => {
            target.innerHTML = html;
            if (typeof callback === 'function') {
                callback();
            }
        })
        .catch(error => {
            target.innerHTML = `<div class="alert alert-danger">Error loading content: ${error.message}</div>`;
        });
}
