import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, status, HTTPException, Form
from pydantic import BaseModel

router = APIRouter(
    prefix="/api/videos",
    tags=["videos"],
)

UPLOAD_DIR = "temp_matches"


class UploadResponse(BaseModel):
    transaction_id: uuid.UUID
    message: str
    filename: str


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload(
        file: UploadFile = File(...),
        ref_number: Optional[int] = Form(default=None),
        ref_image: Optional[UploadFile] = File(default=None)
):
    print(f"--- Novo Upload Recebido ---")
    print(f"Vídeo: {file.filename}")
    print(f"Número de Referência: {ref_number}")
    if ref_image:
        allowed_image_extensions = {".png", ".jpg", ".jpeg"}
        image_ext = os.path.splitext(ref_image.filename)[1].lower()
        if(image_ext) not in allowed_image_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de imagem não suportado. Apenas {allowed_image_extensions} são permitidos."
            )
        print(f"Imagem de Referência recebida: {ref_image.filename}")
    else:
        print("Nenhuma imagem de referência enviada.")
    print(f"----------------------------")

    allowed_extensions = {".mp4", ".avi"}  # validação de formato
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Formato de video não suportado. Apenas {allowed_extensions} são permitidos."
        )

    transaction_id = uuid.uuid4()

    safe_filename = f"{transaction_id}{file_ext}"

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_location = os.path.join(UPLOAD_DIR, safe_filename)

    # salvamento feito em chunks (útil para grandes arquivos)
    try:
        with open(file_location, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao salvar o arquivo de vídeo: {str(e)}"
        )
    finally:
        file.file.close()  # libera memória

    return UploadResponse(
        transaction_id=transaction_id,
        message="Upload recebido com sucesso. Processamento pendente.",
        filename=safe_filename
    )