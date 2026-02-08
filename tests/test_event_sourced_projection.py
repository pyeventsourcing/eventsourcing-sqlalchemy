# -*- coding: utf-8 -*-

from __future__ import annotations

import multiprocessing
import multiprocessing.synchronize
import os
import traceback
from threading import Thread
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from eventsourcing.application import (
    Application,
)
from eventsourcing.domain import Aggregate
from eventsourcing.persistence import OperationalError
from eventsourcing.projection import (
    EventSourcedProjectionRunner,
)
from eventsourcing.tests.projection import (
    Counters,
    EventSourcedProjectionTestCase,
)

from tests.utils import drop_pg_tables, pg_close_all_connections

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping


class TestEventSourcedProjectionWithSQLAlchemy(EventSourcedProjectionTestCase):
    env: ClassVar[dict[str, str]] = {
        "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
        "SQLALCHEMY_URL": (
            "postgresql://eventsourcing:eventsourcing@localhost:5432/eventsourcing_sqlalchemy"
        ),
    }

    def setUp(self) -> None:
        super().setUp()
        self.orig_postgres_dbname = os.environ.get("POSTGRES_DBNAME")
        os.environ["POSTGRES_DBNAME"] = "eventsourcing_sqlalchemy"
        self.drop_tables()

    def tearDown(self) -> None:
        if self.orig_postgres_dbname is not None:
            os.environ["POSTGRES_DBNAME"] = self.orig_postgres_dbname
        else:
            del os.environ["POSTGRES_DBNAME"]
        super().tearDown()
        self.drop_tables()

    def drop_tables(self) -> None:
        drop_pg_tables()

    def test_server_closes_connections_before_run_forever(self) -> None:
        with EventSourcedProjectionRunner(
            application_class=Application,
            projection_class=Counters,
            env=self.env,
        ) as runner:
            recordings = runner.app.save(Aggregate())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(1, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(0, runner.projection.get_count(Aggregate.Event))

            pg_close_all_connections()

            with self.assertRaises(OperationalError) as cm:
                runner.run_forever(timeout=1)

            self.assertIn("server closed the connection", str(cm.exception))

    def test_server_closes_connections_with_run_forever_in_thread(self) -> None:
        with EventSourcedProjectionRunner(
            application_class=Application,
            projection_class=Counters,
            env=self.env,
        ) as runner:
            recordings = runner.app.save(Aggregate())
            runner.wait(recordings[-1].notification.id)
            self.assertEqual(1, runner.projection.get_count(Aggregate.Created))
            self.assertEqual(0, runner.projection.get_count(Aggregate.Event))

            errors = []

            def thread_target() -> None:
                try:
                    runner.run_forever(timeout=5)
                except BaseException as e:  # noqa: B036
                    errors.append(e)

            run_forever_thread = Thread(target=thread_target)
            run_forever_thread.start()

            pg_close_all_connections()

            run_forever_thread.join(timeout=1)
            self.assertFalse(run_forever_thread.is_alive())
            self.assertEqual(1, len(errors))
            self.assertIsInstance(errors[0], OperationalError)
            self.assertIn("server closed the connection", str(errors[0]))

    def test_server_closes_connections_with_projection_in_thread(self) -> None:
        app = Application[UUID](env=self.env)
        projection = Counters(env=self.env)

        errors = []

        def thread_target() -> None:
            with EventSourcedProjectionRunner(
                application_class=Application,
                projection_class=Counters,
                env=self.env,
            ) as runner:
                try:
                    runner.run_forever(timeout=5)
                except BaseException as e:  # noqa: B036
                    errors.append(e)

        projection_thread = Thread(target=thread_target)
        projection_thread.start()

        recordings = app.save(Aggregate())
        projection.recorder.wait(app.name, recordings[-1].notification.id)
        self.assertEqual(1, projection.get_count(Aggregate.Created))
        self.assertEqual(0, projection.get_count(Aggregate.Event))

        pg_close_all_connections()

        projection_thread.join(timeout=1)
        self.assertFalse(projection_thread.is_alive())
        self.assertEqual(1, len(errors))
        self.assertIsInstance(errors[0], OperationalError)
        self.assertIn("server closed the connection", str(errors[0]))

    @staticmethod
    def run_projection(
        projection_started: multiprocessing.synchronize.Event,
        projection_errored: multiprocessing.synchronize.Event,
        projection_stopped: multiprocessing.synchronize.Event,
    ) -> None:
        try:
            with EventSourcedProjectionRunner(
                application_class=Application,
                projection_class=Counters,
                env=TestEventSourcedProjectionWithSQLAlchemy.env,
            ) as runner:
                projection_started.set()
                runner.run_forever(timeout=5)
        except BaseException:  # noqa: B036
            projection_errored.set()
            raise
        finally:
            projection_stopped.set()

    class MonitoredProcess(multiprocessing.Process):
        def __init__(
            self,
            group: None = None,
            target: Callable[..., object] | None = None,
            name: str | None = None,
            args: Iterable[Any] = (),
            kwargs: Mapping[str, Any] | None = None,
            *,
            daemon: bool | None = None,
        ) -> None:
            if kwargs is None:
                kwargs = {}
            super().__init__(group, target, name, args, kwargs, daemon=daemon)
            self._parent_conn, self._child_conn = multiprocessing.Pipe()
            self._child_error = None

        def run(self) -> None:
            try:
                super().run()
                self._child_conn.send((None, None))
            except BaseException as e:  # noqa: B036
                tb = traceback.format_exc()
                self._child_conn.send((e, tb))

        @property
        def error(self) -> tuple[BaseException, str] | None:
            if self._parent_conn.poll():
                self._child_error = self._parent_conn.recv()
            return self._child_error

    def test_server_closes_connections_with_projection_in_subprocess(self) -> None:
        projection_started = multiprocessing.Event()
        projection_errored = multiprocessing.Event()
        projection_stopped = multiprocessing.Event()

        with (
            Application[UUID](env=self.env) as app,
            Counters(env=self.env) as projection,
        ):

            projection_process = self.MonitoredProcess(
                target=self.run_projection,
                args=(projection_started, projection_errored, projection_stopped),
            )
            projection_process.start()

            recordings = app.save(Aggregate())
            projection.recorder.wait(app.name, recordings[-1].notification.id)
            self.assertEqual(1, projection.get_count(Aggregate.Created))
            self.assertEqual(0, projection.get_count(Aggregate.Event))

            self.assertTrue(projection_started.wait(timeout=1))

            pg_close_all_connections()

            projection_process.join(timeout=10)
            self.assertFalse(projection_process.is_alive())
            process_error = projection_process.error
            self.assertIsNotNone(process_error)
            assert process_error is not None  # for mypy
            exception, _ = process_error
            self.assertIsInstance(exception, OperationalError)
            self.assertIn("server closed the connection", str(exception))
            self.assertTrue(projection_errored.is_set())
            self.assertTrue(projection_stopped.is_set())


del EventSourcedProjectionTestCase
