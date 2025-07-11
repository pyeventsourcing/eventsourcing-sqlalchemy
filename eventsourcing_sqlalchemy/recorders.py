# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, List, Optional, Sequence, Type, cast
from uuid import UUID

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    IntegrityError,
    Notification,
    ProcessRecorder,
    StoredEvent,
    Subscription,
    Tracking,
)
from sqlalchemy import Column, Table, text
from sqlalchemy.orm import Session

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore, Transaction
from eventsourcing_sqlalchemy.models import (  # type: ignore
    EventRecord,
    StoredEventRecord,
)


class SQLAlchemyAggregateRecorder(AggregateRecorder):
    def __init__(
        self,
        datastore: SQLAlchemyDatastore,
        events_table_name: str,
        schema_name: str | None = None,
        for_snapshots: bool = False,
    ):
        super().__init__()
        self.datastore = datastore
        self.events_table_name = events_table_name
        self.schema_name = schema_name
        record_cls_name = "".join(
            [
                s.capitalize()
                for s in (schema_name or "").split("_")
                + events_table_name.rstrip("s").split("_")
            ]
        )
        if not for_snapshots:
            base_cls: Type[EventRecord] = self.datastore.base_stored_event_record_cls
            self._has_autoincrementing_ids = True
        else:
            base_cls = self.datastore.base_snapshot_record_cls
            self._has_autoincrementing_ids = False
        self.events_record_cls = self.datastore.define_record_class(
            cls_name=record_cls_name,
            table_name=self.events_table_name,
            schema_name=self.schema_name,
            base_cls=base_cls,
        )
        self.stored_events_table = self.events_record_cls.__table__

    def transaction(self, commit: bool = True) -> Transaction:
        return self.datastore.transaction(commit=commit)

    def create_table(self) -> None:
        assert self.datastore.engine is not None
        self.stored_events_table.create(self.datastore.engine, checkfirst=True)

    def insert_events(
        self, stored_events: Sequence[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        with self.transaction(commit=True) as session:
            self._insert_events(session, stored_events, **kwargs)
        return None

    def _insert_events(
        self, session: Session, stored_events: Sequence[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        if len(stored_events) == 0:
            return []
        records = [
            self.events_record_cls(
                originator_id=e.originator_id,
                originator_version=e.originator_version,
                topic=e.topic,
                state=e.state,
            )
            for e in stored_events
        ]
        if self._has_autoincrementing_ids:
            self._lock_table(session)
        for record in records:
            session.add(record)
        if self._has_autoincrementing_ids:
            session.flush()  # We want the autoincremented IDs now.
            return [cast(StoredEventRecord, r).id for r in records]
        else:
            return None

    def _lock_table(self, session: Session) -> None:
        assert self.datastore.engine is not None
        events_table_name = self.events_table_name
        if self.schema_name is not None:
            events_table_name = f"{self.schema_name}.{events_table_name}"
        if self.datastore.engine.dialect.name == "postgresql":
            # Todo: "SET LOCAL lock_timeout = '{x}s'" like in eventsourcing.postgres?
            session.execute(text(f"LOCK TABLE {events_table_name} IN EXCLUSIVE MODE"))
        elif self.datastore.engine.dialect.name == "mssql":
            pass
            # This doesn't work to ensure insert and commit order are the same:
            # session.connection(execution_options={"isolation_level": "SERIALIZABLE"})
            # This avoids deadlocks from TABLOCK but together still doesn't ensure
            # insert and commit order are the same:
            # session.execute(text(f"SET LOCK_TIMEOUT 18;"))
            # This gives deadlocks:
            # session.execute(
            #     text(
            #         f"DECLARE  @HideSelectFromOutput TABLE ( DoNotOutput INT); "  # noqa E702
            #         f"INSERT INTO @HideSelectFromOutput "
            #         f"SELECT TOP 1 Id FROM {events_table_name} "
            #         f"WITH (TABLOCK);"  # noqa E231
            #     )
            # )

    def select_events(
        self,
        originator_id: UUID | str,
        gt: Optional[int] = None,
        lte: Optional[int] = None,
        desc: bool = False,
        limit: Optional[int] = None,
    ) -> List[StoredEvent]:
        with self.transaction(commit=False) as session:
            q = session.query(self.events_record_cls)
            q = q.filter(self.events_record_cls.originator_id == originator_id)
            originator_version: Column[int] = self.events_record_cls.originator_version
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
                    state=(
                        bytes(r.state) if isinstance(r.state, memoryview) else r.state
                    ),
                )
                for r in records
            ]
        return stored_events


class SQLAlchemyApplicationRecorder(SQLAlchemyAggregateRecorder, ApplicationRecorder):
    def insert_events(
        self,
        stored_events: Sequence[StoredEvent],
        *,
        session: Optional[Session] = None,
        **kwargs: Any,
    ) -> Optional[Sequence[int]]:
        if session is not None:
            assert isinstance(session, Session), type(session)
            notification_ids = self._insert_events(session, stored_events, **kwargs)
        else:
            with self.transaction(commit=True) as session:
                notification_ids = self._insert_events(session, stored_events, **kwargs)
        return notification_ids

    def max_notification_id(self) -> int | None:
        try:
            with self.transaction(commit=False) as session:
                # record_class = cast(Type[StoredEventRecord], self.events_record_cls)
                record_class = self.events_record_cls
                q = session.query(record_class)
                q = q.order_by(record_class.id.desc())
                records = q[0:1]
                return records[0].id
        except (IndexError, AssertionError):
            return None

    def select_notifications(
        self,
        start: int | None,
        limit: int,
        stop: int | None = None,
        topics: Sequence[str] = (),
        *,
        inclusive_of_start: bool = True,
    ) -> list[Notification]:
        with self.transaction(commit=False) as session:
            # record_class = cast(Type[StoredEventRecord], self.events_record_cls)
            record_class = self.events_record_cls
            q = session.query(record_class)
            if start is not None:
                if inclusive_of_start:
                    q = q.filter(record_class.id >= start)
                else:
                    q = q.filter(record_class.id > start)
            if stop is not None:
                q = q.filter(record_class.id <= stop)
            if topics:
                q = q.filter(record_class.topic.in_(topics))
            q = q.order_by(record_class.id)  # Make it an index scan
            q = q[0:limit]

            notifications = [
                Notification(
                    id=r.id,
                    originator_id=r.originator_id,
                    originator_version=r.originator_version,
                    topic=r.topic,
                    state=(
                        bytes(r.state) if isinstance(r.state, memoryview) else r.state
                    ),
                )
                for r in q
            ]
        return notifications

    def subscribe(
        self, gt: int | None = None, topics: Sequence[str] = ()
    ) -> Subscription[ApplicationRecorder]:
        msg = "SQLAlchemyApplicationRecorder.subscribe() is not implemented"
        raise NotImplementedError(msg)


class SQLAlchemyProcessRecorder(SQLAlchemyApplicationRecorder, ProcessRecorder):
    def __init__(
        self,
        datastore: SQLAlchemyDatastore,
        events_table_name: str,
        tracking_table_name: str,
        schema_name: str | None = None,
    ):
        super().__init__(
            datastore=datastore,
            events_table_name=events_table_name,
            schema_name=schema_name,
        )
        self.tracking_table_name = tracking_table_name
        self.tracking_record_cls = self.datastore.define_record_class(
            cls_name="NotificationTrackingRecord",
            table_name=self.tracking_table_name,
            schema_name=self.schema_name,
            base_cls=datastore.base_notification_tracking_record_cls,
        )
        self.tracking_table: Table = self.tracking_record_cls.__table__

    def create_table(self) -> None:
        super().create_table()
        self.tracking_table.create(self.datastore.engine, checkfirst=True)

    def _insert_events(
        self, session: Session, stored_events: Sequence[StoredEvent], **kwargs: Any
    ) -> Optional[Sequence[int]]:
        notification_ids = super(SQLAlchemyProcessRecorder, self)._insert_events(
            session, stored_events, **kwargs
        )
        tracking: Optional[Tracking] = kwargs.get("tracking", None)
        if tracking is not None:
            if self.has_tracking_id(
                tracking.application_name, tracking.notification_id
            ):
                raise IntegrityError
            record = self.tracking_record_cls(
                application_name=tracking.application_name,
                notification_id=tracking.notification_id,
            )
            session.add(record)
        return notification_ids

    def max_tracking_id(self, application_name: str) -> int | None:
        with self.transaction(commit=False) as session:
            q = session.query(self.tracking_record_cls)
            q = q.filter(self.tracking_record_cls.application_name == application_name)
            q = q.order_by(self.tracking_record_cls.notification_id.desc())
            try:
                max_id = q[0].notification_id
            except IndexError:
                max_id = None
        return max_id

    def insert_tracking(self, tracking: Tracking) -> None:
        raise NotImplementedError
