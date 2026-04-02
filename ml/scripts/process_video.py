"""
Pipeline de processamento de vídeo:
  1. YOLO detecta pessoas frame a frame
  2. EasyOCR lê número da camisa nos crops
  3. Após encontrar o jogador, rastreia por IoU
  4. Corta clipes dos trechos em que ele aparece
  5. Retorna lista de dicts {path, start_ts, end_ts}
"""

from csv import reader

from scripts.trackers.tracker import PlayerTracker
import os
import cv2
import numpy as np
import easyocr
from pathlib import Path
from ultralytics import YOLO



FRAME_SKIP         = 2
#OCR_SEARCH_FRAMES  = 1200
MIN_W, MIN_H       = 60, 120
MIN_CLIP_FRAMES    = 15
GAP_TOLERANCE      = 30
IOU_THRESHOLD      = 0.25
PROCESS_WIDTH      = 1280   # redimensiona frames maiores que isso antes de processar

ML_ROOT = Path(__file__).resolve().parents[1]  # "ml"
MODEL_PATH = ML_ROOT / "models" / "best.pt"
tracker = PlayerTracker()

try:
    import torch
    USE_GPU = torch.cuda.is_available()
except ImportError:
    USE_GPU = False


def _resize_frame(frame: np.ndarray) -> np.ndarray:
    """Redimensiona o frame para PROCESS_WIDTH se for maior."""
    h, w = frame.shape[:2]
    if w > PROCESS_WIDTH:
        scale = PROCESS_WIDTH / w
        frame = cv2.resize(frame, (PROCESS_WIDTH, int(h * scale)))
    return frame


def preprocess_crop_for_ocr(crop: np.ndarray) -> np.ndarray:
    """Aumenta e melhora o contraste do crop para facilitar o OCR."""
    h, w = crop.shape[:2]
    crop = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def _iou(a: list, b: list) -> float:
    """Calcula IoU entre dois bboxes [x1, y1, x2, y2]."""
    xa = max(a[0], b[0]); ya = max(a[1], b[1])
    xb = min(a[2], b[2]); yb = min(a[3], b[3])
    inter = max(0, xb - xa) * max(0, yb - ya)
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / float(area_a + area_b - inter)


def _read_numbers(crop: np.ndarray, reader: easyocr.Reader) -> list[int]:
    """Retorna lista de números encontrados no crop via OCR."""
    crop    = preprocess_crop_for_ocr(crop)
    results = reader.readtext(crop, allowlist="0123456789", detail=0)
    numbers = []
    for text in results:
        text = text.strip()
        if text.isdigit():
            numbers.append(int(text))
    return numbers


def _save_clip(frames: list, out_path: str, fps: float, size: tuple[int, int]) -> None:
    """Salva lista de frames como arquivo .mp4."""
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out    = cv2.VideoWriter(out_path, fourcc, fps, size)
    for frame in frames:
        out.write(frame)
    out.release()


def _get_person_boxes(results) -> list[list[float]]:
    """Extrai bboxes de pessoas (classe 0) dos resultados do YOLO."""
    boxes = []
    for box, cls in zip(results[0].boxes.xyxy, results[0].boxes.cls):
        if int(cls) != 0:
            continue
        x1, y1, x2, y2 = map(float, box)
        if (x2 - x1) >= MIN_W and (y2 - y1) >= MIN_H:
            boxes.append([x1, y1, x2, y2])
    return boxes


