# -*- coding: utf-8 -*-
import sqlite3
from contextvars import ContextVar, Token
from threading import Lock, Semaphore
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


transactions: ContextVar["Transaction"] = ContextVar("transactions")


class Transaction:
    def __init__(self, session: Session, commit: bool, lock: Optional[Semaphore]):
        self.session = session
        self.commit = commit
        self.lock = lock
        self.nested_level = 0
        self.token: Optional[Token["Transaction"]] = None

    def __enter__(self) -> Session:
        if self.nested_level == 0:
            self.session.begin()
        self.nested_level += 1
        return self.session

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.nested_level -= 1
        if self.nested_level == 0:
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
            assert self.token is not None
            transactions.reset(self.token)


class SQLAlchemyDatastore:
    base_snapshot_record_cls = SnapshotRecord
    base_stored_event_record_cls = StoredEventRecord
    base_notification_tracking_record_cls = NotificationTrackingRecord
    record_classes: Dict[str, Tuple[Type[EventRecord], Type[EventRecord]]] = {}

    def __init__(
        self,
        *,
        session_maker: Optional[sessionmaker] = None,
        url: Optional[str] = None,
        autoflush: bool = True,
        **engine_kwargs: Any,
    ):
        self.access_lock: Optional[Semaphore] = None
        self.write_lock: Optional[Semaphore] = None
        self.is_sqlite_in_memory_db = False

        if session_maker is not None:
            self.session_maker = session_maker
            self.engine = self.session_maker().get_bind()
        elif url is not None:
            if url.startswith("sqlite"):
                if ":memory:" in url or "mode=memory" in url:
                    engine_kwargs = dict(engine_kwargs)
                    self.is_sqlite_in_memory_db = True
                    connect_args = engine_kwargs.get("connect_args") or {}
                    if "check_same_thread" not in connect_args:
                        connect_args["check_same_thread"] = False
                    engine_kwargs["connect_args"] = connect_args
                    if "poolclass" not in engine_kwargs:
                        engine_kwargs["poolclass"] = StaticPool
                    self.access_lock = Semaphore()
                else:
                    self.write_lock = Semaphore()

            self.engine = create_engine(url, echo=False, **engine_kwargs)
            self.session_maker = sessionmaker(bind=self.engine, autoflush=autoflush)
        else:
            raise EnvironmentError(
                "SQLAlchemyDatastore must be created with url or session_cls param"
            )

        self.is_sqlite_filedb = (
            self.engine.dialect.name == "sqlite" and not self.is_sqlite_in_memory_db
        )
        self._tried_init_sqlite_wal_mode = False
        self._wal_mode_lock = Lock()
        self.is_sqlite_wal_mode = False

    def init_sqlite_wal_mode(self) -> None:
        self._tried_init_sqlite_wal_mode = True
        if self.is_sqlite_filedb and not self.is_sqlite_wal_mode:
            with self._wal_mode_lock:
                with self.engine.connect() as connection:
                    cursor_result = connection.execute(text("PRAGMA journal_mode=WAL;"))
                    if list(cursor_result)[0][0] == "wal":
                        self.is_sqlite_wal_mode = True

    def transaction(self, commit: bool) -> Transaction:
        try:
            transaction = transactions.get()
            if commit is True and transaction.commit is False:
                raise ProgrammingError("Transaction already started with commit=False")
        except LookupError:
            if not self._tried_init_sqlite_wal_mode:
                # Do this after creating tables otherwise get disk I/0 error with SQLA v2.
                self.init_sqlite_wal_mode()
            lock: Optional[Semaphore] = None
            if self.access_lock:
                self.access_lock.acquire()
                lock = self.access_lock
            elif commit and self.write_lock:
                # print(get_ident(), "getting lock")
                self.write_lock.acquire()
                # print(get_ident(), "got lock")
                lock = self.write_lock
            session = self.session_maker()
            transaction = Transaction(session, commit=commit, lock=lock)
            transaction.token = transactions.set(transaction)
        return transaction

    @classmethod
    def define_record_class(
        cls, cls_name: str, table_name: str, base_cls: Type[TEventRecord]
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
                        *table_arg.expressions,  # noqa B026
                    )
                    table_args.append(new_index)
                else:
                    table_args.append(table_arg)
            record_class = type(
                cls_name,
                (base_cls,),
                {
                    "__tablename__": table_name,
                    "__table_args__": tuple(table_args),
                },
            )
            cls.record_classes[table_name] = (record_class, base_cls)
        return cast(Type[TEventRecord], record_class)
