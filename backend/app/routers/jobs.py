"""
Rotas para criação e consulta de jobs de processamento.
Fluxo: Upload vídeo → cria Video → cria ProcessingJob → roda ML em background.
"""
import traceback
import uuid
import threading
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Video, ProcessingJob, Clip, Candidate
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
            candidatos = session.exec(select(Candidate).where(Candidate.job_id == job_id)).all()
            
            payload = {
                "job_id": str(job.id),
                "status": job.status,
                "candidates": [
                    {
                        "id": c.signature,          # O React espera 'id', nós mandamos a 'signature'
                        "name": c.name,
                        "number": c.number,
                        "color_hex": c.color_hex,
                        "image": c.image_path,      # O React espera 'image', mandamos o 'image_path'
                        "is_target": c.is_target
                    }
                    for c in candidatos
                ],
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

def update_job_status(job_id: uuid.UUID, status: str):
    """Função auxiliar isolada para atualizar status no banco dentro de threads."""
    from app.database import get_session
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

def run_fast_scan(job_id: uuid.UUID, video_path: str, target_number: int, start_ts: int, end_ts: int):
    """
    FASE 1: Roda a busca expressa e salva os candidatos no banco EM TEMPO REAL.
    """
    import sys
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
        
    print(f"[FAST SCAN] Iniciando job {job_id}")
    update_job_status(job_id, "FAST_SCAN")
    
    # CALLBACK 1: Salva foto no banco instantaneamente
    def save_candidate_to_db(cand_dict):
        from app.database import get_session
        session = next(get_session())
        try:
            novo_candidato = Candidate(
                job_id=job_id,
                signature=cand_dict["id"],
                name=cand_dict["name"],
                number=cand_dict["number"],
                color_hex=cand_dict["color"],
                image_path=cand_dict["image"],
                is_target=(cand_dict["number"] == target_number)
            )
            session.add(novo_candidato)
            
            # Força o 'updated_at' para o SSE disparar pro Frontend
            job = session.get(ProcessingJob, job_id)
            if job:
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as e:
            print(f"[DB ERROR] Erro ao salvar candidato: {e}")
            session.rollback()
        finally:
            session.close()

    # CALLBACK 2: Checa se o usuário clicou para abortar o Fast Scan
    def check_stop():
        from app.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            # Se o status mudou de FAST_SCAN para TRACKING (usuário clicou), interrompe!
            if not job:
                return True
            return job.status != "FAST_SCAN"
        finally:
            session.close()

    try:
        from ml.scripts.video_pipeline import VideoPipeline
        pipeline = VideoPipeline()
        output_dir = str(CLIPS_DIR / str(job_id))
        
        pipeline.fast_scan(
            video_path=video_path,
            output_dir=output_dir,
            target_number=target_number,
            frames_to_skip=30,
            on_candidate_found=save_candidate_to_db,
            should_stop=check_stop,
            start_ts=start_ts,
            end_ts=end_ts
        )

        # Se terminou o loop e ninguém clicou, muda para WAITING_USER
        from app.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if job and job.status == "FAST_SCAN":
                job.status = "WAITING_USER"
                session.commit()
                print(f"[FAST SCAN] Vídeo inteiro verificado. Aguardando usuário.")
        finally:
            session.close()

    except Exception:
        print(f"[FAST SCAN ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")


def run_full_tracking(job_id: uuid.UUID, video_path: str, target_number: int, target_signature: str, start_ts: int, end_ts: int):
    """
    FASE 2: Rastreio rigoroso filtrando pela Assinatura (Número + Cor).
    """
    import sys
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
        
    print(f"[TRACKING] Iniciando recorte final do job {job_id}")
    update_job_status(job_id, "TRACKING")
    
    def save_clip_to_db(clip_dict):
        from app.database import get_session
        session = next(get_session())
        try:
            new_clip = Clip(
                job_id=job_id,
                storage_path=clip_dict["path"],
                start_timestamp=clip_dict["start_ts"],
                end_timestamp=clip_dict["end_ts"],
            )
            session.add(new_clip)
            
            job = session.get(ProcessingJob, job_id)
            if job:
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"[db error] Falha ao salvar clipe: {e}")
        finally:
            session.close()

    def set_extracting_status():
        print(f"[TRACKING] Iniciando recorte de clipes. Mudando status para EXTRACTING.")
        update_job_status(job_id, "EXTRACTING")

    try:
        from ml.scripts.video_pipeline import VideoPipeline
        pipeline = VideoPipeline()
        output_dir = str(CLIPS_DIR / str(job_id))
        
        pipeline.process(
            video_path=video_path,
            target_number=target_number,
            target_signature=target_signature,
            output_dir=output_dir,
            start_ts=start_ts,
            end_ts=end_ts,
            on_clip_generated=save_clip_to_db,
            on_extracting_start=set_extracting_status,
            debug=True,
        )

        update_job_status(job_id, "COMPLETED")
        print(f"[TRACKING] Job {job_id} concluído.")

    except Exception:
        print(f"[TRACKING ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")



@router.post("/", status_code=202)
async def create_job(
    target_number: int  = Form(..., ge=0, le=999),
    video: UploadFile   = File(...),
    start_ts: int       = Form(0),
    end_ts: int         = Form(0),
    current_user: User  = Depends(get_current_user),
    session: Session    = Depends(get_session),
):
    """Fase 1: Recebe vídeo e dispara o Fast Scan."""
    # 1. Salva o arquivo em disco
    video_id   = uuid.uuid4()
    safe_name  = Path(str(video.filename)).name
    video_path = UPLOAD_DIR / f"{video_id}_{safe_name}"
    
    content = await video.read()
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

    # 4. Dispara o FAST SCAN (fase 1) em background
    thread = threading.Thread(
        target=run_fast_scan,
        args=(job.id, str(video_path), target_number, start_ts, end_ts),
        daemon=True,
    )
    thread.start()

    return {"job_id": str(job.id), "status": job.status}

class ConfirmPlayerRequest(BaseModel):
    candidate_signature: str

@router.post("/{job_id}/confirm")
def confirm_player(
    job_id: uuid.UUID, 
    payload: ConfirmPlayerRequest, 
    session: Session = Depends(get_session)
):
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job não encontrado.")

    if job.status not in ["FAST_SCAN", "WAITING_USER"]:
        raise HTTPException(status_code=400, detail="Este job não aceita mais confirmações.")

    if not job.video:
        raise HTTPException(status_code=500, detail="Erro interno: Vídeo não atrelado ao Job.")

    job.status = "TRACKING"
    session.add(job)
    session.commit()

    thread = threading.Thread(
        target=run_full_tracking,
        args=(job.id, job.video.storage_path, job.target_number, payload.candidate_signature, 0, 0),
        daemon=True,
    )
    thread.start()

    return {"message": "Processamento retomado.", "status": "TRACKING"}