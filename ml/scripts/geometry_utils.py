"""Funções geométricas puras usadas pelo VideoPipeline."""
import cv2
import numpy as np

from ml.scripts.config import (
    MAX_PLAYER_ASPECT_RATIO,
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
