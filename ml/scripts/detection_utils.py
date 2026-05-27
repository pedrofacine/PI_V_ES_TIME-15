"""
Funções utilitárias puras para detecção e processamento de frames.

Extraídas de VideoPipeline para compartilhamento entre MetadataExtractor,
ClipExtractor e fast_scan — sem dependências circulares.
"""
from __future__ import annotations

import cv2
import numpy as np

from ml.scripts.config import (
    MAX_PLAYER_ASPECT_RATIO,
    PROCESS_WIDTH,
    SCOREBOARD_ZONE_BOTTOM,
    SCOREBOARD_ZONE_TOP,
    TORSO_Y_END,
    TORSO_Y_START,
)


def get_safe_fps(cap: cv2.VideoCapture) -> float:
    """Retorna FPS válido; fallback para 30 se fora da faixa [10, 120]."""
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps < 10 or fps > 120:
        return 30.0
    return fps


def color_distance(hex1: str, hex2: str) -> float:
    """Distância perceptual entre duas cores no espaço LAB (ΔE aproximado)."""
    def hex_to_lab(h: str) -> np.ndarray:
        h = h.lstrip('#')
        r, g, b = (int(h[i:i+2], 16) for i in (0, 2, 4))
        bgr = np.array([[[b, g, r]]], dtype=np.uint8)
        return cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)[0, 0].astype(float)

    try:
        return float(np.linalg.norm(hex_to_lab(hex1) - hex_to_lab(hex2)))
    except Exception:
        return 999.0


def is_valid_player_detection(bbox_xywh: tuple, frame_h: float) -> bool:
    """
    Retorna True se o bbox é geometricamente compatível com um jogador.

    Rejeita bboxes com aspect ratio horizontal (overlays, banners)
    e torsos que intersectam as dead zones de placar de transmissão.
    """
    x1, y1, w, h = bbox_xywh

    if h > 0 and (w / h) > MAX_PLAYER_ASPECT_RATIO:
        return False

    torso_y1 = y1 + h * TORSO_Y_START
    torso_y2 = y1 + h * TORSO_Y_END
    dead_top = frame_h * SCOREBOARD_ZONE_TOP
    dead_bottom = frame_h * (1 - SCOREBOARD_ZONE_BOTTOM)

    return not (torso_y1 < dead_top or torso_y2 > dead_bottom)


def resize_frame(frame: np.ndarray) -> np.ndarray:
    """Redimensiona frame para largura máxima PROCESS_WIDTH."""
    h, w = frame.shape[:2]
    if w > PROCESS_WIDTH:
        scale = PROCESS_WIDTH / w
        frame = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))
    return frame


def extract_core_color(torso_crop: np.ndarray, color_extractor) -> str | None:
    """Extrai a cor do miolo do torso, ignorando bordas e fundo."""
    if torso_crop.size == 0:
        return None

    h, w = torso_crop.shape[:2]
    cx, cy = w // 2, h // 2
    margin_w, margin_h = int(w * 0.2), int(h * 0.2)

    core_crop = torso_crop[
        max(0, cy - margin_h): min(h, cy + margin_h),
        max(0, cx - margin_w): min(w, cx + margin_w),
    ]

    target = core_crop if core_crop.size > 0 else torso_crop
    return color_extractor.get_dominant_color_hex(target)
