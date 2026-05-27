"""Single source of truth for opening Postgres connections.

Reads `DATABASE_URL` from environment (loaded from `.env` via python-dotenv).
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg
from dotenv import load_dotenv

load_dotenv()


def database_url(test: bool = False) -> str:
    var = "DATABASE_URL_TEST" if test else "DATABASE_URL"
    url = os.environ.get(var)
    if not url:
        raise RuntimeError(f"{var} is not set; see docs/notes/postgres-setup.md")
    return url


@contextmanager
def connect(test: bool = False) -> Iterator[psycopg.Connection]:
    """Open a psycopg connection; commit on success, rollback on exception."""
    with psycopg.connect(database_url(test=test)) as conn:
        yield conn
