CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS vectors
(
    id            SERIAL PRIMARY KEY,
    document_name VARCHAR(64),
    text          TEXT NOT NULL,
    embedding     VECTOR(384) NOT NULL
);

CREATE TABLE IF NOT EXISTS rag_index (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    metadata JSONB NOT NULL
);
