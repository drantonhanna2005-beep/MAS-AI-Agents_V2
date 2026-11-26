"""تحليل الفيديو: أخذ لقطات موزّعة زمنياً (OpenCV) + محاولة تفريغ الصوت.

- اللقطات تُرسل لنموذج رؤية مع أزمنتها → وصف فعلي للمحتوى البصري.
- الصوت يحتاج ffmpeg لاستخراجه؛ إن لم يوجد ffmpeg نوضّح ذلك صراحةً بدل ادّعاء
  تفريغ لم يحدث (لا سلوك وهمي).
"""
from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path


def meta(path: Path) -> dict:
    """مدة/أبعاد/معدل إطارات الفيديو."""
    try:
        import cv2
    except Exception:
        return {"ok": False, "error": "OpenCV غير مثبت"}
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"ok": False, "error": "تعذر فتح الفيديو (صيغة غير مدعومة؟)"}
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        return {"ok": True, "fps": round(fps, 2), "frames_total": count,
                "duration": round(count / fps, 2) if fps else None,
                "width": w, "height": h}
    finally:
        cap.release()


def _to_data_url(frame, max_width: int = 960) -> str:
    import cv2
    h, w = frame.shape[:2]
    if w > max_width:
        frame = cv2.resize(frame, (max_width, int(h * max_width / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def sample_frames(path: Path, max_frames: int = 6) -> dict:
    """لقطات موزّعة على مدة الفيديو مع طابع زمني لكل لقطة."""
    try:
        import cv2
    except Exception:
        return {"ok": False, "error": "OpenCV غير مثبت"}
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return {"ok": False, "error": "تعذر فتح الفيديو"}
    frames: list[dict] = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if count > 0 and fps > 0:
            # لقطات عند 0%, 20%, ... 100% تقريباً (بدون تكرار آخر إطار)
            step = max(1, (count - 1) // max(1, max_frames - 1))
            idxs = list(range(0, count, step))[:max_frames]
            for idx in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                du = _to_data_url(frame)
                if du:
                    frames.append({"t": round(idx / fps, 2), "dataUrl": du})
        else:
            # بعض الملفات لا تُبلّغ عن عدد الإطارات: اقرأ متتابعاً
            while len(frames) < max_frames:
                ok, frame = cap.read()
                if not ok:
                    break
                if fps and len(frames) and len(frames) % max(1, int(fps * 2)) == 0:
                    du = _to_data_url(frame)
                    if du:
                        frames.append({"t": round(len(frames) * 2, 2), "dataUrl": du})
    finally:
        cap.release()
    return {"ok": bool(frames), "fps": round(fps, 2) if fps else None,
            "duration": round(count / fps, 2) if (fps and count) else None, "frames": frames}


def transcribe_audio(path: Path, max_seconds: int = 600) -> dict:
    """تفريغ صوت الفيديو عبر Gemini إذا توفّر ffmpeg واستخراج الصوت نجح."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "reason": "ffmpeg غير مثبت — لا يمكن استخراج/تفريغ الصوت"}
    tmp_dir = Path(tempfile.mkdtemp(prefix="vid_audio_"))
    wav = tmp_dir / "audio.wav"
    try:
        cmd = [ffmpeg, "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
               "-t", str(max_seconds), str(wav)]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=180, check=False)
        if not wav.exists() or wav.stat().st_size < 2000:
            return {"ok": False, "reason": "لم يُعثر على مسار صوتي في الفيديو"}
        from .config import load_config, get_model_key
        from .llm import gemini_transcribe
        cfg = load_config()
        model = ((cfg.get("stt") or {}).get("gemini_model")
                 or (cfg.get("main_models") or {}).get("gemini") or "gemini-flash-lite-latest")
        key = get_model_key("gemini", model, cfg)
        if not key:
            return {"ok": False, "reason": "مفتاح Gemini غير متاح لتفريغ الصوت"}
        text = gemini_transcribe(wav.read_bytes(), "audio/wav", key, model)
        return {"ok": bool(text.strip()), "text": text.strip()}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"فشل تفريغ الصوت: {e}"}
    finally:
        try:
            for p in tmp_dir.iterdir():
                p.unlink()
            tmp_dir.rmdir()
        except Exception:
            pass
