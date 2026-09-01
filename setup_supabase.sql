-- Run this in your Supabase project's SQL editor (supabase.com → your project → SQL Editor)

-- 1. Create the phrases table
CREATE TABLE IF NOT EXISTS phrases (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    phrase       TEXT NOT NULL,
    count        INTEGER DEFAULT 0,
    last_detected TIMESTAMPTZ
);

-- 2. Atomic increment function (avoids race conditions)
CREATE OR REPLACE FUNCTION increment_phrase_count(phrase_id TEXT)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    new_count INTEGER;
BEGIN
    UPDATE phrases
    SET count = count + 1,
        last_detected = NOW()
    WHERE id = phrase_id
    RETURNING count INTO new_count;
    RETURN new_count;
END;
$$;

-- 3. Enable real-time so the web page updates live
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'phrases'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE phrases;
    END IF;
END $$;

-- 4. The web dashboard is public, so it must only ever be able to read.
-- Writes come from main.py using the secret key, which bypasses RLS —
-- no write policy needed here.
ALTER TABLE phrases ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read access" ON phrases;
CREATE POLICY "Public read access" ON phrases FOR SELECT USING (true);

-- 5. Live transcript — lets the speaker see what's being transcribed in
-- real time, to manually spot-check accuracy.
CREATE TABLE IF NOT EXISTS live_transcript (
    id   TEXT PRIMARY KEY DEFAULT 'current',
    text TEXT NOT NULL DEFAULT ''
);

INSERT INTO live_transcript (id, text)
VALUES ('current', '')
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication_tables
        WHERE pubname = 'supabase_realtime' AND schemaname = 'public' AND tablename = 'live_transcript'
    ) THEN
        ALTER PUBLICATION supabase_realtime ADD TABLE live_transcript;
    END IF;
END $$;

ALTER TABLE live_transcript ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Public read access" ON live_transcript;
CREATE POLICY "Public read access" ON live_transcript FOR SELECT USING (true);
