import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship
from app.models.user import User
from app.models.processingJob import ProcessingJob


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