"""Backend marker isolation is derived from module declarations."""

from __future__ import annotations

from pathlib import Path

from tests.conftest import _backend_marked_files


def test_backend_isolation_discovers_new_module_markers_without_a_manual_file_list(
    tmp_path: Path,
) -> None:
    (tmp_path / "test_shared.py").write_text("def test_shared(): pass\n", encoding="utf-8")
    (tmp_path / "test_torch.py").write_text(
        "import pytest\npytestmark = pytest.mark.pytorch\n",
        encoding="utf-8",
    )
    nested = tmp_path / "algorithms"
    nested.mkdir()
    (nested / "test_paddle.py").write_text(
        "import pytest\npytestmark = [pytest.mark.paddle]\n",
        encoding="utf-8",
    )

    assert _backend_marked_files(tmp_path, "pytorch") == ["test_torch.py"]
    assert _backend_marked_files(tmp_path, "paddle") == [str(Path("algorithms") / "test_paddle.py")]
