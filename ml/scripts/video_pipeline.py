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
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable
import uuid
import logging

import cv2
import numpy as np

from ml.detector import BallDetector, YoloDetector
from ml.scripts.ball_event_detector import BallEventDetector
from ml.scripts.clip_writer import ClipWriter
from ml.scripts.config import (
    CLIP_PADDING_SECONDS,
    FRAME_SKIP,
    GAP_TOLERANCE,
    MIN_CLIP_FRAMES,
    MIN_OCR_VOTES,
    MAX_DISTINCT_READINGS,
    OCR_INTERVAL,
    PROCESS_WIDTH,
    USE_GPU,
    TRACKING_COLOR_TOLERANCE,
    FAST_SCAN_COLOR_TOLERANCE,
    SCOREBOARD_ZONE_TOP,
    SCOREBOARD_ZONE_BOTTOM,
    MAX_PLAYER_ASPECT_RATIO,
    TORSO_Y_START,
    TORSO_Y_END,
)
from ml.scripts.kinematic_analyzer import KinematicAnalyzer
from ml.scripts.jersey_reader import JerseyReader
from ml.scripts.trackers.ball_tracker import BallTracker
from ml.scripts.trackers.tracker import PlayerTracker
from ml.scripts.color_extractor import ColorExtractor
from ml.scripts.config import setup_pipeline_logger

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
        init_logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

        # Estado por thread: logger e session_id são isolados por thread para
        # evitar race condition quando dois jobs rodam simultaneamente no singleton.
        self._tl = threading.local()
        self._tl.logger = init_logger
        self._tl.session_id = None

        init_logger.info(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

        # Componentes (carregados uma vez)
        self.detector = YoloDetector()
        self.ball_detector = BallDetector()
        self.jersey_reader = JerseyReader()
        self.ball_event_detector = BallEventDetector()
        self.kinematic_analyzer = KinematicAnalyzer()
        self.clip_writer = ClipWriter()
        self.color_extractor = ColorExtractor()

        # Tracker é instanciado por vídeo (dentro de process)
        # porque mantém estado interno que não pode vazar entre execuções

    # ------------------------------------------------------------------
    # Propriedades thread-local: cada thread tem seu próprio logger e
    # session_id, evitando race condition no singleton compartilhado.
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

    def fast_scan(
        self,
        video_path: str,
        output_dir: str,
        target_number: int | None = None,
        frames_to_skip: int = 30,
        on_candidate_found: Callable[[dict], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        start_ts: int = 0,
        end_ts: int = 0
    ) -> list[dict]:
        """
        Faz uma varredura super rápida no vídeo procurando candidatos.
        Utiliza processamento em Lote (Batch Inference) para otimização extrema na GPU.
        """
        
        self.logger, self.session_id = setup_pipeline_logger(output_dir, True) # remover em prod
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

        candidates_found = {}

        try:
            while True:
                if should_stop and should_stop():
                    self.logger.warning("[FAST SCAN] Interrompido pelo usuário! Iniciando tracking...")
                    break

                ret, frame_orig = cap.read()
                if not ret:
                    break
                
                frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                
                # Pula frames para agilizar
                if frame_idx % frames_to_skip != 0:
                    continue
                    
                frame = self._resize_frame(frame_orig)
                scale = frame_orig.shape[1] / frame.shape[1]

                # =======================================================
                # 1. PEGA DETECÇÕES JÁ FILTRADAS PELA ZONA DO PLACAR
                # =======================================================
                detecoes_validadas, _ = self._get_valid_detections(frame, scale)

                # =======================================================
                # 2. PREPARA O LOTE (BATCH) DE RECORTES PARA A GPU
                # =======================================================
                crops_lote = []
                bboxes_lote = []
                
                for det in detecoes_validadas:
                    bbox_orig = det["bbox_orig"]
                    crop = self.jersey_reader._torso_crop(frame_orig, *bbox_orig)
                    
                    # Filtro de tamanho para evitar mandar lixo para a IA
                    if crop.shape[0] >= 10 and crop.shape[1] >= 10:
                        crops_lote.append(crop)
                        bboxes_lote.append(bbox_orig)

                # Se não tem ninguém válido neste frame, vai para o próximo
                if not crops_lote:
                    continue

                # =======================================================
                # 3. CHAMA A IA 1 ÚNICA VEZ PARA TODOS OS JOGADORES!
                # =======================================================
                target_num_pass = target_number if target_number is not None else -1
                resultados_lote = self.jersey_reader.read_batch(crops_lote, target_num_pass)
                
                # =======================================================
                # 4. PROCESSA OS RESULTADOS
                # =======================================================
                # zip une os bboxes, as imagens recortadas e os números lidos
                for bbox_orig, crop, numbers in zip(bboxes_lote, crops_lote, resultados_lote):
                    if not numbers:
                        continue
                        
                    # [CORREÇÃO] Desempacota a tupla retornada pelo novo JerseyReader
                    for num, conf in numbers:
                        
                        # Ignora leituras de baixíssima confiança no Fast Scan para evitar spam na UI
                        if conf < 0.40:
                            continue
                            
                        # Extraindo cor apenas do miolo para evitar piso/fundo
                        hex_color = self._extract_core_color(crop)
                        
                        if not hex_color:
                            continue

                        # DEDUPLICAÇÃO INTELIGENTE (Distância de Cor)
                        is_duplicate = False
                        for existing_sig, existing_data in candidates_found.items():
                            if existing_data["number"] == num:
                                if self._color_distance(hex_color, existing_data["color"]) < FAST_SCAN_COLOR_TOLERANCE:
                                    is_duplicate = True
                                    break
                        
                        if not is_duplicate:
                            signature = f"{num}_{hex_color}"
                            img_filename = f"cand_numero_{num}_{uuid.uuid4().hex[:8]}.jpg"
                            img_path = os.path.join(output_dir, img_filename)
                            
                            px1, py1, px2, py2 = bbox_orig
                            h_box = py2 - py1
                            w_box = px2 - px1

                            # 1. Encontra o centro geográfico da bounding box original
                            center_x = px1 + (w_box // 2)
                            center_y = py1 + (h_box // 2)

                            # 2. Define a aresta do quadrado baseada na maior dimensão + 20% de margem
                            square_size = int(max(w_box, h_box) * 1.2)
                            half_size = square_size // 2

                            # 3. Calcula as novas coordenadas projetando do centro para as extremidades
                            cy1_ideal = center_y - half_size
                            cy2_ideal = center_y + half_size
                            cx1_ideal = center_x - half_size
                            cx2_ideal = center_x + half_size

                            # 4. Clamping: Limita as coordenadas às dimensões reais do frame do vídeo
                            cy1 = max(0, cy1_ideal)
                            cy2 = min(frame_orig.shape[0], cy2_ideal)
                            cx1 = max(0, cx1_ideal)
                            cx2 = min(frame_orig.shape[1], cx2_ideal)

                            player_crop = frame_orig[cy1:cy2, cx1:cx2]
                            
                            # 5. Normalização Absoluta
                            target_resolution = (256, 256)
                            if player_crop.size > 0:
                                player_crop = cv2.resize(player_crop, target_resolution, interpolation=cv2.INTER_AREA)
                            
                            cv2.imwrite(img_path, player_crop)
                            
                            cand_dict = {
                                "id": signature,
                                "name": f"Jogador {num}",
                                "number": num,
                                "color": hex_color,
                                "image": f"/uploads/clips/{os.path.basename(output_dir)}/{img_filename}"
                            }
                            candidates_found[signature] = cand_dict
                            self.logger.info(f"[FAST SCAN] Novo candidato encontrado e enviado à UI: {num} (conf: {conf:.2f})")
                            
                            if on_candidate_found:
                                on_candidate_found(cand_dict)
                            
        finally:
            cap.release()
            
        self.logger.info(f"[FAST SCAN] Concluído. {len(candidates_found)} perfis distintos encontrados.")
        return list(candidates_found.values())

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

        # Tracker novo a cada execução (estado limpo)
        tracker = PlayerTracker()
        ball_tracker = BallTracker()

        # Abre vídeo e extrai metadados
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
            self.logger.info(f"Resolução Original: {width}x{height} | FPS Real: {fps:.2f} | Duração: {duracao_seg:.2f}s")
            
            if width > PROCESS_WIDTH:
                escala = PROCESS_WIDTH / width
                altura_proc = int(height * escala)
                self.logger.info(f"[PRÉ-PROCESSAMENTO] Downscale ativo: {width}x{height} será reduzido para {PROCESS_WIDTH}x{altura_proc} (Fator: {escala:.2f})")
            else:
                self.logger.info("[PRÉ-PROCESSAMENTO] Vídeo menor que o PROCESS_WIDTH. Downscale não será aplicado.")
            
            self.logger.info("=== HIPERPARÂMETROS (Para Reprodutibilidade) ===")
            self.logger.info(f"FRAME_SKIP={FRAME_SKIP} | MIN_OCR_VOTES={MIN_OCR_VOTES} | GAP_TOLERANCE={GAP_TOLERANCE}s | PROCESS_WIDTH={PROCESS_WIDTH}px")
            self.logger.info("=========================================")

            start_frame = int(start_ts * fps)
            end_frame = int(end_ts * fps) if end_ts > 0 else total_frames - 1

            # ============== PASSO 1 ==============
            video_metadata, jersey_map, max_frame = self._extract_metadata(
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
            )
        finally:
            cap.release()

        processed_total = max_frame + 1

        # ============== PASSO 2 ==============
        target_track_ids = self._resolve_player_ids(
            jersey_map=jersey_map,
            target_number=target_number,
            target_signature=target_signature,
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
        if on_extracting_start:
            on_extracting_start()
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
        ball_tracker: BallTracker,
        start_frame: int,
        end_frame: int,
        total_frames: int,
        target_number: int,
        target_signature: str | None,
        debug: bool,
        debug_dir: str | None,
    ) -> tuple[dict, dict, int]:
        self.logger.info(f"[1/4] Extraindo metadados com IA ({total_frames} frames)...")
        self.logger.info(f"[video] Começando no segundo {start_frame // max(1, int(cap.get(cv2.CAP_PROP_FPS)))} (frame {start_frame})")
        self.logger.info(f"[video] Terminando no frame {end_frame}")

        video_metadata: dict[int, dict] = {}
        jersey_map: dict[str, dict] = defaultdict(lambda: defaultdict(float))
        max_frame = start_frame - 1

        fps = self._get_safe_fps(cap)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame

        # ---------------------------------------------------------
        # CONFIGURAÇÕES DA HEURÍSTICA DE DENSIDADE (FAST-FORWARD)
        # ---------------------------------------------------------
        consecutive_low_density = 0
        MIN_PLAYERS_THRESHOLD = 1
        TIME_TO_SLEEP_SEC = 10       # Tempo de espera para avançar
        FAST_FORWARD_SKIP_SEC = 5   # Tempo do avanço

        # Ajuste de FPS considerando o FRAME_SKIP (se FRAME_SKIP=3 e FPS=30, processamos 10 fps)
        processed_fps = fps / max(1, FRAME_SKIP)
        frames_to_trigger_sleep = int(processed_fps * TIME_TO_SLEEP_SEC)
        fast_forward_frames = int(fps * FAST_FORWARD_SKIP_SEC)

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

            # ---------------------------------------------------------
            # 1. ZONA DE EXCLUSÃO ESPACIAL (Filtragem do Overlay de Transmissão)
            # ---------------------------------------------------------
            deteccoes_validas, bolas_yolo = self._get_valid_detections(frame, scale)
            valid_detections = [[d["box_yolo"], d["conf"], d["cls"]] for d in deteccoes_validas]

            # ---------------------------------------------------------
            # 2. HEURÍSTICA DE DENSIDADE (Fast-Forward Dinâmico)
            # ---------------------------------------------------------
            if len(valid_detections) < MIN_PLAYERS_THRESHOLD:
                consecutive_low_density += 1
            else:
                consecutive_low_density = 0 # O jogo está a decorrer, reinicia o contador

            if consecutive_low_density > frames_to_trigger_sleep:
                self.logger.info(f"[FAST-FORWARD] Campo vazio (frame {frame_idx}). Pulando {FAST_FORWARD_SKIP_SEC}s...")
                next_frame = frame_idx + fast_forward_frames
                cap.set(cv2.CAP_PROP_POS_FRAMES, next_frame)
                frame_idx = next_frame
                consecutive_low_density = 0 # Reinicia após o salto para dar tempo de reavaliação
                continue # Pula o processamento pesado (Tracker, OCR) deste ciclo

            # ---------------------------------------------------------
            # PROCESSAMENTO NORMAL
            # ---------------------------------------------------------
            # Passa apenas as detecções validadas (sem placar) para o tracker
            #balls = self.ball_detector.detect(frame)

            ball_box = ball_tracker.update(frame_idx, bolas_yolo)
            tracks = tracker.update(valid_detections, frame)

            # Armazena metadata do frame
            video_metadata[frame_idx] = {
                "tracks": [
                    [float(l), float(t), float(r), float(b), str(tid)]
                    for l, t, r, b, tid in tracks
                ],
                "balls": [
                    [float(x) for x in ball_box]
                ] if ball_box else []
            }

            # OCR em subconjunto de frames
            if frame_idx % OCR_INTERVAL == 0:
                self._run_ocr_on_tracks(
                    tracks=tracks,
                    frame_orig=frame_orig,
                    scale=scale,
                    target_number=target_number,
                    target_signature=target_signature,
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
        target_signature: str | None,
        frame_idx: int,
        jersey_map: dict,
        debug: bool,
        debug_dir: str | None,
    ) -> None:
        """Roda OCR em LOTE com otimizações de cache (votos) e filtragem geométrica."""

        target_color = None
        if target_signature and "_" in target_signature:
            try:
                target_color = target_signature.split("_")[1]
            except IndexError:
                pass

        # Calcula a altura na escala de processamento para a função geométrica
        proc_h = frame_orig.shape[0] / scale if scale else frame_orig.shape[0]

        # 1. Prepara as listas do Lote
        crops_lote = []
        track_ids_lote = []
        bboxes_orig_lote = []

        for l, t, r, b, track_id in tracks:
            # OTIMIZAÇÃO 1 (Do Commit): Pula tracks que já acumularam votos suficientes
            existing = jersey_map.get(str(track_id))
            if existing and max(existing.values(), default=0) >= MIN_OCR_VOTES:
                continue

            # OTIMIZAÇÃO 2 (Do Commit): Filtra bboxes panorâmicas geradas pelo tracker
            w_track = r - l
            h_track = b - t
            if not self._is_valid_player_detection((l, t, w_track, h_track), proc_h):
                continue

            bbox = (int(l * scale), int(t * scale), int(r * scale), int(b * scale))
            crop = self.jersey_reader._torso_crop(frame_orig, *bbox)

            # Só adiciona no lote se o recorte for válido (O commit ajustou MIN_CROP_H para 35)
            if crop.shape[0] >= 35 and crop.shape[1] >= 10: 
                crops_lote.append(crop)
                track_ids_lote.append(track_id)
                bboxes_orig_lote.append(bbox)

        # Se não há recortes válidos após os filtros, saímos
        if not crops_lote:
            return

        # 2. CHAMA O YOLO 1 ÚNICA VEZ PARA TODOS OS JOGADORES DO LOTE!
        target_num_pass = target_number if target_number is not None else -1
        resultados_lote = self.jersey_reader.read_batch(crops_lote, target_num_pass)

        # 3. Processa os resultados
        for track_id, bbox, crop, numbers in zip(track_ids_lote, bboxes_orig_lote, crops_lote, resultados_lote):
            if not numbers:
                continue

            for n, conf in numbers: 
                if target_color and n == target_number:
                    hex_color = self._extract_core_color(crop)
                    if hex_color and self._color_distance(target_color, hex_color) < TRACKING_COLOR_TOLERANCE:
                        # Jogador correto. Damos um multiplicador de peso na confiança.
                        # Exemplo: Uma leitura de 0.8 vale 1.6 pontos na assinatura oficial.
                        jersey_map[str(track_id)][target_signature] += (conf * 2.0)
                    else:
                        # É do outro time. Acumula lixo com peso real.
                        jersey_map[str(track_id)][f"LIXO_{n}_{hex_color}"] += conf
                else:
                    # Fluxo normal (Soft Voting: em vez de += 1, soma a confiança)
                    jersey_map[str(track_id)][n] += conf

            if debug and debug_dir:
                # Nota: 'numbers' agora será impresso no log como uma lista de tuplas. Ex: [(10, 0.85)]
                self._save_debug_crop(frame_orig, bbox, frame_idx, track_id, numbers, debug_dir)
                self.logger.debug(f"  [MAP] frame={frame_idx} track={track_id} leu={numbers}")

    def _color_distance(self, hex1: str, hex2: str) -> float:
        """Calcula a distância perceptual entre duas cores usando o espaço LAB (Visão Humana)"""
        def hex_to_lab(h: str) -> np.ndarray:
            h = h.lstrip('#')
            # Converte Hex string para valores BGR inteiros
            b, g, r = tuple(int(h[i:i+2], 16) for i in (4, 2, 0))
            # Cria um "pixel" 1x1 no formato que o OpenCV entende (uint8)
            pixel_bgr = np.array([[[b, g, r]]], dtype=np.uint8)
            # Converte para LAB e extrai os valores float
            pixel_lab = cv2.cvtColor(pixel_bgr, cv2.COLOR_BGR2LAB)
            return pixel_lab[0][0].astype(float)
        
        try:
            lab1 = hex_to_lab(hex1)
            lab2 = hex_to_lab(hex2)
            # Retorna a distância Euclidiana 3D, mas agora no espaço LAB
            return float(np.linalg.norm(lab1 - lab2))
        except Exception:
            self.logger.warning(f"Falha ao calcular cor entre {hex1} e {hex2}")
            return 999.0 # Em caso de erro de parsing, assume que são muito diferentes

    # ======================================================
    # PASSO 2 — RESOLUÇÃO DE IDs
    # ======================================================
    def _resolve_player_ids(
        self,
        jersey_map: dict,
        target_number: int,
        target_signature: str | None,
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
        self.logger.info("[2/4] Resolvendo Identidades dos Jogadores...")

        # Descarta tracks com leituras muito inconsistentes (ex: torcedores na
        # arquibancada que produzem números aleatórios a cada frame)
        jersey_map_filtered = {
            tid: counter
            for tid, counter in jersey_map.items()
            if counter and len(counter) <= MAX_DISTINCT_READINGS
        }
        discarded = len(jersey_map) - len(jersey_map_filtered)
        if discarded:
            self.logger.info(f"    [{discarded} tracks descartados por leituras inconsistentes]")

        resolved: dict[str, int | str] = {}

        for tid, conf_dict in jersey_map_filtered.items():
            # [NOVO] Extrai a chave com maior valor (maior soma de confiança)
            best_num = max(conf_dict, key=conf_dict.get)
            votes = conf_dict[best_num]
            
            if votes >= MIN_OCR_VOTES:
                resolved[tid] = best_num

        if debug:
            # Formatação simplificada para debug no log
            detailed = {tid: dict(c) for tid, c in jersey_map_filtered.items()}
            self.logger.debug(f"  [MAP] Detalhado (filtrado): {detailed}")
            self.logger.debug(f"  [MAP] Resolvido: {resolved}")

        target_val = target_signature if target_signature else target_number

        target_track_ids = {
            tid for tid, num in resolved.items() if num == target_val
        }

        # --- CORREÇÃO: RESGATE INTELIGENTE COM PROTEÇÃO DE PROPORÇÃO (RATIO) ---
        if not target_track_ids:
            for tid, conf_dict in jersey_map_filtered.items():
                target_votes = conf_dict.get(target_val, 0)
                total_votes = sum(conf_dict.values())
                
                # Exigimos no mínimo 1.5 pontos (peso absoluto mínimo)
                if target_votes >= 1.5 and total_votes > 0:
                    # Exigimos que o alvo represente pelo menos 25% de tudo que foi lido neste track (peso relativo)
                    ratio = target_votes / total_votes
                    if ratio >= 0.25:
                        target_track_ids.add(tid)
                        resolved[tid] = target_val
                        self.logger.warning(
                            f"    [!] Resgate Ativado: Track {tid} teve {target_votes:.2f} pts "
                            f"({ratio*100:.1f}% de dominância) para o alvo e foi resgatado."
                        )

        # Fallback 2: O antigo (se não achou nada acima de 1.5 e 25%, pega quem liderou a track de forma absoluta)
        if not target_track_ids:
            for tid, conf_dict in jersey_map_filtered.items():
                if conf_dict:
                    best_num = max(conf_dict, key=conf_dict.get)
                    if best_num == target_val:
                        target_track_ids.add(tid)
                        resolved[tid] = target_val

        if not target_track_ids:
            self.logger.warning(f"    [!] Jogador alvo {target_val} não foi encontrado com firmeza no rastreamento. Abortando clipes sem crash.")
            return set() # Retorna vazio. A pipeline não quebra o backend e devolve 0 clipes.

        self.logger.info(f"    ✓ Jogador #{target_val} vinculado aos IDs: {target_track_ids}")
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
        self.logger.info("[3/4] Calculando intervalos de ação...")

        # Coleta todos os frames em que o jogador aparece
        target_frames = sorted(
            f_idx
            for f_idx in range(start_frame, processed_total)
            if self._target_in_frame(video_metadata, f_idx, target_track_ids)
        )

        # Detecta anomalias cinemáticas (velocidade e aceleração) em bola e jogadores
        kinematic_events = self.kinematic_analyzer.analyze(video_metadata, fps)
        self._print_kinematic_events(kinematic_events)

        # Detecta eventos de interação com a bola
        events = self.ball_event_detector.detect(
            target_frames=target_frames,
            video_metadata=video_metadata,
            target_track_ids=target_track_ids,
            fps=fps,
        )
        self.logger.info(f"    {len(events)} interações com a bola detectadas.")

        # Agrupa frames em intervalos contíguos
        clip_intervals = self._group_frames_into_intervals(target_frames)

        if not target_frames:
            self.logger.warning("    [!] O jogador não foi encontrado no vídeo.")
        else:
            self.logger.info(f"    ✓ {len(clip_intervals)} blocos de ação encontrados (Modo Player Cam).")

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
        self.logger.info(f"[4/4] Fatiando vídeo em {len(clip_intervals)} clipes...")

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
                    video_path=video_path
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
        video_path: str
    ) -> dict | None:
        """Extrai e salva um único clipe. Retorna None em caso de falha."""
        padded_start = max(0, start_f - padding_frames)
        padded_end = min(total_frames - 1, end_f + padding_frames)

        if padded_start >= total_frames:
            self.logger.error(f"Tentativa de acesso a frame fora dos limites do vídeo: {padded_start}")
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
            self.logger.error(f"Falha de I/O: Nenhum frame capturado para o clipe {clip_idx}")
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
        self.clip_writer.write(clip_frames, clip_path, fps, (w, h), source_video=video_path, start_sec=start_s)

        return {
            "path": clip_path,
            "start_ts": start_s,
            "end_ts": end_s,
            "events": clip_events,
        }

    # ======================================================
    # HELPERS
    # ======================================================

    def _get_valid_detections(self, frame: np.ndarray, scale: float) -> tuple[list, list]:
        """
        Roda o YOLO e aplica a função aprimorada de validação de bboxes do commit recente.
        """
        detections, bolas_yolo = self.detector.detect(frame)
        frame_h = frame.shape[0]
        
        valid_detections = []
        for box, conf, cls in detections:
            x1, y1, w, h = box
            
            # AQUI ESTÁ A INTEGRAÇÃO: Usamos o filtro do Lucas!
            if not self._is_valid_player_detection((x1, y1, w, h), frame_h):
                continue
                
            bbox_orig = (
                int(x1 * scale),
                int(y1 * scale),
                int((x1 + w) * scale),
                int((y1 + h) * scale)
            )
            
            valid_detections.append({
                "box_yolo": box, 
                "bbox_orig": bbox_orig,
                "conf": conf,
                "cls": cls
            })
            
        return valid_detections, bolas_yolo

    def _extract_core_color(self, torso_crop: np.ndarray) -> str | None:
        """Extrai a COR MÉDIA da parte superior do torso (ombros/peito). 
        Evita o efeito flip-flop de camisas divididas."""
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
            
        # O PULO DO GATO: Tira a média exata de todos os pixels para neutralizar estampas/dobras
        mean_bgr = cv2.mean(shoulders_crop)[:3]
        
        # Converte o BGR médio para código Hexadecimal
        hex_color = '#%02x%02x%02x' % (int(mean_bgr[2]), int(mean_bgr[1]), int(mean_bgr[0]))
        return hex_color

    def _is_valid_player_detection(self, bbox_xywh: tuple, frame_h: float) -> bool:
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

    def _resize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Redimensiona o frame para largura máxima de PROCESS_WIDTH, registando a alteração."""
        h, w = frame.shape[:2]
        if w > PROCESS_WIDTH:
            scale = PROCESS_WIDTH / w
            new_h = int(h * scale)
            frame = cv2.resize(frame, (PROCESS_WIDTH, new_h))
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
        numbers: list[tuple[int, float]],
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
        nums_str = "_".join(f"{n}-c{int(conf*100)}" for n, conf in numbers)
        
        filename = f"ocr_f{frame_idx:05d}_t{track_id}_leu_{nums_str}.png"
        cv2.imwrite(os.path.join(debug_dir, filename), crop)


    def _print_kinematic_events(self, events: list[dict]) -> None:
        """Imprime no terminal os timestamps de anomalias cinemáticas detectadas."""
        if not events:
            return
        for e in events:
            total_seconds = int(e["time"])
            mm = total_seconds // 60
            ss = total_seconds % 60
            timestamp = f"{mm:02d}:{ss:02d}"
            unit = "px/frame" if e["type"] == "pico_velocidade" else "px/frame²"
            self.logger.info(
                f"[ANOMALIA] Possível lance aos {timestamp} "
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
        """Imprime métricas de performance no final da execução."""
        elapsed = time.time() - start_time
        self.logger.info(
            "\n=== MÉTRICAS DE PERFORMANCE ===\n"
            f"Total de Frames Analisados: {processed_total - start_frame}\n"
            f"Tempo Total de Execução: {elapsed:.2f}s ({elapsed / 60:.2f} min)\n"
            f"Clipes Gerados: {num_clips}\n"
            "==============================="
        )