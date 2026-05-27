"""
Ports (interfaces) do pipeline de análise de vídeo.

Seguindo Arquitetura Hexagonal (Ports & Adapters), cada Protocol define
o contrato que o pipeline exige de seus componentes externos. As classes
concretas (YoloDetector, JerseyReader, etc.) são os adaptadores que
implementam esses contratos.

Princípios aplicados
--------------------
DIP — VideoPipeline depende destes Protocols, não das implementações concretas.
ISP — Cada porta é estreita e coesa: nenhuma classe precisa implementar
      mais do que o pipeline realmente usa.
OCP — Novos detectores ou leitores são adicionados implementando um Protocol,
      sem modificar o pipeline principal.
LSP — Qualquer classe que satisfaça um Protocol é substituível por outra
      sem que o pipeline perceba a diferença.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class PlayerDetectorPort(Protocol):
    """
    Strategy de detecção de jogadores em frames de vídeo.

    Implementações concretas: YoloDetector (yolov8s.pt, best.pt).
    Exemplos de extensão: detectores baseados em outros frameworks
    (DETR, RT-DETR) ou stubs de teste.
    """

    def detect(self, frame: np.ndarray) -> tuple[list, list]: ...


@runtime_checkable
class BallDetectorPort(Protocol):
    """
    Strategy de detecção da bola em frames de vídeo.

    Implementações concretas: BallDetector (ball_tracker.pt).
    """

    def detect(self, frame: np.ndarray) -> list: ...


@runtime_checkable
class JerseyReaderPort(Protocol):
    """
    Leitura do número da camisa via OCR.

    Implementações concretas: JerseyReader (EasyOCR).
    """

    def read_from_bbox(
        self,
        frame: np.ndarray,
        bbox: tuple[int, int, int, int],
        target_number: int,
    ) -> list[int]: ...

    def _torso_crop(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
    ) -> np.ndarray: ...


@runtime_checkable
class ClipWriterPort(Protocol):
    """
    Escrita de sequências de frames em arquivo de vídeo.

    Implementações concretas: ClipWriter (ffmpeg via cv2).
    """

    def write(
        self,
        frames: list[np.ndarray],
        path: str,
        fps: float,
        size: tuple[int, int],
    ) -> None: ...


@runtime_checkable
class ColorExtractorPort(Protocol):
    """
    Extração da cor dominante de uma região de imagem.

    Implementações concretas: ColorExtractor (k-means / histograma).
    """

    def get_dominant_color_hex(self, image: np.ndarray) -> str | None: ...


@runtime_checkable
class KinematicAnalyzerPort(Protocol):
    """
    Análise cinemática de trajetórias de jogadores e bola.

    Implementações concretas: KinematicAnalyzer.
    """

    def analyze(self, video_metadata: dict, fps: float) -> list[dict]: ...


@runtime_checkable
class BallEventDetectorPort(Protocol):
    """
    Detecção de eventos de interação entre jogador e bola.

    Implementações concretas: BallEventDetector.
    """

    def detect(
        self,
        target_frames: list[int],
        video_metadata: dict,
        target_track_ids: set[str],
        fps: float,
    ) -> list[dict]: ...
