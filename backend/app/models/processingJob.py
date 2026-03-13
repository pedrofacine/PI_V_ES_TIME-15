import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from models import Video, Clip

class ProcessingJob(SQLModel, table=True):
    __tablename__ = "processing_jobs"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    video_id: uuid.UUID = Field(foreign_key="videos.id")
    target_number: int
    status: str # PENDING, SCANNING, PAUSED_FOR_HITL, TRACKING, COMPLETED
    hitl_thumbnail_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    video: Optional[Video] = Relationship(back_populates="jobs")
    clips: List["Clip"] = Relationship(back_populates="job")