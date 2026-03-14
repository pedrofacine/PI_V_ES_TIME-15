from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select
from app.database import get_session
from app.models.user import User
from sqlalchemy.exc import SQLAlchemyError
from app.schemas.user_schema import UserCreate

router = APIRouter(prefix="/users", tags=["Users"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, session: Session = Depends(get_session)):
    try:
        statement = select(User).where(User.email == user.email)
        existing_user = session.exec(statement).first()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="E-mail já cadastrado"
            )

        new_user = User(
            email=user.email,
            password_hash=user.password,  
            first_name=user.first_name,
            last_name=user.last_name
        )

        session.add(new_user)
        session.commit()
        session.refresh(new_user)

        return {
            "message": "Usuário criado com sucesso",
            "user_id": new_user.id
        }

    except SQLAlchemyError:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro ao conectar ao banco de dados"
        )