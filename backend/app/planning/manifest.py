"""Resume sidecar lifecycle and chunk filename conventions.

Owns ``SegmentManifest`` plus the resume-related public state and internal
chunk/decision records.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from app.planning.manifest_store import ManifestRepository
from app.planning.resume_policy import ResumeMode, decide_output_action
from app.planning.segment_workspace import SegmentWorkspace
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class _SegmentRecord:
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
    completed_segments: list[_SegmentRecord]


@dataclass(frozen=True, slots=True)
class ResumeInspection:
    """Read-only domain projection of the resumable sidecar state."""

    output_path: str
    final_exists: bool
    sidecar_exists: bool
    signature_match: bool
    completed_chunks: int
    completed_output_frames: int
    next_source_frame: int
    total_output_frames: int


_ResumeKind = Literal["fresh", "resume", "conflict_final_exists"]


@dataclass(slots=True)
class _ResumeDecision:
    """Outcome of preparing a sidecar for a run."""

    kind: _ResumeKind
    state: ResumeState
    sidecar_signature_match: bool = False


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

    def __init__(
        self,
        output_path: str | Path | None = None,
        *,
        workspace: SegmentWorkspace | None = None,
    ) -> None:
        if workspace is None:
            if output_path is None:
                raise TypeError("output_path or workspace is required")
            workspace = SegmentWorkspace.for_output(output_path)
        elif output_path is not None:
            raise TypeError("pass output_path or workspace, not both")
        self.workspace = workspace
        self.repository = ManifestRepository(workspace)

    # ------------------------------------------------------------------ prepare
    def prepare(
        self,
        signature: str,
        config_snapshot: dict[str, Any] | None = None,
        *,
        mode: ResumeMode = ResumeMode.AUTO,
    ) -> _ResumeDecision:
        """Resolve the sidecar state and return an internal decision.

        ``mode`` controls how conflicts with an already-existing final output
        are handled. The default ``"auto"`` returns ``conflict_final_exists``
        without touching the filesystem so the caller can prompt the user.
        ``"force-fresh"`` deletes both the sidecar and the existing final
        output, then returns a fresh state. ``"force-resume"`` ignores the
        existing final output and continues with whatever progress the sidecar
        contains.
        """
        config_snapshot = config_snapshot or {}

        manifest_data = self.repository.load()
        if self.workspace.sidecar_dir.is_dir() and manifest_data is None:
            self._quarantine_sidecar()
        else:
            # A leftover in-flight sentinel belongs to the current schema and
            # can be discarded; incompatible state is quarantined intact above.
            self._cleanup_partial()
        signature_match = bool(manifest_data and manifest_data.signature == signature)

        state = self._prepare_resume_state() if signature_match else self._empty_state()
        action = decide_output_action(
            final_exists=self.workspace.output_path.exists(),
            sidecar_exists=self.workspace.manifest_path.is_file(),
            signature_match=signature_match,
            has_progress=state.completed_output_frames > 0,
            mode=mode,
        )
        if action == "conflict":
            return _ResumeDecision(
                kind="conflict_final_exists",
                state=state,
                sidecar_signature_match=signature_match,
            )
        if action == "resume":
            return self._resume_decision(state)
        delete_final = self.workspace.output_path.exists() and mode == "force-fresh"
        if self.workspace.manifest_path.is_file() and not signature_match:
            return self._prepare_changed_signature(
                signature,
                config_snapshot,
                delete_final=delete_final,
            )
        return self._prepare_fresh(
            signature,
            config_snapshot,
            delete_final=delete_final,
        )

    def _resume_decision(self, state: ResumeState | None = None) -> _ResumeDecision:
        state = state or self._prepare_resume_state()
        return _ResumeDecision(
            kind="resume" if state.completed_output_frames > 0 else "fresh",
            state=state,
            sidecar_signature_match=True,
        )

    def _prepare_changed_signature(
        self,
        signature: str,
        config_snapshot: dict[str, Any],
        *,
        delete_final: bool,
    ) -> _ResumeDecision:
        self._quarantine_sidecar()
        decision = self._prepare_fresh(
            signature,
            config_snapshot,
            delete_final=delete_final,
        )
        logger.info("Configuration changed; previous progress invalidated.")
        return decision

    # -------------------------------------------------------------- inspection
    def inspect(
        self,
        signature: str,
        *,
        total_output_frames: int = 0,
    ) -> ResumeInspection:
        """Read-only probe of the sidecar state used by ``inspect-output``."""
        manifest_data = self.repository.load()
        signature_match = bool(manifest_data and manifest_data.signature == signature)

        if signature_match:
            state = self._read_resume_state()
        else:
            state = self._empty_state()

        return ResumeInspection(
            output_path=str(self.workspace.output_path),
            final_exists=self.workspace.output_path.exists(),
            sidecar_exists=self.workspace.manifest_path.is_file(),
            signature_match=signature_match,
            completed_chunks=len(state.completed_segments),
            completed_output_frames=state.completed_output_frames,
            next_source_frame=state.start_source_frame,
            total_output_frames=total_output_frames,
        )

    # ------------------------------------------------------------------ state
    def scan_completed_chunks(self) -> list[_SegmentRecord]:
        """Return chunks that form a contiguous prefix from output frame 0."""
        if not self.workspace.sidecar_dir.is_dir():
            return []

        candidates: list[_SegmentRecord] = []
        for entry in self.workspace.sidecar_dir.iterdir():
            if not entry.is_file():
                continue
            match = self.workspace.CHUNK_PATTERN.match(entry.name)
            if match is None:
                continue
            candidates.append(
                _SegmentRecord(
                    index=int(match.group("index")),
                    path=entry.name,
                    start_output_frame=int(match.group("start")),
                    end_output_frame=int(match.group("end")),
                    frame_count=int(match.group("end")) - int(match.group("start")) + 1,
                    next_source_frame=int(match.group("next_src")),
                )
            )

        candidates.sort(key=lambda record: record.index)

        contiguous: list[_SegmentRecord] = []
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

    def _cleanup_partial(self) -> None:
        """Remove in-flight sentinel files and stranded non-contiguous chunks."""
        if not self.workspace.sidecar_dir.is_dir():
            return

        for entry in self.workspace.sidecar_dir.iterdir():
            if entry.is_file() and self.workspace.TMP_PATTERN.match(entry.name):
                entry.unlink()

    def _cleanup_stale_chunks(self, keep: list[_SegmentRecord]) -> None:
        """Delete chunk files past the contiguous prefix, plus stale auxiliaries."""
        if not self.workspace.sidecar_dir.is_dir():
            return

        keep_names = {record.path for record in keep}
        keep_names.add(self.workspace.manifest_path.name)

        for entry in self.workspace.sidecar_dir.iterdir():
            if entry.name in keep_names:
                continue
            if self.workspace.TMP_PATTERN.match(entry.name):
                # already handled by cleanup_partial; keep idempotent
                entry.unlink()
                continue
            if self.workspace.CHUNK_PATTERN.match(entry.name):
                entry.unlink()
                logger.info("Discarded non-contiguous chunk %s", entry.name)

    def _quarantine_sidecar(self) -> None:
        """Move incompatible progress aside without keeping a read fallback."""
        destination = self.workspace.quarantine()
        if destination is not None:
            logger.info("Quarantined incompatible progress at %s", destination)

    # ------------------------------------------------------------- internals
    def _prepare_resume_state(self) -> ResumeState:
        chunks = self.scan_completed_chunks()
        self._cleanup_stale_chunks(chunks)
        return self._state_from_chunks(chunks)

    def _read_resume_state(self) -> ResumeState:
        return self._state_from_chunks(self.scan_completed_chunks())

    @classmethod
    def _state_from_chunks(cls, chunks: list[_SegmentRecord]) -> ResumeState:
        if not chunks:
            return cls._empty_state()
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

    def _prepare_fresh(
        self,
        signature: str,
        config_snapshot: dict[str, Any],
        *,
        delete_final: bool = False,
    ) -> _ResumeDecision:
        self.workspace.cleanup()
        if delete_final:
            self.workspace.delete_final_output()
        self.repository.write(
            signature=signature,
            config_snapshot=config_snapshot,
        )
        return _ResumeDecision(kind="fresh", state=self._empty_state())
