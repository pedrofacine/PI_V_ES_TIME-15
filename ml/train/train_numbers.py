from ultralytics import YOLO

model = YOLO("yolov8s.pt")  # modelo mais forte

model.train(
    data="C:\\Users\\danie\\Downloads\\Smart Scout.v1i.yolov8\\data.yaml",
    epochs=100,          
    imgsz=1024,         
    batch=8,             
    name="numbers_v2",
    patience=30,         
    workers=4            
)