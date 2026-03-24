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
    result.className = 'm-0';
    result.textContent = typeof data.result === 'object' 
        ? JSON.stringify(data.result, null, 2) 
        : data.result;
    
    contentDiv.appendChild(result);
    details.appendChild(summary);
    details.appendChild(contentDiv);
    
    // Auto scroll to bottom when expanding
    details.addEventListener('toggle', (e) => {
        if(details.open) {
            setTimeout(() => {
                details.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }, 50);
        }
    });
    
    outputContainer.appendChild(details);
    scrollToBottom();
}

function playVerdict(data, fullLog) {
    finalizeThinkingBlock();
    lastVerdictData = data;
    
    const isSAR = data.verdict === 'TRUE_POSITIVE';
    
    const container = document.createElement('div');
    container.className = `rounded-md p-6 animate-fade-in max-w-full border shadow-sm mt-4 mb-8 ${isSAR ? 'bg-red-50 border-red-200' : 'bg-green-50 border-green-200'}`;
    
    // Verdict header
    const header = document.createElement('div');
    header.className = `text-lg font-bold mb-4 flex items-center gap-2 ${isSAR ? 'text-red-700' : 'text-green-700'}`;
    header.innerHTML = isSAR 
        ? `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg> TRUE POSITIVE - SAR RECOMMENDED` 
        : `<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> FALSE POSITIVE - NO SUSPICIOUS ACTIVITY`;
    container.appendChild(header);

    // Metadata row: confidence, SAR recommended, duplicate SAR safe
    const metaRow = document.createElement('div');
    metaRow.className = 'flex flex-wrap items-center gap-2 mb-4';
    if (data.customer_id) {
        const custLabel = document.createElement('span');
        custLabel.className = 'text-xs font-bold text-slate-500 uppercase tracking-wider mr-1';
        custLabel.textContent = 'Customer';
        metaRow.appendChild(custLabel);
        metaRow.appendChild(makeChip(data.customer_id, 'customer', data.customer_id));
        const sep = document.createElement('span');
        sep.className = 'w-px h-4 bg-slate-300 mx-1';
        metaRow.appendChild(sep);
    }
    if (data.confidence) {
        const confColors = { HIGH: 'bg-red-100 text-red-700 border-red-200', MEDIUM: 'bg-amber-100 text-amber-700 border-amber-200', LOW: 'bg-green-100 text-green-700 border-green-200' };
        const confBadge = document.createElement('span');
        confBadge.className = `text-[0.65rem] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${confColors[data.confidence] || 'bg-slate-100 text-slate-600 border-slate-200'}`;
        confBadge.textContent = `${data.confidence} confidence`;
        metaRow.appendChild(confBadge);
    }
    if (data.sar_recommended !== undefined) {
        const sarBadge = document.createElement('span');
        sarBadge.className = `text-[0.65rem] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${data.sar_recommended ? 'bg-red-100 text-red-700 border-red-200' : 'bg-green-100 text-green-700 border-green-200'}`;
        sarBadge.textContent = data.sar_recommended ? 'SAR Recommended' : 'No SAR';
        metaRow.appendChild(sarBadge);
    }
    if (data.duplicate_sar_safe !== undefined) {
        const dupBadge = document.createElement('span');
        dupBadge.className = 'text-[0.65rem] font-bold px-2 py-0.5 rounded border uppercase tracking-wider bg-slate-100 text-slate-600 border-slate-200';
        dupBadge.textContent = data.duplicate_sar_safe ? 'No duplicate SAR' : 'Duplicate SAR risk';
        metaRow.appendChild(dupBadge);
    }
    container.appendChild(metaRow);

    // Rules triggered
    if (data.rules_triggered && data.rules_triggered.length > 0) {
        const rulesRow = document.createElement('div');
        rulesRow.className = 'flex flex-wrap items-center gap-2 mb-4';
        const rulesLabel = document.createElement('span');
        rulesLabel.className = 'text-xs font-bold text-slate-500 uppercase tracking-wider';
        rulesLabel.textContent = 'Rules Triggered';
        rulesRow.appendChild(rulesLabel);
        for (const rule of data.rules_triggered) {
            const pill = document.createElement('span');
            pill.className = 'bg-slate-800 text-white text-[0.6rem] font-bold px-2.5 py-1 rounded uppercase tracking-wider';
            pill.textContent = rule;
            rulesRow.appendChild(pill);
        }
        container.appendChild(rulesRow);
    }

    // Investigation summary
    if (data.investigation_summary) {
        const sumLabel = document.createElement('div');
        sumLabel.className = 'text-xs font-bold text-slate-500 uppercase tracking-wider mb-2';
        sumLabel.textContent = 'Investigation Summary';
        container.appendChild(sumLabel);
        const summaryDiv = document.createElement('div');
        summaryDiv.className = 'text-sm text-slate-700 mb-4 p-4 bg-white rounded-md border border-slate-200 leading-relaxed';
        summaryDiv.textContent = data.investigation_summary;
        container.appendChild(summaryDiv);
    }

    // False positive hypotheses considered
    if (data.false_positive_hypotheses_considered && data.false_positive_hypotheses_considered.length > 0) {
        const fpLabel = document.createElement('div');
        fpLabel.className = 'text-xs font-bold text-slate-500 uppercase tracking-wider mb-2';
        fpLabel.textContent = `False Positive Hypotheses (${data.false_positive_hypotheses_considered.length})`;
        container.appendChild(fpLabel);
        for (const hyp of data.false_positive_hypotheses_considered) {
            const hCard = document.createElement('div');
            hCard.className = 'bg-white rounded-md border border-slate-200 p-3 mb-2 shadow-sm';
            const hHeader = document.createElement('div');
            hHeader.className = 'flex items-start gap-2 mb-1';
            const assessColor = hyp.assessment === 'REJECTED' ? 'bg-red-100 text-red-700 border-red-200' : 'bg-green-100 text-green-700 border-green-200';
            const assessBadge = document.createElement('span');
            assessBadge.className = `text-[0.6rem] font-bold px-2 py-0.5 rounded border uppercase tracking-wider shrink-0 mt-0.5 ${assessColor}`;
            assessBadge.textContent = hyp.assessment || 'N/A';
            hHeader.appendChild(assessBadge);
            const hText = document.createElement('span');
            hText.className = 'text-sm text-slate-700 font-medium';
            hText.textContent = hyp.hypothesis || '';
            hHeader.appendChild(hText);
            hCard.appendChild(hHeader);
            if (hyp.reason) {
                const hReason = document.createElement('div');
                hReason.className = 'text-xs text-slate-500 mt-1.5 ml-[calc(0.5rem+2px)] pl-4 border-l-2 border-slate-200';
                hReason.textContent = hyp.reason;
                hCard.appendChild(hReason);
            }
            container.appendChild(hCard);
        }
    }

    // Render key_evidence cards
    if (data.key_evidence && data.key_evidence.length > 0) {
        const evTitle = document.createElement('div');
        evTitle.className = 'text-xs font-bold text-slate-500 uppercase tracking-wider mb-3';
        evTitle.textContent = `Key Evidence (${data.key_evidence.length} entries) — Click IDs to verify`;
        container.appendChild(evTitle);

        for (const ev of data.key_evidence) {
            const card = document.createElement('div');
            card.className = 'bg-white rounded-md border border-slate-200 p-4 mb-3 shadow-sm';

            // Rule badge + finding
            const cardHeader = document.createElement('div');
            cardHeader.className = 'flex items-start gap-2 mb-2';
            if (ev.rule_mapped) {
                const badge = document.createElement('span');
                badge.className = 'bg-slate-800 text-white text-[0.6rem] font-bold px-2 py-0.5 rounded uppercase tracking-wider shrink-0 mt-0.5';
                badge.textContent = ev.rule_mapped;
                cardHeader.appendChild(badge);
            }
            const finding = document.createElement('span');
            finding.className = 'text-sm text-slate-700';
            finding.textContent = ev.finding || '';
            cardHeader.appendChild(finding);
            card.appendChild(cardHeader);

            // Clickable ID chips
            const sd = ev.supporting_data;
            if (sd) {
                const chipRow = document.createElement('div');
                chipRow.className = 'flex flex-wrap gap-1.5 mt-3';

                if (sd.transaction_ids) {
                    for (const txnId of sd.transaction_ids) {
                        chipRow.appendChild(makeChip(txnId, 'transaction', txnId));
                    }
                }
                if (sd.accounts_involved) {
                    for (const accId of sd.accounts_involved) {
                        chipRow.appendChild(makeChip(accId, 'account', accId));
                    }
                }
                if (sd.counterparties) {
                    for (const cp of sd.counterparties) {
                        chipRow.appendChild(makeChip(cp, 'counterparty', cp));
                    }
                }
                card.appendChild(chipRow);
            }

            // Regulatory significance
            if (ev.regulatory_significance) {
                const regDiv = document.createElement('div');
                regDiv.className = 'text-xs text-slate-500 mt-3 italic';
                regDiv.textContent = ev.regulatory_significance;
                card.appendChild(regDiv);
            }

            container.appendChild(card);
        }
    }

    // Raw JSON fallback (collapsible)
    const rawDetails = document.createElement('details');
    rawDetails.className = 'group mt-4';
    const rawSummary = document.createElement('summary');
    rawSummary.className = 'cursor-pointer select-none text-xs text-slate-500 hover:text-slate-700 font-medium';
    rawSummary.textContent = 'View Raw Verdict JSON';
    const rawPre = document.createElement('pre');
    rawPre.className = 'font-mono text-xs whitespace-pre-wrap bg-white border border-slate-200 p-4 rounded text-slate-700 m-0 mt-2';
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
    
    outputContainer.appendChild(container);
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
