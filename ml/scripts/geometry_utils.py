"""Funções geométricas puras usadas pelo VideoPipeline."""
import logging

import cv2
import numpy as np

from ml.scripts.config import (
    GAP_TOLERANCE,
    MAX_PLAYER_ASPECT_RATIO,
    MIN_CLIP_FRAMES,
    TORSO_Y_START,
    TORSO_Y_END,
    SCOREBOARD_ZONE_TOP,
    SCOREBOARD_ZONE_BOTTOM,
)


def is_valid_player_detection(bbox_xywh: tuple, frame_h: float) -> bool:
    """
    Retorna True se o bbox é geometricamente compatível com um jogador.

    Rejeita:
    - Aspect ratio horizontal demais (bboxes panorâmicas do tracker ou overlays)
    - Torso crop que intersecta dead zones de overlay de transmissão (topo/base)
    """
    x1, y1, w, h = bbox_xywh

    if h > 0 and (w / h) > MAX_PLAYER_ASPECT_RATIO:
        return False

    torso_y1 = y1 + h * TORSO_Y_START
    torso_y2 = y1 + h * TORSO_Y_END

    dead_top    = frame_h * SCOREBOARD_ZONE_TOP
    dead_bottom = frame_h * (1 - SCOREBOARD_ZONE_BOTTOM)

    if torso_y1 < dead_top:
        return False
    if torso_y2 > dead_bottom:
        return False

    return True


def extract_core_color(torso_crop: np.ndarray) -> str | None:
    """Extrai a cor média da parte superior do torso (ombros/peito).

    Usar a média de todos os pixels da região, em vez de uma amostra pontual,
    evita leitura incorreta em camisas bicolores ou divididas, cuja cor varia
    conforme o ponto do recorte amostrado."""
    if torso_crop.size == 0:
        return None

    h, w = torso_crop.shape[:2]

    # Foca apenas nos 40% superiores da imagem (peito para cima)
    margem_lateral = int(w * 0.15)
    altura_ombros = int(h * 0.40)

    shoulders_crop = torso_crop[
        0 : max(1, altura_ombros),
        margem_lateral : max(margem_lateral + 1, w - margem_lateral)
    ]

    # Fallback de segurança
    if shoulders_crop.size == 0:
        shoulders_crop = torso_crop

    mean_bgr = cv2.mean(shoulders_crop)[:3]

    # Converte o BGR médio para código hexadecimal
    hex_color = '#%02x%02x%02x' % (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))
    return hex_color


def color_distance(hex1: str, hex2: str, logger: logging.Logger | None = None) -> float:
    """Calcula a distância perceptual entre duas cores usando o espaço LAB (visão humana)."""
    def hex_to_lab(h: str) -> np.ndarray:
        h = h.lstrip('#')
        b, g, r = tuple(int(h[i:i+2], 16) for i in (4, 2, 0))
        pixel_bgr = np.array([[[b, g, r]]], dtype=np.uint8)
        pixel_lab = cv2.cvtColor(pixel_bgr, cv2.COLOR_BGR2LAB)
        return pixel_lab[0][0].astype(float)

    try:
        lab1 = hex_to_lab(hex1)
        lab2 = hex_to_lab(hex2)
        return float(np.linalg.norm(lab1 - lab2))
    except Exception:
        if logger:
            logger.warning(f"Falha ao calcular cor entre {hex1} e {hex2}")
        return 999.0  # Em caso de erro de parsing, assume que são muito diferentes


def target_in_frame(video_metadata: dict, f_idx: int, target_track_ids: set[str]) -> bool:
    """Verifica se algum dos track_ids alvo está presente neste frame."""
    frame_data = video_metadata.get(f_idx)
    if not frame_data:
        return False
    return any(
        str(tid) in target_track_ids
        for _, _, _, _, tid in frame_data["tracks"]
    )


def group_frames_into_intervals(target_frames: list[int]) -> list[tuple[int, int]]:
    """
    Agrupa uma lista ordenada de frames em intervalos contíguos.

    Frames com gap <= GAP_TOLERANCE são considerados do mesmo intervalo.
    Intervalos menores que MIN_CLIP_FRAMES são descartados.
    """
    if not target_frames:
        return []

    intervals: list[tuple[int, int]] = []
    current_start = target_frames[0]
    current_end = target_frames[0]

    for f in target_frames[1:]:
        if f - current_end <= GAP_TOLERANCE:
            current_end = f
        else:
            if (current_end - current_start) >= MIN_CLIP_FRAMES:
                intervals.append((current_start, current_end))
            current_start = f
            current_end = f

    # Fecha o último intervalo
    if (current_end - current_start) >= MIN_CLIP_FRAMES:
        intervals.append((current_start, current_end))

    return intervals
