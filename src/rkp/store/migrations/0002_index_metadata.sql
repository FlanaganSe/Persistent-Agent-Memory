-- RKP schema v2: index metadata for freshness tracking.

CREATE TABLE IF NOT EXISTS index_metadata (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    last_indexed   TEXT NOT NULL,
    repo_head      TEXT NOT NULL,
    branch         TEXT NOT NULL,
    file_count     INTEGER NOT NULL DEFAULT 0,
    claim_count    INTEGER NOT NULL DEFAULT 0
);
