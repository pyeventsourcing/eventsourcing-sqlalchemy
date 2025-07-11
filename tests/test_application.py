# -*- coding: utf-8 -*-
import os
from unittest import TestCase, skip
from uuid import UUID

from eventsourcing.application import AggregateNotFoundError, Application
from eventsourcing.domain import Aggregate
from eventsourcing.tests.application import ExampleApplicationTestCase
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import clear_topic_cache, get_topic
from fastapi_sqlalchemy import DBSessionMiddleware
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import scoped_session

from eventsourcing_sqlalchemy.factory import SQLAlchemyFactory
from tests.utils import drop_mssql_table

try:
    from sqlalchemy.orm import declarative_base  # type: ignore
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base

from eventsourcing_sqlalchemy.recorders import SQLAlchemyApplicationRecorder


class ScopedSessionAdapter(scoped_session):
    def __init__(self) -> None:
        pass


class TestApplicationWithSQLAlchemy(ExampleApplicationTestCase):
    expected_factory_topic = "eventsourcing_sqlalchemy.factory:SQLAlchemyFactory"
    sqlalchemy_database_url = "sqlite:///:memory:"

    def setUp(self) -> None:
        super().setUp()
        os.environ["PERSISTENCE_MODULE"] = "eventsourcing_sqlalchemy"
        os.environ["SQLALCHEMY_URL"] = self.sqlalchemy_database_url
        clear_topic_cache()

    def tearDown(self) -> None:
        del os.environ["PERSISTENCE_MODULE"]
        if "SQLALCHEMY_URL" in os.environ:
            del os.environ["SQLALCHEMY_URL"]
        super().tearDown()

    def test_transactions_managed_outside_application(self) -> None:
        app = Application[UUID]()

        assert isinstance(app.factory, SQLAlchemyFactory)  # For IDE/mypy.
        assert isinstance(app.recorder, SQLAlchemyApplicationRecorder)  # For IDE/mypy.

        # Create an aggregate - autoflush=True.
        with app.recorder.transaction(commit=True) as session:
            self.assertTrue(session.autoflush)
            aggregate = Aggregate()
            app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False with session.no_autoflush.
        with app.recorder.transaction(commit=True) as session:
            with session.no_autoflush:
                self.assertFalse(session.autoflush)
                aggregate = Aggregate()
                app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False with session.no_autoflush.
        with app.recorder.transaction(commit=True) as session:
            with session.no_autoflush:
                self.assertFalse(session.autoflush)
                aggregate = Aggregate()
                app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        # Create an aggregate - autoflush=False after configuring session maker.
        assert app.factory.datastore.session_maker is not None
        app.factory.datastore.session_maker.kw["autoflush"] = False
        with app.recorder.transaction(commit=True) as session:
            self.assertFalse(session.autoflush)
            aggregate = Aggregate()
            app.save(aggregate)

            # Get aggregate.
            self.assertIsInstance(app.repository.get(aggregate.id), Aggregate)

        app = Application(env={"SQLALCHEMY_AUTOFLUSH": "False"})

        # Create an aggregate - autoflush=False after configuring environment.
        assert isinstance(app.recorder, SQLAlchemyApplicationRecorder)
        with app.recorder.transaction(commit=True) as session:
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

        class MyScopedSession(ScopedSessionAdapter):
            def __getattribute__(self, item: str) -> None:
                return getattr(session, item)

        scoped_session_topic = get_topic(MyScopedSession)

        app = Application[UUID](
            env={"SQLALCHEMY_SCOPED_SESSION_TOPIC": scoped_session_topic}
        )

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
        with self.assertRaises(AggregateNotFoundError):
            # forgot to commit
            app.repository.get(aggregate.id)

        # After request.
        session.remove()

    def test_flask_sqlalchemy(self) -> None:  # (40% popularity for Python Web devs)
        # flask_sqlalchemy.SQLAlchemy.session  #  <- this is an SQLA scoped_session

        del os.environ["SQLALCHEMY_URL"]

        from flask import Flask
        from flask_sqlalchemy import SQLAlchemy

        flask_app = Flask(__name__)
        flask_app.config["SQLALCHEMY_DATABASE_URI"] = self.sqlalchemy_database_url

        Base = declarative_base()
        db = SQLAlchemy(flask_app, model_class=Base)

        class FlaskScopedSession(ScopedSessionAdapter):
            def __getattribute__(self, item: str) -> None:
                return getattr(db.session, item)

        # Set up database.
        with flask_app.app_context():
            es_app = Application[UUID](
                env={"SQLALCHEMY_SCOPED_SESSION_TOPIC": get_topic(FlaskScopedSession)}
            )

        # Handle requests.
        with flask_app.app_context():
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

    def test_fastapi_sqlalchemy(self) -> None:  # (20% popularity for Python Web devs)
        # fastapi_sqlalchemy.db.session  # <- this is not a scoped_session,
        # it's a property that returns a new session when accessed

        del os.environ["SQLALCHEMY_URL"]

        from fastapi import FastAPI
        from fastapi_sqlalchemy import db

        fastapi_app = FastAPI()

        fastapi_app.add_middleware(
            DBSessionMiddleware, db_url=self.sqlalchemy_database_url
        )

        fastapi_app.build_middleware_stack()

        class FastapiScopedSession(ScopedSessionAdapter):
            def __getattribute__(self, item: str) -> None:
                return getattr(db.session, item)

        # Set up database.
        with db(commit_on_exit=True):
            es_app = Application[UUID](
                env={"SQLALCHEMY_SCOPED_SESSION_TOPIC": get_topic(FastapiScopedSession)}
            )

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
            with self.assertRaises(AggregateNotFoundError):
                es_app.repository.get(aggregate.id)

    #
    # def test_tornado_sqlalchemy(self) -> None:  # 3% popularity
    #     tornado_sqlalchemy.SessionMixin.session  #  <- this just calls an SQLA sessionmaker
    #
    # def test_web2py_sqlalchemy(self) -> None:  # 3% popularity
    #
    # def test_bottle_sqlalchemy(self) -> None:  # 2% popularity
    #
    # def test_cherrypy_sqlalchemy(self) -> None:  # 2% popularity
    #     cherrypy.request.db  #  <- this is an SQLA scoped_session
    #
    # def test_falcon_sqlalchemy(self) -> None:  # 2% popularity
    #
    # def test_pyramid_sqlalchemy(self) -> None:  # 1% popularity
    #     pyramid_sqlalchemy.Session  #  <- this is an SQLA scoped_session


