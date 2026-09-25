CREATE TABLE IF NOT EXISTS match_runs (
    id UUID PRIMARY KEY,
    brief JSONB NOT NULL,
    params JSONB NOT NULL,
    pipeline JSONB NOT NULL,
    result JSONB NOT NULL,
    warnings JSONB NOT NULL DEFAULT '[]'::JSONB,
    summary JSONB NOT NULL DEFAULT '{}'::JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS match_runs_created_at_idx
    ON match_runs (created_at DESC, id DESC);
