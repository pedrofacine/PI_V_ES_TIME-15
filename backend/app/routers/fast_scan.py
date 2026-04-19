import uuid

from fastapi import BackgroundTasks
from sqlmodel import Session
from backend.app.models import ProcessingJob
from backend.app.models import Candidate
from ml.scripts.video_pipeline import VideoPipeline
import os

def run_fast_scan(job_id: uuid.UUID, video_path: str, output_dir: str, target_number: int, db: Session):
    """
    Fase 1: Busca expressa de candidatos.
    """
    job = db.get(ProcessingJob, job_id)
    if not job:
        return

    try:
        # Atualiza o status para o Front-end saber o que está a acontecer
        job.status = "FAST_SCAN"
        db.add(job)
        db.commit()

        pipeline = VideoPipeline() # Usa a nossa classe refatorada
        
        # Executa o Fast Scan (pulando 30 frames = 1 seg)
        candidatos_dict = pipeline.fast_scan(
            video_path=video_path,
            output_dir=output_dir,
            target_number=target_number,
            frames_to_skip=30
        )

        # Guarda os candidatos na Base de Dados usando o modelo Candidate
        for cand in candidatos_dict:
            novo_candidato = Candidate(
                job_id=job.id,
                signature=cand["signature"],
                name=cand["name"],
                number=cand["number"],
                color_hex=cand["color_hex"],
                image_path=cand["image_path"],
                is_target=cand["is_target"]
            )
            db.add(novo_candidato)

        # Muda o status para pausar o processamento e avisar o utilizador
        job.status = "WAITING_USER"
        db.add(job)
        db.commit()

    except Exception as e:
        job.status = "ERROR"
        db.add(job)
        db.commit()
        print(f"[ERRO NO FAST SCAN] {e}")