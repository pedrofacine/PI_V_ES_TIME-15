"""
Rotas para criação e consulta de jobs de processamento.
Fluxo: Upload vídeo → cria Video → cria ProcessingJob → roda ML em background.
"""
import uuid
import json
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from app.core.database import get_session, engine
from app.core.deps import get_current_user
from app.core.exceptions import NotFoundError, ForbiddenError, ConflictError, DomainError
from app.core.storage import get_storage
from app.modules.identity.models import User
from app.modules.clips.models import Video, ProcessingJob, Clip, Candidate
from app.modules.clips.schemas import ConfirmPlayerRequest
from app.modules.clips.tasks import run_fast_scan, run_full_tracking

router = APIRouter(prefix="/jobs", tags=["jobs"])

BASE_DIR = Path(__file__).resolve().parents[2]

UPLOAD_DIR = BASE_DIR / "uploads" / "videos"
CLIPS_DIR  = BASE_DIR / "uploads" / "clips"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CLIPS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/{job_id}/stream")
def stream_job_status(job_id: uuid.UUID):
    def event_generator():
        while True:
            with Session(engine) as session:
                job = session.get(ProcessingJob, job_id)
                if not job:
                    yield f"data: {json.dumps({'error': 'Job não encontrado'})}\n\n"
                    return

                clips = session.exec(select(Clip).where(Clip.job_id == job_id)).all()
                candidatos = session.exec(select(Candidate).where(Candidate.job_id == job_id)).all()

                payload = {
                    "job_id": str(job.id),
                    "status": job.status,
                    "candidates": [
                        {
                            "id": c.signature,
                            "name": c.name,
                            "number": c.number,
                            "color_hex": c.color_hex,
                            "image": c.image_path,
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

                done = job.status in ["COMPLETED", "ERROR"]

            yield f"data: {json.dumps(payload)}\n\n"

            if done:
                return

            time.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

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

    content = await video.read()
    storage = get_storage()
    video_path = storage.save(content, f"videos/{video_id}_{safe_name}")

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

    # 4. Publica o FAST SCAN (fase 1) na fila do worker
    run_fast_scan.delay(job.id, str(video_path), target_number, start_ts, end_ts)

    return {"job_id": str(job.id), "status": job.status}

@router.delete("/{job_id}/clips", status_code=204)
def delete_job_clips(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Apaga todos os clipes de um job (remove o job do histórico)."""
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise NotFoundError("Job não encontrado.")

    video = session.get(Video, job.video_id)
    if not video or video.user_id != current_user.id:
        raise ForbiddenError("Este job não pertence ao usuário autenticado.")

    storage = get_storage()
    clips = session.exec(select(Clip).where(Clip.job_id == job_id)).all()
    for clip in clips:
        storage.delete(clip.storage_path)
        session.delete(clip)
    session.commit()


@router.post("/{job_id}/confirm")
def confirm_player(
    job_id: uuid.UUID, 
    payload: ConfirmPlayerRequest, 
    session: Session = Depends(get_session)
):
    job = session.get(ProcessingJob, job_id)
    if not job:
        raise NotFoundError("Job não encontrado.")

    if job.status not in ["FAST_SCAN", "WAITING_USER"]:
        raise ConflictError("Este job não aceita mais confirmações.")

    if not job.video:
        raise DomainError("Erro interno: Vídeo não atrelado ao Job.")
 
    if "_" in payload.candidate_signature:
        try:
            novo_numero = int(payload.candidate_signature.split("_")[0])
            job.target_number = novo_numero
        except ValueError:
            pass

    job.status = "TRACKING"
    session.add(job)
    session.commit()

    run_full_tracking.delay(
        job.id, job.video.storage_path, job.target_number,
        payload.candidate_signature, payload.start_ts, payload.end_ts,
    )

    return {"message": "Processamento retomado.", "status": "TRACKING"}

clips_router = APIRouter(prefix="/clips", tags=["clips"])
brasilia = timezone(timedelta(hours=-3))


@clips_router.get("/")
def list_clips(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    jobs = session.exec(
        select(ProcessingJob)
        .join(Video, ProcessingJob.video_id == Video.id)
        .where(Video.user_id == current_user.id)
        .where(ProcessingJob.status == "COMPLETED")
        .order_by(ProcessingJob.created_at.desc())
    ).all()

    result = []
    for job in jobs:
        clips = session.exec(select(Clip).where(Clip.job_id == job.id)).all()
        if not clips:
            continue
        result.append({
            "job_id": str(job.id),
            "target_number": job.target_number,
            "generated_at": job.updated_at.astimezone(brasilia).strftime("%d/%m/%Y - %H:%M"),
            "clips": [
                {
                    "id": str(c.id),
                    "file_url": f"/uploads/clips/{job.id}/{Path(c.storage_path).name}",
                    "duration": _format_duration(c.end_timestamp - c.start_timestamp),
                }
                for c in clips
            ],
        })
    return result


@clips_router.delete("/{clip_id}", status_code=204)
def delete_clip(
    clip_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    clip = session.get(Clip, clip_id)
    if not clip:
        raise NotFoundError("Clipe não encontrado.")

    job = session.get(ProcessingJob, clip.job_id)
    video = session.get(Video, job.video_id) if job else None
    if not video or video.user_id != current_user.id:
        raise ForbiddenError("Este clipe não pertence ao usuário autenticado.")

    get_storage().delete(clip.storage_path)
    session.delete(clip)
    session.commit()


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    m = total // 60
    s = total % 60
    return f"{m}:{s:02d}"
