from sqlalchemy import BigInteger, Column, Index, Integer, LargeBinary, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_utils.types.uuid import UUIDType

Base = declarative_base()


class StoredEventRecord(Base):
    __tablename__ = "stored_events"
    __abstract__ = True

    # Notification ID.
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType())

    # Originator version of item in sequence.
    originator_version = Column(
        BigInteger().with_variant(Integer, "sqlite")
    )

    # Topic of the item (e.g. path to domain event class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(LargeBinary())

    __table_args__ = (
        Index(
            "stored_aggregate_event_index",
            "originator_id",
            "originator_version",
            unique=True,
        ),
    )


class SnapshotRecord(Base):
    __tablename__ = "snapshots"
    __abstract__ = True

    # Originator ID (e.g. an entity or aggregate ID).
    originator_id = Column(UUIDType(), primary_key=True)

    # Originator version of item in sequence.
    originator_version = Column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )

    # Topic of the item (e.g. path to domain entity class).
    topic = Column(Text(), nullable=False)

    # State of the item (serialized dict, possibly encrypted).
    state = Column(LargeBinary())


class NotificationTrackingRecord(Base):
    __tablename__ = "notification_tracking"
    __abstract__ = True

    # Application name.
    application_name = Column(String(length=32), primary_key=True)

    # Notification ID.
    notification_id = Column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True
    )
