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