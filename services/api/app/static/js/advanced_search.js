// Advanced Search JavaScript

// Metadata served by backend (/api/v2/modules/metadata).
// No static duplication: UI depends on backend-provided definitions.
let moduleMetadata = {};
let metadataLoaded = false;
let metadataLoadError = null;

// Hints por tipo de búsqueda
const SEARCH_TYPE_HINTS = {
    'person': 'Ejemplo: Juan Pérez, John Doe',
    'email': 'Ejemplo: usuario@ejemplo.com',
    'username': 'Ejemplo: @usuario, username123',
    'phone': 'Ejemplo: +1234567890, (555) 123-4567',
    'domain': 'Ejemplo: ejemplo.com',
    'ip': 'Ejemplo: 192.168.1.1, 8.8.8.8',
    'company': 'Ejemplo: Microsoft, Google Inc.',
    'password': 'Ejemplo: hash SHA-1 o contraseña a verificar',
    'url': 'Ejemplo: https://ejemplo.com/perfil'
};

document.addEventListener('DOMContentLoaded', function() {
// Estado de la aplicación
let selectedModules = new Set();
let userApiKeys = {};
let currentJobId = null;
let pollingInterval = null;
let pollingErrorCount = 0;
let lastStatsSnapshot = { findings: -1, indicators: -1, modules: -1 };

// Inicialización
document.addEventListener('DOMContentLoaded', async function() {
    initializeEventListeners();
    await initializeApp();
});

async function initializeApp() {
    try {
        await Promise.all([loadModulesMetadata(), loadUserApiKeys()]);
    } catch (error) {
        renderInlineAlert('No se pudo cargar la configuración inicial. Intenta recargar la página.', 'warning');
    }

    const searchType = document.getElementById('searchType');
    if (searchType.value) {
        loadModulesForType(searchType.value);
    }
}

function initializeEventListeners() {
    // Cambio de tipo de búsqueda
    document.getElementById('searchType').addEventListener('change', function(e) {
        const type = e.target.value;
        updateValueHint(type);
        loadModulesForType(type);
    });

    // Threshold slider
    document.getElementById('relevanceThreshold').addEventListener('input', function(e) {
        document.getElementById('thresholdValue').textContent = e.target.value;
    });

    // Botones de control de módulos
    document.getElementById('selectAllModules').addEventListener('click', selectAllModules);
    document.getElementById('deselectAllModules').addEventListener('click', deselectAllModules);
    document.getElementById('selectRecommended').addEventListener('click', selectRecommendedModules);

    // Botones de acción
    document.getElementById('resetForm').addEventListener('click', resetForm);
    document.getElementById('savePreset').addEventListener('click', savePreset);
    document.getElementById('startSearch').addEventListener('click', startSearch);

    // Tabs
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    const shortestBtn = document.getElementById('shortestPathBtn');
    if (shortestBtn) {
        shortestBtn.addEventListener('click', handleShortestPath);
    }
}

function updateValueHint(type) {
    const hint = SEARCH_TYPE_HINTS[type] || '';
    document.getElementById('valueHint').textContent = hint;
}

async function loadModulesMetadata() {
    metadataLoaded = false;
    metadataLoadError = null;

    try {
        const response = await fetch('/api/v2/modules/metadata');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        moduleMetadata = data.modules || {};
        metadataLoaded = true;
        console.info('[advanced-search] Metadata cargada desde /api/v2/modules/metadata', {
            total: data.total_modules || Object.keys(moduleMetadata).length
        });
    } catch (error) {
        metadataLoadError = error;
        moduleMetadata = {};
        metadataLoaded = false;
        renderInlineAlert('No se pudo cargar la metadata de módulos desde el backend.', 'warning');
        console.error('Error loading modules metadata:', error);
        throw error;
    }
}

function loadModulesForType(searchType) {
    if (!searchType) return;

    const modulesList = document.getElementById('modulesList');
    modulesList.innerHTML = '';
    selectedModules.clear();

    if (!Object.keys(moduleMetadata || {}).length) {
        modulesList.innerHTML = '<p class="hint">Sin metadata de módulos disponible. Reintenta más tarde.</p>';
        return;
    }

    // Filtrar módulos compatibles con el tipo de búsqueda
    const compatibleModules = Object.entries(moduleMetadata)
        .filter(([, config]) => Array.isArray(config.types) && config.types.includes(searchType))
        .sort((a, b) => (b[1].priority || 0) - (a[1].priority || 0));

    if (compatibleModules.length === 0) {
        modulesList.innerHTML = '<p class="hint">No hay módulos compatibles para este tipo de búsqueda.</p>';
        return;
    }

    compatibleModules.forEach(([moduleKey, config]) => {
        const moduleCard = createModuleCard(moduleKey, config, searchType);
        modulesList.appendChild(moduleCard);
    });

    // Auto-seleccionar módulos recomendados
    selectRecommendedModules();
    checkRequiredApiKeys();
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-button').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.toggle('active', tab.id === tabId);
    });
}

