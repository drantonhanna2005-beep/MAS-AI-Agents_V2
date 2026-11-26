"""حاسبة GPA — حساب حتمي 100% بدون LLM (دقة مضمونة) — ثنائي اللغة (عربي/إنجليزي)."""
from __future__ import annotations

import re

# تطبيع المدخلات: إزالة التشكيل/التنوين، توحيد الهمزات والتاء المربوطة، أرقام عربية-هندية.
_AR_MARKS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def norm_digits(value) -> str:
    """يحوّل الأرقام العربية-الهندية/الفارسية إلى لاتينية (الساعات والنقاط)."""
    return str(value if value is not None else "").translate(_DIGITS)


def norm_grade(value) -> str:
    """تطبيع نص التقدير: «جيد جدًا» == «جيد جدا»، «B+» == «b+»، وإزالة المسافات الزائدة."""
    g = _AR_MARKS.sub("", str(value or ""))
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه"), ("ؤ", "و"), ("ئ", "ي")):
        g = g.replace(a, b)
    return re.sub(r"\s+", " ", g).strip().lower()

SCALES: dict[str, dict[str, float]] = {
    "egypt5": {"ممتاز": 5.0, "جيد جدا": 4.0, "جيد جداً": 4.0, "جيد": 3.0, "مقبول": 2.0, "ضعيف": 1.0, "راسب": 0.0},
    "standard4": {"A": 4.0, "A-": 3.7, "A+": 4.0, "B+": 3.3, "B": 3.0, "B-": 2.7,
                  "C+": 2.3, "C": 2.0, "C-": 1.7, "D+": 1.3, "D": 1.0, "F": 0.0},
}

_SCALE_ALIASES = {"egypt5": "سلّم 5 نقاط (ممتاز..راسب)", "standard4": "سلّم 4 نقاط (A..F)"}
_SCALE_ALIASES_EN = {"egypt5": "5-point scale (Excellent..Fail)", "standard4": "4-point scale (A..F)"}
_MAX_POINTS = {"egypt5": 5.0, "standard4": 4.0}

_T = {
    "ar": {
        "title": "نتيجة حساب المعدل", "gpa": "معدل الترم", "of": "من", "hours_total": "إجمالي ساعات الترم",
        "cum": "المعدل التراكمي بعد الترم", "on": "على", "hours_w": "ساعة", "notes": "ملاحظات",
        "th": ["المادة", "الساعات", "التقدير", "النقاط"],
        "err_hours": "الساعات يجب أن تكون أكبر من صفر.",
        "err_grade": "تقدير غير معروف «{g}» — استخدم التقديرات المتاحة.",
        "err_prev": "المعدل السابق «{p}» غير منطقي لسلّم {m:g} نقاط — تم تجاهل حساب التراكمي.",
        "course_n": "مادة {i}",
        "err_empty": "لا توجد مواد صالحة للحساب — أدخل الساعات والتقديرات.",
        "err_empty_detail": "لا توجد مواد صالحة للحساب — تقديرات غير معروفة: {g}. التقديرات المتاحة لهذا السلّم: {v}.",
    },
    "en": {
        "title": "GPA Result", "gpa": "Term GPA", "of": "out of", "hours_total": "Total term hours",
        "cum": "Cumulative GPA after this term", "on": "over", "hours_w": "hours", "notes": "Notes",
        "th": ["Course", "Hours", "Grade", "Points"],
        "err_hours": "Hours must be greater than zero.",
        "err_grade": "Unknown grade “{g}” — use the available grades.",
        "err_prev": "Previous GPA “{p}” is not valid for a {m:g}-point scale — cumulative ignored.",
        "course_n": "Course {i}",
        "err_empty": "No valid courses — enter hours and grades.",
        "err_empty_detail": "No valid courses — unknown grades: {g}. Available grades for this scale: {v}.",
    },
}


def _grade_points(grade: str, points, scale: str) -> float | None:
    if points is not None and str(points).strip() != "":
        try:
            p = float(norm_digits(points))
            return p if 0 <= p <= _MAX_POINTS[scale] else None
        except Exception:
            return None
    if grade is None or str(grade).strip() == "":
        return None
    # النقاط الرقمية قد تُكتب في حقل التقدير نفسه (كما يوحي placeholder: A / 3.7)
    numeric = norm_digits(grade).strip()
    try:
        p = float(numeric)
        if 0 <= p <= _MAX_POINTS[scale]:
            return p
    except Exception:
        pass
    table = {norm_grade(k): v for k, v in SCALES[scale].items()}
    g = norm_grade(grade)
    if g in table:
        return table[g]
    # مرادفات إنجليزية شائعة للسلّم العربي
    if scale == "egypt5":
        synonyms = {"excellent": "ممتاز", "very good": "جيد جدا", "good": "جيد",
                    "pass": "مقبول", "weak": "ضعيف", "fail": "راسب"}
        if g in synonyms:
            return table.get(norm_grade(synonyms[g]))
    return None


