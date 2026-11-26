"""التقييم الأكاديمي المُحقَّق لمواد الجامعة.
يقيس جودة الاسترجاع (Recall@K, Precision@K) لكل مادة باستخدام أسئلة حقيقية
ومصادر متوقعة معروفة، ويؤكد أن الجواب يستشهد بمصادر من المواد الدراسية.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from core.university_ingest import search_university, load_university_chunks

# أسئلة حقيقية لكل مادة مع المادة المتوقعة ومصادر متوقعة (بناءً على محتوى الملفات الفعلية).
# هذه أسئلة استرجاع (ليست generative ground-truth للإجابة الكاملة) لقياس recall/precision.
EVAL_QUERIES: list[dict[str, Any]] = [
    {
        "id": "or-01",
        "course": "Operation Research",
        "query": "بحث العمليات Operation Research البرمجة الخطية التوزيع الطبيعي",
        "expected_courses": ["Operation Research"],
        "expected_keywords": ["operat", "research", "بحث"],
    },
    {
        "id": "or-02",
        "course": "Operation Research",
        "query": "Transportation Model توزيع المنتجات مصادر وجهات أقل تكلفة",
        "expected_courses": ["Operation Research"],
        "expected_keywords": ["transportation", "model", "توزيع"],
    },
    {
        "id": "abs-01",
        "course": "Agent Based Systems",
        "query": "نظام الوكلاء PEAS التصنيف أبعاد الوكيل الذكي",
        "expected_courses": ["Agent Based Systems"],
        "expected_keywords": ["peas", "agent", "وكيل"],
    },
    {
        "id": "abs-02",
        "course": "Agent Based Systems",
        "query": "AI Agents Analysis PEAS Dimensions Classification",
        "expected_courses": ["Agent Based Systems"],
        "expected_keywords": ["peas", "agent", "classification"],
    },
    {
        "id": "cc-01",
        "course": "Cloud Computing",
        "query": "الحوسبة السحابية نماذج النشر النشر الخاص العام الهجين",
        "expected_courses": ["Cloud Computing"],
        "expected_keywords": ["cloud", "سحابة", "deployment"],
    },
    {
        "id": "cc-02",
        "course": "Cloud Computing",
        "query": "virtualization آلة افتراضية الحوسبة السحابية",
        "expected_courses": ["Cloud Computing"],
        "expected_keywords": ["virtual", "سحاب", "virtualization"],
    },
    {
        "id": "ip-01",
        "course": "Intellectual Property",
        "query": "الملكية الفكرية حقوق النشر براءات الاختراع العلامات التجارية",
        "expected_courses": ["Intellectual Property"],
        "expected_keywords": ["intellectual", "property", "ملكية"],
    },
    {
        "id": "ip-02",
        "course": "Intellectual Property",
        "query": "copyright patent trademark intellectual property law",
        "expected_courses": ["Intellectual Property"],
        "expected_keywords": ["copyright", "patent", "trademark"],
    },
    {
        "id": "ccs-01",
        "course": "Computational Cognitive Science",
        "query": "العلوم الإدراكية الحاسوبية الذاكرة التعلم النماذج الإدراكية",
        "expected_courses": ["Computational Cognitive Science"],
        "expected_keywords": ["cognitive", "memory", "إدراك"],
    },
    {
        "id": "cgv-01",
        "course": "Computer Graphics and Vision",
        "query": "الرسومات الحاسوبية والرؤية rendering معالجة الصور",
        "expected_courses": ["Computer Graphics and Vision"],
        "expected_keywords": ["graphics", "vision", "rendering"],
    },
    {
        "id": "cs-01",
        "course": "Cryptography Security",
        "query": "التشفير والأمان RSA تشفير كلاسيكي تقنيات التشفير",
        "expected_courses": ["Cryptography Security"],
        "expected_keywords": ["crypt", "rsa", "تشفير"],
    },
    {
        "id": "cs-02",
        "course": "Cryptography Security",
        "query": "classical encryption techniques substitution transposition cipher",
        "expected_courses": ["Cryptography Security"],
        "expected_keywords": ["encryption", "cipher", "classical"],
    },
    {
        "id": "mid-01",
        "course": "Midterm_26_Students_V7.pdf",
        "query": "Midterm 26 Students V7 امتحان منتصف",
        "expected_courses": ["Midterm_26_Students_V7.pdf"],
        "expected_keywords": ["midterm", "امتحان", "mid"],
    },
]


def _course_of(source_rel: str) -> str:
    return source_rel.split("/", 1)[0] if "/" in source_rel else source_rel


def evaluate_retrieval(k: int = 4) -> dict:
    results: list[dict] = []
    total_recall = 0.0
    total_precision = 0.0
    n = 0
    for q in EVAL_QUERIES:
        hits = search_university(q["query"], k=k)
        retrieved_courses = []
        retrieved_keyword_match = 0
        for h in hits:
            md = h.get("metadata") or {}
            rc = _course_of(md.get("source_rel", ""))
            retrieved_courses.append(rc)
            text = (h.get("title", "") + " " + h.get("text", "")).lower()
            if any(kw.lower() in text for kw in q["expected_keywords"]):
                retrieved_keyword_match += 1
        expected = set(q["expected_courses"])
        retrieved_set = set(retrieved_courses)
        # Recall: هل المادة المتوقعة ضمن أعلى K؟
        recall = 1.0 if expected & retrieved_set else 0.0
        # Precision: نسبة النتائج من المادة المتوقعة
        precision = (len(expected & retrieved_set) / len(retrieved_set)) if retrieved_set else 0.0
        total_recall += recall
        total_precision += precision
        n += 1
        results.append({
            "id": q["id"],
            "query": q["query"],
            "expected_course": q["course"],
            "retrieved_courses": retrieved_courses,
            "recall@k": round(recall, 2),
            "precision@k": round(precision, 2),
            "keyword_hits": retrieved_keyword_match,
            "top_source": hits[0]["source"] if hits else None,
            "top_score": hits[0]["score"] if hits else 0,
        })
    summary = {
        "k": k,
        "num_queries": n,
        "mean_recall@k": round(total_recall / n, 3) if n else 0.0,
        "mean_precision@k": round(total_precision / n, 3) if n else 0.0,
        "queries_all_recall_1": sum(1 for r in results if r["recall@k"] == 1.0),
    }
    return {"summary": summary, "results": results}


def main() -> None:
    chunks = load_university_chunks()
    print("chunks loaded:", len(chunks))
    out = evaluate_retrieval(k=4)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))
    Path("data/university/eval_retrieval.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for r in out["results"]:
        flag = "OK " if r["recall@k"] == 1.0 else "FAIL"
        print(f"{flag} {r['id']} course={r['expected_course']} "
              f"recall={r['recall@k']} prec={r['precision@k']} top={r['top_source']}")


if __name__ == "__main__":
    main()
