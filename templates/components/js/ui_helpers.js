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

// Clipboard fallback for non-secure contexts (HTTP on non-localhost)
function fallbackCopy(text, onSuccess) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    try {
        document.execCommand('copy');
        if (onSuccess) onSuccess();
    } catch (err) {
        alert('Failed to copy to clipboard: ' + err);
    }
    document.body.removeChild(textarea);
}
