// State and Metadata
window.appState = {};
let activeTab = 'aml-rules';
let hasUnsavedChanges = false;
let pendingTabSwitch = null;

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
const formContainer = document.getElementById('form-container');
const btnSave = document.getElementById('btn-save');
const spinner = document.getElementById('loading-spinner');
const unsavedModal = document.getElementById('unsaved-modal');

// Mark state as dirty
function markDirty() {
    hasUnsavedChanges = true;
    btnSave.classList.add('ring-2', 'ring-blue-300', 'ring-offset-2');
}

function clearDirty() {
    hasUnsavedChanges = false;
    btnSave.classList.remove('ring-2', 'ring-blue-300', 'ring-offset-2');
}

// Escaping logic
function escapeHtml(unsafe) {
    if (!unsafe) return "";
    return unsafe
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}

// Tab Switching & Unsaved Check
tabs.forEach(tab => {
    tab.addEventListener('click', (e) => {
        const target = tab.getAttribute('data-target');
        if (target === activeTab) return;
        
        if (hasUnsavedChanges) {
            pendingTabSwitch = target;
            unsavedModal.classList.remove('hidden');
        } else {
            switchTab(target);
        }
    });
});

document.getElementById('btn-cancel-switch').addEventListener('click', () => {
    unsavedModal.classList.add('hidden');
    pendingTabSwitch = null;
});

document.getElementById('btn-confirm-switch').addEventListener('click', () => {
    unsavedModal.classList.add('hidden');
    hasUnsavedChanges = false; // Discard
    clearDirty();
    switchTab(pendingTabSwitch);
});

