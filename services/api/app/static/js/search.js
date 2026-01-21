// search.js - Lógica de búsqueda

const API_BASE = '/api/v2';
let currentJobId = null;
let pollingInterval = null;
let findingsPage = 0;
let findingsTotal = 0;
let findingsPageSize = 20;
let cachedFindings = [];

const searchForm = document.getElementById('searchForm');
const searchValue = document.getElementById('searchValue');
const searchBtn = document.getElementById('searchBtn');
const alertContainer = document.getElementById('alertContainer');
const resultsCard = document.getElementById('resultsCard');
const recentSearch = document.getElementById('recentSearch');
const typeFilter = document.getElementById('typeFilter');
const minConfidence = document.getElementById('minConfidence');
const verifiedOnly = document.getElementById('verifiedOnly');
const pageSizeSelect = document.getElementById('pageSize');
const applyFiltersBtn = document.getElementById('applyFilters');
const prevFindingsBtn = document.getElementById('prevFindings');
const nextFindingsBtn = document.getElementById('nextFindings');
const findingsPageInfo = document.getElementById('findingsPageInfo');
const exportJsonBtn = document.getElementById('exportJson');
const exportCsvBtn = document.getElementById('exportCsv');
const timelineCanvas = document.getElementById('timelineChart');
const moduleCanvas = document.getElementById('moduleChart');
const confidenceCanvas = document.getElementById('confidenceChart');

function showAlert(message, type = 'info') {
    const alert = document.createElement('div');
    alert.className = `alert alert-${type}`;
    alert.textContent = message;
    alertContainer.innerHTML = '';
    alertContainer.appendChild(alert);
    setTimeout(() => alert.remove(), 5000);
}

function formatValue(value) {
    if (value.length > 100) {
        return value.substring(0, 100) + '...';
    }
    return value;
}

async function performSearch(e) {
    e.preventDefault();
    
    const value = searchValue.value.trim();
    if (!value) return;
    
    searchBtn.disabled = true;
    searchBtn.innerHTML = '<span class="loading"></span>Buscando...';
    
    try {
        const response = await fetch(`${API_BASE}/ingest/name`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                input_type: 'auto',
                value: value,
                requester_id: 'web_user'
            })
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        recentSearch.innerHTML = `<strong>${value}</strong><br><small>${new Date().toLocaleString()}</small>`;
        
        resultsCard.style.display = 'block';
        document.getElementById('jobId').textContent = currentJobId;
        
        showAlert('Búsqueda iniciada - procesando...', 'info');
        
        pollJobStatus(true);
        pollingInterval = setInterval(() => pollJobStatus(false), 2000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = 'Buscar';
    }
}