function createModuleCard(moduleKey, config, currentType) {
    const card = document.createElement('div');
    card.className = 'module-card';
    card.dataset.module = moduleKey;

    const priority = config.priority ?? 0;
    const isRecommended = priority >= 8;
    const requiresAuth = Boolean(config.requiresAuth);

    if (isRecommended) {
        card.classList.add('recommended');
    }
    if (requiresAuth) {
        card.classList.add('requires-auth');
    }

    card.dataset.apikey = config.apiKeyName || '';

    card.innerHTML = `
        <div class="module-header">
            <input type="checkbox" class="module-checkbox" id="module_${moduleKey}">
            <label class="module-name" for="module_${moduleKey}">${config.name || moduleKey}</label>
            ${isRecommended ? '<span class="module-badge recommended">Recomendado</span>' : ''}
            ${requiresAuth ? '<span class="module-badge auth-required">API Key</span>' : ''}
        </div>
        <div class="module-description">${config.description || 'Módulo disponible en backend'}</div>
        <div class="module-meta">
            <span>${config.category || 'General'}</span>
            <span>Prioridad: ${priority}</span>
        </div>
    `;

    const checkbox = card.querySelector('.module-checkbox');
    checkbox.addEventListener('change', function() {
        if (this.checked) {
            selectedModules.add(moduleKey);
            card.classList.add('selected');
        } else {
            selectedModules.delete(moduleKey);
            card.classList.remove('selected');
        }
        checkRequiredApiKeys();
    });

    card.addEventListener('click', function(e) {
        if (e.target !== checkbox) {
            checkbox.checked = !checkbox.checked;
            checkbox.dispatchEvent(new Event('change'));
        }
    });

    return card;
}

function selectAllModules() {
    document.querySelectorAll('.module-checkbox').forEach(checkbox => {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change'));
    });
}

function deselectAllModules() {
    document.querySelectorAll('.module-checkbox').forEach(checkbox => {
        checkbox.checked = false;
        checkbox.dispatchEvent(new Event('change'));
    });
}

function selectRecommendedModules() {
    deselectAllModules();
    document.querySelectorAll('.module-card.recommended .module-checkbox').forEach(checkbox => {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change'));
    });
}

async function loadUserApiKeys() {
    try {
        const response = await fetch('/api/v2/user/api-keys');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        userApiKeys = data.api_keys || {};
        console.info('[advanced-search] API keys cargadas desde /api/v2/user/api-keys');
    } catch (error) {
        renderInlineAlert('No se pudieron cargar tus API Keys. Continúa solo si no necesitas claves.', 'warning');
        console.error('Error loading API keys:', error);
    }
}

function checkRequiredApiKeys() {
    const requiredKeys = [];
    const apiKeysSection = document.getElementById('apiKeysSection');
    const keysList = document.getElementById('requiredApiKeysList');

    selectedModules.forEach(moduleKey => {
        const config = moduleMetadata[moduleKey];
        if (config && config.requiresAuth) {
            const hasKey = userApiKeys[config.apiKeyName];
            if (!hasKey) {
                requiredKeys.push({
                    module: config.name,
                    keyName: config.apiKeyName
                });
            }
        }
    });

    if (requiredKeys.length > 0) {
        apiKeysSection.style.display = 'block';
        keysList.innerHTML = requiredKeys.map(key => 
            `<li><strong>${key.module}</strong>: ${key.keyName}</li>`
        ).join('');
    } else {
        apiKeysSection.style.display = 'none';
    }

    return requiredKeys.length === 0;
}

