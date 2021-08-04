import sqlite3
from threading import Lock
from typing import Optional

import sqlalchemy.exc
from eventsourcing.persistence import (
    DataError,
    DatabaseError,
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


class SqlAlchemyDatastore:
    record_classes = {}

    def __init__(self, url: str, **kwargs):
        kwargs = dict(kwargs)
        self.is_sqlite_in_memory_db = False
        self.access_lock: Optional[Lock] = None
        if url.startswith("sqlite"):
            if ":memory:" in url or "mode=memory" in url:
                self.is_sqlite_in_memory_db = True
                connect_args = kwargs.get("connect_args") or {}
                if "check_same_thread" not in connect_args:
                    connect_args["check_same_thread"] = False
                kwargs["connect_args"] = connect_args
                if "pool_class" not in kwargs:
                    kwargs["poolclass"] = StaticPool
                self.access_lock = Lock()

        self.engine = create_engine(url, echo=False, **kwargs)
        self.is_sqlite_wal_mode = False
        if self.engine.dialect.name == "sqlite":
            if not self.is_sqlite_in_memory_db:
                with self.engine.connect() as connection:
                    cursor_result = connection.execute(text("PRAGMA journal_mode=WAL;"))
                    if list(cursor_result)[0][0] == "wal":
                        self.is_sqlite_wal_mode = True
                # if ":memory:" in url or "mode=memory" in url:
                # self.engine = create_engine(
                #     "sqlite:///:memory:?cache=shared",
                #     connect_args={
                #         'check_same_thread': False,
                #     },
                #     poolclass=StaticPool
                # )
                # # self.write_lock = Lock()
            # else:
            #     with self.engine.connect() as connection:
            #         cursor_result = connection.execute(text("PRAGMA journal_mode=WAL;"))
            #         if list(cursor_result)[0][0] == "wal":
            #             self.is_sqlite_wal_mode = True

        self.session_cls = sessionmaker(bind=self.engine)

    def transaction(self, commit: bool):
        if self.access_lock:
            self.access_lock.acquire()
        return Transaction(self.session_cls(), commit=commit, lock=self.access_lock)

    @classmethod
    def define_record_class(cls, name, table_name, base_cls):
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
        return record_class


class Transaction:
    def __init__(self, session: Session, commit: bool, lock: Optional[Lock]):
        self.session = session
        self.commit = commit
        self.lock = lock

    def __enter__(self) -> Session:
        self.session.begin()
        return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_val:
                self.session.rollback()
                raise exc_val
            elif not self.commit:
                try:
                    self.session.rollback()
                except sqlite3.OperationalError:
                    if self.lock:
                        pass
            else:
                self.session.commit()
        except sqlalchemy.exc.InterfaceError as e:
            raise InterfaceError(e)
        except sqlalchemy.exc.DataError as e:
            raise DataError(e)
        except sqlalchemy.exc.OperationalError as e:
            if isinstance(e.args[0], sqlite3.OperationalError) and self.lock:
                pass
            else:
                raise OperationalError(e)
        except sqlalchemy.exc.IntegrityError as e:
            raise IntegrityError(e)
        except sqlalchemy.exc.InternalError as e:
            raise InternalError(e)
        except sqlalchemy.exc.ProgrammingError as e:
            raise ProgrammingError(e)
        except sqlalchemy.exc.NotSupportedError as e:
            raise NotSupportedError(e)
        except sqlalchemy.exc.DatabaseError as e:
            raise DatabaseError(e)
        except sqlalchemy.exc.SQLAlchemyError as e:
            raise PersistenceError(e)
        finally:
            self.session.close()
            self.session = None
            if self.lock is not None:
                self.lock.release()
