# ADR-003: Padrão Observer para Eventos do Pipeline

**Status:** Aceito  
**Data:** 2026-05-27  
**Decisores:** Equipe PI_V_ES_TIME-15  
**Referência:** Nygard, M. (2011). *Documenting Architecture Decisions*. Cognitect.

---

## Contexto

O pipeline precisa notificar consumidores externos sobre eventos de ciclo de vida: candidato encontrado durante fast scan, jogador identificado, início da extração, clipe gerado. Os consumidores variam: logs de terminal, atualização de UI via WebSocket, callbacks de teste — e novos consumidores podem surgir.

A abordagem original usava callbacks individuais opcionais (`on_player_found: Callable | None`), com verificações `if callback: callback()` espalhadas pelo código. Isso tornava cada novo evento uma modificação no contrato de `process()`.

## Decisão

Aplicar o padrão **Observer** (GoF Comportamental) via `PipelineObserver` Protocol definido em `ml/scripts/pipeline_observer.py`.

Três classes complementam a decisão:

1. **`PipelineObserver`** (Protocol) — contrato com 4 eventos.
2. **`NullObserver`** (Null Object) — implementação vazia; elimina todos os `if observer:` no pipeline.
3. **`CallbackObserver`** (Adapter) — adapta `Callable` ao `PipelineObserver`; mantém retrocompatibilidade.
4. **`make_observer()`** (Factory Function) — retorna `NullObserver` ou `CallbackObserver` conforme callbacks fornecidos.

No pipeline: `observer = make_observer(...)` uma vez; depois apenas `observer.on_candidate_found(c)` — sem checagem de nulo.

## Consequências

**Positivas:**
- Pipeline desacoplado dos consumidores: não sabe quem ouve, apenas notifica.
- Eliminação de todos os `if callback: callback()` — código mais limpo e sem branching desnecessário.
- Novos eventos adicionados ao Protocol sem alterar callers que não se importam (implementam com `pass`).
- Testabilidade: testes injetam `CallbackObserver` para capturar eventos sem acesso ao stdout.

**Negativas / Trade-offs:**
- Suporte a múltiplos observers simultâneos exigiria um `CompositeObserver` — não implementado (YAGNI).
- Eventos são síncronos; uso em contextos assíncronos (WebSocket) requer wrapper.

## Alternativas Consideradas

| Alternativa | Razão da Rejeição |
|---|---|
| Callbacks individuais opcionais | Verificações `if callback` espalhadas; cada evento novo altera assinatura de `process()`. |
| Logging direto | Acopla o pipeline ao sistema de log; impossível redirecionar eventos para UI ou testes. |
| Event bus / signals | Overhead desnecessário para 4 eventos síncronos em um pipeline single-threaded. |
