from ultralytics import YOLO

# Carregar o modelo treinado
model = YOLO(r"ml/models/best.pt")

# Prever em uma imagem
results = model.predict(r"ml\tests\player_4214.jpg")
