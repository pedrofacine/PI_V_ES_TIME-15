"""
Rotas de autenticação: registro e login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import User
from app.schemas.auth import UserCreate, UserLogin, UserResponse, Token, TokenPayload
from app.core.security import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


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
