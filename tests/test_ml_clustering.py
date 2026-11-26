"""أحد تجارب تعلُّم الآلة الواقعية والقابلة للتنفيذ على العتاد المتاح.

ملحوظات هامة (مصداقية):
- الجهاز: 16 جيجابايت RAM، معالج Intel i7-9850H (6 أنوية/12 خيط)، بطاقة رسومات Intel UHD 630 (1 جيجابايت)،
  وبدون دعم CUDA (torch يعمل على المعالج فقط).
-ゆえ، أي تدريب دقيق (fine-tuning) لنموذج لغوي كبير أو نموذج رؤية كبير غير ممكن ولم يُنفَّذ، ولا يُزعم أنه نُفِّذ.
- التجربة التالية هي تجزؤ/تجميع غير مُشرف (unsupervised clustering) على النصوص المستخرجة فعلياً من مواد الجامعة
  باستخدام scikit-learn على المعالج. هدفها إظهار فهم هيكلي للمحتوى (تجميع وثائق متشابهة موضوعياً)،
  وليس "تدريب نموذج على كل الملفات".
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.decomposition import NMF
from sklearn.metrics import silhouette_score

from core.university_ingest import load_university_chunks

ART_DIR = Path("data/university")
ML_DIR = ART_DIR / "ml_experiments"
ML_DIR.mkdir(parents=True, exist_ok=True)


def _clean(text: str) -> str:
    text = text or ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def run_clustering(n_clusters: int = 8, max_docs: int | None = None) -> dict:
    chunks = load_university_chunks()
    docs = []
    metas = []
    for ch in chunks:
        t = _clean(ch.get("text", ""))
        if len(t) < 40:
            continue
        docs.append(t)
        metas.append(ch.get("metadata") or {})
    if max_docs is not None:
        docs = docs[:max_docs]
        metas = metas[:max_docs]
    if len(docs) < n_clusters * 3:
        return {
            "status": "insufficient_data",
            "n_docs": len(docs),
            "n_clusters": n_clusters,
            "message": "عدد الوثائق غير كافٍ للتجميع بعدد هذه الكتل",
        }

    # تمثيل نصوصي باستخدام TF-IDF (محلي بالكامل، لا يحتاج نموذج خارجي ولا GPU).
    vectorizer = TfidfVectorizer(max_features=4000, stop_words="english", ngram_range=(1, 2),
                                 min_df=2, max_df=0.85)
    X = vectorizer.fit_transform(docs)
    feature_names = np.array(vectorizer.get_feature_names_out())

    # KMeans (تجميع) على المعالج.
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10, max_iter=300)
    labels = kmeans.fit_predict(X)

    # NMF (ت Moor विषयات) لكشف الموضوعات المهيمنة.
    nmf = NMF(n_components=n_clusters, random_state=42, max_iter=500)
    W = nmf.fit_transform(X)
    H = nmf.components_

    # مقاييس تقييم موضوعية.
    try:
        sil = float(silhouette_score(X, labels, sample_size=min(1000, len(docs)), random_state=42))
    except Exception:
        sil = None
    inertia = float(kmeans.inertia_)

    # Top terms لكل كتلة.
    order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
    clusters = []
    for i in range(n_clusters):
        top_terms = [feature_names[idx] for idx in order_centroids[i][:12]]
        #documentes في هذه الكتلة
        member_idx = [j for j, lab in enumerate(labels) if lab == i]
        member_courses = Counter((metas[j] or {}).get("course", "(root)") for j in member_idx)
        top_courses = member_courses.most_common(4)
        clusters.append({
            "cluster": i,
            "size": len(member_idx),
            "top_terms": top_terms,
            "top_courses": top_courses,
            "sample_sources": [(metas[j] or {}).get("source_rel", "") for j in member_idx[:5]],
        })

    # توزيع المواد على الكتل (للكشف عن ارتباط مادة-موضوع).
    course_cluster = defaultdict(Counter)
    for j, lab in enumerate(labels):
        course = (metas[j] or {}).get("course", "(root)")
        course_cluster[course][int(lab)] += 1

    result = {
        "status": "ok",
        "n_docs": len(docs),
        "n_clusters": n_clusters,
        "features": int(X.shape[1]),
        "silhouette": round(sil, 4) if sil is not None else None,
        "kmeans_inertia": round(inertia, 2),
        "clusters": clusters,
        "course_cluster_matrix": {c: dict(cnt) for c, cnt in course_cluster.items()},
        "artifact": "document_clustering_tfidf_kmeans",
        "note": "تنفيذ محلي على المعالج (CPU) باستخدام scikit-learn؛ لا Fine-tuning ولا نموذج خارجي ولا GPU.",
    }
    out_path = ML_DIR / "document_clustering.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    res = run_clustering(n_clusters=8)
    print(json.dumps({"status": res["status"], "n_docs": res.get("n_docs"),
                      "n_clusters": res.get("n_clusters"), "silhouette": res.get("silhouette"),
                      "inertia": res.get("kmeans_inertia")}, ensure_ascii=False))
    for c in res.get("clusters", []):
        print(f"Cluster {c['cluster']} (size={c['size']}): terms={c['top_terms'][:6]} "
              f"courses={c['top_courses']}")


if __name__ == "__main__":
    main()
