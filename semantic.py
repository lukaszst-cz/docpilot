from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from .intelligence import expand_query, meaning_score


@dataclass
class SemanticResult:
    score: float
    lexical_score: float
    vector_score: float
    document: dict[str, Any]


_CACHE: dict[str, Any] = {}


def semantic_rank(query: str, documents: list[dict[str, Any]], limit: int = 50) -> list[SemanticResult]:
    """Local dense-vector ranking using TF-IDF + latent semantic analysis.

    This is deliberately model-free: no document content or query is sent to a
    cloud service and there is no model download. If scikit-learn is unavailable
    we fall back to the existing local lexical/synonym scorer.
    """
    docs = [d for d in documents if _document_text(d).strip()]
    if not docs:
        return []
    try:
        return _lsa_rank(query, docs, limit)
    except Exception:
        ranked = sorted(((meaning_score(query, d), d) for d in docs), key=lambda x: x[0], reverse=True)
        return [SemanticResult(float(s), float(s), 0.0, d) for s, d in ranked[:limit] if s > 0]


def _lsa_rank(query: str, documents: list[dict[str, Any]], limit: int) -> list[SemanticResult]:
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    from sklearn.preprocessing import Normalizer

    texts = [_document_text(d) for d in documents]
    fingerprint = _fingerprint(documents)
    cached = _CACHE.get("lsa")
    if cached and cached[0] == fingerprint:
        vectorizer, doc_vectors = cached[1], cached[2]
    else:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=16000,
            min_df=1,
            max_df=0.98,
        )
        matrix = vectorizer.fit_transform(texts)
        if matrix.shape[0] >= 4 and matrix.shape[1] >= 8:
            n_components = max(2, min(128, matrix.shape[0] - 1, matrix.shape[1] - 1))
            svd = TruncatedSVD(n_components=n_components, random_state=42)
            normalizer = Normalizer(copy=False)
            dense = normalizer.fit_transform(svd.fit_transform(matrix))
            # Store a small transform tuple on the vectorizer for query conversion.
            vectorizer._docpilot_svd = svd  # type: ignore[attr-defined]
            vectorizer._docpilot_normalizer = normalizer  # type: ignore[attr-defined]
            doc_vectors = dense
        else:
            doc_vectors = matrix
        _CACHE["lsa"] = (fingerprint, vectorizer, doc_vectors)

    expanded = " ".join([query, *expand_query(query)])
    q = vectorizer.transform([expanded])
    svd = getattr(vectorizer, "_docpilot_svd", None)
    normalizer = getattr(vectorizer, "_docpilot_normalizer", None)
    if svd is not None:
        q = normalizer.transform(svd.transform(q))
    vector_scores = cosine_similarity(q, doc_vectors).ravel()

    results: list[SemanticResult] = []
    for i, d in enumerate(documents):
        lexical = max(0.0, float(meaning_score(query, d)))
        vector = max(0.0, float(vector_scores[i]))
        score = min(1.0, 0.72 * vector + 0.28 * lexical)
        if score > 0.005:
            results.append(SemanticResult(score, lexical, vector, d))
    results.sort(key=lambda x: x.score, reverse=True)
    return results[:limit]


def _document_text(d: dict[str, Any]) -> str:
    md = d.get("metadata") or {}
    return "\n".join([
        str(d.get("source_name") or ""),
        str(md.get("document_type") or ""),
        str(md.get("issuer") or ""),
        str(d.get("category") or ""),
        str(d.get("case_name") or ""),
        " ".join(d.get("tags") or []),
        str(d.get("extracted_text") or "")[:30000],
    ])


def _fingerprint(documents: list[dict[str, Any]]) -> str:
    h = hashlib.sha1()
    for d in documents:
        h.update(str(d.get("id")).encode())
        h.update(str(d.get("updated_at")).encode())
        h.update(str(d.get("sha256")).encode())
    return h.hexdigest()
