# ADR-004: Padrão Template Method em `process()`

**Status:** Aceito  
**Data:** 2026-05-27  
**Decisores:** Equipe PI_V_ES_TIME-15  
**Referência:** Nygard, M. (2011). *Documenting Architecture Decisions*. Cognitect.

---

## Contexto

O método `process()` orquestra 4 etapas sequenciais com ordem invariante:

1. Extração de metadados do vídeo (detecção frame a frame).
2. Resolução de identidades (mapeamento número de camisa → track IDs).
3. Cálculo de intervalos temporais (agrupamento de frames em clipes).
4. Escrita dos clipes (leitura de frames + codificação em vídeo).

Essa sequência é fixa — não pode ser reordenada. Porém, as implementações de cada passo podem variar por subclasse ou configuração.

Antes da refatoração, as 4 etapas estavam inline em `process()` sem delimitação clara, dificultando leitura, teste individual e substituição.

## Decisão

Aplicar o padrão **Template Method** (GoF Comportamental) em `process()`.

O método define o esqueleto algorítmico via comentários de seção explícitos e delegação a métodos protegidos:

```python
def process(self, ...) -> list[dict]:
    # ── Passo 1: Extração de metadados
    video_metadata, jersey_map, fps = self._extract_metadata(...)

    # ── Passo 2: Resolução de identidades
    target_track_ids = self._resolve_player_ids(...)

    # ── Passo 3: Cálculo de intervalos temporais
    clip_intervals = self._compute_clip_intervals(...)

    # ── Passo 4: Escrita dos clipes
    clips = self._write_clips(...)
    return clips
```

Cada passo `_step_N()` é um método protegido com responsabilidade única, testável de forma isolada.

## Consequências

**Positivas:**
- `process()` lê como um índice de 4 linhas; a complexidade está nos métodos delegados.
- Testes de integração (`test_pipeline_steps.py`) testam cada passo isoladamente via `__new__`.
- Subclasses podem sobrepor passos individuais sem duplicar a orquestração.
- Localização imediata de bugs: erro no Passo 2 → investigar `_resolve_player_ids`.

**Negativas / Trade-offs:**
- Herança como mecanismo de variação — preferível a composição em projetos mais complexos.
- Métodos protegidos com prefixo `_` são convenção, não restrição real em Python.

## Alternativas Consideradas

| Alternativa | Razão da Rejeição |
|---|---|
| Pipeline como lista de funções (`steps = [f1, f2, f3, f4]`) | Perde tipagem; ordem implícita na lista em vez de explícita no código. |
| Classe separada por etapa | Aumentaria o número de classes sem benefício claro para 4 etapas sequenciais fixas. |
| Manter inline | Método `process()` de 200+ linhas sem delimitação clara — baixa legibilidade. |
