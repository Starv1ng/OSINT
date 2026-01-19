// jobs.js - Lógica de historial de trabajos

const API_BASE = '/api/v2';
let currentPage = 0;
const pageSize = 20;
let allJobs = [];

async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE}/jobs?limit=${pageSize}&offset=${currentPage * pageSize}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        allJobs = data.jobs;
        
        renderJobs();
        updatePagination(data.pagination);
        
    } catch (error) {
        document.getElementById('jobsList').innerHTML = `<p style="color: var(--danger);">Error: ${error.message}</p>`;
    }
}

function renderJobs() {
    const container = document.getElementById('jobsList');
    const filter = document.getElementById('searchFilter').value.toLowerCase();
    const statusFilter = document.getElementById('statusFilter').value;
    
    const filtered = allJobs.filter(job => {
        const matchesSearch = job.input_value.toLowerCase().includes(filter);
        const matchesStatus = !statusFilter || job.status === statusFilter;
        return matchesSearch && matchesStatus;
    });
    
    if (filtered.length === 0) {
        container.innerHTML = '<p style="color: var(--accent);">No hay búsquedas</p>';
        return;
    }
    
    container.innerHTML = filtered.map(job => {
        const statusColors = {
            'completed': 'badge-success',
            'processing': 'badge-warning',
            'failed': 'badge-danger',
            'accepted': 'badge-info'
        };
        
        const statusColor = statusColors[job.status] || 'badge-info';
        const createdDate = new Date(job.created_at).toLocaleString();
        
        return `
            <div class="job-card" onclick="toggleDetails('${job.job_id}')">
                <div class="job-header">
                    <div class="job-value">${job.input_value}</div>
                    <span class="badge ${statusColor}">${job.status}</span>
                </div>
                
                <div class="job-meta">
                    <span>ID: ${job.job_id}</span>
                    <span class="job-type">${job.input_type}</span>
                    <span>Fecha: ${createdDate}</span>
                </div>
                
                <div class="job-details" id="details-${job.job_id}">
                    <div class="detail-row">
                        <div class="detail-label">Job ID:</div>
                        <div class="detail-value">${job.job_id}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Tipo:</div>
                        <div class="detail-value">${job.input_type}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Valor:</div>
                        <div class="detail-value">${job.input_value}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Estado:</div>
                        <div class="detail-value">${job.status}</div>
                    </div>
                    <div class="detail-row">
                        <div class="detail-label">Creado:</div>
                        <div class="detail-value">${createdDate}</div>
                    </div>
                    <div style="margin-top: 12px;">
                        <button class="btn-primary" onclick="viewJob('${job.job_id}'); event.stopPropagation();" style="font-size: 12px;">
                            Ver Detalles Completos
                        </button>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function toggleDetails(jobId) {
    const details = document.getElementById(`details-${jobId}`);
    details.classList.toggle('show');
}

async function viewJob(jobId) {
    try {
        const response = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const job = await response.json();
        alert(`Job: ${jobId}\nStatus: ${job.status}\nFindings: ${job.findings ? job.findings.length : 0}`);
        
    } catch (error) {
        alert(`Error: ${error.message}`);
    }
}

function updatePagination(pagination) {
    const pageInfo = document.getElementById('pageInfo');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    pageInfo.textContent = `Página ${currentPage + 1} de ${Math.ceil(pagination.total / pageSize)} (${pagination.total} total)`;
    
    prevBtn.style.display = currentPage > 0 ? 'block' : 'none';
    nextBtn.style.display = pagination.has_more ? 'block' : 'none';
    
    prevBtn.onclick = () => {
        currentPage--;
        loadJobs();
    };
    
    nextBtn.onclick = () => {
        currentPage++;
        loadJobs();
    };
}

document.getElementById('searchFilter').addEventListener('input', renderJobs);
document.getElementById('statusFilter').addEventListener('change', renderJobs);

loadJobs();
setInterval(loadJobs, 5000);