async function startSearch() {
    // Validación
    const searchType = document.getElementById('searchType').value;
    const searchValue = document.getElementById('searchValue').value.trim();

    renderInlineAlert('');

    if (!Object.keys(moduleMetadata || {}).length) {
        renderInlineAlert('No hay metadata de módulos disponible. Intenta recargar la página.', 'danger');
        return;
    }

    if (!searchType) {
        alert('Por favor seleccione un tipo de búsqueda');
        return;
    }

    if (!searchValue) {
        alert('Por favor ingrese un valor a buscar');
        return;
    }

    if (selectedModules.size === 0) {
        alert('Por favor seleccione al menos un módulo');
        return;
    }

    if (!checkRequiredApiKeys()) {
        alert('Debe configurar las API Keys requeridas antes de continuar');
        return;
    }

    // Construir payload
    const searchData = {
        input_type: searchType,
        value: searchValue,
        additional_context: document.getElementById('additionalContext').value.trim(),
        selected_modules: Array.from(selectedModules),
        config: {
            execution_mode: document.getElementById('executionMode').value,
            max_iterations: parseInt(document.getElementById('maxIterations').value),
            relevance_threshold: parseFloat(document.getElementById('relevanceThreshold').value),
            validate_profiles: document.getElementById('validateProfiles').checked,
            extract_indicators: document.getElementById('extractIndicators').checked
        }
    };

    try {
        // Enviar búsqueda
        const response = await fetch('/api/v2/search/advanced', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(searchData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Error al iniciar búsqueda');
        }

        const result = await response.json();
        currentJobId = result.job_id;
        pollingErrorCount = 0;
        lastStatsSnapshot = { findings: -1, indicators: -1, modules: -1 };

        // Mostrar sección de resultados
        document.getElementById('resultsContainer').style.display = 'block';
        document.getElementById('jobId').textContent = currentJobId;
        document.getElementById('jobStatus').textContent = 'Procesando...';
        document.getElementById('jobStatus').className = 'status-badge processing';

        // Iniciar polling
        startJobPolling(currentJobId);

        console.info('[advanced-search] Búsqueda avanzada iniciada', { jobId: currentJobId, modules: searchData.selected_modules });

        // Scroll a resultados
        document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });

    } catch (error) {
        renderInlineAlert(error.message || 'Error al iniciar búsqueda', 'danger');
        console.error('Search error:', error);
    }
}

