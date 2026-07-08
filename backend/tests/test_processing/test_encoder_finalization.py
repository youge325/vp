from __future__ import annotations

from pathlib import Path

import pytest

from app.planning import SegmentManifest
from app.processing.streaming.encoder_finalization import finalize_segmented_output


class _FakeFFmpeg:
    def __init__(self, *, has_audio: bool = False, extracted_audio: bool = True) -> None:
        self.has_audio_value = has_audio
        self.extracted_audio = extracted_audio
        self.concat_calls: list[tuple[list[str], str]] = []
        self.merged: tuple[str, str, str] | None = None

    def concat_videos(self, segment_paths: list[str], output_path: str) -> str:
        self.concat_calls.append((segment_paths, output_path))
        Path(output_path).write_bytes(b"concat")
        return output_path

    def has_audio(self, _input_path: str) -> bool:
        return self.has_audio_value

    def extract_audio(self, _input_path: str, output_path: str) -> str | None:
        if not self.extracted_audio:
            return None
        Path(output_path).write_bytes(b"audio")
        return output_path

    def merge_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        self.merged = (video_path, audio_path, output_path)
        Path(output_path).write_bytes(b"merged")
        return output_path


def _manifest_with_chunk(tmp_path: Path, *, output_name: str = "out.mp4") -> SegmentManifest:
    output_path = tmp_path / output_name
    manifest = SegmentManifest(str(output_path))
    manifest.prepare("sig", {"test": True}, mode="force-fresh")
    tmp_chunk = manifest.chunk_tmp_path(".mp4", index=1)
    Path(tmp_chunk).write_bytes(b"segment")
    manifest.finalize_chunk(
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
    ffmpeg = _FakeFFmpeg(has_audio=False)

    result = finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=output_path,
        encode_config={"container": "mp4", "keepAudio": False},
        manifest=manifest,
        signature="sig",
        completed_output_frames=2,
        total_output_frames=2,
        strict_total_frames=True,
    )

    assert result == output_path
    assert Path(output_path).read_bytes() == b"concat"
    assert ffmpeg.concat_calls[0][0] == [str(manifest.sidecar_dir / manifest.read_completed_segments()[0].path)]
    assert ffmpeg.merged is None


def test_finalize_segmented_output_merges_audio_when_requested(tmp_path: Path) -> None:
    manifest = _manifest_with_chunk(tmp_path)
    output_path = str(tmp_path / "out.mp4")
    ffmpeg = _FakeFFmpeg(has_audio=True)

    result = finalize_segmented_output(
        ffmpeg=ffmpeg,
        input_path=str(tmp_path / "input.mp4"),
        output_path=output_path,
        encode_config={"container": "mp4", "keepAudio": True},
        manifest=manifest,
        signature="sig",
        completed_output_frames=2,
        total_output_frames=2,
        strict_total_frames=True,
    )

    assert result == output_path
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
            signature="sig",
            completed_output_frames=1,
            total_output_frames=2,
            strict_total_frames=True,
        )
