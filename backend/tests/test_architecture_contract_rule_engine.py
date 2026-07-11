from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from architecture_contracts.rules import (  # noqa: E402
    AbsentPathRule,
    ContractParseError,
    ForbiddenPatternRule,
    ForbiddenReferenceRule,
    RequiredPatternRule,
    run_rules,
)
from architecture_contracts.catalog import RULES  # noqa: E402
from architecture_contracts.checks import (  # noqa: E402
    _check_stage_sequence_metrics,
    _check_typed_ndjson_error_emission,
)


def test_forbidden_pattern_rule_reports_matching_source(tmp_path: Path) -> None:
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir()
    source.write_text("def obsolete_helper():\n    pass\n", encoding="utf-8")

    issues = run_rules(
        tmp_path,
        [ForbiddenPatternRule("dead-helper", "src/module.py", r"def\s+obsolete_helper\b", "dead helper")],
    )

    assert issues == ["dead helper: src/module.py"]


def test_required_pattern_rule_reports_missing_contract(tmp_path: Path) -> None:
    source = tmp_path / "contract.ts"
    source.write_text("export const value = 1\n", encoding="utf-8")

    issues = run_rules(
        tmp_path,
        [RequiredPatternRule("typed-command", "contract.ts", r"type\s+IpcCommand\b", "typed IPC command")],
    )

    assert issues == ["typed IPC command: contract.ts"]


def test_absent_path_rule_reports_reintroduced_file(tmp_path: Path) -> None:
    obsolete = tmp_path / "obsolete.py"
    obsolete.write_text("", encoding="utf-8")

    issues = run_rules(tmp_path, [AbsentPathRule("obsolete-module", "obsolete.py", "obsolete module")])

    assert issues == ["obsolete module: obsolete.py"]


def test_forbidden_reference_rule_scans_roots_and_honors_excludes(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    source_root.mkdir()
    (source_root / "consumer.py").write_text("from app.obsolete import helper\n", encoding="utf-8")
    (source_root / "allowed.py").write_text("from app.obsolete import helper\n", encoding="utf-8")

    issues = run_rules(
        tmp_path,
        [
            ForbiddenReferenceRule(
                "obsolete-import",
                roots=("src",),
                patterns=(r"app\.obsolete\b",),
                message="obsolete import",
                suffixes=(".py",),
                excludes=("src/allowed.py",),
            )
        ],
    )

    assert issues == ["obsolete import: src/consumer.py"]


def test_source_rule_raises_parse_error_for_missing_file(tmp_path: Path) -> None:
    rule = ForbiddenPatternRule("missing", "missing.py", r"anything", "missing source")

    with pytest.raises(ContractParseError, match="missing file: missing.py"):
        run_rules(tmp_path, [rule])


@pytest.mark.parametrize(
    ("rule_id", "source"),
    [
        ("base-select-local-option-type", "interface SelectOption { value: string }\n"),
        ("batch-lifecycle-type-reexport", "export type { BatchLifecycle } from './types'\n"),
        ("pipeline-owned-lifecycle", "decision = manifest.prepare('sig', {})\n"),
        ("encoder-finalization-signature", "def finalize_segmented_output(*, signature: str): pass\n"),
        (
            "worker-pipeline-plan-implementation",
            "from app.processing.streaming.worker_plans import (StageWorkerPlan, build_stage_chunk_plans)\n",
        ),
        (
            "stage-file-pipeline-chunk-implementation",
            "from app.processing.streaming.stage_file_rules import stage_signature\nstage_signature(step)\n",
        ),
        ("encoder-worker-segment-implementation", "resolve_segment_output_frame_count(writer)\n"),
        ("stage-file-chunk-input-fps", "def run_single_stage_file_chunks(input_fps):\n    pass\n"),
        ("manifest-sidecar-reset-duplicate", "def _reset_sidecar(self):\n    pass\n"),
        ("runtime-config-positional-interface", "    def legacy_tuple(self):\n        pass\n"),
        ("runtime-config-snapshots", "    workflow_json: dict[str, object]\n"),
        ("benchmark-test-runner-parameter", "def run_benchmark(options, process_runner=None):\n    pass\n"),
        ("rust-obsolete-environment-fields", "pub struct BackendDeviceSupport {}\n"),
        ("manifest-test-only-public-helpers", "    def cleanup_partial(self):\n        pass\n"),
        ("stage-worker-config-mapping-interface", "    def from_mapping(cls, payload):\n        pass\n"),
        ("legacy-anime-workflow-model", "class AnimeConfig:\n    pass\n"),
        ("legacy-anime-enhance-view", "<section>动漫优化</section>\n"),
        ("legacy-task-store-reset", "function resetBatch() {}\n"),
        ("legacy-encoded-frame-index", "output_index: int\n"),
        ("obsolete-anime-module-references", "const config = workflow.anime\n"),
        ("ffmpeg-dead-delegates", "    def parse_avoptions(self, text):\n        return []\n"),
        ("python-super-resolution-auto-download-field", "    auto_download_weights: bool = False\n"),
        ("rust-super-resolution-auto-download-field", "pub auto_download_weights: bool,\n"),
        ("public-segment-record", "class SegmentRecord:\n    pass\n"),
        ("public-reporter-progress-constants", "TERMINAL_PROGRESS_PREFIX = '[VP_PROGRESS]'\n"),
        ("public-error-code-cache", "ALL_CODES = frozenset()\n"),
        ("public-onnx-internals", "def select_onnx_providers(engine, runtime):\n    return []\n"),
        ("public-system-probe-constants", "GPU_VENDOR_KEYWORDS = {}\n"),
        ("public-file-extension-constant", "SUPPORTED_EXTENSIONS = set()\n"),
        ("public-paddlegan-weight-root", "def fixed_weight_root():\n    return None\n"),
        ("obsolete-ffmpeg-probe-imports", "from app.utils.ffmpeg.probe import get_video_info\n"),
        ("removed-super-resolution-auto-download", "config = {'autoDownloadWeights': False}\n"),
        ("obsolete-e2e-environment-fields", "const value = result.result.rifeModel\n"),
        ("obsolete-frontend-environment-protocol", "import type { AppEnv } from '@/types/domain/env'\n"),
        ("obsolete-frontend-video-info-fields", "const info = { type: 'info' }\n"),
        ("preset-sync-test-only-return", "return {\n    persistDraft,\n}\n"),
        ("enhance-onnx-alias-return", "return {\n    isOnnxBackend,\n}\n"),
        ("stage-file-chunk-encoding-leak", "frame = read_rgb_frame(stream)\n"),
        ("obsolete-decode-queue-symbols", "class DecodedFrame:\n    pass\n"),
        ("form-binding-param-export-0", "export type DecodeFormBindingParams = {}\n"),
        (
            "pipeline-test-private-aliases",
            "from app.processing.streaming.pipeline import _run_streaming_pipeline\n",
        ),
    ],
)
def test_critical_catalog_rules_reject_reintroduced_sources(tmp_path: Path, rule_id: str, source: str) -> None:
    rule = next(rule for rule in RULES if rule.rule_id == rule_id)
    if isinstance(rule, ForbiddenReferenceRule):
        for relative_root in rule.roots:
            search_root = tmp_path / relative_root
            if search_root.suffix:
                search_root.parent.mkdir(parents=True, exist_ok=True)
                search_root.write_text("", encoding="utf-8")
            else:
                search_root.mkdir(parents=True, exist_ok=True)
        first_root = tmp_path / rule.roots[0]
        target = first_root if first_root.is_file() else first_root / f"contract_violation{rule.suffixes[0]}"
    else:
        target = tmp_path / rule.path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")

    assert rule.check(tmp_path)


def test_stage_sequence_metrics_semantic_check_rejects_dead_parameter(tmp_path: Path) -> None:
    streaming = tmp_path / "backend/app/processing/streaming"
    streaming.mkdir(parents=True)
    (streaming / "stage_worker_execution.py").write_text(
        "def run_sequence_stage(config, metrics):\n    del metrics\n",
        encoding="utf-8",
    )
    (streaming / "stage_worker.py").write_text("run_sequence_stage(config, metrics)\n", encoding="utf-8")

    issues = _check_stage_sequence_metrics(tmp_path)

    assert len(issues) == 3


def test_stage_sequence_metrics_semantic_check_normalizes_python_syntax_errors(tmp_path: Path) -> None:
    streaming = tmp_path / "backend/app/processing/streaming"
    streaming.mkdir(parents=True)
    (streaming / "stage_worker_execution.py").write_text("def broken(:\n", encoding="utf-8")
    (streaming / "stage_worker.py").write_text("", encoding="utf-8")

    with pytest.raises(ContractParseError, match="could not parse Python source"):
        _check_stage_sequence_metrics(tmp_path)


def test_typed_ndjson_semantic_check_rejects_extra_manual_error_envelopes(tmp_path: Path) -> None:
    app_main = tmp_path / "backend/app/__main__.py"
    app_main.parent.mkdir(parents=True)
    app_main.write_text(
        'BOOTSTRAP = {"type": "error"}\nEXTRA = {"type": "error"}\n',
        encoding="utf-8",
    )

    assert _check_typed_ndjson_error_emission(tmp_path)
