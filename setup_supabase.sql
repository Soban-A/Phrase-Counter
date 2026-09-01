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
ALTER PUBLICATION supabase_realtime ADD TABLE phrases;
