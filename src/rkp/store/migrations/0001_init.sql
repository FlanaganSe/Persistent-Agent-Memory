-- RKP schema v1: claims, evidence, history, applicability, artifacts,
-- environment profiles, module edges, session log.

CREATE TABLE IF NOT EXISTS claims (
    id                   TEXT PRIMARY KEY,
    content              TEXT NOT NULL,
    claim_type           TEXT NOT NULL,
    source_authority     TEXT NOT NULL,
    authority_level      INTEGER NOT NULL,
    scope                TEXT NOT NULL DEFAULT '**',
    applicability        TEXT NOT NULL DEFAULT '[]',
    sensitivity          TEXT NOT NULL DEFAULT 'public',
    review_state         TEXT NOT NULL DEFAULT 'unreviewed',
    confidence           REAL NOT NULL DEFAULT 0.0,
    evidence             TEXT NOT NULL DEFAULT '[]',
    provenance           TEXT NOT NULL DEFAULT '{}',
    risk_class           TEXT,
    projection_targets   TEXT NOT NULL DEFAULT '[]',
    repo_id              TEXT NOT NULL,
    branch               TEXT NOT NULL DEFAULT 'main',
    worktree_id          TEXT,
    session_id           TEXT,
    last_validated       TEXT,
    revalidation_trigger TEXT,
    stale                INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    CHECK (confidence >= 0.0 AND confidence <= 1.0)
);

CREATE TABLE IF NOT EXISTS claim_evidence (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id           TEXT NOT NULL REFERENCES claims(id),
    file_path          TEXT NOT NULL,
    file_hash          TEXT NOT NULL,
    line_start         INTEGER,
    line_end           INTEGER,
    evidence_level     TEXT NOT NULL DEFAULT 'discovered',
    extraction_version TEXT NOT NULL,
    UNIQUE(claim_id, file_path, extraction_version)
);

CREATE TABLE IF NOT EXISTS claim_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id       TEXT NOT NULL REFERENCES claims(id),
    action         TEXT NOT NULL,
    content_before TEXT,
    content_after  TEXT,
    actor          TEXT NOT NULL DEFAULT 'system',
    timestamp      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    reason         TEXT
);

CREATE TABLE IF NOT EXISTS claim_applicability (
    claim_id TEXT NOT NULL REFERENCES claims(id),
    tag      TEXT NOT NULL,
    PRIMARY KEY (claim_id, tag)
);

CREATE TABLE IF NOT EXISTS managed_artifacts (
    path           TEXT PRIMARY KEY,
    artifact_type  TEXT NOT NULL,
    target_host    TEXT NOT NULL,
    expected_hash  TEXT NOT NULL,
    last_projected TEXT NOT NULL,
    ownership_mode TEXT NOT NULL DEFAULT 'managed-by-rkp'
);

CREATE TABLE IF NOT EXISTS environment_profiles (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    claim_id       TEXT REFERENCES claims(id),
    runtime        TEXT,
    tools          TEXT DEFAULT '[]',
    services       TEXT DEFAULT '[]',
    env_vars       TEXT DEFAULT '[]',
    setup_commands TEXT DEFAULT '[]',
    repo_id        TEXT NOT NULL,
    UNIQUE(name, repo_id)
);

CREATE TABLE IF NOT EXISTS module_edges (
    source_path TEXT NOT NULL,
    target_path TEXT NOT NULL,
    edge_type   TEXT NOT NULL,
    repo_id     TEXT NOT NULL,
    branch      TEXT NOT NULL DEFAULT 'main',
    PRIMARY KEY (source_path, target_path, edge_type, repo_id)
);

CREATE TABLE IF NOT EXISTS session_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_data TEXT NOT NULL DEFAULT '{}',
    timestamp  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_claims_type ON claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_claims_review ON claims(review_state);
CREATE INDEX IF NOT EXISTS idx_claims_repo ON claims(repo_id, branch);
CREATE INDEX IF NOT EXISTS idx_claims_scope ON claims(scope);
CREATE INDEX IF NOT EXISTS idx_claims_sensitivity ON claims(sensitivity);
CREATE INDEX IF NOT EXISTS idx_applicability_tag ON claim_applicability(tag);
CREATE INDEX IF NOT EXISTS idx_evidence_claim ON claim_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_evidence_file ON claim_evidence(file_path);
CREATE INDEX IF NOT EXISTS idx_history_claim ON claim_history(claim_id);
CREATE INDEX IF NOT EXISTS idx_module_source ON module_edges(source_path);
CREATE INDEX IF NOT EXISTS idx_module_target ON module_edges(target_path);
CREATE INDEX IF NOT EXISTS idx_session_log_session ON session_log(session_id);

-- FTS5 table for full-text search on claim content.
-- Created here for schema completeness; population deferred.
CREATE VIRTUAL TABLE IF NOT EXISTS claims_fts USING fts5(
    content,
    content=claims,
    content_rowid=rowid,
    tokenize='porter unicode61'
);
