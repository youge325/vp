from pathlib import Path

import pytest

from app.config import settings
from app.errors import ProcessError, TaskErrorCode


def test_paddlegan_weight_paths_are_fixed_under_backend_models(monkeypatch):
    monkeypatch.setenv("VP_RIFE_MODEL_DIR", "D:/should/not/be/used")

    from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS, resolve_weight_path

    path = resolve_weight_path("ppmsvsr")

    assert path == Path(settings.backend_root) / "models" / "super_resolution" / "paddlegan" / "ppmsvsr" / (
        "PP-MSVSR_reds_x4.pdparams"
    )
    assert "D:/should/not/be/used" not in str(path)
    assert set(PADDLEGAN_VSR_SPECS) == {
        "ppmsvsr",
        "ppmsvsr-large",
        "edvr",
        "basicvsr",
        "iconvsr",
        "basicvsr-plus-plus",
    }


def test_ensure_weight_file_downloads_to_tmp_then_replaces(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    target = tmp_path / "PP-MSVSR_reds_x4.pdparams"
    calls = []

    def fake_downloader(url: str, destination: Path) -> None:
        calls.append((url, destination))
        assert destination.name.endswith(".tmp")
        destination.write_bytes(b"downloaded")

    monkeypatch.setattr(weights, "resolve_weight_path", lambda _model_id: target)

    resolved = weights.ensure_weight_file("ppmsvsr", auto_download=True, downloader=fake_downloader)

    assert resolved == target
    assert target.read_bytes() == b"downloaded"
    assert calls == [(weights.PADDLEGAN_VSR_SPECS["ppmsvsr"].url, target.with_suffix(".pdparams.tmp"))]
    assert not target.with_suffix(".pdparams.tmp").exists()


def test_ensure_weight_file_reports_missing_when_auto_download_disabled(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    target = tmp_path / "missing.pdparams"
    monkeypatch.setattr(weights, "resolve_weight_path", lambda _model_id: target)

    with pytest.raises(ProcessError) as exc_info:
        weights.ensure_weight_file("ppmsvsr", auto_download=False)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(target) in exc_info.value.message
