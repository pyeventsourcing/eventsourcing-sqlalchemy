# Event Sourcing in Python with SQLAlchemy

This package supports using the Python [eventsourcing](https://github.com/pyeventsourcing/eventsourcing) library with [SQLAlchemy](https://www.sqlalchemy.org/).

To use SQLAlchemy with your Python eventsourcing applications, install
`eventsourcing_sqlalchemy` and use `eventsourcing_sqlalchemy` as the value
of the `PERSISTENCE_MODULE` environment variable, and set an SQLAlchemy
database URL as the value of the environment variable `SQLALCHEMY_URL`.

## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing_sqlalchemy/)
from the Python Package Index. Please note, it is recommended to
install Python packages into a Python virtual environment.

    $ pip install eventsourcing_sqlalchemy

## Synopsis

Define aggregates and applications in the usual way.

```python
from eventsourcing.domain import Aggregate, event

class Dog(Aggregate):
    @event('Registered')
    def __init__(self, name):
        self.name = name
        self.tricks = []

    @event('TrickAdded')
    def add_trick(self, what):
        self.tricks.append(what)
```

Use the library's `Application` class to define an event-sourced application.
Add command and query methods that use event-sourced aggregates.

```python
from eventsourcing.application import Application

class TrainingSchool(Application):
    def register(self, name):
        dog = Dog(name)
        self.save(dog)
        return dog.id

    def add_trick(self, dog_id, trick):
        dog = self.repository.get(dog_id)
        dog.add_trick(trick)
        self.save(dog)

    def get_tricks(self, dog_id):
        dog = self.repository.get(dog_id)
        return dog.tricks
```

Set environment variables `PERSISTENCE_MODULE` and `SQLALCHEMY_URL`.
See the [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/14/core/engines.html)
for more information about SQLAlchemy Database URLs.

```python
import os

os.environ.update({
    "PERSISTENCE_MODULE": "eventsourcing_sqlalchemy",
    "SQLALCHEMY_URL": "sqlite:///:memory:",
})
```

Construct and use the application.

```python
school = TrainingSchool()
```

Evolve the state of the application by calling the
application command methods.

```python
dog_id = school.register('Fido')
school.add_trick(dog_id, 'roll over')
school.add_trick(dog_id, 'play dead')
```

Access the state of the application by calling the
application query methods.

```python
tricks = school.get_tricks(dog_id)
assert tricks == ['roll over', 'play dead']
```

See the library's [documentation](https://eventsourcing.readthedocs.io/)
and the [SQLAlchemy](https://www.sqlalchemy.org/) project for more information.
