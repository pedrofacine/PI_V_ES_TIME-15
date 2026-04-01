"""
Rotas para criação e consulta de jobs de processamento.
Fluxo: Upload vídeo → cria Video → cria ProcessingJob → roda ML em background.
"""
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Video, ProcessingJob, Clip
from app.core.auth import get_current_user

import traceback

router = APIRouter(prefix="/jobs", tags=["jobs"])

UPLOAD_DIR = Path("uploads/videos")
CLIPS_DIR  = Path("uploads/clips")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)



def run_pipeline(job_id: uuid.UUID, video_path: str, target_number: int, start_ts: int, end_ts: int):
    import sys
    print(f"[pipeline] Iniciando job {job_id} do seg {start_ts} ao {end_ts}") 
    
    # Adiciona o caminho dos scripts de ML
    scripts_path = str(Path(__file__).parent.parent.parent.parent / "ml" / "scripts")
    if scripts_path not in sys.path:
        sys.path.append(scripts_path)

    # IMPORTANTE: Importamos a engine diretamente, não o generator de sessão do FastAPI
    from app.database import engine 

    # Abrimos uma sessão de banco EXCLUSIVA para esta thread
    try:
        with Session(engine) as session:
            job = session.get(ProcessingJob, job_id)
            if not job:
                print(f"[pipeline error] Job {job_id} não encontrado no banco de dados.")
                return

            # Atualiza para TRACKING imediatamente
            job.status     = "TRACKING"
            job.updated_at = datetime.now(timezone.utc)
            session.commit()

            print(f"[pipeline] Importando módulo process_video...")
            from process_video import process_video
            print(f"[pipeline] process_video importado com sucesso.")

            output_dir = str(CLIPS_DIR / str(job_id))
            
            print(f"[pipeline] Executando IA...")
            clip_data = process_video(video_path, target_number, output_dir, start_ts, end_ts)

            for item in clip_data:
                clip = Clip(
                    job_id          = job_id,
                    storage_path    = item["path"],
                    start_timestamp = item["start_ts"],
                    end_timestamp   = item["end_ts"],
                )
                session.add(clip)

            job.status     = "COMPLETED"
            job.updated_at = datetime.now(timezone.utc)
            session.commit()
            print(f"[pipeline] Job {job_id} concluído com {len(clip_data)} clipe(s).")

    except Exception as e:
        # Se qualquer coisa falhar (importação, banco, YOLO), o código cai aqui
        print(f"\n[PIPELINE CRASH] Erro durante o processamento do Job {job_id}:")
        traceback.print_exc() # Imprime o stack trace completo no console para podermos debugar
        
        # Garante que o frontend saiba que falhou abrindo uma nova sessão de emergência
        try:
            from app.database import engine
            with Session(engine) as error_session:
                job = error_session.get(ProcessingJob, job_id)
                if job:
                    job.status     = "ERROR"
                    job.updated_at = datetime.now(timezone.utc)
                    error_session.commit()
                    print(f"[pipeline recovery] Status do Job {job_id} atualizado para ERROR.")
        except Exception as db_err:
            print(f"[pipeline error] Falha crítica ao tentar gravar ERROR no banco: {db_err}")



@router.post("/", status_code=202)
async def create_job(
    target_number: int  = Form(..., ge=0, le=999),
    video: UploadFile   = File(...),
    current_user: User  = Depends(get_current_user),
    session: Session    = Depends(get_session),
    start_ts: int       = Form(...),
    end_ts: int         = Form(...)
):
    """Recebe vídeo + número da camisa, persiste e inicia o processamento."""

    # 1. Salva o arquivo em disco
    video_id   = uuid.uuid4()
    safe_name  = Path(video.filename).name
    video_path = UPLOAD_DIR / f"{video_id}_{safe_name}"
    content    = await video.read()

    with open(video_path, "wb") as f:
        f.write(content)

    size_mb = len(content) / (1024 * 1024)

    # 2. Cria registro Video
    db_video = Video(
        id                = video_id,
        user_id           = current_user.id,
        original_filename = safe_name,
        storage_path      = str(video_path),
        file_size_mb      = round(size_mb, 2),
    )
    session.add(db_video)
    session.commit()
    session.refresh(db_video)

    # 3. Cria ProcessingJob
    job = ProcessingJob(
        video_id      = video_id,
        target_number = target_number,
        status        = "PENDING",
    )
    session.add(job)
    session.commit()
    session.refresh(job)

    # 4. Dispara pipeline em background
    thread = threading.Thread(
        target  = run_pipeline,
        args    = (job.id, str(video_path), target_number, start_ts, end_ts),
        daemon  = True,
    )
    thread.start()

    return {"job_id": str(job.id), "status": job.status}


@router.get("/{job_id}")
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session   = Depends(get_session),
):
    
    job = session.get(ProcessingJob, job_id)

    # valida existência e ownership via Video
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    video = session.get(Video, job.video_id)
    if not video or str(video.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Acesso negado.")

    clips = session.exec(
        select(Clip).where(Clip.job_id == job_id)
    ).all()

    return {
        "job_id": str(job.id),
        "status": job.status,
        "clips": [
            {
                "id":              str(c.id),
                "file_url":        f"/uploads/clips/{job_id}/{Path(c.storage_path).name}",
                "start_timestamp": c.start_timestamp,
                "end_timestamp":   c.end_timestamp,
                "duration":        round(c.end_timestamp - c.start_timestamp, 2),
            }
            for c in clips
        ],
    }