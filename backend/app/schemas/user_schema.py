import uuid
from datetime import datetime
from sqlmodel import SQLModel


class UserCreate(SQLModel):
    email: str
    password: str
    first_name: str
    last_name: str


class UserLogin(SQLModel):
    email: str
    password: str


class UserResponse(SQLModel):
    id: uuid.UUID
    email: str
    first_name: str
    last_name: str
    max_clips_allowed: int
    created_at: datetime