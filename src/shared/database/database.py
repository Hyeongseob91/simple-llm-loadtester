"""Database module for storing benchmark results."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator, Optional

# 한국 표준시 (KST, UTC+9)
KST = timezone(timedelta(hours=9))

from pydantic import BaseModel


class BenchmarkRunDB(BaseModel):
    """Database model for benchmark run."""

    id: str
    server_url: str
    model: str
    adapter: str
    config_json: str
    status: str  # pending, running, completed, failed
    result_json: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class Database:
    """SQLite database for benchmark results."""

    def __init__(self, db_path: str = "benchmarks.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables."""
        with self._get_connection() as conn:
            # Create main table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    id TEXT PRIMARY KEY,
                    server_url TEXT NOT NULL,
                    model TEXT NOT NULL,
                    adapter TEXT DEFAULT 'openai',
                    config_json TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    result_json TEXT,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            # Index on created_at for chronological queries (DESC for latest first)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_runs_created_at
                ON benchmark_runs(created_at DESC)
            """)

            # Index on status for filtering by status
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_runs_status
                ON benchmark_runs(status)
            """)

            # Composite index for status + created_at (common query pattern)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_runs_status_created
                ON benchmark_runs(status, created_at DESC)
            """)

            # Index on model for filtering by model
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_benchmark_runs_model
                ON benchmark_runs(model)
            """)

            conn.commit()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def create_run(
        self,
        run_id: str,
        server_url: str,
        model: str,
        adapter: str,
        config: dict,
    ) -> str:
        """Create a new benchmark run record."""
        now_kst = datetime.now(KST).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO benchmark_runs (id, server_url, model, adapter, config_json, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (run_id, server_url, model, adapter, json.dumps(config), now_kst),
            )
            conn.commit()
        return run_id

    def update_status(
        self,
        run_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        """Update run status."""
        with self._get_connection() as conn:
            if started_at:
                # 한국 시간으로 변환
                started_at_kst = started_at.astimezone(KST) if started_at.tzinfo else started_at.replace(tzinfo=KST)
                conn.execute(
                    "UPDATE benchmark_runs SET status = ?, started_at = ? WHERE id = ?",
                    (status, started_at_kst.isoformat(), run_id),
                )
            elif completed_at:
                # 한국 시간으로 변환
                completed_at_kst = completed_at.astimezone(KST) if completed_at.tzinfo else completed_at.replace(tzinfo=KST)
                conn.execute(
                    "UPDATE benchmark_runs SET status = ?, completed_at = ? WHERE id = ?",
                    (status, completed_at_kst.isoformat(), run_id),
                )
            else:
                conn.execute(
                    "UPDATE benchmark_runs SET status = ? WHERE id = ?",
                    (status, run_id),
                )
            conn.commit()

    def save_result(self, run_id: str, result: dict) -> None:
        """Save benchmark result."""
        now_kst = datetime.now(KST).isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE benchmark_runs
                SET result_json = ?, status = 'completed', completed_at = ?
                WHERE id = ?
                """,
                (json.dumps(result, default=str), now_kst, run_id),
            )
            conn.commit()

    def get_run(self, run_id: str) -> Optional[dict]:
        """Get a benchmark run by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM benchmark_runs WHERE id = ?",
                (run_id,),
            ).fetchone()

            if not row:
                return None

            return dict(row)

    def get_result(self, run_id: str) -> Optional[dict]:
        """Get benchmark result by run ID."""
        run = self.get_run(run_id)
        if not run or not run.get("result_json"):
            return None
        return json.loads(run["result_json"])

    def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> list[dict]:
        """List benchmark runs."""
        with self._get_connection() as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT id, server_url, model, adapter, status, started_at, completed_at, created_at
                    FROM benchmark_runs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, server_url, model, adapter, status, started_at, completed_at, created_at
                    FROM benchmark_runs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                ).fetchall()

            return [dict(row) for row in rows]

    def delete_run(self, run_id: str) -> bool:
        """Delete a benchmark run."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM benchmark_runs WHERE id = ?",
                (run_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
