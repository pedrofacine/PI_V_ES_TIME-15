import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.models.processingJob import ProcessingJob


class Clip(SQLModel, table=True):
    __tablename__ = "clips"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    storage_path: str
    start_timestamp: float
    end_timestamp: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    job: Optional["ProcessingJob"] = Relationship(back_populates="clips")