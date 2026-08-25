from app.core.exceptions import (
    DomainError,
    NotFoundError,
    ForbiddenError,
    ConflictError,
    QuotaExceededError,
    ValidationError,
)


def test_status_codes():
    assert DomainError().status_code == 500
    assert NotFoundError().status_code == 404
    assert ForbiddenError().status_code == 403
    assert ConflictError().status_code == 409
    assert QuotaExceededError().status_code == 402
    assert ValidationError().status_code == 422


def test_custom_detail_and_default():
    assert NotFoundError("Job não encontrado.").detail == "Job não encontrado."
    assert NotFoundError().detail == NotFoundError.default_detail
    assert str(ConflictError("x")) == "x"


def test_hierarchy():
    for exc in [NotFoundError, ForbiddenError, ConflictError, QuotaExceededError, ValidationError]:
        assert issubclass(exc, DomainError)
