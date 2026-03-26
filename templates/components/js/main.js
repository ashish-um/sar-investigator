// ── Main Event Wiring ──────────────────────────────────
investigateBtn.addEventListener('click', () => {
    let payload;
    try {
        payload = JSON.parse(alertInput.value);
    } catch (e) {
        alert('Invalid JSON in input box');
        return;
    }

    // Clear output
    outputContainer.innerHTML = '';
    currentThinkingBlock = null;
    fullOutputLog = "=== INVESTIGATION LOG ===\n\n";
    fullOutputLog += "ALERT PAYLOAD:\n" + JSON.stringify(payload, null, 2) + "\n\n";
    fullOutputLog += "AGENT REASONING FLIGHT RECORDER:\n==============================================\n\n";
    
    // UI State
    setStatus('Investigating...', true);
    toggleRunningIndicator(true);
    investigateBtn.disabled = true;
    
    // We use fetch instead of EventSource because EventSource doesn't support POST
    fetchSSE('http://127.0.0.1:8000/investigate', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream'
        },
        body: JSON.stringify(payload)
    }, (eventType, data) => {
        // Event Router
        if (eventType === 'system_prompt') {
            const promptText = data.content || data;
            fullOutputLog += "DYNAMIC SYSTEM PROMPT:\n" + promptText + "\n\n==============================================\n\n";
        } else if (eventType === 'thinking') {
            if (data.content) {
                fullOutputLog += data.content;
                appendThinking(data.content);
            }
        } else if (eventType === 'tool_call') {
            fullOutputLog += `\n\n[CALLING TOOL: ${data.tool}]\nArguments: ${JSON.stringify(data.arguments)}\n\n`;
            playToolCall(data);
        } else if (eventType === 'tool_result') {
            const resStr = typeof data.result === 'object' ? JSON.stringify(data.result, null, 2) : data.result;
            fullOutputLog += `[TOOL RESULT]\n${resStr}\n\n`;
            playToolResult(data);
        } else if (eventType === 'rate_limit') {
            if (data.type === 'key_rotated') {
                fullOutputLog += `\n[RATE LIMIT] Key ${data.exhausted_key}/${data.total_keys} exhausted → switching to key ${data.new_key}/${data.total_keys} (${data.remaining_keys} remaining)\n\n`;
            } else if (data.type === 'all_keys_exhausted') {
                fullOutputLog += `\n[RATE LIMIT] All ${data.total_keys} API keys exhausted. Investigation cannot continue.\n\n`;
            }
            playRateLimit(data);
        } else if (eventType === 'verdict') {
            fullOutputLog += `\n==============================================\n[FINAL VERDICT]\n${JSON.stringify(data, null, 2)}\n`;
            playVerdict(data, fullOutputLog);
            setStatus('Investigation Complete', false);
            toggleRunningIndicator(false);
            investigateBtn.disabled = false;
        } else if (eventType === 'error') {
            fullOutputLog += `\n[ERROR]\n${data.message}\n`;
            playError(data);
        }
    });
});
