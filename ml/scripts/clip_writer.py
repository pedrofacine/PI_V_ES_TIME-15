"""
Escrita de clipes de vídeo em disco.

Responsabilidade única: pegar uma lista de frames (numpy arrays)
e salvar como um arquivo MP4 com encoding H.264 via ffmpeg,
para garantir compatibilidade com navegadores.
"""
import os
import shutil
import subprocess
import cv2
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from ml.scripts.config import FFMPEG_CRF, FFMPEG_PRESET


class ClipWriter:
    """
    Escreve clipes de vídeo em MP4 com re-encode H.264.

    Usa um fluxo de duas etapas:
      1. Escreve MP4 temporário com OpenCV (codec mp4v, rápido mas com baixa compatibilidade)
      2. Re-encoda com ffmpeg para H.264 + faststart (compatível com browsers)

    Se o ffmpeg falhar, mantém o arquivo original do OpenCV como fallback.
    """

    def __init__(self, crf: int = FFMPEG_CRF, preset: str = FFMPEG_PRESET) -> None:
        self.crf = crf
        self.preset = preset
        self._ffmpeg_bin = get_ffmpeg_exe()

    def write(
        self,
        frames: list[np.ndarray],
        out_path: str,
        fps: float,
        size: tuple[int, int],
        source_video: str,  # NOVO: Necessário para extrair a trilha de áudio
        start_sec: float,   # NOVO: Necessário para sincronizar o corte do áudio
    ) -> None:
        """
        Salva uma lista de frames como arquivo MP4, injetando o áudio original.

        Args:
            frames: Lista de numpy arrays (BGR) representando os frames do clipe.
            out_path: Caminho completo do arquivo .mp4 de saída.
            fps: Taxa de quadros do clipe.
            size: Tupla (largura, altura) do clipe.
            source_video: Caminho completo do vídeo original (raw).
            start_sec: Tempo de início do clipe no vídeo original (em segundos).
        """
        if not frames:
            raise ValueError("Lista de frames vazia, nada a gravar.")

        # 1. Calculamos a duração exata do clipe para instruir o corte do FFmpeg
        duration = len(frames) / fps

        tmp_path = out_path.replace(".mp4", "_tmp.mp4")

        # Etapa 1: OpenCV grava MP4 temporário (gera a trilha de vídeo crua)
        self._write_with_opencv(frames, tmp_path, fps, size)

        # Etapa 2: FFmpeg encoda o vídeo para H.264 (web) e multiplexa o áudio
        try:
            self._reencode_with_ffmpeg(
                input_tmp_path=tmp_path, 
                output_path=out_path, 
                source_video=source_video, 
                start_sec=start_sec, 
                duration=duration
            )
            os.remove(tmp_path)
        except Exception as e:
            # Fallback: Se o FFmpeg falhar (ex: arquivo de áudio corrompido), 
            # devolvemos o arquivo mudo do OpenCV para não quebrar a pipeline.
            print(f"[warn] ffmpeg re-encode/audio multiplexing falhou ({e}), usando mp4v original sem áudio.")
            import shutil
            shutil.move(tmp_path, out_path)

    def _write_with_opencv(
        self,
        frames: list[np.ndarray],
        path: str,
        fps: float,
        size: tuple[int, int],
    ) -> None:
        """Grava um MP4 usando VideoWriter do OpenCV."""
        w, h = size
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(path, fourcc, fps, size)

        for frame in frames:
            # Redimensiona se o frame não bater com o tamanho declarado
            if frame.shape[1] != w or frame.shape[0] != h:
                frame = cv2.resize(frame, (w, h))
            out.write(frame)

        out.release()

    def _reencode_with_ffmpeg(
        self, input_tmp_path: str, output_path: str, source_video: str, start_sec: float, duration: float
    ) -> None:
        """Injeta a faixa de áudio do arquivo original em sync com o vídeo temporário."""
        subprocess.run(
            [
                self._ffmpeg_bin,
                "-y",
                "-i", input_tmp_path,             # Input 0: Vídeo das arrays OpenCV
                "-ss", str(start_sec),            # Ponto de início para cortar o áudio
                "-t", str(duration),              # Duração do clipe
                "-i", source_video,               # Input 1: Vídeo original (para pegar áudio)
                "-c:v", "libx264",                # Compressão H264 pro Browser
                "-preset", self.preset,
                "-crf", str(self.crf),
                "-c:a", "aac",                    # Encoding de áudio suportado web
                "-b:a", "128k",
                "-map", "0:v:0",                  # Usa o track de VÍDEO do input 0 (OpenCV)
                "-map", "1:a:0",                  # Usa o track de ÁUDIO do input 1 (Source)
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )