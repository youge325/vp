"""Atomic JSON persistence for resumable segment manifests."""

from __future__ import annotations

import datetime as dt
import os
from contextlib import suppress
from typing import Any, get_args

from pydantic import ValidationError

from app.errors.codes import TaskErrorCode
from app.errors.process import ProcessError
from app.generated.contracts import SegmentManifest as SegmentManifestContract
from app.planning.segment_workspace import SegmentWorkspace

_MANIFEST_VERSION = int(get_args(SegmentManifestContract.model_fields["version"].annotation)[0])


class ManifestRepository:
    """Versioned atomic persistence for one resume manifest."""

    def __init__(self, workspace: SegmentWorkspace) -> None:
        self.workspace = workspace

    def load(self) -> SegmentManifestContract | None:
        path = self.workspace.manifest_path
        if not path.is_file():
            return None
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ProcessError(
                TaskErrorCode.PERSISTENCE_FAILED,
                f"Unable to read segment manifest {path}: {exc}",
                details={"operation": "read", "path": str(path)},
            ) from exc
        try:
            return SegmentManifestContract.model_validate_json(raw, by_alias=True, by_name=False)
        except ValidationError:
            return None

    def write(
        self,
        *,
        signature: str,
        config_snapshot: dict[str, Any],
    ) -> None:
        path = self.workspace.manifest_path
        payload = SegmentManifestContract(
            version=_MANIFEST_VERSION,
            signature=signature,
            created_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0),
            input_path=str(config_snapshot.get("input_path", "")),
            output_path=str(self.workspace.output_path),
            config_snapshot=config_snapshot,
        )
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        replaced = False
        try:
            try:
                self.workspace.ensure()
                with tmp_path.open("w", encoding="utf-8") as handle:
                    handle.write(payload.model_dump_json(by_alias=True, indent=2))
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, path)
                replaced = True
            except OSError as exc:
                raise ProcessError(
                    TaskErrorCode.PERSISTENCE_FAILED,
                    f"Unable to write segment manifest {path}: {exc}",
                    details={"operation": "write", "path": str(path)},
                ) from exc
        finally:
            if not replaced:
                with suppress(OSError):
                    tmp_path.unlink()
