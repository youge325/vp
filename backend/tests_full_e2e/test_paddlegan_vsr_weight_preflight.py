from __future__ import annotations

import pytest

from app.algorithms.paddle.paddlegan_vsr.weights import PADDLEGAN_VSR_SPECS, ensure_paddlegan_vsr_weights


@pytest.mark.full_e2e
def test_all_paddlegan_vsr_models_have_preprovisioned_weights() -> None:
    assert set(PADDLEGAN_VSR_SPECS) == {
        "ppmsvsr",
        "ppmsvsr-large",
        "edvr",
        "basicvsr",
        "iconvsr",
        "basicvsr-plus-plus",
    }

    for model_id in sorted(PADDLEGAN_VSR_SPECS):
        weight_path = ensure_paddlegan_vsr_weights(model_id)
        assert weight_path.is_file()
        assert weight_path.stat().st_size > 0
