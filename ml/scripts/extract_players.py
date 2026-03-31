import cv2
import os
from ultralytics import YOLO

# =========================
# CONFIG
# =========================
VIDEO_PATH = "../videos/jogo.mp4"
OUTPUT_DIR = "../dataset/images/train"

MIN_WIDTH = 60     # largura mínima do jogador
MIN_HEIGHT = 120   # altura mínima do jogador
FRAME_SKIP = 5     # pegar 1 frame a cada N (reduz duplicados)

# =========================
# SETUP
# =========================
os.makedirs(OUTPUT_DIR, exist_ok=True)

model = YOLO("yolov8n.pt")  # pode trocar por yolov8s depois

cap = cv2.VideoCapture(r"C:\Users\danie\PI_V_ES_TIME-15\ml\videos\JOGO-SUB-17-S-E-JUVENTUDE-X-E-C-CASTELO.mp4")

frame_count = 0
img_count = 0

# =========================
# LOOP
# =========================
while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    # pular frames pra evitar imagens repetidas
    if frame_count % FRAME_SKIP != 0:
        continue

    results = model(frame)

    for box, cls in zip(results[0].boxes.xyxy, results[0].boxes.cls):

        # filtrar só pessoas (classe 0 no COCO)
        if int(cls) != 0:
            continue

        x1, y1, x2, y2 = map(int, box)

        w = x2 - x1
        h = y2 - y1

        # filtro de tamanho (evita jogadores muito pequenos)
        if w < MIN_WIDTH or h < MIN_HEIGHT:
            continue

        crop = frame[y1:y2, x1:x2]

        # salvar imagem
        filename = f"{OUTPUT_DIR}/player_{img_count}.jpg"
        cv2.imwrite(filename, crop)

        img_count += 1

    print(f"Frame: {frame_count} | Imagens salvas: {img_count}")

cap.release()
print("Finalizado!")