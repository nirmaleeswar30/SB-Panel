/**
 * SBPanel - Files JavaScript
 * Handles file management functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Set up file browser navigation
    setupFileBrowserNavigation();
    
    // Setup file upload progress
    setupFileUpload();
    
    // Setup directory creation validation
    setupMkdirValidation();
    
    // Setup URL download validation
    setupUrlDownloadValidation();
});

/**
 * Setup file browser navigation
 */
function setupFileBrowserNavigation() {
    // Handle directory clicks
    const dirLinks = document.querySelectorAll('.dir-link');
    dirLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const path = this.getAttribute('data-path');
            const containerId = getContainerId();
            
            // Navigate to the directory
            window.location.href = `/files/?container_id=${containerId}&path=${encodeURIComponent(path)}`;
        });
    });
    
    // Handle breadcrumb navigation
    const breadcrumbLinks = document.querySelectorAll('.breadcrumb-item a');
    breadcrumbLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const path = this.getAttribute('data-path');
            const containerId = getContainerId();
            
            // Navigate to the directory
            window.location.href = `/files/?container_id=${containerId}&path=${encodeURIComponent(path)}`;
        });
    });
    
    // Handle container change
    const containerSelect = document.getElementById('containerSelect');
    if (containerSelect) {
        containerSelect.addEventListener('change', function() {
            const containerId = this.value;
            window.location.href = `/files/?container_id=${containerId}&path=/`;
        });
    }
}

/**
 * Get the current container ID
 * @returns {string} - Container ID
 */
function getContainerId() {
    const containerSelect = document.getElementById('containerSelect');
    return containerSelect ? containerSelect.value : '';
}

/**
 * Setup file upload progress
 */
function setupFileUpload() {
    const fileUploadForm = document.getElementById('fileUploadForm');
    const fileInput = document.getElementById('fileInput');
    const progressBar = document.getElementById('uploadProgressBar');
    const progressContainer = document.getElementById('uploadProgressContainer');
    
    if (fileUploadForm && fileInput && progressBar && progressContainer) {
        fileInput.addEventListener('change', function() {
            // Show file name in input group
            const fileLabel = document.getElementById('fileInputLabel');
            if (fileLabel) {
                fileLabel.textContent = this.files[0] ? this.files[0].name : 'Choose file';
            }
        });
        
        fileUploadForm.addEventListener('submit', function() {
            if (fileInput.files.length === 0) {
                alert('Please select a file to upload.');
                return false;
            }
            
            // Show progress
            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            
            // In a real implementation, you would use FormData and XMLHttpRequest to track upload progress
            // For simplicity, we'll just simulate progress here
            simulateProgress();
            
            return true;
        });
    }
}

/**
 * Simulate upload progress (for demonstration)
 * In a real implementation, you would use XMLHttpRequest's progress event
 */
function simulateProgress() {
    const progressBar = document.getElementById('uploadProgressBar');
    let progress = 0;
    
    const interval = setInterval(function() {
        progress += 10;
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
        
        if (progress >= 100) {
            clearInterval(interval);
        }
    }, 200);
}

/**
 * Setup directory creation validation
 */
