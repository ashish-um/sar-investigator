// ── Stream Renderer Functions ──────────────────────────────────
function appendThinking(text) {
    if (!currentThinkingBlock) {
        currentThinkingBlock = document.createElement('div');
        currentThinkingBlock.className = 'p-2 animate-fade-in max-w-full text-slate-700 whitespace-pre-wrap font-sans text-[0.9375rem] leading-relaxed';

        // Add blinking cursor
        const cursor = document.createElement('div');
        cursor.className = 'loader inline-block w-1.5 h-1.5 rounded-full bg-slate-400 animate-typing ml-3 opacity-100 transition-opacity duration-300';

        outputContainer.appendChild(currentThinkingBlock);
        outputContainer.appendChild(cursor);
    }

    // Append exactly as-is but format bold text
    currentThinkingBlock.innerHTML += formatThinking(text);
    scrollToBottom();
}

function finalizeThinkingBlock() {
    if (currentThinkingBlock) {
        currentThinkingBlock = null;
        // Remove loaders
        document.querySelectorAll('.loader').forEach(e => e.remove());
    }
}

function playToolCall(data) {
    finalizeThinkingBlock();

    const div = document.createElement('div');
    div.className = 'rounded-md p-4 animate-fade-in max-w-full bg-white border border-slate-200 border-l-4 border-l-blue-500 shadow-sm font-mono text-sm ml-2 mb-1';

    const header = document.createElement('div');
    header.className = 'text-blue-600 font-bold flex items-center gap-2 mb-2 text-xs uppercase tracking-wide';
    header.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg> Calling Tool: ${data.tool}`;

    const args = document.createElement('pre');
    args.className = 'bg-slate-50 border border-slate-100 p-3 rounded overflow-x-auto text-slate-600 m-0 text-xs';
    args.textContent = JSON.stringify(data.arguments, null, 2);

    div.appendChild(header);
    div.appendChild(args);
    outputContainer.appendChild(div);
    scrollToBottom();
}

function playToolResult(data) {
    finalizeThinkingBlock();

    const details = document.createElement('details');
    details.className = 'group rounded-md border border-slate-200 bg-white shadow-sm mb-2 ml-2 transition-all';

    const summary = document.createElement('summary');
    // Remove flex from summary, wrap it in a child div instead
    summary.className = 'cursor-pointer select-none outline-none list-none [&::-webkit-details-marker]:hidden';

    const summaryContainer = document.createElement('div');
    summaryContainer.className = 'px-4 py-3 font-medium text-slate-700 hover:bg-slate-50 flex items-center justify-between focus:bg-slate-50';

    const innerDiv = document.createElement('div');
    innerDiv.className = 'flex items-center gap-2 text-emerald-600 text-[0.9375rem]';
    innerDiv.innerHTML = `
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
        <span>Result Received</span>
    `;

    const chevron = document.createElement('span');
    chevron.innerHTML = `<svg class="w-4 h-4 text-slate-400 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>`;

    summaryContainer.appendChild(innerDiv);
    summaryContainer.appendChild(chevron);
    summary.appendChild(summaryContainer);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'p-4 border-t border-slate-200 bg-slate-50 font-mono text-xs overflow-x-auto text-slate-600';

    const result = document.createElement('pre');
    result.className = 'm-0 whitespace-pre-wrap break-all';
    result.textContent = typeof data.result === 'object'
        ? JSON.stringify(data.result, null, 2)
        : data.result;

    contentDiv.appendChild(result);
    details.appendChild(summary);
    details.appendChild(contentDiv);

    // Auto scroll to bottom when expanding
    details.addEventListener('toggle', (e) => {
        if (details.open) {
            setTimeout(() => {
                details.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }, 50);
        }
    });

    outputContainer.appendChild(details);
    scrollToBottom();
}

