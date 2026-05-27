# ADR-001: Padrão Facade em VideoPipeline

**Status:** Aceito  
**Data:** 2026-05-27  
**Decisores:** Equipe PI_V_ES_TIME-15  
**Referência:** Nygard, M. (2011). *Documenting Architecture Decisions*. Cognitect.

---

## Contexto

O sistema de análise de vídeo envolve múltiplos subsistemas independentes: detecção de jogadores (YOLO), leitura de camisa (EasyOCR), rastreamento (DeepSort), escrita de clipes (FFmpeg/cv2), extração de cor (K-means), análise cinemática e detecção de eventos de bola. Cada subsistema possui sua própria interface, configuração e ciclo de vida.

Os clientes externos — `process_video.py` (singleton de produção) e `fast_scan.py` (endpoint FastAPI) — precisam de um ponto de entrada único e estável para orquestrar todo o processamento, sem precisar conhecer os subsistemas internos.

## Decisão

Aplicar o padrão **Facade** (GoF Estrutural, Gamma et al., 1994) na classe `VideoPipeline`.

`VideoPipeline` expõe exatamente dois pontos de entrada públicos:
- `process(video_path, target_number, output_dir, ...)` — processamento completo com extração de clipes
- `fast_scan(video_path, output_dir, target_number, frames_to_skip)` — varredura rápida para candidatos

Toda a orquestração interna entre detectores, leitores e escritores é encapsulada nos métodos privados da classe.

## Consequências

**Positivas:**
- Clientes dependem de uma interface estável com dois métodos; mudanças internas são transparentes.
- O acoplamento entre camadas (backend ↔ ML) é minimizado: o roteador FastAPI não importa nenhum subsistema de ML diretamente.
- Testabilidade aumentada: a fachada aceita injeção de dependência via `__init__` (ver ADR-002).

**Negativas / Trade-offs:**
- `VideoPipeline` concentra responsabilidade de orquestração; risco de crescimento se etapas novas não forem delegadas corretamente.
- Clientes que precisam de controle fino sobre subsistemas específicos precisam contornar a fachada.

## Alternativas Consideradas

| Alternativa | Razão da Rejeição |
|---|---|
| Funções livres por subsistema | Forçaria o cliente a conhecer e orquestrar cada subsistema — acoplamento alto. |
| Classe separada por etapa (ex.: `ClipExtractor`, `PlayerFinder`) | Aumentaria a superfície de API; requereria que o cliente entendesse a ordem de chamada. |
