import os
import cv2
import numpy as np
import easyocr
from pathlib import Path
from collections import Counter, defaultdict
from ultralytics import YOLO
from scripts.trackers.tracker import PlayerTracker
from typing import Callable
import time 

OCR_INTERVAL       = 5
FRAME_SKIP         = 2
MIN_W, MIN_H       = 30, 50
PLAYER_CLS         = [0]
BALL_CLS           = 32 
MIN_CLIP_FRAMES    = 30
GAP_TOLERANCE      = 60
PROCESS_WIDTH      = 640
MIN_OCR_VOTES      = 2

ML_ROOT = Path(__file__).resolve().parents[1]

try:
    import torch
    USE_GPU = torch.cuda.is_available()
except ImportError:
    USE_GPU = False


def _resize_frame(frame: np.ndarray) -> np.ndarray:
    h, w = frame.shape[:2]
    if w > PROCESS_WIDTH:
        scale = PROCESS_WIDTH / w
        frame = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))
    return frame


def _torso_crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    h = y2 - y1
    torso_y1 = y1 + int(h * 0.15)
    torso_y2 = y1 + int(h * 0.55)
    fh, fw = frame.shape[:2]
    return frame[max(0, torso_y1):min(fh, torso_y2), max(0, x1):min(fw, x2)]


def _read_numbers(crop: np.ndarray, reader: easyocr.Reader, target_number: int) -> list[int]:
    """Single-strategy OCR: Gaussian Blur + CLAHE com Filtro de Confiança."""
    h, w = crop.shape[:2]
    if h < 5 or w < 5:
        return []

    # Amplia a imagem
    big = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    results: set[int] = set()

    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    
    # Suavização Gaussiana para "passar a ferro" as rugas e pixels borrados
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(blur)
    
    # detail=1 pede ao EasyOCR para retornar a "certeza" da leitura
    detections = reader.readtext(enhanced, allowlist="0123456789", detail=1)
    
    # Substituímos 'bbox' por '_' para silenciar o aviso de variável não utilizada
    for _, text, prob in detections:
        # Cast explícito para garantir ao linter que é um número
        try:
            confidence = float(prob)
        except (ValueError, TypeError):
            continue # Ignora se a biblioteca devolver algo bizarro

        # Se a IA tem menos de 40% de certeza, é lixo (ruga/sombra). Ignora.
        if confidence < 0.40:
            continue

        t = str(text).strip()
        if t.isdigit():
            val = int(t)

            if val == 0 and target_number != 0:
                continue
            
            # Mantém a nossa Heurística de tamanho
            if 1 <= len(t) <= 2 or val == target_number:
                results.add(val)

    return list(results)


def _iou(a: list, b: list) -> float:
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)


def _is_ball_near_player(player_box: list[float], ball_box: list[float]) -> bool:
    if _iou(player_box, ball_box) > 0.01:
        return True

    px1, py1, px2, py2 = player_box
    width = px2 - px1
    height = py2 - py1
    pad = 0.2
    expanded = [px1 - width * pad, py1 - height * pad,
                px2 + width * pad, py2 + height * pad]

    bx1, by1, bx2, by2 = ball_box
    bcx, bcy = (bx1 + bx2) / 2.0, (by1 + by2) / 2.0

    if expanded[0] <= bcx <= expanded[2] and expanded[1] <= bcy <= expanded[3]:
        return True

    dx = max(expanded[0] - bcx, 0, bcx - expanded[2])
    dy = max(expanded[1] - bcy, 0, bcy - expanded[3])
    threshold = max(width, height) * 0.15
    return (dx * dx + dy * dy) <= threshold * threshold


def _save_clip(frames: list, out_path: str, fps: float, size: tuple[int, int]) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore
    out = cv2.VideoWriter(out_path, fourcc, fps, size)
    for frame in frames:
        out.write(frame)
    out.release()


