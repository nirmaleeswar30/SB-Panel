/**
 * SBPanel - Websites JavaScript
 * Handles website-specific functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation
    initFormValidation();
    
    // Setup PHP version toggle based on server type
    setupPhpToggle();
});

/**
 * Initialize form validation for website creation
 */
function initFormValidation() {
    const createWebsiteForm = document.getElementById('createWebsiteForm');
    if (createWebsiteForm) {
        createWebsiteForm.addEventListener('submit', function(event) {
            let isValid = true;
            
            // Domain validation
            const domainInput = document.getElementById('domain');
            if (!domainInput.value.trim() || !isValidDomain(domainInput.value.trim())) {
                domainInput.classList.add('is-invalid');
                isValid = false;
            }
            
            // Container validation
            const containerSelect = document.getElementById('container_id');
            if (!containerSelect.value) {
                containerSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // Server type validation
            const serverTypeSelect = document.getElementById('server_type');
            if (!serverTypeSelect.value) {
                serverTypeSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // PHP version validation if applicable
            const phpVersionSelect = document.getElementById('php_version');
            if (phpVersionSelect.parentElement.style.display !== 'none' && !phpVersionSelect.value) {
                phpVersionSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // Document root validation
            const documentRootInput = document.getElementById('document_root');
            if (!documentRootInput.value.trim() || !documentRootInput.value.startsWith('/')) {
                documentRootInput.classList.add('is-invalid');
                isValid = false;
            }
            
            if (!isValid) {
                event.preventDefault();
                return false;
            }
            
            return true;
        });
        
        // Clear validation errors on input
        const inputs = createWebsiteForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('is-invalid');
            });
        });
    }
}

/**
 * Validate domain name format
 * @param {string} domain - Domain name to validate
 * @returns {boolean} - Whether the domain is valid
 */
function isValidDomain(domain) {
    const pattern = /^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$/;
    return pattern.test(domain);
}

/**
 * Setup PHP version toggle based on server type
 */
function setupPhpToggle() {
    const serverTypeSelect = document.getElementById('server_type');
    const phpVersionGroup = document.getElementById('phpVersionGroup');
    
    if (serverTypeSelect && phpVersionGroup) {
        // Initial state
        togglePhpVisibility(serverTypeSelect.value);
        
        // Change event
        serverTypeSelect.addEventListener('change', function() {
            togglePhpVisibility(this.value);
        });
    }
}

/**
 * Toggle PHP version visibility based on server type
 * @param {string} serverType - Type of web server
 */
function togglePhpVisibility(serverType) {
    const phpVersionGroup = document.getElementById('phpVersionGroup');
    
    if (serverType === 'nginx' || serverType === 'apache') {
        phpVersionGroup.style.display = 'block';
    } else {
        phpVersionGroup.style.display = 'none';
    }
}

/**
 * Show creation modal with appropriate settings
 */
function showCreateWebsiteModal() {
    const modal = new bootstrap.Modal(document.getElementById('createWebsiteModal'));
    
    // Reset form
    const form = document.getElementById('createWebsiteForm');
    if (form) {
        form.reset();
        
        // Set default document root
        const documentRootInput = document.getElementById('document_root');
        if (documentRootInput) {
            documentRootInput.value = '/var/www/html';
        }
        
        // Reset validation states
        const inputs = form.querySelectorAll('.is-invalid');
        inputs.forEach(input => {
            input.classList.remove('is-invalid');
        });
        
        // Set initial PHP visibility
        const serverTypeSelect = document.getElementById('server_type');
        if (serverTypeSelect) {
            togglePhpVisibility(serverTypeSelect.value);
        }
    }
    
    modal.show();
}

/**
 * Show DNS management modal for a website
 * @param {number} websiteId - Website ID
 * @param {string} domain - Domain name
 */
function showDnsModal(websiteId, domain) {
    // Redirect to the DNS management page
    window.location.href = `/websites/${websiteId}/dns`;
}
