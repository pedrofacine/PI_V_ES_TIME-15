"""
Abstração de armazenamento de arquivos (§4.2 da spec).

No F0 só existe o backend local em disco. A interface permite trocar por
S3/Supabase Storage sem tocar nos módulos que a consomem.
"""
from abc import ABC, abstractmethod
from pathlib import Path


class StorageBackend(ABC):
    @abstractmethod
    def save(self, data: bytes, key: str) -> str:
        """Grava `data` sob `key` e retorna o caminho/identificador armazenado."""

    @abstractmethod
    def path_for(self, key: str) -> Path:
        """Resolve `key` para um caminho local (usado pelo servidor de estáticos)."""

    @abstractmethod
    def delete(self, stored_path: str) -> None:
        """Remove o arquivo em `stored_path` (caminho retornado por `save`). No-op se não existir."""


class LocalStorageBackend(StorageBackend):
    def __init__(self, root: Path):
        self.root = Path(root)

    def save(self, data: bytes, key: str) -> str:
        dest = self.root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return str(dest)

    def path_for(self, key: str) -> Path:
        return self.root / key

    def delete(self, stored_path: str) -> None:
        Path(stored_path).unlink(missing_ok=True)


# Backend padrão do processo (uploads locais na raiz do backend).
_UPLOADS_ROOT = Path(__file__).resolve().parents[2] / "uploads"


def get_storage() -> StorageBackend:
    return LocalStorageBackend(root=_UPLOADS_ROOT)
