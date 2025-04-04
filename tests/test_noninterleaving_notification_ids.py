# -*- coding: utf-8 -*-
from eventsourcing.persistence import ApplicationRecorder
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.persistence import (
    NonInterleavingNotificationIDsBaseCase,
    tmpfile_uris,
)
from eventsourcing.tests.postgres_utils import drop_postgres_table
from sqlalchemy.engine.url import URL

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore
from eventsourcing_sqlalchemy.recorders import SQLAlchemyApplicationRecorder
from tests.utils import drop_mssql_table


class TestNonInterleaving(NonInterleavingNotificationIDsBaseCase):
    sqlalchemy_db_url = "sqlite:///:memory:"

    def setUp(self) -> None:
        super().setUp()
        self.datastore = SQLAlchemyDatastore(url=self.sqlalchemy_db_url)

    def create_recorder(self) -> ApplicationRecorder:
        recorder = SQLAlchemyApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        self.datastore.init_sqlite_wal_mode()
        return recorder


class TestNonInterleavingSQLiteFileDB(TestNonInterleaving):
    insert_num = 1000

    def setUp(self) -> None:
        uris = tmpfile_uris()
        db_uri = next(uris)
        db_uri = db_uri.lstrip("file:")
        self.sqlalchemy_db_url = "sqlite:///" + db_uri
        super().setUp()

    def test(self) -> None:
        super().test()
        self.assertTrue(self.datastore.is_sqlite_wal_mode)


class TestNonInterleavingPostgres(TestNonInterleaving):
    insert_num = 5000
    sqlalchemy_db_url = (
        "postgresql://eventsourcing:eventsourcing@localhost:5432"
        "/eventsourcing_sqlalchemy"
    )

    def setUp(self) -> None:
        super().setUp()
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def drop_tables(self) -> None:
        with PostgresDatastore(
            dbname="eventsourcing_sqlalchemy",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        ) as datastore:
            drop_postgres_table(datastore, "stored_events")


class TestNonInterleavingMSSQL(TestNonInterleaving):
    insert_num = 5000
    sqlalchemy_db_url = URL.create(  # type: ignore[attr-defined]
        "mssql+pyodbc",
        username="sa",
        password="Password1",
        host="localhost",
        port=1433,
        database="eventsourcing_sqlalchemy",
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "TrustServerCertificate": "yes",
            # "authentication": "ActiveDirectoryIntegrated",
        },
    ).render_as_string(hide_password=False)

    def setUp(self) -> None:
        super().setUp()
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def test(self) -> None:
        with self.assertRaises(
            AssertionError, msg="Somehow MSSQL didn't interleave events"
        ):
            super().test()

    def drop_tables(self) -> None:
        drop_mssql_table("stored_events")


del NonInterleavingNotificationIDsBaseCase
