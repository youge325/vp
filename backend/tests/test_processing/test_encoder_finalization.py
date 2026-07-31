from __future__ import annotations

from pathlib import Path

import pytest

from app.planning.manifest import SegmentManifest
from tests.support.streaming_runtime import create_test_manifest
from app.processing.streaming.encoder_finalization import finalize_segmented_output


class _FakeFFmpeg:
    def __init__(self, *, extracted_audio: bool = True) -> None:
        self.extracted_audio = extracted_audio
        self.concat_calls: list[tuple[list[str], str]] = []
        self.merged: tuple[str, str, str] | None = None

    def concat_videos(self, segment_paths: list[str], output_path: str) -> None:
        self.concat_calls.append((segment_paths, output_path))
        Path(output_path).write_bytes(b"concat")

    def extract_audio(self, _input_path: str, output_path: str) -> bool:
        if not self.extracted_audio:
            return False
        Path(output_path).write_bytes(b"audio")
        return True

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> None:
        self.merged = (video_path, audio_path, output_path)
        Path(output_path).write_bytes(b"merged")


def _manifest_with_chunk(tmp_path: Path, *, output_name: str = "out.mp4") -> SegmentManifest:
    output_path = tmp_path / output_name
    manifest = create_test_manifest(str(output_path))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    tmp_chunk = manifest.workspace.chunk_tmp_path(".mp4", index=1)
    Path(tmp_chunk).write_bytes(b"segment")
    manifest.workspace.finalize_chunk(
        tmp_chunk,
        index=1,
        start_output_frame=0,
        end_output_frame=1,
        next_source_frame=2,
    )
    return manifest


def test_finalize_segmented_output_concats_segments_without_audio(tmp_path: Path) -> None:
    manifest = _manifest_with_chunk(tmp_path)
    output_path = str(tmp_path / "out.mp4")
    ffmpeg = _FakeFFmpeg()

    finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=output_path,
        encode_config={"container": "mp4", "keepAudio": False},
        manifest=manifest,
        completed_output_frames=2,
        total_output_frames=2,
        strict_total_frames=True,
        source_has_audio=False,
    )

    assert Path(output_path).read_bytes() == b"concat"
    assert ffmpeg.concat_calls[0][0] == [str(manifest.workspace.sidecar_dir / manifest.scan_completed_chunks()[0].path)]
    assert ffmpeg.merged is None


def test_finalize_segmented_output_merges_audio_when_requested(tmp_path: Path) -> None:
    manifest = _manifest_with_chunk(tmp_path)
    output_path = str(tmp_path / "out.mp4")
    ffmpeg = _FakeFFmpeg()

    finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=output_path,
        encode_config={"container": "mp4", "keepAudio": True},
        manifest=manifest,
        completed_output_frames=2,
        total_output_frames=2,
        strict_total_frames=True,
        source_has_audio=True,
    )

    assert Path(output_path).read_bytes() == b"merged"
    assert ffmpeg.merged is not None
    assert not Path(ffmpeg.merged[0]).exists()
    assert not Path(ffmpeg.merged[1]).exists()


def test_finalize_segmented_output_rejects_incomplete_strict_totals(tmp_path: Path) -> None:
    manifest = _manifest_with_chunk(tmp_path)

    with pytest.raises(RuntimeError, match="Temporary segments are incomplete"):
        finalize_segmented_output(
            ffmpeg=_FakeFFmpeg(),
            input_path=str(tmp_path / "input.mp4"),
            output_path=str(tmp_path / "out.mp4"),
            encode_config={"container": "mp4", "keepAudio": False},
            manifest=manifest,
            completed_output_frames=1,
            total_output_frames=2,
            strict_total_frames=True,
            source_has_audio=False,
        )
