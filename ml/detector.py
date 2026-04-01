import sys
import os

# adiciona o repo no path
sys.path.append(os.path.join(os.path.dirname(__file__), "football_analysis"))

import cv2

# exemplo (ajuste conforme o repo)
from ultralytics import YOLO

class PlayerDetector:
    def __init__(self):
        self.model = YOLO("yolov8n.pt")  # ou modelo do repo

    def detect(self, frame):
        results = self.model(frame)[0]

        detections = []

        for box in results.boxes:
            cls = int(box.cls[0])

            # filtrar só jogadores (classe person)
            if cls != 0:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])

            detections.append((x1, y1, x2, y2))

        return detections