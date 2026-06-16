from datetime import datetime,timezone
from app.database import Base
from app.models.workspaces import Workspace
from app.models.tasks import Task

from sqlalchemy import String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        unique=True
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="assigned_user",
        cascade="all, delete-orphan")
    

    workspaces: Mapped[list["Workspace"]] = relationship(
        back_populates="owner",
        cascade="all, delete-orphan")

    def __repr__(self):
        return (
            f"User(id={self.id!r}),"
            f"User(name={self.name!r}),"
            f"User(email={self.email!r}),"
        )
