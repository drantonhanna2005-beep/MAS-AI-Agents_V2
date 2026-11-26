"""نظام التغذية الراجعة والاختبارات الانحدارية (Feedback & Regression).
يسجّل ملاحظات المستخدم على إجابات الوكلاء، يصنّف الفشل المؤكّد، ويحوله إلى
حالات اختبار انحدارية تُعاد לרוץ للتحقق من أن الخطأ قد أُصلح دون تراجع.
كل المخزّنات محلية (SQLite/M JSON ضمن مجلد البرنامج) ولا تُرسل لأي خدمة خارجية.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from .config import DB_PATH, ROOT

FEEDBACK_DIR = ROOT / "data" / "feedback"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
REGRESSION_CASES_PATH = FEEDBACK_DIR / "regression_cases.jsonl"

# فئات الفشل المعتمدة (تُستخدم في تصنيف الأخطاء المؤكّدة).
FAILURE_CATEGORIES = (
    "retrieval_failure",
    "missing_source_content",
    "incorrect_extraction",
    "poor_chunking",
    "wrong_course_selection",
    "incorrect_calculation",
    "model_reasoning_failure",
    "tool_execution_failure",
    "prompt_or_routing_failure",
    "insufficient_evidence",
    "hallucination",
    "other",
)

_lock = threading.RLock()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS feedback_events(
            id TEXT PRIMARY KEY,
            chat_id TEXT,
            message_id INTEGER,
            question TEXT,
            agent TEXT,
            answer TEXT,
            sources TEXT,
            feedback TEXT,
            category TEXT,
            root_cause TEXT,
            confirmed INTEGER DEFAULT 0,
            created REAL NOT NULL)"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS regression_runs(
            id TEXT PRIMARY KEY,
            case_id TEXT,
            passed INTEGER,
            detail TEXT,
            created REAL NOT NULL)"""
    )
    conn.commit()
    return conn


def record_feedback(*, chat_id: str, message_id: int, question: str, agent: str,
                    answer: str, sources: list[dict], feedback: str,
                    category: str | None = None,
                    root_cause: str | None = None,
                    confirmed: bool = False) -> str:
    """يسجّل حدث تغذية راجعة. لو كان feedback='dislike' وconfirmed=True يُصنّف كخطأ مؤكّد."""
    fid = uuid.uuid4().hex[:12]
    now = time.time()
    cat = category if category in FAILURE_CATEGORIES else "other"
    with _lock:
        conn = _conn()
        conn.execute(
            """INSERT INTO feedback_events(id,chat_id,message_id,question,agent,answer,
                sources,feedback,category,root_cause,confirmed,created)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (fid, chat_id, int(message_id), question, agent, answer,
             json.dumps(sources or [], ensure_ascii=False), feedback, cat,
             root_cause, 1 if confirmed else 0, now))
        conn.commit()
    # إذا كان خطأً مؤكداً، أضفه كحالة انحدار.
    if confirmed and category:
        add_regression_case(fid, question, agent, answer, sources, category, root_cause)
    return fid


def add_regression_case(feedback_id: str, question: str, agent: str, answer: str,
                        sources: list[dict], category: str, root_cause: str | None) -> str:
    """يضيف حالة اختبار انحدارية من خطأ مؤكّد."""
    cid = uuid.uuid4().hex[:12]
    now = time.time()
    case = {
        "id": cid,
        "feedback_id": feedback_id,
        "question": question,
        "agent": agent,
        "answer": answer,
        "sources": sources,
        "category": category,
        "root_cause": root_cause,
        "created_at": now,
        "status": "open",
    }
    with REGRESSION_CASES_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(case, ensure_ascii=False) + "\n")
    return cid


def list_regression_cases() -> list[dict]:
    if not REGRESSION_CASES_PATH.exists():
        return []
    cases = []
    with REGRESSION_CASES_PATH.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    cases.append(json.loads(line))
                except Exception:
                    continue
    return cases


def run_regression_case(case: dict, agent_runner) -> dict:
    """يُعيد تشغيل حالة انحدار واحدة باستخدام دالة تنفيذ الوكيل الممرّرة.
    agent_runner(question, agent) -> dict مع مفاتيح: answer, sources, ok, error.
    يرجع نتيجة التشغيل للمقارنة."""
    cid = case["id"]
    question = case["question"]
    agent = case.get("agent", "research")
    now = time.time()
    try:
        out = agent_runner(question, agent)
        passed = bool(out.get("ok", False)) and bool(out.get("answer"))
        detail = out.get("error") or ""
        # نجاح جزئيّ: لو كان الخطأ استرجاعاً والآن هناك مصادر، يُحسب نجاحاً جزئياً.
        if case.get("category") == "retrieval_failure" and out.get("sources"):
            passed = True
    except Exception as e:  # noqa: BLE001
        passed = False
        detail = f"{type(e).__name__}: {e}"
        out = {}
    with _lock:
        conn = _conn()
        rid = uuid.uuid4().hex[:12]
        conn.execute(
            """INSERT INTO regression_runs(id,case_id,passed,detail,created)
                VALUES(?,?,?,?,?)""",
            (rid, cid, 1 if passed else 0, detail, now))
        conn.commit()
    return {"case_id": cid, "passed": passed, "detail": detail,
            "expected_category": case.get("category"),
            "root_cause": case.get("root_cause"),
            "got_sources": bool(out.get("sources")),
            "got_answer": bool(out.get("answer"))}


def get_stats() -> dict:
    with _lock:
        conn = _conn()
        total = conn.execute("SELECT COUNT(*) FROM feedback_events").fetchone()[0]
        confirmed = conn.execute(
            "SELECT COUNT(*) FROM feedback_events WHERE confirmed=1").fetchone()[0]
        by_cat = {}
        for row in conn.execute(
            "SELECT category, COUNT(*) FROM feedback_events WHERE confirmed=1 GROUP BY category"):
            by_cat[row[0]] = row[1]
        runs_total = conn.execute("SELECT COUNT(*) FROM regression_runs").fetchone()[0]
        runs_passed = conn.execute(
            "SELECT COUNT(*) FROM regression_runs WHERE passed=1").fetchone()[0]
    cases = list_regression_cases()
    return {
        "feedback_events": total,
        "confirmed_failures": confirmed,
        "by_category": by_cat,
        "regression_cases": len(cases),
        "regression_runs_total": runs_total,
        "regression_runs_passed": runs_passed,
        "regression_pass_rate": round(runs_passed / runs_total, 3) if runs_total else None,
        "categories": list(FAILURE_CATEGORIES),
    }
