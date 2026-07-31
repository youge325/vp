from __future__ import annotations

from pathlib import Path

from app.planning.manifest import SegmentManifest
from app.planning.manifest_store import ManifestRepository
from app.planning.segment_workspace import SegmentWorkspace


def test_segment_workspace_is_the_single_path_owner(tmp_path: Path) -> None:
    output_path = tmp_path / "render.mp4"
    workspace = SegmentWorkspace.for_output(output_path)

    assert workspace.output_path == output_path.resolve()
    assert workspace.sidecar_dir == output_path.resolve().with_name("render.mp4.vp_segments")
    assert workspace.manifest_path == workspace.sidecar_dir / "manifest.json"
    assert workspace.stages_dir == workspace.sidecar_dir / "stages"
    assert workspace.chunk_tmp_path(".mp4", index=2).endswith("chunk-tmp-0002.mp4")
    assert workspace.concat_temp_path("mp4").endswith("concat_noaudio.mp4")


def test_manifest_and_repository_depend_on_segment_workspace(tmp_path: Path) -> None:
    workspace = SegmentWorkspace.for_output(tmp_path / "render.mp4")
    repository = ManifestRepository(workspace)
    manifest = SegmentManifest(workspace=workspace, repository=repository)

    assert manifest.workspace is workspace
    assert manifest.repository.workspace is workspace
    assert repository.workspace is workspace
    assert not hasattr(manifest, "sidecar_dir")
    assert not hasattr(manifest, "manifest_path")
