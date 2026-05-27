# ADR-005: Factory Method `VideoPipeline.build()`

**Status:** Aceito  
**Data:** 2026-05-27  
**Decisores:** Equipe PI_V_ES_TIME-15  
**Referência:** Nygard, M. (2011). *Documenting Architecture Decisions*. Cognitect.

---

## Contexto

`VideoPipeline.__init__` aceita até 7 dependências opcionais via keyword args. Em produção, todas são `None` (usa padrões concretos). Em testes, algumas são substituídas por stubs.

Sem um ponto centralizado de criação, qualquer mudança na lista de dependências concretas (ex.: trocar `YoloDetector` por uma variante com threshold diferente) requereria localizar e atualizar todos os pontos de instanciação no código de produção.

## Decisão

Adicionar o classmethod **`build()`** como Factory Method (GoF Criacional) em `VideoPipeline`:

```python
@classmethod
def build(cls) -> "VideoPipeline":
    """Cria instância de produção com todas as dependências padrão."""
    return cls()
```

`build()` é o ponto de entrada canônico para código de produção. `__init__` permanece acessível para testes que precisam injetar stubs.

## Consequências

**Positivas:**
- Semântica clara: `VideoPipeline.build()` = instância de produção; `VideoPipeline(detector=stub)` = instância de teste.
- Centraliza eventual lógica de criação complexa (configuração por ambiente, feature flags) sem expor ao cliente.
- Compatibilidade total: código legado que chama `VideoPipeline()` sem args continua funcionando.

**Negativas / Trade-offs:**
- `build()` atual é trivial (`return cls()`); o valor aumenta conforme a criação se torna mais complexa.
- Dois caminhos de criação podem confundir contribuidores novos sem documentação clara.

## Alternativas Consideradas

| Alternativa | Razão da Rejeição |
|---|---|
| Manter apenas `__init__` | Sem sinalização clara do "caminho feliz" de produção vs. caminho de teste. |
| Classe `VideoPipelineFactory` separada | Overhead de classe extra para um único método — YAGNI para o escopo atual. |
| Parâmetro `production: bool` em `__init__` | Lógica condicional em construtor — viola SRP e dificulta leitura. |
