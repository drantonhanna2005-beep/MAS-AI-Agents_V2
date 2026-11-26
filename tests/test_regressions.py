"""اختبارات انحدار (بدون اعتماديات خارجية) — تشغيل:

    python -m unittest discover -s tests -v

تغطي:
1. استخراج النص من كل صيغ الملفات المدعومة (DOCX/XLSX/PPTX/CSV/TXT/كود).
2. ترتيب البحث: مطابقة اسم الملف/الامتداد (مثال: «ملف Python» → .py).
3. تحرير الرسائل: edited_at + النسخ القديمة + حذف ما بعدها + رفض رسالة مساعد.
4. تقييم المحادثة (like/dislike/dismiss) عبر list_chats.
5. المشاركة: theme/lang/count/الرسائل والوسائط تُحفظ وتُسترجع.
6. CV: عدد فواصل الصفحات = الصفحات المطلوبة − 1 (1..8) وبنية ATS أحادية العمود.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core import university_ingest  # noqa: E402

from core import history  # noqa: E402
from core import extract  # noqa: E402
from core import cvgen  # noqa: E402
from core import rag  # noqa: E402


# ---------------------------------------------------------------- استخراج النص
class ExtractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_docx_heading_table(self):
        import docx
        p = self.dir / "a.docx"
        d = docx.Document()
        d.add_heading("AUDIT DOCX", 0)
        d.add_paragraph("DOCX secret code: DOCX-3311-AA")
        t = d.add_table(rows=1, cols=2)
        t.cell(0, 0).text = "Deadline"
        t.cell(0, 1).text = "3 June 2030"
        d.save(p)
        out = extract.extract_text(p)
        self.assertIn("DOCX-3311-AA", out)
        self.assertIn("Deadline | 3 June 2030", out)

    def test_xlsx_keeps_formula(self):
        from openpyxl import Workbook
        p = self.dir / "a.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = "Budget"
        ws["A1"], ws["B1"] = "code", "XLSX-7722-BB"
        ws["A2"], ws["B2"] = "Total", "=100+250"
        wb.save(p)
        out = extract.extract_text(p)
        self.assertIn("[ورقة: Budget]", out)
        self.assertIn("XLSX-7722-BB", out)
        self.assertIn("=100+250", out)  # الصيغة لا تُفقد

    def test_pptx_slide_text(self):
        from pptx import Presentation
        p = self.dir / "a.pptx"
        prs = Presentation()
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = "AUDIT PPTX"
        s.placeholders[1].text = "PPTX secret code: PPTX-9944-CC"
        prs.save(p)
        out = extract.extract_text(p)
        self.assertIn("[شريحة 1]", out)
        self.assertIn("PPTX-9944-CC", out)

    def test_csv_txt_code(self):
        csv_p = self.dir / "a.csv"
        csv_p.write_text("name,code\nCSV secret,CSV-1188-DD\n", encoding="utf-8")
        txt_p = self.dir / "a.txt"
        txt_p.write_text("TXT secret code: TXT-6655-EE\n", encoding="utf-8")
        py_p = self.dir / "a.py"
        py_p.write_text("# CODE secret marker: CODE-2211-FF\n", encoding="utf-8")
        self.assertIn("CSV-1188-DD", extract.extract_text(csv_p))
        self.assertIn("TXT-6655-EE", extract.extract_text(txt_p))
        self.assertIn("CODE-2211-FF", extract.extract_text(py_p))

    def test_empty_file_returns_empty(self):
        p = self.dir / "empty.txt"
        p.write_text("", encoding="utf-8")
        self.assertEqual(extract.extract_text(p).strip(), "")


# ---------------------------------------------------------------- ترتيب البحث
class _FakeBM25:
    def __init__(self, scores):
        self._scores = scores

    def get_scores(self, _q):
        return list(self._scores)


class RagRankingTests(unittest.TestCase):
    def test_filename_extension_bonus_prefers_python_file(self):
        docs = [
            {"source": "دليل\\عام.pdf", "title": "دليل", "text": "محتوى عام عن الملفات"},
            {"source": "من_الشات\\test_code.py", "title": "test_code", "text": "print(1)"},
        ]
        # BM25 يفضّل الدليل قليلاً؛ يجب أن يتغلّب عليه وسم اسم الملف/الامتداد
        state = {
            "docs": docs,
            "bm25": _FakeBM25([1.0, 0.85]),
            "vectors": None,
            "mtime": 0.0,
            "title_tok": [set(rag.tokenize(d["title"])) for d in docs],
            "source_tok": [set(rag.tokenize(f"{d['source']} {d['title']}")) for d in docs],
        }
        with mock.patch.object(rag, "_load_index", lambda *a, **k: None), \
             mock.patch.object(rag, "_state", state):
            hits = rag.search("ما هو رمز CODE في ملف Python؟", k=2)
        self.assertTrue(hits)
        self.assertIn("test_code.py", hits[0]["source"])

    def test_tokenize_splits_codes(self):
        self.assertEqual(rag.tokenize("CODE-2211-FF"), ["code", "2211", "ff"])


# ---------------------------------------------------------------- قاعدة البيانات
class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self._old_path = history.DB_PATH
        history.DB_PATH = str(self.db_path)
        history._conn = None
        self.chat_id = history.create_chat("اختبار")

    def tearDown(self):
        if history._conn is not None:
            history._conn.close()
        history._conn = None
        history.DB_PATH = self._old_path
        self.tmp.cleanup()

    def test_edit_user_message_metadata_and_truncation(self):
        uid = history.add_message(self.chat_id, "user", "الأولى")
        aid = history.add_message(self.chat_id, "assistant", "إجابة", agent="research")
        before = history.get_message(self.chat_id, uid)
        edited = history.edit_user_message(self.chat_id, uid, "الثانية")
        self.assertIsNotNone(edited)
        self.assertEqual(edited["content"], "الثانية")
        self.assertIsNotNone(edited["edited_at"])
        self.assertEqual(edited["created"], before["created"])  # الوقت الأصلي محفوظ
        # حذف ما بعد الرسالة المعدّلة
        self.assertIsNone(history.get_message(self.chat_id, aid))
        # نسخة قديمة محفوظة
        with history._lock:
            rows = history._db().execute(
                "SELECT content FROM message_versions WHERE message_id=?", (uid,)).fetchall()
        self.assertEqual([r[0] for r in rows], ["الأولى"])

    def test_edit_rejects_assistant_and_unknown(self):
        aid = history.add_message(self.chat_id, "assistant", "إجابة", agent="research")
        self.assertIsNone(history.edit_user_message(self.chat_id, aid, "x"))
        self.assertIsNone(history.edit_user_message(self.chat_id, 999999, "x"))

    def test_feedback_visible_in_list_chats(self):
        history.add_message(self.chat_id, "user", "سؤال")
        history.add_message(self.chat_id, "assistant", "إجابة", agent="research")
        res = history.set_conversation_feedback(self.chat_id, "dislike")
        self.assertEqual(res["conversation_feedback"], "dislike")
        row = [c for c in history.list_chats() if c["id"] == self.chat_id][0]
        self.assertEqual(row["conversation_feedback"], "dislike")
        self.assertFalse(row["conversation_feedback_dismissed"])
        history.set_conversation_feedback(self.chat_id, "dismiss")
        row = [c for c in history.list_chats() if c["id"] == self.chat_id][0]
        self.assertIsNone(row["conversation_feedback"])
        self.assertTrue(row["conversation_feedback_dismissed"])
        self.assertIsNone(history.set_conversation_feedback(self.chat_id, "bogus"))

    def test_share_roundtrip_theme_lang_media(self):
        att = [{"name": "x.jpg", "library_id": "lib1", "kind": "image"}]
        history.add_message(self.chat_id, "user", "سؤال", attachments=att)
        history.add_message(self.chat_id, "assistant", "```python\nprint(1)\n```", agent="research")
        created = history.create_share(self.chat_id, [], "عنوان", theme="light", lang="ar")
        self.assertIsNotNone(created)
        self.assertEqual((created["theme"], created["lang"], created["count"]), ("light", "ar", 2))
        data = history.get_share(created["id"])
        self.assertEqual(data["theme"], "light")
        self.assertEqual(data["lang"], "ar")
        self.assertEqual(data["messages"][0]["attachments"][0]["library_id"], "lib1")
        self.assertIn("```python", data["messages"][1]["content"])
        self.assertIsNone(history.get_share("does-not-exist"))
        self.assertIsNone(history.create_share("missing-chat", [], None))


# ---------------------------------------------------------------- CV
class CvPagesTests(unittest.TestCase):
    PROFILE = {
        "full_name": "أحمد محمد",
        "job_title": "مهندس برمجيات",
        "summary": "ملخص مهني " * 20,
        "email": "a@b.com", "phone": "0100", "city": "أسيوط",
        "education": [{"degree": "BSc CS", "institution": "Sphinx", "year": "2026"}],
        "experience": [{"role": "Intern", "company": "X", "period": "2025",
                        "bullets": ["عمل 1", "عمل 2"]}],
        "projects": [{"name": "P", "tech": "Python", "bullets": ["بند"]}],
        "skills": ["Python", "SQL"],
        "courses": ["ML"],
        "languages": ["العربية", "English"],
    }

    def test_page_breaks_match_requested_pages(self):
        for pages in range(1, 9):
            html = cvgen.render_html(self.PROFILE, "ar", {"pages": pages})
            breaks = html.count("break-before: page")
            self.assertEqual(breaks, pages - 1, f"pages={pages}")

    def test_ats_single_column_and_readable(self):
        html = cvgen.render_html(self.PROFILE, "en", {"pages": 1})
        self.assertIn('class="ats-line"', html)          # نسخة نصية صديقة لأنظمة ATS
        self.assertNotIn("column-count", html)           # عمود واحد
        self.assertIn("<h2>", html)                      # عناوين قياسية
        self.assertIn('dir="ltr"', html)
        html_ar = cvgen.render_html(self.PROFILE, "ar", {"pages": 1})
        self.assertIn('dir="rtl"', html_ar)

    def test_invalid_page_count_falls_back_to_auto(self):
        html = cvgen.render_html(self.PROFILE, "ar", {"pages": 99})
        self.assertEqual(html.count("break-before: page"), 0)


# ---------------------------------------------------------------- انحدار مصدر الجامعة
class UniversityIngestionRegressions(unittest.TestCase):
    """حالات انحدار مستمدة من نتائج المعالجة الفعلية لدليل الجامعة."""

    def test_corrupt_pdf_recorded_as_failed_not_crash(self):
        """الملف التالف Lectuer1,2,3.pdf يُسجّل كفشل ولا يسقط كامل خط الأنابيب."""
        status = university_ingest.get_status()
        # يجب أن تكون المعالجة قد اكتملت (لا محاولات معلّقة) وأن يكون هناك سجل خطأ واحد على الأقل للملف التالف.
        self.assertEqual(status["counts"]["pending"], 0)
        errors = status.get("errors", [])
        self.assertTrue(any("Lectuer1,2,3.pdf" in e.get("rel", "") for e in errors),
                        f"يجب تسجيل خطأ للملف التالف: {errors}")

    def test_university_retrieval_returns_correct_course(self):
        """الاسترجاع من مواد الجامعة يُعيد مادة Operation Research عند السؤال عنها."""
        hits = university_ingest.search_university(
            "بحث العمليات Operation Research البرمجة الخطية", k=4)
        self.assertTrue(hits, "يجب إرجاع نتائج استرجاع")
        courses = { (h.get("metadata") or {}).get("course") for h in hits }
        self.assertIn("Operation Research", courses,
                      f"يجب أن تشمل أعلى نتائج استرجاع مادة Operation Research،したが: {courses}")

    def test_university_chunks_have_citation_metadata(self):
        """كل مقطع مفهرس يحتفظ ببيانات الاستشهاد (المسار relative،.course، SHA-256)."""
        chunks = university_ingest.load_university_chunks()
        self.assertTrue(chunks, "يجب أن يكون هناك مقاطع مفهرسة")
        for ch in chunks[:20]:
            md = ch.get("metadata") or {}
            self.assertIn("source_rel", md)
            self.assertIn("course", md)
            self.assertIn("sha256", md)
            self.assertIn("extractor", md)
            self.assertTrue(ch.get("text"), "لا يجب أن يكون نص المقطع فارغاً")


# ---------------------------------------------------------------- انحدار حاسبة GPA (واجهة API)
class GpaApiRegressions(unittest.TestCase):
    """تأكيد أن واجهة GPA تُعيد أخطاء واضحة للمدخلات غير الصالحة (لا تُثبّت التحقّق)."""

    def test_invalid_grade_returns_400_with_actionable_message(self):
        import requests
        base = "http://127.0.0.1:8765"
        try:
            r = requests.post(base + "/api/tools/gpa",
                              json={"rows": [{"course": "M", "hours": 3, "grade": "A"}],
                                  "scale": "egypt5", "lang": "ar"}, timeout=15)
        except Exception:
            self.skipTest("الخادم المحلي غير متاح لاختبار واجهة GPA")
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertIn("A", body.get("error", ""))          # التقدير المرفوض مذكور (حرف لاتيني)
        self.assertIn("ممتاز", body.get("error", ""))      # التقديرات المتاحة مذكورة

    def test_valid_gpa_returns_200_and_correct_value(self):
        import requests
        base = "http://127.0.0.1:8765"
        try:
            r = requests.post(base + "/api/tools/gpa",
                              json={"rows": [{"course": "رياضيات", "hours": 3, "grade": "ممتاز"},
                                            {"course": "فيزياء", "hours": 3, "grade": "جيد"}],
                                  "scale": "egypt5", "lang": "ar"}, timeout=15)
        except Exception:
            self.skipTest("الخادم المحلي غير متاح لاختبار واجهة GPA")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["gpa"], 4.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
