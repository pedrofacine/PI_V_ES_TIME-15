"""
Pipeline principal de análise de vídeo.

Responsabilidade: orquestrar todas as etapas do processamento de um vídeo,
desde a extração de metadados até a geração dos clipes finais.

Divide o fluxo em 4 passos bem definidos:
  1. Extração de metadados (YOLO + tracking + OCR)
  2. Resolução de identidades (cruza OCR + track_ids)
  3. Cálculo de intervalos temporais (onde o jogador aparece)
  4. Escrita dos clipes (fatia o vídeo original)
"""
import os
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from detector import YoloDetector
from scripts.ball_event_detector import BallEventDetector
from scripts.clip_writer import ClipWriter
from scripts.config import (
    CLIP_PADDING_SECONDS,
    FRAME_SKIP,
    GAP_TOLERANCE,
    MIN_CLIP_FRAMES,
    MIN_OCR_VOTES,
    OCR_INTERVAL,
    PROCESS_WIDTH,
    USE_GPU,
)
from scripts.jersey_reader import JerseyReader
from scripts.trackers.tracker import PlayerTracker


class VideoPipeline:
    """
    Orquestra o pipeline de análise de vídeo do início ao fim.

    Uso típico:
        pipeline = VideoPipeline()
        clips = pipeline.process(
            video_path="entrada.mp4",
            target_number=10,
            output_dir="saida/",
        )

    A classe é projetada para ser instanciada uma vez e reutilizada
    entre várias chamadas. Modelos pesados (YOLO, EasyOCR) são carregados
    no construtor e ficam disponíveis enquanto a instância viver.
    """

    def __init__(self) -> None:
        print(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

        # Componentes (carregados uma vez)
        self.detector = YoloDetector()
        self.jersey_reader = JerseyReader()
        self.ball_event_detector = BallEventDetector()
        self.clip_writer = ClipWriter()

        # Tracker é instanciado por vídeo (dentro de process)
        # porque mantém estado interno que não pode vazar entre execuções

    def process(
        self,
        video_path: str,
        target_number: int,
        output_dir: str,
        start_ts: int = 0,
        end_ts: int = 0,
        on_player_found: Callable | None = None,
        on_clip_generated: Callable | None = None,
        debug: bool = False,
    ) -> list[dict]:
        """
        Processa um vídeo e gera os clipes focados no jogador-alvo.

        Args:
            video_path: Caminho do vídeo de entrada.
            target_number: Número da camisa do jogador a rastrear.
            output_dir: Pasta onde os clipes serão salvos.
            start_ts: Segundo onde começar o processamento.
            end_ts: Segundo onde terminar (0 = até o fim).
            on_player_found: Callback chamado quando o jogador é identificado.
            on_clip_generated: Callback chamado a cada clipe gerado.
            debug: Se True, salva imagens de debug e loga detalhes.

        Returns:
            Lista de dicionários descrevendo os clipes gerados.
        """
        pipeline_start = time.time()
        os.makedirs(output_dir, exist_ok=True)
        debug_dir = self._setup_debug_dir(output_dir, debug)

        # Tracker novo a cada execução (estado limpo)
        tracker = PlayerTracker()

        # Abre vídeo e extrai metadados
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Falha ao abrir vídeo.")

        try:
            fps = self._get_safe_fps(cap)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            start_frame = int(start_ts * fps)
            end_frame = int(end_ts * fps) if end_ts > 0 else total_frames - 1

            # ============== PASSO 1 ==============
            video_metadata, jersey_map, max_frame = self._extract_metadata(
                cap=cap,
                tracker=tracker,
                start_frame=start_frame,
                end_frame=end_frame,
                total_frames=total_frames,
                target_number=target_number,
                debug=debug,
                debug_dir=debug_dir,
            )
        finally:
            cap.release()

        processed_total = max_frame + 1

        # ============== PASSO 2 ==============
        target_track_ids = self._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=target_number,
            debug=debug,
        )
        if on_player_found:
            on_player_found()

        # ============== PASSO 3 ==============
        target_frames, events, clip_intervals = self._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids=target_track_ids,
            start_frame=start_frame,
            processed_total=processed_total,
            fps=fps,
        )

        # ============== PASSO 4 ==============
        results = self._write_clips(
            video_path=video_path,
            clip_intervals=clip_intervals,
            events=events,
            target_number=target_number,
            output_dir=output_dir,
            fps=fps,
            total_frames=total_frames,
            on_clip_generated=on_clip_generated,
        )

        self._log_metrics(
            start_time=pipeline_start,
            processed_total=processed_total,
            start_frame=start_frame,
            num_clips=len(results),
        )

        return results

    # ======================================================
    # PASSO 1 — EXTRAÇÃO DE METADADOS
    # ======================================================
    def _extract_metadata(
        self,
        cap: cv2.VideoCapture,
        tracker: PlayerTracker,
        start_frame: int,
        end_frame: int,
        total_frames: int,
        target_number: int,
        debug: bool,
        debug_dir: str | None,
    ) -> tuple[dict, dict, int]:
        """
        Percorre o vídeo frame a frame extraindo detecções, tracking e OCR.

        Retorna:
          - video_metadata: {frame_idx: {"tracks": [...], "balls": [...]}}
          - jersey_map: {track_id: Counter({numero: votos})}
          - max_frame: maior frame_idx processado
        """
        print(f"[1/4] Extraindo metadados com IA ({total_frames} frames)...")
        print(f"[video] Começando no segundo {start_frame // max(1, int(cap.get(cv2.CAP_PROP_FPS)))} (frame {start_frame})")
        print(f"[video] Terminando no frame {end_frame}")

        video_metadata: dict[int, dict] = {}
        jersey_map: dict[str, Counter] = defaultdict(Counter)
        max_frame = start_frame - 1

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame

        while True:
            ret, frame_orig = cap.read()
            if not ret:
                break
            if frame_idx > end_frame:
                break

            max_frame = max(max_frame, frame_idx)

            # Skip de frames: copia metadata do frame anterior
            if frame_idx % FRAME_SKIP != 0:
                if frame_idx > start_frame and (frame_idx - 1) in video_metadata:
                    video_metadata[frame_idx] = video_metadata[frame_idx - 1]
                frame_idx += 1
                continue

            # Redimensiona para o YOLO
            frame = self._resize_frame(frame_orig)
            scale = frame_orig.shape[1] / frame.shape[1]

            # Detecção + Tracking
            detections, balls = self.detector.detect(frame)
            tracks = tracker.update(detections, frame)

            # Armazena metadata do frame
            video_metadata[frame_idx] = {
                "tracks": [
                    [float(l), float(t), float(r), float(b), str(tid)]
                    for l, t, r, b, tid in tracks
                ],
                "balls": [
                    [float(x1), float(y1), float(x2), float(y2)]
                    for x1, y1, x2, y2 in balls
                ],
            }

            # OCR em subconjunto de frames
            if frame_idx % OCR_INTERVAL == 0:
                self._run_ocr_on_tracks(
                    tracks=tracks,
                    frame_orig=frame_orig,
                    scale=scale,
                    target_number=target_number,
                    frame_idx=frame_idx,
                    jersey_map=jersey_map,
                    debug=debug,
                    debug_dir=debug_dir,
                )

            frame_idx += 1

        return video_metadata, jersey_map, max_frame

    def _run_ocr_on_tracks(
        self,
        tracks: list,
        frame_orig: np.ndarray,
        scale: float,
        target_number: int,
        frame_idx: int,
        jersey_map: dict,
        debug: bool,
        debug_dir: str | None,
    ) -> None:
        """Roda OCR em cada track do frame e atualiza o jersey_map."""
        for l, t, r, b, track_id in tracks:
            # Converte bbox para coordenadas da imagem original
            bbox = (
                int(l * scale),
                int(t * scale),
                int(r * scale),
                int(b * scale),
            )

            numbers = self.jersey_reader.read_from_bbox(
                frame_orig, bbox, target_number
            )

            if not numbers:
                continue

            for n in numbers:
                jersey_map[str(track_id)][n] += 1

            if debug and debug_dir:
                self._save_debug_crop(
                    frame_orig, bbox, frame_idx, track_id, numbers, debug_dir
                )
                print(f"  [MAP] frame={frame_idx} track={track_id} leu={numbers}")

    # ======================================================
    # PASSO 2 — RESOLUÇÃO DE IDs
    # ======================================================
    def _resolve_player_ids(
        self,
        jersey_map: dict,
        target_number: int,
        debug: bool,
    ) -> set[str]:
        """
        Cruza o jersey_map com o número-alvo para descobrir os track_ids
        que pertencem ao jogador procurado.

        Estratégia:
          1. Resolve cada track_id para seu número mais votado (com mínimo de votos)
          2. Seleciona os track_ids cujo número resolvido == target_number
          3. Fallback: se nada bater, aceita tracks cujo TOP número é o alvo
             (mesmo sem atingir MIN_OCR_VOTES)
        """
        print("[2/4] Resolvendo Identidades dos Jogadores...")

        resolved: dict[str, int] = {}
        for tid, counter in jersey_map.items():
            if not counter:
                continue
            best_num, votes = counter.most_common(1)[0]
            if votes >= MIN_OCR_VOTES:
                resolved[tid] = best_num

        if debug:
            detailed = {tid: dict(c) for tid, c in jersey_map.items() if c}
            print(f"  [MAP] Detalhado: {detailed}")
            print(f"  [MAP] Resolvido: {resolved}")

        target_track_ids = {
            tid for tid, num in resolved.items() if num == target_number
        }

        # Fallback: aceita tracks cujo top-number é o alvo, mesmo sem votos suficientes
        if not target_track_ids:
            for tid, counter in jersey_map.items():
                if counter and counter.most_common(1)[0][0] == target_number:
                    target_track_ids.add(tid)
                    resolved[tid] = target_number

        if not target_track_ids:
            all_nums = sorted(set(resolved.values())) if resolved else []
            raise ValueError(
                f"Jogador #{target_number} não encontrado. Identificados: {all_nums}"
            )

        print(f"    ✓ Jogador #{target_number} vinculado aos IDs: {target_track_ids}")
        return target_track_ids

    # ======================================================
    # PASSO 3 — LÓGICA TEMPORAL
    # ======================================================
    def _compute_clip_intervals(
        self,
        video_metadata: dict,
        target_track_ids: set[str],
        start_frame: int,
        processed_total: int,
        fps: float,
    ) -> tuple[list[int], list[dict], list[tuple[int, int]]]:
        """
        Calcula os intervalos (start_frame, end_frame) de cada clipe.

        Junta frames próximos (dentro de GAP_TOLERANCE) em um único clipe,
        descartando intervalos muito curtos (< MIN_CLIP_FRAMES).
        """
        print("[3/4] Calculando intervalos de ação...")

        # Coleta todos os frames em que o jogador aparece
        target_frames = sorted(
            f_idx
            for f_idx in range(start_frame, processed_total)
            if self._target_in_frame(video_metadata, f_idx, target_track_ids)
        )

        # Detecta eventos de interação com a bola
        events = self.ball_event_detector.detect(
            target_frames=target_frames,
            video_metadata=video_metadata,
            target_track_ids=target_track_ids,
            fps=fps,
        )
        print(f"    {len(events)} interações com a bola detectadas.")

        # Agrupa frames em intervalos contíguos
        clip_intervals = self._group_frames_into_intervals(target_frames)

        if not target_frames:
            print("    [!] O jogador não foi encontrado no vídeo.")
        else:
            print(f"    ✓ {len(clip_intervals)} blocos de ação encontrados (Modo Player Cam).")

        return target_frames, events, clip_intervals

    def _target_in_frame(
        self,
        video_metadata: dict,
        f_idx: int,
        target_track_ids: set[str],
    ) -> bool:
        """Verifica se algum dos track_ids alvo está presente neste frame."""
        frame_data = video_metadata.get(f_idx)
        if not frame_data:
            return False
        return any(
            str(tid) in target_track_ids
            for _, _, _, _, tid in frame_data["tracks"]
        )

    def _group_frames_into_intervals(
        self,
        target_frames: list[int],
    ) -> list[tuple[int, int]]:
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

    # ======================================================
    # PASSO 4 — ESCRITA DOS CLIPES
    # ======================================================
    def _write_clips(
        self,
        video_path: str,
        clip_intervals: list[tuple[int, int]],
        events: list[dict],
        target_number: int,
        output_dir: str,
        fps: float,
        total_frames: int,
        on_clip_generated: Callable | None,
    ) -> list[dict]:
        """Fatia o vídeo original em clipes aplicando padding temporal."""
        print(f"[4/4] Fatiando vídeo em {len(clip_intervals)} clipes...")

        results: list[dict] = []
        padding_frames = int(CLIP_PADDING_SECONDS * fps)

        cap = cv2.VideoCapture(video_path)
        try:
            for idx, (start_f, end_f) in enumerate(clip_intervals):
                clip_dict = self._extract_and_write_clip(
                    cap=cap,
                    clip_idx=idx,
                    start_f=start_f,
                    end_f=end_f,
                    padding_frames=padding_frames,
                    total_frames=total_frames,
                    fps=fps,
                    target_number=target_number,
                    output_dir=output_dir,
                    events=events,
                )
                if clip_dict:
                    results.append(clip_dict)
                    if on_clip_generated:
                        on_clip_generated(clip_dict)
        finally:
            cap.release()

        return results

    def _extract_and_write_clip(
        self,
        cap: cv2.VideoCapture,
        clip_idx: int,
        start_f: int,
        end_f: int,
        padding_frames: int,
        total_frames: int,
        fps: float,
        target_number: int,
        output_dir: str,
        events: list[dict],
    ) -> dict | None:
        """Extrai e salva um único clipe. Retorna None em caso de falha."""
        padded_start = max(0, start_f - padding_frames)
        padded_end = min(total_frames - 1, end_f + padding_frames)

        if padded_start >= total_frames:
            print(f"[ERRO] Frame fora do vídeo: {padded_start}")
            return None

        # Lê os frames do clipe
        cap.set(cv2.CAP_PROP_POS_FRAMES, padded_start)
        clip_frames: list[np.ndarray] = []
        num_frames = padded_end - padded_start + 1

        for _ in range(num_frames):
            ret, frame_orig = cap.read()
            if not ret:
                break
            clip_frames.append(self._resize_frame(frame_orig))

        if not clip_frames:
            print(f"[ERRO] Nenhum frame capturado para o clipe {clip_idx}")
            return None

        # Monta nome e path
        start_s = padded_start / fps
        end_s = padded_end / fps
        clip_name = (
            f"jogador_{target_number}_clipe_{clip_idx + 1}_"
            f"{int(start_s)}s_a_{int(end_s)}s.mp4"
        )
        clip_path = os.path.join(output_dir, clip_name)

        # Eventos que caem dentro desse clipe
        clip_events = [e for e in events if start_f <= e["frame"] <= end_f]

        # Escreve o arquivo
        h, w = clip_frames[0].shape[:2]
        self.clip_writer.write(clip_frames, clip_path, fps, (w, h))

        return {
            "path": clip_path,
            "start_ts": start_s,
            "end_ts": end_s,
            "events": clip_events,
        }

    # ======================================================
    # HELPERS
    # ======================================================
    @staticmethod
    def _resize_frame(frame: np.ndarray) -> np.ndarray:
        """Redimensiona o frame para largura máxima de PROCESS_WIDTH."""
        h, w = frame.shape[:2]
        if w > PROCESS_WIDTH:
            scale = PROCESS_WIDTH / w
            frame = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))
        return frame

    @staticmethod
    def _get_safe_fps(cap: cv2.VideoCapture) -> float:
        """Retorna FPS válido, com fallback para 30 se estiver fora da faixa esperada."""
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps < 10 or fps > 120:
            return 30.0
        return fps

    @staticmethod
    def _setup_debug_dir(output_dir: str, debug: bool) -> str | None:
        """Cria a pasta de debug se necessário."""
        if not debug:
            return None
        debug_dir = os.path.join(output_dir, "debug_ocr")
        os.makedirs(debug_dir, exist_ok=True)
        return debug_dir

    @staticmethod
    def _save_debug_crop(
        frame_orig: np.ndarray,
        bbox: tuple[int, int, int, int],
        frame_idx: int,
        track_id,
        numbers: list[int],
        debug_dir: str,
    ) -> None:
        """Salva crop do torso com nome indicativo do que foi lido."""
        x1, y1, x2, y2 = bbox
        # Re-crop para salvar (mesma região que foi para o OCR)
        h = y2 - y1
        fh, fw = frame_orig.shape[:2]
        # Aqui usamos valores fixos de torso, mas o ideal é delegar pro JerseyReader
        # (mantido assim por simplicidade, já que é só debug)
        crop = frame_orig[
            max(0, y1 + int(h * 0.15)):min(fh, y1 + int(h * 0.55)),
            max(0, x1):min(fw, x2),
        ]
        nums_str = "_".join(map(str, numbers))
        filename = f"ocr_f{frame_idx:05d}_t{track_id}_leu_{nums_str}.png"
        cv2.imwrite(os.path.join(debug_dir, filename), crop)

    def _log_metrics(
        self,
        start_time: float,
        processed_total: int,
        start_frame: int,
        num_clips: int,
    ) -> None:
        """Imprime métricas de performance no final da execução."""
        elapsed = time.time() - start_time
        print("\n[MÉTRICAS] Performance do Pipeline:")
        print(f"  -> Total de Frames Analisados: {processed_total - start_frame}")
        print(f"  -> Tempo Total de Execução: {elapsed:.2f}s ({elapsed / 60:.2f} min)")
        print(f"  -> Clipes Gerados: {num_clips}")
        print("[Concluído] Pipeline finalizado com sucesso.")