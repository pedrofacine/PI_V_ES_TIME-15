import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str
    first_name: str
    last_name: str
    max_clips_allowed: int = Field(default=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    videos: List["Video"] = Relationship(back_populates="user")


class Video(SQLModel, table=True):
    __tablename__ = "videos"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id")
    original_filename: str
    storage_path: str
    duration_seconds: Optional[float] = None
    file_size_mb: Optional[float] = None
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    user: Optional[User] = Relationship(back_populates="videos")
    jobs: List["ProcessingJob"] = Relationship(back_populates="video")


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


class Clip(SQLModel, table=True):
    __tablename__ = "clips"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    job_id: uuid.UUID = Field(foreign_key="processing_jobs.id")
    storage_path: str
    start_timestamp: float
    end_timestamp: float
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relacionamentos
    job: Optional[ProcessingJob] = Relationship(back_populates="clips")