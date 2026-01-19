// search.js - Lógica de búsqueda

const API_BASE = '/api/v1';
let currentJobId = null;
let pollingInterval = null;

const searchForm = document.getElementById('searchForm');
const searchValue = document.getElementById('searchValue');
const searchBtn = document.getElementById('searchBtn');
const alertContainer = document.getElementById('alertContainer');
const resultsCard = document.getElementById('resultsCard');
const recentSearch = document.getElementById('recentSearch');

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
        
        pollJobStatus();
        pollingInterval = setInterval(pollJobStatus, 2000);
        
    } catch (error) {
        showAlert(`Error: ${error.message}`, 'error');
    } finally {
        searchBtn.disabled = false;
        searchBtn.innerHTML = 'Buscar';
    }
}

async function pollJobStatus() {
    try {
        const response = await fetch(`${API_BASE}/jobs/${currentJobId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const job = await response.json();
        
        document.getElementById('statusText').textContent = job.status;
        
        const badge = document.getElementById('statusBadge');
        if (job.status === 'completed') {
            badge.className = 'badge badge-success';
            badge.textContent = 'Completado';
            clearInterval(pollingInterval);
        } else if (job.status === 'processing') {
            badge.className = 'badge badge-warning';
            badge.textContent = 'Procesando';
        } else if (job.status === 'failed') {
            badge.className = 'badge badge-danger';
            badge.textContent = 'Error';
            clearInterval(pollingInterval);
        }
        
        if (job.input_type) {
            document.getElementById('detectedType').textContent = job.input_type;
        }
        
        if (job.findings && job.findings.length > 0) {
            displayFindings(job.findings);
            
            if (job.module_runs) {
                document.getElementById('statIters').textContent = job.module_runs.length;
            }
        }
        
    } catch (error) {
        console.error('Polling error:', error);
    }
}

function displayFindings(findings) {
    const container = document.getElementById('findingsList');
    const statsContainer = document.getElementById('statsContainer');
    const findingsContainer = document.getElementById('findingsContainer');
    
    if (findings.length === 0) {
        container.innerHTML = '<p style="color: var(--accent);">Sin hallazgos</p>';
        return;
    }
    
    findings.sort((a, b) => (b.score || 0) - (a.score || 0));
    
    const totalFindings = findings.length;
    const avgScore = findings.reduce((sum, f) => sum + (f.score || 0), 0) / totalFindings;
    
    document.getElementById('statTotal').textContent = totalFindings;
    document.getElementById('statValid').textContent = totalFindings;
    document.getElementById('statScore').textContent = avgScore.toFixed(2);
    
    container.innerHTML = findings.map(finding => `
        <div class="finding-item">
            <div class="finding-header">
                <div>
                    <span class="finding-type">${finding.type || 'unknown'}</span>
                    <span class="finding-score">Score: ${(finding.score || 0).toFixed(2)}</span>
                </div>
            </div>
            <div class="finding-value">${finding.value}</div>
            <div class="finding-meta">
                <span>Fuente: ${finding.source || 'unknown'}</span>
                <span>Confianza: ${((finding.confidence || 0) * 100).toFixed(0)}%</span>
            </div>
        </div>
    `).join('');
    
    findingsContainer.style.display = 'block';
    statsContainer.style.display = 'block';
}

searchForm.addEventListener('submit', performSearch);
searchValue.focus();
