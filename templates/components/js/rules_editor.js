// state management
let activeTab = 'aml-rules';

const API_ENDPOINTS = {
    'aml-rules': '/api/rules/aml-rules',
    'glossary-codes': '/api/rules/glossary-codes',
    'legal-snippets': '/api/rules/legal-snippets'
};

const TAB_METADATA = {
    'aml-rules': {
        title: 'AML Rules Configuration',
        desc: 'Configure the core triggers and evidence requirements for the AML investigation agent.'
    },
    'glossary-codes': {
        title: 'Glossary Codes Matrix',
        desc: 'Define the NCA UKFIU glossary codes and conditional secondary reporting triggers.'
    },
    'legal-snippets': {
        title: 'Legal Snippets Configuration',
        desc: 'Organize specific regulatory frameworks, Acts, and FATF Recommendations used by the LLM.'
    }
};

// DOM Nodes
const tabs = document.querySelectorAll('.tab-btn');
const editorTitle = document.getElementById('editor-title');
const editorDesc = document.getElementById('editor-desc');
const jsonEditor = document.getElementById('json-editor');
const btnFormat = document.getElementById('btn-format');
const btnSave = document.getElementById('btn-save');
const spinner = document.getElementById('loading-spinner');

// Setup Tabs
tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
        const target = tab.getAttribute('data-target');
        if (target === activeTab) return;
        
        activeTab = target;
        updateTabUI();
        loadConfigData();
    });
});

function updateTabUI() {
    tabs.forEach(tab => {
        const target = tab.getAttribute('data-target');
        if (target === activeTab) {
            tab.className = 'tab-btn w-full text-left px-4 py-3 rounded text-sm font-medium transition-colors bg-blue-50 text-blue-700 border border-blue-200';
            tab.querySelector('.text-xs').className = 'text-xs text-blue-600/80 font-normal';
        } else {
            tab.className = 'tab-btn w-full text-left px-4 py-3 rounded text-sm font-medium transition-colors hover:bg-slate-100 text-slate-600 border border-transparent';
            tab.querySelector('.text-xs').className = 'text-xs text-slate-500 font-normal';
        }
    });

    const meta = TAB_METADATA[activeTab];
    editorTitle.textContent = meta.title;
    editorDesc.textContent = meta.desc;
}

// Data Fetching
async function loadConfigData() {
    try {
        spinner.classList.remove('hidden');
        jsonEditor.disabled = true;
        jsonEditor.style.opacity = '0.5';
        
        const response = await fetch(API_ENDPOINTS[activeTab]);
        if (!response.ok) throw new Error('Network error loading configuration');
        
        const data = await response.json();
        const formatted = JSON.stringify(data, null, 2);
        
        // Remove text styling overrides during parsing
        jsonEditor.style.color = '#e2e8f0'; // slate-200 for dark bg visibility
        jsonEditor.value = formatted;
        
    } catch (err) {
        showToast('Error', 'Failed to load configuration data.', 'error');
        console.error(err);
        jsonEditor.value = "Error loading data.";
    } finally {
        spinner.classList.add('hidden');
        jsonEditor.disabled = false;
        jsonEditor.style.opacity = '1';
    }
}

// Initial Load
document.addEventListener('DOMContentLoaded', () => {
    jsonEditor.style.color = '#e2e8f0'; // ensure good contrast against dark background
    loadConfigData();
});

// Format action
btnFormat.addEventListener('click', () => {
    try {
        const parsed = JSON.parse(jsonEditor.value);
        jsonEditor.value = JSON.stringify(parsed, null, 2);
        showToast('Success', 'JSON formatted successfully!', 'success');
    } catch (err) {
        showToast('Syntax Error', 'Invalid JSON format. Cannot format.', 'error');
    }
});

// Save action
btnSave.addEventListener('click', async () => {
    const originalText = btnSave.innerHTML;
    try {
        // 1. Validate JSON
        const rawText = jsonEditor.value;
        const payload = JSON.parse(rawText);

        // 2. Loading UI
        btnSave.disabled = true;
        btnSave.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Saving...
        `;

        // 3. PUT Request
        const response = await fetch(API_ENDPOINTS[activeTab], {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('API request failed');

        const result = await response.json();
        
        // Formatically re-format text
        jsonEditor.value = JSON.stringify(payload, null, 2);
        showToast('Saved', result.message || 'Config stored in active memory.', 'success');

    } catch (err) {
        if (err instanceof SyntaxError) {
            showToast('Syntax Error', 'Invalid JSON payload. Check for missing commas or quotes.', 'error');
        } else {
            showToast('API Error', 'Failed to update backend configuration.', 'error');
        }
        console.error(err);
    } finally {
        btnSave.innerHTML = originalText;
        btnSave.disabled = false;
    }
});

/* Toast Notification System */
let toastTimeout;
function showToast(title, message, type = 'success') {
    const toastElem = document.getElementById('toast');
    const toastTitle = document.getElementById('toast-title');
    const toastMsg = document.getElementById('toast-msg');
    const toastIcon = document.getElementById('toast-icon');

    // Reset classes
    toastElem.className = 'fixed bottom-6 right-6 transform transition-all duration-300 z-50 flex items-start gap-4 px-5 py-4 rounded shadow-xl min-w-[320px] max-w-sm';
    
    // Style configurations based on type
    if (type === 'success') {
        toastElem.classList.add('bg-green-800', 'text-white', 'border', 'border-green-700');
        toastTitle.classList.add('text-green-50');
        toastMsg.classList.add('text-green-100');
        toastIcon.innerHTML = `
            <svg class="w-6 h-6 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        `;
    } else if (type === 'error') {
        toastElem.classList.add('bg-red-800', 'text-white', 'border', 'border-red-700');
        toastTitle.classList.add('text-red-50');
        toastMsg.classList.add('text-red-100');
        toastIcon.innerHTML = `
            <svg class="w-6 h-6 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        `;
    }

    // Set Text
    toastTitle.textContent = title;
    toastMsg.textContent = message;

    // Show animation
    toastElem.classList.remove('translate-y-20', 'opacity-0');
    toastElem.classList.add('translate-y-0', 'opacity-100');

    // Hide animation after 4 seconds
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toastElem.classList.remove('translate-y-0', 'opacity-100');
        toastElem.classList.add('translate-y-20', 'opacity-0');
    }, 4000);
}
