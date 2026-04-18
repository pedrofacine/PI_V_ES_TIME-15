"""
Rotas para criação e consulta de jobs de processamento.
Fluxo: Upload vídeo → cria Video → cria ProcessingJob → roda ML em background.
"""
import traceback
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

import json
import time
from fastapi.responses import StreamingResponse
from fastapi import Query
from app.database import get_session as _get_session
from app.models import ProcessingJob

router = APIRouter(prefix="/jobs", tags=["jobs"])

BASE_DIR = Path(__file__).resolve().parents[2]

UPLOAD_DIR = BASE_DIR / "uploads" / "videos"
CLIPS_DIR  = BASE_DIR / "uploads" / "clips"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/{job_id}/stream")
def stream_job_status(
    job_id: uuid.UUID,
    token: str = Query(...),
    session: Session = Depends(get_session),
):
    def event_generator():
        while True:
            # 1. LIMPEZA DE CACHE (Força a leitura dos dados reais do banco)
            session.expire_all()
            
            # 2. Busca o status atual no banco
            job = session.get(ProcessingJob, job_id)
            if not job:
                yield f"data: {json.dumps({'error': 'Job não encontrado'})}\n\n"
                break
            
            clips = session.exec(select(Clip).where(Clip.job_id == job_id)).all()
            
            payload = {
                "job_id": str(job.id),
                "status": job.status,
                "clips": [
                    {
                        "id": str(c.id),
                        "file_url": f"/uploads/clips/{job_id}/{Path(c.storage_path).name}",
                        "start_timestamp": c.start_timestamp,
                        "end_timestamp": c.end_timestamp,
                        "duration": round(c.end_timestamp - c.start_timestamp, 2),
                    }
                    for c in clips
                ]
            }

            yield f"data: {json.dumps(payload)}\n\n"

            if job.status in ["COMPLETED", "ERROR"]:
                break
            
            time.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

def run_pipeline(job_id: uuid.UUID, video_path: str, target_number: int, start_ts: int = 0, end_ts: int = 0):
    import sys
    import traceback
    from datetime import datetime, timezone
    
    print(f"[pipeline] Iniciando job {job_id}") 
    print(f"[pipeline] start_ts={start_ts} end_ts={end_ts}")

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    ML_ROOT = PROJECT_ROOT / "ml"

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if str(ML_ROOT) not in sys.path:
        sys.path.insert(0, str(ML_ROOT))

    # 1. FUNÇÃO AUXILIAR: Abre e fecha a sessão rapidamente apenas para atualizar status
    def update_job_status(status: str):
        from app.database import get_session
        from app.models import ProcessingJob
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if job:
                job.status = status
                job.updated_at = datetime.now(timezone.utc)
                session.commit()
        except Exception as e:
            session.rollback()
            print(f"[db error] Falha ao atualizar status: {e}")
        finally:
            session.close()

    try:
        try:
            from ml.scripts.process_video import process_video
            print(f"[pipeline] process_video importado OK")
        except Exception:
            print("ERRO AO IMPORTAR process_video")
            print(traceback.format_exc())
            update_job_status("ERROR")
            return

        # Atualiza status inicial (Sessão rápida)
        update_job_status("SCANNING")

        # 2. CALLBACKS ISOLADOS: Cada callback abre e fecha sua própria conexão
        def set_status_to_tracking():
            print(f"[pipeline] Callback: Jogador encontrado. Mudando para TRACKING.")
            update_job_status("TRACKING")

        def save_clip_to_db(clip_dict):
            from app.database import get_session
            from app.models import Clip, ProcessingJob
            
            session = next(get_session())
            try:
                new_clip = Clip(
                    job_id          = job_id,
                    storage_path    = clip_dict["path"],
                    start_timestamp = clip_dict["start_ts"],
                    end_timestamp   = clip_dict["end_ts"],
                )
                session.add(new_clip)
                
                # Atualiza o timestamp do job para forçar o frontend (via SSE) a perceber a mudança
                job_to_update = session.get(ProcessingJob, job_id)
                if job_to_update:
                    job_to_update.updated_at = datetime.now(timezone.utc)
                
                session.commit()
                print(f"[pipeline] Clipe persistido e enviado ao front: {clip_dict['path']}")
            except Exception as e:
                session.rollback()
                print(f"[db error] Falha ao salvar clipe: {e}")
            finally:
                session.close()

        # 3. CHAMADA PRINCIPAL: Executa a IA. Não há nenhuma conexão de BD aberta vazando aqui!
        print(f"[pipeline] Chamando process_video...")
        output_dir = str(CLIPS_DIR / str(job_id))
        
        process_video(
            video_path=video_path, 
            target_number=target_number, 
            output_dir=output_dir,
            start_ts=start_ts,
            end_ts=end_ts,
            on_player_found=set_status_to_tracking,
            on_clip_generated=save_clip_to_db,
            debug=True,
        )

        # Atualiza final (Sessão rápida)
        update_job_status("COMPLETED")
        print(f"[pipeline] Job {job_id} concluído.")

    except Exception:
        print(f"[pipeline error] Falha durante a execução:")
        print(traceback.format_exc())
        update_job_status("ERROR")



@router.post("/", status_code=202)
async def create_job(
    target_number: int  = Form(..., ge=0, le=999),
    video: UploadFile   = File(...),
    start_ts: int       = Form(0),
    end_ts: int         = Form(0),
    current_user: User  = Depends(get_current_user),
    session: Session    = Depends(get_session),
):
    """Recebe vídeo + número da camisa, persiste e inicia o processamento."""

    # 1. Salva o arquivo em disco
    video_id   = uuid.uuid4()
    safe_name  = Path(video.filename).name
    video_path = UPLOAD_DIR / f"{video_id}_{safe_name}"

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    
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