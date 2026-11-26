"""اختبارات انحدار لحاسبة GPA — تثبت إصلاح خطأ 400 والتقديرات غير المعروفة.

يغطي: السلّمين، التنوين/التشكيل، الحروف الصغيرة، النقاط الرقمية،
الأرقام العربية-الهندية، المرادفات الإنجليزية، التراكمي، الصفوف المختلطة،
ورسائل الخطأ القابلة للتنفيذ.
"""
from __future__ import annotations

import unittest

from core import gpatool


class GpaValidTests(unittest.TestCase):
    def test_egypt5_valid_expected_value(self):
        r = gpatool.calc([
            {"course": "رياضيات", "hours": 3, "grade": "ممتاز"},
            {"course": "فيزياء", "hours": 3, "grade": "جيد"},
        ], scale="egypt5", lang="ar")
        # (5*3 + 3*3) / 6 = 4.0
        self.assertEqual(r["gpa"], 4.0)
        self.assertEqual(r["term_hours"], 6.0)
        self.assertEqual(r["errors"], [])

    def test_standard4_valid_expected_value(self):
        r = gpatool.calc([
            {"course": "Math", "hours": 3, "grade": "A"},
            {"course": "Phys", "hours": 3, "grade": "B+"},
        ], scale="standard4", lang="en")
        self.assertEqual(r["gpa"], 3.65)
        self.assertEqual(r["term_hours"], 6.0)

    def test_decimal_hours(self):
        r = gpatool.calc([{"course": "Lab", "hours": 1.5, "grade": "A"}],
                         scale="standard4", lang="en")
        self.assertEqual(r["gpa"], 4.0)
        self.assertEqual(r["term_hours"], 1.5)

    def test_tanween_and_diacritics_normalized(self):
        r = gpatool.calc([{"course": "A", "hours": 3, "grade": "جيد جدًا"}],
                         scale="egypt5", lang="ar")
        self.assertEqual(r["gpa"], 4.0)  # «جيد جدًا» == «جيد جدا»

    def test_lowercase_latin_grade(self):
        r = gpatool.calc([{"course": "M", "hours": 3, "grade": "b+"}],
                         scale="standard4", lang="en")
        self.assertEqual(r["gpa"], 3.3)

    def test_numeric_points_in_grade_field(self):
        r = gpatool.calc([{"course": "M", "hours": 3, "grade": "3.7"}],
                         scale="standard4", lang="en")
        self.assertEqual(r["gpa"], 3.7)

    def test_arabic_indic_digits_hours(self):
        r = gpatool.calc([{"course": "M", "hours": "٣", "grade": "ممتاز"}],
                         scale="egypt5", lang="ar")
        self.assertEqual(r["term_hours"], 3.0)
        self.assertEqual(r["gpa"], 5.0)

    def test_english_synonyms_on_arabic_scale(self):
        r = gpatool.calc([{"course": "M", "hours": 3, "grade": "Excellent"}],
                         scale="egypt5", lang="ar")
        self.assertEqual(r["gpa"], 5.0)

    def test_cumulative(self):
        r = gpatool.calc([{"course": "M", "hours": 3, "grade": "ممتاز"}],
                         scale="egypt5", lang="ar",
                         previous_gpa=3.4, previous_hours=30)
        # (3.4*30 + 5*3) / 33 = 3.54545 -> 3.55
        self.assertIn("cumulative", r)
        self.assertEqual(r["cumulative"]["gpa"], 3.55)
        self.assertEqual(r["cumulative"]["total_hours"], 33.0)

    def test_repeated_calc_is_deterministic(self):
        rows = [{"course": "M", "hours": 3, "grade": "A"}]
        a = gpatool.calc(rows, scale="standard4", lang="en")
        b = gpatool.calc(rows, scale="standard4", lang="en")
        self.assertEqual(a["gpa"], b["gpa"])


class GpaInvalidTests(unittest.TestCase):
    def test_empty_rows_raises(self):
        with self.assertRaises(ValueError):
            gpatool.calc([], scale="egypt5", lang="ar")

    def test_zero_and_negative_hours_raise(self):
        with self.assertRaises(ValueError):
            gpatool.calc([{"course": "M", "hours": 0, "grade": "ممتاز"},
                          {"course": "N", "hours": -3, "grade": "ممتاز"}],
                         scale="egypt5", lang="ar")

    def test_cross_scale_grade_error_is_actionable(self):
        with self.assertRaises(ValueError) as ctx:
            gpatool.calc([{"course": "M", "hours": 3, "grade": "A"}],
                         scale="egypt5", lang="ar")
        msg = str(ctx.exception)
        self.assertIn("A", msg)                 # التقدير المرفوض مذكور
        self.assertIn("ممتاز", msg)             # التقديرات المتاحة مذكورة

    def test_english_error_message(self):
        with self.assertRaises(ValueError) as ctx:
            gpatool.calc([{"course": "M", "hours": 3, "grade": "ممتاز"}],
                         scale="standard4", lang="en")
        self.assertIn("Available grades", str(ctx.exception))

    def test_mixed_rows_keep_valid_and_report_invalid(self):
        # صف صالح + صف بتقدير غير معروف: لا يُسقط الصالح ولا يُقبل غير الصالح.
        r = gpatool.calc([
            {"course": "OK", "hours": 3, "grade": "ممتاز"},
            {"course": "BAD", "hours": 2, "grade": "A"},
        ], scale="egypt5", lang="ar")
        self.assertEqual(r["gpa"], 5.0)
        self.assertEqual(r["term_hours"], 3.0)
        self.assertTrue(any("BAD" in e for e in r["errors"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
