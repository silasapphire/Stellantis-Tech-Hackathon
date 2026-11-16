"""RAG lookup over the repair-doc corpus so recommendations shown to users are
grounded, not hallucinated inline by an agent.

Retrieval: Cohere `embed` (search_document / search_query input types) + cosine
similarity in numpy - the corpus is a few dozen documents, so a vector database would be
overkill. Document embeddings are computed once and cached on disk (keyed by a hash of the
corpus + model); only the short query is embedded per search.

If COHERE_API_KEY is missing or the embed call fails, retrieval falls back to keyword
overlap so the tool keeps working (the result says which method was used).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("kb")

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "repair_docs.json"
_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "processed"
_EMBED_MODEL = os.environ.get("COHERE_EMBED_MODEL", "embed-english-v3.0")


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def kb_search_repair_docs(query: str, top_k: int = 3, vehicle_type: str = "") -> list[dict]:
        """RAG lookup over the repair-doc corpus; grounds recommendations shown to users instead of letting an agent hallucinate them. Optionally restrict to vehicle_type 'EV' or 'ICE'."""
        return search(query, top_k, vehicle_type or None)

    @mcp.tool()
    def kb_stats() -> dict:
        """Size and composition of the repair-knowledge corpus."""
        corpus = load_corpus()
        by_type: dict[str, int] = {}
        for d in corpus:
            by_type[d["vehicle_type"]] = by_type.get(d["vehicle_type"], 0) + 1
        return {"documents": len(corpus), "by_vehicle_type": by_type, "embedding_model": _EMBED_MODEL}


@lru_cache(maxsize=1)
def load_corpus() -> list[dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _doc_text(doc: dict) -> str:
    return f"{doc['title']}. {doc['text']}"


def _embed(texts: list[str], input_type: str) -> np.ndarray:
    import cohere

    client = cohere.ClientV2(api_key=os.environ["COHERE_API_KEY"])
    response = client.embed(
        model=_EMBED_MODEL, texts=texts, input_type=input_type, embedding_types=["float"]
    )
    vectors = np.asarray(response.embeddings.float_, dtype=np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


@lru_cache(maxsize=1)
def _doc_embeddings() -> np.ndarray:
    corpus = load_corpus()
    texts = [_doc_text(d) for d in corpus]
    digest = hashlib.sha256((_EMBED_MODEL + "".join(texts)).encode()).hexdigest()[:16]
    cache_file = _CACHE_DIR / f"kb_embeddings_{digest}.npy"
    if cache_file.exists():
        return np.load(cache_file)
    vectors = np.concatenate([_embed(texts[i : i + 96], "search_document") for i in range(0, len(texts), 96)])
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.save(cache_file, vectors)
    except OSError:
        logger.warning("could not cache KB embeddings", exc_info=True)
    return vectors


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


def _keyword_scores(query: str, corpus: list[dict]) -> np.ndarray:
    q = _tokens(query)
    scores = []
    for d in corpus:
        doc = _tokens(_doc_text(d)) | _tokens(d["fault_type"].replace("_", " "))
        scores.append(len(q & doc) / max(len(q), 1))
    return np.asarray(scores)


def search(query: str, top_k: int = 3, vehicle_type: str | None = None) -> list[dict]:
    corpus = load_corpus()
    method = "cohere-embeddings"
    try:
        if not os.environ.get("COHERE_API_KEY"):
            raise RuntimeError("COHERE_API_KEY not set")
        scores = _doc_embeddings() @ _embed([query], "search_query")[0]
    except Exception as exc:
        logger.warning("embedding retrieval unavailable (%s); using keyword fallback", exc)
        method = "keyword-fallback"
        scores = _keyword_scores(query, corpus)

    order = np.argsort(-scores)
    results = []
    for i in order:
        doc = corpus[i]
        if vehicle_type and doc["vehicle_type"] not in (vehicle_type, "ALL"):
            continue
        results.append(
            {
                "doc_id": doc["id"],
                "fault_type": doc["fault_type"],
                "vehicle_type": doc["vehicle_type"],
                "title": doc["title"],
                "text": doc["text"],
                "score": float(scores[i]),
                "retrieval": method,
            }
        )
        if len(results) >= top_k:
            break
    return results
