ALTER TABLE match_jobs
    ADD COLUMN IF NOT EXISTS claimed_at TIMESTAMPTZ;

DELETE FROM match_jobs
WHERE run_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM match_runs WHERE match_runs.id = match_jobs.run_id
  );

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'match_jobs_run_fk'
          AND conrelid = 'match_jobs'::regclass
    ) THEN
        ALTER TABLE match_jobs
            ADD CONSTRAINT match_jobs_run_fk
            FOREIGN KEY (run_id) REFERENCES match_runs(id) ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE match_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE match_jobs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF to_regclass('public.influencers') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.influencers ENABLE ROW LEVEL SECURITY';
    END IF;
END $$;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        REVOKE ALL ON TABLE match_runs, match_jobs FROM anon;
        IF to_regclass('public.influencers') IS NOT NULL THEN
            EXECUTE 'REVOKE ALL ON TABLE public.influencers FROM anon';
        END IF;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON TABLE match_runs, match_jobs FROM authenticated;
        IF to_regclass('public.influencers') IS NOT NULL THEN
            EXECUTE 'REVOKE ALL ON TABLE public.influencers FROM authenticated';
        END IF;
    END IF;
END $$;