const RULE_LABELS = {
    "RULE-01": "Structuring / Smurfing",
    "RULE-02": "Rapid Movement of Funds",
    "RULE-03": "High-risk jurisdiction transfer",
    "RULE-04": "Transaction-Profile Mismatch",
    "RULE-05": "Dormant Account Reactivation",
    "RULE-06": "Third-Party Funding",
    "RULE-07": "PEP / Sanctions proximity",
    "RULE-08": "Round Tripping / Layering"
};

async function fetchAndRenderInlineTable(tableName, id, containerDiv, btn) {
    // Toggle logic: if already loaded and visible, just hide it
    if (containerDiv.dataset.loadedId === id) {
        const isHidden = containerDiv.classList.contains('hidden');
        if (isHidden) {
            containerDiv.classList.remove('hidden');
            btn.classList.add('ring-2', 'ring-offset-1');
        } else {
            containerDiv.classList.add('hidden');
            btn.classList.remove('ring-2', 'ring-offset-1');
        }
        return;
    }

    // Reset peers
    const siblingBtns = btn.parentElement.querySelectorAll('button');
    siblingBtns.forEach(b => b.classList.remove('ring-2', 'ring-offset-1'));
    btn.classList.add('ring-2', 'ring-offset-1');

    containerDiv.classList.remove('hidden');
    containerDiv.innerHTML = `<div class="text-xs text-slate-500 animate-pulse bg-slate-50 border border-slate-200 rounded p-4">Loading ${tableName}.csv row ${id}...</div>`;

    try {
        const res = await fetch(`/data/${tableName}/${id}`);
        const result = await res.json();

        if (result.error) {
            containerDiv.innerHTML = `<div class="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-4">Error: ${result.error}</div>`;
            return;
        }

        const data = result.data;
        const keys = Object.keys(data);

        let tableHTML = `<div class="bg-white border border-slate-200 rounded-md overflow-hidden mt-3 shadow-sm w-full">
            <div class="px-3 py-2 bg-slate-50 border-b border-slate-200 text-xs text-slate-600 font-mono flex items-center gap-2">
                <span>${tableName}.csv</span>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
                <span class="font-bold text-slate-800">${id}</span>
            </div>
            <div class="grid grid-cols-1 w-full">
                <div class="overflow-x-auto w-full">
                    <table class="w-full text-left border-collapse whitespace-nowrap min-w-max">
                        <thead><tr class="text-xs text-slate-500 border-b border-slate-200">`;

        for (const k of keys) {
            tableHTML += `<th class="py-2 px-3 font-medium font-mono">${k}</th>`;
        }
        tableHTML += `</tr></thead><tbody class="text-xs text-slate-800"><tr class="hover:bg-green-50/50 bg-[#F0FDF4] transition-colors">`;

        for (const k of keys) {
            let val = data[k];
            if (val === null) val = '<span class="text-slate-400 italic">null</span>';
            else if (Array.isArray(val)) val = val.join(', ');
            tableHTML += `<td class="py-2 px-3 border-r border-slate-100 last:border-0 font-mono">${val}</td>`;
        }

        tableHTML += `</tr></tbody></table></div></div></div>`;

        containerDiv.innerHTML = tableHTML;
        containerDiv.dataset.loadedId = id;
    } catch (err) {
        containerDiv.innerHTML = `<div class="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-4">Fetch error: ${err.message}</div>`;
    }
}

