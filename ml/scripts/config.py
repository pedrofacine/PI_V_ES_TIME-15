"""
Configurações centralizadas do pipeline de análise de vídeos.

Todos os parâmetros ajustáveis estão aqui para facilitar tuning
sem precisar mexer na lógica de negócio.
"""
from pathlib import Path


# ==========================================================
# CAMINHOS
# ==========================================================
ML_ROOT = Path(__file__).resolve().parents[1]
MODELS_DIR = ML_ROOT / "models"


# ==========================================================
# MODELO YOLO
# ==========================================================
# Modelo padrão. Troque para ML_ROOT / "models" / "best.pt"
# quando quiser usar o modelo customizado para futebol.
DEFAULT_MODEL_PATH = "yolov8s.pt"

# IDs de classe quando usando modelo COCO padrão
COCO_PERSON_CLS = [0]
COCO_BALL_CLS = 32

# Threshold mínimo de confiança das detecções do YOLO
YOLO_MIN_CONF = 0.3


# ==========================================================
# FILTROS DE DETECÇÃO
# ==========================================================
# Tamanho mínimo do bounding box de jogador (em pixels da imagem processada)
MIN_PLAYER_W = 30
MIN_PLAYER_H = 50


# ==========================================================
# PROCESSAMENTO DE FRAMES
# ==========================================================
# Largura máxima da imagem que entra no YOLO (maior = mais preciso, mais lento)
PROCESS_WIDTH = 640

# Analisa 1 a cada N frames no loop principal
FRAME_SKIP = 2

# Roda OCR a cada N frames (sobre os frames já filtrados por FRAME_SKIP)
OCR_INTERVAL = 5


# ==========================================================
# OCR (LEITURA DO NÚMERO DA CAMISA)
# ==========================================================
# Confiança mínima para aceitar uma leitura do EasyOCR
OCR_MIN_CONFIDENCE = 0.40

# Região vertical do bbox que contém o torso (% da altura total)
# Exemplo: (0.15, 0.55) = do 15% ao 55% da altura do bbox
TORSO_Y_START = 0.15
TORSO_Y_END = 0.55

# Fator de upscale do crop antes do OCR (maior = melhor, mas mais lento)
OCR_UPSCALE_FACTOR = 3

# Tamanho mínimo do crop para rodar OCR (abaixo disso, descartamos)
MIN_CROP_H = 10
MIN_CROP_W = 10


# ==========================================================
# RESOLUÇÃO DE IDs DOS JOGADORES
# ==========================================================
# Número mínimo de votos (leituras consistentes) para "confirmar" um número
MIN_OCR_VOTES = 2


# ==========================================================
# GERAÇÃO DE CLIPES
# ==========================================================
# Número mínimo de frames contíguos para considerar um clipe válido
MIN_CLIP_FRAMES = 30

# Tolerância de "buracos" (frames sem o jogador) dentro de um mesmo clipe
GAP_TOLERANCE = 120

# Padding em segundos aplicado antes e depois de cada clipe
CLIP_PADDING_SECONDS = 6


# ==========================================================
# DETECÇÃO DE EVENTOS (TOQUES NA BOLA)
# ==========================================================
# Expansão do bounding box do jogador para detectar bola próxima (fração do bbox)
BALL_PROXIMITY_PAD = 0.2

# Distância máxima entre bola e bbox expandido (fração do maior lado do bbox)
BALL_PROXIMITY_THRESHOLD = 0.15

# IoU mínimo entre bbox do jogador e da bola para detectar contato direto
BALL_IOU_THRESHOLD = 0.01

# Intervalo mínimo entre dois eventos (em segundos, evita spam)
EVENT_MIN_GAP_SECONDS = 1.0


# ==========================================================
# ENCODING DE VÍDEO
# ==========================================================
# Qualidade do ffmpeg (menor = melhor qualidade, maior arquivo)
FFMPEG_CRF = 23
FFMPEG_PRESET = "fast"


# ==========================================================
# ANÁLISE CINEMÁTICA (ANOMALIAS DE VELOCIDADE/ACELERAÇÃO)
# ==========================================================
# Piso mínimo de velocidade (px/frame) para considerar anomalia
KINEMATIC_MIN_VELOCITY = 15.0

# Piso mínimo de aceleração (px/frame²) para considerar anomalia
KINEMATIC_MIN_ACCEL = 8.0

# Número de desvios-padrão acima da média para flagiar como anomalia
KINEMATIC_STD_MULTIPLIER = 2.5

# Cooldown mínimo entre dois eventos do mesmo track (segundos)
KINEMATIC_COOLDOWN_SECONDS = 1.5


# ==========================================================
# GPU
# ==========================================================
def _check_gpu() -> bool:
    """Verifica se CUDA está disponível. Falha silenciosamente se torch não instalado."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


USE_GPU = _check_gpu()