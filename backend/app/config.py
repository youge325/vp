"""Application configuration and runtime resource resolution."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_path(value: str | Path | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def _first_existing_path(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _system_executable(name: str) -> str:
    return shutil.which(name) or name


def _platform_executable(name: str) -> str:
    return f"{name}.exe" if sys.platform.startswith("win") else name


def _candidate_runtime_roots(app_root: Path, backend_root: Path) -> list[Path]:
    return [
        app_root / "resources" / "runtime",
        app_root / "runtime",
        backend_root.parent / "resources" / "runtime",
        backend_root / "resources" / "runtime",
    ]


def _candidate_executable_paths(runtime_root: Path, name: str) -> list[Path]:
    executable_name = _platform_executable(name)
    return [
        runtime_root / executable_name,
        runtime_root / "bin" / executable_name,
        runtime_root / name / executable_name,
        runtime_root / name / "bin" / executable_name,
    ]


def _candidate_python_paths(runtime_root: Path) -> list[Path]:
    executable_name = _platform_executable("python")
    return [
        runtime_root / executable_name,
        runtime_root / "python" / executable_name,
        runtime_root / "python" / "bin" / executable_name,
        runtime_root / "bin" / executable_name,
    ]


class Settings(BaseSettings):
    """Settings loaded from environment variables with sensible defaults."""

    APP_NAME: str = "Video Processing Workbench"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    APP_ROOT: str = ""
    RUNTIME_ROOT: str = ""
    PYTHON_EXECUTABLE: str = ""

    FFMPEG_PATH: str = ""
    FFPROBE_PATH: str = ""

    OUTPUT_DIR: str = ""
    MAX_CONCURRENT_TASKS: int = 1

    DEFAULT_TENSOR_BACKEND: str = "pytorch"

    LOG_DIR: str = ""
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 5
    LOG_STARTUP_FILE_KEEP_COUNT: int = 30

    RIFE_MODEL_DIR: str = ""
    RIFE_MODEL_VERSION: str = "4.25"
    RIFE_SCALE: float = 1.0
    RIFE_FP16: bool = False
    RIFE_DEFAULT_MULTI: int = 2

    model_config = SettingsConfigDict(env_prefix="VP_", env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        backend_root = Path(__file__).resolve().parents[1]
        repo_root = backend_root.parent

        app_root = _resolve_path(self.APP_ROOT) or repo_root
        runtime_root = _resolve_path(self.RUNTIME_ROOT)
        if runtime_root is None:
            runtime_root = _first_existing_path(_candidate_runtime_roots(app_root, backend_root))

        output_dir = _resolve_path(self.OUTPUT_DIR) or (backend_root / "output")
        log_dir = _resolve_path(self.LOG_DIR) or (backend_root / "logs")

        model_dir = _resolve_path(self.RIFE_MODEL_DIR)
        if model_dir is None:
            if runtime_root is not None:
                model_dir = runtime_root / "models"
            else:
                model_dir = backend_root / "models"

        ffmpeg_path = _resolve_path(self.FFMPEG_PATH)
        ffprobe_path = _resolve_path(self.FFPROBE_PATH)
        python_executable = _resolve_path(self.PYTHON_EXECUTABLE)

        if runtime_root is not None:
            if ffmpeg_path is None:
                ffmpeg_path = _first_existing_path(_candidate_executable_paths(runtime_root, "ffmpeg"))
            if ffprobe_path is None:
                ffprobe_path = _first_existing_path(_candidate_executable_paths(runtime_root, "ffprobe"))
            if python_executable is None:
                python_executable = _first_existing_path(_candidate_python_paths(runtime_root))

        ffmpeg_value = str(ffmpeg_path) if ffmpeg_path is not None else _system_executable("ffmpeg")
        ffprobe_value = str(ffprobe_path) if ffprobe_path is not None else _system_executable("ffprobe")
        python_value = str(python_executable) if python_executable is not None else sys.executable

        object.__setattr__(self, "APP_ROOT", str(app_root))
        object.__setattr__(self, "RUNTIME_ROOT", str(runtime_root) if runtime_root is not None else "")
        object.__setattr__(self, "PYTHON_EXECUTABLE", python_value)
        object.__setattr__(self, "FFMPEG_PATH", ffmpeg_value)
        object.__setattr__(self, "FFPROBE_PATH", ffprobe_value)
        object.__setattr__(self, "OUTPUT_DIR", str(output_dir))
        object.__setattr__(self, "LOG_DIR", str(log_dir))
        object.__setattr__(self, "RIFE_MODEL_DIR", str(model_dir))

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def repo_root(self) -> Path:
        return self.backend_root.parent

    @property
    def runtime_root_path(self) -> Path | None:
        return _resolve_path(self.RUNTIME_ROOT)

    @property
    def runtime_mode(self) -> str:
        runtime_root = self.runtime_root_path
        if runtime_root is None:
            return "external"
        if runtime_root.exists():
            return "bundled"
        return "expected-bundled"

    @property
    def bundled_runtime_available(self) -> bool:
        runtime_root = self.runtime_root_path
        return runtime_root is not None and runtime_root.exists()

    def resource_summary(self) -> dict[str, object]:
        default_model_path = Path(self.RIFE_MODEL_DIR) / f"rife_v{self.RIFE_MODEL_VERSION}.onnx"
        onnx_interpolation_dir = Path(self.RIFE_MODEL_DIR) / "interpolation"
        onnx_super_resolution_dir = Path(self.RIFE_MODEL_DIR) / "super_resolution"
        return {
            "app_root": self.APP_ROOT,
            "backend_root": str(self.backend_root),
            "repo_root": str(self.repo_root),
            "runtime_root": self.RUNTIME_ROOT,
            "runtime_mode": self.runtime_mode,
            "python_executable": self.PYTHON_EXECUTABLE,
            "ffmpeg_path": self.FFMPEG_PATH,
            "ffprobe_path": self.FFPROBE_PATH,
            "output_dir": self.OUTPUT_DIR,
            "log_dir": self.LOG_DIR,
            "model_dir": self.RIFE_MODEL_DIR,
            "onnx_interpolation_model_dir": str(onnx_interpolation_dir),
            "onnx_super_resolution_model_dir": str(onnx_super_resolution_dir),
            "default_model_path": str(default_model_path),
            "default_model_available": default_model_path.is_file() and default_model_path.stat().st_size > 0,
        }


settings = Settings()