function setupMkdirValidation() {
    const mkdirForm = document.getElementById('mkdirForm');
    const dirNameInput = document.getElementById('dir_name');
    
    if (mkdirForm && dirNameInput) {
        mkdirForm.addEventListener('submit', function(e) {
            if (!dirNameInput.value.trim()) {
                e.preventDefault();
                dirNameInput.classList.add('is-invalid');
                return false;
            }
            
            // Check for invalid characters
            const invalidChars = /[<>:"|?*]/;
            if (invalidChars.test(dirNameInput.value)) {
                e.preventDefault();
                dirNameInput.classList.add('is-invalid');
                alert('Directory name contains invalid characters. Avoid using: < > : " | ? *');
                return false;
            }
            
            return true;
        });
        
        dirNameInput.addEventListener('input', function() {
            this.classList.remove('is-invalid');
        });
    }
}

/**
 * Setup URL download validation
 */
function setupUrlDownloadValidation() {
    const urlDownloadForm = document.getElementById('urlDownloadForm');
    const urlInput = document.getElementById('url');
    
    if (urlDownloadForm && urlInput) {
        urlDownloadForm.addEventListener('submit', function(e) {
            if (!urlInput.value.trim()) {
                e.preventDefault();
                urlInput.classList.add('is-invalid');
                return false;
            }
            
            // Check if it's a valid URL
            try {
                new URL(urlInput.value);
            } catch (error) {
                e.preventDefault();
                urlInput.classList.add('is-invalid');
                alert('Please enter a valid URL');
                return false;
            }
            
            return true;
        });
        
        urlInput.addEventListener('input', function() {
            this.classList.remove('is-invalid');
        });
    }
}

/**
 * Show file actions dropdown
 * @param {Element} button - Button element
 * @param {string} filePath - File path
 * @param {string} fileName - File name
 * @param {boolean} isDir - Whether it's a directory
 */
function showFileActions(button, filePath, fileName, isDir) {
    // Get container ID
    const containerId = getContainerId();
    
    // Get or create dropdown menu
    let dropdown = document.getElementById('fileActionsDropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'fileActionsDropdown';
        dropdown.className = 'dropdown-menu';
        document.body.appendChild(dropdown);
    }
    
    // Generate dropdown content based on file type
    let content = '';
    
    if (isDir) {
        // Directory actions
        content = `
            <a class="dropdown-item" href="/files/?container_id=${containerId}&path=${encodeURIComponent(filePath)}">
                <i class="fa fa-folder-open"></i> Open
            </a>
            <div class="dropdown-divider"></div>
            <form action="/files/delete" method="post" class="dropdown-item-form">
                <input type="hidden" name="container_id" value="${containerId}">
                <input type="hidden" name="file_path" value="${filePath}">
                <button type="submit" class="dropdown-item text-danger" data-confirm="Are you sure you want to delete the directory '${fileName}'? This will delete all contents!">
                    <i class="fa fa-trash"></i> Delete
                </button>
            </form>
        `;
    } else {
        // File extension
        const extension = fileName.split('.').pop().toLowerCase();
        const isText = ['txt', 'html', 'css', 'js', 'php', 'py', 'json', 'xml', 'md', 'sh', 'ini', 'conf', 'cfg'].includes(extension);
        
        // File actions
        content = `
            <a class="dropdown-item" href="/files/download?container_id=${containerId}&path=${encodeURIComponent(filePath)}">
                <i class="fa fa-download"></i> Download
            </a>
        `;
        
        // Add edit option for text files
        if (isText) {
            content += `
                <a class="dropdown-item" href="/files/view?container_id=${containerId}&path=${encodeURIComponent(filePath)}">
                    <i class="fa fa-edit"></i> Edit
                </a>
            `;
        }
        
        content += `
            <div class="dropdown-divider"></div>
            <form action="/files/delete" method="post" class="dropdown-item-form">
                <input type="hidden" name="container_id" value="${containerId}">
                <input type="hidden" name="file_path" value="${filePath}">
                <button type="submit" class="dropdown-item text-danger" data-confirm="Are you sure you want to delete the file '${fileName}'?">
                    <i class="fa fa-trash"></i> Delete
                </button>
            </form>
        `;
    }
    
    // Update dropdown content
    dropdown.innerHTML = content;
    
    // Position dropdown
    const rect = button.getBoundingClientRect();
    dropdown.style.top = (rect.bottom + window.scrollY) + 'px';
    dropdown.style.left = (rect.left + window.scrollX) + 'px';
    dropdown.style.display = 'block';
    
    // Setup confirmation dialogs for delete actions
    setupConfirmationDialogs();
    
    // Hide dropdown when clicking outside
    document.addEventListener('click', function hideDropdown(e) {
        if (!dropdown.contains(e.target) && e.target !== button) {
            dropdown.style.display = 'none';
            document.removeEventListener('click', hideDropdown);
        }
    });
}

/**
 * Show modal for creating a directory
 */
function showMkdirModal() {
    const modal = new bootstrap.Modal(document.getElementById('mkdirModal'));
    
    // Reset form
    const form = document.getElementById('mkdirForm');
    if (form) {
        form.reset();
    }
    
    modal.show();
}

/**
 * Show modal for downloading from URL
 */
function showUrlDownloadModal() {
    const modal = new bootstrap.Modal(document.getElementById('urlDownloadModal'));
    
    // Reset form
    const form = document.getElementById('urlDownloadForm');
    if (form) {
        form.reset();
    }
    
    modal.show();
}