def _parse_detections(results, player_classes: list[int], ball_class: int, min_conf: float = 0.3) -> tuple[list, list]:
    """Split YOLO results using dynamic classes."""
    detections = []
    balls = []
    for box, cls, conf in zip(
        results[0].boxes.xyxy, results[0].boxes.cls, results[0].boxes.conf
    ):
        cls_i = int(cls)
        conf_f = float(conf)
        if conf_f < min_conf:
            continue
        x1, y1, x2, y2 = map(float, box)
        if cls_i in player_classes:
            if (x2 - x1) >= MIN_W and (y2 - y1) >= MIN_H:
                detections.append([[x1, y1, x2 - x1, y2 - y1], conf_f, cls_i])
        elif cls_i == ball_class:
            balls.append([x1, y1, x2, y2])
    return detections, balls

def _detectar_eventos_bola(
    target_frames: list[int],
    video_metadata: dict,
    target_track_ids: set[str],
    fps: float
) -> list[dict]:

    eventos = []
    ultimo_evento_frame = -999

    EVENT_GAP = int(fps * 1.0)  # 1 segundo entre eventos

    for f_idx in target_frames:
        frame_data = video_metadata.get(f_idx)
        if not frame_data:
            continue

        target_box = None

        for l, t, r, b, tid in frame_data["tracks"]:
            if str(tid) in target_track_ids:
                target_box = [l, t, r, b]
                break

        if not target_box:
            continue

        for ball_box in frame_data["balls"]:
            if _is_ball_near_player(target_box, ball_box):

                # evita spam de eventos
                if f_idx - ultimo_evento_frame > EVENT_GAP:
                    eventos.append({
                        "type": "toque",
                        "frame": f_idx,
                        "time": f_idx / fps
                    })
                    ultimo_evento_frame = f_idx

                break

    return eventos

