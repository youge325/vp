"""ONNX model discovery and safe path resolution."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Literal

from app.catalog.model_metrics import ModelMetricSpec
from app.utils.logger import get_logger

logger = get_logger(__name__)

_OnnxModelKind = Literal["interpolation", "super_resolution"]

_ONNX_MODEL_SUBDIRS: dict[_OnnxModelKind, str] = {
    "interpolation": "interpolation",
    "super_resolution": "super_resolution",
}

_ENGINE_PROVIDER_PRIORITY: dict[str, list[str]] = {
    "tensorrt": ["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"],
    "cuda": ["CUDAExecutionProvider", "CPUExecutionProvider"],
}


@dataclass(frozen=True, slots=True)
class OnnxModelCatalog:
    names: dict[str, dict[str, list[str]]]
    details: dict[str, dict[str, list[ModelMetricSpec]]]


def _get_onnx_model_dir(kind: _OnnxModelKind, model_root: str | Path | None = None) -> Path:
    """Return the configured ONNX model directory for a model kind."""
    if model_root is None:
        raise ValueError("model_root is required")
    root = Path(model_root).expanduser().resolve()
    return root / _ONNX_MODEL_SUBDIRS[kind]


def scan_onnx_catalog(model_root: str | Path | None = None) -> OnnxModelCatalog:
    """Discover names and analyze details from one directory traversal."""
    from app.utils.onnx_metric_analyzer import analyze_onnx_model

    names: dict[str, dict[str, list[str]]] = {}
    details: dict[str, dict[str, list[ModelMetricSpec]]] = {}
    for kind in _ONNX_MODEL_SUBDIRS:
        grouped_paths = _scan_kind_paths(_get_onnx_model_dir(kind, model_root))
        names[kind] = {algorithm: [path.name for path in paths] for algorithm, paths in grouped_paths.items()}
        details[kind] = {
            algorithm: [analyze_onnx_model(path, name=path.name, label=path.name) for path in paths]
            for algorithm, paths in grouped_paths.items()
        }
    return OnnxModelCatalog(names=names, details=details)


def resolve_onnx_model_path(
    kind: _OnnxModelKind,
    algorithm: str,
    filename: str | None,
    model_root: str | Path | None = None,
) -> Path:
    """Resolve a frontend-supplied ONNX basename inside ``<kind>/<algorithm>/``."""
    if not filename or not _is_safe_onnx_basename(filename):
        raise FileNotFoundError(f"Invalid ONNX model filename: {filename or '<empty>'}")
    if not _is_safe_algorithm_name(algorithm):
        raise FileNotFoundError(f"Invalid ONNX algorithm name: {algorithm!r}")

    kind_dir = _get_onnx_model_dir(kind, model_root)
    candidate = (kind_dir / algorithm / filename).resolve()
    kind_dir_resolved = kind_dir.resolve()

    try:
        candidate.relative_to(kind_dir_resolved)
    except ValueError as exc:
        raise FileNotFoundError(f"ONNX model path escapes the model directory: {algorithm}/{filename}") from exc

    if not candidate.is_file() or candidate.stat().st_size <= 0:
        raise FileNotFoundError(f"ONNX model file not found: {candidate}")
    return candidate


def _is_basename_only(name: str) -> bool:
    """True when ``name`` is a single path segment — no separators, no traversal, no drive.

    ``is_safe_onnx_basename`` 与 ``is_safe_algorithm_name`` 共享
    重复的"basename-only"验证(空 / `.` / `..` / posix split / windows
    split / drive / root 检查),两个公开函数现在只差 ``.onnx`` 后缀。
    """
    if name in {"", ".", ".."}:
        return False
    if PurePosixPath(name).name != name:
        return False
    windows_path = PureWindowsPath(name)
    if windows_path.name != name or windows_path.drive or windows_path.root:
        return False
    return True


def _is_safe_onnx_basename(filename: str) -> bool:
    """True when ``filename`` is a basename-only ``.onnx`` file reference."""
    return _is_basename_only(filename) and filename.lower().endswith(".onnx")


def _is_safe_algorithm_name(name: str) -> bool:
    """True when ``name`` is a single path segment (no separators, no traversal)."""
    return _is_basename_only(name)


def _scan_kind_paths(kind_dir: Path) -> dict[str, list[Path]]:
    if not kind_dir.is_dir():
        return {}
    result: dict[str, list[Path]] = {}
    for alg_dir in sorted(kind_dir.iterdir(), key=lambda p: p.name.casefold()):
        if not alg_dir.is_dir() or not _is_safe_algorithm_name(alg_dir.name):
            continue
        files = sorted(
            (
                item
                for item in alg_dir.iterdir()
                if item.is_file()
                and item.suffix.lower() == ".onnx"
                and item.stat().st_size > 0
                and _is_safe_onnx_basename(item.name)
            ),
            key=lambda path: path.name.casefold(),
        )
        if files:
            result[alg_dir.name] = files
    return result


def _select_onnx_providers(engine: str, ort_module: Any) -> list[str]:
    """Pick the provider list for the requested engine, refusing silent CPU fallback.

    ONNX Runtime can silently drop an unavailable requested provider and run on
    CPU. Check ``ort.get_available_providers()`` first so accelerator
    misconfiguration becomes a precise error.
    """
    available = list(ort_module.get_available_providers())
    if engine not in _ENGINE_PROVIDER_PRIORITY:
        raise ValueError(f"Unsupported ONNX inference engine: {engine!r}.")

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
    providers = _select_onnx_providers(engine, ort_module)
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
