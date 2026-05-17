import cv2
import numpy as np
from ultralytics import YOLO
import logging

# Certifique-se de adicionar NUMBER_MODEL_PATH no seu ml.scripts.config!
from ml.scripts.config import (
    MIN_CROP_H,
    MIN_CROP_W,
    OCR_MIN_CONFIDENCE,
    TORSO_Y_END,
    TORSO_Y_START,
    USE_GPU,
    NUMBER_MODEL_PATH # <-- O caminho para o seu best.pt
)

_logger = logging.getLogger(__name__)

class JerseyReader:
    """
    Leitor de número de camisa baseado no modelo YOLO customizado (best.pt).

    Estratégia atual: crop do torso -> YOLO Especialista em Números -> 
    Ordenação Esquerda-Direita -> Filtro de confiança.
    """

    def __init__(
        self,
        model_path = NUMBER_MODEL_PATH,
        min_confidence: float = OCR_MIN_CONFIDENCE,
        torso_y_start: float = TORSO_Y_START,
        torso_y_end: float = TORSO_Y_END,
        use_gpu: bool = USE_GPU,
    ) -> None:
        self.min_confidence = min_confidence
        self.torso_y_start = torso_y_start
        self.torso_y_end = torso_y_end
        self.use_gpu = use_gpu

        # 1. Carrega o nosso YOLO treinado para números (1 única vez)
        self.model = YOLO(model_path)
        _logger.info(f"[JerseyReader] Modelo Especialista carregado: {model_path}")

    def read_from_bbox(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        target_number: int,
    ) -> list[int]:
        
        x1, y1, x2, y2 = bbox
        
        # Mantemos a sua excelente lógica de focar apenas no torso
        crop = self._torso_crop(frame, x1, y1, x2, y2)

        # Filtro de tamanho para evitar processar ruído
        if crop.shape[0] < MIN_CROP_H or crop.shape[1] < MIN_CROP_W:
            return []

        return self._read_numbers(crop, target_number)
    
    def read_batch(self, crops: list[np.ndarray], target_number: int) -> list[list[int]]:
        """
        [NOVO] Otimização: Processa múltiplos recortes de uma só vez na GPU!
        Retorna uma lista contendo as leituras de cada recorte.
        """
        if not crops:
            return []

        # O YOLO aceita nativamente uma lista de imagens!
        results = self.model(crops, verbose=False, conf=self.min_confidence, half=self.use_gpu)

        batch_numbers = []
        for res in results:
            boxes = res.boxes
            if boxes is None or len(boxes) == 0:
                batch_numbers.append([])
                continue

            digits = []
            for box in boxes:
                x_min = float(box.xyxy[0][0])
                cls_id = int(box.cls[0])
                digits.append((x_min, cls_id))

            if not digits:
                batch_numbers.append([])
                continue

            # Ordena da esquerda para a direita
            digits.sort(key=lambda d: d[0])
            number_str = "".join(str(d[1]) for d in digits)
            value = int(number_str)

            if value == 0 and target_number != 0:
                batch_numbers.append([])
            else:
                batch_numbers.append([value])

        return batch_numbers

    def _torso_crop(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> np.ndarray:
        h = y2 - y1
        torso_y1 = y1 + int(h * self.torso_y_start)
        torso_y2 = y1 + int(h * self.torso_y_end)

        fh, fw = frame.shape[:2]
        return frame[
            max(0, torso_y1):min(fh, torso_y2),
            max(0, x1):min(fw, x2),
        ]

    def _read_numbers(self, crop: np.ndarray, target_number: int) -> list[int]:
        """
        Executa o YOLO no recorte e ordena os dígitos da esquerda para a direita.
        """
        # 2. Inferência direta! Sem grayscale, sem upscale, o YOLO cuida disso.
        # Passamos conf e half para otimizar velocidade se estiver usando GPU.
        results = self.model(crop, verbose=False, conf=self.min_confidence, half=self.use_gpu)

        boxes = results[0].boxes
        if boxes is None or len(boxes) == 0:
            return []

        digits = []
        
        # 3. Extrai cada dígito detectado
        for box in boxes:
            # Pega a coordenada X inicial da caixinha do número (para sabermos quem vem antes)
            x_min = float(box.xyxy[0][0]) 
            
            # Pega o ID da classe (Como treinamos de 0 a 9, o ID é o próprio dígito)
            cls_id = int(box.cls[0])      
            
            digits.append((x_min, cls_id))

        if not digits:
            return []

        # 4. A MÁGICA: Ordena da esquerda para a direita com base no X
        digits.sort(key=lambda d: d[0])

        # 5. Concatena (Ex: Lê "1" e "0" -> Transforma na string "10" -> Converte para Int 10)
        number_str = "".join(str(d[1]) for d in digits)
        value = int(number_str)

        # 6. Mantemos a sua heurística de segurança para falsos positivos do 0
        if value == 0 and target_number != 0:
            return []

        return [value]