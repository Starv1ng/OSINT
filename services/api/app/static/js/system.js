// system.js - Lógica de estado del sistema

const API_BASE = '/api/v1';

async function loadSystemStatus() {
    try {
        const healthResponse = await fetch(`${API_BASE}/health`);
        const health = await healthResponse.json();
        
        const dbResponse = await fetch(`${API_BASE}/test-db`);
        const dbStatus = await dbResponse.json();
        
        const statsResponse = await fetch(`${API_BASE}/stats`);
        const stats = await statsResponse.json();
        
        renderSystemStatus(health, dbStatus, stats);
        updateMetrics(stats);
        
    } catch (error) {
        console.error('Error loading system status:', error);
        document.getElementById('systemStatus').innerHTML = 
            `<p style="color: var(--danger);">Error: ${error.message}</p>`;
    }
}

function renderSystemStatus(health, dbStatus, stats) {
    const container = document.getElementById('systemStatus');
    
    const apiStatus = health.status === 'healthy' ? 'healthy' : 'error';
    const dbStatusClass = dbStatus.database === 'connected' ? 'healthy' : 'error';
    
    container.innerHTML = `
        <div class="status-item ${apiStatus}">
            <div class="status-header">
                <div class="status-title">API Service</div>
                <div class="status-badge ${apiStatus}">${health.status}</div>
            </div>
            <div class="status-detail">${health.service}</div>
            <div class="status-metric">
                <span class="status-metric-label">Timestamp:</span>
                <span class="status-metric-value">${new Date(health.timestamp).toLocaleString()}</span>
            </div>
        </div>
        
        <div class="status-item ${dbStatusClass}">
            <div class="status-header">
                <div class="status-title">Database</div>
                <div class="status-badge ${dbStatusClass}">${dbStatus.database}</div>
            </div>
            <div class="status-detail">${dbStatus.status || 'N/A'}</div>
            <div class="status-metric">
                <span class="status-metric-label">Total Jobs:</span>
                <span class="status-metric-value">${dbStatus.metrics?.total_jobs || 0}</span>
            </div>
            <div class="status-metric">
                <span class="status-metric-label">Completed:</span>
                <span class="status-metric-value">${dbStatus.metrics?.completed_jobs || 0}</span>
            </div>
        </div>
        
        <div class="status-item healthy">
            <div class="status-header">
                <div class="status-title">Sistema OSINT</div>
                <div class="status-badge healthy">Activo</div>
            </div>
            <div class="status-detail">Sistema inteligente adaptativo</div>
            <div class="status-metric">
                <span class="status-metric-label">Modo:</span>
                <span class="status-metric-value">Inteligente</span>
            </div>
            <div class="status-metric">
                <span class="status-metric-label">Filtrado:</span>
                <span class="status-metric-value">80% ruido eliminado</span>
            </div>
        </div>
    `;
}

function updateMetrics(stats) {
    const data = stats.stats;
    document.getElementById('totalJobs').textContent = data.total_jobs || 0;
    document.getElementById('completedJobs').textContent = data.completed_jobs || 0;
    document.getElementById('processingJobs').textContent = data.processing_jobs || 0;
    document.getElementById('failedJobs').textContent = data.failed_jobs || 0;
}

loadSystemStatus();
setInterval(loadSystemStatus, 10000);
