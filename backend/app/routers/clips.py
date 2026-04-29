"""
Rotas de clipes gerados pelo usuário.
"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models import User, Video, ProcessingJob, Clip
from app.core.auth import get_current_user
from datetime import timezone, timedelta


router = APIRouter(prefix="/clips", tags=["clips"])
brasilia = timezone(timedelta(hours=-3))

@router.get("/")
def list_clips(
    current_user: User = Depends(get_current_user),
    session: Session   = Depends(get_session),
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
        clips = session.exec(
            select(Clip).where(Clip.job_id == job.id)
        ).all()

        if not clips:
            continue

        result.append({
            "job_id":        str(job.id),
            "target_number": job.target_number,
            "generated_at": job.updated_at.astimezone(brasilia).strftime("%d/%m/%Y - %H:%M"),
            "clips": [
                {
                    "id":       str(c.id),
                    "file_url": f"/uploads/clips/{job.id}/{Path(c.storage_path).name}",
                    "duration": _format_duration(c.end_timestamp - c.start_timestamp),
                }
                for i, c in enumerate(clips)
            ],
        })

    return result


def _format_duration(seconds: float) -> str:
    total = int(seconds)
    m = total // 60
    s = total % 60
    return f"{m}:{s:02d}"