// Cliente JS para OSINT Inteligente
class OSINTClient {
    constructor(baseURL = '/api/v1') {
        this.baseURL = baseURL;
        this.currentJobId = null;
        this.pollingInterval = null;
    }

    async search(value, inputType = 'auto', requesterId = 'web_user') {
        try {
            const response = await fetch(`${this.baseURL}/ingest/name`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    input_type: inputType,
                    value: value,
                    requester_id: requesterId
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Search error: ${error.message}`);
        }
    }

    async getJobStatus(jobId) {
        try {
            const response = await fetch(`${this.baseURL}/jobs/${jobId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Status error: ${error.message}`);
        }
    }

    async getFindings(jobId, size = 100, offset = 0) {
        try {
            const response = await fetch(`${this.baseURL}/jobs/${jobId}/findings?size=${size}&offset=${offset}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Findings error: ${error.message}`);
        }
    }

    async getModuleRuns(jobId) {
        try {
            const response = await fetch(`${this.baseURL}/jobs/${jobId}/module_runs`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Module runs error: ${error.message}`);
        }
    }

    async listJobs(limit = 20, offset = 0, status = null) {
        try {
            let url = `${this.baseURL}/jobs?limit=${limit}&offset=${offset}`;
            if (status) url += `&status=${status}`;
            
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`List jobs error: ${error.message}`);
        }
    }

    async getSystemHealth() {
        try {
            const response = await fetch(`${this.baseURL}/health`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Health check error: ${error.message}`);
        }
    }

    async getDatabaseStatus() {
        try {
            const response = await fetch(`${this.baseURL}/test-db`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Database status error: ${error.message}`);
        }
    }

    async getStats() {
        try {
            const response = await fetch(`${this.baseURL}/stats`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            throw new Error(`Stats error: ${error.message}`);
        }
    }

    pollStatus(jobId, callback, interval = 2000) {
        this.currentJobId = jobId;
        
        const poll = async () => {
            try {
                const status = await this.getJobStatus(jobId);
                callback(null, status);
                
                if (status.status === 'completed' || status.status === 'failed') {
                    this.stopPolling();
                }
            } catch (error) {
                callback(error, null);
            }
        };

        // Polling inicial
        poll();
        
        // Polling periódico
        this.pollingInterval = setInterval(poll, interval);
    }

    stopPolling() {
        if (this.pollingInterval) {
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }

    // Utilidades
    static formatScore(score) {
        if (!score) return '0.00';
        return (score * 1).toFixed(2);
    }

    static formatConfidence(confidence) {
        if (!confidence) return '0%';
        return `${(confidence * 100).toFixed(0)}%`;
    }

    static formatDate(dateString) {
        if (!dateString) return '-';
        return new Date(dateString).toLocaleString();
    }

    static formatStatus(status) {
        const statuses = {
            'completed': { text: 'Completado', class: 'badge-success' },
            'processing': { text: 'Procesando', class: 'badge-warning' },
            'failed': { text: 'Error', class: 'badge-danger' },
            'accepted': { text: 'Aceptado', class: 'badge-info' }
        };
        return statuses[status] || { text: status, class: 'badge-info' };
    }
}

// Exportar globalmente
window.OSINTClient = OSINTClient;
