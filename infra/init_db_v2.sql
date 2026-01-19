-- ============================================================
-- OSINT v2.0 - PostgreSQL Database Schema
-- Date: 2026-01-19
-- Purpose: Normalized schema for OSINT findings, indicators, 
--          deduplication, audit, and lineage tracking
-- ============================================================

-- Ensure jobs table exists (updated version)
CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    requester_id TEXT,
    input_type TEXT NOT NULL,
    input_value TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'accepted',
    progress REAL DEFAULT 0,
    result JSONB,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- CORE TABLES
-- ============================================================

CREATE TABLE findings (
    finding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    module_run_id UUID,
    module_name TEXT NOT NULL,
    type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    confidence FLOAT CHECK (confidence >= 0 AND confidence <= 1),
    relevance_score FLOAT CHECK (relevance_score >= 0 AND relevance_score <= 1),
    verified BOOLEAN DEFAULT false,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    iteration INT DEFAULT 1,
    source_url TEXT,
    raw_text TEXT,
    metadata JSONB DEFAULT '{}',
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    soft_deleted BOOLEAN DEFAULT false,
    dup_of_id UUID REFERENCES findings(finding_id),
    created_by TEXT
);

CREATE TABLE indicators (
    indicator_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    data_type VARCHAR(20),
    source_finding_id UUID REFERENCES findings(finding_id) ON DELETE SET NULL,
    confidence FLOAT,
    first_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INT DEFAULT 1,
    created_by TEXT,
    UNIQUE(normalized_value, type)
);

