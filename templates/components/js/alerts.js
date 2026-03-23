// ── Sample Alert Loading ──────────────────────────────────
async function fetchSampleAlerts() {
    try {
        const response = await fetch('/api/alerts');
        if (!response.ok) throw new Error('Failed to fetch alerts');
        const data = await response.json();
        
        alertSelect.innerHTML = '<option value="">-- Select an alert to load --</option>';
        
        if (data.fp && data.fp.length > 0) {
            const groupFP = document.createElement('optgroup');
            groupFP.label = 'False Positives';
            data.fp.forEach(alert => {
                const opt = document.createElement('option');
                const id = `fp_${alert.name}`;
                loadedAlerts[id] = alert.content;
                opt.value = id;
                opt.textContent = `✓ ${alert.name.replace('.json', '')}`;
                groupFP.appendChild(opt);
            });
            alertSelect.appendChild(groupFP);
        }
        
        if (data.tp && data.tp.length > 0) {
            const groupTP = document.createElement('optgroup');
            groupTP.label = 'True Positives';
            data.tp.forEach(alert => {
                const opt = document.createElement('option');
                const id = `tp_${alert.name}`;
                loadedAlerts[id] = alert.content;
                opt.value = id;
                opt.textContent = `⚠ ${alert.name.replace('.json', '')}`;
                groupTP.appendChild(opt);
            });
            alertSelect.appendChild(groupTP);
        }
        
        // Auto-select the first FP if available
        if (data.fp && data.fp.length > 0) {
            const firstId = `fp_${data.fp[0].name}`;
            alertSelect.value = firstId;
            alertInput.value = JSON.stringify(loadedAlerts[firstId], null, 2);
        }
        
    } catch (error) {
        console.error('Error fetching alerts:', error);
        alertSelect.innerHTML = '<option value="">-- Error loading alerts --</option>';
    }
}

document.addEventListener('DOMContentLoaded', fetchSampleAlerts);

alertSelect.addEventListener('change', (e) => {
    const id = e.target.value;
    if (id && loadedAlerts[id]) {
        alertInput.value = JSON.stringify(loadedAlerts[id], null, 2);
    } else {
        alertInput.value = '';
    }
});
