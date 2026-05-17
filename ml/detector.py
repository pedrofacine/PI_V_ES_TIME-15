from pathlib import Path
from typing import Union
import numpy as np
import logging
from ultralytics import YOLO

from ml.scripts.config import (
    BALL_MODEL_PATH,
    COCO_BALL_CLS,
    COCO_PERSON_CLS,
    DEFAULT_MODEL_PATH,
    MIN_PLAYER_H,
    MIN_PLAYER_W,
    USE_GPU,
    YOLO_MIN_CONF,
)

_logger = logging.getLogger(__name__)

# ==========================================================
# 1. CLASSE BASE (Unifica tudo o que é repetido)
# ==========================================================
class BaseYoloDetector:
    """Classe base que contém a lógica comum para rodar modelos YOLO."""
    
    def __init__(self, model_path: Union[str, Path], min_conf: float, use_gpu: bool):
        self.model_path = str(model_path)
        self.min_conf = min_conf
        self.use_gpu = use_gpu
        self.model = YOLO(self.model_path)

    def _run_inference(self, frame: np.ndarray, classes: list[int]):
        """Roda o YOLO já filtrando as classes direto na GPU (Otimização)"""
        return self.model(
            frame,
            classes=classes, 
            verbose=False,
            conf=self.min_conf,
            half=self.use_gpu,
            device=0 if self.use_gpu else 'cpu' # Garante o uso explícito da GPU
        )

# ==========================================================
# 2. DETECTOR DE JOGADORES (E BOLA FALLBACK)
# ==========================================================
class YoloDetector(BaseYoloDetector):
    PLAYER_KEYWORDS = ("player", "person", "goalkeeper")
    BALL_KEYWORDS = ("ball", "sports ball", "soccer ball", "football")

    def __init__(
        self,
        model_path: Union[str, Path] = DEFAULT_MODEL_PATH,
        min_conf: float = YOLO_MIN_CONF,
        min_player_w: int = MIN_PLAYER_W,
        min_player_h: int = MIN_PLAYER_H,
        use_gpu: bool = USE_GPU,
    ) -> None:
        super().__init__(model_path, min_conf, use_gpu)
        self.min_player_w = min_player_w
        self.min_player_h = min_player_h

        self.player_classes, self.ball_class = self._discover_class_ids()
        self.yolo_classes = self.player_classes + [self.ball_class]
        
        self._log_init()

    def detect(self, frame: np.ndarray) -> tuple[list, list]:
        results = self._run_inference(frame, self.yolo_classes)
        return self._parse_detections(results)

    def _discover_class_ids(self) -> tuple[list[int], int]:
        player_classes, ball_class = [], None
        for class_id, class_name in self.model.names.items():
            name_lower = class_name.lower()
            if any(k in name_lower for k in self.PLAYER_KEYWORDS):
                player_classes.append(class_id)
            elif any(k in name_lower for k in self.BALL_KEYWORDS):
                ball_class = class_id

        if not player_classes: player_classes = list(COCO_PERSON_CLS)
        if ball_class is None: ball_class = COCO_BALL_CLS
        return player_classes, ball_class

    def _parse_detections(self, results) -> tuple[list, list]:
        detections, balls = [], []
        boxes = results[0].boxes
        if not boxes: return detections, balls

        for box, cls, conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
            cls_i, conf_f = int(cls), float(conf)
            x1, y1, x2, y2 = map(float, box)
            
            if cls_i in self.player_classes:
                w, h = x2 - x1, y2 - y1
                if w >= self.min_player_w and h >= self.min_player_h:
                    detections.append([[x1, y1, w, h], conf_f, cls_i])
            elif cls_i == self.ball_class:
                balls.append([x1, y1, x2, y2])

        return detections, balls

    def _log_init(self) -> None:
        _logger.info(f"[YoloDetector] Modelo: {self.model_path}")
        _logger.info(f"[YoloDetector] player_ids={self.player_classes} ball_id={self.ball_class}")

# ==========================================================
# 3. DETECTOR ESPECIALISTA DA BOLA (Herdando da base limpa)
# ==========================================================
class BallDetector(BaseYoloDetector):
    BALL_KEYWORDS = ("ball", "sports ball", "soccer ball", "football")

    def __init__(
        self,
        model_path: Union[str, Path] = BALL_MODEL_PATH,
        min_conf: float = YOLO_MIN_CONF,
        use_gpu: bool = USE_GPU,
    ) -> None:
        super().__init__(model_path, min_conf, use_gpu)
        self.ball_class = self._discover_ball_class()
        self._log_init()

    def detect(self, frame: np.ndarray) -> list[list[float]]:
        # CORREÇÃO CRÍTICA: Agora passamos a classe correta para a GPU não fazer trabalho extra
        results = self._run_inference(frame, [self.ball_class])
        
        balls = []
        boxes = results[0].boxes
        if not boxes: return balls

        for box in boxes.xyxy:
            balls.append(list(map(float, box)))
        return balls

    def _discover_ball_class(self) -> int:
        for class_id, class_name in self.model.names.items():
            if any(k in class_name.lower() for k in self.BALL_KEYWORDS):
                return class_id
        return COCO_BALL_CLS

    def _log_init(self) -> None:
        _logger.info(f"[BallDetector] Modelo: {self.model_path} | ball_id={self.ball_class}")