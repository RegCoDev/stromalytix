"""
Knowledge Vault — SQLite + VSS database layer.

Manages schema for papers, chunks (with FTS5 + vector search), parameters, and benchmarks.
"""

import sqlite3
import os

import sqlite_vss

DB_PATH = os.environ.get("VAULT_DB_PATH", "vault.db")

_conn: sqlite3.Connection | None = None


def init_db(db_path: str = "vault.db") -> sqlite3.Connection:
    """Create connection, enable WAL + FK, load sqlite-vss, create all tables."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    # Load sqlite-vss extension
    sqlite_vss.load(conn)

    # --- papers ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            id          INTEGER PRIMARY KEY,
            pmid        TEXT UNIQUE NOT NULL,
            doi         TEXT,
            title       TEXT NOT NULL,
            year        INTEGER,
            journal     TEXT,
            authors     TEXT NOT NULL DEFAULT '[]',
            clusters    TEXT NOT NULL DEFAULT '[]',
            biofab_method TEXT,
            tissue_type   TEXT,
            materials     TEXT NOT NULL DEFAULT '[]',
            cell_types    TEXT NOT NULL DEFAULT '[]',
            full_abstract TEXT NOT NULL,
            indexed_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- chunks ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id          INTEGER PRIMARY KEY,
            paper_id    INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            section     TEXT NOT NULL DEFAULT 'full',
            text        TEXT NOT NULL,
            embedding   BLOB,
            token_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_paper_id ON chunks(paper_id)")

    # --- FTS5 external content table ---
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
        USING fts5(text, content=chunks, content_rowid=id)
    """)

    # --- FTS5 sync triggers ---
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
        END
    """)
    conn.execute("""
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.id, old.text);
            INSERT INTO chunks_fts(rowid, text) VALUES (new.id, new.text);
        END
    """)

    # --- sqlite-vss vector index (must come after extension load) ---
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vss USING vss0(embedding(384))
    """)

    # --- parameters ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parameters (
            id          TEXT PRIMARY KEY,
            table_name  TEXT NOT NULL,
            parameter   TEXT NOT NULL,
            value       REAL,
            unit        TEXT,
            material    TEXT,
            cell_type   TEXT,
            conditions  TEXT,
            confidence  TEXT,
            doi         TEXT,
            pmid        TEXT,
            notes       TEXT,
            source      TEXT NOT NULL DEFAULT 'curated',
            extra       TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_params_table ON parameters(table_name, parameter)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_params_material ON parameters(material)")

    # --- benchmarks ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS benchmarks (
            id          INTEGER PRIMARY KEY,
            category    TEXT NOT NULL,
            material    TEXT,
            cell_type   TEXT,
            data        TEXT NOT NULL,
            source_doi  TEXT
        )
    """)

    conn.commit()
    return conn


def get_db() -> sqlite3.Connection:
    """Return module-level singleton connection (created on first call)."""
    global _conn
    if _conn is None:
        _conn = init_db(DB_PATH)
    return _conn


def close_db() -> None:
    """Close the singleton connection."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None
