import os
import cv2
import numpy as np
import easyocr
from pathlib import Path
from ultralytics import YOLO
from scripts.trackers.tracker import PlayerTracker
from typing import Callable

FRAME_SKIP         = 5
MIN_W, MIN_H       = 40, 80       # Reduzido para acompanhar a redução da imagem
MIN_CLIP_FRAMES    = 15
GAP_TOLERANCE      = 30
IOU_THRESHOLD      = 0.25
PROCESS_WIDTH      = 640          # OTIMIZAÇÃO 1: 640px é o limite ideal para CPU/YOLO

ML_ROOT = Path(__file__).resolve().parents[1]
tracker = PlayerTracker()

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

def preprocess_crop_for_ocr(crop: np.ndarray) -> np.ndarray:
    h, w = crop.shape[:2]
    crop = cv2.resize(crop, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.equalizeHist(gray)

def _iou(a: list, b: list) -> float:
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0: return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)

def _read_numbers(crop: np.ndarray, reader: easyocr.Reader) -> list[int]:
    crop = preprocess_crop_for_ocr(crop)
    results = reader.readtext(crop, allowlist="0123456789", detail=0)
    return [int(str(text).strip()) for text in results if str(text).strip().isdigit()]

def _save_clip(frames: list, out_path: str, fps: float, size: tuple[int, int]) -> None:
    fourcc = cv2.VideoWriter_fourcc(*"mp4v") # type: ignore
    out = cv2.VideoWriter(out_path, fourcc, fps, size)
    for frame in frames: out.write(frame)
    out.release()

def process_video(
    video_path: str,
    target_number: int,
    output_dir: str,
    start_ts: int = 0,
    end_ts: int = 0,
    on_player_found: Callable | None = None,
    on_clip_generated: Callable | None = None # OTIMIZAÇÃO 2: Callback de geração de clipe
) -> list[dict]:
    
    os.makedirs(output_dir, exist_ok=True)
    print(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

    model  = YOLO("yolov8n.pt")
    reader = easyocr.Reader(["en"], gpu=USE_GPU)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened(): raise ValueError("Falha ao abrir vídeo.")

    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    cap.set(cv2.CAP_PROP_POS_MSEC, start_ts * 1000)
    
    frame_size = (PROCESS_WIDTH, int(vid_h * (PROCESS_WIDTH / vid_w))) if vid_w > PROCESS_WIDTH else (vid_w, vid_h)

    print(f"[1/3] Procurando jogador #{target_number}...")
    target_box = None
    frame_count = 0

    # FASE 1: BUSCA
    while True:
        ret, frame = cap.read()
        if not ret or (end_ts > 0 and cap.get(cv2.CAP_PROP_POS_MSEC) > end_ts * 1000): break
        
        frame = _resize_frame(frame)
        frame_count += 1
        if frame_count % FRAME_SKIP != 0: continue

        results = model(frame, verbose=False, conf=0.4) # Confiança p/ CPU
        
        for box in results[0].boxes.xyxy:
            x1, y1, x2, y2 = map(int, box)
            if (x2 - x1) < MIN_W or (y2 - y1) < MIN_H: continue
            
            crop = frame[y1:y2, x1:x2]
            if target_number in _read_numbers(crop, reader):
                target_box = [x1, y1, x2, y2]
                print(f"    ✓ Jogador encontrado no frame {frame_count}!")
                break
        if target_box: break

    if not target_box: raise ValueError("Jogador não encontrado.")
    if on_player_found: on_player_found()

    print("[2/3] Rastreando jogador...")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)

    current_clip = []
    clip_start_frame = 0
    gap_counter = 0
    tracking_frame = frame_count - 1
    target_id = None
    clip_index = 1
    results_list = []

    # FASE 2: RASTREAMENTO
    while True:
        ret, frame = cap.read()
        if not ret or (end_ts > 0 and cap.get(cv2.CAP_PROP_POS_MSEC) > end_ts * 1000): break
        
        frame = _resize_frame(frame)
        tracking_frame += 1
        
        results = model(frame, verbose=False, conf=0.4)
        
        detections = []
        for box in results[0].boxes.xyxy:
            x1, y1, x2, y2 = map(float, box)
            detections.append([[x1, y1, x2-x1, y2-y1], 0.9, 0])
        
        tracks = tracker.update(detections, frame)
        players = [{"track_id": t[4], "bbox": [t[0], t[1], t[2], t[3]]} for t in tracks]

        if target_id is None and target_box is not None:
            for p in players:
                if _iou(p["bbox"], target_box) >= IOU_THRESHOLD:
                    target_id = p["track_id"]
                    break

        found = False
        for p in players:
            if target_id == p["track_id"]:
                target_box = p["bbox"]
                found = True
                break
            
            # OTIMIZAÇÃO 3: Fallback de OCR roda apenas a cada 5 frames para poupar CPU
            elif target_id is None and tracking_frame % 5 == 0:
                x1, y1, x2, y2 = map(int, p["bbox"])
                crop = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
                if crop.shape[0] >= MIN_H and crop.shape[1] >= MIN_W:
                    if target_number in _read_numbers(crop, reader):
                        target_id = p["track_id"]
                        target_box = p["bbox"]
                        found = True
                        break

        if found:
            gap_counter = 0
            if not current_clip: clip_start_frame = tracking_frame
            current_clip.append(frame) # Mantém referência em memória
        else:
            gap_counter += 1
            if gap_counter > GAP_TOLERANCE:
                if len(current_clip) >= MIN_CLIP_FRAMES:
                    # OTIMIZAÇÃO 4: Grava, envia pro front e limpa a memória imediatamente!
                    start_s = clip_start_frame / fps
                    end_s = tracking_frame / fps
                    clip_path = os.path.join(output_dir, f"clip_{clip_index}_{target_number}_{int(start_s)}-{int(end_s)}.mp4")
                    
                    _save_clip(current_clip, clip_path, fps, frame_size)
                    clip_dict = {"path": clip_path, "start_ts": start_s, "end_ts": end_s}
                    results_list.append(clip_dict)
                    
                    if on_clip_generated: on_clip_generated(clip_dict) # ATUALIZA O FRONT
                    clip_index += 1
                
                current_clip.clear() # LIBERA MEMÓRIA RAM
                gap_counter = 0
                target_id = None 

    # Salva o resíduo se o vídeo acabar no meio de um lance
    if len(current_clip) >= MIN_CLIP_FRAMES:
        start_s = clip_start_frame / fps
        end_s = tracking_frame / fps
        clip_path = os.path.join(output_dir, f"clip_{clip_index}_{target_number}.mp4")
        _save_clip(current_clip, clip_path, fps, frame_size)
        clip_dict = {"path": clip_path, "start_ts": start_s, "end_ts": end_s}
        results_list.append(clip_dict)
        if on_clip_generated: on_clip_generated(clip_dict)

    return results_list