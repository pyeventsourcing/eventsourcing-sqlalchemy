# Event Sourcing in Python with SQLAlchemy

This package supports using the Python
[eventsourcing](https://github.com/pyeventsourcing/eventsourcing) library
with [SQLAlchemy](https://www.sqlalchemy.org/).

To use SQLAlchemy with your Python eventsourcing applications:
* install the Python package `eventsourcing_sqlalchemy`
* set the environment variable `PERSISTENCE_MODULE` to `'eventsourcing_sqlalchemy'`
* set the environment variable `SQLALCHEMY_URL` to an SQLAlchemy database URL

See below for more information.

## Installation

Use pip to install the [stable distribution](https://pypi.org/project/eventsourcing_sqlalchemy/)
from the Python Package Index. Please note, it is recommended to
install Python packages into a Python virtual environment.

    $ pip install eventsourcing_sqlalchemy

## Getting started

Define aggregates and applications in the usual way.

```python
from eventsourcing.application import Application
from eventsourcing.domain import Aggregate, event
from uuid import uuid5, NAMESPACE_URL


class TrainingSchool(Application):
    def register(self, name):
        dog = Dog(name)
        self.save(dog)

    def add_trick(self, name, trick):
        dog = self.repository.get(Dog.create_id(name))
        dog.add_trick(trick)
        self.save(dog)

    def get_tricks(self, name):
        dog = self.repository.get(Dog.create_id(name))
        return dog.tricks


class Dog(Aggregate):
    @event('Registered')
    def __init__(self, name):
        self.name = name
        self.tricks = []

    @staticmethod
    def create_id(name):
        return uuid5(NAMESPACE_URL, f'/dogs/{name}')

    @event('TrickAdded')
    def add_trick(self, trick):
        self.tricks.append(trick)
```

To use this module as the persistence module for your application, set the environment
variable `PERSISTENCE_MODULE` to `'eventsourcing_sqlalchemy'`.

When using this module, you need to set the environment variable `SQLALCHEMY_URL` to an
SQLAlchemy database URL for your database.
Please refer to the [SQLAlchemy documentation](https://docs.sqlalchemy.org/en/14/core/engines.html)
for more information about SQLAlchemy Database URLs.

```python
import os

os.environ["PERSISTENCE_MODULE"] = "eventsourcing_sqlalchemy"
os.environ["SQLALCHEMY_URL"] = "sqlite:///:memory:"
```

Construct and use the application in the usual way.

```python
school = TrainingSchool()
school.register('Fido')
school.add_trick('Fido', 'roll over')
school.add_trick('Fido', 'play dead')
tricks = school.get_tricks('Fido')
assert tricks == ['roll over', 'play dead']
```

See the library's [documentation](https://eventsourcing.readthedocs.io/)
and the [SQLAlchemy](https://www.sqlalchemy.org/) project for more information.
