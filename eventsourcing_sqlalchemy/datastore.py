# -*- coding: utf-8 -*-
import sqlite3
from threading import Semaphore
from typing import Any, Dict, Optional, Tuple, Type, TypeVar, cast

import sqlalchemy.exc
from eventsourcing.persistence import (
    DatabaseError,
    DataError,
    IntegrityError,
    InterfaceError,
    InternalError,
    NotSupportedError,
    OperationalError,
    PersistenceError,
    ProgrammingError,
)
from sqlalchemy import Index, text
from sqlalchemy.future import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from eventsourcing_sqlalchemy.models import (  # type: ignore
    EventRecord,
    NotificationTrackingRecord,
    SnapshotRecord,
    StoredEventRecord,
)

TEventRecord = TypeVar("TEventRecord", bound=EventRecord)


class Transaction:
    def __init__(self, session: Session, commit: bool, lock: Optional[Semaphore]):
        self.session = session
        self.commit = commit
        self.lock = lock

    def __enter__(self) -> Session:
        self.session.begin()
        return self.session

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if exc_val:
                self.session.rollback()
                raise exc_val
            elif not self.commit:
                try:
                    self.session.rollback()
                except sqlite3.OperationalError:
                    pass
            else:
                self.session.commit()
        except sqlalchemy.exc.InterfaceError as e:
            raise InterfaceError from e
        except sqlalchemy.exc.DataError as e:
            raise DataError from e
        except sqlalchemy.exc.OperationalError as e:
            if isinstance(e.args[0], sqlite3.OperationalError) and self.lock:
                pass
            else:
                raise OperationalError from e
        except sqlalchemy.exc.IntegrityError as e:
            raise IntegrityError from e
        except sqlalchemy.exc.InternalError as e:
            raise InternalError from e
        except sqlalchemy.exc.ProgrammingError as e:
            raise ProgrammingError from e
        except sqlalchemy.exc.NotSupportedError as e:
            raise NotSupportedError from e
        except sqlalchemy.exc.DatabaseError as e:
            raise DatabaseError from e
        except sqlalchemy.exc.SQLAlchemyError as e:
            raise PersistenceError from e
        finally:
            self.session.close()
            if self.lock is not None:
                # print(get_ident(), "releasing lock")
                self.lock.release()


class SQLAlchemyDatastore:
    record_classes: Dict[str, Tuple[Type[EventRecord], Type[EventRecord]]] = {}

    def __init__(self, **kwargs: Any):
        kwargs = dict(kwargs)
        self.access_lock: Optional[Semaphore] = kwargs.get("access_lock") or None
        self.write_lock: Optional[Semaphore] = kwargs.get("access_lock") or None
        self.is_sqlite_in_memory_db = kwargs.get("is_sqlite_in_memory_db") or False
        self._init_session(kwargs)
        self._init_sqlite_wal_mode()
        self._init_record_cls(kwargs)

    def _init_session(self, kwargs: Dict[Any, Any]) -> None:
        url: Optional[str] = kwargs.get("url") or None
        session_cls = kwargs.get("session_cls") or None
        if url:
            return self._init_session_with_url(url, kwargs)
        elif session_cls:
            return self._init_session_with_session_cls(session_cls)
        else:
            raise EnvironmentError(
                "SQLAlchemy Datastore must be created with url or session_cls param"
            )

    def _init_session_with_url(self, url: str, kwargs: Dict[Any, Any]) -> None:
        if url.startswith("sqlite"):
            if ":memory:" in url or "mode=memory" in url:
                self.is_sqlite_in_memory_db = True
                connect_args = kwargs.get("connect_args") or {}
                if "check_same_thread" not in connect_args:
                    connect_args["check_same_thread"] = False
                kwargs["connect_args"] = connect_args
                if "poolclass" not in kwargs:
                    kwargs["poolclass"] = StaticPool
                self.access_lock = Semaphore()
            else:
                self.write_lock = Semaphore()

        self.engine = create_engine(echo=False, **kwargs)
        self.session_cls: sessionmaker = sessionmaker(bind=self.engine)

    def _init_session_with_session_cls(self, session_cls: sessionmaker) -> None:
        self.session_cls = session_cls
        self.engine = session_cls().get_bind()

    def _init_sqlite_wal_mode(self) -> None:
        self.is_sqlite_wal_mode = False
        if self.engine.dialect.name != "sqlite":
            return
        if self.is_sqlite_in_memory_db:
            return
        with self.engine.connect() as connection:
            cursor_result = connection.execute(text("PRAGMA journal_mode=WAL;"))
            if list(cursor_result)[0][0] == "wal":
                self.is_sqlite_wal_mode = True

    def _init_record_cls(self, kwargs: Dict[Any, Any]) -> None:
        self.snapshot_record_cls = kwargs.get("snapshot_record_cls") or SnapshotRecord
        self.stored_event_record_cls = (
            kwargs.get("stored_event_record_cls") or StoredEventRecord
        )
        self.notification_tracking_record_cls = (
            kwargs.get("notification_tracking_record_cls") or NotificationTrackingRecord
        )

    def transaction(self, commit: bool) -> Transaction:
        lock: Optional[Semaphore] = None
        if self.access_lock:
            self.access_lock.acquire()
            lock = self.access_lock
        elif commit and self.write_lock:
            # print(get_ident(), "getting lock")
            self.write_lock.acquire()
            # print(get_ident(), "got lock")
            lock = self.write_lock
        return Transaction(self.session_cls(), commit=commit, lock=lock)

    @classmethod
    def define_record_class(
        cls, name: str, table_name: str, base_cls: Type[TEventRecord]
    ) -> Type[TEventRecord]:
        try:
            (record_class, record_base_cls) = cls.record_classes[table_name]
            if record_base_cls is not base_cls:
                raise ValueError(
                    f"Have already defined a record class with table name {table_name} "
                    f"from a different base class {record_base_cls}"
                )
        except KeyError:
            table_args = []
            for table_arg in base_cls.__dict__.get("__table_args__", []):
                if isinstance(table_arg, Index):
                    new_index = Index(
                        f"{table_name}_aggregate_idx",
                        unique=table_arg.unique,
                        *table_arg.expressions,
                    )
                    table_args.append(new_index)
                else:
                    table_args.append(table_arg)
            record_class = type(
                name,
                (base_cls,),
                {
                    "__tablename__": table_name,
                    "__table_args__": tuple(table_args),
                },
            )
            cls.record_classes[table_name] = (record_class, base_cls)
        return cast(Type[TEventRecord], record_class)