def process_video(
    video_path: str,
    target_number: int,
    output_dir: str,
    start_ts: int = 0,
    end_ts: int = 0
) -> list[dict]:
    """
    Processa o vídeo e retorna lista de dicts:
      [{ "path": str, "start_ts": float, "end_ts": float }, ...]
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"[GPU] {'Ativada' if USE_GPU else 'Desativada — usando CPU'}")

    model  = YOLO("yolov8n.pt")
    reader = easyocr.Reader(["en"], gpu=USE_GPU)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Não foi possível abrir o vídeo: {video_path}")

    fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    start_msec = start_ts * 1000
    end_msec   = end_ts * 1000
    cap.set(cv2.CAP_PROP_POS_MSEC, start_msec)
    frame_count = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

    # Tamanho final dos clipes (respeitando redimensionamento)
    if vid_w > PROCESS_WIDTH:
        scale      = PROCESS_WIDTH / vid_w
        frame_size = (PROCESS_WIDTH, int(vid_h * scale))
    else:
        frame_size = (vid_w, vid_h)

  
    print(f"[1/3] Procurando jogador #{target_number}...")

    target_box    = None
    frame_count   = 0
    search_frames = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)
        
        # Condição de parada: passamos do tempo de fim e não achou o jogador
        if end_msec > 0 and current_msec > end_msec:
            raise ValueError(f"Jogador #{target_number} não encontrado no trecho selecionado ({start_ts}s - {end_ts}s).")

        frame = _resize_frame(frame)
        frame_count += 1

        if frame_count % FRAME_SKIP != 0:
            continue

        results = model(frame, verbose=False)
        boxes   = _get_person_boxes(results)

        for box in boxes:
            x1, y1, x2, y2 = map(int, box)
            crop    = frame[y1:y2, x1:x2]
            numbers = _read_numbers(crop, reader)

            if target_number in numbers:
                target_box = box
                print(f"    ✓ Jogador encontrado no frame {frame_count}!")
                break

        if target_box:
            break

    if target_box is None:
        raise ValueError(f"Jogador #{target_number} não encontrado no vídeo.")

   
    print("[2/3] Rastreando jogador...")

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_count - 1)

    clips_data:      list[tuple[list, int, int]] = []
    current_clip:    list = []
    clip_start_frame = 0
    gap_counter      = 0
    tracking_frame   = frame_count - 1
    target_id:       int | None = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        current_msec = cap.get(cv2.CAP_PROP_POS_MSEC)

        # Condição de parada: atingimos o tempo de fim definido pelo usuário
        if end_msec > 0 and current_msec > end_msec:
            break

        frame = _resize_frame(frame)   # redimensiona antes de tudo
        tracking_frame += 1

        results  = model(frame, verbose=False)
        boxes    = _get_person_boxes(results)

        # roda tracker no frame atual
        # Converter boxes para formato esperado pelo PlayerTracker
        detections = []
        for box in boxes:
            x1, y1, x2, y2 = box
            # Formato: (x1, y1, x2, y2, confidence, class_id)
            detections.append([[x1, y1, x2, y2], 0.9, 0])  # bbox, confidence, class_id
        
        tracks = tracker.update(detections, frame)
        
        # Converter tracks para formato esperado pelo código
        players = []
        for track in tracks:
            x1, y1, x2, y2, track_id = track
            players.append({
                "track_id": track_id,
                "bbox": [x1, y1, x2, y2]
            })

        # Inicializa target_id no primeiro frame de tracking usando IoU com a box encontrada
        if target_id is None and target_box is not None:
            for player in players:
                if _iou(player["bbox"], target_box) >= IOU_THRESHOLD:
                    target_id = player["track_id"]
                    break

        found = False

        for player in players:
            track_id = player["track_id"]
            x1, y1, x2, y2 = player["bbox"]

            if target_id is not None:
                if track_id == target_id:
                    target_box = [x1, y1, x2, y2]
                    found = True
                    break
            else:
                # fallback: OCR sobre cada player (raramente usado quando já achou no primeiro estágio)
                crop = frame[y1:y2, x1:x2]
                numbers = _read_numbers(crop, reader)
                if target_number in numbers:
                    target_id = track_id
                    target_box = [x1, y1, x2, y2]
                    found = True
                    break

        if found:
            gap_counter = 0

            if not current_clip:
                clip_start_frame = tracking_frame

            current_clip.append(frame.copy())
        else:
            gap_counter += 1

            if gap_counter > GAP_TOLERANCE:
                if len(current_clip) >= MIN_CLIP_FRAMES:
                    clips_data.append((current_clip, clip_start_frame, tracking_frame))
                current_clip = []
                gap_counter  = 0

    if current_clip and len(current_clip) >= MIN_CLIP_FRAMES:
        clips_data.append((current_clip, clip_start_frame, tracking_frame))

    results = []
    for i, (frames_clip, start_frame, end_frame) in enumerate(clips_data, start=1):
        start_ts = start_frame / fps
        end_ts = end_frame / fps
        clip_filename = f"clip_{i}_{target_number}_{int(start_ts)}-{int(end_ts)}.mp4"
        clip_path = os.path.join(output_dir, clip_filename)
        _save_clip(frames_clip, clip_path, fps, frame_size)
        results.append({"path": clip_path, "start_ts": start_ts, "end_ts": end_ts})

    return results


if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 4:
        print("Uso: python process_video.py <video_path> <numero_camisa> <output_dir>")
        print("Ex:  python process_video.py ../videos/jogo.mp4 11 ../output/clips")
        sys.exit(1)

    result = process_video(
        video_path=sys.argv[1],
        target_number=int(sys.argv[2]),
        output_dir=sys.argv[3],
    )

    print(json.dumps(result, indent=2))