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
from architecture_contracts.catalog import (  # noqa: E402
    FORBIDDEN_PATTERN_RULES,
    REQUIRED_PATTERN_RULES,
    RULES,
)
from architecture_contracts.checks import (  # noqa: E402
    _check_rust_public_surface,
    _check_stage_sequence_metrics,
    _check_typed_ndjson_error_emission,
)


@pytest.mark.parametrize(
    ("rule", "source_text", "expected"),
    [
        (
            ForbiddenPatternRule("dead-helper", "contract.ts", r"obsolete_helper", "dead helper"),
            "obsolete_helper()\n",
            ["dead helper: contract.ts"],
        ),
        (
            ForbiddenPatternRule("dead-helper", "contract.ts", r"obsolete_helper", "dead helper"),
            "supported_helper()\n",
            [],
        ),
        (
            RequiredPatternRule("typed-command", "contract.ts", r"type\s+IpcCommand\b", "typed IPC command"),
            "type IpcCommand = string\n",
            [],
        ),
        (
            RequiredPatternRule("typed-command", "contract.ts", r"type\s+IpcCommand\b", "typed IPC command"),
            "export const value = 1\n",
            ["typed IPC command: contract.ts"],
        ),
    ],
)
def test_pattern_rule_polarity(
    tmp_path: Path,
    rule: ForbiddenPatternRule | RequiredPatternRule,
    source_text: str,
    expected: list[str],
) -> None:
    source = tmp_path / "contract.ts"
    source.write_text(source_text, encoding="utf-8")

    assert run_rules(tmp_path, [rule]) == expected


