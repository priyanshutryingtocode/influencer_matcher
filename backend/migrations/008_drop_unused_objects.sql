-- Drop objects nothing reads.
--
-- match_jobs was created by 002 as a database-backed job queue, but jobs are
-- held in process by api/jobs/manager.py (a ThreadPoolExecutor plus a dict) and
-- no code has ever read or written this table. It carried 13 columns, three
-- indexes, a foreign key to match_runs, RLS and a REVOKE for a queue that does
-- not exist. Dropping the table takes its indexes and the FK with it;
-- match_runs is untouched.
--
-- match_runs.pipeline was provenance (embedding model, embed width, ranking
-- model, indexed creator count). It was written to every run and served in the
-- RunDetail response, but no client surface ever displayed it, so the data was
-- stored, shipped and ignored. Dropping the column loses provenance for runs
-- already stored; their JSONB result snapshots are unaffected.
--
-- creator_signals_growth_idx indexes growth_trend, which is never filtered or
-- sorted on -- it is only written and read back by primary key. Every insert of
-- a creator paid to maintain an index no query could use.
DROP TABLE IF EXISTS match_jobs;

ALTER TABLE match_runs DROP COLUMN IF EXISTS pipeline;

DROP INDEX IF EXISTS creator_signals_growth_idx;