# eventsourcing-sqlalchemy

Python package for eventsourcing with SQLAlchemy


## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing_sqlalchemy/)
from the Python Package Index. Please note, it is recommended to
install Python packages into a Python virtual environment.

    $ pip install eventsourcing_sqlalchemy


## Synopsis

To use SQLAlchemy with your Python eventsourcing application, use the topic `eventsourcing_sqlalchemy.factory:Factory` as the `INFRASTRUCTURE_FACTORY`
environment variable, and set an SQLAlchemy database URL as the value of
environment variable `SQLALCHEMY_URL`.

First define a domain model and application, in the usual way.

```python
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event


class World(Aggregate):
    def __init__(self):
        self.history = []

    @event("SomethingHappened")
    def make_it_so(self, what):
        self.history.append(what)


class Worlds(Application):
    is_snapshotting_enabled = True

    def create_world(self):
        world = World()
        self.save(world)
        return world.id

    def make_it_so(self, world_id, what):
        world = self.repository.get(world_id)
        world.make_it_so(what)
        self.save(world)

    def get_world_history(self, world_id):
        world = self.repository.get(world_id)
        return world.history
```

Set environment variables `INFRASTRUCTURE_FACTORY` and `SQLALCHEMY_URL`.
See the [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/14/core/engines.html) for more information about SQLAlchemy Database URLs.

```python
import os

os.environ.update({
    "INFRASTRUCTURE_FACTORY": "eventsourcing_sqlalchemy.factory:Factory",
    "SQLALCHEMY_URL": "sqlite:///:memory:",
})
```

Construct and use the application.

```python
# Construct the application.
app = Worlds()

# Call application command methods.
world_id = app.create_world()
app.make_it_so(world_id, "dinosaurs")
app.make_it_so(world_id, "trucks")
app.make_it_so(world_id, "internet")

# Call application query methods.
history = app.get_world_history(world_id)
assert history == ["dinosaurs", "trucks", "internet"]    
```

These settings can be used with others supported by the library,
for example to enable application-level compression and encryption
of stored events, set `COMPRESSOR_TOPIC` and `CIPHER_KEY`.

```python
from eventsourcing.cipher import AESCipher


# Generate a cipher key (keep this safe).
cipher_key = AESCipher.create_key(num_bytes=32)

# Set environment variables.
os.environ.update({
    "COMPRESSOR_TOPIC": "zlib",
    "CIPHER_KEY": cipher_key,
})

# Construct the application.
app = Worlds()
```

We can see the application is using the SQLAlchemy infrastructure,
and that compression and encryption are enabled, by checking the
attributes of the application object.

```python
from eventsourcing_sqlalchemy.datastore import SqlAlchemyDatastore
from eventsourcing_sqlalchemy.factory import Factory
from eventsourcing_sqlalchemy.recorders import SqlAlchemyAggregateRecorder
from eventsourcing_sqlalchemy.recorders import SqlAlchemyApplicationRecorder
from eventsourcing_sqlalchemy.models import StoredEventRecord
from eventsourcing_sqlalchemy.models import SnapshotRecord
import zlib

assert isinstance(app.factory, Factory)
assert isinstance(app.factory.datastore, SqlAlchemyDatastore)
assert isinstance(app.events.recorder, SqlAlchemyApplicationRecorder)
assert isinstance(app.snapshots.recorder, SqlAlchemyAggregateRecorder)
assert issubclass(app.events.recorder.events_record_cls, StoredEventRecord)
assert issubclass(app.snapshots.recorder.events_record_cls, SnapshotRecord)
assert isinstance(app.mapper.cipher, AESCipher)
assert app.mapper.compressor == zlib
```