def process_video(
    video_path: str,
    target_number: int,
    output_dir: str,
    start_ts: int = 0,
    end_ts: int = 0,
    on_player_found: Callable | None = None,
    on_clip_generated: Callable | None = None,
    debug: bool = False,
) -> list[dict]:

    pipeline_start_time = time.time()

    os.makedirs(output_dir, exist_ok=True)
    debug_dir: str | None = None
    if debug:
        debug_dir = os.path.join(output_dir, "debug_ocr")
        os.makedirs(debug_dir, exist_ok=True)

    print(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

    # ==========================================================
    # CARREGAMENTO DO MODELO E AUTO-DISCOVERY DE CLASSES
    # ==========================================================
    model = YOLO("yolov8s.pt")
    player_classes = PLAYER_CLS
    ball_class = BALL_CLS
    yolo_classes = player_classes + [ball_class]
    
    print(f"[model] yolov8s.pt | person_ids={player_classes} ball_id={ball_class}")
    
    # Descobre automaticamente os IDs vasculhando o dicionário interno do modelo
    player_classes = []
    ball_class = None
    
    for class_id, class_name in model.names.items():
        name_lower = class_name.lower()
        if "player" in name_lower or "person" in name_lower or "goalkeeper" in name_lower:
            player_classes.append(class_id)
        elif "ball" in name_lower or "sports ball" in name_lower:
            ball_class = class_id

    # Fallback de segurança se os nomes não forem padrões
    if not player_classes: player_classes = [0]
    if ball_class is None: ball_class = 32
    
    yolo_classes = player_classes + [ball_class]
    print(f"[model] best.pt Auto-Mapped | person_ids={player_classes} ball_id={ball_class}")

    reader = easyocr.Reader(["en"], gpu=USE_GPU)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError("Falha ao abrir vídeo.")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    if vid_w > PROCESS_WIDTH:
        frame_size = (PROCESS_WIDTH, int(vid_h * (PROCESS_WIDTH / vid_w)))
    else:
        frame_size = (vid_w, vid_h)

    cap.set(cv2.CAP_PROP_POS_MSEC, start_ts * 1000)

    # ==========================================================
    # PASSO 1 — EXTRAÇÃO DE METADADOS
    # ==========================================================
    print(f"[1/4] Extraindo metadados com IA ({total_frames} frames)...")
    
    tracker = PlayerTracker()
    jersey_map: dict[str, Counter] = defaultdict(Counter)
    video_metadata: dict[int, dict] = {}
    
    frame_idx = 0
    start_frame_offset = int(start_ts * fps)

    while True:
        ret, frame_orig = cap.read()
        if not ret: break
        
        current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
        if end_ts > 0 and current_msec > end_ts * 1000:
            break
        
        if frame_idx % FRAME_SKIP != 0:
            if frame_idx > 0 and (frame_idx - 1) in video_metadata:
                video_metadata[frame_idx] = video_metadata[frame_idx - 1]
            frame_idx += 1
            continue

        frame = _resize_frame(frame_orig)
        scale = frame_orig.shape[1] / frame.shape[1]

        results = model(frame, classes=yolo_classes, verbose=False, conf=0.3, half=USE_GPU)
        detections, balls = _parse_detections(results, player_classes, ball_class)
        tracks = tracker.update(detections, frame)

        # Conversão segura para numéricos puros (Evita vazamento de memória com DeepSORT)
        safe_tracks = [[float(l), float(t), float(r), float(b), str(tid)] for l, t, r, b, tid in tracks]
        safe_balls = [[float(x1), float(y1), float(x2), float(y2)] for x1, y1, x2, y2 in balls]

        video_metadata[frame_idx] = {
            "tracks": safe_tracks,
            "balls": safe_balls
        }

        if frame_idx % OCR_INTERVAL == 0:
            for l, t, r, b, track_id in tracks:
                ol, ot = int(l * scale), int(t * scale)
                or_, ob = int(r * scale), int(b * scale)

                crop = _torso_crop(frame_orig, ol, ot, or_, ob)
                if crop.shape[0] >= 10 and crop.shape[1] >= 10:
                    numbers = _read_numbers(crop, reader, target_number)

                    # [OTIMIZAÇÃO I/O] Verifica se há números ANTES de iterar e salvar imagens
                    if numbers:
                        for n in numbers:
                            jersey_map[str(track_id)][n] += 1

                        if debug and debug_dir:
                            # Constrói o nome dinâmico para facilitar o visual debugging
                            nums_str = "_".join(map(str, numbers))
                            img_filename = f"ocr_f{frame_idx:05d}_t{track_id}_leu_{nums_str}.png"
                            
                            cv2.imwrite(os.path.join(debug_dir, img_filename), crop)
                            print(f"  [MAP] frame={frame_idx} track={track_id} leu={numbers}")

        frame_idx += 1

    total_processed_frames = frame_idx

    # ==========================================================
    # PASSO 2 - RESOLUÇÃO DE IDs
    # ==========================================================
    print("[2/4] Resolvendo Identidades dos Jogadores...")

    resolved: dict[str, int] = {}
    for tid, counter in jersey_map.items():
        if counter:
            best_num, votes = counter.most_common(1)[0]
            if votes >= MIN_OCR_VOTES:
                resolved[tid] = best_num

    if debug:
        print(f"  [MAP] Detalhado: { {tid: dict(c) for tid, c in jersey_map.items() if c} }")
        print(f"  [MAP] Resolvido: {resolved}")

    target_track_ids: set[str] = {
        tid for tid, num in resolved.items() if num == target_number
    }

    if not target_track_ids:
        for tid, counter in jersey_map.items():
            if counter and counter.most_common(1)[0][0] == target_number:
                target_track_ids.add(tid)
                resolved[tid] = target_number

    if not target_track_ids:
        all_nums = sorted(set(resolved.values())) if resolved else []
        raise ValueError(f"Jogador #{target_number} não encontrado. Identificados: {all_nums}")

    print(f"    ✓ Jogador #{target_number} vinculado aos IDs: {target_track_ids}")
    if on_player_found:
        on_player_found()

    # ==========================================================
    # PASSO 3 — LÓGICA TEMPORAL (Player Cam Definitivo)
    # ==========================================================
    print("[3/4] Calculando intervalos de ação...")

    target_presence_frames = set()

    # Coleta todos os frames onde o jogador aparece
    for f_idx in range(total_processed_frames):
        frame_data = video_metadata.get(f_idx)
        if not frame_data:
            continue

        for l, t, r, b, tid in frame_data["tracks"]:
            if str(tid) in target_track_ids:
                target_presence_frames.add(f_idx)
                break

    # Ordena os frames
    target_frames = sorted(list(target_presence_frames))

    eventos_bola = _detectar_eventos_bola(
                                            target_frames,
                                            video_metadata,
                                            target_track_ids,
                                            fps
                                        )

    print(f"    ⚽ {len(eventos_bola)} interações com a bola detectadas.")

    clip_intervals = []

    if not target_frames:
        print("    [!] O jogador não foi encontrado no vídeo.")
    else:
        current_start = target_frames[0]
        current_end = target_frames[0]

        for f in target_frames[1:]:
            if f - current_end <= GAP_TOLERANCE:
                current_end = f
            else:
                if (current_end - current_start) >= MIN_CLIP_FRAMES:
                    clip_intervals.append((current_start, current_end))
                current_start = f
                current_end = f

        # último bloco
        if (current_end - current_start) >= MIN_CLIP_FRAMES:
            clip_intervals.append((current_start, current_end))

        print(f"    ✓ {len(clip_intervals)} blocos de ação encontrados (Modo Player Cam).")

    # ==========================================================
    # PASSO 4 — FASE DE I/O (Geração de Clipes Fatiados)
    # ==========================================================
    print(f"[4/4] Fatiando vídeo em {len(clip_intervals)} clipes...")
    
    results_list: list[dict] = []

    # Adicionando margem antes e depois da jogada
    PADDING_SECONDS = 2
    padding_frames = int(PADDING_SECONDS + fps)
    
    for idx, (start_f, end_f) in enumerate(clip_intervals):
        padded_start_f = max(0, start_f - padding_frames)
        padded_end_f = min(total_processed_frames - 1, end_f + padding_frames)
        
        absolute_start_f = start_frame_offset + padded_start_f
        cap.set(cv2.CAP_PROP_POS_FRAMES, absolute_start_f)
        
        clip_frames = []
        for f in range(start_f, end_f + 1):
            ret, frame_orig = cap.read()
            if not ret: break
            clip_frames.append(_resize_frame(frame_orig))
            
        start_s = padded_start_f / fps
        end_s = padded_end_f / fps

        clip_name = f"jogador_{target_number}_clipe_{idx+1}_{int(start_s)}s_a_{int(end_s)}s.mp4"
        clip_path = os.path.join(output_dir, clip_name)
        
        clip_events = [
                        e for e in eventos_bola
                        if start_f <= e["frame"] <= end_f
                        ]
        
        _save_clip(clip_frames, clip_path, fps, frame_size)
        
        clip_dict = {
            "path": clip_path,
            "start_ts": start_s,
            "end_ts": end_s,
            "events": clip_events
        }
        results_list.append(clip_dict)
        if on_clip_generated: on_clip_generated(clip_dict)

    cap.release()
    pipeline_end_time = time.time()
    elapsed_seconds = pipeline_end_time - pipeline_start_time
    elapsed_minutes = elapsed_seconds / 60
    
    print(f"\n[MÉTRICAS] Performance do Pipeline:")
    print(f"  -> Total de Frames Analisados: {total_frames}")
    print(f"  -> Tempo Total de Execução: {elapsed_seconds:.2f} segundos ({elapsed_minutes:.2f} minutos)")
    print(f"  -> Clipes Gerados: {len(results_list)}")
    print("[Concluído] Pipeline finalizado com sucesso.")
    return results_list