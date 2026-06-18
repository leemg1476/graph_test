from __future__ import annotations

import hashlib
import math
import re


TOKEN_RE = re.compile(r"[A-Za-z0-9\uac00-\ud7a3_]{2,}")


def _has_hangul(value: str) -> bool:
    return any("\uac00" <= char <= "\ud7a3" for char in value)


class HashingEmbedder:
    """Small deterministic embedder for local ingestion and tests.

    This keeps the storage contract vector-like without requiring a separate
    embedding model server. It can be replaced later with model embeddings.
    """

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in self._tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dim
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    @staticmethod
    def _tokens(text: str) -> list[str]:
        tokens: list[str] = []
        for token in TOKEN_RE.findall(text.lower()):
            tokens.append(token)
            if _has_hangul(token):
                max_n = min(4, len(token))
                for n in range(2, max_n + 1):
                    tokens.extend(token[i : i + n] for i in range(0, len(token) - n + 1))
        return tokens
