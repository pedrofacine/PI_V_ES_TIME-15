"""
Observer pattern para eventos do pipeline de análise de vídeo.

Padrões aplicados
-----------------
Observer (GoF Comportamental)
    PipelineObserver define o contrato que qualquer observador deve
    implementar. O pipeline notifica eventos sem conhecer os consumidores.

Null Object (GoF Comportamental)
    NullObserver elimina verificações `if callback: callback(...)` no
    código do pipeline, substituindo-as por chamadas diretas e seguras.

Adapter (GoF Estrutural)
    CallbackObserver adapta funções simples (Callable) ao protocolo
    PipelineObserver, garantindo retrocompatibilidade com código legado
    que passa lambdas ou funções como callbacks.
"""
from __future__ import annotations

from typing import Callable, Protocol, runtime_checkable


@runtime_checkable
class PipelineObserver(Protocol):
    """
    Contrato para observadores do pipeline de análise de vídeo.

    Cada método corresponde a um evento significativo no ciclo de vida
    do processamento. Implementações podem ignorar eventos irrelevantes
    com um corpo vazio (`pass`).
    """

    def on_candidate_found(self, candidate: dict) -> None: ...
    def on_player_found(self) -> None: ...
    def on_extracting_start(self) -> None: ...
    def on_clip_generated(self, clip: dict) -> None: ...


class NullObserver:
    """
    Null Object para PipelineObserver.

    Substitui todas as verificações `if callback is not None` por chamadas
    diretas ao observer — sem efeitos colaterais, sem overhead de branching.
    """

    def on_candidate_found(self, candidate: dict) -> None:
        pass

    def on_player_found(self) -> None:
        pass

    def on_extracting_start(self) -> None:
        pass

    def on_clip_generated(self, clip: dict) -> None:
        pass


class CallbackObserver:
    """
    Adapter de Callable → PipelineObserver.

    Permite que código existente que passa funções simples como callbacks
    continue funcionando sem alteração, enquanto o pipeline usa internamente
    o contrato PipelineObserver.
    """

    def __init__(
        self,
        *,
        on_candidate_found: Callable[[dict], None] | None = None,
        on_player_found: Callable[[], None] | None = None,
        on_extracting_start: Callable[[], None] | None = None,
        on_clip_generated: Callable[[dict], None] | None = None,
    ) -> None:
        self._on_candidate_found = on_candidate_found
        self._on_player_found = on_player_found
        self._on_extracting_start = on_extracting_start
        self._on_clip_generated = on_clip_generated

    def on_candidate_found(self, candidate: dict) -> None:
        if self._on_candidate_found:
            self._on_candidate_found(candidate)

    def on_player_found(self) -> None:
        if self._on_player_found:
            self._on_player_found()

    def on_extracting_start(self) -> None:
        if self._on_extracting_start:
            self._on_extracting_start()

    def on_clip_generated(self, clip: dict) -> None:
        if self._on_clip_generated:
            self._on_clip_generated(clip)


def make_observer(
    on_candidate_found: Callable[[dict], None] | None = None,
    on_player_found: Callable[[], None] | None = None,
    on_extracting_start: Callable[[], None] | None = None,
    on_clip_generated: Callable[[dict], None] | None = None,
) -> PipelineObserver:
    """
    Retorna NullObserver se nenhum callback for fornecido,
    ou CallbackObserver adaptando os callbacks presentes.

    Uso no pipeline::

        observer = make_observer(on_clip_generated=fn)
        observer.on_clip_generated(clip)   # nunca precisa checar None
    """
    if not any([on_candidate_found, on_player_found, on_extracting_start, on_clip_generated]):
        return NullObserver()
    return CallbackObserver(
        on_candidate_found=on_candidate_found,
        on_player_found=on_player_found,
        on_extracting_start=on_extracting_start,
        on_clip_generated=on_clip_generated,
    )
