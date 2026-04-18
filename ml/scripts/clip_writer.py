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

from scripts.config import FFMPEG_CRF, FFMPEG_PRESET


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
    ) -> None:
        """
        Salva uma lista de frames como arquivo MP4.

        Args:
            frames: Lista de numpy arrays (BGR) representando os frames do clipe.
            out_path: Caminho completo do arquivo .mp4 de saída.
            fps: Taxa de quadros do clipe.
            size: Tupla (largura, altura) do clipe. Frames fora desse tamanho
                  serão redimensionados.
        """
        if not frames:
            raise ValueError("Lista de frames vazia, nada a gravar.")

        tmp_path = out_path.replace(".mp4", "_tmp.mp4")

        # Etapa 1: OpenCV grava MP4 temporário
        self._write_with_opencv(frames, tmp_path, fps, size)

        # Etapa 2: ffmpeg re-encoda para H.264
        try:
            self._reencode_with_ffmpeg(tmp_path, out_path)
            os.remove(tmp_path)
        except Exception as e:
            print(f"[warn] ffmpeg re-encode falhou ({e}), usando mp4v original.")
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

    def _reencode_with_ffmpeg(self, input_path: str, output_path: str) -> None:
        """Re-encoda o arquivo com ffmpeg para H.264 + faststart."""
        subprocess.run(
            [
                self._ffmpeg_bin,
                "-y",
                "-i", input_path,
                "-c:v", "libx264",
                "-preset", self.preset,
                "-crf", str(self.crf),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-an",  # sem áudio
                output_path,
            ],
            check=True,
            capture_output=True,
        )