# -*- coding: utf-8 -*-
import os
from unittest import TestCase

from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.domain import Aggregate
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.application import TIMEIT_FACTOR, ExampleApplicationTestCase
from eventsourcing.tests.postgres_utils import drop_postgres_table
from eventsourcing.utils import get_topic

# from fastapi_sqlalchemy import db
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import scoped_session

from eventsourcing_sqlalchemy.factory import Factory
from eventsourcing_sqlalchemy.recorders import SQLAlchemyApplicationRecorder


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):
    timeit_number = 30 * TIMEIT_FACTOR
    expected_factory_topic = "eventsourcing_sqlalchemy.factory:Factory"
    sqlalchemy_database_url = "sqlite:///:memory:"

    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing_sqlalchemy"
        os.environ["SQLALCHEMY_URL"] = self.sqlalchemy_database_url

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        if "SQLALCHEMY_URL" in os.environ:
            del os.environ["SQLALCHEMY_URL"]
        super().tearDown()

    def test_transactions_managed_outside_application(self) -> None:
        app = Application()

        assert isinstance(app.recorder, SQLAlchemyApplicationRecorder)  # For IDE/mypy.

        # Create an aggregate - autoflush=True.
        with app.recorder.datastore.transaction(commit=True) as session:
            self.assertTrue(session.autoflush)
            aggregate = Aggregate()
            app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False with session.no_autoflush.
        with app.recorder.datastore.transaction(commit=True) as session:
            with session.no_autoflush:
                self.assertFalse(session.autoflush)
                aggregate = Aggregate()
                app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False with session.no_autoflush.
        with app.recorder.datastore.transaction(commit=True) as session:
            with session.no_autoflush:
                self.assertFalse(session.autoflush)
                aggregate = Aggregate()
                app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False after configuring session maker.
        assert app.recorder.datastore.session_maker is not None
        app.recorder.datastore.session_maker.kw["autoflush"] = False
        with app.recorder.datastore.transaction(commit=True) as session:
            self.assertFalse(session.autoflush)
            aggregate = Aggregate()
            app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        app = Application(env={"SQLALCHEMY_AUTOFLUSH": "False"})

        # Create an aggregate - autoflush=False after configuring environment.
        assert isinstance(app.recorder, SQLAlchemyApplicationRecorder)
        with app.recorder.datastore.transaction(commit=True) as session:
            self.assertFalse(session.autoflush)
            aggregate = Aggregate()
            app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

    def test_set_scoped_session(self) -> None:
        del os.environ["SQLALCHEMY_URL"]

        # Define application to use scoped sessions (e.g. like a Web application).
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        engine = create_engine(self.sqlalchemy_database_url)
        session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=engine)
        )

        app = Application()
        assert isinstance(app.factory, Factory)  # For IDE/mypy.
        app.factory.datastore.set_scoped_session(session)

        # Set up database.
        assert isinstance(app.recorder, SQLAlchemyApplicationRecorder)  # For IDE/mypy.
        app.recorder.create_table()

        # Handle request.
        aggregate = Aggregate()
        app.save(aggregate)
        app.repository.get(aggregate.id)
        session.commit()

        # After request.
        session.remove()

        # Handle request.
        app.repository.get(aggregate.id)

        # After request.
        session.remove()

        # Handle request.
        aggregate = Aggregate()
        app.save(aggregate)
        # forget to commit

        # After request.
        session.remove()

        # Handle request.
        with self.assertRaises(AggregateNotFound):
            # forgot to commit
            app.repository.get(aggregate.id)

        # After request.
        session.remove()

    # def test_fastapi_sqlalchemy(self) -> None:
    #     db
    #
    # def test_flask_sqlalchemy(self) -> None:
    #     SQLAlchemy

    #     # Get aggregate.
    #     self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)
    #
    # # Create an aggregate - autoflush=False with session.no_autoflush.
    # with app.recorder.datastore.transaction(commit=True) as session:
    #     with session.no_autoflush:
    #         self.assertFalse(session.autoflush)
    #         aggregate = Aggregate()
    #         app.save(aggregate)
    #
    #     # Get aggregate.
    #     self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)
    #
    # # Create an aggregate - autoflush=False with session.no_autoflush.
    # with app.recorder.datastore.transaction(commit=True) as session:
    #     with session.no_autoflush:
    #         self.assertFalse(session.autoflush)
    #         aggregate = Aggregate()
    #         app.save(aggregate)
    #
    #     # Get aggregate.
    #     self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)
    #
    # # Create an aggregate - autoflush=False after configuring session maker.
    # app.recorder.datastore.session_maker.kw["autoflush"] = False
    # with app.recorder.datastore.transaction(commit=True) as session:
    #     self.assertFalse(session.autoflush)
    #     aggregate = Aggregate()
    #     app.save(aggregate)
    #
    #     # Get aggregate.
    #     self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)


class TestWithPostgres(TestApplicationWithSQLAlchemy):
    timeit_number = 5 * TIMEIT_FACTOR
    sqlalchemy_database_url = (
        "postgresql://eventsourcing:eventsourcing@localhost:5432"
        "/eventsourcing_sqlalchemy"
    )

    def setUp(self) -> None:
        super().setUp()
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def drop_tables(self) -> None:
        datastore = PostgresDatastore(
            dbname="eventsourcing_sqlalchemy",
            host="127.0.0.1",
            port="5432",
            user="eventsourcing",
            password="eventsourcing",
        )
        drop_postgres_table(datastore, "bankaccounts_events")
        drop_postgres_table(datastore, "bankaccounts_events")


class TestWithConnectionCreatorTopic(TestCase):
    def test(self) -> None:
        class MyCreatorException(Exception):
            pass

        def creator() -> None:
            raise MyCreatorException()

        creator_topic = get_topic(creator)  # type: ignore[arg-type]

        env = {
            "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
            "SQLALCHEMY_URL": (
                "postgresql://eventsourcing:eventsourcing@localhost:5432"
                "/eventsourcing_sqlalchemy"
            ),
            "SQLALCHEMY_CONNECTION_CREATOR_TOPIC": creator_topic,
        }
        with self.assertRaises(MyCreatorException):
            Application(env=env)


del ExampleApplicationTestCase
