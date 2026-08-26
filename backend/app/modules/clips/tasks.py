"""Tasks Celery de processamento de vídeo (rodam no worker, com torch/GPU).

Movidas de `router.py`. O import de `ml` é feito DENTRO da task (lazy), então a
API pode importar este módulo (para publicar via `.delay()`) sem puxar torch.
"""
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.modules.clips.models import ProcessingJob, Clip, Candidate

BASE_DIR = Path(__file__).resolve().parents[2]
CLIPS_DIR = BASE_DIR / "uploads" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)


def update_job_status(job_id: uuid.UUID, status: str):
    """Atualiza o status do job no DB de forma isolada."""
    from app.core.database import get_session
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


@celery_app.task(name="app.modules.clips.tasks.run_fast_scan")
def run_fast_scan(job_id: uuid.UUID, video_path: str, target_number: int, start_ts: int, end_ts: int):
    """FASE 1: busca expressa; salva candidatos no DB em tempo real."""
    print(f"[FAST SCAN] Iniciando job {job_id}")
    update_job_status(job_id, "FAST_SCAN")

    def save_candidate_to_db(cand_dict):
        from app.core.database import get_session
        session = next(get_session())
        try:
            novo_candidato = Candidate(
                job_id=job_id,
                signature=cand_dict["id"],
                name=cand_dict["name"],
                number=cand_dict["number"],
                color_hex=cand_dict["color"],
                image_path=cand_dict["image"],
                is_target=(cand_dict["number"] == target_number),
            )
            session.add(novo_candidato)
            job = session.get(ProcessingJob, job_id)
            if job:
                job.updated_at = datetime.now(timezone.utc)
            session.commit()
        except Exception as e:
            print(f"[DB ERROR] Erro ao salvar candidato: {e}")
            session.rollback()
        finally:
            session.close()

    def check_stop():
        from app.core.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if not job:
                return True
            return job.status != "FAST_SCAN"
        finally:
            session.close()

    try:
        from ml.scripts.process_video import _get_pipeline
        pipeline = _get_pipeline()
        output_dir = str(CLIPS_DIR / str(job_id))

        pipeline.fast_scan(
            video_path=video_path,
            output_dir=output_dir,
            target_number=target_number,
            frames_to_skip=30,
            on_candidate_found=save_candidate_to_db,
            should_stop=check_stop,
            start_ts=start_ts,
            end_ts=end_ts,
        )

        from app.core.database import get_session
        session = next(get_session())
        try:
            job = session.get(ProcessingJob, job_id)
            if job and job.status == "FAST_SCAN":
                job.status = "WAITING_USER"
                session.commit()
                print("[FAST SCAN] Vídeo inteiro verificado. Aguardando usuário.")
        finally:
            session.close()

    except Exception:
        print("[FAST SCAN ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")


@celery_app.task(name="app.modules.clips.tasks.run_full_tracking")
def run_full_tracking(job_id: uuid.UUID, video_path: str, target_number: int, target_signature: str, start_ts: int, end_ts: int):
    """FASE 2: rastreio rigoroso filtrando pela assinatura (número + cor)."""
    print(f"[TRACKING] Iniciando recorte final do job {job_id}")
    update_job_status(job_id, "TRACKING")

    def save_clip_to_db(clip_dict):
        from app.core.database import get_session
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
        print("[TRACKING] Iniciando recorte de clipes. Mudando status para EXTRACTING.")
        update_job_status(job_id, "EXTRACTING")

    try:
        from ml.scripts.process_video import _get_pipeline
        pipeline = _get_pipeline()
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
        print("[TRACKING ERROR] Falha:")
        print(traceback.format_exc())
        update_job_status(job_id, "ERROR")
