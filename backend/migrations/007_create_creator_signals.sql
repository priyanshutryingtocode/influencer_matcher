-- Split inferred creator characteristics into their own table.
--
-- `influencers` keeps what a creator's own profile states: handle, reach,
-- topics, bio. Everything moved here is an estimate made *about* that profile
-- by a third party, so it has a different refresh cadence and a different
-- trust level. The split lets a signal be updated without re-embedding a
-- profile, and lets a ranking reason say "inferred audience 25-34" instead of
-- implying the creator declared it.
--
-- Column moves: content_style, audience_age, audience_gender, audience_country,
-- brand_collaborations.
--
-- New signals that did not exist as columns before:
--   reach_ratio              - views / followers; whether reach is real
--   sponsored_ratio          - share of posts that are paid
--   growth_trend             - rising / steady / declining
--   audience_top_countries   - the headline country is not the whole audience
--
-- IMPORTANT: `Influencer.corpus_text()` is unchanged. It still reads these
-- five fields (via the LEFT JOIN in vector_store.search) and emits the same
-- string, so no cached embedding is invalidated by this migration. That is
-- what makes it safe to apply before the pending re-embed rather than
-- compounding it. The four new signals are *not* in corpus_text, so they are
-- stored and displayable but not citable by the ranking model.
--
-- reach_ratio is recomputed from average_views / followers rather than copied,
-- so a reader dividing the two numbers cannot catch the row out.

DO $$
BEGIN
    IF to_regclass('public.influencers') IS NULL THEN
        -- Fresh database: the CLI creates `influencers` from vector_store's
        -- own DDL afterwards, and that DDL no longer has the signal columns.
        -- The table is still created now so a cold start does not depend on
        -- migration ordering.
        EXECUTE $ddl$
            CREATE TABLE IF NOT EXISTS public.creator_signals (
                creator_id INTEGER PRIMARY KEY,
                content_style TEXT,
                audience_age TEXT,
                audience_gender TEXT,
                audience_country TEXT,
                brand_collaborations TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                reach_ratio DOUBLE PRECISION,
                sponsored_ratio DOUBLE PRECISION,
                growth_trend TEXT,
                audience_top_countries TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]
            )
        $ddl$;
        RETURN;
    END IF;

    EXECUTE $ddl$
        CREATE TABLE IF NOT EXISTS public.creator_signals (
            creator_id INTEGER PRIMARY KEY
                REFERENCES public.influencers(id) ON DELETE CASCADE,
            content_style TEXT,
            audience_age TEXT,
            audience_gender TEXT,
            audience_country TEXT,
            brand_collaborations TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
            reach_ratio DOUBLE PRECISION,
            sponsored_ratio DOUBLE PRECISION,
            growth_trend TEXT,
            audience_top_countries TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]
        )
    $ddl$;

    -- Column moves. ADD COLUMN IF NOT EXISTS on the destination, then copy,
    -- then drop the source. Each step is idempotent so re-running is safe.
    EXECUTE 'ALTER TABLE public.creator_signals ADD COLUMN IF NOT EXISTS content_style TEXT';
    EXECUTE 'ALTER TABLE public.creator_signals ADD COLUMN IF NOT EXISTS audience_age TEXT';
    EXECUTE 'ALTER TABLE public.creator_signals ADD COLUMN IF NOT EXISTS audience_gender TEXT';
    EXECUTE 'ALTER TABLE public.creator_signals ADD COLUMN IF NOT EXISTS audience_country TEXT';
    EXECUTE 'ALTER TABLE public.creator_signals ADD COLUMN IF NOT EXISTS brand_collaborations TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[]';

    -- Backfill before dropping, so nothing is lost if the table already held
    -- creators from an earlier run. The whole copy is dynamic SQL because a
    -- pre-007 database does have these columns and a fresh one does not, and
    -- a static statement would fail to parse on the latter.
    EXECUTE $copy$
        DO $inner$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'influencers'
                  AND column_name = 'content_style'
            ) THEN
                EXECUTE $copy2$
                    INSERT INTO public.creator_signals
                        (creator_id, content_style, audience_age, audience_gender,
                         audience_country, brand_collaborations, reach_ratio)
                    SELECT i.id, i.content_style, i.audience_age, i.audience_gender,
                           i.audience_country,
                           COALESCE(i.brand_collaborations, ARRAY[]::TEXT[]),
                           CASE WHEN i.followers > 0
                                THEN i.average_views::DOUBLE PRECISION / i.followers
                                ELSE NULL END
                    FROM public.influencers AS i
                    WHERE i.content_style IS NOT NULL
                       OR i.audience_age IS NOT NULL
                       OR i.audience_gender IS NOT NULL
                       OR i.audience_country IS NOT NULL
                    ON CONFLICT (creator_id) DO NOTHING
                $copy2$;
            END IF;
        END $inner$;
    $copy$;

    -- Dropping from the source is unconditional and idempotent: a fresh table
    -- has no such column and IF EXISTS makes that a no-op.
    EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS content_style';
    EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS audience_age';
    EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS audience_gender';
    EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS audience_country';
    EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS brand_collaborations';
END $$;

-- Signals are server-side only. Same posture as `influencers`: RLS on, and
-- no grants to the browser roles. The API connects directly as the table
-- owner, so this does not affect it.
DO $$
BEGIN
    IF to_regclass('public.creator_signals') IS NOT NULL THEN
        EXECUTE 'ALTER TABLE public.creator_signals ENABLE ROW LEVEL SECURITY';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        EXECUTE 'REVOKE ALL ON TABLE public.creator_signals FROM anon';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        EXECUTE 'REVOKE ALL ON TABLE public.creator_signals FROM authenticated';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS creator_signals_growth_idx
    ON public.creator_signals (growth_trend);
