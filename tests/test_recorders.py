from eventsourcing.tests.ramdisk import tmpfile_uris

from eventsourcingsqlalchemy.datastore import SqlAlchemyDatastore
from eventsourcingsqlalchemy.recorders import (
    SqlAlchemyAggregateRecorder,
    SqlAlchemyApplicationRecorder,
    SqlAlchemyProcessRecorder,
)


from eventsourcing.tests.aggregaterecorder_testcase import (
    AggregateRecorderTestCase,
)
from eventsourcing.tests.applicationrecorder_testcase import (
    ApplicationRecorderTestCase,
)
from eventsourcing.tests.processrecorder_testcase import ProcessRecorderTestCase


class TestSqlAlchemyAggregateRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SqlAlchemyDatastore("sqlite:///:memory:")

    def create_recorder(self):
        recorder = SqlAlchemyAggregateRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_insert_and_select(self):
        super(TestSqlAlchemyAggregateRecorder, self).test_insert_and_select()


class TestSqlAlchemySnapshotRecorder(AggregateRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SqlAlchemyDatastore("sqlite:///:memory:")

    def create_recorder(self):
        recorder = SqlAlchemyAggregateRecorder(
            datastore=self.datastore, events_table_name="snapshots", for_snapshots=True
        )
        recorder.create_table()
        return recorder


class TestSqlAlchemyApplicationRecorder(ApplicationRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SqlAlchemyDatastore("sqlite:///:memory:?cache=shared")

    def create_recorder(self):
        recorder = SqlAlchemyApplicationRecorder(
            datastore=self.datastore, events_table_name="stored_events"
        )
        recorder.create_table()
        return recorder

    def test_insert_select(self):
        super().test_insert_select()

    def test_concurrent_no_conflicts_sqlite_filedb(self):
        uris = tmpfile_uris()
        db_uri = next(uris)
        db_uri = db_uri.lstrip("file:")
        db_url = f"sqlite:///{db_uri}"
        self.datastore = SqlAlchemyDatastore(url=db_url)
        self.assertTrue(self.datastore.is_sqlite_wal_mode)
        self.assertFalse(self.datastore.access_lock)
        super().test_concurrent_no_conflicts()

    def test_concurrent_no_conflicts(self):
        self.assertFalse(self.datastore.is_sqlite_wal_mode)
        self.assertTrue(self.datastore.access_lock)
        super().test_concurrent_no_conflicts()


class TestSqlAlchemyProcessRecorder(ProcessRecorderTestCase):
    def setUp(self) -> None:
        self.datastore = SqlAlchemyDatastore("sqlite:///:memory:")

    def create_recorder(self):
        recorder = SqlAlchemyProcessRecorder(datastore=self.datastore, events_table_name="stored_events",
                                             tracking_table_name="tracking", )
        recorder.create_table()
        return recorder

    def test_performance(self):
        super().test_performance()


del AggregateRecorderTestCase
del ApplicationRecorderTestCase
del ProcessRecorderTestCase
