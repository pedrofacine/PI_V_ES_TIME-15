import os
import cv2
import numpy as np
import easyocr
from pathlib import Path
from collections import Counter, defaultdict
from ultralytics import YOLO
from scripts.trackers.tracker import PlayerTracker
from typing import Callable

OCR_INTERVAL       = 5
MIN_W, MIN_H       = 30, 50
MIN_CLIP_FRAMES    = 15
GAP_TOLERANCE      = 30
PROCESS_WIDTH      = 640
MIN_OCR_VOTES      = 2
PLAYER_CLS         = [0]
BALL_CLS           = 32

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


def _read_numbers(crop: np.ndarray, reader: easyocr.Reader) -> list[int]:
    """Multi-strategy OCR: color + CLAHE, results merged."""
    h, w = crop.shape[:2]
    if h < 5 or w < 5:
        return []

    big = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    results: set[int] = set()

    for text in reader.readtext(big, allowlist="0123456789", detail=0):
        t = str(text).strip()
        if t.isdigit():
            results.add(int(t))

    gray = cv2.cvtColor(big, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    enhanced = clahe.apply(gray)
    for text in reader.readtext(enhanced, allowlist="0123456789", detail=0):
        t = str(text).strip()
        if t.isdigit():
            results.add(int(t))

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


def _parse_detections(results, min_conf: float = 0.3) -> tuple[list, list]:
    """Split YOLO results into DeepSort-compatible detections and ball boxes."""
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
        if cls_i in PLAYER_CLS:
            if (x2 - x1) >= MIN_W and (y2 - y1) >= MIN_H:
                detections.append([[x1, y1, x2 - x1, y2 - y1], conf_f, cls_i])
        elif cls_i == BALL_CLS:
            balls.append([x1, y1, x2, y2])
    return detections, balls


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

    os.makedirs(output_dir, exist_ok=True)
    debug_dir: str | None = None
    if debug:
        debug_dir = os.path.join(output_dir, "debug")
        os.makedirs(debug_dir, exist_ok=True)

    print(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

    model = YOLO("yolov8n.pt")
    print(f"[model] yolov8n.pt | person={PLAYER_CLS} ball={BALL_CLS}")

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

    yolo_classes = PLAYER_CLS + [BALL_CLS]

    # ==========================================================
    # PASSO 1 — MAPEAMENTO: rastrear todos, OCR em todos (video inteiro)
    # ==========================================================
    print(f"[1/3] Mapeando jogadores ({total_frames} frames, video inteiro)...")

    tracker_map = PlayerTracker()
    jersey_map: dict[str, Counter] = defaultdict(Counter)
    frame_idx = 0

    while True:
        ret, frame_orig = cap.read()
        if not ret:
            break
        if end_ts > 0 and cap.get(cv2.CAP_PROP_POS_MSEC) > end_ts * 1000:
            break

        frame = _resize_frame(frame_orig)
        scale = frame_orig.shape[1] / frame.shape[1]
        frame_idx += 1

        results = model(frame, classes=yolo_classes, verbose=False, conf=0.3)
        detections, _ = _parse_detections(results)
        tracks = tracker_map.update(detections, frame)

        if frame_idx % OCR_INTERVAL != 0:
            continue

        for l, t, r, b, track_id in tracks:
            ol, ot = int(l * scale), int(t * scale)
            or_, ob = int(r * scale), int(b * scale)

            crop = _torso_crop(frame_orig, ol, ot, or_, ob)
            if crop.shape[0] < 10 or crop.shape[1] < 10:
                continue

            numbers = _read_numbers(crop, reader)

            for n in numbers:
                jersey_map[track_id][n] += 1

            if debug and debug_dir:
                cv2.imwrite(
                    os.path.join(debug_dir, f"map_f{frame_idx}_t{track_id}.png"),
                    crop,
                )
                if numbers:
                    print(f"  [MAP] frame={frame_idx} track={track_id} leu={numbers}")

    # ==========================================================
    # RESOLVER MAPA DE CAMISAS
    # ==========================================================
    print("[2/3] Resolvendo mapa de camisas...")

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
        print(f"  [MAP] Números encontrados: {all_nums}")
        raise ValueError(
            f"Jogador #{target_number} não encontrado. Números detectados: {all_nums}"
        )

    print(f"    ✓ Jogador #{target_number} -> track_ids: {target_track_ids}")
    if on_player_found:
        on_player_found()

    # ==========================================================
    # PASSO 2 — GERAR CLIPES (vídeo inteiro, tracker fresco)
    # ==========================================================
    print("[3/3] Gerando clipes...")

    cap.set(cv2.CAP_PROP_POS_MSEC, start_ts * 1000)
    tracker_clip = PlayerTracker()
    clip_jersey: dict[str, Counter] = defaultdict(Counter)
    active_targets: set[str] = set()

    current_clip: list[np.ndarray] = []
    clip_start_frame = 0
    gap_counter = 0
    clip_index = 1
    results_list: list[dict] = []
    frame_idx = 0

    while True:
        ret, frame_orig = cap.read()
        if not ret:
            break
        if end_ts > 0 and cap.get(cv2.CAP_PROP_POS_MSEC) > end_ts * 1000:
            break

        frame = _resize_frame(frame_orig)
        scale = frame_orig.shape[1] / frame.shape[1]
        frame_idx += 1

        results = model(frame, classes=yolo_classes, verbose=False, conf=0.3)
        detections, balls = _parse_detections(results)
        tracks = tracker_clip.update(detections, frame)

        if frame_idx % OCR_INTERVAL == 0:
            for l, t, r, b, track_id in tracks:
                if track_id in active_targets:
                    continue

                ol, ot = int(l * scale), int(t * scale)
                or_, ob = int(r * scale), int(b * scale)
                crop = _torso_crop(frame_orig, ol, ot, or_, ob)
                if crop.shape[0] < 10 or crop.shape[1] < 10:
                    continue

                numbers = _read_numbers(crop, reader)
                for n in numbers:
                    clip_jersey[track_id][n] += 1

                if target_number in numbers:
                    active_targets.add(track_id)
                    if debug:
                        print(
                            f"  [CLIP] Identified track {track_id} "
                            f"as #{target_number} at frame {frame_idx}"
                        )
                elif clip_jersey[track_id].get(target_number, 0) >= MIN_OCR_VOTES:
                    active_targets.add(track_id)
                    if debug:
                        print(
                            f"  [CLIP] Confirmed track {track_id} "
                            f"as #{target_number} by votes at frame {frame_idx}"
                        )

        found_target = False
        target_box: list[float] | None = None
        for l, t, r, b, track_id in tracks:
            if track_id in active_targets:
                target_box = [float(l), float(t), float(r), float(b)]
                found_target = True
                break

        contact = False
        if found_target and target_box and balls:
            for ball_box in balls:
                if _is_ball_near_player(target_box, ball_box):
                    contact = True
                    break

        if contact:
            gap_counter = 0
            if not current_clip:
                clip_start_frame = frame_idx
            current_clip.append(frame)
        else:
            gap_counter += 1
            if gap_counter > GAP_TOLERANCE:
                if len(current_clip) >= MIN_CLIP_FRAMES:
                    start_s = clip_start_frame / fps
                    end_s = frame_idx / fps
                    clip_path = os.path.join(
                        output_dir,
                        f"clip_{clip_index}_{target_number}_{int(start_s)}-{int(end_s)}.mp4",
                    )
                    _save_clip(current_clip, clip_path, fps, frame_size)
                    clip_dict = {
                        "path": clip_path,
                        "start_ts": start_s,
                        "end_ts": end_s,
                    }
                    results_list.append(clip_dict)
                    if on_clip_generated:
                        on_clip_generated(clip_dict)
                    clip_index += 1

                current_clip.clear()
                gap_counter = 0

    if len(current_clip) >= MIN_CLIP_FRAMES:
        start_s = clip_start_frame / fps
        end_s = frame_idx / fps
        clip_path = os.path.join(
            output_dir, f"clip_{clip_index}_{target_number}.mp4"
        )
        _save_clip(current_clip, clip_path, fps, frame_size)
        clip_dict = {"path": clip_path, "start_ts": start_s, "end_ts": end_s}
        results_list.append(clip_dict)
        if on_clip_generated:
            on_clip_generated(clip_dict)

    cap.release()
    return results_list
