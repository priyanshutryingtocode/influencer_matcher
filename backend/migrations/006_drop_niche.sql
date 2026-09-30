-- Drop the single-label taxonomy. Topic tags are now the only topical signal.
--
-- The old `niche TEXT NOT NULL` was a lossy label over vocabulary that already
-- existed in `tags`, and nothing validated against it once briefs became free
-- text. `secondary_niches` was the same idea, duplicated.
--
-- DROP COLUMN is used rather than SET NULL because no code reads either column.
-- The table is truncated at the end: `Influencer.corpus_text()` changed in the
-- same change (it now includes content style, audience, and brand partners), so
-- every stored vector was built from text that no longer exists. Serving those
-- would mean retrieval ran on a profile description the ranking model never
-- saw. The table is fully regenerable from `main.py --reindex`.
--
-- `match_runs` is untouched on purpose: stored runs keep their JSONB snapshot,
-- including creators captured with a niche, and still export correctly.

DO $$
BEGIN
    IF to_regclass('public.influencers') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS niche';
        EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS secondary_niches';
        EXECUTE 'TRUNCATE TABLE public.influencers';
    END IF;
END $$;
