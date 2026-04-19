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
        """
        Analisa a imagem e retorna a cor predominante em formato HEX (ex: '#FF0000').
        """
        if image_bgr is None or image_bgr.size == 0:
            return None

        # 1. Redimensiona para acelerar o processamento
        h, w = image_bgr.shape[:2]
        max_dim = 50
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            image_bgr = cv2.resize(image_bgr, (int(w * scale), int(h * scale)))

        # 2. Converte para RGB
        image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

        # 3. Prepara os dados para o K-Means preservando a tipagem de matriz
        pixels = image_rgb.reshape((-1, 3)).astype(np.float32)

        # 4. Critérios de parada: (type, max_iter, epsilon)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)

        # 5. O TRUQUE: Passamos uma matriz vazia em vez de None para agradar o Pylance
        best_labels = np.empty(0, dtype=np.int32)

        # Roda o algoritmo (Zero erros no Pylance!)
        _, labels, centers = cv2.kmeans(
            pixels, self.k, best_labels, criteria, 10, cv2.KMEANS_RANDOM_CENTERS
        )
        
        # 6. Conta os pixels de cada grupo (cluster)
        labels = labels.flatten()
        counts = np.bincount(labels)
        dominant_cluster_index = int(np.argmax(counts))

        # 7. Extrai a cor do grupo vencedor
        dominant_rgb = centers[dominant_cluster_index]
        r, g, b = [int(c) for c in dominant_rgb]

        return f"#{r:02x}{g:02x}{b:02x}"