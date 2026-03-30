import os
import cv2
import numpy as np

# =========================
# CONFIG
# =========================
INPUT_DIR = "../dataset/images/train"
#OUTPUT_DIR = "../dataset/images/clean"
OUTPUT_DIR = "../dataset/images/clean_v2"

MIN_WIDTH = 120
MIN_HEIGHT = 220
BLUR_THRESHOLD = 180
BRIGHTNESS_THRESHOLD = 40

# =========================
# SETUP
# =========================
os.makedirs(OUTPUT_DIR, exist_ok=True)

def is_blurry(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()
    return variance < BLUR_THRESHOLD

def is_dark(image):
    brightness = np.mean(image)
    return brightness < BRIGHTNESS_THRESHOLD

# =========================
# PROCESSAMENTO
# =========================
files = os.listdir(INPUT_DIR)

saved = 0
removed = 0

for file in files:
    path = os.path.join(INPUT_DIR, file)

    img = cv2.imread(path)
    if img is None:
        continue

    h, w = img.shape[:2]

    img = img[int(h*0.2):h, 0:w]
    
    h, w = img.shape[:2]

    # filtro tamanho
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        removed += 1
        continue

    # filtro blur
    if is_blurry(img):
        removed += 1
        continue

    # filtro luz
    if is_dark(img):
        removed += 1
        continue

    # salvar imagem boa
    save_path = os.path.join(OUTPUT_DIR, file)
    cv2.imwrite(save_path, img)
    saved += 1

    if saved % 500 == 0:
        print(f"Salvas: {saved} | Removidas: {removed}")

print("FINALIZADO")
print(f"Imagens boas: {saved}")
print(f"Removidas: {removed}")