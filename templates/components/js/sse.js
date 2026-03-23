// ── SSE Fetch Helper ──────────────────────────────────
async function fetchSSE(url, options, onEvent) {
    try {
        const response = await fetch(url, options);
        
        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            
            // Parse SSE format
            const events = buffer.split('\n\n');
            buffer = events.pop(); // Keep the last incomplete chunk in buffer
            
            for (const eventStr of events) {
                if (!eventStr.trim()) continue;
                
                const lines = eventStr.split('\n');
                let eventType = 'message';
                let eventData = '';
                
                for (const line of lines) {
                    if (line.startsWith('event:')) {
                        eventType = line.substring(6).trim();
                    } else if (line.startsWith('data:')) {
                        eventData += line.substring(5).trim();
                    }
                }
                
                if (eventData) {
                    try {
                        const parsedData = JSON.parse(eventData);
                        onEvent(eventType, parsedData);
                    } catch (e) {
                        console.error('Failed to parse SSE JSON data:', e, eventData);
                    }
                }
            }
        }
    } catch (error) {
        playError({ message: error.message });
    } finally {
        setStatus('Ready', false);
        toggleRunningIndicator(false);
        investigateBtn.disabled = false;
        finalizeThinkingBlock();
    }
}
