from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session

DATABASE_URL = "sqlite:///./flowdesk.db"

# Later:
# DATABASE_URL = "postgresql+psycopg2://user:password@localhost/dbname"

class Base(DeclarativeBase):
    pass

connect_args = {"check_same_thread": False}
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
