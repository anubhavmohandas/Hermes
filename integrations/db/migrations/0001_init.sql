-- 0001_init.sql — baseline schema for the db module (Stage 5).
-- Portable across SQLite (fallback) and Postgres (Supabase). Keep types to
-- the common subset: TEXT, INTEGER, TIMESTAMP.
CREATE TABLE IF NOT EXISTS project_notes (
    id INTEGER PRIMARY KEY,
    topic TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
