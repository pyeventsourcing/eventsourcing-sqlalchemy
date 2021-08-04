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
from eventsourcing.domain import Aggregate, event


class World(Aggregate):
    def __init__(self):
        self.history = []

    @event("SomethingHappened")
    def make_it_so(self, what):
        self.history.append(what)


from eventsourcing.application import Application

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

Set environment variables.

```python
import os

os.environ.update({
    "INFRASTRUCTURE_FACTORY": "eventsourcingsqlalchemy.factory:Factory",
    "SQLALCHEMY_URL": "sqlite:///:memory:",
})
```

Construct and use the application.

```python
app = Worlds()
world_id = app.create_world()
app.make_it_so(world_id, "dinosaurs")
app.make_it_so(world_id, "trucks")
app.make_it_so(world_id, "internet")

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

# Construct and use the application.
app = Worlds()
world_id = app.create_world()
app.make_it_so(world_id, "dinosaurs")
app.make_it_so(world_id, "trucks")
app.make_it_so(world_id, "internet")

history = app.get_world_history(world_id)
assert history == ["dinosaurs", "trucks", "internet"]
```

We can see the application is using the SQLAlchemy infrastructure,
and that compression and encryption are enabled, by checking the
attributes of the application object.

```python
from eventsourcingsqlalchemy.datastore import SqlAlchemyDatastore
from eventsourcingsqlalchemy.factory import Factory
from eventsourcingsqlalchemy.recorders import SqlAlchemyAggregateRecorder
from eventsourcingsqlalchemy.recorders import SqlAlchemyApplicationRecorder
from eventsourcingsqlalchemy.models import StoredEventRecord
from eventsourcingsqlalchemy.models import SnapshotRecord
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
