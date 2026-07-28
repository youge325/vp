"""Filesystem paths and mutations for resumable segment workspaces."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SegmentWorkspace:
    """Own every path derived from a segmented output target."""

    output_path: Path
    sidecar_dir: Path

    MANIFEST_NAME = "manifest.json"
    TMP_PREFIX = "chunk-tmp"
    CONCAT_BASENAME = "concat_noaudio"
    CHUNK_PATTERN = re.compile(
        r"^chunk-(?P<index>\d{4})-out(?P<start>\d{8})-(?P<end>\d{8})-src(?P<next_src>\d{8})\."
        r"(?P<ext>[^.]+)$"
    )
    TMP_PATTERN = re.compile(r"^chunk-tmp(?:-\d{4})?\.[^.]+$")

    @classmethod
    def for_output(cls, output_path: str | Path) -> SegmentWorkspace:
        output = Path(output_path).expanduser().resolve()
        return cls(
            output_path=output,
            sidecar_dir=output.with_name(f"{output.name}.vp_segments"),
        )

    @property
    def manifest_path(self) -> Path:
        return self.sidecar_dir / self.MANIFEST_NAME

    @property
    def stages_dir(self) -> Path:
        return self.sidecar_dir / "stages"

    def ensure(self) -> None:
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)

    def chunk_tmp_path(self, extension: str, *, index: int | None = None) -> str:
        self.ensure()
        suffix = f"-{index:04d}" if index is not None else ""
        return str(self.sidecar_dir / f"{self.TMP_PREFIX}{suffix}{self._extension(extension)}")

    def chunk_final_path(
        self,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
        extension: str,
    ) -> str:
        self.ensure()
        name = (
            f"chunk-{index:04d}"
            f"-out{start_output_frame:08d}-{end_output_frame:08d}"
            f"-src{next_source_frame:08d}{self._extension(extension)}"
        )
        return str(self.sidecar_dir / name)

    def finalize_chunk(
        self,
        tmp_path: str,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
    ) -> None:
        final_path = self.chunk_final_path(
            index=index,
            start_output_frame=start_output_frame,
            end_output_frame=end_output_frame,
            next_source_frame=next_source_frame,
            extension=Path(tmp_path).suffix,
        )
        os.replace(tmp_path, final_path)

    def concat_temp_path(self, extension: str) -> str:
        self.ensure()
        return str(self.sidecar_dir / f"{self.CONCAT_BASENAME}{self._extension(extension)}")

    def cleanup(self) -> None:
        if self.sidecar_dir.is_dir():
            shutil.rmtree(self.sidecar_dir)

    def quarantine(self) -> Path | None:
        if not self.sidecar_dir.is_dir():
            return None
        base = self.sidecar_dir.with_name(f"{self.sidecar_dir.name}.incompatible")
        destination = base
        suffix = 1
        while destination.exists():
            destination = base.with_name(f"{base.name}-{suffix}")
            suffix += 1
        os.replace(self.sidecar_dir, destination)
        return destination

    def delete_final_output(self) -> None:
        if self.output_path.is_file():
            self.output_path.unlink()

    @staticmethod
    def _extension(extension: str) -> str:
        return extension if extension.startswith(".") else f".{extension}"


__all__ = ["SegmentWorkspace"]
