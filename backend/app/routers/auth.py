"""
Rotas de autenticação: registro e login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.auth import get_current_user
from sqlmodel import Session, select
from app.database import get_session
from app.models import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, TokenPayload
from app.core.security import hash_password, verify_password, create_access_token
from pydantic import BaseModel, Field
import os
import secrets
from datetime import datetime, timedelta, timezone
from app.models.password_reset import PasswordResetToken
from app.core.email import send_reset_email
from app.core.security import hash_password

router = APIRouter(prefix="/auth", tags=["auth"])

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=8)

@router.post("/register", response_model=TokenPayload)
def register(data: UserCreate, session: Session = Depends(get_session)):
    """
    Registra um novo usuário. Retorna token e dados do usuário.
    """
    # Verifica se o e-mail já existe
    statement = select(User).where(User.email == data.email.lower())
    existing = session.exec(statement).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="E-mail já cadastrado.",
        )

    user = User(
        email=data.email.lower(),
        password_hash=hash_password(data.password),
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_access_token(str(user.id))
    return TokenPayload(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            max_clips_allowed=user.max_clips_allowed,
        ),
    )


@router.post("/login", response_model=TokenPayload)
def login(data: UserLogin, session: Session = Depends(get_session)):
    """
    Login com e-mail e senha. Retorna token e dados do usuário.
    """
    statement = select(User).where(User.email == data.email.lower())
    user = session.exec(statement).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha inválidos.",
        )

    access_token = create_access_token(str(user.id))
    return TokenPayload(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            max_clips_allowed=user.max_clips_allowed,
        ),
    )



@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(current_user: User = Depends(get_current_user)):
    """
    Logout. O cliente deve descartar o token localmente.
    """
    # Futuro: adicionar token à blacklist, registrar log, etc.
    return None


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
def forgot_password(data: ForgotPasswordRequest, session: Session = Depends(get_session)):
    statement = select(User).where(User.email == data.email.lower())
    user = session.exec(statement).first()

    if not user:
        return None

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    reset = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=expires_at,
    )
    session.add(reset)
    session.commit()

    send_reset_email(user.email, token)
    return None


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest, session: Session = Depends(get_session)):
    # Busca o token
    statement = select(PasswordResetToken).where(PasswordResetToken.token == data.token)
    reset = session.exec(statement).first()

    if not reset:
        raise HTTPException(status_code=400, detail="Token inválido.")

    if reset.used:
        raise HTTPException(status_code=400, detail="Token já utilizado.")

    if datetime.now(timezone.utc) > reset.expires_at.replace(tzinfo=timezone.utc):
        raise HTTPException(status_code=400, detail="Token expirado.")

    # Atualiza a senha
    statement = select(User).where(User.id == reset.user_id)
    user = session.exec(statement).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    user.password_hash = hash_password(data.new_password)
    reset.used = True

    session.add(user)
    session.add(reset)
    session.commit()

    return None