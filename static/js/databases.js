/**
 * SBPanel - Databases JavaScript
 * Handles database-specific functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation
    initFormValidation();
    
    // Setup password generation
    setupPasswordGeneration();
});

/**
 * Initialize form validation for database creation
 */
function initFormValidation() {
    const createDatabaseForm = document.getElementById('createDatabaseForm');
    if (createDatabaseForm) {
        createDatabaseForm.addEventListener('submit', function(event) {
            let isValid = true;
            
            // Database name validation
            const nameInput = document.getElementById('db_name');
            if (!nameInput.value.trim() || !isValidDatabaseName(nameInput.value.trim())) {
                nameInput.classList.add('is-invalid');
                isValid = false;
            }
            
            // Container validation
            const containerSelect = document.getElementById('container_id');
            if (!containerSelect.value) {
                containerSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // Database type validation
            const dbTypeSelect = document.getElementById('db_type');
            if (!dbTypeSelect.value) {
                dbTypeSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // Username validation
            const userInput = document.getElementById('db_user');
            if (!userInput.value.trim() || !isValidDatabaseUsername(userInput.value.trim())) {
                userInput.classList.add('is-invalid');
                isValid = false;
            }
            
            // Password validation (if not auto-generated)
            const passwordInput = document.getElementById('db_password');
            const autoGenerateCheckbox = document.getElementById('auto_generate_password');
            
            if (!autoGenerateCheckbox.checked && (!passwordInput.value || passwordInput.value.length < 8)) {
                passwordInput.classList.add('is-invalid');
                isValid = false;
            }
            
            if (!isValid) {
                event.preventDefault();
                return false;
            }
            
            return true;
        });
        
        // Clear validation errors on input
        const inputs = createDatabaseForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('is-invalid');
            });
        });
    }
}

/**
 * Validate database name format
 * @param {string} name - Database name to validate
 * @returns {boolean} - Whether the name is valid
 */
function isValidDatabaseName(name) {
    // Alphanumeric and underscore only, must start with a letter
    const pattern = /^[a-zA-Z][a-zA-Z0-9_]*$/;
    return pattern.test(name);
}

/**
 * Validate database username format
 * @param {string} username - Username to validate
 * @returns {boolean} - Whether the username is valid
 */
function isValidDatabaseUsername(username) {
    // Alphanumeric and underscore only, must start with a letter
    const pattern = /^[a-zA-Z][a-zA-Z0-9_]*$/;
    return pattern.test(username);
}

/**
 * Setup password generation functionality
 */
function setupPasswordGeneration() {
    const autoGenerateCheckbox = document.getElementById('auto_generate_password');
    const passwordInput = document.getElementById('db_password');
    const passwordGroup = document.getElementById('passwordInputGroup');
    
    if (autoGenerateCheckbox && passwordInput && passwordGroup) {
        // Initial state
        togglePasswordVisibility(autoGenerateCheckbox.checked);
        
        // Change event
        autoGenerateCheckbox.addEventListener('change', function() {
            togglePasswordVisibility(this.checked);
        });
    }
    
    // Generate password button
    const generatePasswordBtn = document.getElementById('generatePasswordBtn');
    if (generatePasswordBtn && passwordInput) {
        generatePasswordBtn.addEventListener('click', function() {
            passwordInput.value = generateRandomPassword();
            passwordInput.classList.remove('is-invalid');
        });
    }
}

/**
 * Toggle password input visibility
 * @param {boolean} autoGenerate - Whether to auto-generate the password
 */
function togglePasswordVisibility(autoGenerate) {
    const passwordGroup = document.getElementById('passwordInputGroup');
    
    if (autoGenerate) {
        passwordGroup.style.display = 'none';
    } else {
        passwordGroup.style.display = 'flex';
    }
}

/**
 * Generate a random secure password
 * @param {number} length - Password length
 * @returns {string} - Generated password
 */
function generateRandomPassword(length = 16) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()_+';
    let password = '';
    
    for (let i = 0; i < length; i++) {
        const randomIndex = Math.floor(Math.random() * chars.length);
        password += chars.charAt(randomIndex);
    }
    
    return password;
}

/**
 * Show creation modal with appropriate settings
 */
function showCreateDatabaseModal() {
    const modal = new bootstrap.Modal(document.getElementById('createDatabaseModal'));
    
    // Reset form
    const form = document.getElementById('createDatabaseForm');
    if (form) {
        form.reset();
        
        // Reset validation states
        const inputs = form.querySelectorAll('.is-invalid');
        inputs.forEach(input => {
            input.classList.remove('is-invalid');
        });
        
        // Check auto-generate password by default
        const autoGenerateCheckbox = document.getElementById('auto_generate_password');
        if (autoGenerateCheckbox) {
            autoGenerateCheckbox.checked = true;
            togglePasswordVisibility(true);
        }
    }
    
    modal.show();
}

/**
 * Toggle visibility of database password
 * @param {string} dbId - Database ID
 */
function togglePasswordVisibility(dbId) {
    const passwordField = document.getElementById(`db-password-${dbId}`);
    const toggleButton = document.getElementById(`toggle-password-${dbId}`);
    
    if (passwordField && toggleButton) {
        if (passwordField.type === 'password') {
            passwordField.type = 'text';
            toggleButton.innerHTML = '<i class="fa fa-eye-slash"></i>';
            toggleButton.setAttribute('title', 'Hide Password');
        } else {
            passwordField.type = 'password';
            toggleButton.innerHTML = '<i class="fa fa-eye"></i>';
            toggleButton.setAttribute('title', 'Show Password');
        }
    }
}
