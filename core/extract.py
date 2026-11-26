"""استخراج النص من الملفات: PDF / DOCX / PPTX / XLSX / CSV / TXT / MD / JSON.

الصور والصوت والفيديو لا نص مباشر لها (تُفهرس كأرشيف أسماء، وتُحلل بالذكاء البصري
لو النموذج يدعم الصور). كل الاستخراجات آمنة: أي خطأ يرجع نص توضيحي ولا يكسر الفهرسة.
"""
from __future__ import annotations

from pathlib import Path

MAX_CHARS = 120_000

TEXT_EXTS = {".pdf", ".docx", ".pptx", ".xlsx", ".xlsm", ".csv", ".txt", ".md", ".json", ".log", ".html", ".htm", ".py"}


def extract_text(path: Path | str) -> str:
    path = Path(path)
    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            return _pdf(path)
        if ext == ".docx":
            return _docx(path)
        if ext == ".pptx":
            return _pptx(path)
        if ext in (".xlsx", ".xlsm"):
            return _xlsx(path)
        if ext == ".csv":
            return _csv(path)
        if ext in (".txt", ".md", ".json", ".log", ".html", ".htm", ".py"):
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                return f.read(MAX_CHARS)
        return ""
    except Exception as e:  # pragma: no cover
        return f"[تعذر استخراج النص من {path.name}: {e}]"


def _pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts: list[str] = []
    for i, page in enumerate(reader.pages, 1):
        try:
            t = (page.extract_text() or "").strip()
        except Exception:
            t = ""
        if t:
            parts.append(f"[صفحة {i}]\n{t}")
    text = "\n\n".join(parts)[:MAX_CHARS]
    if text.strip():
        return text
    # Scanned/image-only PDF: pypdf returns nothing. Use Gemini OCR when a key exists.
    try:
        from .config import load_config, get_model_key
        cfg = load_config()
        model = ((cfg.get("stt") or {}).get("gemini_model")
                 or (cfg.get("main_models") or {}).get("gemini") or "gemini-flash-lite-latest")
        key = get_model_key("gemini", model, cfg)
        if key:
            from .llm import gemini_extract_document
            ocr = gemini_extract_document(path.read_bytes(), "application/pdf", key, model)
            if ocr.strip():
                return f"[نص مستخرج بالـ OCR من ملف ممسوح]\n{ocr[:MAX_CHARS]}"
    except Exception as e:
        return f"[تعذر استخراج النص من {path.name}: {e}]"
    return ""


def _docx(path: Path) -> str:
    import docx  # python-docx
    d = docx.Document(str(path))
    parts = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)[:MAX_CHARS]


def _pptx(path: Path) -> str:
    from pptx import Presentation  # python-pptx
    prs = Presentation(str(path))
    parts: list[str] = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                t = shape.text_frame.text.strip()
                if t:
                    texts.append(t)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    cells = [c.text.strip() for c in row.cells]
                    if any(cells):
                        texts.append(" | ".join(cells))
        if texts:
            parts.append(f"[شريحة {i}]\n" + "\n".join(texts))
    return "\n\n".join(parts)[:MAX_CHARS]


def _xlsx(path: Path) -> str:
    from openpyxl import load_workbook
    # Keep formulas (they are lost with data_only=True) and cached values when present.
    wb_f = load_workbook(str(path), read_only=True, data_only=False)
    wb_v = load_workbook(str(path), read_only=True, data_only=True)
    parts: list[str] = []
    try:
        for ws_f, ws_v in zip(wb_f.worksheets, wb_v.worksheets):
            parts.append(f"[ورقة: {ws_f.title}]")
            for row_f, row_v in zip(ws_f.iter_rows(values_only=True), ws_v.iter_rows(values_only=True)):
                cells = []
                for f, v in zip(row_f, row_v):
                    if isinstance(f, str) and f.startswith("="):
                        cells.append(f + (f" → {v}" if v is not None else ""))
                    else:
                        cells.append("" if v is None else str(v).strip())
                if any(cells):
                    parts.append(" | ".join(cells))
            parts.append("")
    finally:
        # must close on Windows, otherwise the file handle blocks delete/replace
        for wb in (wb_f, wb_v):
            try:
                wb.close()
            except Exception:
                pass
    return "\n".join(parts)[:MAX_CHARS]


def _csv(path: Path) -> str:
    import csv
    import sys
    try:
        csv.field_size_limit(sys.maxsize)
    except OverflowError:
        csv.field_size_limit(2147483647)
    parts: list[str] = []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except Exception:
            dialect = csv.excel
        for row in csv.reader(f, dialect):
            cells = [c.strip() for c in row]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)[:MAX_CHARS]
