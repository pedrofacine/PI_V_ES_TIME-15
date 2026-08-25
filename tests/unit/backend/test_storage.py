from pathlib import Path

from app.core.storage import LocalStorageBackend


def test_save_writes_file_and_returns_path(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    stored = backend.save(b"conteudo do video", "videos/abc_test.mp4")

    saved = Path(stored)
    assert saved.exists()
    assert saved.read_bytes() == b"conteudo do video"
    assert saved == tmp_path / "videos" / "abc_test.mp4"


def test_path_for_resolves_key(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    assert backend.path_for("clips/x.mp4") == tmp_path / "clips" / "x.mp4"
