import json
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, Text, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator
from .config import settings


class EncryptedJSON(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return (
            Fernet(settings().encryption_key.encode())
            .encrypt(json.dumps(value, ensure_ascii=False, default=str).encode())
            .decode()
        )

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(
            Fernet(settings().encryption_key.encode()).decrypt(value.encode())
        )


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings().database_url,
    pool_pre_ping=True,
    **(
        {"connect_args": {"check_same_thread": False}}
        if settings().database_url.startswith("sqlite")
        else {"pool_size": 4, "max_overflow": 2}
    ),
)
if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def sqlite_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        yield db
