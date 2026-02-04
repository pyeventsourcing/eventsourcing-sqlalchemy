# -*- coding: utf-8 -*-
from threading import Semaphore
from uuid import uuid4

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    ProcessRecorder,
    StoredEvent,
    Tracking,
)
from eventsourcing.tests.persistence import (
    AggregateRecorderTestCase,
    ApplicationRecorderTestCase,
    ProcessRecorderTestCase,
    tmpfile_uris,
)
from sqlalchemy.future import create_engine
from sqlalchemy.orm import sessionmaker

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore
from eventsourcing_sqlalchemy.recorders import (
    SQLAlchemyAggregateRecorder,
    SQLAlchemyApplicationRecorder,
    SQLAlchemyProcessRecorder,
)


class TestSQLAlchemyAggregateRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SQLAlchemyDatastore(url="sqlite:///:memory:")

    def create_recorder(self) -> AggregateRecorder:
        recorder = SQLAlchemyAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_insert_and_select(self) -> None:
        super(TestSQLAlchemyAggregateRecorder, self).test_insert_and_select()


class TestSQLAlchemyAggregateRecorderWithExternalSession(AggregateRecorderTestCase):
    def setUp(self) -> None:
        session_maker = sessionmaker(bind=create_engine(url="sqlite:///:memory:"))
        self.datastore = SQLAlchemyDatastore(session_maker=session_maker)

    def create_recorder(self) -> AggregateRecorder:
        recorder = SQLAlchemyAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_insert_and_select(self) -> None:
        super(
            TestSQLAlchemyAggregateRecorderWithExternalSession, self
        ).test_insert_and_select()


class TestSQLAlchemySnapshotRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SQLAlchemyDatastore(url="sqlite:///:memory:")

    def create_recorder(self) -> AggregateRecorder:
        recorder = SQLAlchemyAggregateRecorder(
            datastore=self.datastore, events_table_name="snapshots", for_snapshots=True
        )
        recorder.create_table()
        return recorder


class TestSQLAlchemyApplicationRecorder(ApplicationRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SQLAlchemyDatastore(url="sqlite:///:memory:?cache=shared")

    def create_recorder(self) -> ApplicationRecorder:
        recorder = SQLAlchemyApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        self.datastore.init_sqlite_wal_mode()
        return recorder

    def test_insert_select(self) -> None:
        self.assertFalse(self.datastore.is_sqlite_wal_mode)
        super().test_insert_select()

    def test_concurrent_no_conflicts(self, initial_position: int = 0) -> None:
        self.assertFalse(self.datastore.is_sqlite_wal_mode)
        self.assertTrue(self.datastore.access_lock)
        self.assertFalse(self.datastore.write_lock)
        self.assertIsInstance(self.datastore.access_lock, Semaphore)
        super().test_concurrent_no_conflicts(initial_position=initial_position)

    def test_concurrent_no_conflicts_sqlite_filedb(self) -> None:
        uris = tmpfile_uris()
        db_uri = next(uris)
        db_uri = db_uri.lstrip("file:")
        db_url = "sqlite:///" + db_uri
        self.datastore = SQLAlchemyDatastore(url=db_url, connect_args={"timeout": 15})
        self.assertFalse(self.datastore.access_lock)
        self.assertTrue(self.datastore.write_lock)
        self.assertIsInstance(self.datastore.write_lock, Semaphore)
        super().test_concurrent_no_conflicts()
        self.assertTrue(self.datastore.is_sqlite_wal_mode)


class TestSQLAlchemyProcessRecorder(ProcessRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SQLAlchemyDatastore(url="sqlite:///:memory:")

    def create_recorder(self) -> ProcessRecorder:
        recorder = SQLAlchemyProcessRecorder(
            datastore=self.datastore,
            events_table_name="stored_events",
            tracking_table_name="tracking",
        )
        recorder.create_table()
        return recorder

    def test_has_tracking_id(self) -> None:
        super().test_has_tracking_id()

    def test_performance(self) -> None:
        super().test_performance()

    def test_max_tracking_id_query_should_be_filtered_by_application_name(self) -> None:
        recorder = self.create_recorder()
        self.assertEqual(
            recorder.max_tracking_id("upstream_app1"),
            None,
        )
        self.assertEqual(
            recorder.max_tracking_id("upstream_app2"),
            None,
        )

        originator_id1 = uuid4()

        stored_event1 = StoredEvent(
            originator_id=originator_id1,
            originator_version=1,
            topic="topic1",
            state=b"state1",
        )
        tracking1 = Tracking(
            application_name="upstream_app1",
            notification_id=1,
        )

        recorder.insert_events(
            stored_events=[
                stored_event1,
            ],
            tracking=tracking1,
        )

        self.assertEqual(
            recorder.max_tracking_id("upstream_app1"),
            1,
        )
        self.assertEqual(
            recorder.max_tracking_id("upstream_app2"),
            None,
        )


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
