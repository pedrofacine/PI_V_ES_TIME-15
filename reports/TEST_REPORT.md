# Relatório de Testes e Benchmark — SmartScout (PI_V_ES_TIME-15)

**Data:** 2026-05-27  
**Projeto:** SmartScout — Sistema de Análise de Desempenho em Vídeos de Futebol  
**Versão:** Pós-refatoração arquitetural (`video_pipeline.py` v2)

---

## Sobre os Testes

O sistema foi desenvolvido com uma estratégia de testes em três camadas, pensada para garantir tanto a correção dos algoritmos de visão computacional quanto a integridade do backend e da integração entre os módulos. Na camada de testes unitários de ML, validamos os comportamentos internos do pipeline: cálculo de distância de cor, agrupamento de intervalos de frames, filtros de detecção de jogadores e resolução de identidades por número de camisa. Na camada de testes unitários de backend, cobrimos os endpoints FastAPI de autenticação e gerenciamento de jobs, utilizando um banco de dados SQLite em memória para isolar completamente o ambiente. Por fim, os testes de integração verificam o fluxo de ponta a ponta entre as etapas de resolução de identidades e cômputo de intervalos temporais, garantindo que as interfaces entre os módulos se comportem conforme o esperado. Essa organização permite que qualquer desenvolvedor identifique rapidamente a origem de uma regressão — se um teste de integração falha mas os unitários passam, o problema está na interface; se um unitário falha, o problema está no algoritmo.

---

## Resultados dos Testes

| Camada | Arquivo | Testes | Status |
|---|---|---|---|
| Unit — ML | `test_video_pipeline.py` | 89 | ✅ Passou |
| Unit — ML | `test_ball_event_detector.py` | 14 | ✅ Passou |
| Unit — ML | `test_kinematic_analyzer.py` | 10 | ✅ Passou |
| Unit — ML | `test_detector.py` | 4 | ✅ Passou |
| Unit — Backend | `test_auth.py` | 8 | ✅ Passou |
| Unit — Backend | `test_jobs.py` | 4 | ✅ Passou |
| Integration | `test_pipeline_steps.py` | 3 | ✅ Passou |
| **Total** | | **132** | **✅ 132/132** |

**Comando executado:** `python3 -m pytest tests/ -q`  
**Resultado:** `132 passed` — nenhuma regressão introduzida pela refatoração arquitetural.

---

## Qualidade de Código

| Ferramenta | Escopo | Resultado |
|---|---|---|
| ESLint | `frontend/src/` | ✅ Sem erros |
| TypeScript (tsc) | `frontend/` | ✅ Sem erros de tipo |
| pytest | `tests/` | ✅ 132/132 |

---

## Benchmark — Processamento de Vídeo Real

### Configuração

| Parâmetro | Valor |
|---|---|
| Vídeo | BIQUEIRA x REAL RECANTO — Copa Martins Neto 2023 |
| Resolução | 1920 × 1080 |
| FPS | 59,94 |
| Duração | ~615 s (≈ 10 min 15 s) |
| Jogador alvo | #9 |
| Data de execução | 2026-05-26 |
| Hardware | CUDA disponível (GPU) |

### Resultados

| Métrica | Valor |
|---|---|
| Clipes gerados | 4 |
| Toques de bola detectados | 11 |
| Anomalias cinemáticas | 0 |
| Tempo total de processamento | 3.863,75 s (≈ 64 min) |

### Clipes Extraídos

| Clipe | Intervalo | Duração | Toques |
|---|---|---|---|
| Clipe 1 | 1:39 – 1:58 | 18,4 s | 3 (105 s, 108 s, 109 s) |
| Clipe 2 | 3:07 – 3:21 | 13,9 s | 1 (194 s) |
| Clipe 3 | 5:44 – 6:06 | 21,2 s | 3 (351 s, 355 s, 359 s) |
| Clipe 4 | 6:10 – 6:31 | 20,7 s | 4 (376 s, 377 s, 378 s, 379 s) |

### Arquivos gerados

```
benchmark/benchmark_output/
├── jogador_9_clipe_1_99s_a_117s.mp4
├── jogador_9_clipe_2_187s_a_201s.mp4
├── jogador_9_clipe_3_344s_a_365s.mp4
└── jogador_9_clipe_4_369s_a_390s.mp4
benchmark/benchmark_report.json
```

### Observações

- O processamento de ~10 min de vídeo 1080p@60fps levou ~64 min em CPU+GPU, indicando taxa de processamento de aproximadamente 0,16× real-time — dentro do esperado para análise frame-a-frame com YOLO + OCR.
- Nenhuma anomalia cinemática detectada para o jogador #9 neste jogo.
- O agrupamento de 4 toques no Clipe 4 (376–379 s) reflete sequência de passes rápidos em ~3 segundos.

---

## Refatoração Arquitetural

Como parte deste ciclo de desenvolvimento, o módulo `ml/scripts/video_pipeline.py` passou por refatoração arquitetural completa, com aplicação dos seguintes padrões e princípios:

| Padrão / Princípio | Aplicação |
|---|---|
| **Facade** (GoF) | `VideoPipeline` encapsula todos os subsistemas em dois pontos de entrada |
| **Strategy** (GoF) | 7 Protocols em `ports.py` tornam detectores/leitores intercambiáveis |
| **Observer** (GoF) | `PipelineObserver` em `pipeline_observer.py` desacopla notificações |
| **Template Method** (GoF) | `process()` define 4 passos fixos delegados a métodos protegidos |
| **Factory Method** (GoF) | `VideoPipeline.build()` centraliza criação de instâncias de produção |
| **Null Object** (GoF) | `NullObserver` elimina verificações `if observer:` no pipeline |
| **Adapter** (GoF) | `CallbackObserver` adapta `Callable` ao protocolo `PipelineObserver` |
| **SOLID** | SRP, OCP, LSP, ISP e DIP aplicados — ver ADRs |
| **Clean Architecture** | Ports & Adapters (Cockburn, 2005) — dependências apontam para dentro |
| **ADRs** | 5 decisões documentadas em `docs/adr/` (Nygard, 2011) |
| **ISO/IEC 25010:2023** | Testabilidade, Manutenibilidade e Extensibilidade como atributos prioritários |

**Resultado:** 132/132 testes passando após a refatoração — zero regressões.

---

*Gerado em 2026-05-27 — SmartScout / PI_V_ES_TIME-15*
