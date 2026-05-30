"""
SQLite 数据库 - 持久化存储
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from models import (
    ABTest,
    ABTestStatus,
    ABTestVariant,
    EvalMetric,
    EvalResult,
    Prompt,
    PromptStatus,
    PromptVersion,
    VariableDefinition,
    VariableType,
)

DB_PATH = Path(__file__).parent / "data" / "prompts.db"


class Database:
    """SQLite 数据库封装"""

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = Path(db_path or DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    # ── 建表 ──────────────────────────────────────────────────────────────
    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS prompts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                category TEXT DEFAULT 'general',
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT 'draft',
                current_version INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS prompt_versions (
                id TEXT PRIMARY KEY,
                prompt_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                template TEXT NOT NULL,
                variables TEXT DEFAULT '[]',
                system_prompt TEXT DEFAULT '',
                model_hint TEXT DEFAULT '',
                temperature REAL DEFAULT 0.7,
                max_tokens INTEGER DEFAULT 2048,
                change_note TEXT DEFAULT '',
                created_at TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id),
                UNIQUE(prompt_id, version)
            );

            CREATE TABLE IF NOT EXISTS eval_results (
                id TEXT PRIMARY KEY,
                prompt_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                metric TEXT NOT NULL,
                score REAL NOT NULL,
                details TEXT DEFAULT '',
                input_sample TEXT DEFAULT '',
                output_sample TEXT DEFAULT '',
                created_at TEXT,
                FOREIGN KEY (prompt_id) REFERENCES prompts(id)
            );

            CREATE TABLE IF NOT EXISTS ab_tests (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'draft',
                variants TEXT DEFAULT '[]',
                sample_size INTEGER DEFAULT 100,
                results TEXT DEFAULT '[]',
                winner_variant_idx INTEGER,
                created_at TEXT,
                updated_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_pv_prompt ON prompt_versions(prompt_id);
            CREATE INDEX IF NOT EXISTS idx_er_prompt ON eval_results(prompt_id);
            CREATE INDEX IF NOT EXISTS idx_prompt_cat ON prompts(category);
            CREATE INDEX IF NOT EXISTS idx_prompt_status ON prompts(status);
        """)
        self.conn.commit()

    # ── Prompt CRUD ──────────────────────────────────────────────────────
    def save_prompt(self, prompt: Prompt) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO prompts
               (id, name, description, category, tags, status,
                current_version, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                prompt.id,
                prompt.name,
                prompt.description,
                prompt.category,
                json.dumps(prompt.tags, ensure_ascii=False),
                prompt.status.value,
                prompt.current_version,
                prompt.created_at.isoformat(),
                prompt.updated_at.isoformat(),
            ),
        )
        # 保存所有版本
        for ver in prompt.versions:
            self._save_version(ver)
        self.conn.commit()

    def _save_version(self, ver: PromptVersion) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO prompt_versions
               (id, prompt_id, version, template, variables, system_prompt,
                model_hint, temperature, max_tokens, change_note, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                ver.id,
                ver.prompt_id,
                ver.version,
                ver.template,
                json.dumps(
                    [v.model_dump() for v in ver.variables],
                    ensure_ascii=False,
                ),
                ver.system_prompt,
                ver.model_hint,
                ver.temperature,
                ver.max_tokens,
                ver.change_note,
                ver.created_at.isoformat(),
            ),
        )

    def get_prompt(self, prompt_id: str) -> Optional[Prompt]:
        row = self.conn.execute(
            "SELECT * FROM prompts WHERE id = ?", (prompt_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_prompt(row)

    def _row_to_prompt(self, row: sqlite3.Row) -> Prompt:
        versions = self._get_versions(row["id"])
        return Prompt(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            category=row["category"],
            tags=json.loads(row["tags"]),
            status=PromptStatus(row["status"]),
            current_version=row["current_version"],
            versions=versions,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _get_versions(self, prompt_id: str) -> list[PromptVersion]:
        rows = self.conn.execute(
            "SELECT * FROM prompt_versions WHERE prompt_id = ? ORDER BY version",
            (prompt_id,),
        ).fetchall()
        results = []
        for r in rows:
            vars_raw = json.loads(r["variables"])
            var_defs = [VariableDefinition(**v) for v in vars_raw]
            results.append(
                PromptVersion(
                    id=r["id"],
                    prompt_id=r["prompt_id"],
                    version=r["version"],
                    template=r["template"],
                    variables=var_defs,
                    system_prompt=r["system_prompt"],
                    model_hint=r["model_hint"],
                    temperature=r["temperature"],
                    max_tokens=r["max_tokens"],
                    change_note=r["change_note"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return results

    def list_prompts(
        self,
        category: Optional[str] = None,
        status: Optional[str] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[Prompt]:
        query = "SELECT * FROM prompts WHERE 1=1"
        params: list[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)
        if search:
            query += " AND (name LIKE ? OR description LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY updated_at DESC"
        rows = self.conn.execute(query, params).fetchall()

        prompts = [self._row_to_prompt(r) for r in rows]

        if tag:
            prompts = [p for p in prompts if tag in p.tags]

        return prompts

    def delete_prompt(self, prompt_id: str) -> bool:
        cur = self.conn.execute("DELETE FROM prompts WHERE id = ?", (prompt_id,))
        self.conn.execute(
            "DELETE FROM prompt_versions WHERE prompt_id = ?", (prompt_id,)
        )
        self.conn.execute(
            "DELETE FROM eval_results WHERE prompt_id = ?", (prompt_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # ── 评估结果 ──────────────────────────────────────────────────────────
    def save_eval_result(self, result: EvalResult) -> None:
        self.conn.execute(
            """INSERT INTO eval_results
               (id, prompt_id, version, metric, score, details,
                input_sample, output_sample, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.id,
                result.prompt_id,
                result.version,
                result.metric.value,
                result.score,
                result.details,
                result.input_sample,
                result.output_sample,
                result.created_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_eval_results(
        self, prompt_id: str, version: Optional[int] = None
    ) -> list[EvalResult]:
        query = "SELECT * FROM eval_results WHERE prompt_id = ?"
        params: list[Any] = [prompt_id]
        if version is not None:
            query += " AND version = ?"
            params.append(version)
        query += " ORDER BY created_at DESC"

        rows = self.conn.execute(query, params).fetchall()
        return [
            EvalResult(
                id=r["id"],
                prompt_id=r["prompt_id"],
                version=r["version"],
                metric=EvalMetric(r["metric"]),
                score=r["score"],
                details=r["details"],
                input_sample=r["input_sample"],
                output_sample=r["output_sample"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    # ── A/B 测试 ─────────────────────────────────────────────────────────
    def save_ab_test(self, test: ABTest) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO ab_tests
               (id, name, description, status, variants, sample_size,
                results, winner_variant_idx, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                test.id,
                test.name,
                test.description,
                test.status.value,
                json.dumps(
                    [v.model_dump() for v in test.variants], ensure_ascii=False
                ),
                test.sample_size,
                json.dumps(test.results, ensure_ascii=False),
                test.winner_variant_idx,
                test.created_at.isoformat(),
                test.updated_at.isoformat(),
            ),
        )
        self.conn.commit()

    def get_ab_test(self, test_id: str) -> Optional[ABTest]:
        row = self.conn.execute(
            "SELECT * FROM ab_tests WHERE id = ?", (test_id,)
        ).fetchone()
        if not row:
            return None
        variants_raw = json.loads(row["variants"])
        return ABTest(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            status=ABTestStatus(row["status"]),
            variants=[ABTestVariant(**v) for v in variants_raw],
            sample_size=row["sample_size"],
            results=json.loads(row["results"]),
            winner_variant_idx=row["winner_variant_idx"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def list_ab_tests(self) -> list[ABTest]:
        rows = self.conn.execute(
            "SELECT * FROM ab_tests ORDER BY updated_at DESC"
        ).fetchall()
        results = []
        for row in rows:
            variants_raw = json.loads(row["variants"])
            results.append(
                ABTest(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    status=ABTestStatus(row["status"]),
                    variants=[ABTestVariant(**v) for v in variants_raw],
                    sample_size=row["sample_size"],
                    results=json.loads(row["results"]),
                    winner_variant_idx=row["winner_variant_idx"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                )
            )
        return results

    # ── 统计 ──────────────────────────────────────────────────────────────
    def get_stats(self) -> dict[str, Any]:
        prompt_count = self.conn.execute(
            "SELECT COUNT(*) FROM prompts"
        ).fetchone()[0]
        version_count = self.conn.execute(
            "SELECT COUNT(*) FROM prompt_versions"
        ).fetchone()[0]
        eval_count = self.conn.execute(
            "SELECT COUNT(*) FROM eval_results"
        ).fetchone()[0]
        ab_count = self.conn.execute(
            "SELECT COUNT(*) FROM ab_tests"
        ).fetchone()[0]

        categories = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM prompts GROUP BY category"
        ).fetchall()

        avg_scores = self.conn.execute(
            "SELECT metric, AVG(score) as avg_score FROM eval_results GROUP BY metric"
        ).fetchall()

        return {
            "total_prompts": prompt_count,
            "total_versions": version_count,
            "total_evaluations": eval_count,
            "total_ab_tests": ab_count,
            "categories": {r["category"]: r["cnt"] for r in categories},
            "avg_scores_by_metric": {
                r["metric"]: round(r["avg_score"], 4) for r in avg_scores
            },
        }

    def close(self):
        self.conn.close()