function playVerdict(data, fullLog) {
    finalizeThinkingBlock();
    lastVerdictData = data;

    const container = document.createElement('div');
    container.className = `animate-fade-in max-w-full mt-6 mb-12`;

    // 1. Top Summary Bar (4 metric chips)
    const isSAR = data.verdict === 'TRUE_POSITIVE';
    let verdictColor = 'text-amber-700';
    let verdictBorder = 'border-amber-200';
    let verdictBg = 'bg-amber-50';
    if (data.verdict === 'TRUE_POSITIVE') {
        verdictColor = 'text-red-700'; verdictBorder = 'border-red-200'; verdictBg = 'bg-red-50';
    } else if (data.verdict === 'FALSE_POSITIVE') {
        verdictColor = 'text-green-700'; verdictBorder = 'border-green-200'; verdictBg = 'bg-green-50';
    }

    const confColor = data.confidence === 'HIGH' ? 'text-amber-700' : 'text-slate-700';
    const sarRecStr = data.sar_recommended ? 'Yes' : 'No';
    const sarRecColor = data.sar_recommended ? 'text-green-700' : 'text-slate-700';
    const dupSafeStr = data.duplicate_sar_safe ? 'Yes' : 'No';
    const dupSafeColor = data.duplicate_sar_safe ? 'text-green-700' : 'text-red-700';

    const metricsHTML = `
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="${verdictBg} border ${verdictBorder} rounded-lg p-4 shadow-sm">
                <div class="text-[0.65rem] text-slate-500 uppercase tracking-wider mb-1">Verdict</div>
                <div class="text-xl font-bold ${verdictColor}">${data.verdict || 'UNKNOWN'}</div>
            </div>
            <div class="bg-[#FCF8F2] border border-stone-200 rounded-lg p-4 shadow-sm">
                <div class="text-[0.65rem] text-slate-500 uppercase tracking-wider mb-1">Confidence</div>
                <div class="text-xl font-bold ${confColor}">${data.confidence || 'UNKNOWN'}</div>
            </div>
            <div class="bg-[#FCF8F2] border border-stone-200 rounded-lg p-4 shadow-sm">
                <div class="text-[0.65rem] text-slate-500 uppercase tracking-wider mb-1">SAR Recommended</div>
                <div class="text-xl font-bold ${sarRecColor}">${sarRecStr}</div>
            </div>
            <div class="bg-[#FCF8F2] border border-stone-200 rounded-lg p-4 shadow-sm">
                <div class="text-[0.65rem] text-slate-500 uppercase tracking-wider mb-1">Duplicate Safe</div>
                <div class="text-xl font-bold ${dupSafeColor}">${dupSafeStr}</div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', metricsHTML);

    // 2. Investigation Summary Block
    if (data.investigation_summary) {
        const sumDiv = document.createElement('div');
        sumDiv.className = 'bg-white border border-slate-200 rounded-lg p-5 shadow-sm mb-6';

        const sumLabel = document.createElement('div');
        sumLabel.className = 'text-[0.65rem] text-slate-500 uppercase tracking-wider mb-3';
        sumLabel.textContent = 'Investigation Summary';
        sumDiv.appendChild(sumLabel);

        const sumText = document.createElement('p');
        sumText.className = 'text-sm text-slate-800 leading-relaxed mb-4';
        sumText.textContent = data.investigation_summary;
        sumDiv.appendChild(sumText);

        if (data.rules_triggered && data.rules_triggered.length > 0) {
            const ruleChipsRow = document.createElement('div');
            ruleChipsRow.className = 'flex flex-wrap gap-2';
            for (const rule of data.rules_triggered) {
                const btn = document.createElement('button');
                btn.className = 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-100 px-3 py-1 rounded-full text-[0.7rem] font-semibold cursor-pointer transition-colors';
                btn.textContent = `${rule} ${RULE_LABELS[rule] || ''}`;
                btn.onclick = () => {
                    const el = document.getElementById(`ev-card-${rule}`);
                    if (el) {
                        el.open = true;
                        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        el.classList.add('ring-2', 'ring-indigo-400', 'ring-offset-2');
                        setTimeout(() => el.classList.remove('ring-2', 'ring-indigo-400', 'ring-offset-2'), 1500);
                    }
                };
                ruleChipsRow.appendChild(btn);
            }
            sumDiv.appendChild(ruleChipsRow);
        }
        container.appendChild(sumDiv);
    }

    // 3. Key Evidence Cards
    if (data.key_evidence && data.key_evidence.length > 0) {
        const evLabel = document.createElement('div');
        evLabel.className = 'text-[0.65rem] text-slate-500 uppercase tracking-wider mb-3 ml-1';
        evLabel.textContent = 'Key Evidence';
        container.appendChild(evLabel);

        for (const ev of data.key_evidence) {
            const details = document.createElement('details');
            details.id = `ev-card-${ev.rule_mapped}`;
            details.open = true; // start expanded by default based on screenshot design
            details.className = 'group bg-white border border-slate-200 rounded-lg shadow-sm mb-4 transition-all duration-300 relative';

            const summary = document.createElement('summary');
            summary.className = 'flex justify-between items-center p-4 cursor-pointer select-none outline-none [&::-webkit-details-marker]:hidden bg-[#FCF8F2] rounded-t-lg group-open:border-b border-slate-200';

            summary.innerHTML = `
                <div class="flex items-center gap-3">
                    <span class="bg-indigo-100 text-indigo-800 text-[0.65rem] font-bold px-2 py-0.5 rounded uppercase">${ev.rule_mapped || 'MAPPED RULE'}</span>
                    <span class="text-sm font-semibold text-slate-800">${RULE_LABELS[ev.rule_mapped] || ''}</span>
                </div>
                <svg class="w-4 h-4 text-slate-600 group-open:rotate-180 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
            `;
            details.appendChild(summary);

            const bodyDiv = document.createElement('div');
            bodyDiv.className = 'p-5';

            // Finding paragraph
            const findingP = document.createElement('p');
            findingP.className = 'text-sm text-slate-800 leading-relaxed mb-5';
            findingP.textContent = ev.finding || '';
            bodyDiv.appendChild(findingP);

            // CSV Chips
            const sd = ev.supporting_data;
            if (sd) {
                // Determine if we show TXNs or Watchlists based on source_table
                const source = ev.source_table || '';

                if (source === 'transactions' && sd.transaction_ids && sd.transaction_ids.length > 0) {
                    const block = document.createElement('div');
                    block.className = 'mb-5';
                    block.innerHTML = `<div class="text-[0.65rem] text-slate-500 mb-2">Transaction IDs — click to inspect CSV row</div>`;

                    const chipsRow = document.createElement('div');
                    chipsRow.className = 'flex flex-wrap gap-2';
                    const inlineDump = document.createElement('div');
                    inlineDump.className = 'mt-1 mb-2 hidden';

                    for (const tid of sd.transaction_ids) {
                        const btn = document.createElement('button');
                        btn.className = 'bg-blue-50 text-blue-700 border border-blue-200 px-2.5 py-1 rounded text-[0.7rem] font-mono hover:bg-blue-100 transition-colors cursor-pointer outline-none ring-blue-400';
                        btn.textContent = tid;
                        btn.onclick = () => fetchAndRenderInlineTable('transactions', tid, inlineDump, btn);
                        chipsRow.appendChild(btn);
                    }
                    block.appendChild(chipsRow);
                    block.appendChild(inlineDump);
                    bodyDiv.appendChild(block);
                }

                if (source === 'watchlists') {
                    // Customer ID Chip
                    if (data.customer_id) {
                        const block = document.createElement('div');
                        block.className = 'mb-4';
                        block.innerHTML = `<div class="text-[0.65rem] text-slate-500 mb-2">Customer profile — click to inspect CSV row</div>`;

                        const chipsRow = document.createElement('div');
                        chipsRow.className = 'flex flex-wrap gap-2';
                        const inlineDump = document.createElement('div');
                        inlineDump.className = 'mt-1 hidden';

                        const btn = document.createElement('button');
                        btn.className = 'bg-stone-50 text-stone-700 border border-stone-200 px-2.5 py-1 rounded text-[0.7rem] font-mono hover:bg-stone-100 transition-colors cursor-pointer outline-none ring-stone-400';
                        btn.textContent = data.customer_id;
                        btn.onclick = () => fetchAndRenderInlineTable('customers', data.customer_id, inlineDump, btn);
                        chipsRow.appendChild(btn);

                        block.appendChild(chipsRow);
                        block.appendChild(inlineDump);
                        bodyDiv.appendChild(block);
                    }

                    // Watchlist ID Chip
                    if (sd.watchlist_ids && sd.watchlist_ids.length > 0) {
                        const block = document.createElement('div');
                        block.className = 'mb-5';
                        block.innerHTML = `<div class="text-[0.65rem] text-slate-500 mb-2">Watchlist entry — click to inspect CSV row</div>`;

                        const chipsRow = document.createElement('div');
                        chipsRow.className = 'flex flex-wrap gap-2';
                        const inlineDump = document.createElement('div');
                        inlineDump.className = 'mt-1 hidden';

                        for (const wid of sd.watchlist_ids) {
                            const btn = document.createElement('button');
                            btn.className = 'bg-stone-50 text-stone-700 border border-stone-200 px-2.5 py-1 rounded text-[0.7rem] font-mono hover:bg-stone-100 transition-colors cursor-pointer outline-none ring-stone-400';
                            btn.textContent = wid;
                            btn.onclick = () => fetchAndRenderInlineTable('watchlists', wid, inlineDump, btn);
                            chipsRow.appendChild(btn);
                        }
                        block.appendChild(chipsRow);
                        block.appendChild(inlineDump);
                        bodyDiv.appendChild(block);
                    }
                }
            }

            // Statistical Context
            if (ev.statistical_context) {
                const statBox = document.createElement('div');
                statBox.className = 'bg-[#FCF8F2] text-slate-700 px-4 py-3 rounded-md text-[0.8rem] mb-4';
                statBox.textContent = ev.statistical_context;
                bodyDiv.appendChild(statBox);
            }

            // Regulatory Significance
            if (ev.regulatory_significance) {
                const regText = document.createElement('div');
                regText.className = 'text-xs text-slate-500';
                regText.textContent = ev.regulatory_significance;
                bodyDiv.appendChild(regText);
            }

            details.appendChild(bodyDiv);
            container.appendChild(details);
        }
    }

    // 4. Hypotheses Considered
    if (data.false_positive_hypotheses_considered && data.false_positive_hypotheses_considered.length > 0) {
        const hLabel = document.createElement('div');
        hLabel.className = 'text-[0.65rem] text-slate-500 uppercase tracking-wider mb-3 mt-2 ml-1';
        hLabel.textContent = 'Hypotheses Considered';
        container.appendChild(hLabel);

        for (const hyp of data.false_positive_hypotheses_considered) {
            const hCard = document.createElement('div');

            const isAccepted = hyp.assessment === 'ACCEPTED';
            const bgClass = 'bg-[#FCF8F2]';
            const borderCol = isAccepted ? 'border-green-500' : 'border-red-500';
            const badgeClass = isAccepted ? 'text-green-700 flex-shrink-0' : 'text-red-500 flex-shrink-0';
            const badgeText = isAccepted ? '✓ ACCEPTED' : '✗ REJECTED';

            hCard.className = `${bgClass} border border-slate-200 border-l-4 ${borderCol} rounded-lg p-4 mb-3`;

            const headRow = document.createElement('div');
            headRow.className = 'flex items-baseline gap-2 mb-2';
            headRow.innerHTML = `
                <span class="text-[0.65rem] font-bold ${badgeClass} tracking-wider mr-1">${badgeText}</span>
                <span class="text-[0.85rem] font-semibold text-slate-800">${hyp.hypothesis || ''}</span>
            `;
            hCard.appendChild(headRow);

            if (hyp.reason) {
                const rText = document.createElement('div');
                rText.className = 'text-[0.8rem] text-slate-600 leading-relaxed';
                rText.textContent = hyp.reason;
                hCard.appendChild(rText);
            }

            container.appendChild(hCard);
        }
    }

    // Raw JSON fallback (collapsible) - minimal representation
    const rawDetails = document.createElement('details');
    rawDetails.className = 'group mt-8 w-full max-w-full overflow-hidden';
    const rawSummary = document.createElement('summary');
    rawSummary.className = 'cursor-pointer select-none text-xs text-slate-400 hover:text-slate-600 font-medium [&::-webkit-details-marker]:hidden flex items-center gap-1';
    rawSummary.innerHTML = `<span>View Raw JSON Response</span><svg class="w-3 h-3 group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>`;
    const rawPre = document.createElement('pre');
    rawPre.className = 'font-mono text-[0.65rem] whitespace-pre-wrap break-all bg-white border border-slate-200 p-3 rounded text-slate-600 mt-2 shadow-inner';
    rawPre.textContent = JSON.stringify(data, null, 2);
    rawDetails.appendChild(rawSummary);
    rawDetails.appendChild(rawPre);
    container.appendChild(rawDetails);

    // Copy button
    const copyBtn = document.createElement('button');
    copyBtn.className = 'mt-4 bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-4 py-2 rounded text-sm font-medium flex items-center gap-2 transition-colors cursor-pointer shadow-sm';
    copyBtn.innerHTML = `<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg> Copy Full Investigation Log`;
    copyBtn.onclick = () => {
        const originalHtml = copyBtn.innerHTML;
        const showSuccess = () => {
            copyBtn.innerHTML = `<svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg> Copied!`;
            setTimeout(() => copyBtn.innerHTML = originalHtml, 2000);
        };
        // Clipboard API requires secure context (HTTPS/localhost); fall back to execCommand
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(fullLog).then(showSuccess).catch(() => fallbackCopy(fullLog, showSuccess));
        } else {
            fallbackCopy(fullLog, showSuccess);
        }
    };
    if (fullLog) container.appendChild(copyBtn);

    // Handoff to SAR Editor
    if (data.verdict === 'TRUE_POSITIVE' || data.sar_recommended) {
        const proceedBtn = document.createElement('button');
        // bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded mt-4
        proceedBtn.className = 'w-full bg-green-600 hover:bg-green-700 text-white px-4 py-3 rounded mt-4 shadow font-semibold transition-colors';
        proceedBtn.textContent = 'Proceed to SAR Generation';
        proceedBtn.onclick = () => {
            sessionStorage.setItem('sar_verdict', JSON.stringify(data));
            window.location.href = '/sar-editor';
        };
        container.appendChild(proceedBtn);
    }

    outputContainer.appendChild(container);
    scrollToBottom();
}

