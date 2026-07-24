"""RAG lookup over a small repair-doc corpus so recommendations shown to users
are grounded, not hallucinated inline by an agent. Embeddings via
sentence-transformers, similarity search via plain numpy cosine similarity -
the corpus is small enough that a vector DB/FAISS index would be overkill.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from mcp.server.fastmcp import FastMCP

_CORPUS_PATH = Path(__file__).resolve().parent.parent / "knowledge_base" / "repair_docs.json"
_EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def kb_search_repair_docs(query: str, top_k: int = 3) -> list[dict]:
        """RAG lookup over the repair-doc corpus; grounds recommendations shown to users instead of letting an agent hallucinate them."""
        return _search(query, top_k)


@lru_cache(maxsize=1)
def _load_corpus() -> list[dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def _corpus_embeddings() -> np.ndarray:
    corpus = _load_corpus()
    model = _get_model()
    texts = [f"{doc['title']}. {doc['text']}" for doc in corpus]
    embeddings = model.encode(texts, normalize_embeddings=True)
    return np.asarray(embeddings)


def _search(query: str, top_k: int) -> list[dict]:
    corpus = _load_corpus()
    model = _get_model()
    query_embedding = np.asarray(model.encode([query], normalize_embeddings=True))[0]

    similarities = _corpus_embeddings() @ query_embedding
    top_indices = np.argsort(-similarities)[:top_k]

    return [
        {
            "fault_type": corpus[i]["fault_type"],
            "title": corpus[i]["title"],
            "text": corpus[i]["text"],
            "score": float(similarities[i]),
        }
        for i in top_indices
    ]
