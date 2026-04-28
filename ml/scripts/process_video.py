"""
Ponto de entrada público do pipeline de análise de vídeos.

Este módulo existe como uma **fachada** (façade pattern) sobre a classe
`VideoPipeline`, preservando retrocompatibilidade com código existente
(especialmente `backend/app/routers/jobs.py`) que importa a função
`process_video` diretamente.

Toda a lógica real está em classes isoladas:
    - VideoPipeline: orquestração do fluxo
    - YoloDetector: detecção de jogadores e bola
    - PlayerTracker: tracking entre frames
    - JerseyReader: OCR do número da camisa
    - BallEventDetector: detecção de toques na bola
    - ClipWriter: escrita dos clipes em MP4

Para usar a API orientada a classe diretamente (recomendado em código novo):

    from scripts.video_pipeline import VideoPipeline

    pipeline = VideoPipeline()
    clips = pipeline.process(video_path="entrada.mp4", target_number=10, ...)
"""
from typing import Callable

from ml.scripts.video_pipeline import VideoPipeline


# Instância única reutilizada entre chamadas.
# Modelos pesados (YOLO, EasyOCR) ficam em memória, evitando recarregar
# a cada vídeo processado. Inicialização preguiçosa (lazy): só é criada
# na primeira chamada de process_video().
_pipeline: VideoPipeline | None = None


def _get_pipeline() -> VideoPipeline:
    """Retorna a instância singleton do pipeline, criando se necessário."""
    global _pipeline
    if _pipeline is None:
        _pipeline = VideoPipeline()
    return _pipeline


def process_video(
    video_path: str,
    target_number: int,
    output_dir: str,
    start_ts: int = 0,
    end_ts: int = 0,
    on_player_found: Callable | None = None,
    on_clip_generated: Callable | None = None,
    debug: bool = False,
) -> list[dict]:
    """
    Processa um vídeo e gera clipes focados no jogador-alvo.

    Mantém a mesma assinatura da versão anterior (pré-refatoração)
    para compatibilidade com `jobs.py` e qualquer outro código que
    importe esta função.

    Args:
        video_path: Caminho do arquivo de vídeo de entrada.
        target_number: Número da camisa do jogador a rastrear.
        output_dir: Pasta onde os clipes gerados serão salvos.
        start_ts: Segundo de início do processamento (default: 0).
        end_ts: Segundo de fim do processamento (0 = até o fim).
        on_player_found: Callback disparado quando o jogador é identificado.
        on_clip_generated: Callback disparado a cada clipe salvo.
        debug: Se True, salva crops de debug em `{output_dir}/debug_ocr/`.

    Returns:
        Lista de dicionários, cada um descrevendo um clipe gerado:
          {
              "path": str,           # caminho absoluto do .mp4
              "start_ts": float,     # início em segundos
              "end_ts": float,       # fim em segundos
              "events": list[dict],  # eventos de bola dentro do clipe
          }

    Raises:
        ValueError: Se o vídeo não puder ser aberto ou o jogador-alvo
                    não for encontrado no trecho processado.
    """
    pipeline = _get_pipeline()
    return pipeline.process(
        video_path=video_path,
        target_number=target_number,
        output_dir=output_dir,
        start_ts=start_ts,
        end_ts=end_ts,
        on_player_found=on_player_found,
        on_clip_generated=on_clip_generated,
        debug=debug,
    )