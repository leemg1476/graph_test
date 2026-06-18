from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from .config import Settings


@contextmanager
def connect(settings: Settings | None = None) -> Iterator[psycopg.Connection]:
    cfg = settings or Settings()
    conn = psycopg.connect(cfg.dsn, row_factory=dict_row)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def prepare_age(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS age")
        cur.execute("LOAD 'age'")
        cur.execute('SET search_path = ag_catalog, "$user", public')