CREATE TABLE entity_references (
    reference_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id UUID NOT NULL REFERENCES indicators(indicator_id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
    context TEXT,
    position INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE module_runs (
    module_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    module_name TEXT NOT NULL,
    module_version TEXT,
    status VARCHAR(20) DEFAULT 'started',
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    duration_ms INT,
    items_processed INT DEFAULT 0,
    findings_count INT DEFAULT 0,
    errors TEXT,
    raw_result JSONB,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TRACKING TABLES
-- ============================================================

CREATE TABLE execution_metrics (
    metric_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_run_id UUID NOT NULL REFERENCES module_runs(module_run_id) ON DELETE CASCADE,
    metric_name VARCHAR(100),
    metric_value FLOAT,
    recorded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE data_lineage (
    lineage_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_finding_id UUID REFERENCES findings(finding_id) ON DELETE SET NULL,
    derived_finding_id UUID REFERENCES findings(finding_id) ON DELETE CASCADE,
    transformation TEXT,
    iteration INT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE indicators_relationships (
    relationship_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    indicator_id_1 UUID NOT NULL REFERENCES indicators(indicator_id) ON DELETE CASCADE,
    indicator_id_2 UUID NOT NULL REFERENCES indicators(indicator_id) ON DELETE CASCADE,
    relationship_type TEXT,
    confidence FLOAT,
    evidence TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(indicator_id_1, indicator_id_2, relationship_type)
);

-- ============================================================
-- QUALITY & COMPLIANCE TABLES
-- ============================================================

CREATE TABLE job_deduplication (
    dedup_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    indicator_hash TEXT NOT NULL,
    finding_id UUID NOT NULL REFERENCES findings(finding_id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(job_id, indicator_hash)
);

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID,
    action VARCHAR(100),
    resource_type VARCHAR(50),
    resource_id TEXT,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE system_config (
    config_id SERIAL PRIMARY KEY,
    config_key VARCHAR(100) UNIQUE NOT NULL,
    config_value JSONB,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- ============================================================
-- INDICES (CRITICAL FOR PERFORMANCE)
-- ============================================================

-- Findings indices
CREATE INDEX idx_findings_job_id ON findings(job_id);
CREATE INDEX idx_findings_type ON findings(type);
CREATE INDEX idx_findings_confidence ON findings(confidence DESC);
CREATE INDEX idx_findings_created_at ON findings(created_at DESC);
CREATE INDEX idx_findings_normalized_value ON findings(normalized_value);
CREATE INDEX idx_findings_status ON findings(verified, soft_deleted);
CREATE INDEX idx_findings_module_name ON findings(module_name);

-- Indicators indices
CREATE INDEX idx_indicators_normalized_value ON indicators(normalized_value);
CREATE INDEX idx_indicators_type ON indicators(type);
CREATE INDEX idx_indicators_finding_id ON indicators(source_finding_id);
CREATE INDEX idx_indicators_first_seen ON indicators(first_seen DESC);

-- Entity references indices
CREATE INDEX idx_entity_refs_indicator ON entity_references(indicator_id);
CREATE INDEX idx_entity_refs_finding ON entity_references(finding_id);

-- Module runs indices
CREATE INDEX idx_module_runs_job_id ON module_runs(job_id);
CREATE INDEX idx_module_runs_status ON module_runs(status);
CREATE INDEX idx_module_runs_created_at ON module_runs(created_at DESC);
CREATE INDEX idx_module_runs_module_name ON module_runs(module_name);

-- Audit log indices
CREATE INDEX idx_audit_log_timestamp ON audit_log(created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- Job deduplication index
CREATE UNIQUE INDEX idx_job_dedup ON job_deduplication(job_id, indicator_hash);

-- Execution metrics indices
CREATE INDEX idx_metrics_module_run ON execution_metrics(module_run_id);
CREATE INDEX idx_metrics_recorded_at ON execution_metrics(recorded_at DESC);

-- Data lineage indices
CREATE INDEX idx_lineage_source ON data_lineage(source_finding_id);
CREATE INDEX idx_lineage_derived ON data_lineage(derived_finding_id);

-- Indicators relationships indices
CREATE INDEX idx_indicator_rel_1 ON indicators_relationships(indicator_id_1);
CREATE INDEX idx_indicator_rel_2 ON indicators_relationships(indicator_id_2);

-- ============================================================
-- TRIGGERS FOR UPDATED_AT
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_findings_updated_at BEFORE UPDATE ON findings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- SEED DATA (OPTIONAL)
-- ============================================================

INSERT INTO system_config (config_key, config_value, description) VALUES
    ('max_iterations', '3', 'Maximum iterations for dynamic search'),
    ('dedup_threshold', '0.95', 'Similarity threshold for deduplication'),
    ('default_confidence_threshold', '0.5', 'Minimum confidence for findings'),
    ('cache_ttl_seconds', '3600', 'Cache TTL in seconds')
ON CONFLICT (config_key) DO NOTHING;

-- ============================================================
-- VIEWS (OPTIONAL - FOR CONVENIENCE)
-- ============================================================

CREATE OR REPLACE VIEW v_findings_with_indicators AS
SELECT 
    f.finding_id,
    f.job_id,
    f.module_name,
    f.type,
    f.value,
    f.confidence,
    f.created_at,
    COUNT(i.indicator_id) as indicators_count,
    json_agg(
        json_build_object(
            'indicator_id', i.indicator_id,
            'type', i.type,
            'value', i.value
        )
    ) FILTER (WHERE i.indicator_id IS NOT NULL) as indicators
FROM findings f
LEFT JOIN indicators i ON i.source_finding_id = f.finding_id
WHERE f.soft_deleted = false
GROUP BY f.finding_id;

CREATE OR REPLACE VIEW v_job_statistics AS
SELECT 
    j.job_id,
    j.status,
    j.created_at,
    COUNT(DISTINCT f.finding_id) as findings_count,
    COUNT(DISTINCT i.indicator_id) as indicators_count,
    COUNT(DISTINCT mr.module_run_id) as module_runs_count,
    AVG(f.confidence) as avg_confidence,
    MAX(mr.finished_at) as last_module_finished
FROM jobs j
LEFT JOIN findings f ON f.job_id = j.job_id AND f.soft_deleted = false
LEFT JOIN indicators i ON i.source_finding_id = f.finding_id
LEFT JOIN module_runs mr ON mr.job_id = j.job_id
GROUP BY j.job_id;

-- ============================================================
-- GRANTS (ADJUST FOR YOUR USER)
-- ============================================================

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO dev;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO dev;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO dev;
