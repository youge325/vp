"""ONNX model discovery and safe path resolution."""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from app.utils.logger import get_logger

logger = get_logger(__name__)

OnnxModelKind = Literal["interpolation", "super_resolution"]
OnnxEngine = Literal["tensorrt", "cuda", "auto"]

ONNX_MODEL_SUBDIRS: dict[OnnxModelKind, str] = {
    "interpolation": "interpolation",
    "super_resolution": "super_resolution",
}

_ENGINE_PROVIDER_PRIORITY: dict[str, list[str]] = {
    "tensorrt": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
}


def get_onnx_model_dir(kind: OnnxModelKind, model_root: str | Path | None = None) -> Path:
    """Return the configured ONNX model directory for a model kind."""
    if model_root is None:
        raise ValueError("model_root is required")
    root = Path(model_root).expanduser().resolve()
    return root / ONNX_MODEL_SUBDIRS[kind]


def scan_onnx_models(model_root: str | Path | None = None) -> dict[str, dict[str, list[str]]]:
    """List ONNX model basenames grouped by kind, then by algorithm subdir.

    Layout: ``<model_root>/<kind>/<algorithm>/<basename>.onnx``
    Returns ``{"interpolation": {"rife": ["rife_v4.25.onnx", ...]}, "super_resolution": {...}}``.
    """
    return {kind: _scan_kind_dir(get_onnx_model_dir(kind, model_root)) for kind in ONNX_MODEL_SUBDIRS}


def resolve_onnx_model_path(
    kind: OnnxModelKind,
    algorithm: str,
    filename: str | None,
    model_root: str | Path | None = None,
) -> Path:
    """Resolve a frontend-supplied ONNX basename inside ``<kind>/<algorithm>/``."""
    if not filename or not is_safe_onnx_basename(filename):
        raise FileNotFoundError(f"Invalid ONNX model filename: {filename or '<empty>'}")
    if not is_safe_algorithm_name(algorithm):
        raise FileNotFoundError(f"Invalid ONNX algorithm name: {algorithm!r}")

    kind_dir = get_onnx_model_dir(kind, model_root)
    candidate = (kind_dir / algorithm / filename).resolve()
    kind_dir_resolved = kind_dir.resolve()

    try:
        candidate.relative_to(kind_dir_resolved)
    except ValueError as exc:
        raise FileNotFoundError(f"ONNX model path escapes the model directory: {algorithm}/{filename}") from exc

    if not candidate.is_file() or candidate.stat().st_size <= 0:
        raise FileNotFoundError(f"ONNX model file not found: {candidate}")
    return candidate


def is_safe_onnx_basename(filename: str) -> bool:
    """True when ``filename`` is a basename-only ``.onnx`` file reference."""
    if filename in {"", ".", ".."}:
        return False
    if PurePosixPath(filename).name != filename:
        return False

    windows_path = PureWindowsPath(filename)
    if windows_path.name != filename or windows_path.drive or windows_path.root:
        return False

    return filename.lower().endswith(".onnx")


def is_safe_algorithm_name(name: str) -> bool:
    """True when ``name`` is a single path segment (no separators, no traversal)."""
    if name in {"", ".", ".."}:
        return False
    if PurePosixPath(name).name != name:
        return False
    windows_path = PureWindowsPath(name)
    if windows_path.name != name or windows_path.drive or windows_path.root:
        return False
    return True


def _scan_kind_dir(kind_dir: Path) -> dict[str, list[str]]:
    """Scan a kind directory: each immediate subdirectory is treated as an algorithm name."""
    if not kind_dir.is_dir():
        return {}
    result: dict[str, list[str]] = {}
    for alg_dir in sorted(kind_dir.iterdir(), key=lambda p: p.name.casefold()):
        if not alg_dir.is_dir() or not is_safe_algorithm_name(alg_dir.name):
            continue
        files = sorted(
            (
                item.name
                for item in alg_dir.iterdir()
                if item.is_file()
                and item.suffix.lower() == ".onnx"
                and item.stat().st_size > 0
                and is_safe_onnx_basename(item.name)
            ),
            key=str.casefold,
        )
        if files:
            result[alg_dir.name] = files
    return result


def select_onnx_providers(engine: str, ort_module: Any) -> list[str]:
    """Pick the provider list for the requested engine, refusing silent CPU fallback.

    The previous behaviour mirrored the ONNX Runtime default, which silently
    drops a requested provider (e.g. ``CUDAExecutionProvider``) when the
    matching shared library is missing — it then keeps the session running on
    ``CPUExecutionProvider`` while telling the user nothing. That made GPU
    misconfigurations look like algorithm slowness. This helper instead checks
    ``ort.get_available_providers()`` up front and raises with a precise
    message if the requested accelerator is unavailable.
    """
    available = list(ort_module.get_available_providers())
    if engine == "auto" or engine not in _ENGINE_PROVIDER_PRIORITY:
        logger.info(
            "ONNX engine=%s, using available providers in default order: %s",
            engine,
            available,
        )
        return available

    desired = _ENGINE_PROVIDER_PRIORITY[engine]
    primary = desired[0]
    if primary not in available:
        raise RuntimeError(
            "ONNX engine '{engine}' requires '{primary}' but it is not registered with "
            "this onnxruntime build. Available providers: {available}. Install "
            "onnxruntime-gpu (and TensorRT runtime for the tensorrt engine), then make "
            "sure no plain 'onnxruntime' wheel shadows it.".format(engine=engine, primary=primary, available=available)
        )

    selected = [provider for provider in desired if provider in available]
    if selected != desired:
        missing = [provider for provider in desired if provider not in available]
        logger.warning(
            "ONNX engine=%s requested providers %s but %s are unavailable; using %s.",
            engine,
            desired,
            missing,
            selected,
        )
    else:
        logger.info("ONNX engine=%s, providers=%s", engine, selected)
    return selected


def create_onnx_session(
    onnx_path: str,
    *,
    engine: str,
    ort_module: Any,
    sess_options: Any | None = None,
) -> Any:
    """Create an InferenceSession and verify it actually bound the requested EP.

    Even when the requested provider is registered, ONNX Runtime can still
    fall through to CPU at session-creation time if e.g. CUDA libraries cannot
    be loaded at runtime. We compare ``session.get_providers()`` against the
    request so the caller learns about it instead of paying CPU prices for
    GPU work without warning.
    """
    # Defer the import so test stubs that don't rely on a real onnxruntime
    # build can monkeypatch ``app.utils.dll_paths.register_native_dll_paths``
    # without forcing us to load CUDA/TRT libraries up front.
    from app.utils.dll_paths import register_native_dll_paths

    register_native_dll_paths()
    providers = select_onnx_providers(engine, ort_module)
    if sess_options is None:
        session = ort_module.InferenceSession(onnx_path, providers=providers)
    else:
        session = ort_module.InferenceSession(onnx_path, sess_options=sess_options, providers=providers)
    bound = list(session.get_providers())
    primary_request = providers[0] if providers else None
    if primary_request and primary_request != "CPUExecutionProvider" and primary_request not in bound:
        logger.warning(
            "ONNX session for %s fell back to %s despite requesting %s. Check the "
            "matching CUDA / cuDNN / TensorRT runtime is installed and reachable.",
            onnx_path,
            bound,
            providers,
        )
    return session
