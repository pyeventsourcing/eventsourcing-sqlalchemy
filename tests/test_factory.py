# -*- coding: utf-8 -*-
import os
from typing import Type

from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
)
from eventsourcing.tests.infrastructure_testcases import InfrastructureFactoryTestCase
from eventsourcing.utils import get_topic

from eventsourcing_sqlalchemy.factory import Factory
from eventsourcing_sqlalchemy.recorders import (
    SQLAlchemyAggregateRecorder,
    SQLAlchemyApplicationRecorder,
    SQLAlchemyProcessRecorder,
)


class TestFactory(InfrastructureFactoryTestCase):
    def test_create_aggregate_recorder(self) -> None:
        super().test_create_aggregate_recorder()

    def expected_factory_class(self) -> Type[InfrastructureFactory]:
        return Factory

    def expected_aggregate_recorder_class(self) -> Type[AggregateRecorder]:
        return SQLAlchemyAggregateRecorder

    def expected_application_recorder_class(self) -> Type[ApplicationRecorder]:
        return SQLAlchemyApplicationRecorder

    def expected_process_recorder_class(self) -> Type[ProcessRecorder]:
        return SQLAlchemyProcessRecorder

    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.SQLALCHEMY_URL] = "sqlite:///:memory:"
        super().setUp()

    def tearDown(self) -> None:
        if Factory.SQLALCHEMY_URL in os.environ:
            del os.environ[Factory.SQLALCHEMY_URL]
        super().tearDown()


del InfrastructureFactoryTestCase
