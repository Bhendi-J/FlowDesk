
from app.database import Base
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False
    )

    depends_on_task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id"),
        nullable=False
    )