// ── SAR Generation Functions ──────────────────────────────────
let sarState = {
    status: 'idle',  // idle | generating | done | error
    sections: {},
    sarDraftId: null,
    error: null
};

const SAR_SECTION_NAMES = [
    { field: 'section_1_subject_identity', label: 'Subject Identity' },
    { field: 'section_2_account_overview', label: 'Account Overview' },
    { field: 'section_3_transaction_chronology', label: 'Transaction Chronology' },
    { field: 'section_4_reason_for_suspicion', label: 'Reason for Suspicion' },
    { field: 'section_5_exculpatory_analysis', label: 'Exculpatory Analysis' },
    { field: 'section_6_conclusion', label: 'Conclusion' },
];

function generateSAR() {
    if (!lastVerdictData || !lastAlertPayload) {
        console.error('Missing verdict or alert data for SAR generation');
        return;
    }

    sarState = { status: 'generating', sections: {}, sarDraftId: null, error: null };

    // Remove any existing SAR container and re-create
    const existingSar = document.getElementById('sar-container');
    if (existingSar) existingSar.remove();

    const sarContainer = document.createElement('div');
    sarContainer.id = 'sar-container';
    sarContainer.className = 'rounded-md p-6 animate-fade-in max-w-full border border-indigo-200 bg-indigo-50 shadow-sm mt-4 mb-8';

    // Header
    const header = document.createElement('div');
    header.className = 'text-lg font-bold mb-4 flex items-center gap-2 text-indigo-700';
    header.innerHTML = `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg> SAR Draft Generation`;
    sarContainer.appendChild(header);

    // Progress area
    const progress = document.createElement('div');
    progress.id = 'sar-progress';
    progress.className = 'text-sm text-indigo-600 mb-4 flex items-center gap-2';
    progress.innerHTML = `<div class="flex items-center justify-center relative w-4 h-4"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span></div> Initialising SAR generation...`;
    sarContainer.appendChild(progress);

    // Sections container
    const sectionsDiv = document.createElement('div');
    sectionsDiv.id = 'sar-sections';
    sectionsDiv.className = 'flex flex-col gap-3';
    sarContainer.appendChild(sectionsDiv);

    // Actions container (hidden until complete)
    const actionsDiv = document.createElement('div');
    actionsDiv.id = 'sar-actions';
    actionsDiv.className = 'hidden mt-4 flex items-center gap-3';
    sarContainer.appendChild(actionsDiv);

    outputContainer.appendChild(sarContainer);
    scrollToBottom();

    // Disable the generate button
    const genBtn = document.getElementById('generate-sar-btn');
    if (genBtn) {
        genBtn.disabled = true;
        genBtn.textContent = 'Generating...';
    }

    // Start SSE fetch
    fetchSSE('http://127.0.0.1:8000/api/generate-sar', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        },
        body: JSON.stringify({
            verdict: lastVerdictData,
            alert: lastAlertPayload
        })
    }, (eventType, data) => {
        handleSAREvent(eventType, data);
    });
}

function handleSAREvent(eventType, data) {
    const progress = document.getElementById('sar-progress');
    const sectionsDiv = document.getElementById('sar-sections');

    switch (eventType) {
        case 'sar_status':
            if (progress) {
                progress.innerHTML = `<div class="flex items-center justify-center relative w-4 h-4"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span></div> ${data.message}`;
            }
            break;

        case 'evidence_ready':
            if (progress) {
                const codesHtml = data.glossary_codes
                    ? data.glossary_codes.map(c => `<span class="bg-indigo-100 text-indigo-700 text-[0.6rem] font-bold px-2 py-0.5 rounded border border-indigo-200 uppercase tracking-wider">${c}</span>`).join(' ')
                    : '';
                progress.innerHTML = `<div class="flex items-center justify-center relative w-4 h-4"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span></div> Evidence built. Generating SAR sections... <div class="flex gap-1 ml-2">${codesHtml}</div>`;
            }
            break;

        case 'section_start':
            if (progress) {
                progress.innerHTML = `<div class="flex items-center justify-center relative w-4 h-4"><span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span><span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-indigo-500"></span></div> Writing Section ${data.index || ''}: ${data.section}...`;
            }
            break;

        case 'section_complete':
            sarState.sections[data.field] = data.content;
            if (sectionsDiv) {
                renderSARSection(sectionsDiv, data.section, data.field, data.content, data.index);
            }
            scrollToBottom();
            break;

        case 'complete':
            sarState.status = 'done';
            sarState.sarDraftId = data.sar_draft_id;
            if (progress) {
                progress.innerHTML = `<svg class="w-5 h-5 text-emerald-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> <span class="text-emerald-700 font-medium">SAR Draft Complete</span> <span class="text-slate-500 text-xs ml-2">${data.sar_draft_id}</span>`;
            }
            showSARActions();
            // Re-enable button
            const genBtn = document.getElementById('generate-sar-btn');
            if (genBtn) {
                genBtn.disabled = false;
                genBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg> Regenerate SAR`;
            }
            break;

        case 'error':
            sarState.status = 'error';
            sarState.error = data.message;
            if (progress) {
                progress.innerHTML = `<svg class="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> <span class="text-red-700 font-medium">Error: ${data.message}</span>`;
            }
            const genBtnErr = document.getElementById('generate-sar-btn');
            if (genBtnErr) {
                genBtnErr.disabled = false;
                genBtnErr.textContent = 'Retry SAR Generation';
            }
            break;
    }
}