def test_pattern_rule_catalogs_are_classified_by_polarity() -> None:
    assert not any(isinstance(rule, RequiredPatternRule) for rule in FORBIDDEN_PATTERN_RULES)
    assert all(isinstance(rule, RequiredPatternRule) for rule in REQUIRED_PATTERN_RULES)


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
        ("obsolete-batch-lifecycle-facade-reference", "createBatchLifecycle(deps)\n"),
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
        (
            "encoder-worker-static-config-signature",
            "def run_encoder_worker(*, ffmpeg: object, encode_queue: object):\n    pass\n",
        ),
        (
            "raw-encoder-static-config-signature",
            "def start_raw_encoder_thread(*, output_width: int, encode_queue: object):\n    pass\n",
        ),
        ("encoder-writer-public-config-state", "self.manifest = manifest\n"),
        ("encoder-writer-seal-result", "def seal_if_ready(self, next_source_frame: int) -> bool:\n    return True\n"),
        ("stage-file-chunk-input-fps", "def run_single_stage_file_chunks(input_fps):\n    pass\n"),
        ("manifest-sidecar-reset-duplicate", "def _reset_sidecar(self):\n    pass\n"),
        ("runtime-config-positional-interface", "    def legacy_tuple(self):\n        pass\n"),
        ("runtime-config-snapshots", "    workflow_json: dict[str, object]\n"),
        ("benchmark-test-runner-parameter", "def run_benchmark(options, process_runner=None):\n    pass\n"),
        ("rust-obsolete-environment-fields", "pub struct BackendDeviceSupport {}\n"),
        ("rust-public-internal-root-modules", "pub mod protocol;\n"),
        ("rust-public-environment-model-module", "pub mod env;\n"),
        ("rust-public-model-root-reexports", "pub use task::TaskRequest;\n"),
        (
            "frontend-resume-inspection-protocol-mirror",
            "export interface ResumeInspectionResult {}\n",
        ),
        (
            "frontend-resume-conflict-dead-state",
            "export interface ResumeConflictDescriptor { itemId: string }\n",
        ),
        (
            "frontend-resume-conflict-stale-test-fixtures",
            "const conflict = { kind: 'final_exists_no_resume', inspection: {} }\n",
        ),
        (
            "frontend-resume-conflict-e2e-helper-bypass",
            "pinia.state.value.task.pendingConflict = conflict\n",
        ),
        (
            "frontend-resume-conflict-wire-fabrication",
            "function buildInspectionFromError() { return { pipeline_kind: 'streaming' } }\n",
        ),
        (
            "frontend-unused-task-error-code-aliases",
            "export const TASK_ERROR_CODES = { MissingModel: 'missing_model' }\n",
        ),
        ("frontend-resume-status-protocol-mirror", "export interface ResumeStatus {}\n"),
        (
            "frontend-resume-mode-protocol-mirror",
            "export type ResumeMode = 'auto' | 'force-fresh'\n",
        ),
        ("frontend-video-info-result-alias", "export type VideoInfoResult = VideoInfo\n"),
        (
            "python-error-inference-string-interface",
            "def infer_error_code(exc_or_message: BaseException | str):\n    pass\n",
        ),
        (
            "rust-command-manifest-test-interface",
            "#[allow(dead_code)]\npub const APP_COMMAND_NAMES: &[&str] = &[];\n",
        ),
        ("rust-command-manifest-module", "mod commands_manifest;\n"),
        ("rust-command-manifest-test-include", "#[cfg(test)]\nmod tests {}\n"),
        (
            "protocol-reporter-metrics-view-import",
            "from app.protocol.metrics_view import MetricsSnapshot\n",
        ),
        ("protocol-reporter-private-metrics-contract", "class Reporter:\n    pass\n"),
        (
            "frame-filter-write-only-logger",
            "from app.utils.logger import get_logger\nlogger = get_logger(__name__)\n",
        ),
        (
            "frame-filter-imperative-dispatch",
            "if kind == 'scale':\n    return self._apply_scale(frame, params)\n",
        ),
        ("parallel-frame-filter-handler-maps", "_NUMPY_FILTER_HANDLERS = {}\n"),
        ("frame-filter-kind-capability-branch", "if kind == 'denoise':\n    return False\n"),
        (
            "rust-untyped-resume-inspection-command",
            "async fn check_resume_state() -> Result<Value, ShellError> { todo!() }\n",
        ),
        ("generated-resume-inspection-contract", "export type ResumeInspectionResult = {}\n"),
        ("resume-inspection-json-schema", "{}\n"),
        ("rust-resume-mode-contract", "pub enum ResumeMode { Auto }\n"),
        ("frontend-resume-mode-protocol-export", "export type { TaskRequest } from './TaskRequest'\n"),
        ("task-request-resume-mode-schema", "{}\n"),
        ("rust-runtime-output-dir-state", "pub output_dir: PathBuf,\n"),
        (
            "rust-environment-fingerprint-output-dir",
            'let value = json!({"outputDir": paths.output_dir});\n',
        ),
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
        ("obsolete-gpu-device-type", "def _classify_gpu_device_type(name):\n    return 'virtual'\n"),
        (
            "environment-gpu-adapter-projection",
            "public_gpu_adapters = [{'name': adapter['name']} for adapter in gpu_adapters]\n",
        ),
        (
            "frontend-virtual-gpu-filtering",
            "const adapters = gpu.adapters.filter((adapter) => adapter.vendor === 'nvidia')\n",
        ),
        ("public-file-extension-constant", "SUPPORTED_EXTENSIONS = set()\n"),
        ("public-paddlegan-weight-root", "def fixed_weight_root():\n    return None\n"),
        ("obsolete-ffmpeg-probe-imports", "from app.utils.ffmpeg.probe import get_video_info\n"),
        (
            "obsolete-stage-file-rules-reference",
            "from app.processing.streaming.stage_file_rules import stage_signature\n",
        ),
        ("removed-super-resolution-auto-download", "config = {'autoDownloadWeights': False}\n"),
        ("obsolete-e2e-environment-fields", "const value = result.result.rifeModel\n"),
        ("obsolete-frontend-environment-protocol", "import type { AppEnv } from '@/types/domain/env'\n"),
        ("obsolete-frontend-video-info-fields", "const info = { type: 'info' }\n"),
        ("preset-sync-test-only-return", "return {\n    persistDraft,\n}\n"),
        ("enhance-onnx-alias-return", "return {\n    isOnnxBackend,\n}\n"),
        (
            "enhance-model-selection-dead-output",
            "interface EnhanceModelSelection {\n  currentSuperResolutionModelDetail: ModelVariantInfo\n}\n",
        ),
        (
            "enhance-runtime-view-dead-output",
            "interface EnhanceRuntimeView {\n  superResolutionRuntimeEstimate: RuntimeMetricEstimate\n}\n",
        ),
        ("enhance-model-selection-return-mirror", "interface EnhanceModelSelection {}\n"),
        ("enhance-runtime-estimates-return-mirror", "interface EnhanceRuntimeEstimates {}\n"),
        ("enhance-runtime-rows-return-mirror", "interface EnhanceRuntimeRows {}\n"),
        ("rate-control-view-state-return-mirror", "interface RateControlViewState {}\n"),
        ("batch-preflight-verdict-return-mirror", "interface BatchPreflightVerdict {}\n"),
        ("algorithm-lens-return-mirror", "interface AlgorithmLens {}\n"),
        ("enhance-view-model-internal-output", "interface EnhanceViewModel {}\n"),
        ("positional-workbench-module-access", "const module = WORKBENCH_MODULES[0]\n"),
        ("hardcoded-workbench-module-route", "const route = { path: '/home' }\n"),
        ("stage-file-chunk-encoding-leak", "frame = read_rgb_frame(stream)\n"),
        ("obsolete-decode-queue-symbols", "class DecodedFrame:\n    pass\n"),
        ("form-binding-param-export-0", "export type DecodeFormBindingParams = {}\n"),
        (
            "filter-step-number-event-glue",
            '@input="patch((params) => params.x = Number(($event.target as HTMLInputElement).value))"\n',
        ),
        ("batch-runner-interface-mirror", "export interface BatchRunner {}\n"),
        ("batch-event-interface-mirror", "interface EventHandlers {}\n"),
        ("worker-runtime-lifecycle-0", "spawn_stage_workers(plans)\n"),
        ("worker-runtime-lifecycle-1", "threading.Thread(target=run)\n"),
        ("worker-processes-public-lifecycle-helpers", "def spawn_stage_workers(plans):\n    pass\n"),
        (
            "stage-worker-frame-count-return",
            "def run_stage_worker_stream(config, input_stream, output_stream) -> int:\n    return written\n",
        ),
        (
            "stage-worker-execution-frame-count-return",
            "def run_sequence_stage(config, input_stream, output_stream) -> int:\n    return len(output_frames)\n",
        ),
        (
            "native-dll-registration-result",
            "def register_native_dll_paths() -> list[Path]:\n    return targets\n",
        ),
        ("video-dimension-stream-loop-0", "for stream in info.get('streams', []):\n    pass\n"),
        ("video-dimension-stream-loop-1", "for stream in info.get('streams', []):\n    pass\n"),
        ("benchmark-direction-comparator-duplicates", "def _compare_lower_is_worse():\n    pass\n"),
        (
            "paddlegan-inline-chunk-trace",
            "    def _process_window_model(self):\n        trace_chunks.append({})\n",
        ),
        ("batch-conflict-return-interface-mirror", "interface ConflictResolver {}\n"),
        (
            "obsolete-decoded-frame-writer-starter",
            "start_decoded_frame_writer(config, thread_name='decode')\n",
        ),
        (
            "decoded-frame-writer-video-info-bag",
            "class DecodedFrameWriterConfig:\n    video_info: dict\n",
        ),
        ("decoded-writer-manual-lifecycle-0", "decode_thread.join()\n"),
        ("decoded-writer-manual-lifecycle-1", "decode_thread.join()\n"),
        (
            "stage-file-chunk-requeued-raised-error",
            "except BaseException as exc:\n    error_queue.put(exc)\n    raise\n",
        ),
        (
            "benchmark-success-report-prewrite",
            "_write_reports(report, json_path=json_path, markdown_path=markdown_path)\n"
            "baseline = _load_baseline(baseline_path)\n",
        ),
        (
            "obsolete-decoder-hardware-probe-interfaces",
            "probe_decoder_hardware_devices('ffmpeg', 'h264', 'h264', [], [], set())\n",
        ),
        (
            "task-listener-forwarding-adapter",
            "listenTaskEvents({ onProgress: (payload) => runner.onProgress(payload) })\n",
        ),
        (
            "optional-resume-event-handler",
            "interface Handlers { onResumeStatus?: (payload: object) => void }\n",
        ),
        (
            "duplicated-pause-resume-transitions",
            "async function pause() { await deps.pauseTask() }\nasync function resume() { await deps.resumeTask() }\n",
        ),
        (
            "duplicated-console-task-state-lookups",
            "function onProgress() { const item = getConsoleItem() }\n",
        ),
        (
            "pipeline-stream-fps-multi-rule",
            "def resolved_stream_fps(source_fps, stage_plan):\n"
            "    return source_fps * stage_plan.interpolation_step.algorithm_kwargs['multi']\n",
        ),
        (
            "paddlegan-output-conversion-duplicates",
            "def _sequence_tensor_to_frames(tensor):\n    array = _as_numpy(tensor)\n",
        ),
        (
            "duplicate-workflow-summary-label",
            "const workflowLabel = computed(() => workflow.interpolation.enabled ? '补帧' : '转码')\n",
        ),
        ("app-task-status-projection", "const shell = useAppShellStatus()\n"),
        ("step-rail-task-status-projection", "const state = useTaskOrchestrator()\n"),
        ("task-orchestrator-current-item-return", "return { currentTaskItem }\n"),
        (
            "task-orchestrator-direct-media-search",
            "const item = mediaStore.mediaItems.find((candidate) => candidate.id === id)\n",
        ),
        (
            "task-orchestrator-listener-lifecycle-return",
            "return { attachTaskListeners }\n",
        ),
        (
            "rust-task-controller-argument-suppression",
            "#[allow(clippy::too_many_arguments)]\nfn spawn_task_controller() {}\n",
        ),
        (
            "rust-task-controller-watchdog-config",
            "struct WatchdogConfig { stall_timeout: Duration }\n",
        ),
        (
            "rust-cancelling-started-at",
            "enum TaskStatePhase { Cancelling { started_at: Instant } }\n",
        ),
        (
            "rust-task-spawn-runtime-policy",
            "let controller = process_control::default_controller();\n",
        ),
        (
            "rust-split-ffmpeg-tool-resolvers",
            "fn resolve_ffmpeg_path() {}\nfn resolve_ffprobe_path() {}\n",
        ),
        (
            "settings-runtime-root-path-forwarder",
            "def runtime_root_path(self) -> Path | None:\n    return _resolve_path(self.RUNTIME_ROOT)\n",
        ),
        (
            "settings-python-candidate-builder",
            "def _candidate_python_paths(runtime_root: Path) -> list[Path]:\n    return []\n",
        ),
        (
            "stage-file-chunks-static-config-signature",
            "def run_single_stage_file_chunks(*, ffmpeg: object) -> int:\n    return 0\n",
        ),
        (
            "stage-file-chunk-runtime-static-config-signature",
            "def run_stage_chunk_to_file(*, input_path: str) -> int:\n    return 0\n",
        ),
        (
            "stage-file-encoder-static-config-signature",
            "def encode_stage_worker_output(*, output_width: int) -> int:\n    return 0\n",
        ),
        ("cli-startup-hook-forwarder", "def _startup_hooks():\n    pass\n"),
        ("obsolete-app-shell-status-reference", "useAppShellStatus()\n"),
        (
            "stage-worker-python-executable-plumbing",
            "def run_worker_chain(*, python_executable=None):\n    pass\n",
        ),
        (
            "stage-worker-factory-injection-parameters",
            "def run_stage_worker_stream(*, algorithm_factory=None):\n    pass\n",
        ),
        (
            "optional-stage-worker-event-sink",
            "def run_stage_worker_stream(*, event_sink: EventSink | None = None):\n    pass\n",
        ),
        (
            "stage-event-stream-injection",
            "def emit_stage_event(event, *, stream=None):\n    pass\n",
        ),
        (
            "logging-configuration-injection",
            "def setup_logging(log_dir=None, force=False):\n    pass\n",
        ),
        (
            "native-dll-path-injection",
            "def register_native_dll_paths(tensorrt_dir=None, extra=None):\n    pass\n",
        ),
        (
            "pipeline-test-private-aliases",
            "from app.processing.streaming.pipeline import _run_streaming_pipeline\n",
        ),
        ("algorithm-info-private-alias", "type AlgorithmSpec = AlgorithmInfo\n"),
        (
            "paddlegan-tensorrt-config-result",
            "def _configure_tensorrt_config(config) -> Any:\n    return config\n",
        ),
        (
            "manifest-finalize-chunk-result",
            "class Manifest:\n    def finalize_chunk(self) -> str:\n        return final_path\n",
        ),
        (
            "ffmpeg-encode-command-results",
            "def concat_videos() -> str:\n    return output_path\n",
        ),
        (
            "ffmpeg-wrapper-command-results",
            "class Wrapper:\n    def transcode_video(self) -> str:\n        return _encode.transcode_video()\n",
        ),
        (
            "ffmpeg-audio-command-path-results",
            "def merge_audio(video_path, audio_path, output_path) -> str:\n    return output_path\n",
        ),
        (
            "ffmpeg-wrapper-audio-command-path-results",
            "class Wrapper:\n    def merge_audio(self, video_path, audio_path, output_path) -> str:\n        return output_path\n",
        ),
        (
            "encoder-finalization-path-result",
            "def finalize_segmented_output(output_path) -> str:\n    return output_path\n",
        ),
        (
            "assigned-segmented-finalization-result",
            "final_output = finalize_segmented_output(output_path='out.mp4')\n",
        ),
        ("obsolete-segment-progress-adapter", "make_segment_progress_callback(10, callback)\n"),
        (
            "inline-encode-progress-adapter",
            "progress_callback=lambda progress: progress.get('fps') and progress.get('out_time_seconds')\n",
        ),
        (
            "duplicate-frame-filter-crop-params",
            "def _apply_numpy_crop(frame, params):\n    return params.get('x')\n",
        ),
        (
            "duplicate-frame-filter-padding-params",
            "def _apply_tensor_pad(frame, params):\n    return params.get('top')\n",
        ),
        (
            "rust-inline-backend-error-payload",
            "match status { Ok(_) => TaskErrorPayload { code, message, details } }\n",
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


@pytest.mark.parametrize(
    ("rule_id", "source"),
    [
        (
            "shared-ffmpeg-encode-progress-adapter",
            "EncodeProgressCallback = Callable[[int], None]\n"
            "def make_encode_progress_callback(callback, *, frame_offset: int = 0):\n    pass\n",
        ),
        (
            "frontend-resume-conflict-domain-projection",
            "function createResumeConflictDescriptor(source) {\n"
            "  const kind = source.signatureMatch && source.completedChunks > 0\n"
            "  return { kind, progress: {} }\n"
            "}\n"
            "export function buildResumeConflictDescriptor(inspection) {\n"
            "  return createResumeConflictDescriptor(inspection)\n"
            "}\n"
            "export function buildResumeConflictDescriptorFromError(error) { return error }\n",
        ),
        (
            "ffmpeg-audio-command-contract",
            "def extract_audio() -> bool:\n    return True\n\ndef merge_audio() -> None:\n    pass\n",
        ),
        (
            "segmented-finalization-command-contract",
            "def finalize_segmented_output(*, output_path: str) -> None:\n    pass\n",
        ),
        (
            "shared-frame-filter-geometry-params",
            "def _crop_slices(params):\n    pass\n\ndef _padding(params):\n    pass\n",
        ),
        (
            "shared-rust-backend-error-payload",
            "fn backend_error_payload(stderr_capture: &StderrCapture) -> TaskErrorPayload { todo!() }\n",
        ),
        (
            "shared-decoded-frame-writer-session",
            "class DecodedFrameWriterConfig:\n"
            "    width: int\n"
            "    height: int\n"
            "@contextmanager\n"
            "def decoded_frame_writer_session(config):\n"
            "    thread = Thread(target=_write_decoded_frames_to_worker)\n"
            "    thread.start()\n"
            "    yield\n"
            "    thread.join()\n",
        ),
        (
            "shared-decoder-hardware-capability-probe",
            "def probe_decoder_hardware_capabilities():\n"
            "    devices = []\n"
            "    options_by_device = {}\n"
            "    return devices, options_by_device\n",
        ),
        (
            "direct-task-listener-composition",
            "runner = getTaskRunner()\ndetachHandle = await listenTaskEvents(runner)\n",
        ),
        (
            "shared-task-pause-transition",
            "async function setPaused(paused: boolean) {\n"
            "  if (batch.isPaused === paused) return\n"
            "  await deps.pauseTask()\n"
            "  await deps.resumeTask()\n"
            "}\n",
        ),
        (
            "shared-console-task-state-updater",
            "function updateConsoleTaskState(update) {\n"
            "  const item = getConsoleItem()\n"
            "  const state = getConsoleRunState()\n"
            "  setItemTaskState(item.id, update(state.taskState))\n"
            "}\n",
        ),
        (
            "stage-fps-rule-delegation",
            "def resolved_stream_fps(source_fps, stage_plan):\n"
            "    interpolation_step = stage_plan.interpolation_step\n"
            "    return stage_output_fps(interpolation_step, source_fps)\n",
        ),
        (
            "shared-paddlegan-output-conversion",
            "def _tensor_output_to_frames(tensor, expected_ndim, batch_index):\n"
            "    return [_chw_float_to_rgb_uint8(frame) for frame in tensor]\n",
        ),
        (
            "shared-workflow-summary-label",
            "const workflowLabel = computed(() =>\n  getWorkflowSummaryLabel(editorConfig.value.workflowConfig),\n)\n",
        ),
        (
            "stage-worker-current-interpreter",
            "def _spawn_stage_workers():\n    process = subprocess.Popen([sys.executable, '-m', 'app'])\n",
        ),
        (
            "direct-stage-worker-factory-composition",
            "def run_stage_worker_stream(*, event_sink: EventSink):\n"
            "    backend = create_backend(config)\n"
            "    algorithm = create_algorithm(config.stage, backend)\n",
        ),
        (
            "fixed-stage-event-stderr",
            "def emit_stage_event(event: dict[str, Any]) -> None:\n    print(event, file=sys.stderr)\n",
        ),
        (
            "settings-driven-logging",
            "def setup_logging() -> None:\n    settings = _load_settings()\n",
        ),
        (
            "environment-driven-native-dll-paths",
            "def _candidate_dirs() -> list[Path]:\n"
            "    value = os.environ.get('VP_TENSORRT_DIR')\n"
            "def register_native_dll_paths() -> None:\n"
            "    pass\n",
        ),
        (
            "shared-current-task-status-selector",
            "const currentItem = mediaStore.findItem(taskStore.batch.currentId)\n"
            "const currentStatus = runStateStore.getByItemId(currentItem?.id)?.taskState.status ?? null\n"
            "return getTaskStatusLabel(taskStore.batch, currentStatus)\n",
        ),
        (
            "app-current-task-status-selector",
            "const envStore = useEnvStore()\nconst taskStatusLabel = useCurrentTaskStatusLabel()\n",
        ),
        (
            "step-rail-current-task-status-selector",
            "const taskStore = useTaskStore()\n"
            "const taskStatusLabel = useCurrentTaskStatusLabel()\n"
            "const moduleStates = computed(() => ({ render: taskStore.batch.isRunning }))\n",
        ),
        (
            "task-orchestrator-store-item-lookup",
            "const consoleTaskItem = computed(\n"
            "  () => mediaStore.findItem(taskStore.batch.currentId) ?? mediaStore.activeItem,\n"
            ")\n",
        ),
        (
            "bootstrap-task-listener-lifecycle",
            "import { attachTaskListeners, disposeRunner } from './taskOrchestratorRuntime'\n"
            "await attachTaskListeners()\n"
            "disposeRunner()\n",
        ),
        (
            "rust-task-controller-session",
            "struct TaskControllerSession<R: Runtime> { app: AppHandle<R> }\n"
            "fn spawn_task_controller<R: Runtime + 'static>(session: TaskControllerSession<R>) {}\n",
        ),
        (
            "rust-controller-owned-runtime-policy",
            "let controller = process_control::default_controller();\n"
            "if let Some(timeout) = parse_stall_timeout() {}\n",
        ),
        (
            "rust-shared-ffmpeg-tool-resolver",
            "fn resolve_ffmpeg_tools() {\n"
            '    resolve_tool_path(None, None, None, "ffmpeg");\n'
            "}\n"
            "fn resolve_tool_path() {}\n",
        ),
        (
            "rust-ffmpeg-tool-pair-consumer",
            "let (ffmpeg_path, ffprobe_path) = ffmpeg::resolve_ffmpeg_tools(None, None);\n",
        ),
        (
            "shared-runtime-executable-candidates",
            "def _candidate_executable_paths(\n"
            "    runtime_root: Path,\n"
            "    name: str,\n"
            "    *,\n"
            "    prefer_tool_directory: bool = False,\n"
            ") -> list[Path]:\n"
            "    root_path = runtime_root / name\n"
            "    tool_paths = [runtime_root / name]\n"
            "    if prefer_tool_directory:\n"
            "        return [root_path, *tool_paths]\n",
        ),
        (
            "embedded-python-candidate-order",
            '_candidate_executable_paths(\n    runtime_root,\n    "python",\n    prefer_tool_directory=True,\n)\n',
        ),
        (
            "direct-runtime-mode-root-resolution",
            "def runtime_mode(self) -> str:\n"
            "    runtime_root = _resolve_path(self.RUNTIME_ROOT)\n"
            '    return "bundled" if runtime_root else "external"\n',
        ),
        (
            "shared-stage-file-runtime-config",
            "@dataclass(frozen=True, slots=True)\nclass StageFileRuntimeConfig:\n    pass\n",
        ),
        (
            "stage-file-runtime-config-root",
            "runtime_config = StageFileRuntimeConfig(ffmpeg=ffmpeg)\n"
            "run_single_stage_file_chunks(config=runtime_config)\n",
        ),
        (
            "stage-file-chunk-config-forwarding",
            "stage_total_frames = stage_progress_total(config.step, input_frames, output_frames)\n"
            "for chunk in chunks:\n"
            "    run_stage_chunk_to_file(\n"
            "        config=config,\n"
            "        chunk=chunk,\n"
            "        stage_total_frames=stage_total_frames,\n"
            "    )\n",
        ),
        (
            "stage-file-encoder-config-consumer",
            "def encode_stage_worker_output(*, config: StageFileRuntimeConfig, output_path: str):\n"
            "    writer = config.ffmpeg.open_rawvideo_encoder(output_path=output_path)\n"
            "    config.metrics.record_processed_frames(1)\n",
        ),
        (
            "direct-cli-logging-setup",
            "args = parser.parse_args()\nsetup_logging()\nargs.func(args)\n",
        ),
        (
            "windows-virtual-gpu-filter",
            "def _is_virtual_gpu_adapter(name, compatibility, pnp_device_id):\n"
            "    return True\n"
            "script = 'Select-Object Name,AdapterCompatibility,PNPDeviceID'\n"
            "if _is_virtual_gpu_adapter(name, compatibility, pnp_device_id):\n"
            "    continue\n",
        ),
        (
            "gpu-vendor-word-boundaries",
            "NVIDIA = re.compile(r'\\bnvidia\\b', re.IGNORECASE)\nATI = re.compile(r'\\bati\\b', re.IGNORECASE)\n",
        ),
    ],
)
def test_critical_required_catalog_rules_accept_shared_boundaries(tmp_path: Path, rule_id: str, source: str) -> None:
    rule = next(rule for rule in REQUIRED_PATTERN_RULES if rule.rule_id == rule_id)
    target = tmp_path / rule.path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")

    assert rule.check(tmp_path) == []


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


def test_rust_public_surface_rejects_public_items_outside_allowlist(tmp_path: Path) -> None:
    internal = tmp_path / "frontend/src-tauri/src/tasks/worker.rs"
    internal.parent.mkdir(parents=True)
    internal.write_text("pub fn leaked() {}\npub(crate) fn internal() {}\n", encoding="utf-8")

    assert _check_rust_public_surface(tmp_path) == [
        "Rust crate-internal source exposes a public item: frontend/src-tauri/src/tasks/worker.rs"
    ]


def test_rust_public_surface_allows_schema_and_crate_entrypoints(tmp_path: Path) -> None:
    model = tmp_path / "frontend/src-tauri/src/models/task.rs"
    model.parent.mkdir(parents=True)
    model.write_text("pub struct TaskRequest { pub input_path: String }\n", encoding="utf-8")
    lib = tmp_path / "frontend/src-tauri/src/lib.rs"
    lib.parent.mkdir(parents=True, exist_ok=True)
    lib.write_text("pub mod models;\npub fn run() {}\n", encoding="utf-8")

    assert _check_rust_public_surface(tmp_path) == []


def test_typed_ndjson_semantic_check_rejects_extra_manual_error_envelopes(tmp_path: Path) -> None:
    app_main = tmp_path / "backend/app/__main__.py"
    app_main.parent.mkdir(parents=True)
    app_main.write_text(
        'BOOTSTRAP = {"type": "error"}\nEXTRA = {"type": "error"}\n',
        encoding="utf-8",
    )

    assert _check_typed_ndjson_error_emission(tmp_path)
