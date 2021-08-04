import os

from eventsourcing.tests.test_application_with_popo import (
    TIMEIT_FACTOR,
    TestApplicationWithPOPO,
)


class TestApplicationWithSqlAlchemy(TestApplicationWithPOPO):
    timeit_number = 5 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing_sqlalchemy.factory:Factory"

    def setUp(self) -> None:
        super().setUp()
        os.environ["INFRASTRUCTURE_FACTORY"] = "eventsourcing_sqlalchemy.factory:Factory"
        os.environ["SQLALCHEMY_URL"] = "sqlite:///:memory:"

    def tearDown(self) -> None:
        del os.environ["INFRASTRUCTURE_FACTORY"]
        del os.environ["SQLALCHEMY_URL"]
        super().tearDown()


del TestApplicationWithPOPO
