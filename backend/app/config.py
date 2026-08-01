"""Application configuration and runtime resource resolution."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.generated.application_defaults import (
    DEFAULT_RIFE_FP16,
    DEFAULT_RIFE_MODEL_VERSION,
    DEFAULT_RIFE_MULTI,
    DEFAULT_RIFE_SCALE,
)


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


def _candidate_executable_paths(
    runtime_root: Path,
    name: str,
    *,
    prefer_tool_directory: bool = False,
) -> list[Path]:
    executable_name = _platform_executable(name)
    root_path = runtime_root / executable_name
    shared_bin_path = runtime_root / "bin" / executable_name
    tool_paths = [
        runtime_root / name / executable_name,
        runtime_root / name / "bin" / executable_name,
    ]
    if prefer_tool_directory:
        return [root_path, *tool_paths, shared_bin_path]
    return [root_path, shared_bin_path, *tool_paths]


class _Settings(BaseSettings):
    """Settings loaded from environment variables with sensible defaults."""

    DEBUG: bool = True

    APP_ROOT: str = ""
    RUNTIME_ROOT: str = ""
    PYTHON_EXECUTABLE: str = ""

    FFMPEG_PATH: str = ""
    FFPROBE_PATH: str = ""

    LOG_DIR: str = ""
    LOG_FILE_MAX_BYTES: int = 10 * 1024 * 1024
    LOG_FILE_BACKUP_COUNT: int = 5
    LOG_STARTUP_FILE_KEEP_COUNT: int = 5

    RIFE_MODEL_DIR: str = ""
    RIFE_MODEL_VERSION: str = DEFAULT_RIFE_MODEL_VERSION
    RIFE_SCALE: float = DEFAULT_RIFE_SCALE
    RIFE_FP16: bool = DEFAULT_RIFE_FP16
    RIFE_DEFAULT_MULTI: int = DEFAULT_RIFE_MULTI

    model_config = SettingsConfigDict(env_prefix="VP_", env_file=".env", extra="ignore")

    def model_post_init(self, __context: object) -> None:
        backend_root = Path(__file__).resolve().parents[1]
        repo_root = backend_root.parent

        app_root = _resolve_path(self.APP_ROOT) or repo_root
        runtime_root = _resolve_path(self.RUNTIME_ROOT)
        if runtime_root is None:
            runtime_root = _first_existing_path(_candidate_runtime_roots(app_root, backend_root))

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
                python_executable = _first_existing_path(
                    _candidate_executable_paths(
                        runtime_root,
                        "python",
                        prefer_tool_directory=True,
                    )
                )

        ffmpeg_value = str(ffmpeg_path) if ffmpeg_path is not None else _system_executable("ffmpeg")
        ffprobe_value = str(ffprobe_path) if ffprobe_path is not None else _system_executable("ffprobe")
        python_value = str(python_executable) if python_executable is not None else sys.executable

        object.__setattr__(self, "APP_ROOT", str(app_root))
        object.__setattr__(self, "RUNTIME_ROOT", str(runtime_root) if runtime_root is not None else "")
        object.__setattr__(self, "PYTHON_EXECUTABLE", python_value)
        object.__setattr__(self, "FFMPEG_PATH", ffmpeg_value)
        object.__setattr__(self, "FFPROBE_PATH", ffprobe_value)
        object.__setattr__(self, "LOG_DIR", str(log_dir))
        object.__setattr__(self, "RIFE_MODEL_DIR", str(model_dir))

    @property
    def backend_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    @property
    def runtime_mode(self) -> str:
        runtime_root = _resolve_path(self.RUNTIME_ROOT)
        if runtime_root is None:
            return "external"
        if runtime_root.exists():
            return "bundled"
        return "expected-bundled"


settings = _Settings()