class TestWithPostgres(TestApplicationWithSQLAlchemy):
    sqlalchemy_database_url = (
        "postgresql://eventsourcing:eventsourcing@localhost:5432"
        "/eventsourcing_sqlalchemy"
    )

    def setUp(self) -> None:
        super().setUp()
        self.orig_postgres_dbname = os.environ.get("POSTGRES_DBNAME")
        os.environ["POSTGRES_DBNAME"] = "eventsourcing_sqlalchemy"
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        if self.orig_postgres_dbname is not None:
            os.environ["POSTGRES_DBNAME"] = self.orig_postgres_dbname
        else:
            del os.environ["POSTGRES_DBNAME"]
        super().tearDown()

    def drop_tables(self) -> None:
        drop_tables()

    def test_example_application(self) -> None:
        super().test_example_application()


class TestWithPostgresSchema(TestWithPostgres):
    def setUp(self) -> None:
        super().setUp()
        os.environ["SQLALCHEMY_SCHEMA"] = "myschema"

    def tearDown(self) -> None:
        super().tearDown()
        if "SQLALCHEMY_SCHEMA" in os.environ:
            del os.environ["SQLALCHEMY_SCHEMA"]

    def drop_tables(self) -> None:
        drop_tables()


@skip("SQL Server not supported yet")
class TestWithMSSQL(TestApplicationWithSQLAlchemy):
    """
    On MacOS: need to run `brew install unixodbc`
    brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release
    brew update
    HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18 mssql-tools18

    docker exec -it sql2022 "bash"
    /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Password1
    CREATE DATABASE eventsourcing_sqlalchemy;
    GO
    USE eventsourcing_sqlalchemy;
    GO
    SELECT * FROM bankaccounts_events;
    GO
    SELECT convert(varchar(max),state) FROM bankaccounts_events;
    GO

    docker exec -it sql2022 "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P Password1" -No

    -q "SELECT * FROM AdventureWorks2022.Person.Person"


    """

    sqlalchemy_database_url = URL.create(  # type: ignore[attr-defined]
        "mssql+pyodbc",
        username="sa",
        password="Password1",
        host="localhost",
        port=1433,
        database="eventsourcing_sqlalchemy",
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "TrustServerCertificate": "yes",
            # "authentication": "ActiveDirectoryIntegrated",
        },
    ).render_as_string(hide_password=False)

    def setUp(self) -> None:
        super().setUp()
        self.drop_tables()

    def tearDown(self) -> None:
        self.drop_tables()
        super().tearDown()

    def test_example_application(self) -> None:
        super().test_example_application()

    def drop_tables(self) -> None:
        drop_mssql_table("bankaccounts_events")


@skip("SQL Server not supported yet")
class TestWithMSSQLSchema(TestWithMSSQL):
    def setUp(self) -> None:
        super().setUp()
        os.environ["SQLALCHEMY_SCHEMA"] = "myschema"

    def tearDown(self) -> None:
        super().tearDown()
        if "SQLALCHEMY_SCHEMA" in os.environ:
            del os.environ["SQLALCHEMY_SCHEMA"]

    def test_example_application(self) -> None:
        super().test_example_application()

    def drop_tables(self) -> None:
        drop_mssql_table("myschema.bankaccounts_events")


class TestWithConnectionCreatorTopic(TestCase):
    def test(self) -> None:
        class MyCreatorException(Exception):
            pass

        def creator() -> None:
            raise MyCreatorException()

        creator_topic = get_topic(creator)

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
