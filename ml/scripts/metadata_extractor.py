"""
Extração de metadados do vídeo: tracks de jogadores, bola e mapa de camisas.

Responsabilidade única (SRP): concentra toda a lógica de processamento
frame-a-frame — detecção, tracking e OCR de camisas.
Corresponde ao Passo 1 do Template Method em VideoPipeline.
"""
from __future__ import annotations

import os
from collections import Counter, defaultdict
from logging import Logger

import cv2
import numpy as np

from ml.scripts.config import (
    FRAME_SKIP,
    MIN_OCR_VOTES,
    OCR_INTERVAL,
    TRACKING_COLOR_TOLERANCE,
)
from ml.scripts.detection_utils import (
    color_distance,
    extract_core_color,
    get_safe_fps,
    is_valid_player_detection,
    resize_frame,
)


class MetadataExtractor:
    """
    Executa o Passo 1 do pipeline: detecção + tracking + OCR frame-a-frame.

    Recebe componentes de detecção via injeção de dependência (DIP),
    tornando-o testável e extensível sem modificar o pipeline principal (OCP).
    """

    def __init__(self, detector, ball_detector, jersey_reader, color_extractor) -> None:
        self.detector = detector
        self.ball_detector = ball_detector
        self.jersey_reader = jersey_reader
        self.color_extractor = color_extractor

    def extract(
        self,
        cap: cv2.VideoCapture,
        tracker,
        ball_tracker,
        start_frame: int,
        end_frame: int,
        total_frames: int,
        target_number: int,
        target_signature: str | None,
        debug: bool,
        debug_dir: str | None,
        logger: Logger,
    ) -> tuple[dict, dict, int]:
        """Processa o vídeo frame-a-frame e retorna (video_metadata, jersey_map, max_frame)."""
        logger.info(f"[1/4] Extraindo metadados com IA ({total_frames} frames)...")
        fps = get_safe_fps(cap)
        logger.info(
            f"[video] Começando no segundo "
            f"{start_frame // max(1, int(fps))} (frame {start_frame})"
        )
        logger.info(f"[video] Terminando no frame {end_frame}")

        video_metadata: dict[int, dict] = {}
        jersey_map: dict[str, Counter] = defaultdict(Counter)
        max_frame = start_frame - 1

        # Heurística de densidade (fast-forward dinâmico)
        MIN_PLAYERS_THRESHOLD = 1
        TIME_TO_SLEEP_SEC = 10
        FAST_FORWARD_SKIP_SEC = 5

        processed_fps = fps / max(1, FRAME_SKIP)
        frames_to_trigger_sleep = int(processed_fps * TIME_TO_SLEEP_SEC)
        fast_forward_frames = int(fps * FAST_FORWARD_SKIP_SEC)
        consecutive_low_density = 0

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame

        while True:
            ret, frame_orig = cap.read()
            if not ret:
                break
            if frame_idx > end_frame:
                break

            max_frame = max(max_frame, frame_idx)

            if frame_idx % FRAME_SKIP != 0:
                if frame_idx > start_frame and (frame_idx - 1) in video_metadata:
                    video_metadata[frame_idx] = video_metadata[frame_idx - 1]
                frame_idx += 1
                continue

            frame = resize_frame(frame_orig)
            scale = frame_orig.shape[1] / frame.shape[1]

            raw_detections, _ = self.detector.detect(frame)
            valid_detections = [
                det for det in raw_detections
                if is_valid_player_detection(det[0], frame.shape[0])
            ]

            if len(valid_detections) < MIN_PLAYERS_THRESHOLD:
                consecutive_low_density += 1
            else:
                consecutive_low_density = 0

            if consecutive_low_density > frames_to_trigger_sleep:
                logger.info(
                    f"[FAST-FORWARD] Campo vazio (frame {frame_idx}). "
                    f"Pulando {FAST_FORWARD_SKIP_SEC}s..."
                )
                next_frame = frame_idx + fast_forward_frames
                cap.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
                frame_idx = next_frame
                consecutive_low_density = 0
                continue

            balls = self.ball_detector.detect(frame)
            ball_box = ball_tracker.update(frame_idx, balls)
            tracks = tracker.update(valid_detections, frame)

            video_metadata[frame_idx] = {
                "tracks": [
                    [float(l), float(t), float(r), float(b), str(tid)]
                    for l, t, r, b, tid in tracks
                ],
                "balls": [[float(x) for x in ball_box]] if ball_box else [],
            }

            if frame_idx % OCR_INTERVAL == 0:
                self._run_ocr_on_tracks(
                    tracks=tracks,
                    frame_orig=frame_orig,
                    scale=scale,
                    target_number=target_number,
                    target_signature=target_signature,
                    frame_idx=frame_idx,
                    jersey_map=jersey_map,
                    debug=debug,
                    debug_dir=debug_dir,
                    logger=logger,
                )

            frame_idx += 1

        return video_metadata, jersey_map, max_frame

    def _run_ocr_on_tracks(
        self,
        tracks: list,
        frame_orig: np.ndarray,
        scale: float,
        target_number: int,
        target_signature: str | None,
        frame_idx: int,
        jersey_map: dict,
        debug: bool,
        debug_dir: str | None,
        logger: Logger,
    ) -> None:
        """Roda OCR em cada track do frame e atualiza o jersey_map."""
        target_color = None
        if target_signature and "_" in target_signature:
            try:
                target_color = target_signature.split("_")[1]
            except IndexError:
                pass

        proc_h = frame_orig.shape[0] / scale if scale else frame_orig.shape[0]

        for l, t, r, b, track_id in tracks:
            existing = jersey_map.get(str(track_id))
            if existing and existing.most_common(1)[0][1] >= MIN_OCR_VOTES:
                continue

            w_track = r - l
            h_track = b - t
            if not is_valid_player_detection((l, t, w_track, h_track), proc_h):
                continue

            bbox = (int(l * scale), int(t * scale), int(r * scale), int(b * scale))
            target_num_pass = target_number if target_number is not None else -1
            numbers = self.jersey_reader.read_from_bbox(frame_orig, bbox, target_num_pass)

            if not numbers:
                continue

            for n in numbers:
                if target_color and n == target_number:
                    crop = self.jersey_reader._torso_crop(frame_orig, *bbox)
                    hex_color = extract_core_color(crop, self.color_extractor)

                    if hex_color and color_distance(target_color, hex_color) < TRACKING_COLOR_TOLERANCE:
                        jersey_map[str(track_id)][target_signature] += 5
                    else:
                        jersey_map[str(track_id)][f"LIXO_{n}_{hex_color}"] += 1
                else:
                    jersey_map[str(track_id)][n] += 1

            if debug and debug_dir:
                self._save_debug_crop(frame_orig, bbox, frame_idx, track_id, numbers, debug_dir)
                logger.debug(f"  [MAP] frame={frame_idx} track={track_id} leu={numbers}")

    @staticmethod
    def _save_debug_crop(
        frame_orig: np.ndarray,
        bbox: tuple[int, int, int, int],
        frame_idx: int,
        track_id,
        numbers: list[int],
        debug_dir: str,
    ) -> None:
        """Salva crop do torso com nome indicativo do que foi lido."""
        x1, y1, x2, y2 = bbox
        h = y2 - y1
        fh, fw = frame_orig.shape[:2]
        crop = frame_orig[
            max(0, y1 + int(h * 0.15)): min(fh, y1 + int(h * 0.55)),
            max(0, x1): min(fw, x2),
        ]
        filename = f"ocr_f{frame_idx:05d}_t{track_id}_leu_{'_'.join(map(str, numbers))}.png"
        cv2.imwrite(os.path.join(debug_dir, filename), crop)
