# -*- coding: utf-8 -*-
import subprocess
from pathlib import Path

from sqlalchemy import MetaData, create_engine

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
