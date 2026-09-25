DO $$
DECLARE
    embedding_type TEXT;
BEGIN
    IF to_regclass('public.influencers') IS NOT NULL THEN
        SELECT format_type(attribute.atttypid, attribute.atttypmod)
        INTO embedding_type
        FROM pg_attribute AS attribute
        WHERE attribute.attrelid = 'public.influencers'::regclass
          AND attribute.attname = 'embedding'
          AND NOT attribute.attisdropped;

        IF embedding_type IS DISTINCT FROM 'vector(384)' THEN
            EXECUTE 'DROP INDEX IF EXISTS public.influencers_embedding_idx';
            EXECUTE 'TRUNCATE TABLE public.influencers';
            EXECUTE 'ALTER TABLE public.influencers DROP COLUMN IF EXISTS embedding';
            EXECUTE 'ALTER TABLE public.influencers ADD COLUMN embedding vector(384) NOT NULL';
        END IF;
    END IF;
END $$;
