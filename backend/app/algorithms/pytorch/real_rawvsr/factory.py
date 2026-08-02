"""Lazy factory for the Real-RawVSR RGB model family."""

from __future__ import annotations

from typing import Any

from app.algorithms.pytorch.real_rawvsr.fixed_window import RealRawVsrFixedWindow
from app.algorithms.pytorch.real_rawvsr.sequence_adapter import ModelLoader
from app.generated.model_assets import REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM


def _load_edvr(scale: int, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.edvr import load_edvr_model

    return load_edvr_model(scale, weight_path)


def _load_tdan(scale: int, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.tdan import load_tdan_model

    return load_tdan_model(scale, weight_path)


def _load_toflow(scale: int, weight_path: str) -> tuple[Any, Any]:
    from app.algorithms.pytorch.real_rawvsr.toflow import load_toflow_model

    return load_toflow_model(scale, weight_path)


_FIXED_WINDOW_LOADERS: dict[str, ModelLoader] = {
    "real-rawvsr-edvr": _load_edvr,
    "real-rawvsr-tdan": _load_tdan,
    "real-rawvsr-toflow": _load_toflow,
}


def create_real_rawvsr_algorithm(
    *,
    algorithm_id: str,
    scale_factor: int,
    num_frames: int,
    engine: str,
    model_root: str,
) -> Any:
    try:
        family = REAL_RAWVSR_MODEL_FAMILIES_BY_ALGORITHM[algorithm_id]
    except KeyError as exc:
        raise ValueError(f"Unsupported Real-RawVSR RGB algorithm: {algorithm_id!r}.") from exc
    if family.input_frame_mode == "editable_chunk":
        from app.algorithms.pytorch.real_rawvsr_basicvsr.runner import RealRawVsrBasicVsr

        return RealRawVsrBasicVsr(
            algorithm_id=algorithm_id,
            scale_factor=scale_factor,
            num_frames=num_frames,
            engine=engine,
            model_root=model_root,
        )
    try:
        loader = _FIXED_WINDOW_LOADERS[algorithm_id]
    except KeyError as exc:
        raise ValueError(f"No fixed-window loader registered for {algorithm_id!r}.") from exc
    return RealRawVsrFixedWindow(
        algorithm_id=algorithm_id,
        scale_factor=scale_factor,
        num_frames=num_frames,
        engine=engine,
        model_root=model_root,
        model_loader=loader,
    )


__all__ = ["create_real_rawvsr_algorithm"]
