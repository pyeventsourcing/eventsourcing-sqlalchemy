# -*- coding: utf-8 -*-
import os
from typing import Type

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
    TrackingRecorder,
)
from eventsourcing.tests.persistence import InfrastructureFactoryTestCase
from eventsourcing.utils import Environment

from eventsourcing_sqlalchemy.factory import SQLAlchemyFactory
from eventsourcing_sqlalchemy.recorders import (
    SQLAlchemyAggregateRecorder,
    SQLAlchemyApplicationRecorder,
    SQLAlchemyProcessRecorder,
    SQLAlchemyTrackingRecorder,
)


class TestSQLAlchemyFactory(InfrastructureFactoryTestCase[SQLAlchemyFactory]):
    def test_create_aggregate_recorder(self) -> None:
        super().test_create_aggregate_recorder()

    def expected_factory_class(self) -> Type[SQLAlchemyFactory]:
        return SQLAlchemyFactory

    def expected_aggregate_recorder_class(self) -> Type[AggregateRecorder]:
        return SQLAlchemyAggregateRecorder

    def expected_application_recorder_class(self) -> Type[ApplicationRecorder]:
        return SQLAlchemyApplicationRecorder

    def expected_process_recorder_class(self) -> Type[ProcessRecorder]:
        return SQLAlchemyProcessRecorder

    def expected_tracking_recorder_class(self) -> type[TrackingRecorder]:
        return SQLAlchemyTrackingRecorder

    class SQLAchemyTrackingRecorderSubclass(SQLAlchemyTrackingRecorder):
        pass

    def tracking_recorder_subclass(self) -> type[TrackingRecorder]:
        return self.SQLAchemyTrackingRecorderSubclass

    def setUp(self) -> None:
        self.env = Environment("TestCase")
        self.env[InfrastructureFactory.PERSISTENCE_MODULE] = (
            SQLAlchemyFactory.__module__
        )
        self.env[SQLAlchemyFactory.SQLALCHEMY_URL] = "sqlite:///:memory:"
        super().setUp()

    def tearDown(self) -> None:
        if SQLAlchemyFactory.SQLALCHEMY_URL in os.environ:
            del os.environ[SQLAlchemyFactory.SQLALCHEMY_URL]
        super().tearDown()


del InfrastructureFactoryTestCase
