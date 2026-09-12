import os
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./flowdesk.db"))

class Base(DeclarativeBase):
    pass

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)


def get_db():
    with Session(engine) as session:
        yield session

def create_tables():
    print(Base.metadata.tables.keys())
    Base.metadata.create_all(bind = engine)
    _ensure_task_duration_uncertainty_columns()


def _ensure_task_duration_uncertainty_columns():
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    missing_columns = [
        column
        for column in (
            "duration_optimistic",
            "duration_likely",
            "duration_pessimistic",
        )
        if column not in existing_columns
    ]
    if not missing_columns:
        return

    with engine.begin() as connection:
        for column in missing_columns:
            connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {column} INTEGER"))

DBsession = Annotated[Session, Depends(get_db)]
