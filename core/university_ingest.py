"""Incremental, read-only ingestion pipeline for a local university knowledge source.

Design goals:
- Never modify/delete source files.
- Incremental by SHA-256 content hash + mtime/size metadata.
- Isolated artifacts under data/university/.
- Per-file error isolation and resumable manifest.
- Produces structured records/chunks consumable by existing RAG.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATA_DIR, INDEX_DIR

# Default target requested by user; can be overridden by API/config.
DEFAULT_UNIVERSITY_DIR = Path(r"E:\Level 3 Term 1 2026 Sphinx University")

ART_DIR = DATA_DIR / "university"
MANIFEST_PATH = ART_DIR / "manifest.json"
INVENTORY_PATH = ART_DIR / "inventory.json"
RECORDS_PATH = ART_DIR / "records.jsonl"
STATUS_PATH = ART_DIR / "status.json"
CHUNKS_PATH = INDEX_DIR / "university_chunks.json"

# Keep ingestion safe and bounded.
MAX_TEXT_CHARS = 120_000
MAX_FILE_BYTES = 60 * 1024 * 1024  # skip very large files by default; recorded in manifest
EXCLUDE_DIR_NAMES = {".git", "__pycache__", ".venv", "venv", "node_modules", ".idea", ".vscode"}
EXCLUDE_EXTS = {".exe", ".dll", ".so", ".dylib", ".bin", ".msi", ".psd", ".db", ".sqlite", ".sqlite3"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}

# Extensions we attempt to process with specialized adapters.
SUPPORTED_EXTS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".xlsm", ".csv", ".txt", ".md", ".json", ".log", ".html", ".htm",
    ".py", ".ipynb", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".mp4", ".mov", ".mkv", ".webm",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except Exception:
        return path.name


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_dirs() -> None:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, obj: Any) -> None:
    _ensure_dirs()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    _ensure_dirs()
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def discover_files(root: Path) -> list[Path]:
    files: list[Path] = []
    if not root.exists():
        return files
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        parts = {x.lower() for x in p.parts}
        if parts & EXCLUDE_DIR_NAMES:
            continue
        if p.suffix.lower() in EXCLUDE_EXTS:
            continue
        files.append(p)
    return sorted(files)


def build_inventory(root: Path = DEFAULT_UNIVERSITY_DIR) -> dict:
    _ensure_dirs()
    files = discover_files(root)
    by_hash: dict[str, list[str]] = {}
    items = []
    for p in files:
        try:
            st = p.stat()
            rel = _safe_rel(p, root)
            sha = _sha256(p)
            rec = {
                "path": str(p),
                "rel": rel,
                "course": rel.split("/", 1)[0] if "/" in rel else rel,
                "parent": str(p.parent.relative_to(root)).replace("\\", "/") if p.parent != root else "",
                "name": p.name,
                "ext": p.suffix.lower(),
                "mime": mimetypes.guess_type(p.name)[0],
                "size": st.st_size,
                "mtime": st.st_mtime,
                "sha256": sha,
            }
            items.append(rec)
            by_hash.setdefault(sha, []).append(rel)
        except Exception as e:
            items.append({"path": str(p), "rel": _safe_rel(p, root), "error": str(e), "status": "inventory_error"})
    duplicates = {h: v for h, v in by_hash.items() if len(v) > 1}
    inv = {
        "root": str(root),
        "generated_at": _utc_now(),
        "count": len(items),
        "duplicates": duplicates,
        "files": items,
    }
    _save_json(INVENTORY_PATH, inv)
    return inv


def _load_manifest() -> dict:
    m = _load_json(MANIFEST_PATH, {})
    if not isinstance(m, dict):
        m = {}
    m.setdefault("version", 1)
    m.setdefault("root", str(DEFAULT_UNIVERSITY_DIR))
    m.setdefault("files", {})  # keyed by rel path
    m.setdefault("updated_at", None)
    return m


def _status_from_manifest(manifest: dict) -> dict:
    files = manifest.get("files", {})
    counts = {"discovered": 0, "processed": 0, "failed": 0, "skipped": 0, "duplicates": 0, "pending": 0}
    by_ext: dict[str, dict[str, int]] = {}
    by_course: dict[str, dict[str, int]] = {}
    errors = []
    for rel, rec in files.items():
        counts["discovered"] += 1
        st = rec.get("status", "pending")
        key = "duplicates" if st == "duplicate" else st
        if key in counts:
            counts[key] += 1
        else:
            counts["pending"] += 1
        ext = rec.get("ext") or "(none)"
        course = rec.get("course") or "(root)"
        by_ext.setdefault(ext, {"discovered": 0, "processed": 0, "failed": 0, "skipped": 0, "duplicates": 0})
        by_course.setdefault(course, {"discovered": 0, "processed": 0, "failed": 0, "skipped": 0, "duplicates": 0})
        by_ext[ext]["discovered"] += 1
        by_course[course]["discovered"] += 1
        if st in by_ext[ext]:
            by_ext[ext][st] += 1
            by_course[course][st] += 1
        if st == "failed":
            errors.append({"rel": rel, "error": rec.get("error"), "ext": ext, "course": course})
    status = {
        "root": manifest.get("root"),
        "updated_at": manifest.get("updated_at"),
        "counts": counts,
        "by_ext": by_ext,
        "by_course": by_course,
        "errors": errors[:200],
        "manifest_path": str(MANIFEST_PATH),
        "inventory_path": str(INVENTORY_PATH),
        "records_path": str(RECORDS_PATH),
        "chunks_path": str(CHUNKS_PATH),
    }
    _save_json(STATUS_PATH, status)
    return status


def get_status() -> dict:
    _ensure_dirs()
    manifest = _load_manifest()
    if MANIFEST_PATH.exists():
        return _status_from_manifest(manifest)
    # Build light status from inventory if present.
    inv = _load_json(INVENTORY_PATH, None)
    if isinstance(inv, dict) and inv.get("files"):
        files = {}
        for f in inv["files"]:
            if "error" in f:
                files[f.get("rel", f.get("path", "unknown"))] = {**f, "status": "failed", "error": f.get("error")}
            else:
                files[f["rel"]] = {**f, "status": "pending"}
        manifest["root"] = inv.get("root", manifest["root"])
        manifest["files"] = files
        manifest["updated_at"] = _utc_now()
        _save_json(MANIFEST_PATH, manifest)
        return _status_from_manifest(manifest)
    return {"root": str(DEFAULT_UNIVERSITY_DIR), "counts": {"discovered": 0, "processed": 0, "failed": 0, "skipped": 0, "duplicates": 0, "pending": 0}, "errors": [], "message": "No inventory/manifest yet."}


def _extract_pdf(path: Path) -> tuple[str, dict]:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    parts = []
    pages = 0
    for i, page in enumerate(reader.pages, 1):
        pages = i
        try:
            t = (page.extract_text() or "").strip()
        except Exception:
            t = ""
        if t:
            parts.append(f"[Page {i}]\n{t}")
    text = "\n\n".join(parts).strip()
    meta = {"pages": pages, "extractor": "pypdf"}
    if not text:
        # OCR fallback through existing Gemini-based extraction when configured.
        try:
            from .extract import extract_text as fallback_extract
            t2 = fallback_extract(path)
            if t2 and t2.strip():
                return t2[:MAX_TEXT_CHARS], {"pages": pages, "extractor": "extract.extract_text_fallback"}
        except Exception:
            pass
    return text[:MAX_TEXT_CHARS], meta


def _extract_docx(path: Path) -> tuple[str, dict]:
    import docx
    d = docx.Document(str(path))
    parts = []
    for p in d.paragraphs:
        style = (p.style.name or "").lower() if getattr(p, "style", None) else ""
        txt = (p.text or "").strip()
        if not txt:
            continue
        if "heading" in style:
            parts.append(f"## {txt}")
        else:
            parts.append(txt)
    for ti, table in enumerate(d.tables, 1):
        parts.append(f"[Table {ti}]")
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return "\n".join(parts)[:MAX_TEXT_CHARS], {"extractor": "python-docx", "paragraphs": len(d.paragraphs), "tables": len(d.tables)}


def _extract_pptx(path: Path) -> tuple[str, dict]:
    from pptx import Presentation
    prs = Presentation(str(path))
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        parts.append(f"[Slide {i}]")
        for shape in slide.shapes:
            if hasattr(shape, "has_text_frame") and shape.has_text_frame:
                t = (shape.text_frame.text or "").strip()
                if t:
                    parts.append(t)
            if getattr(shape, "has_table", False):
                try:
                    tbl = shape.table
                    for row in tbl.rows:
                        cells = [c.text.strip() for c in row.cells]
                        if any(cells):
                            parts.append(" | ".join(cells))
                except Exception:
                    pass
    return "\n\n".join(parts)[:MAX_TEXT_CHARS], {"extractor": "python-pptx", "slides": len(prs.slides)}


def _extract_xlsx(path: Path) -> tuple[str, dict]:
    from openpyxl import load_workbook
    wb_f = load_workbook(str(path), read_only=True, data_only=False)
    wb_v = load_workbook(str(path), read_only=True, data_only=True)
    parts = []
    try:
        for ws_f, ws_v in zip(wb_f.worksheets, wb_v.worksheets):
            parts.append(f"[Sheet: {ws_f.title}]")
            rows = 0
            for row_f, row_v in zip(ws_f.iter_rows(values_only=True), ws_v.iter_rows(values_only=True)):
                rows += 1
                cells = []
                for fval, vval in zip(row_f, row_v):
                    if isinstance(fval, str) and fval.startswith("="):
                        cells.append(f"{fval} => {vval}")
                    else:
                        cells.append("" if vval is None else str(vval).strip())
                if any(cells):
                    parts.append(" | ".join(cells))
                if len("\n".join(parts)) > MAX_TEXT_CHARS:
                    break
            parts.append(f"[Sheet rows read: {rows}]")
    finally:
        for wb in (wb_f, wb_v):
            try: wb.close()
            except Exception: pass
    return "\n".join(parts)[:MAX_TEXT_CHARS], {"extractor": "openpyxl", "sheets": len(wb_f.sheetnames)}


def _extract_csv(path: Path) -> tuple[str, dict]:
    import csv
    parts = []
    rows = 0
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        sample = f.read(4096); f.seek(0)
        try: dialect = csv.Sniffer().sniff(sample)
        except Exception: dialect = csv.excel
        for row in csv.reader(f, dialect):
            rows += 1
            cells = [c.strip() for c in row]
            if any(cells):
                parts.append(" | ".join(cells))
            if len("\n".join(parts)) > MAX_TEXT_CHARS:
                break
    return "\n".join(parts)[:MAX_TEXT_CHARS], {"extractor": "csv", "rows_read": rows}


def _extract_ipynb(path: Path) -> tuple[str, dict]:
    obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    parts = []
    for i, cell in enumerate(obj.get("cells", []), 1):
        ctype = cell.get("cell_type", "cell")
        src = cell.get("source", [])
        if isinstance(src, list):
            src = "".join(src)
        src = str(src).strip()
        if src:
            parts.append(f"[{ctype} {i}]\n{src[:4000]}")
        if ctype == "code":
            for out in cell.get("outputs", [])[:2]:
                text = out.get("text")
                if isinstance(text, list):
                    text = "".join(text)
                if text:
                    parts.append(f"[output {i}]\n{str(text)[:2000]}")
    return "\n\n".join(parts)[:MAX_TEXT_CHARS], {"extractor": "ipynb", "cells": len(obj.get("cells", []))}


def _extract_image(path: Path) -> tuple[str, dict]:
    # Lightweight local metadata + optional OCR if available; no external transmission.
    meta = {"extractor": "image-metadata"}
    try:
        import cv2
        img = cv2.imread(str(path))
        if img is not None:
            h, w = img.shape[:2]
            meta.update({"width": w, "height": h, "channels": int(img.shape[2]) if len(img.shape) > 2 else 1})
    except Exception:
        pass
    text = f"[Image file: {path.name}]\nPath: {path}\n"
    if meta.get("width"):
        text += f"Dimensions: {meta['width']}x{meta['height']}\n"
    # Optional OCR via pytesseract if installed.
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        ocr = pytesseract.image_to_string(Image.open(path))
        if ocr and ocr.strip():
            text += "\n[OCR]\n" + ocr.strip()[:20000]
            meta["extractor"] = "pytesseract"
    except Exception:
        pass
    return text[:MAX_TEXT_CHARS], meta


def _extract_video(path: Path) -> tuple[str, dict]:
    meta = {"extractor": "video-metadata"}
    text = f"[Video file: {path.name}]\n"
    try:
        import cv2
        cap = cv2.VideoCapture(str(path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS) or 0
            frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            dur = (frames / fps) if fps else None
            meta.update({"fps": fps, "frames": int(frames), "width": w, "height": h, "duration_sec": dur})
            text += f"Duration: {dur:.2f}s\nResolution: {w}x{h}\nFPS: {fps}\n" if dur else f"Resolution: {w}x{h}\nFPS: {fps}\n"
            # sample a few frames for basic visual metadata only (no heavy model).
            samples = []
            for ratio in (0.1, 0.5, 0.9):
                idx = int(frames * ratio) if frames else 0
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if ok and frame is not None:
                    samples.append({"frame": idx, "mean_brightness": float(frame.mean())})
            if samples:
                meta["frame_samples"] = samples
        cap.release()
    except Exception as e:
        meta["video_error"] = str(e)
    return text[:MAX_TEXT_CHARS], meta


def extract_file(path: Path) -> tuple[str, dict]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return _extract_pdf(path)
    if ext == ".docx":
        return _extract_docx(path)
    if ext == ".pptx":
        return _extract_pptx(path)
    if ext in {".xlsx", ".xlsm"}:
        return _extract_xlsx(path)
    if ext == ".csv":
        return _extract_csv(path)
    if ext == ".ipynb":
        return _extract_ipynb(path)
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}:
        return _extract_image(path)
    if ext in {".mp4", ".mov", ".mkv", ".webm"}:
        return _extract_video(path)
    if ext in {".txt", ".md", ".json", ".log", ".html", ".htm", ".py"}:
        return path.read_text(encoding="utf-8", errors="ignore")[:MAX_TEXT_CHARS], {"extractor": "text"}
    # Fallback to existing extractor.
    from .extract import extract_text
    return (extract_text(path) or "")[:MAX_TEXT_CHARS], {"extractor": "core.extract.extract_text"}


def _chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    # Structure-aware split: headings/page/slide/sheet markers first.
    blocks = re.split(r"\n(?=\[Page |\[Slide |\[Sheet: |## |\[cell |\[Table )", text)
    chunks: list[str] = []
    buf = ""
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if len(b) > max_chars:
            if buf:
                chunks.append(buf.strip()); buf = ""
            for i in range(0, len(b), max_chars - overlap):
                part = b[i:i + max_chars].strip()
                if part:
                    chunks.append(part)
            continue
        if len(buf) + len(b) + 2 > max_chars and buf:
            chunks.append(buf.strip())
            tail = buf[-overlap:] if overlap < len(buf) else ""
            buf = (tail + "\n" + b).strip()
        else:
            buf = (buf + "\n\n" + b).strip() if buf else b
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def _make_records(file_rec: dict, text: str, meta: dict) -> list[dict]:
    rel = file_rec["rel"]
    course = file_rec.get("course") or rel.split("/", 1)[0]
    base = {
        "source_root": file_rec.get("root") or str(DEFAULT_UNIVERSITY_DIR),
        "source_path": file_rec["path"],
        "source_rel": rel,
        "course": course,
        "name": file_rec["name"],
        "ext": file_rec["ext"],
        "mime": file_rec.get("mime"),
        "sha256": file_rec["sha256"],
        "size": file_rec["size"],
        "mtime": file_rec["mtime"],
        "extractor": meta.get("extractor"),
        "extraction_meta": meta,
        "processed_at": _utc_now(),
    }
    chunks = _chunk_text(text)
    if not chunks:
        chunks = [f"[No extractable text] {rel}"]
    records = []
    for i, ch in enumerate(chunks, 1):
        records.append({
            **base,
            "chunk_id": f"{file_rec['sha256'][:16]}:{i}",
            "chunk_index": i,
            "chunk_count": len(chunks),
            "text": ch,
            "title": f"{course} / {file_rec['name']}",
            "source": f"university:{rel}",
        })
    return records


def process_university(root: Path = DEFAULT_UNIVERSITY_DIR, *, force: bool = False, max_files: int | None = None) -> dict:
    """Process university directory incrementally. READ-ONLY on source files."""
    _ensure_dirs()
    root = Path(root)
    inv = build_inventory(root)
    manifest = _load_manifest()
    manifest["root"] = str(root)
    files_map: dict[str, dict] = manifest.get("files", {})
    # Update discovery metadata.
    inv_by_rel = {f["rel"]: f for f in inv.get("files", []) if f.get("rel") and not f.get("error")}
    for rel, f in inv_by_rel.items():
        old = files_map.get(rel, {})
        files_map[rel] = {**old, **f, "status": old.get("status", "pending")}
    # Mark removed files.
    for rel in list(files_map.keys()):
        if rel not in inv_by_rel:
            files_map[rel]["status"] = "skipped"
            files_map[rel]["error"] = "Source file no longer present at inventory time; kept manifest record."
    manifest["files"] = files_map
    _save_json(MANIFEST_PATH, manifest)

    # Duplicate detection: keep first rel per hash as primary; mark others duplicate.
    seen_hash: dict[str, str] = {}
    for rel, rec in sorted(files_map.items()):
        if rec.get("error") and rec.get("status") == "failed":
            continue
        h = rec.get("sha256")
        if not h:
            continue
        if h in seen_hash and seen_hash[h] != rel:
            rec["status"] = "duplicate"
            rec["duplicate_of"] = seen_hash[h]
        else:
            seen_hash[h] = rel
            if rec.get("status") == "duplicate" and not force:
                rec["status"] = "pending"

    # Build processing list.
    to_process = []
    for rel, rec in files_map.items():
        if rec.get("status") == "duplicate":
            continue
        if rec.get("sha256") in (None, ""):
            continue
        ext = (rec.get("ext") or "").lower()
        if ext in ARCHIVE_EXTS:
            rec["status"] = "skipped"
            rec["error"] = f"Archive not auto-extracted for safety: {ext}"
            continue
        if rec.get("size", 0) > MAX_FILE_BYTES:
            rec["status"] = "skipped"
            rec["error"] = f"File too large for default ingestion (> {MAX_FILE_BYTES} bytes)"
            continue
        if ext not in SUPPORTED_EXTS:
            rec["status"] = "skipped"
            rec["error"] = f"Unsupported/unsafe extension for current pipeline: {ext or '(none)'}"
            continue
        prev_hash = rec.get("processed_sha256")
        if not force and rec.get("status") == "processed" and prev_hash == rec.get("sha256"):
            continue
        to_process.append(rel)
    if max_files is not None:
        to_process = to_process[:max(0, int(max_files))]

    processed_records: list[dict] = []
    started = time.time()
    processed_count = 0
    failed_count = 0
    for rel in to_process:
        rec = files_map[rel]
        p = Path(rec["path"])
        try:
            text, meta = extract_file(p)
            records = _make_records({**rec, "root": str(root)}, text, meta)
            processed_records.extend(records)
            rec["status"] = "processed"
            rec["processed_sha256"] = rec.get("sha256")
            rec["processed_at"] = _utc_now()
            rec["extractor"] = meta.get("extractor")
            rec["text_chars"] = len(text or "")
            rec["chunk_count"] = len(records)
            rec.pop("error", None)
            processed_count += 1
        except Exception as e:
            rec["status"] = "failed"
            rec["error"] = f"{type(e).__name__}: {e}"
            rec["traceback_tail"] = traceback.format_exc(limit=3)[-1000:]
            failed_count += 1
        # checkpoint manifest periodically
        if (processed_count + failed_count) % 10 == 0:
            manifest["updated_at"] = _utc_now()
            _save_json(MANIFEST_PATH, manifest)

    # Persist records. For simplicity: rebuild records.jsonl from processed manifest entries currently in this run plus existing? 
    # Better: keep existing records for unchanged processed files; replace records for reprocessed rels.
    if processed_records:
        existing = []
        if RECORDS_PATH.exists():
            with RECORDS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    try:
                        obj = json.loads(line)
                    except Exception:
                        continue
                    if obj.get("source_rel") in set(to_process):
                        continue
                    existing.append(obj)
        # Keep only records whose rel is still processed.
        processed_rels = {rel for rel, r in files_map.items() if r.get("status") == "processed"}
        existing = [r for r in existing if r.get("source_rel") in processed_rels]
        tmp = RECORDS_PATH.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in existing + processed_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, RECORDS_PATH)

    # Build compact RAG chunks file from processed records.
    rag_chunks = []
    if RECORDS_PATH.exists():
        with RECORDS_PATH.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                rag_chunks.append({
                    "source": r.get("source"),
                    "title": r.get("title"),
                    "text": r.get("text", ""),
                    "metadata": {
                        "source_rel": r.get("source_rel"),
                        "course": r.get("course"),
                        "name": r.get("name"),
                        "ext": r.get("ext"),
                        "sha256": r.get("sha256"),
                        "chunk_id": r.get("chunk_id"),
                        "chunk_index": r.get("chunk_index"),
                        "chunk_count": r.get("chunk_count"),
                        "extractor": r.get("extractor"),
                    },
                })
    _save_json(CHUNKS_PATH, {"root": str(root), "updated_at": _utc_now(), "chunks": rag_chunks})

    manifest["updated_at"] = _utc_now()
    manifest["last_run"] = {
        "started_at": started,
        "duration_sec": round(time.time() - started, 3),
        "processed": processed_count,
        "failed": failed_count,
        "selected": len(to_process),
    }
    _save_json(MANIFEST_PATH, manifest)
    status = _status_from_manifest(manifest)
    status["last_run"] = manifest["last_run"]
    return status


def load_university_chunks() -> list[dict]:
    obj = _load_json(CHUNKS_PATH, {})
    if isinstance(obj, dict):
        chunks = obj.get("chunks", [])
        if isinstance(chunks, list):
            return chunks
    return []


def search_university(query: str, k: int = 6) -> list[dict]:
    # Lightweight local lexical scorer over processed university chunks; avoids changing global RAG index format.
    q = (query or "").lower().strip()
    if not q:
        return []
    terms = [t for t in re.findall(r"[a-z0-9_]+|[\u0600-\u06FF]+", q) if len(t) > 1]
    if not terms:
        return []
    chunks = load_university_chunks()
    scored = []
    for ch in chunks:
        text = (ch.get("text") or "")
        title = (ch.get("title") or "")
        hay = (title + "\n" + text).lower()
        score = 0
        for t in terms:
            c = hay.count(t)
            if c:
                score += 1 + min(3, c * 0.2)
        if score <= 0:
            continue
        md = ch.get("metadata") or {}
        scored.append({
            "score": round(score, 4),
            "source": ch.get("source"),
            "title": ch.get("title"),
            "text": text[:1200],
            "metadata": md,
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[: max(1, min(k, 20))]
