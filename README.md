# Event Sourcing in Python with SQLAlchemy

This package supports using the Python
[eventsourcing](https://github.com/pyeventsourcing/eventsourcing) library
with [SQLAlchemy](https://www.sqlalchemy.org/).

## Table of contents

<!-- TOC -->
* [Table of contents](#table-of-contents)
* [Quick start](#quick-start)
* [Installation](#installation)
* [Getting started](#getting-started)
* [Google Cloud SQL Python Connector](#google-cloud-sql-python-connector)
* [More information](#more-information)
<!-- TOC -->

## Quick start

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

os.environ['PERSISTENCE_MODULE'] = 'eventsourcing_sqlalchemy'
os.environ['SQLALCHEMY_URL'] = 'sqlite:///:memory:'
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

## Google Cloud SQL Python Connector

You can set the environment variable `SQLALCHEMY_CONNECTION_CREATOR_TOPIC` to a topic
that will resolve to a callable that will be used to create database connections.

For example, you can use the [Cloud SQL Python Connector](https://pypi.org/project/cloud-sql-python-connector/)
in the following way.

First install the Cloud SQL Python Connector package from PyPI.

    $ pip install 'cloud-sql-python-connector[pg8000]'

Then define a `getconn()` function, following the advice in the Cloud SQL
Python Connector README page.

```python
from google.cloud.sql.connector import Connector

# initialize Connector object
connector = Connector()

# function to return the database connection
def get_google_cloud_sql_conn():
    return connector.connect(
        "project:region:instance",
        "pg8000",
        user="postgres-iam-user@gmail.com",
        db="my-db-name",
        enable_iam_auth=True,
   )
```

Set the environment variable `'SQLALCHEMY_CONNECTION_CREATOR_TOPIC'`, along with
`'PERSISTENCE_MODULE'` and `'SQLALCHEMY_URL'`.

```python
from eventsourcing.utils import get_topic

os.environ['PERSISTENCE_MODULE'] = 'eventsourcing_sqlalchemy'
os.environ['SQLALCHEMY_URL'] = 'postgresql+pg8000://'
os.environ['SQLALCHEMY_CONNECTION_CREATOR_TOPIC'] = get_topic(get_google_cloud_sql_conn)
```

## More information

See the library's [documentation](https://eventsourcing.readthedocs.io/)
and the [SQLAlchemy](https://www.sqlalchemy.org/) project for more information.
