// system.js - Lógica de estado del sistema
const API_BASE = '/api/v2';

async function loadSystemStatus() {
	try {
		const [healthRes, statsRes, jobsRes] = await Promise.all([
			fetch(`${API_BASE}/health`),
			fetch(`${API_BASE}/stats`),
			fetch(`${API_BASE}/jobs?limit=200&offset=0`)
		]);

		if (!healthRes.ok || !statsRes.ok) throw new Error('No se pudo obtener estado del sistema');

		const health = await healthRes.json();
		const stats = await statsRes.json();

		let jobStatusCounts = { completed: 0, processing: 0, failed: 0, accepted: 0 };
		if (jobsRes.ok) {
			const jobsPayload = await jobsRes.json();
			jobStatusCounts = jobsPayload.jobs.reduce((acc, job) => {
				acc[job.status] = (acc[job.status] || 0) + 1;
				return acc;
			}, jobStatusCounts);
		}

		renderSystemStatus(health, stats);
		updateMetrics(stats, jobStatusCounts);
	} catch (error) {
		const container = document.getElementById('systemStatus');
		container.innerHTML = `<p style="color: var(--danger);">Error: ${error.message}</p>`;
	}
}

function renderSystemStatus(health, stats) {
	const container = document.getElementById('systemStatus');

	const apiStatus = health.status === 'healthy' ? 'healthy' : 'degraded';
	const postgresStatus = health.components?.postgres === 'up' ? 'healthy' : 'error';
	const esStatus = health.components?.elasticsearch === 'up' ? 'healthy' : 'error';
	const neo4jStatus = health.components?.neo4j === 'up' ? 'healthy' : 'error';

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

		<div class="status-item ${postgresStatus}">
			<div class="status-header">
				<div class="status-title">PostgreSQL</div>
				<div class="status-badge ${postgresStatus}">${health.components?.postgres || 'unknown'}</div>
			</div>
			<div class="status-metric">
				<span class="status-metric-label">Jobs:</span>
				<span class="status-metric-value">${stats.total_jobs || 0}</span>
			</div>
		</div>

		<div class="status-item ${esStatus}">
			<div class="status-header">
				<div class="status-title">Elasticsearch</div>
				<div class="status-badge ${esStatus}">${health.components?.elasticsearch || 'unknown'}</div>
			</div>
			<div class="status-metric">
				<span class="status-metric-label">Findings:</span>
				<span class="status-metric-value">${stats.total_findings || 0}</span>
			</div>
		</div>

		<div class="status-item ${neo4jStatus}">
			<div class="status-header">
				<div class="status-title">Neo4j</div>
				<div class="status-badge ${neo4jStatus}">${health.components?.neo4j || 'unknown'}</div>
			</div>
			<div class="status-metric">
				<span class="status-metric-label">Entities:</span>
				<span class="status-metric-value">${stats.neo4j_stats?.entities_count || 0}</span>
			</div>
		</div>

		<div class="status-item healthy">
			<div class="status-header">
				<div class="status-title">Sistema OSINT</div>
				<div class="status-badge healthy">Activo</div>
			</div>
			<div class="status-detail">Sistema inteligente adaptativo</div>
			<div class="status-metric">
				<span class="status-metric-label">Endpoints:</span>
				<span class="status-metric-value">${Object.keys(health.endpoints || {}).length}</span>
			</div>
		</div>
	`;
}

function updateMetrics(stats, jobStatusCounts) {
	document.getElementById('totalJobs').textContent = stats.total_jobs || 0;
	document.getElementById('completedJobs').textContent = jobStatusCounts.completed || 0;
	document.getElementById('processingJobs').textContent = jobStatusCounts.processing || 0;
	document.getElementById('failedJobs').textContent = jobStatusCounts.failed || 0;
}

loadSystemStatus();
setInterval(loadSystemStatus, 10000);
