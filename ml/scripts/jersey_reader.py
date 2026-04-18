"""
Leitura do número da camisa via OCR.

Responsabilidade única: dado um bounding box de jogador, extrair
a região do torso, pré-processar a imagem e retornar os números
lidos com alta confiança.

Esta classe é o ponto de extensão principal para melhorar a precisão
do pipeline: trocar EasyOCR por CNN própria, PaddleOCR, ou adicionar
estratégias múltiplas de binarização envolve apenas modificar esta classe.
"""
import cv2
import easyocr
import numpy as np

from scripts.config import (
    MIN_CROP_H,
    MIN_CROP_W,
    OCR_MIN_CONFIDENCE,
    OCR_UPSCALE_FACTOR,
    TORSO_Y_END,
    TORSO_Y_START,
    USE_GPU,
)


class JerseyReader:
    """
    Leitor de número de camisa baseado em EasyOCR.

    Estratégia atual: crop do torso → upscale → grayscale →
    Gaussian Blur → CLAHE → EasyOCR com filtro de confiança.

    A classe mantém o reader do EasyOCR como atributo para evitar
    recarregar os pesos em cada chamada (o carregamento leva ~5s).
    """

    def __init__(
        self,
        min_confidence: float = OCR_MIN_CONFIDENCE,
        upscale_factor: int = OCR_UPSCALE_FACTOR,
        torso_y_start: float = TORSO_Y_START,
        torso_y_end: float = TORSO_Y_END,
        use_gpu: bool = USE_GPU,
    ) -> None:
        self.min_confidence = min_confidence
        self.upscale_factor = upscale_factor
        self.torso_y_start = torso_y_start
        self.torso_y_end = torso_y_end

        # Carrega o reader do EasyOCR apenas uma vez
        self._reader = easyocr.Reader(["en"], gpu=use_gpu)

        # CLAHE pode ser criado uma vez e reutilizado
        self._clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))

    def read_from_bbox(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        target_number: int,
    ) -> list[int]:
        """
        Lê número(s) da camisa a partir do bbox de um jogador no frame.

        Args:
            frame: Imagem completa (BGR) de onde extrair o crop.
            bbox: Bounding box (x1, y1, x2, y2) do jogador.
            target_number: Número que o usuário está procurando. Usado
                           para relaxar a heurística de tamanho quando
                           a leitura bate com o alvo.

        Returns:
            Lista de inteiros com os números lidos (normalmente 0, 1 ou 2 elementos).
        """
        x1, y1, x2, y2 = bbox
        crop = self._torso_crop(frame, x1, y1, x2, y2)

        if crop.shape[0] < MIN_CROP_H or crop.shape[1] < MIN_CROP_W:
            return []

        return self._read_numbers(crop, target_number)

    def _torso_crop(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> np.ndarray:
        """
        Recorta a região do torso, onde normalmente fica o número da camisa.

        A região é definida como uma faixa vertical do bbox, do
        torso_y_start ao torso_y_end (frações da altura do bbox).
        """
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
        Executa OCR no crop já recortado e retorna os números lidos.

        Pipeline de pré-processamento:
          1. Upscale (CUBIC) para aumentar resolução
          2. Grayscale
          3. Gaussian Blur para reduzir ruído em rugas/dobras
          4. CLAHE para melhorar contraste local
          5. EasyOCR com allowlist apenas de dígitos
          6. Filtros de confiança e heurística de tamanho
        """
        h, w = crop.shape[:2]
        if h < 5 or w < 5:
            return []

        # 1. Upscale
        upscaled = cv2.resize(
            crop,
            (w * self.upscale_factor, h * self.upscale_factor),
            interpolation=cv2.INTER_CUBIC,
        )

        # 2-4. Pré-processamento para OCR
        enhanced = self._preprocess_for_ocr(upscaled)

        # 5. OCR
        detections = self._reader.readtext(
            enhanced,
            allowlist="0123456789",
            detail=1,  # retorna (bbox, texto, confiança)
        )

        # 6. Filtros de confiança e heurística
        return self._filter_detections(detections, target_number)

    def _preprocess_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """Aplica grayscale + Gaussian Blur + CLAHE na imagem."""
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        return self._clahe.apply(blur)

    def _filter_detections(
        self,
        detections: list,
        target_number: int,
    ) -> list[int]:
        """
        Filtra as detecções do EasyOCR aplicando regras de qualidade.

        Regras:
          - Ignora leituras com confiança abaixo do threshold
          - Ignora leitura "0" quando o target não é 0 (comum falso positivo)
          - Mantém apenas números de 1-2 dígitos, ou qualquer tamanho se bater com target
        """
        results: set[int] = set()

        for _, text, prob in detections:
            try:
                confidence = float(prob)
            except (ValueError, TypeError):
                continue

            if confidence < self.min_confidence:
                continue

            text = str(text).strip()
            if not text.isdigit():
                continue

            value = int(text)

            # "0" sozinho é quase sempre falso positivo
            if value == 0 and target_number != 0:
                continue

            # Aceita 1-2 dígitos, ou qualquer tamanho se for o target
            if 1 <= len(text) <= 2 or value == target_number:
                results.add(value)

        return list(results)