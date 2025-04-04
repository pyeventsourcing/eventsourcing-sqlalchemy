# -*- coding: utf-8 -*-
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parents[1]


def drop_mssql_table(table_name: str) -> None:
    subprocess.run(
        ["make", "drop-mssql-table", f"name={table_name}"], check=True, cwd=BASE_DIR
    )
