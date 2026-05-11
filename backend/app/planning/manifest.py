"""Resume sidecar lifecycle and chunk filename conventions.

Owns ``SegmentManifest`` plus the resume-related dataclasses
(``ResumeState``, ``ResumeDecision``, ``SegmentRecord``) and the
``ResumeKind`` / ``ResumeMode`` literal types.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class SegmentRecord:
    """One completed chunk on disk, parsed from filename."""

    index: int
    path: str
    start_output_frame: int
    end_output_frame: int
    frame_count: int
    next_source_frame: int


@dataclass(slots=True)
class ResumeState:
    """Resume information derived from completed chunk files."""

    start_source_frame: int
    completed_output_frames: int
    completed_segments: list[SegmentRecord]


ResumeKind = Literal["fresh", "resume", "conflict_final_exists"]


@dataclass(slots=True)
class ResumeDecision:
    """Outcome of preparing a sidecar for a run."""

    kind: ResumeKind
    state: ResumeState
    sidecar_signature_match: bool = False


ResumeMode = Literal["auto", "force-fresh", "force-resume"]


class SegmentManifest:
    """Filesystem-as-state sidecar manager for resumable encoding.

    `manifest.json` only persists the configuration signature and a snapshot of
    the parameters used to start the run. Actual progress is recovered by
    scanning the sidecar directory for ``chunk-NNNN-out{start}-{end}-src{next}.{ext}``
    files which encode their frame ranges directly in the filename.

    In-flight chunks are written to the sentinel ``chunk-tmp.{ext}`` and only
    renamed into the final form after the encoder has flushed and closed; on a
    crash the sentinel remains and is purged at the start of the next run.
    """

    MANIFEST_VERSION = 2
    CHUNK_PATTERN = re.compile(
        r"^chunk-(?P<index>\d{4})-out(?P<start>\d{8})-(?P<end>\d{8})-src(?P<next_src>\d{8})\."
        r"(?P<ext>[^.]+)$"
    )
    TMP_PATTERN = re.compile(r"^chunk-tmp(?:-\d{4})?\.[^.]+$")
    TMP_PREFIX = "chunk-tmp"
    AUDIO_FILE_NAME = "source_audio.aac"
    CONCAT_BASENAME = "concat_noaudio"

    def __init__(self, output_path: str):
        output = Path(output_path)
        self.output_path = output.resolve()
        self.sidecar_dir = self.output_path.with_name(f"{self.output_path.name}.vp_segments")
        self.manifest_path = self.sidecar_dir / "manifest.json"

    # ------------------------------------------------------------------ prepare
    def prepare(
        self,
        signature: str,
        config_snapshot: dict[str, Any] | None = None,
        *,
        mode: ResumeMode = "auto",
    ) -> ResumeDecision:
        """Resolve the sidecar state and return a ResumeDecision.

        ``mode`` controls how conflicts with an already-existing final output
        are handled. The default ``"auto"`` returns ``conflict_final_exists``
        without touching the filesystem so the caller can prompt the user.
        ``"force-fresh"`` deletes both the sidecar and the existing final
        output, then returns a fresh state. ``"force-resume"`` ignores the
        existing final output and continues with whatever progress the sidecar
        contains.
        """
        config_snapshot = config_snapshot or {}

        # Always purge a leftover in-flight sentinel before doing anything
        # else; whatever was being written last time is unrecoverable.
        self.cleanup_partial()

        manifest_data = self._load_manifest_safe()
        signature_match = bool(manifest_data and manifest_data.get("signature") == signature)

        if self.output_path.exists():
            if mode == "auto":
                state = self._scan_resume_state() if signature_match else self._empty_state()
                return ResumeDecision(
                    kind="conflict_final_exists",
                    state=state,
                    sidecar_signature_match=signature_match,
                )
            if mode == "force-fresh":
                self._reset_sidecar()
                self._delete_final_output()
                self._write_manifest(signature, config_snapshot)
                return ResumeDecision(kind="fresh", state=self._empty_state())
            if mode == "force-resume":
                if not signature_match:
                    self._reset_sidecar()
                    self._write_manifest(signature, config_snapshot)
                    logger.info("Configuration changed; previous progress invalidated.")
                    return ResumeDecision(kind="fresh", state=self._empty_state())
                state = self._scan_resume_state()
                return ResumeDecision(
                    kind="resume" if state.completed_output_frames > 0 else "fresh",
                    state=state,
                    sidecar_signature_match=True,
                )

        if not self.manifest_path.is_file():
            self._reset_sidecar()
            self._write_manifest(signature, config_snapshot)
            return ResumeDecision(kind="fresh", state=self._empty_state())

        if not signature_match:
            self._reset_sidecar()
            self._write_manifest(signature, config_snapshot)
            logger.info("Configuration changed; previous progress invalidated.")
            return ResumeDecision(kind="fresh", state=self._empty_state())

        state = self._scan_resume_state()
        return ResumeDecision(
            kind="resume" if state.completed_output_frames > 0 else "fresh",
            state=state,
            sidecar_signature_match=True,
        )

    # -------------------------------------------------------------- inspection
    def inspect(
        self,
        signature: str,
        *,
        total_output_frames: int = 0,
    ) -> dict[str, Any]:
        """Read-only probe of the sidecar state used by ``inspect-output``."""
        manifest_data = self._load_manifest_safe()
        signature_match = bool(manifest_data and manifest_data.get("signature") == signature)

        if signature_match:
            state = self._scan_resume_state()
        else:
            state = self._empty_state()

        return {
            "outputPath": str(self.output_path),
            "finalExists": self.output_path.exists(),
            "sidecarExists": self.manifest_path.is_file(),
            "signatureMatch": signature_match,
            "completedChunks": len(state.completed_segments),
            "completedOutputFrames": state.completed_output_frames,
            "nextSourceFrame": state.start_source_frame,
            "totalOutputFrames": total_output_frames,
        }

    # ---------------------------------------------------------- chunk filenames
    def chunk_tmp_path(self, extension: str, *, index: int | None = None) -> str:
        """Return the in-flight sentinel path for the encoder.

        A per-chunk index suffix (``chunk-tmp-NNNN.{ext}``) is used so that a
        previously-renamed sentinel cannot collide with the new ffmpeg process
        on Windows where rapid same-path reuse can wedge the stdin pipe.
        """
        resolved_extension = extension if extension.startswith(".") else f".{extension}"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        suffix = f"-{index:04d}" if index is not None else ""
        return str(self.sidecar_dir / f"{self.TMP_PREFIX}{suffix}{resolved_extension}")

    def chunk_final_path(
        self,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
        extension: str,
    ) -> str:
        """Compute the deterministic final filename for a sealed chunk."""
        resolved_extension = extension if extension.startswith(".") else f".{extension}"
        name = (
            f"chunk-{index:04d}"
            f"-out{start_output_frame:08d}-{end_output_frame:08d}"
            f"-src{next_source_frame:08d}{resolved_extension}"
        )
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        return str(self.sidecar_dir / name)

    def finalize_chunk(
        self,
        tmp_path: str,
        *,
        index: int,
        start_output_frame: int,
        end_output_frame: int,
        next_source_frame: int,
    ) -> str:
        """Atomically rename the sentinel file to its canonical chunk name."""
        extension = Path(tmp_path).suffix
        final_path = self.chunk_final_path(
            index=index,
            start_output_frame=start_output_frame,
            end_output_frame=end_output_frame,
            next_source_frame=next_source_frame,
            extension=extension,
        )
        os.replace(tmp_path, final_path)
        return final_path

    def concat_temp_path(self, extension: str) -> str:
        """Return the temporary concat output path inside the sidecar directory."""
        resolved_extension = extension if extension.startswith(".") else f".{extension}"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        return str(self.sidecar_dir / f"{self.CONCAT_BASENAME}{resolved_extension}")

    # ------------------------------------------------------------------ state
    def scan_completed_chunks(self) -> list[SegmentRecord]:
        """Return chunks that form a contiguous prefix from output frame 0."""
        if not self.sidecar_dir.is_dir():
            return []

        candidates: list[SegmentRecord] = []
        for entry in self.sidecar_dir.iterdir():
            if not entry.is_file():
                continue
            match = self.CHUNK_PATTERN.match(entry.name)
            if match is None:
                continue
            candidates.append(
                SegmentRecord(
                    index=int(match.group("index")),
                    path=entry.name,
                    start_output_frame=int(match.group("start")),
                    end_output_frame=int(match.group("end")),
                    frame_count=int(match.group("end")) - int(match.group("start")) + 1,
                    next_source_frame=int(match.group("next_src")),
                )
            )

        candidates.sort(key=lambda record: record.index)

        contiguous: list[SegmentRecord] = []
        expected_index = 1
        expected_start = 0
        for record in candidates:
            if record.index != expected_index:
                break
            if record.start_output_frame != expected_start:
                break
            if record.frame_count <= 0:
                break
            contiguous.append(record)
            expected_index += 1
            expected_start = record.end_output_frame + 1

        return contiguous

    def cleanup_partial(self) -> None:
        """Remove in-flight sentinel files and stranded non-contiguous chunks."""
        if not self.sidecar_dir.is_dir():
            return

        for entry in self.sidecar_dir.iterdir():
            if entry.is_file() and self.TMP_PATTERN.match(entry.name):
                try:
                    entry.unlink()
                except OSError:
                    logger.warning("Failed to remove stale sentinel %s", entry)

    def cleanup_stale_chunks(self, keep: list[SegmentRecord]) -> None:
        """Delete chunk files past the contiguous prefix, plus stale auxiliaries."""
        if not self.sidecar_dir.is_dir():
            return

        keep_names = {record.path for record in keep}
        keep_names.add(self.manifest_path.name)

        for entry in self.sidecar_dir.iterdir():
            if entry.name in keep_names:
                continue
            if self.TMP_PATTERN.match(entry.name):
                # already handled by cleanup_partial; keep idempotent
                try:
                    entry.unlink()
                except OSError:
                    pass
                continue
            if self.CHUNK_PATTERN.match(entry.name):
                try:
                    entry.unlink()
                    logger.info("Discarded non-contiguous chunk %s", entry.name)
                except OSError:
                    logger.warning("Failed to remove stale chunk %s", entry)

    def cleanup(self) -> None:
        """Delete the sidecar directory after a successful run."""
        if self.sidecar_dir.is_dir():
            shutil.rmtree(self.sidecar_dir, ignore_errors=True)

    def read_completed_segments(self) -> list[SegmentRecord]:
        """Compatibility shim: read contiguous completed chunks from disk."""
        return self.scan_completed_chunks()

    # ------------------------------------------------------------- internals
    def _scan_resume_state(self) -> ResumeState:
        chunks = self.scan_completed_chunks()
        self.cleanup_stale_chunks(chunks)
        if not chunks:
            return self._empty_state()
        last = chunks[-1]
        return ResumeState(
            start_source_frame=last.next_source_frame,
            completed_output_frames=last.end_output_frame + 1,
            completed_segments=chunks,
        )

    @staticmethod
    def _empty_state() -> ResumeState:
        return ResumeState(
            start_source_frame=0,
            completed_output_frames=0,
            completed_segments=[],
        )

    def _reset_sidecar(self) -> None:
        if self.sidecar_dir.is_dir():
            shutil.rmtree(self.sidecar_dir, ignore_errors=True)

    def _delete_final_output(self) -> None:
        if self.output_path.is_file():
            self.output_path.unlink()

    def _write_manifest(self, signature: str, config_snapshot: dict[str, Any]) -> None:
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": self.MANIFEST_VERSION,
            "signature": signature,
            "created_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "input_path": str(config_snapshot.get("input_path", "")),
            "output_path": str(self.output_path),
            "config_snapshot": config_snapshot,
        }
        tmp_path = self.manifest_path.with_suffix(self.manifest_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        os.replace(tmp_path, self.manifest_path)

    def _load_manifest_safe(self) -> dict[str, Any] | None:
        if not self.manifest_path.is_file():
            return None
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or data.get("version") != self.MANIFEST_VERSION:
            return None
        return data
