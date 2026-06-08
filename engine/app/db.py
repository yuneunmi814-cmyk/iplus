"""Local SQLite (aiosqlite). A local subset of the design's tables.

The cloud tier maps the same concepts to PostgreSQL + pgvector. Locally, append-only
logs live in a lightweight SQLite file. The path is injected via --db (Tauri passes
$APPDATA/iplus.db).
"""
from __future__ import annotations

import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER REFERENCES workspaces(id),
    domain TEXT, intent TEXT, status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now'))
);
-- append-only run log
CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    model TEXT, mode TEXT,
    input TEXT, output TEXT,
    tokens_in INTEGER DEFAULT 0, tokens_out INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
-- SCB (context buffer) local store
CREATE TABLE IF NOT EXISTS context_buffers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    summary TEXT, key_facts TEXT, system_prompt_slot TEXT,
    summarized_turns INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


async def init_db(path: str) -> None:
    async with aiosqlite.connect(path) as db:
        await db.executescript(SCHEMA)
        # migration for dbs created before summarized_turns existed
        try:
            await db.execute(
                "ALTER TABLE context_buffers ADD COLUMN summarized_turns INTEGER DEFAULT 0"
            )
        except Exception:
            pass  # column already exists
        await db.commit()


async def get_summary(path: str, task_id: int) -> tuple[str, int]:
    """(running summary, number of turns already folded into it)."""
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "SELECT summary, summarized_turns FROM context_buffers WHERE task_id=? LIMIT 1",
            (task_id,),
        )
        row = await cur.fetchone()
        return (row[0] or "", row[1] or 0) if row else ("", 0)


async def set_summary(path: str, task_id: int, summary: str, summarized_turns: int) -> None:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute("SELECT id FROM context_buffers WHERE task_id=?", (task_id,))
        row = await cur.fetchone()
        if row:
            await db.execute(
                "UPDATE context_buffers SET summary=?, summarized_turns=?, "
                "updated_at=datetime('now') WHERE id=?",
                (summary, summarized_turns, row[0]),
            )
        else:
            await db.execute(
                "INSERT INTO context_buffers (task_id, summary, summarized_turns) VALUES (?,?,?)",
                (task_id, summary, summarized_turns),
            )
        await db.commit()


async def create_task(path: str, *, domain: str, intent: str) -> int:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "INSERT INTO tasks (domain, intent, status) VALUES (?,?,'open')",
            (domain, intent),
        )
        await db.commit()
        return cur.lastrowid


async def get_history(path: str, task_id: int) -> list[tuple[str, str]]:
    """Prior (input, output) turns for a task, oldest first — the SCB context."""
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "SELECT input, output FROM task_runs WHERE task_id=? AND output != '' ORDER BY id",
            (task_id,),
        )
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def log_run(path: str, *, task_id: int | None, model: str | None, mode: str,
                  input_text: str, output: str = "", tokens_in: int = 0, tokens_out: int = 0) -> int:
    async with aiosqlite.connect(path) as db:
        cur = await db.execute(
            "INSERT INTO task_runs (task_id, model, mode, input, output, tokens_in, tokens_out)"
            " VALUES (?,?,?,?,?,?,?)",
            (task_id, model, mode, input_text, output, tokens_in, tokens_out),
        )
        await db.commit()
        return cur.lastrowid
