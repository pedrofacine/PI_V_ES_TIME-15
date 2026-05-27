"""
Pipeline principal de análise de vídeo.

Responsabilidade: orquestrar todas as etapas do processamento de um vídeo,
desde a extração de metadados até a geração dos clipes finais.

Padrões arquiteturais aplicados
--------------------------------
Facade (GoF Estrutural)
    `VideoPipeline` é a fachada sobre um sistema composto por múltiplos
    subsistemas independentes. Clientes interagem apenas com `process` e
    `fast_scan`.

Template Method (GoF Comportamental)
    `process` define o esqueleto fixo em 4 passos; cada passo é delegado a
    um componente especializado (MetadataExtractor, ClipExtractor).

Strategy (GoF Comportamental)
    Cada componente é tipado via Protocol (porta), tornando as implementações
    concretas intercambiáveis — ver `ml.scripts.ports`.

Observer (GoF Comportamental)
    Eventos do ciclo de vida são notificados via `PipelineObserver`,
    desacoplando o pipeline dos consumidores — ver `ml.scripts.pipeline_observer`.

Factory Method (GoF Criacional)
    `VideoPipeline.build()` centraliza a criação de instâncias configuradas.

Princípios SOLID
----------------
S — MetadataExtractor e ClipExtractor têm responsabilidades únicas e módulos
    próprios; VideoPipeline apenas orquestra.
O — Novos detectores são adicionados implementando um Protocol, sem modificar
    o pipeline.
L — Qualquer implementação de PlayerDetectorPort é substituível sem efeitos.
I — Sete Protocols estreitos substituem uma ABC monolítica.
D — `__init__` depende dos Protocols; implementações concretas são injetadas.

Atributos de qualidade (ISO/IEC 25010:2023)
-------------------------------------------
Testabilidade    — DIP permite substituição de todos os componentes em testes.
Manutenibilidade — Cada etapa do pipeline tem módulo dedicado (<150 linhas).
Extensibilidade  — OCP via Protocols: novos modelos sem modificar o pipeline.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable
import uuid
import logging

import cv2
import numpy as np

from ml.detector import BallDetector, YoloDetector
from ml.scripts.ball_event_detector import BallEventDetector
from ml.scripts.clip_writer import ClipWriter
from ml.scripts.config import (
    FAST_SCAN_COLOR_TOLERANCE,
    FRAME_SKIP,
    GAP_TOLERANCE,
    MIN_CLIP_FRAMES,
    MIN_OCR_VOTES,
    MAX_DISTINCT_READINGS,
    PROCESS_WIDTH,
    USE_GPU,
    setup_pipeline_logger,
)
from ml.scripts.kinematic_analyzer import KinematicAnalyzer
from ml.scripts.jersey_reader import JerseyReader
from ml.scripts.trackers.ball_tracker import BallTracker
from ml.scripts.trackers.tracker import PlayerTracker
from ml.scripts.color_extractor import ColorExtractor
from ml.scripts.ports import (
    BallDetectorPort,
    BallEventDetectorPort,
    ClipWriterPort,
    ColorExtractorPort,
    JerseyReaderPort,
    KinematicAnalyzerPort,
    PlayerDetectorPort,
)
from ml.scripts.pipeline_observer import PipelineObserver, make_observer
from ml.scripts.detection_utils import (
    color_distance as _color_distance_fn,
    is_valid_player_detection as _is_valid_player_detection_fn,
    get_safe_fps as _get_safe_fps_fn,
    resize_frame as _resize_frame_fn,
    extract_core_color as _extract_core_color_fn,
)
from ml.scripts.metadata_extractor import MetadataExtractor
from ml.scripts.clip_extractor import ClipExtractor


class VideoPipeline:
    """
    Facade sobre o pipeline de análise de vídeo (GoF Estrutural).

    Expõe dois pontos de entrada públicos:
      - `process`:   análise completa e geração de clipes.
      - `fast_scan`: varredura expressa de candidatos.

    Thread-safety
    -------------
    O estado mutável de execução (logger, session_id) fica em
    `threading.local()` para evitar race conditions no singleton.
    """

    def __init__(
        self,
        *,
        detector: PlayerDetectorPort | None = None,
        ball_detector: BallDetectorPort | None = None,
        jersey_reader: JerseyReaderPort | None = None,
        ball_event_detector: BallEventDetectorPort | None = None,
        kinematic_analyzer: KinematicAnalyzerPort | None = None,
        clip_writer: ClipWriterPort | None = None,
        color_extractor: ColorExtractorPort | None = None,
    ) -> None:
        init_logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

        self._tl = threading.local()
        self._tl.logger = init_logger
        self._tl.session_id = None

        init_logger.info(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

        # Injeção de dependências (DIP) — aceita implementações via Protocol
        # ou instancia as concretas como padrão (OCP).
        self.detector: PlayerDetectorPort = detector or YoloDetector()
        self.ball_detector: BallDetectorPort = ball_detector or BallDetector()
        self.jersey_reader: JerseyReaderPort = jersey_reader or JerseyReader()
        self.ball_event_detector: BallEventDetectorPort = ball_event_detector or BallEventDetector()
        self.kinematic_analyzer: KinematicAnalyzerPort = kinematic_analyzer or KinematicAnalyzer()
        self.clip_writer: ClipWriterPort = clip_writer or ClipWriter()
        self.color_extractor: ColorExtractorPort = color_extractor or ColorExtractor()

        self._metadata_extractor = MetadataExtractor(
            detector=self.detector,
            ball_detector=self.ball_detector,
            jersey_reader=self.jersey_reader,
            color_extractor=self.color_extractor,
        )
        self._clip_extractor = ClipExtractor(clip_writer=self.clip_writer)

    @classmethod
    def build(
        cls,
        *,
        detector: PlayerDetectorPort | None = None,
        ball_detector: BallDetectorPort | None = None,
        jersey_reader: JerseyReaderPort | None = None,
        ball_event_detector: BallEventDetectorPort | None = None,
        kinematic_analyzer: KinematicAnalyzerPort | None = None,
        clip_writer: ClipWriterPort | None = None,
        color_extractor: ColorExtractorPort | None = None,
    ) -> "VideoPipeline":
        """
        Factory Method — cria instância configurada do pipeline.

            pipeline = VideoPipeline.build(detector=MockDetector())
            pipeline = VideoPipeline.build(clip_writer=S3ClipWriter())
        """
        return cls(
            detector=detector,
            ball_detector=ball_detector,
            jersey_reader=jersey_reader,
            ball_event_detector=ball_event_detector,
            kinematic_analyzer=kinematic_analyzer,
            clip_writer=clip_writer,
            color_extractor=color_extractor,
        )

    # ------------------------------------------------------------------
    # Propriedades thread-local
    # ------------------------------------------------------------------

    @property
    def logger(self):
        return getattr(self._tl, 'logger', logging.getLogger(__name__))

    @logger.setter
    def logger(self, value):
        self._tl.logger = value

    @property
    def session_id(self):
        return getattr(self._tl, 'session_id', None)

    @session_id.setter
    def session_id(self, value):
        self._tl.session_id = value

    # ------------------------------------------------------------------
    # Ponto de entrada público: fast_scan
    # ------------------------------------------------------------------

    def fast_scan(
        self,
        video_path: str,
        output_dir: str,
        target_number: int | None = None,
        frames_to_skip: int = 30,
        on_candidate_found: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        start_ts: int = 0,
        end_ts: int = 0,
    ) -> list[dict]:
        """
        Varredura expressa — identifica candidatos sem processamento completo.

        Notifica `on_candidate_found` a cada novo perfil de jogador via Observer.
        """
        observer: PipelineObserver = make_observer(on_candidate_found=on_candidate_found)

        self.logger, self.session_id = setup_pipeline_logger(output_dir, True)
        self.logger.info(f"=== INICIANDO FAST SCAN (Sessão: {self.session_id}) ===")

        os.makedirs(output_dir, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Falha ao abrir vídeo no Fast Scan.")

        fps = self._get_safe_fps(cap)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        start_frame = int(start_ts * fps)
        end_frame = int(end_ts * fps) if end_ts > 0 else total_frames - 1

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        self.logger.debug(f"[FAST SCAN] Pulando para o frame {start_frame} (limite: {end_frame}).")

        candidates_found: dict[str, dict] = {}
        try:
            while True:
                if should_stop and should_stop():
                    self.logger.warning("[FAST SCAN] Interrompido pelo usuário! Iniciando tracking...")
                    break

                ret, frame_orig = cap.read()
                if not ret:
                    break

                frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

                if frame_idx % frames_to_skip != 0:
                    continue

                frame = self._resize_frame(frame_orig)
                scale = frame_orig.shape[1] / frame.shape[1]

                detections, _ = self.detector.detect(frame)

                for box, conf, cls in detections:
                    x1, y1, w, h = box

                    if not self._is_valid_player_detection((x1, y1, w, h), frame.shape[0]):
                        continue

                    bbox_orig = (
                        int(x1 * scale),
                        int(y1 * scale),
                        int((x1 + w) * scale),
                        int((y1 + h) * scale),
                    )

                    numbers = self.jersey_reader.read_from_bbox(
                        frame_orig, bbox_orig, target_number or -1
                    )

                    if not numbers:
                        continue

                    for num in numbers:
                        crop = self.jersey_reader._torso_crop(frame_orig, *bbox_orig)
                        hex_color = self._extract_core_color(crop)

                        if not hex_color:
                            continue

                        is_duplicate = any(
                            existing["number"] == num
                            and self._color_distance(hex_color, existing["color"]) < FAST_SCAN_COLOR_TOLERANCE
                            for existing in candidates_found.values()
                        )

                        if not is_duplicate:
                            cand_dict = self._build_candidate(
                                frame_orig, bbox_orig, num, hex_color, output_dir
                            )
                            candidates_found[cand_dict["id"]] = cand_dict
                            self.logger.info(f"[FAST SCAN] Novo candidato encontrado e enviado à UI: {num}")
                            observer.on_candidate_found(cand_dict)

        finally:
            cap.release()

        self.logger.info(f"[FAST SCAN] Concluído. {len(candidates_found)} perfis distintos encontrados.")
        return list(candidates_found.values())

    # ------------------------------------------------------------------
    # Ponto de entrada público: process (Template Method)
    # ------------------------------------------------------------------

    def process(
        self,
        video_path: str,
        target_number: int,
        output_dir: str,
        target_signature: str | None = None,
        start_ts: int = 0,
        end_ts: int = 0,
        on_player_found: Callable | None = None,
        on_clip_generated: Callable | None = None,
        on_extracting_start: Callable | None = None,
        debug: bool = False,
    ) -> list[dict]:
        """
        Template Method (GoF) — esqueleto fixo em 4 passos:

          Passo 1 — MetadataExtractor  : YOLO + tracking + OCR
          Passo 2 — _resolve_player_ids: cruza OCR com track_ids
          Passo 3 — _compute_clip_intervals: calcula intervalos temporais
          Passo 4 — ClipExtractor      : fatia o vídeo original
        """
        pipeline_start = time.time()

        observer: PipelineObserver = make_observer(
            on_player_found=on_player_found,
            on_clip_generated=on_clip_generated,
            on_extracting_start=on_extracting_start,
        )

        self.logger, self.session_id = setup_pipeline_logger(output_dir, debug)
        self.logger.info(f"=== INICIANDO PROCESSAMENTO (Sessão: {self.session_id}) ===")
        self.logger.info(f"Vídeo: {video_path} | Alvo inicial: {target_number}")

        if target_signature and "_" in target_signature:
            try:
                novo_numero = int(target_signature.split("_")[0])
                target_number = novo_numero
                self.logger.info(f"Alvo atualizado pela UI. Novo alvo: Jogador {target_number}")
            except ValueError:
                pass

        os.makedirs(output_dir, exist_ok=True)
        debug_dir = self._setup_debug_dir(output_dir, debug)

        tracker = PlayerTracker()
        ball_tracker = BallTracker()

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError("Falha ao abrir vídeo.")

        try:
            fps = self._get_safe_fps(cap)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            duracao_seg = total_frames / max(1, fps)

            self.logger.info("=== METADADOS DO VÍDEO ===")
            self.logger.info(
                f"Resolução Original: {width}x{height} | FPS Real: {fps:.2f} | Duração: {duracao_seg:.2f}s"
            )

            if width > PROCESS_WIDTH:
                escala = PROCESS_WIDTH / width
                altura_proc = int(height * escala)
                self.logger.info(
                    f"[PRÉ-PROCESSAMENTO] Downscale ativo: {width}x{height} → "
                    f"{PROCESS_WIDTH}x{altura_proc} (Fator: {escala:.2f})"
                )
            else:
                self.logger.info(
                    "[PRÉ-PROCESSAMENTO] Vídeo menor que o PROCESS_WIDTH. Downscale não será aplicado."
                )

            self.logger.info("=== HIPERPARÂMETROS (Para Reprodutibilidade) ===")
            self.logger.info(
                f"FRAME_SKIP={FRAME_SKIP} | MIN_OCR_VOTES={MIN_OCR_VOTES} "
                f"| GAP_TOLERANCE={GAP_TOLERANCE}s | PROCESS_WIDTH={PROCESS_WIDTH}px"
            )
            self.logger.info("=========================================")

            start_frame = int(start_ts * fps)
            end_frame = int(end_ts * fps) if end_ts > 0 else total_frames - 1

            # ── Passo 1: Extração de metadados ─────────────────────────────
            video_metadata, jersey_map, max_frame = self._metadata_extractor.extract(
                cap=cap,
                tracker=tracker,
                ball_tracker=ball_tracker,
                start_frame=start_frame,
                end_frame=end_frame,
                total_frames=total_frames,
                target_number=target_number,
                target_signature=target_signature,
                debug=debug,
                debug_dir=debug_dir,
                logger=self.logger,
            )
        finally:
            cap.release()

        processed_total = max_frame + 1

        # ── Passo 2: Resolução de identidades ──────────────────────────────
        target_track_ids = self._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=target_number,
            target_signature=target_signature,
            debug=debug,
        )
        observer.on_player_found()

        # ── Passo 3: Cálculo de intervalos temporais ───────────────────────
        target_frames, events, clip_intervals = self._compute_clip_intervals(
            video_metadata=video_metadata,
            target_track_ids=target_track_ids,
            start_frame=start_frame,
            processed_total=processed_total,
            fps=fps,
        )

        # ── Passo 4: Escrita dos clipes ─────────────────────────────────────
        observer.on_extracting_start()
        results = self._clip_extractor.write_clips(
            video_path=video_path,
            clip_intervals=clip_intervals,
            events=events,
            target_number=target_number,
            output_dir=output_dir,
            fps=fps,
            total_frames=total_frames,
            on_clip_generated=observer.on_clip_generated,
            logger=self.logger,
        )

        self._log_metrics(
            start_time=pipeline_start,
            processed_total=processed_total,
            start_frame=start_frame,
            num_clips=len(results),
        )

        return results

    # ======================================================
    # PASSO 2 — RESOLUÇÃO DE IDs (testado diretamente)
    # ======================================================

    def _resolve_player_ids(
        self,
        jersey_map: dict,
        target_number: int,
        target_signature: str | None,
        debug: bool,
    ) -> set[str]:
        """
        Cruza jersey_map com o número-alvo para descobrir os track_ids
        que pertencem ao jogador procurado.
        """
        self.logger.info("[2/4] Resolvendo Identidades dos Jogadores...")

        jersey_map_filtered = {
            tid: counter
            for tid, counter in jersey_map.items()
            if counter and len(counter) <= MAX_DISTINCT_READINGS
        }
        discarded = len(jersey_map) - len(jersey_map_filtered)
        if discarded:
            self.logger.info(f"    [{discarded} tracks descartados por leituras inconsistentes]")

        resolved: dict[str, int | str] = {
            tid: counter.most_common(1)[0][0]
            for tid, counter in jersey_map_filtered.items()
            if counter.most_common(1)[0][1] >= MIN_OCR_VOTES
        }

        if debug:
            self.logger.debug(
                f"  [MAP] Detalhado: { {tid: dict(c) for tid, c in jersey_map_filtered.items()} }"
            )
            self.logger.debug(f"  [MAP] Resolvido: {resolved}")

        target_val = target_signature if target_signature else target_number
        target_track_ids = {tid for tid, num in resolved.items() if num == target_val}

        if not target_track_ids:
            for tid, counter in jersey_map_filtered.items():
                if counter and counter.most_common(1)[0][0] == target_val:
                    target_track_ids.add(tid)

        if not target_track_ids:
            raise ValueError(f"Jogador alvo não encontrado. Alvo: {target_val}")

        self.logger.info(f"    ✓ Jogador #{target_val} vinculado aos IDs: {target_track_ids}")
        return target_track_ids

    # ======================================================
    # PASSO 3 — LÓGICA TEMPORAL (testado diretamente)
    # ======================================================

    def _compute_clip_intervals(
        self,
        video_metadata: dict,
        target_track_ids: set[str],
        start_frame: int,
        processed_total: int,
        fps: float,
    ) -> tuple[list[int], list[dict], list[tuple[int, int]]]:
        """Calcula os intervalos (start_frame, end_frame) de cada clipe."""
        self.logger.info("[3/4] Calculando intervalos de ação...")

        target_frames = sorted(
            f_idx
            for f_idx in range(start_frame, processed_total)
            if self._target_in_frame(video_metadata, f_idx, target_track_ids)
        )

        kinematic_events = self.kinematic_analyzer.analyze(video_metadata, fps)
        self._print_kinematic_events(kinematic_events)

        events = self.ball_event_detector.detect(
            target_frames=target_frames,
            video_metadata=video_metadata,
            target_track_ids=target_track_ids,
            fps=fps,
        )
        self.logger.info(f"    {len(events)} interações com a bola detectadas.")

        clip_intervals = self._group_frames_into_intervals(target_frames)

        if not target_frames:
            self.logger.warning("    [!] O jogador não foi encontrado no vídeo.")
        else:
            self.logger.info(
                f"    ✓ {len(clip_intervals)} blocos de ação encontrados (Modo Player Cam)."
            )

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
        return any(str(tid) in target_track_ids for _, _, _, _, tid in frame_data["tracks"])

    def _group_frames_into_intervals(
        self,
        target_frames: list[int],
    ) -> list[tuple[int, int]]:
        """
        Agrupa frames ordenados em intervalos contíguos.

        Frames com gap ≤ GAP_TOLERANCE pertencem ao mesmo intervalo.
        Intervalos com span < MIN_CLIP_FRAMES são descartados.
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

        if (current_end - current_start) >= MIN_CLIP_FRAMES:
            intervals.append((current_start, current_end))

        return intervals

    # ======================================================
    # DELEGATES → detection_utils (contratos testados)
    # ======================================================

    def _color_distance(self, hex1: str, hex2: str) -> float:
        return _color_distance_fn(hex1, hex2)

    def _is_valid_player_detection(self, bbox_xywh: tuple, frame_h: float) -> bool:
        return _is_valid_player_detection_fn(bbox_xywh, frame_h)

    @staticmethod
    def _get_safe_fps(cap: cv2.VideoCapture) -> float:
        return _get_safe_fps_fn(cap)

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        return _resize_frame_fn(frame)

    def _extract_core_color(self, torso_crop: np.ndarray) -> str | None:
        return _extract_core_color_fn(torso_crop, self.color_extractor)

    # ======================================================
    # HELPERS LOCAIS
    # ======================================================

    @staticmethod
    def _build_candidate(
        frame_orig: np.ndarray,
        bbox_orig: tuple[int, int, int, int],
        num: int,
        hex_color: str,
        output_dir: str,
    ) -> dict:
        """Constrói o dicionário de candidato e salva a imagem recortada."""
        px1, py1, px2, py2 = bbox_orig
        h_box, w_box = py2 - py1, px2 - px1

        center_x = px1 + w_box // 2
        center_y = py1 + h_box // 2
        half_size = int(max(w_box, h_box) * 1.2) // 2

        cy1 = max(0, center_y - half_size)
        cy2 = min(frame_orig.shape[0], center_y + half_size)
        cx1 = max(0, center_x - half_size)
        cx2 = min(frame_orig.shape[1], center_x + half_size)

        player_crop = frame_orig[cy1:cy2, cx1:cx2]
        if player_crop.size > 0:
            player_crop = cv2.resize(player_crop, (256, 256), interpolation=cv2.INTER_AREA)

        img_filename = f"cand_numero_{num}_{uuid.uuid4().hex[:8]}.jpg"
        img_path = os.path.join(output_dir, img_filename)
        cv2.imwrite(img_path, player_crop)

        signature = f"{num}_{hex_color}"
        return {
            "id": signature,
            "name": f"Jogador {num}",
            "number": num,
            "color": hex_color,
            "image": f"/uploads/clips/{os.path.basename(output_dir)}/{img_filename}",
        }

    @staticmethod
    def _setup_debug_dir(output_dir: str, debug: bool) -> str | None:
        if not debug:
            return None
        debug_dir = os.path.join(output_dir, "debug_ocr")
        os.makedirs(debug_dir, exist_ok=True)
        return debug_dir

    def _print_kinematic_events(self, events: list[dict]) -> None:
        for e in events:
            mm, ss = divmod(int(e["time"]), 60)
            unit = "px/frame" if e["type"] == "pico_velocidade" else "px/frame²"
            self.logger.info(
                f"[ANOMALIA] Possível lance aos {mm:02d}:{ss:02d} "
                f"({e['object']} track={e['track_id']}, "
                f"{e['type'].replace('_', ' ')}={e['value']}{unit})"
            )

    def _log_metrics(
        self,
        start_time: float,
        processed_total: int,
        start_frame: int,
        num_clips: int,
    ) -> None:
        elapsed = time.time() - start_time
        self.logger.info(
            "\n=== MÉTRICAS DE PERFORMANCE ===\n"
            f"Total de Frames Analisados: {processed_total - start_frame}\n"
            f"Tempo Total de Execução: {elapsed:.2f}s ({elapsed / 60:.2f} min)\n"
            f"Clipes Gerados: {num_clips}\n"
            "==============================="
        )
