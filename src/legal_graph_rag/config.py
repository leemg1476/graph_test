from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "legal_graph")
    postgres_user: str = os.getenv("POSTGRES_USER", "legal")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "legal")
    graph_name: str = os.getenv("LEGAL_GRAPH_NAME", "legal_graph")
    embed_dim: int = int(os.getenv("LEGAL_EMBED_DIM", "384"))
    project_root: Path = Path(__file__).resolve().parents[2]

    @property
    def dsn(self) -> str:
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

