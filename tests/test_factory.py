import os

from eventsourcing.persistence import InfrastructureFactory
from eventsourcing.tests.infrastructure_testcases import (
    InfrastructureFactoryTestCase,
)
from eventsourcing.utils import get_topic

from eventsourcing_sqlalchemy.factory import Factory
from eventsourcing_sqlalchemy.recorders import (
    SqlAlchemyAggregateRecorder,
    SqlAlchemyApplicationRecorder,
    SqlAlchemyProcessRecorder,
)


class TestFactory(InfrastructureFactoryTestCase):
    def test_create_aggregate_recorder(self):
        super().test_create_aggregate_recorder()

    def expected_factory_class(self):
        return Factory

    def expected_aggregate_recorder_class(self):
        return SqlAlchemyAggregateRecorder

    def expected_application_recorder_class(self):
        return SqlAlchemyApplicationRecorder

    def expected_process_recorder_class(self):
        return SqlAlchemyProcessRecorder

    def setUp(self) -> None:
        os.environ[InfrastructureFactory.TOPIC] = get_topic(Factory)
        os.environ[Factory.SQLALCHEMY_URL] = "sqlite:///:memory:"
        super().setUp()

    def tearDown(self) -> None:
        if Factory.SQLALCHEMY_URL in os.environ:
            del os.environ[Factory.SQLALCHEMY_URL]
        super().tearDown()


del InfrastructureFactoryTestCase
