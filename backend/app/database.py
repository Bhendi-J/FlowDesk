from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
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

DBsession = Annotated[Session, Depends(get_db)]

