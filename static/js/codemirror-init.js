/**
 * SBPanel - CodeMirror Initialization
 * Initializes CodeMirror instances for file editing
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeCodeMirror();
});

/**
 * Initialize CodeMirror for file editing
 */
function initializeCodeMirror() {
    const codeEditor = document.getElementById('codeEditor');
    if (!codeEditor) return;
    
    // Get file path to determine language mode
    const filePath = codeEditor.getAttribute('data-file-path');
    const mode = getEditorMode(filePath);
    
    // Initialize CodeMirror
    const editor = CodeMirror.fromTextArea(codeEditor, {
        lineNumbers: true,
        mode: mode,
        theme: 'dracula',
        indentUnit: 4,
        smartIndent: true,
        tabSize: 4,
        indentWithTabs: false,
        lineWrapping: true,
        extraKeys: {
            "Tab": function(cm) {
                if (cm.somethingSelected()) {
                    cm.indentSelection("add");
                } else {
                    cm.replaceSelection("    ", "end");
                }
            }
        }
    });
    
    // Set editor height
    editor.setSize(null, 500);
    
    // Save button handler
    const saveButton = document.getElementById('saveFileButton');
    if (saveButton) {
        saveButton.addEventListener('click', function() {
            const form = document.getElementById('editFileForm');
            // Update the textarea value with editor content
            editor.save();
            // Submit the form
            form.submit();
        });
    }
}

/**
 * Determine the appropriate CodeMirror mode for a file
 * @param {string} filePath - Path of the file being edited
 * @returns {string} - CodeMirror mode
 */
function getEditorMode(filePath) {
    // Get file extension
    const extension = filePath.split('.').pop().toLowerCase();
    
    // Map file extensions to CodeMirror modes
    const modeMap = {
        // Web
        'html': 'htmlmixed',
        'htm': 'htmlmixed',
        'css': 'css',
        'js': 'javascript',
        'json': 'javascript',
        
        // Server-side languages
        'php': 'php',
        'py': 'python',
        'rb': 'ruby',
        'pl': 'perl',
        'java': 'clike',
        'c': 'clike',
        'cpp': 'clike',
        'h': 'clike',
        'cs': 'clike',
        
        // Configuration
        'xml': 'xml',
        'conf': 'nginx',
        'ini': 'properties',
        'yml': 'yaml',
        'yaml': 'yaml',
        
        // Shell
        'sh': 'shell',
        'bash': 'shell',
        
        // Other
        'md': 'markdown',
        'sql': 'sql'
    };
    
    return modeMap[extension] || 'plaintext';
}