function switchTab(target) {
    activeTab = target;
    
    tabs.forEach(tab => {
        if (tab.getAttribute('data-target') === activeTab) {
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
    
    loadConfigData();
}

// Data Fetching
async function loadConfigData() {
    try {
        spinner.classList.remove('hidden');
        formContainer.innerHTML = ''; // clear previous
        
        const response = await fetch(API_ENDPOINTS[activeTab]);
        if (!response.ok) throw new Error('Network error loading configuration');
        
        window.appState = await response.json();
        clearDirty();

        if (activeTab === 'aml-rules') renderAmlRulesForm();
        else if (activeTab === 'legal-snippets') renderLegalSnippetsForm();
        else if (activeTab === 'glossary-codes') renderGlossaryCodesForm();
        
    } catch (err) {
        showToast('Error', 'Failed to load configuration data.', 'error');
        console.error(err);
        formContainer.innerHTML = `<div class="p-4 bg-red-50 text-red-700 rounded border border-red-200">Error loading data.</div>`;
    } finally {
        spinner.classList.add('hidden');
    }
}

// ----------------------------------------------------
// FORM RENDERERS
// ----------------------------------------------------

// Render Tab 1: AML Rules
function renderAmlRulesForm() {
    let html = '';
    const rulesDef = window.appState.aml_rules_def || {};
    const evRulesDef = window.appState.evidence_rules_def || {};
    
    // Get unique rule IDs from both dicts securely
    const allRuleIds = Array.from(new Set([...Object.keys(rulesDef), ...Object.keys(evRulesDef)])).sort();

    allRuleIds.forEach((ruleId) => {
        html += `
        <div class="bg-white border text-sm border-slate-200 rounded-md shadow-sm overflow-hidden rule-card" data-rule="${escapeHtml(ruleId)}">
            <div class="px-5 py-3 bg-slate-50 border-b border-slate-200 font-bold text-slate-700 tracking-wide flex justify-between items-center">
                <span>${escapeHtml(ruleId)}</span>
                <button type="button" onclick="deleteAmlRule('${escapeHtml(ruleId)}')" class="text-slate-400 hover:text-red-500 transition-colors" title="Delete Rule">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
            <div class="p-5 flex flex-col gap-4">
                <div>
                    <label class="block text-[11px] uppercase tracking-wider font-semibold text-slate-500 mb-2">AML Rule Definition</label>
                    <textarea 
                        class="w-full p-3 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow text-sm text-slate-700" 
                        oninput="updateAmlRule('${escapeHtml(ruleId)}', 'aml', this.value)"
                        rows="4" spellcheck="false">${escapeHtml(rulesDef[ruleId] || '')}</textarea>
                </div>
                <div>
                    <label class="block text-[11px] uppercase tracking-wider font-semibold text-slate-500 mb-2">Evidence Requirements</label>
                    <textarea 
                        class="w-full p-3 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow text-sm text-slate-700" 
                        oninput="updateAmlRule('${escapeHtml(ruleId)}', 'evidence', this.value)"
                        rows="4" spellcheck="false">${escapeHtml(evRulesDef[ruleId] || '')}</textarea>
                </div>
            </div>
        </div>`;
    });

    html += `
        <button onclick="addNewAmlRule()" class="mt-2 w-full border-2 border-dashed border-slate-300 text-slate-500 font-medium py-3 rounded-md hover:bg-slate-50 hover:text-slate-700 hover:border-slate-400 transition-colors">
            + Add New Rule
        </button>
    `;
    formContainer.innerHTML = html;
}

window.updateAmlRule = function(ruleId, type, val) {
    if (!window.appState.aml_rules_def) window.appState.aml_rules_def = {};
    if (!window.appState.evidence_rules_def) window.appState.evidence_rules_def = {};
    
    if (type === 'aml') window.appState.aml_rules_def[ruleId] = val;
    if (type === 'evidence') window.appState.evidence_rules_def[ruleId] = val;
    
    markDirty();
};

window.addNewAmlRule = function() {
    const newId = prompt("Enter new Rule ID (e.g. RULE-09):");
    if (!newId || newId.trim() === '') return;
    const ruleId = newId.trim();
    if (window.appState.aml_rules_def[ruleId]) {
        alert("Rule already exists!");
        return;
    }
    window.appState.aml_rules_def[ruleId] = "";
    window.appState.evidence_rules_def[ruleId] = "";
    markDirty();
    renderAmlRulesForm();
    // Scroll to bottom
    setTimeout(() => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }, 100);
};

// Render Tab 2: Legal Snippets
function renderLegalSnippetsForm() {
    let html = '';
    const snippets = window.appState.rule_specific_snippets || {};
    const rulesIds = Object.keys(snippets).sort();

    rulesIds.forEach(ruleId => {
        // Snippets are arrays of strings. Join by newline for text box.
        const valStr = (snippets[ruleId] || []).join('\n\n');
        
        html += `
        <div class="bg-white border text-sm border-slate-200 rounded-md shadow-sm overflow-hidden data-card">
            <div class="px-5 py-3 bg-slate-50 border-b border-slate-200 font-bold text-slate-700 tracking-wide flex justify-between items-center">
                <span>${escapeHtml(ruleId)}</span>
                <button type="button" onclick="deleteLegalSnippet('${escapeHtml(ruleId)}')" class="text-slate-400 hover:text-red-500 transition-colors" title="Delete Snippet">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
            <div class="p-5">
                <label class="block text-[11px] uppercase tracking-wider font-semibold text-slate-500 mb-2">Statutory Legal Boilerplate</label>
                <textarea 
                    class="w-full p-3 border border-slate-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-shadow text-sm text-slate-700" 
                    oninput="updateLegalSnippet('${escapeHtml(ruleId)}', this.value)"
                    rows="6" spellcheck="false">${escapeHtml(valStr)}</textarea>
                <p class="text-xs text-slate-400 mt-2">Separate separate acts or recommendations with a double newline.</p>
            </div>
        </div>`;
    });

    html += `
        <button onclick="addNewLegalSnippet()" class="mt-2 w-full border-2 border-dashed border-slate-300 text-slate-500 font-medium py-3 rounded-md hover:bg-slate-50 hover:text-slate-700 hover:border-slate-400 transition-colors">
            + Add Legal Snippet
        </button>
    `;
    formContainer.innerHTML = html;
}

window.updateLegalSnippet = function(ruleId, val) {
    if (!window.appState.rule_specific_snippets) window.appState.rule_specific_snippets = {};
    // Split on double newline to retain array schema
    const arr = val.split('\n\n').map(s => s.trim()).filter(s => s !== '');
    window.appState.rule_specific_snippets[ruleId] = arr;
    markDirty();
};

window.addNewLegalSnippet = function() {
    const newId = prompt("Enter new Rule ID (e.g. RULE-09):");
    if (!newId || newId.trim() === '') return;
    const ruleId = newId.trim();
    if (window.appState.rule_specific_snippets[ruleId]) {
        alert("Rule already exists!");
        return;
    }
    window.appState.rule_specific_snippets[ruleId] = [];
    markDirty();
    renderLegalSnippetsForm();
};

// Render Tab 3: Glossary Codes
function renderGlossaryCodesForm() {
    const matrix = window.appState.rules_to_codes_matrix || [];
    const conditionRules = window.appState.conditional_code_decision_rules || {};
    
    // --- SECTION A: The Matrix ---
    let html = `
    <div class="mb-4">
        <h3 class="text-lg font-bold text-slate-800 tracking-tight">Rules vs Codes Matrix</h3>
        <p class="text-xs text-slate-500 mt-1">Map which glossary codes can be applied when an AML rule is triggered.</p>
    </div>
    
    <div class="overflow-x-auto bg-white border border-slate-200 rounded-md shadow-sm mb-10">
        <table class="w-full text-sm text-left align-middle text-slate-700">
            <thead class="text-xs text-slate-500 uppercase bg-slate-50 border-b border-slate-200">
                <tr>
                    <th class="px-4 py-3 min-w-[100px]">Rule ID</th>
                    <th class="px-4 py-3 min-w-[180px]">Title</th>
                    <th class="px-4 py-3 min-w-[250px]">Primary Codes</th>
                    <th class="px-4 py-3 min-w-[250px]">Conditional Codes</th>
                </tr>
            </thead>
            <tbody>
    `;

    matrix.forEach((row, i) => {
        html += `
            <tr class="border-b border-slate-100 hover:bg-slate-50/50">
                <td class="px-4 py-3 font-semibold text-slate-800">
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="deleteMatrixRow(${i})" class="text-slate-400 hover:text-red-500 transition-colors" title="Delete Matrix Row">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                        </button>
                        <span>${escapeHtml(row.rule_id)}</span>
                    </div>
                </td>
                <td class="px-4 py-3"><input type="text" class="w-full text-sm p-2 border border-slate-300 rounded outline-none focus:ring-2 focus:ring-blue-500" value="${escapeHtml(row.title)}" oninput="updateMatrixRow(${i}, 'title', this.value)"></td>
                <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1 mb-2" id="tags-primary-${i}">
                        ${row.primary_codes.map(c => renderPill(c, i, 'primary')).join('')}
                    </div>
                    <input type="text" placeholder="Add code & press Enter" class="w-full text-xs p-1.5 border border-slate-200 rounded outline-none focus:ring-1 focus:ring-blue-400" onkeydown="handleTagInput(event, ${i}, 'primary')">
                </td>
                <td class="px-4 py-3">
                    <div class="flex flex-wrap gap-1 mb-2" id="tags-conditional-${i}">
                        ${row.conditional_codes.map(c => renderPill(c, i, 'conditional')).join('')}
                    </div>
                    <input type="text" placeholder="Add code & press Enter" class="w-full text-xs p-1.5 border border-slate-200 rounded outline-none focus:ring-1 focus:ring-blue-400" onkeydown="handleTagInput(event, ${i}, 'conditional')">
                </td>
            </tr>
        `;
    });

    html += `
            </tbody>
        </table>
        <button onclick="addNewMatrixRow()" class="mt-4 w-full border-2 border-dashed border-slate-300 text-slate-500 font-medium py-3 rounded-md hover:bg-slate-50 hover:text-slate-700 hover:border-slate-400 transition-colors">
            + Add Matrix Row
        </button>
    </div>
    
    <div class="mb-4">
        <h3 class="text-lg font-bold text-slate-800 tracking-tight">Code Definitions</h3>
        <p class="text-xs text-slate-500 mt-1">Definitions used by the LLM logic to decide if a conditional code applies.</p>
    </div>
    
    <div class="flex flex-col gap-3">
    `;

    // --- SECTION B: Code Definitions ---
    const codeKeys = Object.keys(conditionRules).sort();
    codeKeys.forEach(code => {
        html += `
        <div class="flex gap-4 items-start bg-white p-3 border border-slate-200 rounded-md shadow-sm">
            <div class="flex flex-col gap-2">
                <input type="text" class="w-28 text-sm p-2 border border-slate-200 bg-slate-100 rounded text-slate-600 font-semibold text-center select-none" value="${escapeHtml(code)}" disabled border-none>
                <button type="button" onclick="deleteConditionCode('${escapeHtml(code)}')" class="text-slate-400 hover:text-red-500 transition-colors mx-auto" title="Delete Definition">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
                </button>
            </div>
            <textarea class="flex-1 text-sm p-2 border border-slate-300 rounded outline-none focus:ring-2 focus:ring-blue-500" rows="2" oninput="updateConditionCode('${escapeHtml(code)}', this.value)">${escapeHtml(conditionRules[code])}</textarea>
        </div>
        `;
    });

    html += `
        <button onclick="addNewConditionCodeDef()" class="mt-2 w-full border-2 border-dashed border-slate-300 text-slate-500 font-medium py-3 rounded-md hover:bg-slate-50 hover:text-slate-700 hover:border-slate-400 transition-colors">
            + Add Code Definition
        </button>
    </div>`;
    formContainer.innerHTML = html;
}

function renderPill(code, idx, type) {
    return `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
        ${escapeHtml(code)}
        <button type="button" class="hover:text-blue-500 font-bold focus:outline-none" onclick="removeTag(${idx}, '${type}', '${escapeHtml(code)}')">×</button>
    </span>`;
}

window.updateMatrixRow = function(idx, field, val) {
    if (window.appState.rules_to_codes_matrix && window.appState.rules_to_codes_matrix[idx]) {
        window.appState.rules_to_codes_matrix[idx][field] = val;
        markDirty();
    }
}

window.handleTagInput = function(e, idx, type) {
    if (e.key === 'Enter') {
        e.preventDefault();
        const val = e.target.value.trim().toUpperCase();
        if (!val) return;
        
        const targetArr = type === 'primary' ? 'primary_codes' : 'conditional_codes';
        const arr = window.appState.rules_to_codes_matrix[idx][targetArr];
        
        if (!arr.includes(val)) {
            arr.push(val);
            markDirty();
            
            // Add to condition rules implicitly if it doesn't exist
            if (!window.appState.conditional_code_decision_rules) window.appState.conditional_code_decision_rules = {};
            if (!window.appState.conditional_code_decision_rules[val]) {
                window.appState.conditional_code_decision_rules[val] = "Define condition here...";
            }
            
            renderGlossaryCodesForm(); // refresh entire tab to show pill + potential new condition row
        }
        e.target.value = '';
    }
}

window.removeTag = function(idx, type, code) {
    const targetArr = type === 'primary' ? 'primary_codes' : 'conditional_codes';
    const arr = window.appState.rules_to_codes_matrix[idx][targetArr];
    const index = arr.indexOf(code);
    if (index > -1) {
        arr.splice(index, 1);
        markDirty();
        renderGlossaryCodesForm();
    }
}

window.updateConditionCode = function(code, val) {
    if (window.appState.conditional_code_decision_rules) {
        window.appState.conditional_code_decision_rules[code] = val;
        markDirty();
    }
}


window.deleteAmlRule = function(ruleId) {
    if (confirm(`Are you sure you want to delete ${ruleId}?`)) {
        delete window.appState.aml_rules_def[ruleId];
        delete window.appState.evidence_rules_def[ruleId];
        markDirty();
        renderAmlRulesForm();
    }
};

window.deleteLegalSnippet = function(ruleId) {
    if (confirm(`Are you sure you want to delete snippets for ${ruleId}?`)) {
        delete window.appState.rule_specific_snippets[ruleId];
        markDirty();
        renderLegalSnippetsForm();
    }
};

window.deleteMatrixRow = function(idx) {
    if (confirm("Are you sure you want to delete this matrix row?")) {
        window.appState.rules_to_codes_matrix.splice(idx, 1);
        markDirty();
        renderGlossaryCodesForm();
    }
};

window.deleteConditionCode = function(code) {
    if (confirm(`Are you sure you want to delete the definition for ${code}?`)) {
        delete window.appState.conditional_code_decision_rules[code];
        markDirty();
        renderGlossaryCodesForm();
    }
};

window.addNewMatrixRow = function() {
    const newRuleId = prompt("Enter new Rule ID for the matrix (e.g. RULE-09):");
    if (!newRuleId || newRuleId.trim() === '') return;
    const ruleId = newRuleId.trim();
    
    if (!window.appState.rules_to_codes_matrix) window.appState.rules_to_codes_matrix = [];
    const exists = window.appState.rules_to_codes_matrix.find(r => r.rule_id === ruleId);
    if (exists) {
        alert("Rule ID already exists in the matrix!");
        return;
    }
    
    window.appState.rules_to_codes_matrix.push({
        rule_id: ruleId,
        title: "New Rule",
        primary_codes: [],
        conditional_codes: []
    });
    markDirty();
    renderGlossaryCodesForm();
};

window.addNewConditionCodeDef = function() {
    const newCode = prompt("Enter new Glossary Code (e.g. XXNEWXX):");
    if (!newCode || newCode.trim() === '') return;
    const code = newCode.trim().toUpperCase();
    
    if (!window.appState.conditional_code_decision_rules) window.appState.conditional_code_decision_rules = {};
    if (window.appState.conditional_code_decision_rules[code]) {
        alert("Code definition already exists!");
        return;
    }
    
    window.appState.conditional_code_decision_rules[code] = "Define condition here...";
    markDirty();
    renderGlossaryCodesForm();
    setTimeout(() => { window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' }); }, 100);
};

// ----------------------------------------------------
// SAVE ACTION
// ----------------------------------------------------
btnSave.addEventListener('click', async () => {
    if (!hasUnsavedChanges && window.appState) {
        // Can just return or show notice
        showToast('Info', 'No changes to save.');
        return;
    }

    const originalText = btnSave.innerHTML;
    try {
        const payload = window.appState;

        // Loading UI
        btnSave.disabled = true;
        btnSave.innerHTML = `
            <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Saving...
        `;

        // PUT Request
        const response = await fetch(API_ENDPOINTS[activeTab], {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error('API request failed');

        const result = await response.json();
        
        clearDirty();
        showToast('Saved', result.message || 'Config stored in active memory.', 'success');

    } catch (err) {
        showToast('API Error', 'Failed to update backend configuration.', 'error');
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
    } else {
        toastElem.classList.add('bg-blue-800', 'text-white', 'border', 'border-blue-700');
        toastTitle.classList.add('text-blue-50');
        toastMsg.classList.add('text-blue-100');
        toastIcon.innerHTML = `
            <svg class="w-6 h-6 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        `;
    }

    // Set Text
    toastTitle.textContent = title;
    toastMsg.textContent = message;

    // Show animation
    toastElem.classList.remove('translate-y-20', 'opacity-0');
    toastElem.classList.add('translate-y-0', 'opacity-100');

    // Hide animation after 3 seconds
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => {
        toastElem.classList.remove('translate-y-0', 'opacity-100');
        toastElem.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
}

// Kick off
document.addEventListener('DOMContentLoaded', () => {
    loadConfigData();
});
