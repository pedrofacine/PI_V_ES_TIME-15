"""
Schemas Pydantic para auth: registro, login e respostas.
"""
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Payload para registro de usuário."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)


class UserLogin(BaseModel):
    """Payload para login."""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Usuário na resposta (sem senha)."""

    id: UUID
    email: str
    first_name: str
    last_name: str
    max_clips_allowed: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    """Resposta com access token e tipo."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Payload opcional: token + dados do usuário."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