function renderSARSection(container, title, field, content, index) {
    const details = document.createElement('details');
    details.className = 'group rounded-md border border-slate-200 bg-white shadow-sm transition-all';
    details.open = true;  // Auto-expand new sections

    const summary = document.createElement('summary');
    summary.className = 'cursor-pointer select-none outline-none list-none [&::-webkit-details-marker]:hidden';

    const summaryContainer = document.createElement('div');
    summaryContainer.className = 'px-4 py-3 font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-between';

    const innerDiv = document.createElement('div');
    innerDiv.className = 'flex items-center gap-2 text-sm';
    innerDiv.innerHTML = `
        <span class="bg-indigo-100 text-indigo-700 text-[0.6rem] font-bold px-2 py-0.5 rounded uppercase tracking-wider">${index || ''}</span>
        <span class="font-semibold">${title}</span>
        <span class="text-xs text-slate-400">${content.length.toLocaleString()} chars</span>
    `;

    const chevron = document.createElement('span');
    chevron.innerHTML = `<svg class="w-4 h-4 text-slate-400 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>`;

    summaryContainer.appendChild(innerDiv);
    summaryContainer.appendChild(chevron);
    summary.appendChild(summaryContainer);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'p-5 border-t border-slate-200 bg-white text-sm text-slate-700 leading-relaxed whitespace-pre-wrap';
    contentDiv.textContent = content;

    details.appendChild(summary);
    details.appendChild(contentDiv);
    container.appendChild(details);
}

function showSARActions() {
    const actionsDiv = document.getElementById('sar-actions');
    if (!actionsDiv) return;
    actionsDiv.classList.remove('hidden');
    actionsDiv.classList.add('flex');
    actionsDiv.innerHTML = '';

    // Copy button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded text-sm font-medium flex items-center gap-2 transition-colors cursor-pointer shadow-sm';
    copyBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg> Copy Full SAR Text`;
    copyBtn.onclick = () => {
        const fullText = buildFullSARText();
        const origHtml = copyBtn.innerHTML;
        const doSuccess = () => {
            copyBtn.innerHTML = `<svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Copied!`;
            setTimeout(() => copyBtn.innerHTML = origHtml, 2000);
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullText).then(doSuccess).catch(() => fallbackCopy(fullText, doSuccess));
        } else {
            fallbackCopy(fullText, doSuccess);
        }
    };
    actionsDiv.appendChild(copyBtn);

    // Download button
    const dlBtn = document.createElement('button');
    dlBtn.className = 'bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded text-sm font-medium flex items-center gap-2 transition-colors cursor-pointer shadow-sm';
    dlBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg> Download SAR (.txt)`;
    dlBtn.onclick = () => {
        const fullText = buildFullSARText();
        const blob = new Blob([fullText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${sarState.sarDraftId || 'SAR-DRAFT'}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    };
    actionsDiv.appendChild(dlBtn);
}

function buildFullSARText() {
    let text = '';
    for (const sec of SAR_SECTION_NAMES) {
        const content = sarState.sections[sec.field] || '';
        text += `=== SECTION: ${sec.label.toUpperCase()} ===\n\n${content}\n\n`;
    }
    return text.trim();
}
