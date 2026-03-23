// ── Drawer Functions ──────────────────────────────────────
function openDrawer() {
    evidenceDrawer.classList.remove('translate-x-full');
    drawerOverlay.classList.remove('hidden');
}
function closeDrawer() {
    evidenceDrawer.classList.add('translate-x-full');
    drawerOverlay.classList.add('hidden');
}

// Parse a currency string like "£75,000" or "$1,234.56" to a number
function parseCurrencyToNumber(str) {
    if (typeof str === 'number') return str;
    return parseFloat(String(str).replace(/[^0-9.\-]/g, ''));
}

// Extract agent claims for a specific transaction ID from the verdict
function getAgentClaimsForTransaction(txnId) {
    if (!lastVerdictData || !lastVerdictData.key_evidence) return null;
    for (const ev of lastVerdictData.key_evidence) {
        const sd = ev.supporting_data;
        if (sd && sd.transaction_ids && sd.transaction_ids.includes(txnId)) {
            return { evidence: ev, supporting_data: sd };
        }
    }
    return null;
}

// Compare agent's claimed values against the actual DB row.
// Uses SET-MEMBERSHIP checks: does the row's value exist ANYWHERE
// in the agent's claimed arrays (not index-paired).
function buildVerificationRows(dbRow, agentClaims) {
    const checks = [];
    if (!agentClaims) return checks;
    const sd = agentClaims.supporting_data;

    // Check: does this row's amount_gbp exist in the claimed amounts array?
    if (sd.amounts && sd.amounts.length > 0 && dbRow.amount_gbp !== undefined) {
        const actual = dbRow.amount_gbp;
        const claimedNums = sd.amounts.map(a => parseCurrencyToNumber(a));
        const match = claimedNums.some(n => Math.abs(n - actual) < 1);
        checks.push({
            field: 'amount_gbp',
            claimed: sd.amounts.join(', '),
            actual: `\u00a3${Number(actual).toLocaleString()}`,
            match
        });
    }

    // Check: does this row's date exist anywhere in the claimed dates array?
    if (sd.dates && sd.dates.length > 0 && dbRow.transaction_datetime) {
        const actual = dbRow.transaction_datetime;
        const match = sd.dates.some(d => actual.startsWith(d));
        checks.push({
            field: 'transaction_datetime',
            claimed: sd.dates.join(', '),
            actual,
            match
        });
    }

    // Check: does this row's counterparty exist anywhere in the claimed counterparties array?
    if (sd.counterparties && sd.counterparties.length > 0 && dbRow.counterparty_name) {
        const actual = dbRow.counterparty_name;
        const match = sd.counterparties.some(cp =>
            actual.toLowerCase().includes(cp.toLowerCase()) ||
            cp.toLowerCase().includes(actual.toLowerCase())
        );
        checks.push({
            field: 'counterparty_name',
            claimed: sd.counterparties.join(', '),
            actual,
            match
        });
    }

    return checks;
}

// Render the drawer content for a single DB row
function renderDrawerRow(table, dbRow, verificationChecks) {
    let html = '';

    // Verification banner
    if (verificationChecks && verificationChecks.length > 0) {
        html += `<div class="mb-5 p-4 rounded-md border bg-slate-50 border-slate-200">`;
        html += `<div class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Claim Verification</div>`;
        for (const ck of verificationChecks) {
            const icon = ck.match
                ? '<svg class="w-4 h-4 text-emerald-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>'
                : '<svg class="w-4 h-4 text-red-500 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>';
            const bg = ck.match ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200';
            const label = ck.match ? 'Verified' : 'Mismatch';
            html += `<div class="flex items-start gap-2 mb-2 p-2 rounded border ${bg}">`;
            html += `${icon}<div class="text-xs"><span class="font-mono font-bold">${ck.field}</span><br/>`;
            html += `Agent claimed: <span class="font-semibold">${ck.claimed}</span><br/>`;
            html += `Actual value: <span class="font-semibold">${ck.actual}</span>`;
            html += `<span class="ml-2 font-bold ${ck.match ? 'text-emerald-700' : 'text-red-700'}">${label}</span>`;
            html += `</div></div>`;
        }
        html += `</div>`;
    }

    // Raw data table
    html += `<div class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">Raw Database Record</div>`;
    html += `<div class="border border-slate-200 rounded-md overflow-hidden">`;
    const keys = Object.keys(dbRow);
    const highlightFields = verificationChecks ? verificationChecks.map(c => c.field) : [];
    for (let i = 0; i < keys.length; i++) {
        const k = keys[i];
        const v = dbRow[k];
        const isHighlighted = highlightFields.includes(k);
        const stripe = i % 2 === 0 ? 'bg-white' : 'bg-slate-50';
        const highlight = isHighlighted ? 'ring-2 ring-blue-200 ring-inset' : '';
        html += `<div class="flex ${stripe} ${highlight}">`;
        html += `<div class="w-[180px] shrink-0 px-3 py-2 text-xs font-mono font-semibold text-slate-500 border-r border-slate-200">${k}</div>`;
        html += `<div class="flex-1 px-3 py-2 text-xs font-mono text-slate-800 break-all">${v !== null && v !== undefined ? v : '<span class="text-slate-400">null</span>'}</div>`;
        html += `</div>`;
    }
    html += `</div>`;
    return html;
}

