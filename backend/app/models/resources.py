from app.database import Base
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    requirements: Mapped[list["TaskResourceRequirement"]] = relationship(
        back_populates="resource",
        cascade="all, delete-orphan",
    )


class TaskResourceRequirement(Base):
    __tablename__ = "task_resource_requirements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )
    resource_id: Mapped[int] = mapped_column(
        ForeignKey("resources.id"),
        nullable=False,
        index=True,
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    resource: Mapped["Resource"] = relationship(back_populates="requirements")
