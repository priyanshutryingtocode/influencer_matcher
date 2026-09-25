ALTER TABLE match_runs
    ADD COLUMN IF NOT EXISTS owner_id UUID;

CREATE INDEX IF NOT EXISTS match_runs_owner_created_idx
    ON match_runs (owner_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS match_jobs (
    id UUID PRIMARY KEY,
    owner_id UUID NOT NULL,
    brief JSONB NOT NULL,
    params JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT NOT NULL DEFAULT 'queued',
    progress JSONB NOT NULL DEFAULT '{}'::JSONB,
    run_id UUID,
    outcome TEXT,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT match_jobs_status_check
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled'))
);

CREATE INDEX IF NOT EXISTS match_jobs_queue_idx
    ON match_jobs (status, created_at, id);

CREATE INDEX IF NOT EXISTS match_jobs_owner_idx
    ON match_jobs (owner_id, created_at DESC);
