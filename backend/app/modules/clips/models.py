import uuid
from datetime import datetime, timezone
from typing import Optional, List, TYPE_CHECKING

from sqlmodel import Field, SQLModel, Relationship

if TYPE_CHECKING:
    from app.modules.identity.models import User


class Video(SQLModel, table=True):
    __tablename__ = "videos"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    original_filename: str
    storage_path: str
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    user: Optional["User"] = Relationship(back_populates="videos")
    jobs: List["ProcessingJob"] = Relationship(back_populates="video")


class ProcessingJob(SQLModel, table=True):
    __tablename__ = "processing_jobs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    video_id: uuid.UUID = Field(foreign_key="videos.id")
    target_number: int
    status: str
    hitl_thumbnail_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    video: Optional["Video"] = Relationship(back_populates="jobs")
    clips: List["Clip"] = Relationship(back_populates="job")
    candidates: List["Candidate"] = Relationship(
        back_populates="job",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Clip(SQLModel, table=True):
    __tablename__ = "clips"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    storage_path: str
    start_timestamp: float
    end_timestamp: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    job: Optional["ProcessingJob"] = Relationship(back_populates="clips")


class Candidate(SQLModel, table=True):
    __tablename__ = "candidates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    signature: str
    name: str
    number: int
    color_hex: Optional[str] = None
    image_path: str
    is_target: bool = Field(default=False)

    job: Optional["ProcessingJob"] = Relationship(back_populates="candidates")
