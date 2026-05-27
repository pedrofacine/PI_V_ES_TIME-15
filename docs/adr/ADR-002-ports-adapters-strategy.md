# ADR-002: Ports & Adapters com Padrão Strategy

**Status:** Aceito  
**Data:** 2026-05-27  
**Decisores:** Equipe PI_V_ES_TIME-15  
**Referência:** Nygard, M. (2011). *Documenting Architecture Decisions*. Cognitect.

---

## Contexto

`VideoPipeline` dependia diretamente das classes concretas `YoloDetector`, `JerseyReader`, `BallDetector`, etc. Isso impedia:
1. **Testes unitários** sem carregar modelos YOLO/OCR (custo: ~10 s de carregamento, dependência de GPU).
2. **Extensibilidade**: trocar o detector por RT-DETR ou um stub de teste requeria modificar `VideoPipeline`.
3. **Injeção de dependência**: a classe criava suas próprias dependências — violação do Princípio de Inversão de Dependência (DIP).

## Decisão

Adotar **Arquitetura Hexagonal (Ports & Adapters)** (Cockburn, 2005) combinada com o padrão **Strategy** (GoF Comportamental).

Cada componente externo é definido por um `Protocol` (`runtime_checkable`) em `ml/scripts/ports.py`:

- `PlayerDetectorPort` — estratégia de detecção de jogadores
- `BallDetectorPort` — estratégia de detecção da bola
- `JerseyReaderPort` — estratégia de leitura de camisa
- `ClipWriterPort` — estratégia de escrita de clipe
- `ColorExtractorPort` — estratégia de extração de cor
- `KinematicAnalyzerPort` — estratégia de análise cinemática
- `BallEventDetectorPort` — estratégia de detecção de eventos

`VideoPipeline.__init__` recebe todos os componentes como parâmetros keyword-only com padrão `None`; se omitidos, instancia a implementação concreta padrão.

```python
def __init__(self, *, detector: PlayerDetectorPort | None = None, ...) -> None:
    self.detector = detector or YoloDetector()
```

## Consequências

**Positivas:**
- Testes unitários injetam stubs/mocks sem carregar GPU: 132 testes em < 5 s.
- Novas implementações (ex.: RT-DETR) são adicionadas implementando o Protocol — sem modificar `VideoPipeline` (OCP).
- Verificação estrutural via `isinstance(obj, PlayerDetectorPort)` em runtime.

**Negativas / Trade-offs:**
- Adição de arquivo `ports.py` — pequena sobrecarga de módulo.
- `typing.Protocol` com `runtime_checkable` não verifica assinaturas de métodos em runtime, apenas presença.

## Alternativas Consideradas

| Alternativa | Razão da Rejeição |
|---|---|
| ABC (Abstract Base Class) | Requer herança explícita; bibliotecas externas (YOLO) não herdam de nossas ABCs. |
| Duck typing sem Protocol | Perde documentação de contrato e verificação estática pelo type checker. |
| Injeção via `config` dict | Sem type safety; dificulta IDE e análise estática. |
