from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.legal_graph_rag.ingest import ingest_legal_corpus


if __name__ == "__main__":
    print(ingest_legal_corpus())
