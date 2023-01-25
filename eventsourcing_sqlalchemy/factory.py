# -*- coding: utf-8 -*-
from eventsourcing.persistence import (
    AggregateRecorder,
    ApplicationRecorder,
    InfrastructureFactory,
    ProcessRecorder,
)
from eventsourcing.utils import Environment, resolve_topic, strtobool

from eventsourcing_sqlalchemy.datastore import SQLAlchemyDatastore
from eventsourcing_sqlalchemy.recorders import (
    SQLAlchemyAggregateRecorder,
    SQLAlchemyApplicationRecorder,
    SQLAlchemyProcessRecorder,
)


class Factory(InfrastructureFactory):
    SQLALCHEMY_URL = "SQLALCHEMY_URL"
    SQLALCHEMY_CONNECTION_CREATOR_TOPIC = "SQLALCHEMY_CONNECTION_CREATOR_TOPIC"
    CREATE_TABLE = "CREATE_TABLE"

    def __init__(self, env: Environment):
        super().__init__(env)
        db_url = self.env.get(self.SQLALCHEMY_URL)
        if db_url is None:
            raise EnvironmentError(
                "SQLAlchemy URL not found "
                "in environment with keys: "
                f"{', '.join(self.env.create_keys(self.SQLALCHEMY_URL))!r}"
            )
        creator_topic = self.env.get(self.SQLALCHEMY_CONNECTION_CREATOR_TOPIC)
        kwargs = {}
        if isinstance(creator_topic, str):
            kwargs["creator"] = resolve_topic(creator_topic)
        self.datastore = SQLAlchemyDatastore(url=db_url, **kwargs)

    def aggregate_recorder(self, purpose: str = "events") -> AggregateRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_" + purpose
        for_snapshots = purpose == "snapshots"
        recorder = SQLAlchemyAggregateRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            for_snapshots=for_snapshots,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def application_recorder(self) -> ApplicationRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        recorder = SQLAlchemyApplicationRecorder(
            datastore=self.datastore, events_table_name=events_table_name
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def process_recorder(self) -> ProcessRecorder:
        prefix = self.env.name.lower() or "stored"
        events_table_name = prefix + "_events"
        prefix = self.env.name.lower() or "notification"
        tracking_table_name = prefix + "_tracking"
        recorder = SQLAlchemyProcessRecorder(
            datastore=self.datastore,
            events_table_name=events_table_name,
            tracking_table_name=tracking_table_name,
        )
        if self.env_create_table():
            recorder.create_table()
        return recorder

    def env_create_table(self) -> bool:
        default = "yes"
        return bool(strtobool(self.env.get(self.CREATE_TABLE) or default))