def _label(pct: float, lang: str = "ar") -> str:
    if lang == "en":
        if pct >= 85:
            return "Excellent 🏆"
        if pct >= 75:
            return "Very Good 🌟"
        if pct >= 65:
            return "Good 👍"
        if pct >= 50:
            return "Pass ✅"
        return "Weak — urgent study plan needed 📌"
    if pct >= 85:
        return "ممتاز 🏆"
    if pct >= 75:
        return "جيد جداً 🌟"
    if pct >= 65:
        return "جيد 👍"
    if pct >= 50:
        return "مقبول ✅"
    return "ضعيف — يحتاج خطة مذاكرة عاجلة 📌"


def calc(rows: list[dict], scale: str = "egypt5",
         previous_gpa: float | None = None, previous_hours: float | None = None,
         lang: str = "ar") -> dict:
    """rows: [{"course": اسم اختياري, "hours": عدد الساعات, "grade": تقدير, "points": نقاط اختيارية}]"""
    t = _T.get(lang, _T["ar"])
    if scale not in SCALES:
        scale = "egypt5"
    table_rows: list[dict] = []
    total_points = 0.0
    total_hours = 0.0
    errors: list[str] = []
    bad_grades: list[str] = []
    for i, r in enumerate(rows, 1):
        name = str(r.get("course") or t["course_n"].format(i=i))
        try:
            hours = float(norm_digits(r.get("hours") or 0))
        except Exception:
            hours = 0.0
        pts = _grade_points(str(r.get("grade") or ""), r.get("points"), scale)
        if hours <= 0:
            errors.append(f"{name}: {t['err_hours']}")
            continue
        if pts is None:
            errors.append(f"{name}: " + t["err_grade"].format(g=r.get("grade")))
            bad_grades.append(str(r.get("grade") or "—").strip())
            continue
        total_points += pts * hours
        total_hours += hours
        table_rows.append({"course": name, "hours": hours, "grade": r.get("grade") or f"{pts:g}", "points": pts})
    if total_hours <= 0:
        # رسالة قابلة للتنفيذ: ما التقديرات المرفوضة وما المتاح فعلاً لهذا السلّم.
        valid = "، ".join(sorted(SCALES[scale].keys()))
        if bad_grades:
            uniq = "، ".join(dict.fromkeys(bad_grades))
            raise ValueError(t["err_empty_detail"].format(g=uniq, v=valid))
        raise ValueError(t["err_empty"])
    gpa = round(total_points / total_hours, 2)
    percentage = round(gpa / _MAX_POINTS[scale] * 100, 1)
    result: dict = {
        "scale": scale,
        "scale_name": _SCALE_ALIASES[scale] if lang == "ar" else _SCALE_ALIASES_EN[scale],
        "gpa": gpa, "term_hours": total_hours, "percentage": percentage,
        "label": _label(percentage, lang), "table": table_rows, "errors": errors,
    }
    if previous_gpa is not None and previous_hours is not None:
        try:
            pg, ph = float(norm_digits(previous_gpa)), float(norm_digits(previous_hours))
            if not (0 <= pg <= _MAX_POINTS[scale]) or ph <= 0:
                errors.append(t["err_prev"].format(p=pg, m=_MAX_POINTS[scale]))
            elif ph <= 0:
                errors.append(t["err_hours"])
            else:
                cum = (pg * ph + total_points) / (ph + total_hours)
                cum_pct = round(cum / _MAX_POINTS[scale] * 100, 1)
                result["cumulative"] = {
                    "gpa": round(cum, 2),
                    "percentage": cum_pct,
                    "label": _label(cum_pct, lang),
                    "total_hours": ph + total_hours,
                }
        except (ValueError, TypeError):
            errors.append(t["err_prev"].format(p=previous_gpa, m=_MAX_POINTS[scale]))
    return result


def to_markdown(res: dict, lang: str = "ar") -> str:
    t = _T.get(lang, _T["ar"])
    th = t["th"]
    lines = [f"### 🧮 {t['title']} ({res['scale_name']})", "",
             f"| {th[0]} | {th[1]} | {th[2]} | {th[3]} |", "|---|---|---|---|"]
    for r in res["table"]:
        lines.append(f"| {r['course']} | {r['hours']:g} | {r['grade']} | {r['points']:g} |")
    lines += ["", f"**{t['gpa']}: {res['gpa']}** {t['of']} {_MAX_POINTS[res['scale']]:g} "
                  f"≈ **{res['percentage']}%** — {res['label']}",
              f"{t['hours_total']}: {res['term_hours']:g}"]
    if res.get("cumulative"):
        c = res["cumulative"]
        lines.append(f"**{t['cum']}: {c['gpa']}** ≈ {c['percentage']}% — {c['label']} "
                     f"({t['on']} {c['total_hours']:g} {t['hours_w']})")
    if res.get("errors"):
        sep = " ، " if lang == "ar" else ", "
        lines += ["", f"⚠️ {t['notes']}: " + sep.join(res["errors"])]
    return "\n".join(lines)
