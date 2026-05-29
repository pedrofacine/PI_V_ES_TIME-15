import cv2
import numpy as np

class ColorExtractor:
    """
    Extrai a cor predominante de uma imagem (ex: crop do torso).
    Usa o algoritmo K-Means para isolar a cor real da camisa,
    ignorando sombras, luzes estouradas e pequenos logos.
    """

    def __init__(self, k: int = 3) -> None:
        self.k = k

    def get_dominant_color_hex(self, image_bgr: np.ndarray) -> str | None:
        if image_bgr is None or image_bgr.size == 0:
            return None

        # Redimensiona para acelerar
        h, w = image_bgr.shape[:2]
        max_dim = 50
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)))

        # Converte para HSV para lidar melhor com luminância
        image_hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        
        # Cria uma máscara removendo Preto (Value < 30) e Branco (Saturation < 30 e Value > 200)
        # Ajuste esses limiares conforme a iluminação do seu jogo
        lower_bound = np.array([0, 30, 30])
        upper_bound = np.array([179, 255, 255])
        mask = cv2.inRange(image_hsv, lower_bound, upper_bound)
        
        # Filtra apenas os pixels válidos. Retornamos para RGB para obtermos o HEX real
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        valid_pixels = image_rgb[mask > 0]
        
        if len(valid_pixels) == 0:
            return None # Fallback se tudo for sombra/estourado

        pixels = valid_pixels.astype(np.float32)

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        best_labels = np.empty(0, dtype=np.int32)

        _, labels, centers = cv2.kmeans(
            pixels, self.k, best_labels, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )
        
        counts = np.bincount(labels.flatten())
        dominant_rgb = centers[np.argmax(counts)]
        r, g, b = [int(c) for c in dominant_rgb]

        return f"#{r:02x}{g:02x}{b:02x}"