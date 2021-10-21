from typing import Any, List, Optional
from uuid import UUID

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    Notification,
    ProcessRecorder,
    StoredEvent,
    Tracking,
)
from sqlalchemy import Column, Table
from sqlalchemy.orm import Session

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore
from eventsourcing_sqlalchemy.models import (
    NotificationTrackingRecord,
    SnapshotRecord,
    StoredEventRecord,
)


class SQLAlchemyAggregateRecorder(AggregateRecorder):
    def __init__(
        self,
        datastore: SQLAlchemyDatastore,
        events_table_name: str,
        for_snapshots: bool = False,
    ):
        super().__init__()
        self.datastore = datastore
        self.events_table_name = events_table_name
        record_cls_name = "".join(
            [s.capitalize() for s in events_table_name.rstrip("s").split("_")]
        )
        if for_snapshots:
            base_cls = SnapshotRecord
        else:
            base_cls = StoredEventRecord
        self.events_record_cls = self.datastore.define_record_class(
            name=record_cls_name, table_name=self.events_table_name, base_cls=base_cls
        )
        self.stored_events_table: Table = self.events_record_cls.__table__

    def create_table(self):
        self.stored_events_table.create(self.datastore.engine, checkfirst=True)

    def insert_events(self, stored_events: List[StoredEvent], **kwargs: Any) -> None:
        with self.datastore.transaction(commit=True) as session:
            self._insert_events(session, stored_events, **kwargs)

    def _insert_events(
        self, session: Session, stored_events: List[StoredEvent], **kwargs
    ):
        if len(stored_events) == 0:
            return
        mappings = [e.__dict__ for e in stored_events]
        self._lock_table(session)
        session.bulk_insert_mappings(mapper=self.events_record_cls, mappings=mappings)

    def _lock_table(self, session: Session):
        if self.datastore.engine.dialect.name == "postgresql":
            session.execute(f"LOCK TABLE {self.events_table_name} IN EXCLUSIVE MODE")

    def select_events(
        self,
        originator_id: UUID,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        with self.datastore.transaction(commit=False) as session:
            q = session.query(self.events_record_cls)
            q = q.filter(self.events_record_cls.originator_id == originator_id)
            originator_version: Column = self.events_record_cls.originator_version
            if gt is not None:
                q = q.filter(originator_version > gt)
            if lte is not None:
                q = q.filter(originator_version <= lte)
            if desc:
                q = q.order_by(originator_version.desc())
            else:
                q = q.order_by(originator_version)
            if limit is not None:
                records = q[0:limit]
            else:
                records = list(q)

            stored_events = [
                StoredEvent(
                    originator_id=r.originator_id,
                    originator_version=r.originator_version,
                    topic=r.topic,
                    state=bytes(r.state)
                    if isinstance(r.state, memoryview)
                    else r.state,
                )
                for r in records
            ]
        return stored_events


class SQLAlchemyApplicationRecorder(SQLAlchemyAggregateRecorder, ApplicationRecorder):
    def max_notification_id(self) -> int:
        with self.datastore.transaction(commit=False) as session:
            q = session.query(self.events_record_cls)
            notification_id: Column = self.events_record_cls.id
            q = q.order_by(notification_id.desc())
            records = q[0:1]
            try:
                max_id = records[0].id
            except IndexError:
                max_id = 0
        return max_id

    def select_notifications(self, start: int, limit: int) -> List[Notification]:
        with self.datastore.transaction(commit=False) as session:
            q = session.query(self.events_record_cls)
            notification_id: Column = self.events_record_cls.id
            q = q.filter(notification_id >= start)
            q = q[0:limit]

            notifications = [
                Notification(
                    id=r.id,
                    originator_id=r.originator_id,
                    originator_version=r.originator_version,
                    topic=r.topic,
                    state=bytes(r.state)
                    if isinstance(r.state, memoryview)
                    else r.state,
                )
                for r in q
            ]
        return notifications


class SQLAlchemyProcessRecorder(SQLAlchemyApplicationRecorder, ProcessRecorder):
    def __init__(
        self,
        datastore: SQLAlchemyDatastore,
        events_table_name: str,
        tracking_table_name: str,
    ):
        super().__init__(datastore=datastore, events_table_name=events_table_name)
        self.tracking_table_name = tracking_table_name
        self.tracking_record_cls = self.datastore.define_record_class(
            name="NotificationTrackingRecord",
            table_name=self.tracking_table_name,
            base_cls=NotificationTrackingRecord,
        )
        self.tracking_table: Table = self.tracking_record_cls.__table__

    def create_table(self):
        super().create_table()
        self.tracking_table.create(self.datastore.engine, checkfirst=True)

    def _insert_events(
        self, session: Session, stored_events: List[StoredEvent], **kwargs
    ):
        super(SQLAlchemyProcessRecorder, self)._insert_events(
            session, stored_events, **kwargs
        )
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            record = self.tracking_record_cls(
                application_name=tracking.application_name,
                notification_id=tracking.notification_id,
            )
            session.add(record)

    def max_tracking_id(self, application_name: str) -> int:
        with self.datastore.transaction(commit=False) as session:
            q = session.query(self.tracking_record_cls)
            notification_id: Column = self.tracking_record_cls.notification_id
            q = q.order_by(notification_id.desc())
            try:
                max_id = q[0].notification_id
            except IndexError:
                max_id = 0
        return max_id
