"""
Hierarquia de exceções de domínio (§10.2 da spec).

Services levantam estas exceções; um único handler em main.py as traduz
para respostas HTTP. Routers não montam HTTPException.
"""


class DomainError(Exception):
    """Base. Mapeada para 500 quando não for uma subclasse mais específica."""

    status_code: int = 500
    default_detail: str = "Erro interno."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.default_detail
        super().__init__(self.detail)


class NotFoundError(DomainError):
    status_code = 404
    default_detail = "Recurso não encontrado."


class ForbiddenError(DomainError):
    status_code = 403
    default_detail = "Acesso negado."


class ConflictError(DomainError):
    status_code = 409
    default_detail = "Conflito de estado."


class QuotaExceededError(DomainError):
    status_code = 402
    default_detail = "Cota excedida."


class ValidationError(DomainError):
    status_code = 422
    default_detail = "Dados inválidos."
