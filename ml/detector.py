"""
Detecção de jogadores e bola usando YOLO (Ultralytics).

Responsabilidade única: encapsular o modelo YOLO, descobrir quais
classes representam jogadores e bola, e retornar as detecções filtradas
por confiança e tamanho mínimo.

Esta classe é o ponto de extensão para trocar de modelo: se no futuro
o projeto treinar um YOLO customizado, basta alterar o caminho em config.py
ou passar model_path no construtor.
"""
from pathlib import Path
from typing import Union

import numpy as np
from ultralytics import YOLO

from ml.scripts.config import (
    COCO_BALL_CLS,
    COCO_PERSON_CLS,
    DEFAULT_MODEL_PATH,
    MIN_PLAYER_H,
    MIN_PLAYER_W,
    USE_GPU,
    YOLO_MIN_CONF,
)


class YoloDetector:
    """
    Detector de jogadores e bola baseado em YOLO.

    Faz auto-descoberta das classes relevantes no modelo carregado:
    se o modelo foi treinado especificamente para futebol (classes como
    'player', 'goalkeeper', 'ball'), ele identifica os IDs corretos.
    Se for o modelo COCO padrão (class 0 = person, 32 = sports ball),
    usa esses IDs como fallback.

    Uso típico:
        detector = YoloDetector()
        players, balls = detector.detect(frame)
    """

    # Palavras-chave para identificar classes no modelo carregado
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
        self.model_path = str(model_path)
        self.min_conf = min_conf
        self.min_player_w = min_player_w
        self.min_player_h = min_player_h
        self.use_gpu = use_gpu

        # Carrega o modelo
        self.model = YOLO(self.model_path)

        # Descobre IDs de classes de interesse
        self.player_classes, self.ball_class = self._discover_class_ids()
        self.yolo_classes = self.player_classes + [self.ball_class]

        self._log_init()

    def detect(self, frame: np.ndarray) -> tuple[list, list]:
        """
        Roda detecção em um frame e retorna jogadores e bolas separados.

        Args:
            frame: Imagem BGR em formato numpy.

        Returns:
            Tupla (detections, balls), onde:
              - detections: lista no formato esperado pelo DeepSORT:
                  [ [x, y, w, h], confidence, class_id ]
              - balls: lista de bboxes no formato [x1, y1, x2, y2]
        """
        results = self.model(
            frame,
            classes=self.yolo_classes,
            verbose=False,
            conf=self.min_conf,
            half=self.use_gpu,
        )
        return self._parse_detections(results)

    def _discover_class_ids(self) -> tuple[list[int], int]:
        """
        Identifica IDs de classes de jogador e bola no modelo carregado.

        Vasculha o dicionário `model.names` procurando por keywords.
        Usa fallback COCO se não achar nada (útil para yolov8s.pt padrão).
        """
        player_classes: list[int] = []
        ball_class: int | None = None

        for class_id, class_name in self.model.names.items():
            name_lower = class_name.lower()

            if any(keyword in name_lower for keyword in self.PLAYER_KEYWORDS):
                player_classes.append(class_id)
            elif any(keyword in name_lower for keyword in self.BALL_KEYWORDS):
                ball_class = class_id

        # Fallback para COCO se não achou nada
        if not player_classes:
            player_classes = list(COCO_PERSON_CLS)
        if ball_class is None:
            ball_class = COCO_BALL_CLS

        return player_classes, ball_class

    def _parse_detections(self, results) -> tuple[list, list]:
        """
        Separa resultados do YOLO em detecções de jogadores e bolas.

        Aplica filtros de confiança mínima e tamanho mínimo de bbox
        para jogadores. Bolas não têm filtro de tamanho.
        """
        detections: list = []
        balls: list = []

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return detections, balls

        for box, cls, conf in zip(boxes.xyxy, boxes.cls, boxes.conf):
            cls_i = int(cls)
            conf_f = float(conf)

            if conf_f < self.min_conf:
                continue

            x1, y1, x2, y2 = map(float, box)
            w = x2 - x1
            h = y2 - y1

            if cls_i in self.player_classes:
                # Filtra bboxes muito pequenos de jogador (ruído)
                if w >= self.min_player_w and h >= self.min_player_h:
                    # Formato esperado pelo DeepSORT: [[x, y, w, h], conf, cls]
                    detections.append([[x1, y1, w, h], conf_f, cls_i])
            elif cls_i == self.ball_class:
                balls.append([x1, y1, x2, y2])

        return detections, balls

    def _log_init(self) -> None:
        """Registra no log o modelo e classes descobertas."""
        print(f"[YoloDetector] Modelo: {self.model_path}")
        print(f"[YoloDetector] Classes: {self.model.names}")
        print(
            f"[YoloDetector] player_ids={self.player_classes} "
            f"ball_id={self.ball_class}"
        )