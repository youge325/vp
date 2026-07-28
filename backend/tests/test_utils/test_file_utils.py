from pathlib import Path

from app.utils.file_utils import prepare_default_output_path


def test_prepare_default_output_path_creates_directory_and_uses_container(tmp_path: Path) -> None:
    output_dir = tmp_path / "nested" / "output"

    output_path = prepare_default_output_path(
        str(tmp_path / "source.video.mov"),
        str(output_dir),
        "mkv",
    )

    assert Path(output_path) == output_dir / "source.video_processed.mkv"
    assert output_dir.is_dir()


def test_prepare_default_output_path_accepts_dotted_container(tmp_path: Path) -> None:
    output_path = prepare_default_output_path(
        str(tmp_path / "source.mp4"),
        str(tmp_path / "output"),
        ".webm",
    )

    assert Path(output_path).suffix == ".webm"
