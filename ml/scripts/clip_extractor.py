"""
Extração e escrita de clipes de vídeo.

Responsabilidade única (SRP): lê frames do vídeo original, aplica padding
temporal e delega a codificação ao ClipWriterPort.
Corresponde ao Passo 4 do Template Method em VideoPipeline.
"""
from __future__ import annotations

import os
from logging import Logger
from typing import Callable

import cv2
import numpy as np

from ml.scripts.config import CLIP_PADDING_SECONDS
from ml.scripts.detection_utils import resize_frame


class ClipExtractor:
    """
    Executa o Passo 4 do pipeline: fatia o vídeo e grava os clipes.

    Depende apenas de ClipWriterPort (DIP), tornando a estratégia de
    escrita substituível sem alterar esta classe (OCP).
    """

    def __init__(self, clip_writer) -> None:
        self.clip_writer = clip_writer

    def write_clips(
        self,
        video_path: str,
        clip_intervals: list[tuple[int, int]],
        events: list[dict],
        target_number: int,
        output_dir: str,
        fps: float,
        total_frames: int,
        on_clip_generated: Callable | None,
        logger: Logger,
    ) -> list[dict]:
        """Fatia o vídeo original em clipes aplicando padding temporal."""
        logger.info(f"[4/4] Fatiando vídeo em {len(clip_intervals)} clipes...")

        results: list[dict] = []
        padding_frames = int(CLIP_PADDING_SECONDS * fps)

        cap = cv2.VideoCapture(video_path)
        try:
            for idx, (start_f, end_f) in enumerate(clip_intervals):
                clip_dict = self._extract_and_write_clip(
                    cap=cap,
                    clip_idx=idx,
                    start_f=start_f,
                    end_f=end_f,
                    padding_frames=padding_frames,
                    total_frames=total_frames,
                    fps=fps,
                    target_number=target_number,
                    output_dir=output_dir,
                    events=events,
                    logger=logger,
                )
                if clip_dict:
                    results.append(clip_dict)
                    if on_clip_generated:
                        on_clip_generated(clip_dict)
        finally:
            cap.release()

        return results

    def _extract_and_write_clip(
        self,
        cap: cv2.VideoCapture,
        clip_idx: int,
        start_f: int,
        end_f: int,
        padding_frames: int,
        total_frames: int,
        fps: float,
        target_number: int,
        output_dir: str,
        events: list[dict],
        logger: Logger,
    ) -> dict | None:
        """Coordena leitura, escrita e montagem do resultado de um único clipe."""
        padded_start = max(0, start_f - padding_frames)
        padded_end = min(total_frames - 1, end_f + padding_frames)

        if padded_start >= total_frames:
            logger.error(f"Tentativa de acesso a frame fora dos limites do vídeo: {padded_start}")
            return None

        clip_frames = self._read_clip_frames(cap, padded_start, padded_end)

        if not clip_frames:
            logger.error(f"Falha de I/O: Nenhum frame capturado para o clipe {clip_idx}")
            return None

        clip_path = self._build_clip_path(
            target_number, clip_idx, padded_start, padded_end, fps, output_dir
        )

        h, w = clip_frames[0].shape[:2]
        self.clip_writer.write(clip_frames, clip_path, fps, (w, h))

        return {
            "path": clip_path,
            "start_ts": padded_start / fps,
            "end_ts": padded_end / fps,
            "events": [e for e in events if start_f <= e["frame"] <= end_f],
        }

    def _read_clip_frames(
        self,
        cap: cv2.VideoCapture,
        padded_start: int,
        padded_end: int,
    ) -> list[np.ndarray]:
        """Lê e redimensiona os frames de um intervalo de clipe."""
        cap.set(cv2.CAP_PROP_POS_FRAMES, padded_start)
        frames: list[np.ndarray] = []
        for _ in range(padded_end - padded_start + 1):
            ret, frame_orig = cap.read()
            if not ret:
                break
            frames.append(resize_frame(frame_orig))
        return frames

    @staticmethod
    def _build_clip_path(
        target_number: int,
        clip_idx: int,
        padded_start: int,
        padded_end: int,
        fps: float,
        output_dir: str,
    ) -> str:
        """Gera o caminho absoluto do arquivo de clipe."""
        start_s = int(padded_start / fps)
        end_s = int(padded_end / fps)
        name = f"jogador_{target_number}_clipe_{clip_idx + 1}_{start_s}s_a_{end_s}s.mp4"
        return os.path.join(output_dir, name)
