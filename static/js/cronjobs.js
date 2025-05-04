/**
 * SBPanel - Cron Jobs JavaScript
 * Handles cron job functionality
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation
    initFormValidation();
    
    // Initialize cron expression builder
    initCronBuilder();
});

/**
 * Initialize form validation for cron job creation
 */
function initFormValidation() {
    const createCronForm = document.getElementById('createCronForm');
    if (createCronForm) {
        createCronForm.addEventListener('submit', function(event) {
            let isValid = true;
            
            // Name validation
            const nameInput = document.getElementById('cron_name');
            if (!nameInput.value.trim()) {
                nameInput.classList.add('is-invalid');
                isValid = false;
            }
            
            // Container validation
            const containerSelect = document.getElementById('container_id');
            if (!containerSelect.value) {
                containerSelect.classList.add('is-invalid');
                isValid = false;
            }
            
            // Command validation
            const commandInput = document.getElementById('command');
            if (!commandInput.value.trim()) {
                commandInput.classList.add('is-invalid');
                isValid = false;
            }
            
            // Schedule validation
            const scheduleInput = document.getElementById('schedule');
            if (!scheduleInput.value.trim() || !isValidCronExpression(scheduleInput.value.trim())) {
                scheduleInput.classList.add('is-invalid');
                isValid = false;
            }
            
            if (!isValid) {
                event.preventDefault();
                return false;
            }
            
            return true;
        });
        
        // Clear validation errors on input
        const inputs = createCronForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            input.addEventListener('input', function() {
                this.classList.remove('is-invalid');
            });
        });
    }
}

/**
 * Initialize cron expression builder
 */
function initCronBuilder() {
    const minuteSelect = document.getElementById('cronMinute');
    const hourSelect = document.getElementById('cronHour');
    const daySelect = document.getElementById('cronDay');
    const monthSelect = document.getElementById('cronMonth');
    const weekdaySelect = document.getElementById('cronWeekday');
    const scheduleInput = document.getElementById('schedule');
    const buildButton = document.getElementById('buildCronButton');
    
    if (minuteSelect && hourSelect && daySelect && monthSelect && weekdaySelect && scheduleInput && buildButton) {
        // Populate minute options
        populateSelect(minuteSelect, [
            { value: '*', text: 'Every minute' },
            { value: '*/5', text: 'Every 5 minutes' },
            { value: '*/10', text: 'Every 10 minutes' },
            { value: '*/15', text: 'Every 15 minutes' },
            { value: '*/30', text: 'Every 30 minutes' },
            { value: '0', text: 'At the start of the hour' }
        ]);
        
        // Populate hour options
        populateSelect(hourSelect, [
            { value: '*', text: 'Every hour' },
            { value: '*/2', text: 'Every 2 hours' },
            { value: '*/6', text: 'Every 6 hours' },
            { value: '*/12', text: 'Every 12 hours' },
            { value: '0', text: 'At midnight' },
            { value: '12', text: 'At noon' }
        ]);
        
        // Populate day options
        populateSelect(daySelect, [
            { value: '*', text: 'Every day' },
            { value: '1', text: 'On the 1st' },
            { value: '15', text: 'On the 15th' },
            { value: '1,15', text: 'On the 1st and 15th' }
        ]);
        
        // Populate month options
        populateSelect(monthSelect, [
            { value: '*', text: 'Every month' },
            { value: '*/3', text: 'Every quarter' },
            { value: '*/6', text: 'Every half year' },
            { value: '1', text: 'January' },
            { value: '6', text: 'June' },
            { value: '12', text: 'December' }
        ]);
        
        // Populate weekday options
        populateSelect(weekdaySelect, [
            { value: '*', text: 'Every day of the week' },
            { value: '1-5', text: 'Weekdays' },
            { value: '0,6', text: 'Weekends' },
            { value: '1', text: 'Monday' },
            { value: '5', text: 'Friday' }
        ]);
        
        // Build cron expression
        buildButton.addEventListener('click', function() {
            const minute = minuteSelect.value;
            const hour = hourSelect.value;
            const day = daySelect.value;
            const month = monthSelect.value;
            const weekday = weekdaySelect.value;
            
            const cronExpression = `${minute} ${hour} ${day} ${month} ${weekday}`;
            scheduleInput.value = cronExpression;
            scheduleInput.classList.remove('is-invalid');
            
            // Display human-readable description
            const description = describeCronExpression(cronExpression);
            document.getElementById('cronDescription').textContent = description;
        });
    }
}

/**
 * Populate a select element with options
 * @param {HTMLSelectElement} select - Select element to populate
 * @param {Array} options - Array of options {value, text}
 */
function populateSelect(select, options) {
    options.forEach(option => {
        const optElement = document.createElement('option');
        optElement.value = option.value;
        optElement.textContent = option.text;
        select.appendChild(optElement);
    });
}

/**
 * Validate cron expression format
 * @param {string} expression - Cron expression to validate
 * @returns {boolean} - Whether the expression is valid
 */
function isValidCronExpression(expression) {
    // Simple validation, just check the format (5 space-separated fields)
    const parts = expression.trim().split(/\s+/);
    if (parts.length !== 5) {
        return false;
    }
    
    // In a real implementation, you would do more thorough validation
    return true;
}

/**
 * Generate a human-readable description of a cron expression
 * @param {string} expression - Cron expression
 * @returns {string} - Human-readable description
 */
function describeCronExpression(expression) {
    // This is a very simplified description generator
    // In a real implementation, you would use a more comprehensive parser
    
    const parts = expression.trim().split(/\s+/);
    if (parts.length !== 5) {
        return 'Invalid cron expression';
    }
    
    const [minute, hour, day, month, weekday] = parts;
    
    let description = 'Runs ';
    
    // Time of day
    if (minute === '*' && hour === '*') {
        description += 'every minute';
    } else if (minute === '0' && hour === '*') {
        description += 'at the start of every hour';
    } else if (minute === '0' && hour === '0') {
        description += 'at midnight';
    } else if (minute === '0' && hour === '12') {
        description += 'at noon';
    } else if (minute.startsWith('*/') && hour === '*') {
        const interval = minute.substring(2);
        description += `every ${interval} minutes`;
    } else if (minute === '0' && hour.startsWith('*/')) {
        const interval = hour.substring(2);
        description += `every ${interval} hours at the start of the hour`;
    } else {
        description += `at ${minute} minutes past hour ${hour}`;
    }
    
    // Day/month/weekday
    if (day === '*' && month === '*' && weekday === '*') {
        description += ', every day';
    } else if (day === '*' && month === '*' && weekday === '1-5') {
        description += ', Monday through Friday';
    } else if (day === '*' && month === '*' && weekday === '0,6') {
        description += ', on weekends';
    } else if (day !== '*' && month === '*' && weekday === '*') {
        description += `, on day ${day} of every month`;
    } else if (day === '*' && month !== '*' && weekday === '*') {
        description += `, every day in month ${month}`;
    } else {
        // Complex case, just show the expression
        description = `Runs according to the schedule: ${expression}`;
    }
    
    return description;
}

/**
 * Show creation modal with appropriate settings
 */
function showCreateCronModal() {
    const modal = new bootstrap.Modal(document.getElementById('createCronModal'));
    
    // Reset form
    const form = document.getElementById('createCronForm');
    if (form) {
        form.reset();
        
        // Reset validation states
        const inputs = form.querySelectorAll('.is-invalid');
        inputs.forEach(input => {
            input.classList.remove('is-invalid');
        });
        
        // Set initial cron expression description
        document.getElementById('cronDescription').textContent = '';
    }
    
    modal.show();
}
