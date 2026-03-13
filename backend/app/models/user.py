import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship

from ..models import Video

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