// Fetch and display a record in the drawer
async function fetchAndShowRecord(table, id) {
    drawerTitle.textContent = `${table}`;
    drawerSubtitle.textContent = id;
    drawerContent.innerHTML = '<div class="text-sm text-slate-400 animate-pulse">Loading...</div>';
    openDrawer();

    try {
        const resp = await fetch(`/data/${table}/${encodeURIComponent(id)}`);
        const result = await resp.json();
        if (result.error) {
            drawerContent.innerHTML = `<div class="text-sm text-red-500">${result.error}</div>`;
            return;
        }
        const dbRow = result.data;
        let checks = [];

        if (table === 'transactions') {
            const claims = getAgentClaimsForTransaction(id);
            // RULE-07 entries have no transaction_ids — skip verification
            if (claims && claims.evidence && claims.evidence.rule_mapped === 'RULE-07') {
                drawerContent.innerHTML = `<div class="mb-4 p-3 rounded border bg-slate-50 border-slate-200 text-xs text-slate-500 italic">Profile data \u2014 transaction verification not applicable</div>` + renderDrawerRow(table, dbRow, []);
                return;
            }
            checks = buildVerificationRows(dbRow, claims);
        }
        // Accounts: just show existence (the row itself is the proof)
        drawerContent.innerHTML = renderDrawerRow(table, dbRow, checks);
    } catch (err) {
        drawerContent.innerHTML = `<div class="text-sm text-red-500">Failed to fetch: ${err.message}</div>`;
    }
}

// Fetch and display counterparty transactions
async function fetchCounterparty(name) {
    drawerTitle.textContent = 'Counterparty Transactions';
    drawerSubtitle.textContent = name;
    drawerContent.innerHTML = '<div class="text-sm text-slate-400 animate-pulse">Loading...</div>';
    openDrawer();

    try {
        const resp = await fetch(`/data/transactions/counterparty/${encodeURIComponent(name)}`);
        const result = await resp.json();
        if (!result.rows || result.rows.length === 0) {
            drawerContent.innerHTML = `<div class="text-sm text-slate-500">No transactions found for "${name}".</div>`;
            return;
        }
        let html = `<div class="text-xs font-bold text-slate-500 uppercase tracking-wider mb-3">${result.rows.length} transaction(s) found</div>`;
        for (const row of result.rows) {
            html += `<div class="mb-4">`;
            html += renderDrawerRow('transactions', row, []);
            html += `</div>`;
        }
        drawerContent.innerHTML = html;
    } catch (err) {
        drawerContent.innerHTML = `<div class="text-sm text-red-500">Failed to fetch: ${err.message}</div>`;
    }
}

// Create a clickable chip element
function makeChip(label, type, id) {
    const chip = document.createElement('button');
    const colors = {
        transaction: 'bg-blue-50 text-blue-700 border-blue-200 hover:bg-blue-100',
        account: 'bg-violet-50 text-violet-700 border-violet-200 hover:bg-violet-100',
        customer: 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100',
        counterparty: 'bg-teal-50 text-teal-700 border-teal-200 hover:bg-teal-100',
    };
    chip.className = `inline-flex items-center gap-1 px-2 py-0.5 rounded border text-xs font-mono cursor-pointer transition-colors ${colors[type] || colors.transaction}`;
    chip.innerHTML = `<svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>${label}`;
    chip.onclick = (e) => {
        e.stopPropagation();
        if (type === 'transaction') fetchAndShowRecord('transactions', id);
        else if (type === 'account') fetchAndShowRecord('accounts', id);
        else if (type === 'customer') fetchAndShowRecord('customers', id);
        else if (type === 'counterparty') fetchCounterparty(id);
    };
    return chip;
}
