"""
Configurações centralizadas do pipeline de análise de vídeos.

Todos os parâmetros ajustáveis estão aqui para facilitar tuning
sem precisar mexer na lógica de negócio.
"""
from pathlib import Path
import logging
import os
import uuid
from datetime import datetime

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
NUMBER_MODEL_PATH = MODELS_DIR / "best.pt"
BALL_MODEL_PATH = MODELS_DIR / "ball_tracker.pt"

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
TORSO_Y_START = 0.10
TORSO_Y_END = 0.65

# Fator de upscale do crop antes do OCR (maior = melhor, mas mais lento)
OCR_UPSCALE_FACTOR = 3

# Tamanho mínimo do crop para rodar OCR (abaixo disso, descartamos)
# 35px filtra crops de torcedores parcialmente visíveis na arquibancada
MIN_CROP_H = 15
MIN_CROP_W = 8


# ==========================================================
# RESOLUÇÃO DE IDs DOS JOGADORES
# ==========================================================
# Número mínimo de votos (leituras consistentes) para "confirmar" um número
MIN_OCR_VOTES = 3.5

# Máximo de números distintos que um track pode ter lido e ainda ser considerado
# Tracks com muita variação (ex: torcedores) são descartados antes da resolução
MAX_DISTINCT_READINGS = 9


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

# Tolerâncias de Distancia de cor (Euclidiana no espaço LAB)
FAST_SCAN_COLOR_TOLERANCE = 35  # Muito rigoroso para evitar misturar times na UI
TRACKING_COLOR_TOLERANCE = 65   # Um pouco mais flexível para manter o tracking ativo na sombra


# ==========================================================
# FILTRAGEM DE OVERLAY DE TRANSMISSÃO E BBOXES INVÁLIDAS
# ==========================================================
# Dead zone no topo do frame (overlay de placar superior)
SCOREBOARD_ZONE_TOP = 0.10

# Dead zone na base do frame (overlay de placar inferior)
SCOREBOARD_ZONE_BOTTOM = 0.10

# Aspect ratio máximo (largura/altura) — bboxes mais largos são descartados
# Filtra bboxes panorâmicas geradas pelo tracker e overlays horizontais
MAX_PLAYER_ASPECT_RATIO = 2.5


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

# ==========================================================
# LOGGER
# ==========================================================

def setup_pipeline_logger(output_dir: str, debug_mode: bool = False) -> tuple[logging.Logger, str]:
    """
    Configura e retorna uma instância de logger com múltiplos destinos (ecrã e ficheiro).
    Gera um Session ID único para garantir a rastreabilidade da execução.
    
    Args:
        output_dir: Diretório onde o ficheiro .log será guardado.
        debug_mode: Se True, o ecrã também exibe mensagens DEBUG.
        
    Returns:
        Um tuplo contendo a instância do Logger e o Session ID gerado.
    """
    session_id = uuid.uuid4().hex
    
    # Instancia o logger com um nome único para esta sessão
    logger = logging.getLogger(f"VideoPipeline_{session_id}")
    logger.setLevel(logging.DEBUG) # O logger raiz aceita tudo

    logger.propagate = False

    # Previne duplicação de logs caso a função seja chamada múltiplas vezes no mesmo contexto
    if logger.hasHandlers():
        logger.handlers.clear()

    # ==========================================
    # HANDLER 1: Console (Terminal)
    # ==========================================
    console_handler = logging.StreamHandler()
    # No terminal, mostramos INFO, ou DEBUG se a flag for ativada
    console_handler.setLevel(logging.DEBUG if debug_mode else logging.INFO)
    # Formato limpo e direto para leitura humana rápida
    console_format = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # ==========================================
    # HANDLER 2: File (Ficheiro Permanente)
    # ==========================================
    log_dir = os.path.join(output_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(log_dir, f"run_{timestamp}_{session_id[:8]}.log")
    
    file_handler = logging.FileHandler(log_filename, mode='w', encoding='utf-8')
    # O ficheiro guarda SEMPRE o nível máximo de detalhe (DEBUG)
    file_handler.setLevel(logging.DEBUG)
    # Formato altamente verboso, ideal para análise forense e debugging post-mortem
    file_format = logging.Formatter('%(asctime)s | %(levelname)-8s | PID:%(process)d | %(funcName)s:%(lineno)d | %(message)s')
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger, session_id