from ultralytics import YOLO

model = YOLO("yolov8n.pt")  # ou "yolo11s.pt" se você tiver
model.train(
    data="C:\\Users\\danie\\Downloads\\Smart Scout.v1i.yolov8\\data.yaml",
    epochs=50,
    imgsz=640,
    batch=16,
    name="numbers_local"
)