async function pollJobStatus(isInitial = false) {
    try {
        const response = await fetch(`${API_BASE}/jobs/${currentJobId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const job = await response.json();
        
        document.getElementById('statusText').textContent = job.status;
        
        const badge = document.getElementById('statusBadge');
        const isDone = job.status === 'completed' || job.status === 'failed';

        if (job.status === 'completed') {
            badge.className = 'badge badge-success';
            badge.textContent = 'Completado';
        } else if (job.status === 'processing') {
            badge.className = 'badge badge-warning';
            badge.textContent = 'Procesando';
        } else if (job.status === 'failed') {
            badge.className = 'badge badge-danger';
            badge.textContent = 'Error';
        }

        if (isDone) {
            clearInterval(pollingInterval);
        }
        
        if (job.input_type) {
            document.getElementById('detectedType').textContent = job.input_type;
        }

        await loadFindings();
        await loadModuleRunStats();
        await loadModuleBreakdown();
        await loadConfidenceBuckets();
        
    } catch (error) {
        console.error('Polling error:', error);
    }
}

async function loadFindings() {
    try {
        const params = new URLSearchParams();
        params.set('limit', findingsPageSize);
        params.set('offset', findingsPage * findingsPageSize);
        const t = typeFilter.value.trim();
        const c = minConfidence.value.trim();
        if (t) params.set('type', t);
        if (c) params.set('min_confidence', c);
        if (verifiedOnly.checked) params.set('verified', 'true');

        const res = await fetch(`${API_BASE}/jobs/${currentJobId}/findings?${params.toString()}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const payload = await res.json();
        const findings = payload.findings || [];
        cachedFindings = findings;
        findingsTotal = payload.total || findings.length;

        updateFindingsStats(findings, findingsTotal);
        displayFindings(findings);
        updateFindingsPagination();
        drawTimeline(findings);
    } catch (error) {
        console.error('Findings load error:', error);
    }
}

async function loadModuleRunStats() {
    try {
        const res = await fetch(`${API_BASE}/jobs/${currentJobId}/module-runs`);
        if (!res.ok) return;
        const payload = await res.json();
        if (payload.module_runs) {
            document.getElementById('statIters').textContent = payload.module_runs.length;
        }
    } catch (error) {
        console.error('Module runs load error:', error);
    }
}

function displayFindings(findings) {
    const container = document.getElementById('findingsList');
    const statsContainer = document.getElementById('statsContainer');
    const findingsContainer = document.getElementById('findingsContainer');
    
    if (!findings || findings.length === 0) {
        container.innerHTML = '<p style="color: var(--accent);">Sin hallazgos</p>';
        findingsContainer.style.display = 'block';
        statsContainer.style.display = 'block';
        return;
    }

    const sorted = [...findings].sort((a, b) => (b.score || b.confidence || 0) - (a.score || a.confidence || 0));

    container.innerHTML = sorted.map(finding => {
        const type = finding.type || finding._source?.type || 'unknown';
        const value = finding.value || finding._source?.value || '';
        const source = finding.source || finding._source?.source || 'unknown';
        const confidence = finding.confidence ?? finding._source?.confidence ?? 0;
        const score = finding.score ?? finding._source?._score ?? 0;
        return `
        <div class="finding-item">
            <div class="finding-header">
                <div>
                    <span class="finding-type">${type}</span>
                    <span class="finding-score">Score: ${(score || 0).toFixed(2)}</span>
                </div>
            </div>
            <div class="finding-value">${value}</div>
            <div class="finding-meta">
                <span>Fuente: ${source}</span>
                <span>Confianza: ${((confidence || 0) * 100).toFixed(0)}%</span>
            </div>
        </div>
        `;
    }).join('');

    findingsContainer.style.display = 'block';
    statsContainer.style.display = 'block';
}

async function loadModuleBreakdown() {
    try {
        const res = await fetch(`${API_BASE}/jobs/${currentJobId}/findings/by-module`);
        if (!res.ok) return;
        const payload = await res.json();
        const items = payload.results || payload.findings_by_module || [];
        drawBarChart(moduleCanvas, items.map(i => i.module || i.module_name), items.map(i => i.count || i.total || 0), '#1f7aec');
    } catch (e) {
        console.error('Module breakdown error:', e);
    }
}

async function loadConfidenceBuckets() {
    try {
        const res = await fetch(`${API_BASE}/jobs/${currentJobId}/findings/by-confidence`);
        if (!res.ok) return;
        const payload = await res.json();
        const buckets = payload.buckets || [];
        drawBarChart(confidenceCanvas, buckets.map(b => b.label || b.range || ''), buckets.map(b => b.count || 0), '#21c36f');
    } catch (e) {
        console.error('Confidence buckets error:', e);
    }
}

function drawBarChart(canvas, labels, values, color) {
    if (!canvas || !labels || !values || labels.length === 0) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width || canvas.clientWidth;
    const h = canvas.height || 140;
    ctx.clearRect(0,0,w,h);
    if (!values.length) return;
    const maxVal = Math.max(...values, 1);
    const pad = 10;
    const barW = Math.max(6, (w - pad*2) / labels.length - 6);
    ctx.fillStyle = '#f5f7fa';
    ctx.fillRect(0,0,w,h);
    ctx.fillStyle = color || '#1f7aec';
    labels.forEach((lbl, idx) => {
        const x = pad + idx * (barW + 6);
        const barH = Math.max(4, (values[idx] / maxVal) * (h - pad*2));
        const y = h - pad - barH;
        ctx.fillRect(x, y, barW, barH);
    });
}

function updateFindingsStats(findings, totalFromServer) {
    const total = totalFromServer ?? findings.length;
    const valid = findings.length;
    const avgScore = findings.length > 0
        ? findings.reduce((sum, f) => sum + (f.score || f.confidence || 0), 0) / findings.length
        : 0;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statValid').textContent = valid;
    document.getElementById('statScore').textContent = avgScore.toFixed(2);
}

function updateFindingsPagination() {
    const totalPages = Math.max(1, Math.ceil(findingsTotal / findingsPageSize));
    findingsPageInfo.textContent = `Página ${findingsPage + 1} de ${totalPages} (${findingsTotal} hallazgos)`;
    prevFindingsBtn.disabled = findingsPage === 0;
    nextFindingsBtn.disabled = findingsPage + 1 >= totalPages;
}

function exportJson() {
    const blob = new Blob([JSON.stringify(cachedFindings, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentJobId || 'findings'}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function exportCsv() {
    if (!cachedFindings.length) return;
    const headers = ['type','value','source','confidence','score'];
    const rows = cachedFindings.map(f => [
        f.type || f._source?.type || '',
        (f.value || f._source?.value || '').toString().replace(/"/g,'""'),
        f.source || f._source?.source || '',
        f.confidence ?? f._source?.confidence ?? '',
        f.score ?? f._source?._score ?? ''
    ]);
    const csv = [headers.join(','), ...rows.map(r => r.map(v => `"${v}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentJobId || 'findings'}.csv`;
    a.click();
    URL.revokeObjectURL(url);
}

function drawTimeline(findings) {
    if (!timelineCanvas) return;
    const ctx = timelineCanvas.getContext('2d');
    ctx.clearRect(0, 0, timelineCanvas.width, timelineCanvas.height);
    if (!findings || !findings.length) return;

    const buckets = {};
    findings.forEach(f => {
        const ts = f.created_at || f._source?.created_at;
        if (!ts) return;
        const day = new Date(ts).toISOString().slice(0,10);
        buckets[day] = (buckets[day] || 0) + 1;
    });

    const entries = Object.entries(buckets).sort(([a],[b]) => a.localeCompare(b));
    const maxVal = Math.max(...entries.map(([,v]) => v));
    const pad = 10;
    const w = timelineCanvas.width || timelineCanvas.clientWidth;
    const h = timelineCanvas.height || 120;
    const barWidth = Math.max(6, (w - pad*2) / entries.length - 4);

    ctx.fillStyle = '#f5f7fa';
    ctx.fillRect(0,0,w,h);
    ctx.fillStyle = '#1f7aec';

    entries.forEach(([day, count], idx) => {
        const x = pad + idx * (barWidth + 4);
        const barHeight = Math.max(4, (count / maxVal) * (h - pad*2));
        const y = h - pad - barHeight;
        ctx.fillRect(x, y, barWidth, barHeight);
    });
}

searchForm.addEventListener('submit', performSearch);
searchValue.focus();

applyFiltersBtn.addEventListener('click', () => {
    findingsPage = 0;
    findingsPageSize = parseInt(pageSizeSelect.value, 10) || 20;
    loadFindings();
});

prevFindingsBtn.addEventListener('click', () => {
    if (findingsPage > 0) {
        findingsPage -= 1;
        loadFindings();
    }
});

nextFindingsBtn.addEventListener('click', () => {
    const totalPages = Math.ceil(findingsTotal / findingsPageSize);
    if (findingsPage + 1 < totalPages) {
        findingsPage += 1;
        loadFindings();
    }
});

exportJsonBtn.addEventListener('click', exportJson);
exportCsvBtn.addEventListener('click', exportCsv);
