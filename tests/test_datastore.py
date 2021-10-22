# -*- coding: utf-8 -*-
from unittest import TestCase

from sqlalchemy.future import create_engine
from sqlalchemy.orm import sessionmaker

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore


class TestDatastore(TestCase):
    def test_should_be_created_with_url(self) -> None:
        datastore = SQLAlchemyDatastore(url="sqlite:///:memory:")
        self.assertIsInstance(datastore, SQLAlchemyDatastore)

    def test_should_be_created_with_session_cls(self) -> None:
        session_cls = sessionmaker(bind=create_engine(url="sqlite:///:memory:"))
        datastore = SQLAlchemyDatastore(session_cls=session_cls)
        self.assertIsInstance(datastore, SQLAlchemyDatastore)

    def test_should_raise_exception_without_url_or_session_cls(self) -> None:
        with self.assertRaises(EnvironmentError):
            SQLAlchemyDatastore()
