"""مولّد CV احترافي رسمي: تحليل ATS + HTML للطباعة PDF + DOCX + PDF حقيقي عبر المتصفح.

- التحليل حتمي 100% (قواعد واضحة).
- التصميم: أبيض رسمي، لون تمييز قابل للاختيار، خط Cairo/Calibri، مقاسات مثل الشركات.
- PDF حقيقي عبر Microsoft Edge / Chrome بوضع headless — وإن فشل يرجع HTML جاهز للطباعة.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from .config import UPLOAD_DIR

TRACK_KEYWORDS: dict[str, list[str]] = {
    "AI": ["python", "machine learning", "deep learning", "nlp", "pytorch", "tensorflow",
           "data analysis", "statistics", "sql", "pandas", "numpy", "computer vision", "llm"],
    "Cyber": ["networking", "linux", "wireshark", "owasp", "penetration testing", "siem",
              "firewall", "cryptography", "incident response", "nmap", "python", "burp suite"],
    "Bioinformatics": ["python", "r", "genomics", "biopython", "statistics", "sql", "data analysis",
                       "machine learning", "blast", "ngs", "linux"],
    "Web": ["html", "css", "javascript", "react", "git", "rest api", "node.js", "typescript",
            "responsive design", "sql", "testing"],
    "Data": ["sql", "excel", "python", "pandas", "power bi", "tableau", "statistics",
             "data cleaning", "dashboards", "machine learning"],
    "General": ["communication", "teamwork", "problem solving", "time management", "git",
                "microsoft office", "english"],
}

ACTION_VERBS = ["built", "developed", "designed", "implemented", "analyzed", "led", "created",
                "optimized", "automated", "improved", "deployed", "tested", "researched", "trained",
                "برمجت", "صممت", "حللت", "طورت", "نفذت", "أنشأت", "قدت", "حسّنت", "دربت"]

_CV_T = {
    "ar": {
        "contact": ("بيانات تواصل كاملة (إيميل + هاتف)", "أضف بريداً إلكترونياً صحيحاً ورقم هاتف في أعلى الـ CV."),
        "summary": ("ملخص مهني محكم (30–80 كلمة)", "اكتب ملخصاً من 30 إلى 80 كلمة يحدد تخصصك وأهم إنجازاتك."),
        "education": ("التعليم مذكور", "أضف قسم التعليم (الدرجة، الجامعة، السنة)."),
        "skills": ("عدد المهارات ≥ 8", "اذكر 8 مهارات فأكثر — ATS يبحث عن الكلمات المفتاحية."),
        "keywords": ("كلمات تخصص {track} المفتاحية", "كلمات مقترح إضافتها: "),
        "quant": ("إنجازات بأرقام مقاسة", "أضف أرقاماً: تحسين 30%، خدمة 500 مستخدم، دقة 95%..."),
        "verbs": ("أفعال قوية لبداية الجمل", "ابدأ كل جملة بفعل قوي: Built / Developed / Analyzed / طورت / صممت..."),
        "links": ("روابط LinkedIn / GitHub", "أضف رابط LinkedIn وGitHub — ضروريان لتخصص الحاسبات."),
        "langs": ("لغات مذكورة", "أضف قسم اللغات (العربية، الإنجليزية...)."),
        "bullets": ("خبرات أو مشروعات مذكورة", "أضف 3 بنود فأكثر من الخبرات أو المشروعات."),
        "labels": {85: "ممتاز — جاهز للتقديم 🏆", 70: "جيد جداً — تعديلات بسيطة 🌟",
                   50: "متوسط — يحتاج تحسين ⚙️", 0: "ضعيف — أعد البناء 🛠️"},
        "sec": {"summary": "الملخص المهني", "edu": "التعليم", "exp": "الخبرات العملية والتدريب",
                "proj": "المشروعات", "skills": "المهارات", "courses": "كورسات وشهادات", "langs": "اللغات"},
    },
    "en": {
        "contact": ("Complete contact info (email + phone)", "Add a valid email and phone number at the top of your CV."),
        "summary": ("Strong professional summary (30–80 words)", "Write a 30–80 word summary defining your specialty and top achievements."),
        "education": ("Education listed", "Add the Education section (degree, university, year)."),
        "skills": ("At least 8 skills", "List 8+ skills — ATS scans for keywords."),
        "keywords": ("{track} track keywords", "Suggested keywords to add: "),
        "quant": ("Quantified achievements", "Add numbers: improved 30%, served 500 users, 95% accuracy..."),
        "verbs": ("Strong action verbs", "Start every bullet with a strong verb: Built / Developed / Analyzed..."),
        "links": ("LinkedIn / GitHub links", "Add LinkedIn and GitHub — essential for CS tracks."),
        "langs": ("Languages listed", "Add a Languages section (Arabic, English...)."),
        "bullets": ("Experience or projects listed", "Add 3+ bullets from experience or projects."),
        "labels": {85: "Excellent — ready to apply 🏆", 70: "Very Good — minor tweaks 🌟",
                   50: "Average — needs work ⚙️", 0: "Weak — rebuild it 🛠️"},
        "sec": {"summary": "Summary", "edu": "Education", "exp": "Experience",
                "proj": "Projects", "skills": "Skills", "courses": "Courses & Certificates", "langs": "Languages"},
    },
}

ACCENTS = {
    "navy": "#1a365d",
    "teal": "#0f766e",
    "burgundy": "#7f1d1d",
    "forest": "#14532d",
    "graphite": "#1f2937",
    "royal": "#1d4ed8",
}


def _norm_items(seq):
    """توحيد إدخالات القوائم (تعليم/خبرات/مشروعات): النص البسيط يصبح قاموساً
    والأنواع غير المدعومة تُتجاهل — يمنع انهيار التحليل أو توليد CV على أي إدخال."""
    if not seq:
        return []
    if isinstance(seq, (str, dict)):
        seq = [seq]
    elif not isinstance(seq, (list, tuple, set)):
        return []
    out = []
    for e in seq:
        if isinstance(e, str):
            e = {"title": e, "name": e}
        if isinstance(e, dict):
            out.append(e)
    return out


def _norm_bullets(val) -> list[str]:
    """توحيد bullets بحيث لو كانت نصاً منفرداً تصبح قائمة، ولا تتفكك حرفاً بحرف."""
    if not val:
        return []
    if isinstance(val, str):
        val = [val]
    elif not isinstance(val, (list, tuple, set)):
        return [str(val)]
    return [str(b) for b in val if _clean(b)]


def analyze(profile: dict, track: str = "General", lang: str = "ar") -> dict:
    t = _CV_T.get(lang, _CV_T["ar"])
    track = track if track in TRACK_KEYWORDS else "General"
    checks: list[dict] = []
    score = 0.0
    max_score = 0.0

    def add(key: str, ok: bool | float, weight: int, extra: str = ""):
        nonlocal score, max_score
        max_score += weight
        val = float(ok) if isinstance(ok, (int, float)) else (1.0 if ok else 0.0)
        score += weight * val
        name, tip = t[key]
        checks.append({"check": name, "ok": val >= 0.99, "partial": 0 < val < 0.99, "tip": tip + extra})

    email = str(profile.get("email") or "")
    phone = str(profile.get("phone") or "")
    add("contact", bool(re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email)) and bool(phone), 15)

    summary = str(profile.get("summary") or "").strip()
    words = len(summary.split())
    add("summary", min(1.0, (words / 30) if words < 30 else (1.0 if words <= 80 else 60 / words)), 10)

    add("education", len(profile.get("education") or []) >= 1, 10)

    skills = [str(s).strip().lower() for s in (profile.get("skills") or []) if str(s).strip()]
    add("skills", min(1.0, len(skills) / 8), 10)

    kws = TRACK_KEYWORDS[track]
    summary_extra = (str(profile.get("summary") or "") + " " + str(profile.get("extra") or "")).lower()
    found = [k for k in kws if any(k in s for s in skills) or k in summary_extra]
    coverage = len(found) / len(kws)
    name, tip = t["keywords"]
    sep = "، " if lang == "ar" else ", "
    missing = [k for k in kws if k not in found]
    checks.append({"check": name.format(track=track), "ok": coverage >= 0.99, "partial": 0 < coverage < 0.99,
                   "tip": tip + sep.join(missing[:8])})
    max_score += 20
    score += 20 * coverage

    bullets: list[str] = []
    for e in _norm_items(profile.get("experience")) + _norm_items(profile.get("projects")):
        bl = _norm_bullets(e.get("bullets")) or ([e.get("details")] if e.get("details") else [])
        bullets.extend([str(b) for b in bl if b])
    quant = sum(1 for b in bullets if re.search(r"\d+\s*(%|ساعة|طالب|مستخدم|مريض|user|accuracy|x)", str(b), re.I))
    add("quant", min(1.0, quant / 3), 10)

    verbs = sum(1 for b in bullets if any(v in str(b).lower() for v in ACTION_VERBS))
    add("verbs", min(1.0, verbs / max(1, len(bullets))), 10)

    add("links", bool(profile.get("linkedin") or profile.get("github")), 5)
    add("langs", len(profile.get("languages") or []) >= 1, 5)
    add("bullets", len(bullets) >= 3, 5)

    final_score = round(score / max_score * 100)
    labels = t["labels"]
    label = labels[85] if final_score >= 85 else labels[70] if final_score >= 70 else \
        labels[50] if final_score >= 50 else labels[0]
    return {
        "score": final_score,
        "label": label,
        "track": track,
        "checks": checks,
        "missing_keywords": [k for k in kws if k not in found],
    }


def _clean(v) -> str:
    return str(v or "").strip().replace("\u200f", "").replace("\u200e", "")


def _esc(v) -> str:
    s = _clean(v)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def _norm_theme(theme: dict | None) -> dict:
    theme = theme or {}
    accent_name = theme.get("accent") if theme.get("accent") in ACCENTS else "navy"
    density = theme.get("density") if theme.get("density") in ("compact", "normal", "large") else "normal"
    style = theme.get("style") if theme.get("style") in ("classic", "modern") else "classic"
    # عدد الصفحات المطلوب (1..8) — يضبط الكثافة تلقائياً ويضيف فواصل صفحات منطقية عند الحاجة
    try:
        pages = int(theme.get("pages") or 0)
    except Exception:
        pages = 0
    pages = pages if 1 <= pages <= 8 else 0
    auto_density = theme.get("density") in (None, "", "auto")
    if pages and auto_density:
        density = "compact" if pages == 1 else "normal" if pages == 2 else "large"
    return {"accent": ACCENTS[accent_name], "accent_name": accent_name,
            "density": density, "style": style, "pages": pages,
            "auto_density": bool(pages and auto_density)}


def render_html(profile: dict, lang: str = "ar", theme: dict | None = None) -> str:
    """قالب CV رسمي أبيض — جاهز للطباعة PDF بدون أي صفحة سوداء."""
    th = _norm_theme(theme)
    rtl = lang == "ar"
    dir_attr = "rtl" if rtl else "ltr"
    name = _esc(profile.get("full_name")) or ("الاسم الكامل" if rtl else "Full Name")
    title = _esc(profile.get("job_title"))
    summary = _esc(profile.get("summary"))
    contact_items = [_esc(profile.get("email")), _esc(profile.get("phone")),
                     _esc(profile.get("city")), _esc(profile.get("linkedin")),
                     _esc(profile.get("github"))]
    contact = "  ·  ".join(x for x in contact_items if x)

    font = "'Cairo', 'Segoe UI', Tahoma, sans-serif" if rtl else "'Calibri', 'Segoe UI', Arial, sans-serif"
    sizes = {"compact": (20, 11.5, 1.45), "normal": (26, 13.5, 1.55), "large": (31, 15.5, 1.65)}
    name_sz, body_sz, lh = sizes[th["density"]]
    pages = th.get("pages") or 0
    if pages >= 3:  # طلب صفحات أكثر → خط أكثر راحة بمقدار العدد (حتى حد معقول)
        extra = min(pages - 2, 3) * 1.1
        body_sz = round(body_sz + extra, 1); lh = round(lh + 0.12 * min(pages - 2, 3), 2)
    # فواصل صفحات منطقية: الخبرات تبدأ صفحة جديدة عند 2+ صفحات، والمشروعات عند 3+
    pb_exp = "page-break-before: always; break-before: page;" if pages >= 2 else ""
    pb_proj = "page-break-before: always; break-before: page;" if pages >= 3 else ""
    # For 4-8 pages, distribute the remaining standard ATS sections across
    # dedicated pages instead of silently collapsing back to 3 pages.
    pb_edu = "page-break-before: always; break-before: page;" if pages >= 4 else ""
    pb_skills = "page-break-before: always; break-before: page;" if pages >= 5 else ""
    pb_courses = "page-break-before: always; break-before: page;" if pages >= 6 else ""
    pb_langs = "page-break-before: always; break-before: page;" if pages >= 7 else ""
    pb_summary = "page-break-before: always; break-before: page;" if pages >= 8 else ""
    accent = th["accent"]
    sec = _CV_T.get(lang, _CV_T["ar"])["sec"]

    def section(key: str, items_html: str, break_style: str = "") -> str:
        items_html = items_html or ""
        if not items_html.strip():
            return ""
        st = f' style="{break_style}"' if break_style else ""
        return f'<section{st}><h2>{sec[key]}</h2>{items_html}</section>'

    edu = "".join(
        f'<div class="item"><div class="row"><b>{_esc(e.get("degree") or e.get("title") or e.get("name"))}</b>'
        f'<span class="when">{_esc(e.get("year"))}</span></div>'
        f'<div class="sub">{_esc(e.get("institution"))}'
        + (f' — {_esc(e.get("details"))}' if _clean(e.get("details")) else "") + "</div></div>"
        for e in _norm_items(profile.get("education")))
    exp = ""
    for e in _norm_items(profile.get("experience")):
        bullets_list = _norm_bullets(e.get("bullets"))
        bullets = "".join(f"<li>{_esc(b)}</li>" for b in bullets_list)
        details_html = f'<div class="sub">{_esc(e.get("details"))}</div>' if _clean(e.get("details")) else ""
        exp += (f'<div class="item"><div class="row"><b>{_esc(e.get("role"))}</b>'
                f'<span class="when">{_esc(e.get("period"))}</span></div>'
                f'<div class="sub">{_esc(e.get("company"))}</div>'
                + details_html
                + (f'<ul>{bullets}</ul>' if bullets else '') + '</div>')
    proj = ""
    for p in _norm_items(profile.get("projects")):
        bullets_list = _norm_bullets(p.get("bullets"))
        bullets = "".join(f"<li>{_esc(b)}</li>" for b in bullets_list)
        tech = _esc(p.get("tech"))
        details_html = f'<div class="sub">{_esc(p.get("details"))}</div>' if _clean(p.get("details")) else ""
        proj += (f'<div class="item"><div class="row"><b>{_esc(p.get("name"))}</b>'
                f'<span class="when">{tech}</span></div>'
                + details_html
                + (f'<ul>{bullets}</ul>' if bullets else '') + '</div>')
    skills_html = ""
    skills = [_esc(s) for s in (profile.get("skills") or []) if _clean(s)]
    if skills:
        skills_html = '<div class="pills">' + "".join(f"<span>{s}</span>" for s in skills) + "</div>"
        skills_html += f'<p class="ats-line">{", ".join(skills)}</p>'
    langs = ", ".join(_esc(s) for s in (profile.get("languages") or []) if _clean(s))
    courses = ", ".join(_esc(s) for s in (profile.get("courses") or []) if _clean(s))

    # نمط modern: شريط علوي بلون التمييز؛ classic: خط أسفل العنوان فقط
    header_extra = ""
    if th["style"] == "modern":
        header_extra = f'<div class="bar"></div>'

    css = f"""
    @page {{ size: A4; margin: 14mm 15mm; }}
    html {{ background: #ffffff; color-scheme: light; }}
    body {{
      background: #ffffff !important; color: #1a1a1a !important;
      font-family: {font}; font-size: {body_sz}px; line-height: {lh};
      max-width: 210mm; margin: 0 auto; padding: 18px 20px;
      -webkit-print-color-adjust: exact; print-color-adjust: exact;
      text-rendering: optimizeLegibility;
    }}
    * {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }}
    .bar {{ height: 6px; background: {accent}; border-radius: 3px; margin-bottom: 10px; }}
    h1 {{ margin: 0 0 2px; font-size: {name_sz}px; font-weight: 800; color: {accent}; letter-spacing: .3px; }}
    .job {{ font-size: {body_sz + 1}px; font-weight: 700; color: #333; margin-bottom: 4px; }}
    .contact {{ color: #333; font-size: {body_sz - 1.5}px; margin: 2px 0 6px; word-break: break-word; }}
    h2 {{ font-size: {body_sz + 1.5}px; font-weight: 800; color: {accent}; margin: 16px 0 6px;
         padding-bottom: 3px; border-bottom: 2px solid {accent}; letter-spacing: .3px; }}
    p {{ margin: 3px 0; }}
    .row {{ display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }}
    .when {{ color: #555; font-size: {body_sz - 1.5}px; font-weight: 600; white-space: nowrap; }}
    .sub {{ color: #444; margin: 1px 0 2px; }}
    ul {{ margin: 3px 0 6px; padding-inline-start: 18px; }}
    li {{ margin: 2px 0; }}
    .pills {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0 6px; }}
    .pills span {{ background: {accent}14; color: {accent}; border: 1px solid {accent}33;
                  padding: 3px 10px; border-radius: 999px; font-size: {body_sz - 1.5}px; font-weight: 600; }}
    .ats-line {{ color: #444; font-size: {body_sz - 1.5}px; }}
    .item {{ margin-bottom: 8px; }}
    section {{ margin-bottom: 4px; }}
    @media print {{
      body {{ padding: 0; margin: 0; }}
      .no-print {{ display: none !important; }}
      section {{ break-inside: avoid; }}
    }}
    @media screen {{
      body {{ box-shadow: 0 0 24px rgba(0,0,0,.08); min-height: 100vh; }}
    }}
    """
    parts = [
        section("summary", f"<p>{summary}</p>" if summary else "", pb_summary),
        section("edu", edu, pb_edu),
        section("exp", exp, pb_exp),
        section("proj", proj, pb_proj),
        section("skills", skills_html, pb_skills),
        section("courses", f"<p>{courses}</p>" if courses else "", pb_courses),
        section("langs", f"<p>{langs}</p>" if langs else "", pb_langs),
    ]
    html = f"""<!doctype html>
<html lang="{'ar' if rtl else 'en'}" dir="{dir_attr}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} — CV</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
{header_extra}
<h1>{name}</h1>
{f'<div class="job">{title}</div>' if title else ''}
<div class="contact">{contact}</div>
{''.join(parts)}
<div class="no-print" style="margin-top:18px;color:#666;font-size:12px">
  {'للطباعة / حفظ PDF: Ctrl+P — الورق A4 — الهوامش Default — فعّل Background graphics' if rtl else 'Print / Save as PDF: Ctrl+P — A4 — Default margins — enable Background graphics'}
</div>
</body></html>"""
    return html


def html_to_pdf(html: str, out_pdf: Path) -> bool:
    """يحوّل HTML إلى PDF حقيقي عبر Edge/Chrome headless. يرجع True عند النجاح."""
    tmp_html = UPLOAD_DIR / f"cv_print_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}.html"
    try:
        tmp_html.write_text(html, encoding="utf-8")
        url = tmp_html.as_uri()
        out_pdf = Path(out_pdf)
        candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        with tempfile.TemporaryDirectory(dir=str(UPLOAD_DIR)) as profile_dir:
            for exe in candidates:
                if not Path(exe).exists():
                    continue
                try:
                    subprocess.run(
                        [exe, "--headless=new", "--disable-gpu", "--no-first-run",
                         f"--user-data-dir={profile_dir}",
                         "--no-pdf-header-footer", "--print-to-pdf-no-header",
                         f"--print-to-pdf={out_pdf}",
                         "--virtual-time-budget=8000",
                         url],
                        timeout=45, check=False,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                except Exception:
                    continue
                if out_pdf.exists() and out_pdf.stat().st_size > 8000:
                    return True
        return False
    finally:
        try:
            if tmp_html.exists():
                tmp_html.unlink()
        except Exception:
            pass


def render_docx(profile: dict, lang: str = "ar", theme: dict | None = None) -> Path:
    """Word رسمي: نفس المحتوى، اتجاه RTL للعربية، خط Cairo/Calibri."""
    import docx
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor, Cm, Twips

    rtl = lang == "ar"
    th = _norm_theme(theme)
    pages = th.get("pages") or 0
    _dens = {"compact": 0, "normal": 1, "large": 2}.get(th.get("density", "normal"), 1)
    if pages >= 3:
        _dens = min(2, _dens + (pages - 2))
    d = docx.Document()
    # هوامش A4 مناسبة وكثافة حسب عدد الصفحات المطلوب
    for s in d.sections:
        s.top_margin = Cm(1.6 + 0.3 * _dens); s.bottom_margin = Cm(1.6 + 0.3 * _dens)
        s.left_margin = Cm(1.8 + 0.2 * _dens); s.right_margin = Cm(1.8 + 0.2 * _dens)
    accent_hex = th["accent"].lstrip("#")
    accent_rgb = RGBColor(int(accent_hex[0:2], 16), int(accent_hex[2:4], 16), int(accent_hex[4:6], 16))

    def _font(run, size=11, bold=False, color=None):
        font_name = "Cairo" if rtl else "Calibri"
        run.font.name = font_name
        rFonts = run._element.rPr.rFonts
        rFonts.set(qn("w:eastAsia"), font_name)
        rFonts.set(qn("w:cs"), font_name)
        run.font.size = Pt(size)
        run.bold = bold
        if color:
            run.font.color.rgb = color
        if rtl:
            rPr = run._element.get_or_add_rPr()
            rtl_el = OxmlElement("w:rtl")
            rPr.append(rtl_el)

    def _p(text="", size=11, bold=False, color=None, align_right=False, space_after=4):
        p = d.add_paragraph()
        if rtl:
            _rtl_p(p)
        elif align_right:
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if text:
            run = p.add_run(text)
            _font(run, size=size, bold=bold, color=color)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.space_before = Pt(0)
        return p

    def _rtl_p(p):
        pPr = p._p.get_or_add_pPr()
        bidi = OxmlElement("w:bidi")
        pPr.append(bidi)
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def _heading(text):
        p = _p(text, size=13, bold=True, color=accent_rgb, space_after=6)
        # خط سفلي عبر حد الفقرة
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "12")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), accent_hex.upper())
        pBdr.append(bottom)
        pPr.append(pBdr)
        return p

    name = _clean(profile.get("full_name")) or ("الاسم الكامل" if rtl else "Full Name")
    _p(name, size=22, bold=True, color=accent_rgb, space_after=2)
    if _clean(profile.get("job_title")):
        _p(_clean(profile.get("job_title")), size=13, bold=True, space_after=4)
    contact = "  |  ".join(x for x in [_clean(profile.get("email")), _clean(profile.get("phone")),
                                       _clean(profile.get("city")), _clean(profile.get("linkedin")),
                                       _clean(profile.get("github"))] if x)
    if contact:
        _p(contact, size=10, space_after=8)

    if _clean(profile.get("summary")):
        if pages >= 8:
            d.add_page_break()
        _heading("الملخص المهني" if rtl else "Summary")
        _p(_clean(profile.get("summary")), size=11)

    if profile.get("education"):
        if pages >= 4:
            d.add_page_break()
        _heading("التعليم" if rtl else "Education")
        for e in _norm_items(profile.get("education")):
            deg = _clean(e.get("degree") or e.get("title") or e.get("name"))
            line = " — ".join(x for x in [deg, _clean(e.get("institution")),
                                          _clean(e.get("year")), _clean(e.get("details"))] if x)
            if line:
                _p(line, size=11, bold=False, space_after=3)
    if profile.get("experience"):
        if pages >= 2:
            d.add_page_break()  # فاصل منطقي: الخبرات في صفحة جديدة عند 2+ صفحات
        _heading("الخبرات" if rtl else "Experience")
        for e in _norm_items(profile.get("experience")):
            head = " — ".join(x for x in [_clean(e.get("role")), _clean(e.get("company")),
                                          _clean(e.get("period"))] if x)
            if head:
                _p(head, size=11, bold=True, space_after=1)
            bullets_list = _norm_bullets(e.get("bullets"))
            for b in bullets_list:
                p = d.add_paragraph(style="List Bullet")
                if rtl:
                    _rtl_p(p)
                run = p.add_run(_clean(b))
                _font(run, size=11)
                p.paragraph_format.space_after = Pt(2)
            if e.get("details") and not bullets_list:
                _p(_clean(e.get("details")), size=11)
    if profile.get("projects"):
        if pages >= 3:
            d.add_page_break()  # المشروعات في صفحة جديدة عند 3+ صفحات
        _heading("المشروعات" if rtl else "Projects")
        for p_ in _norm_items(profile.get("projects")):
            head = " — ".join(x for x in [_clean(p_.get("name")), _clean(p_.get("tech"))] if x)
            if head:
                _p(head, size=11, bold=True, space_after=1)
            bullets_list = _norm_bullets(p_.get("bullets"))
            for b in bullets_list:
                p = d.add_paragraph(style="List Bullet")
                if rtl:
                    _rtl_p(p)
                run = p.add_run(_clean(b))
                _font(run, size=11)
                p.paragraph_format.space_after = Pt(2)
            if p_.get("details") and not bullets_list:
                _p(_clean(p_.get("details")), size=11)
    if profile.get("skills"):
        if pages >= 5:
            d.add_page_break()
        _heading("المهارات" if rtl else "Skills")
        _p(", ".join(_clean(s) for s in profile.get("skills") or []), size=11)
    if profile.get("courses"):
        if pages >= 6:
            d.add_page_break()
        _heading("كورسات وشهادات" if rtl else "Courses")
        _p(", ".join(_clean(s) for s in profile.get("courses") or []), size=11)
    if profile.get("languages"):
        if pages >= 7:
            d.add_page_break()
        _heading("اللغات" if rtl else "Languages")
        _p(", ".join(_clean(s) for s in profile.get("languages") or []), size=11)

    out = UPLOAD_DIR / f"CV_{int(time.time())}_{uuid.uuid4().hex[:8]}.docx"
    d.save(str(out))
    return out