function playRateLimit(data) {
    finalizeThinkingBlock();

    const div = document.createElement('div');

    if (data.type === 'key_rotated') {
        div.className = 'rounded-md p-4 animate-fade-in max-w-full bg-amber-50 border border-amber-200 border-l-4 border-l-amber-500 text-amber-800 text-sm mt-2 mb-2 flex items-center gap-3';
        div.innerHTML = `
            <svg class="w-5 h-5 shrink-0 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>
            <div>
                <span class="font-semibold">Rate Limit Hit</span> — API Key ${data.exhausted_key}/${data.total_keys} exhausted
                <span class="mx-1">→</span>
                <span class="font-semibold text-emerald-700">Switching to Key ${data.new_key}/${data.total_keys}</span>
                <span class="text-amber-600 ml-2 text-xs">(${data.remaining_keys} key${data.remaining_keys !== 1 ? 's' : ''} remaining)</span>
            </div>`;
    } else if (data.type === 'all_keys_exhausted') {
        div.className = 'rounded-md p-4 animate-fade-in max-w-full bg-red-50 border border-red-200 border-l-4 border-l-red-500 text-red-700 text-sm mt-2 mb-2 flex items-center gap-3';
        div.innerHTML = `
            <svg class="w-5 h-5 shrink-0 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636"/></svg>
            <div>
                <span class="font-semibold">All ${data.total_keys} API Keys Exhausted</span> — all keys have hit their rate limits. Please wait or add more keys.
            </div>`;
    }

    outputContainer.appendChild(div);
    scrollToBottom();
}

function playError(data) {
    finalizeThinkingBlock();

    const div = document.createElement('div');
    div.className = 'rounded-md p-4 animate-fade-in max-w-full bg-red-50 border border-red-200 border-l-4 border-l-red-500 text-red-700 font-mono text-sm mt-4';
    div.textContent = `Error: ${data.message}`;
    outputContainer.appendChild(div);
    scrollToBottom();
}
