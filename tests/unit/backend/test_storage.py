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


def test_delete_removes_file(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    stored = backend.save(b"conteudo do clipe", "clips/job1/x.mp4")

    backend.delete(stored)

    assert not Path(stored).exists()


def test_delete_missing_file_is_noop(tmp_path: Path):
    backend = LocalStorageBackend(root=tmp_path)
    backend.delete(str(tmp_path / "clips" / "nao_existe.mp4"))
