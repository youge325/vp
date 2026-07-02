from pathlib import Path

import pytest

from app.config import settings
from app.errors import ProcessError, TaskErrorCode


def test_paddlegan_weight_paths_are_fixed_under_backend_models(monkeypatch):
    monkeypatch.setenv("VP_RIFE_MODEL_DIR", "D:/should/not/be/used")

    from app.algorithms.paddle.paddlegan_vsr.weights import (
        DISABLED_PADDLEGAN_VSR_MODELS,
        PADDLEGAN_VSR_SPECS,
        resolve_weight_path,
    )

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
    assert DISABLED_PADDLEGAN_VSR_MODELS == {}
    assert not set(PADDLEGAN_VSR_SPECS) & set(DISABLED_PADDLEGAN_VSR_MODELS)


def test_ensure_weight_file_reports_missing_even_when_auto_download_requested(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    target = tmp_path / "PP-MSVSR_reds_x4.pdparams"

    monkeypatch.setattr(weights, "resolve_weight_path", lambda _model_id: target)

    with pytest.raises(ProcessError) as exc_info:
        weights.ensure_weight_file("ppmsvsr", auto_download=True)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(target) in exc_info.value.message
    assert exc_info.value.details == {"model": "ppmsvsr", "path": str(target)}


def test_ensure_weight_file_reports_missing_when_auto_download_disabled(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    target = tmp_path / "missing.pdparams"
    monkeypatch.setattr(weights, "resolve_weight_path", lambda _model_id: target)

    with pytest.raises(ProcessError) as exc_info:
        weights.ensure_weight_file("ppmsvsr", auto_download=False)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(target) in exc_info.value.message


def test_ensure_paddlegan_vsr_weights_checks_ppmsvsr_auxiliary(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    main_weight = tmp_path / "ppmsvsr" / "PP-MSVSR_reds_x4.pdparams"
    main_weight.parent.mkdir(parents=True)
    main_weight.write_bytes(b"main")
    monkeypatch.setattr(weights, "fixed_weight_root", lambda: tmp_path)

    with pytest.raises(ProcessError) as exc_info:
        weights.ensure_paddlegan_vsr_weights("ppmsvsr")

    expected_aux = tmp_path / "_auxiliary" / "modified_spynet_tiny.pdparams"
    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(expected_aux) in exc_info.value.message
    assert exc_info.value.details == {"model": "ppmsvsr", "path": str(expected_aux)}

    expected_aux.parent.mkdir(parents=True)
    expected_aux.write_bytes(b"aux")

    assert weights.ensure_paddlegan_vsr_weights("ppmsvsr") == main_weight


def test_ensure_paddlegan_vsr_weights_checks_only_edvr_main_weight(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr import weights

    main_weight = tmp_path / "edvr" / "EDVR_L_w_tsa_SRx4.pdparams"
    main_weight.parent.mkdir(parents=True)
    main_weight.write_bytes(b"main")
    monkeypatch.setattr(weights, "fixed_weight_root", lambda: tmp_path)

    assert weights.ensure_paddlegan_vsr_weights("edvr") == main_weight


@pytest.mark.parametrize(
    ("model_id", "filename", "auxiliary_filenames"),
    [
        ("ppmsvsr-large", "PP-MSVSR-L_reds_x4.pdparams", ("modified_spynet.pdparams",)),
        ("basicvsr", "BasicVSR_reds_x4.pdparams", ("spynet.pdparams",)),
        ("iconvsr", "IconVSR_reds_x4.pdparams", ("spynet.pdparams", "edvrm.pdparams")),
        ("basicvsr-plus-plus", "BasicVSR++_reds_x4.pdparams", ("spynet.pdparams",)),
    ],
)
def test_ensure_paddlegan_vsr_weights_checks_restored_model_auxiliaries(
    tmp_path,
    monkeypatch,
    model_id,
    filename,
    auxiliary_filenames,
):
    from app.algorithms.paddle.paddlegan_vsr import weights

    main_weight = tmp_path / model_id / filename
    main_weight.parent.mkdir(parents=True)
    main_weight.write_bytes(b"main")
    monkeypatch.setattr(weights, "fixed_weight_root", lambda: tmp_path)

    with pytest.raises(ProcessError) as exc_info:
        weights.ensure_paddlegan_vsr_weights(model_id)

    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert auxiliary_filenames[0] in exc_info.value.message

    aux_root = tmp_path / "_auxiliary"
    aux_root.mkdir(parents=True)
    for auxiliary_filename in auxiliary_filenames:
        (aux_root / auxiliary_filename).write_bytes(b"aux")

    assert weights.ensure_paddlegan_vsr_weights(model_id) == main_weight


def test_vendor_auxiliary_weight_helper_uses_only_local_auxiliary_files(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.utils import download

    local_weight = tmp_path / "modified_spynet_tiny.pdparams"
    local_weight.write_bytes(b"weight")
    monkeypatch.setattr(download, "PPGAN_HOME", str(tmp_path))

    resolved = download.get_path_from_url("https://paddlegan.bj.bcebos.com/models/modified_spynet_tiny.pdparams")

    assert resolved == str(local_weight)


def test_vendor_auxiliary_weight_helper_reports_missing_without_download(tmp_path, monkeypatch):
    from app.algorithms.paddle.paddlegan_vsr.vendor.ppgan.utils import download

    monkeypatch.setattr(download, "PPGAN_HOME", str(tmp_path))
    if hasattr(download, "_download"):
        monkeypatch.setattr(download, "_download", lambda *_args, **_kwargs: pytest.fail("download attempted"))

    with pytest.raises(ProcessError) as exc_info:
        download.get_path_from_url("https://paddlegan.bj.bcebos.com/models/spynet.pdparams")

    expected_path = tmp_path / "spynet.pdparams"
    assert exc_info.value.code == TaskErrorCode.MISSING_MODEL
    assert str(expected_path) in exc_info.value.message
    assert exc_info.value.details["path"] == str(expected_path)
