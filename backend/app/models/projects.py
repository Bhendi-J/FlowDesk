from datetime import datetime,timezone
from app.database import Base
from sqlalchemy import String, Integer, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.users import Workspace
    from app.models.tasks import Task


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    name: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    workspace_id: Mapped[int] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False
    )

    workspace: Mapped["Workspace"] = relationship(
        back_populates="projects"
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=True
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan"
    )
    
    deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    def __repr__(self):
        return (
            f"Project(id={self.id!r}),"
            f"Project(name={self.name!r}),"
            f"Project(workspace_id={self.workspace_id!r})"
        )
    