function startJobPolling(jobId) {
    if (pollingInterval) {
        clearInterval(pollingInterval);
    }

    pollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/v2/jobs/${jobId}`);
            if (!response.ok) {
                pollingErrorCount += 1;
                renderInlineAlert(`No se pudo consultar el estado (intento ${pollingErrorCount}).`, 'warning');

                if (pollingErrorCount >= 3) {
                    clearInterval(pollingInterval);
                    pollingInterval = null;
                }
                return;
            }

            pollingErrorCount = 0;
            renderInlineAlert('');
            const jobData = await response.json();
            updateJobStatus(jobData);

            // Detener polling si el job terminó
            if (['completed', 'failed', 'cancelled', 'paused'].includes(jobData.status)) {
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        } catch (error) {
            pollingErrorCount += 1;
            renderInlineAlert('Error consultando el estado del job.', 'warning');
            console.error('Polling error:', error);
        }
    }, 2000); // Poll cada 2 segundos
}

function updateJobStatus(jobData) {
    // Actualizar badge de estado
    const statusBadge = document.getElementById('jobStatus');
    const normalizedStatus = (jobData.status || 'processing').toUpperCase();
    statusBadge.textContent = normalizedStatus;
    statusBadge.className = `status-badge ${jobData.status || 'processing'}`;

    // Actualizar stats
    const findingsCount = jobData.findings_count || 0;
    const indicatorsCount = jobData.indicators_count || 0;
    const modulesCount = jobData.module_runs_count || 0;

    document.getElementById('findingsCount').textContent = findingsCount;
    document.getElementById('indicatorsCount').textContent = indicatorsCount;
    document.getElementById('modulesCount').textContent = modulesCount;

    const indicatorsPanelCount = document.getElementById('indicatorsPanelCount');
    const moduleRunsPanelCount = document.getElementById('moduleRunsPanelCount');
    if (indicatorsPanelCount) {
        indicatorsPanelCount.textContent = `${indicatorsCount} total`;
    }
    if (moduleRunsPanelCount) {
        moduleRunsPanelCount.textContent = `${modulesCount} total`;
    }

    // Actualizar barra de progreso
    const progress = jobData.status === 'completed' ? 100 :
                    jobData.status === 'processing' ? 60 :
                    jobData.status === 'running' ? 40 :
                    10;
    document.getElementById('progressFill').style.width = progress + '%';

    if (findingsCount !== lastStatsSnapshot.findings) {
        lastStatsSnapshot.findings = findingsCount;
        loadFindings(currentJobId);
    }

    if (indicatorsCount !== lastStatsSnapshot.indicators) {
        lastStatsSnapshot.indicators = indicatorsCount;
        loadIndicators(currentJobId);
    }

    if (modulesCount !== lastStatsSnapshot.modules) {
        lastStatsSnapshot.modules = modulesCount;
        loadModuleRuns(currentJobId);
    }

    // Always refresh graph panel when status changes to completed
    if (jobData.status === 'completed') {
        loadGraph(currentJobId);
    }
}

async function loadFindings(jobId) {
    try {
        const response = await fetch(`/api/v2/jobs/${jobId}/findings`);
        if (!response.ok) {
            renderInlineAlert(`No se pudieron cargar los hallazgos (${response.status}).`, 'warning');
            return;
        }

        const data = await response.json();
        displayFindings(data.findings || []);
        console.debug('[advanced-search] Findings recibidos', { count: (data.findings || []).length });
    } catch (error) {
        renderInlineAlert('Error al cargar hallazgos.', 'danger');
        console.error('Error loading findings:', error);
    }
}

function displayFindings(findings) {
    const findingsList = document.getElementById('findingsList');
    
    if (findings.length === 0) {
        findingsList.innerHTML = '<p>No se encontraron resultados aún...</p>';
        return;
    }

    findingsList.innerHTML = findings.map(finding => {
        const confidence = Number(finding.confidence || 0);
        const confidenceClass = confidence >= 0.8 ? 'confidence-high' : confidence >= 0.5 ? 'confidence-medium' : 'confidence-low';
        const confidenceLabel = isNaN(confidence) ? 'N/D' : `${(confidence * 100).toFixed(0)}%`;

        return `
            <div class="finding-item">
                <div class="finding-header">
                    <span class="finding-module">${escapeHtml(finding.type || 'finding')}</span>
                    <span class="finding-confidence ${confidenceClass}">Conf: ${confidenceLabel}</span>
                </div>
                <div class="finding-content">
                    <p><strong>Valor:</strong> ${escapeHtml(finding.value || '')}</p>
                    <p class="hint"><strong>Módulo:</strong> ${escapeHtml(finding.module_name || 'unknown')}</p>
                    ${finding.metadata ? `<p class="hint">${Object.entries(finding.metadata).map(([k, v]) => `<strong>${escapeHtml(k)}:</strong> ${escapeHtml(String(v))}`).join(' | ')}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

async function loadIndicators(jobId) {
    const indicatorsList = document.getElementById('indicatorsList');
    if (!jobId || !indicatorsList) return;

    try {
        const response = await fetch(`/api/v2/jobs/${jobId}/indicators`);
        if (!response.ok) {
            console.warn('No se pudieron cargar los indicadores');
            return;
        }

        const data = await response.json();
        renderIndicators(data.indicators || []);
        document.getElementById('indicatorsCount').textContent = data.count || (data.indicators ? data.indicators.length : 0);
        console.debug('[advanced-search] Indicadores recibidos', { count: data.count });
    } catch (error) {
        console.error('Error loading indicators:', error);
    }
}

function renderIndicators(indicators) {
    const container = document.getElementById('indicatorsList');
    if (!container) return;

    if (!indicators || indicators.length === 0) {
        container.innerHTML = '<p class="hint">Sin indicadores aún.</p>';
        return;
    }

    container.innerHTML = indicators.map(indicator => `
        <div class="mini-card">
            <div class="mini-card-title">${escapeHtml(indicator.type || 'indicator')}</div>
            <div class="mini-card-body">
                <p><strong>Valor:</strong> ${escapeHtml(indicator.value || '')}</p>
                ${indicator.source_module ? `<p class="hint">Módulo: ${escapeHtml(indicator.source_module)}</p>` : ''}
            </div>
        </div>
    `).join('');
}

async function loadModuleRuns(jobId) {
    const moduleRunsList = document.getElementById('moduleRunsList');
    if (!jobId || !moduleRunsList) return;

    try {
        const response = await fetch(`/api/v2/jobs/${jobId}/module-runs`);
        if (!response.ok) {
            console.warn('No se pudieron cargar las ejecuciones de módulos');
            return;
        }

        const data = await response.json();
        renderModuleRuns(data.module_runs || []);
        document.getElementById('modulesCount').textContent = data.total || (data.module_runs ? data.module_runs.length : 0);
        console.debug('[advanced-search] Ejecuciones de módulos recibidas', { total: data.total });
    } catch (error) {
        console.error('Error loading module runs:', error);
    }
}

async function loadGraph(jobId) {
    const graphContent = document.getElementById('graphContent');
    const graphCounter = document.getElementById('graphCounter');
    if (!graphContent) return;

    try {
        const response = await fetch(`/api/v2/jobs/${jobId}/graph`);
        if (!response.ok) {
            graphContent.innerHTML = '<p class="hint">No se pudo cargar el grafo.</p>';
            return;
        }

        const data = await response.json();
        const graph = data.graph || {};
        const nodes = graph.nodes || graph.vertices || [];
        const edges = graph.relationships || graph.edges || [];

        graphCounter.textContent = `${nodes.length} nodos / ${edges.length} relaciones`;

        if (!nodes.length && !edges.length) {
            graphContent.innerHTML = '<p class="hint">Grafo vacío para este job.</p>';
            return;
        }

        graphContent.innerHTML = `
            <div class="mini-card">
                <div class="mini-card-title">Nodos (hasta 8)</div>
                <div class="mini-card-body">
                    ${nodes.slice(0, 8).map(n => escapeHtml(n.name || n.id || JSON.stringify(n))).join('<br>')}
                </div>
            </div>
            <div class="mini-card">
                <div class="mini-card-title">Relaciones (hasta 8)</div>
                <div class="mini-card-body">
                    ${edges.slice(0, 8).map(e => escapeHtml(e.type || `${e.source} -> ${e.target}`)).join('<br>')}
                </div>
            </div>
        `;
    } catch (error) {
        graphContent.innerHTML = '<p class="hint">Error cargando grafo.</p>';
        console.error('Error loading graph:', error);
    }
}

async function handleShortestPath() {
    if (!currentJobId) return;
    const source = (document.getElementById('graphSource') || {}).value || '';
    const target = (document.getElementById('graphTarget') || {}).value || '';

    if (!source || !target) {
        renderInlineAlert('Define origen y destino para calcular camino más corto.', 'warning');
        return;
    }

    const pathContent = document.getElementById('pathContent');
    if (!pathContent) return;

    pathContent.innerHTML = '<p class="hint">Consultando camino...</p>';

    try {
        const response = await fetch(`/api/v2/jobs/${currentJobId}/graph/shortest-path?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`);
        if (!response.ok) {
            pathContent.innerHTML = '<p class="hint">No se pudo obtener el camino.</p>';
            return;
        }

        const data = await response.json();
        const path = data.path || data.route || [];

        if (!path.length) {
            pathContent.innerHTML = '<p class="hint">Sin ruta entre los nodos indicados.</p>';
            return;
        }

        pathContent.innerHTML = path.map(step => `
            <div class="mini-card">
                <div class="mini-card-title">${escapeHtml(step.name || step.id || 'nodo')}</div>
                <div class="mini-card-body">${escapeHtml(step.type || '')}</div>
            </div>
        `).join('');
    } catch (error) {
        pathContent.innerHTML = '<p class="hint">Error consultando camino.</p>';
        console.error('Error shortest path:', error);
    }
}

function renderModuleRuns(moduleRuns) {
    const container = document.getElementById('moduleRunsList');
    if (!container) return;

    if (!moduleRuns || moduleRuns.length === 0) {
        container.innerHTML = '<p class="hint">Aún no hay módulos ejecutados.</p>';
        return;
    }

    container.innerHTML = moduleRuns.map(run => {
        const status = escapeHtml(run.status || 'desconocido');
        const moduleName = escapeHtml(run.module_name || run.module || 'módulo');
        const duration = run.duration_seconds ? `${run.duration_seconds}s` : (run.duration || '');
        const started = run.started_at || run.started || run.created_at;
        const finished = run.finished_at || run.ended_at;

        return `
            <div class="mini-card">
                <div class="mini-card-title">${moduleName}</div>
                <div class="mini-card-body">
                    <p><strong>Estado:</strong> ${status}</p>
                    ${duration ? `<p class="hint">Duración: ${escapeHtml(String(duration))}</p>` : ''}
                    ${started ? `<p class="hint">Inicio: ${escapeHtml(formatTimestamp(started))}</p>` : ''}
                    ${finished ? `<p class="hint">Fin: ${escapeHtml(formatTimestamp(finished))}</p>` : ''}
                </div>
            </div>
        `;
    }).join('');
}

function resetForm() {
    document.getElementById('searchType').value = '';
    document.getElementById('searchValue').value = '';
    document.getElementById('additionalContext').value = '';
    document.getElementById('executionMode').value = 'normal';
    document.getElementById('maxIterations').value = '5';
    document.getElementById('relevanceThreshold').value = '0.5';
    document.getElementById('thresholdValue').textContent = '0.5';
    document.getElementById('validateProfiles').checked = false;
    document.getElementById('extractIndicators').checked = true;
    document.getElementById('modulesList').innerHTML = '';
    document.getElementById('resultsContainer').style.display = 'none';
    document.getElementById('findingsList').innerHTML = '';
    const indicatorsList = document.getElementById('indicatorsList');
    const moduleRunsList = document.getElementById('moduleRunsList');
    const graphContent = document.getElementById('graphContent');
    const pathContent = document.getElementById('pathContent');
    if (graphContent) graphContent.innerHTML = '';
    if (pathContent) pathContent.innerHTML = '';
    if (indicatorsList) indicatorsList.innerHTML = '';
    if (moduleRunsList) moduleRunsList.innerHTML = '';
    renderInlineAlert('');
    selectedModules.clear();
}

function savePreset() {
    const preset = {
        searchType: document.getElementById('searchType').value,
        selectedModules: Array.from(selectedModules),
        config: {
            executionMode: document.getElementById('executionMode').value,
            maxIterations: document.getElementById('maxIterations').value,
            relevanceThreshold: document.getElementById('relevanceThreshold').value,
            validateProfiles: document.getElementById('validateProfiles').checked,
            extractIndicators: document.getElementById('extractIndicators').checked
        }
    };

    localStorage.setItem('osint_search_preset', JSON.stringify(preset));
    alert('Configuración guardada exitosamente');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function formatTimestamp(value) {
    try {
        return new Date(value).toLocaleString('es-ES');
    } catch (error) {
        return String(value || '');
    }
}

function renderInlineAlert(message, type = 'info') {
    const alertBox = document.getElementById('resultsAlerts');
    if (!alertBox) return;

    if (!message) {
        alertBox.style.display = 'none';
        alertBox.textContent = '';
        alertBox.className = 'inline-alert';
        return;
    }

    alertBox.textContent = message;
    alertBox.className = `inline-alert ${type}`;
    alertBox.style.display = 'block';
}
});