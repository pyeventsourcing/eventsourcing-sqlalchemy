# -*- coding: utf-8 -*-
import os
import subprocess
from pathlib import Path

from sqlalchemy import MetaData, create_engine, text

BASE_DIR = Path(__file__).parents[1]


def drop_mssql_table(table_name: str) -> None:
    subprocess.run(
        ["make", "drop-mssql-table", f"name={table_name}"], check=True, cwd=BASE_DIR
    )


def drop_pg_tables() -> None:
    url = "postgresql://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
    for schema in ["public", "myschema"]:
        engine = create_engine(url=url)
        meta = MetaData(schema=schema)
        meta.reflect(bind=engine)
        with engine.begin() as conn:
            meta.drop_all(bind=conn)


def pg_close_all_connections(url: str | None = None) -> None:
    try:
        url = os.environ["SQLALCHEMY_URL"]
    except KeyError:
        url = (
            "postgresql://eventsourcing:eventsourcing@localhost:5432/"
            "eventsourcing_sqlalchemy"
        )
    engine = create_engine(url, isolation_level="AUTOCOMMIT")

    terminate_sql = """
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = :dbname
      AND pid <> pg_backend_pid();
    """

    with engine.connect() as conn:
        conn.execute(text(terminate_sql), {"dbname": "eventsourcing_sqlalchemy"})
