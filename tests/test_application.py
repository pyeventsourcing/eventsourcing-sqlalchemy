# -*- coding: utf-8 -*-
import os
from typing import Any
from unittest import TestCase

import fastapi_sqlalchemy
from eventsourcing.application import AggregateNotFound, Application
from eventsourcing.domain import Aggregate
from eventsourcing.postgres import PostgresDatastore
from eventsourcing.tests.application import TIMEIT_FACTOR, ExampleApplicationTestCase
from eventsourcing.tests.postgres_utils import drop_postgres_table
from eventsourcing.utils import get_topic
from fastapi_sqlalchemy import DBSessionMiddleware
from sqlalchemy.orm import scoped_session

try:
    from sqlalchemy.orm import declarative_base  # type: ignore
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

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

    def test_flask_sqlalchemy(self) -> None:  # 40%
        # flask_sqlalchemy.SQLAlchemy.session  #  <- this is an SQLA scoped_session

        del os.environ["SQLALCHEMY_URL"]

        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy

        flask_app = Flask(__name__)
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = self.sqlalchemy_database_url

        Base = declarative_base()
        db = SQLAlchemy(flask_app, model_class=Base)

        es_app = Application()
        assert isinstance(
            es_app.recorder, SQLAlchemyApplicationRecorder
        )  # For IDE/mypy.
        assert isinstance(es_app.factory, Factory)  # For IDE/mypy.

        # Set up database.
        with flask_app.app_context():
            es_app.factory.datastore.set_scoped_session(db.session)
            es_app.recorder.create_table()

            # Handle request.
            aggregate = Aggregate()
            es_app.save(aggregate)
            es_app.repository.get(aggregate.id)
            db.session.commit()

            # After request.
            db.session.remove()

            # Handle request.
            es_app.repository.get(aggregate.id)

            # After request.
            db.session.remove()

    #
    def test_fastapi_sqlalchemy(self) -> None:  # 20%
        # fastapi_sqlalchemy.db.session  # <- this is not a scoped_session,
        # it's a property that returns a new session when accessed

        del os.environ["SQLALCHEMY_URL"]

        from fastapi import FastAPI
        from fastapi_sqlalchemy import db

        fastapi_app = FastAPI()

        fastapi_app.add_middleware(DBSessionMiddleware, db_url="sqlite://")

        class FakeScopedSession(scoped_session):
            def __init__(self, db: Any) -> None:
                self._db = db

            def __getattribute__(self, item: str) -> None:
                if item == "_db":
                    return super().__getattribute__(item)
                else:
                    return getattr(self._db.session, item)

        Session = FakeScopedSession(fastapi_sqlalchemy.db)

        es_app = Application()
        assert isinstance(
            es_app.recorder, SQLAlchemyApplicationRecorder
        )  # For IDE/mypy.
        assert isinstance(es_app.factory, Factory)  # For IDE/mypy.

        fastapi_app.build_middleware_stack()

        @fastapi_app.get(path="/index")
        def index() -> str:
            # aggregate = Aggregate()
            # es_app.save(aggregate)
            # es_app.repository.get(aggregate.id)
            return ""

        # Set up database.
        with db(commit_on_exit=True):
            es_app.factory.datastore.set_scoped_session(Session)
            es_app.recorder.create_table()

        with db(commit_on_exit=True):
            # Handle request.
            aggregate = Aggregate()
            es_app.save(aggregate)
            es_app.repository.get(aggregate.id)

        with db():
            es_app.repository.get(aggregate.id)

        with db(commit_on_exit=False):
            # Handle request.
            aggregate = Aggregate()
            es_app.save(aggregate)
            es_app.repository.get(aggregate.id)

        with db():
            with self.assertRaises(AggregateNotFound):
                es_app.repository.get(aggregate.id)

    #
    # def test_tornado_sqlalchemy(self) -> None:  # 3%
    #     tornado_sqlalchemy.SessionMixin.session  #  <- this just calls an SQLA sessionmaker
    #
    # def test_web2py_sqlalchemy(self) -> None:  # 3%
    #
    # def test_bottle_sqlalchemy(self) -> None:  # 2%
    #
    # def test_cherrypy_sqlalchemy(self) -> None:  # 2%
    #     cherrypy.request.db  #  <- this is an SQLA scoped_session
    #
    # def test_falcon_sqlalchemy(self) -> None:  # 2%
    #
    # def test_pyramid_sqlalchemy(self) -> None:  # 1%
    #     pyramid_sqlalchemy.Session  #  <- this is an SQLA scoped_session


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
