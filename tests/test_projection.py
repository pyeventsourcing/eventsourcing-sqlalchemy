# -*- coding: utf-8 -*-
# type: ignore
from __future__ import annotations

from typing import Any
from unittest import skipIf

import sqlalchemy
from eventsourcing.persistence import (
    Tracking,
)
from eventsourcing.tests.projection import (
    AggregateEventCountersProjectionTestCase,
    EventCountersInterface,
    EventCountersViewTestCase,
)
from eventsourcing.utils import Environment
from sqlalchemy import BigInteger, Column, Integer, String

from tests.utils import drop_pg_tables

try:
    from sqlalchemy.orm import declarative_base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import Mapped

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore
from eventsourcing_sqlalchemy.factory import SQLAlchemyFactory
from eventsourcing_sqlalchemy.recorders import SQLAlchemyTrackingRecorder


class Base:
    __allow_unmapped__ = True


Base = declarative_base(cls=Base)


class Counters(Base):
    __tablename__ = "counters_projection"
    counter_name: Mapped[str] = Column(String, primary_key=True)
    counter: Mapped[int] = Column(
        BigInteger().with_variant(Integer(), "sqlite"),
        autoincrement=True,
    )


class SQLAlchemyEventCounters(SQLAlchemyTrackingRecorder, EventCountersInterface):
    _created_event_counter_name = "CREATED_EVENTS"
    _subsequent_event_counter_name = "SUBSEQUENT_EVENTS"

    def __init__(
        self,
        datastore: SQLAlchemyDatastore,
        **kwargs: Any,
    ):
        super().__init__(datastore, **kwargs)
        assert self.tracking_table_name.endswith("_tracking")  # Because we replace it.
        self.counters_table_name = self.tracking_table_name.replace("_tracking", "")
        self.check_identifier_length(self.counters_table_name)
        assert self.datastore.engine is not None
        Base.metadata.create_all(bind=self.datastore.engine, checkfirst=True)

    def get_created_event_counter(self) -> int:
        return self._select_counter(self._created_event_counter_name)

    def get_subsequent_event_counter(self) -> int:
        return self._select_counter(self._subsequent_event_counter_name)

    def incr_created_event_counter(self, tracking: Tracking) -> None:
        self._incr_counter(self._created_event_counter_name, tracking)

    def incr_subsequent_event_counter(self, tracking: Tracking) -> None:
        self._incr_counter(self._subsequent_event_counter_name, tracking)

    def _select_counter(self, name: str) -> int:
        with self.transaction() as session:
            counter = session.query(Counters).filter_by(counter_name=name).first()
            return counter.counter if counter else 0

    def _incr_counter(self, name: str, tracking: Tracking) -> None:
        with self.transaction() as session:
            self._insert_tracking(session, tracking)
            counter = session.query(Counters).filter_by(counter_name=name).first()
            if counter:
                counter.counter += 1
            else:
                session.add(Counters(counter_name=name, counter=1))


@skipIf(sqlalchemy.__version__[0] == "1", "No psycopg/psycopg3 in SQLAlchemy v1.x")
class TestSQLAlchemyEventCountersViewWithPsycopg(EventCountersViewTestCase):
    def setUp(self) -> None:
        drop_pg_tables()
        super().setUp()
        self.factory = SQLAlchemyFactory(
            Environment(
                name="eventcounters",
                env={
                    "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
                    "SQLALCHEMY_URL": (
                        "postgresql+psycopg://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
                    ),
                },
            )
        )

    def tearDown(self) -> None:
        self.factory.close()
        drop_pg_tables()
        super().tearDown()

    def construct_event_counters_view(self) -> EventCountersInterface:
        return self.factory.tracking_recorder(SQLAlchemyEventCounters)


class TestSQLAlchemyEventCountersViewWithPsycopg2(EventCountersViewTestCase):

    def setUp(self) -> None:
        drop_pg_tables()
        super().setUp()
        self.factory = SQLAlchemyFactory(
            Environment(
                name="eventcounters",
                env={
                    "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
                    "SQLALCHEMY_URL": (
                        "postgresql+psycopg2://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
                    ),
                },
            )
        )

    def tearDown(self) -> None:
        self.factory.close()
        drop_pg_tables()
        super().tearDown()

    def construct_event_counters_view(self) -> EventCountersInterface:
        return self.factory.tracking_recorder(SQLAlchemyEventCounters)


@skipIf(sqlalchemy.__version__[0] == "1", "No psycopg/psycopg3 in SQLAlchemy v1.x")
class TestAggregateEventCountersProjectionWithPsycopg(
    AggregateEventCountersProjectionTestCase
):
    view_class: type[EventCountersInterface] = SQLAlchemyEventCounters
    env: dict[str, str] = {
        "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
        "SQLALCHEMY_URL": (
            "postgresql+psycopg://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
        ),
    }

    def setUp(self) -> None:
        drop_pg_tables()
        super().setUp()

    def tearDown(self) -> None:
        drop_pg_tables()
        super().tearDown()


class TestAggregateEventCountersProjectionWithPsycopg2(
    AggregateEventCountersProjectionTestCase
):
    view_class: type[EventCountersInterface] = SQLAlchemyEventCounters
    env: dict[str, str] = {
        "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
        "SQLALCHEMY_URL": (
            "postgresql+psycopg2://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
        ),
    }

    def setUp(self) -> None:
        drop_pg_tables()
        super().setUp()

    def tearDown(self) -> None:
        drop_pg_tables()
        super().tearDown()


del AggregateEventCountersProjectionTestCase
del EventCountersViewTestCase
