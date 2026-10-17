"""Sparse (lexical) vectors for Qdrant hybrid search.

A hashing BM25 encoder: no model download, no new dependency, works offline.
Documents get BM25 term-frequency weights (saturation k1, no length
normalisation); Qdrant's ``Modifier.IDF`` on the sparse vector applies the
inverse document frequency server-side from the collection's own statistics.
Queries get weight 1.0 per distinct term, so the score is the BM25 sum over
matching terms.

Tokens are Unicode word characters, lower-cased with accents folded
("Procédure" and "procedure" match), so identifiers and product names that
dense embeddings blur (e.g. ``ERR_TLS_CERT``, ``oc adm``) still match exactly.
"""
from __future__ import annotations

import re
import unicodedata
import zlib
from collections import Counter
from dataclasses import dataclass

_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class SparseVector:
    indices: list[int]
    values: list[float]


def tokenize(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return [t for t in _TOKEN.findall(folded) if len(t) > 1 or t.isdigit()]


def _index(token: str) -> int:
    # Stable across processes and Python versions (unlike hash()); 31-bit as Qdrant indices are uint32.
    return zlib.crc32(token.encode("utf-8")) & 0x7FFFFFFF


class HashingBM25Encoder:
    """BM25-style sparse encoder over hashed tokens."""

    def __init__(self, k1: float = 1.2) -> None:
        self._k1 = k1

    def encode_document(self, text: str) -> SparseVector:
        counts = Counter(_index(t) for t in tokenize(text))
        return self._vector({i: tf * (self._k1 + 1) / (tf + self._k1) for i, tf in counts.items()})

    def encode_query(self, text: str) -> SparseVector:
        return self._vector({_index(t): 1.0 for t in tokenize(text)})

    @staticmethod
    def _vector(weights: dict[int, float]) -> SparseVector:
        indices = sorted(weights)
        return SparseVector(indices=indices, values=[float(weights[i]) for i in indices])
