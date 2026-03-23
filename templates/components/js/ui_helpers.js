// ── UI Helper Functions ──────────────────────────────────
function setStatus(text, isActive = false) {
    statusIndicator.textContent = text;
    if (isActive) {
        statusIndicator.className = 'text-sm px-4 py-1.5 rounded-full font-medium border transition-all duration-300 bg-blue-50 text-blue-600 border-blue-200';
    } else {
        statusIndicator.className = 'text-sm px-4 py-1.5 rounded-full font-medium border transition-all duration-300 bg-slate-100 text-slate-500 border-slate-200';
    }
}

function toggleRunningIndicator(show) {
    if (show) {
        runningIndicator.classList.remove('hidden');
        runningIndicator.classList.add('flex');
    } else {
        runningIndicator.classList.add('hidden');
        runningIndicator.classList.remove('flex');
    }
}

function scrollToBottom() {
    outputContainer.scrollTop = outputContainer.scrollHeight;
}

// Apply basic markdown formatting for thinking text
function formatThinking(text) {
    return text
        .replace(/\*([^\*]+)\*/g, '<span class="font-semibold text-slate-900">$1</span>')
        .replace(/\*\*([^\*]+)\*\*/g, '<span class="font-semibold text-slate-900">$1</span>');
}
