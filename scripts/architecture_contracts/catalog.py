"""Declarative architecture rules for the current repository shape."""

from __future__ import annotations

from .rules import AbsentPathRule, ForbiddenPatternRule, ForbiddenReferenceRule, RequiredPatternRule


def _absent(rule_id: str, path: str, message: str = "obsolete path remains") -> AbsentPathRule:
    return AbsentPathRule(rule_id, path, message)


def _forbid(rule_id: str, path: str, pattern: str, message: str) -> ForbiddenPatternRule:
    return ForbiddenPatternRule(rule_id, path, pattern, message)


ABSENT_PATH_RULES = (
    _absent("frontend-ipc-barrel", "frontend/src/lib/ipc/index.ts"),
    _absent("frontend-model-metrics-barrel", "frontend/src/services/model-metrics.ts"),
    _absent("frontend-preset-select-option-type", "frontend/src/services/preset/select-options.ts"),
    _absent("frontend-enhance-rules-barrel", "frontend/src/services/preset/enhance-rules.ts"),
    _absent("frontend-enhance-field-aggregator", "frontend/src/composables/forms/enhance-field-bindings.ts"),
    _absent("frontend-enhance-field-aggregator-test", "frontend/src/composables/forms/enhance-field-bindings.spec.ts"),
    _absent("frontend-encode-output-aggregator", "frontend/src/composables/forms/encode-output-bindings.ts"),
    _absent("frontend-enhance-option-aggregator", "frontend/src/composables/forms/enhance-option-bindings.ts"),
    _absent(
        "frontend-enhance-option-aggregator-test",
        "frontend/src/composables/forms/enhance-option-bindings.spec.ts",
    ),
    _absent("backend-tensor-chain", "backend/app/processing/streaming/_tensor_chain.py"),
    _absent("backend-tensor-chain-test", "backend/tests/test_processing/test_tensor_chain.py"),
    _absent("backend-raw-runtime", "backend/app/processing/streaming/pipeline_raw_runtime.py"),
    _absent("backend-raw-state", "backend/app/processing/streaming/pipeline_raw_state.py"),
    _absent("backend-raw-stage", "backend/app/processing/streaming/pipeline_raw_stage.py"),
    _absent("backend-raw-completion", "backend/app/processing/streaming/pipeline_raw_completion.py"),
    _absent("backend-worker-pipeline-queue", "backend/app/processing/streaming/worker_pipeline_queue.py"),
    _absent("backend-raw-runtime-test", "backend/tests/test_processing/test_pipeline_raw_runtime.py"),
    _absent("backend-raw-state-test", "backend/tests/test_processing/test_pipeline_raw_state.py"),
    _absent("backend-raw-stage-test", "backend/tests/test_processing/test_pipeline_raw_stage.py"),
    _absent("backend-raw-completion-test", "backend/tests/test_processing/test_pipeline_raw_completion.py"),
    _absent("backend-worker-pipeline-queue-test", "backend/tests/test_processing/test_worker_pipeline_queue.py"),
    _absent(
        "backend-stage-file-chunk-progress",
        "backend/app/processing/streaming/stage_file_chunk_progress.py",
    ),
    _absent(
        "backend-stage-file-chunk-progress-test",
        "backend/tests/test_processing/test_stage_file_chunk_progress.py",
    ),
    _absent("backend-streaming-decoder", "backend/app/processing/streaming/decoder.py"),
    _absent("backend-streaming-encoder", "backend/app/processing/streaming/encoder.py"),
    _absent("backend-streaming-processor", "backend/app/processing/streaming/processor.py"),
    _absent("backend-processor-algorithms", "backend/app/processing/streaming/processor_algorithms.py"),
    _absent("backend-processor-stage-execution", "backend/app/processing/streaming/processor_stage_execution.py"),
    _absent("backend-processor-streams", "backend/app/processing/streaming/processor_streams.py"),
    _absent("backend-processor-stream-io", "backend/app/processing/streaming/processor_stream_io.py"),
    _absent("backend-processor-stream-single", "backend/app/processing/streaming/processor_stream_single.py"),
    _absent(
        "backend-processor-stream-interpolated", "backend/app/processing/streaming/processor_stream_interpolated.py"
    ),
    _absent("backend-processor-stream-sequence", "backend/app/processing/streaming/processor_stream_sequence.py"),
    _absent(
        "paddlegan-vendor-logger",
        "backend/app/algorithms/paddle/paddlegan_vsr/vendor/ppgan/utils/logger.py",
    ),
)


FORBIDDEN_PATTERN_RULES = (
    _forbid(
        "ipc-error-export",
        "frontend/src/lib/ipc/client.ts",
        r"^\s*export(?:\s+class\s+InvokeError\b|\s*\{[^}\n]*\bInvokeError\b)",
        "test-only IPC error export",
    ),
    _forbid(
        "compile-contract-export",
        "frontend/src/types/protocol/_contract_check.ts",
        r"^\s*export\s+const\s+_[A-Z0-9_]+_CONTRACT\b",
        "compile-only contract export",
    ),
    _forbid(
        "ipc-contract-internal-exports",
        "frontend/src/lib/ipc/contract.ts",
        r"export\s+(?:interface\s+(?:IpcCommandArgs|IpcCommandResult)|type\s+TaskControlKind)|(?:export\s+)?const\s+IPC_COMMAND_NAMES\b",
        "internal IPC contract surface exported",
    ),
    _forbid(
        "paddlegan-disabled-registry",
        "backend/app/algorithms/paddle/paddlegan_vsr/weights.py",
        r"\bDISABLED_PADDLEGAN_VSR_MODELS\b|^\s*def\s+(?:resolve_auxiliary_weight_path|ensure_auxiliary_weight_file)\b",
        "dead PaddleGAN weight surface",
    ),
    _forbid(
        "workflow-validation-dead-surface",
        "backend/app/planning/workflow_validation.py",
        r"\bDISABLED_PADDLEGAN_VSR_MODELS\b|^\s*def\s+(?:get_onnx_model_name|validate_onnx_models_for_workflow)\b",
        "dead workflow validation surface",
    ),
    _forbid(
        "global-algorithm-bootstrap",
        "backend/app/algorithms/factory.py",
        r"\bregister_default_algorithms\b|^\s*def\s+get_available_types\b",
        "dead algorithm factory surface",
    ),
    _forbid(
        "processing-bootstrap",
        "backend/app/processing/__init__.py",
        r"\bregister_default_algorithms\b",
        "global processing bootstrap",
    ),
    _forbid(
        "cli-package-facade",
        "backend/app/cli/__init__.py",
        r"from\s+app\.cli\.(?:commands|parser)\b|\bPROCESS_(?:LABEL|ORDER)_MAP\b",
        "unused CLI package facade",
    ),
    _forbid(
        "planning-package-facade",
        "backend/app/planning/__init__.py",
        r"\b(?:AlgorithmType|PROCESS_LABEL_MAP|ResumeDecision|estimate_encoded_output_frames|ResumeKind|get_onnx_model_name|processing_needs_interpolation|validate_onnx_models_for_workflow)\b",
        "unused planning package facade",
    ),
    _forbid(
        "ffmpeg-dead-delegates",
        "backend/app/utils/ffmpeg/__init__.py",
        r"^\s*def\s+(?:build_rawvideo_decode_command|build_rawvideo_encode_command|convert_format|build_encode_video_args)\b|__all__\s*=\s*\[[^\]]*\b(?:RawVideoReader|RawVideoWriter|build_rawvideo_|open_rawvideo_)",
        "unused FFmpeg facade",
    ),
    _forbid(
        "ffmpeg-dead-converter",
        "backend/app/utils/ffmpeg/encode.py",
        r"^\s*def\s+convert_format\b",
        "dead FFmpeg format converter",
    ),
    _forbid(
        "algorithm-base-test-api",
        "backend/app/algorithms/base.py",
        r"^\s*def\s+(?:process_frame_batch|validate|get_description)\b",
        "test-only algorithm API",
    ),
    *(
        _forbid(
            f"algorithm-implementation-test-api-{index}",
            path,
            r"^\s*def\s+(?:process_frame_batch|validate|get_description)\b",
            "test-only concrete algorithm API",
        )
        for index, path in enumerate(
            (
                "backend/app/processing/anime_optimization.py",
                "backend/app/processing/frame_filters.py",
                "backend/app/processing/interpolation.py",
                "backend/app/processing/super_resolution.py",
            )
        )
    ),
    *(
        _forbid(
            f"rife-solver-dead-api-{index}",
            path,
            r"^\s*def\s+(?:interpolate_multi|clear_cache)\b",
            "unused RIFE solver API",
        )
        for index, path in enumerate(
            (
                "backend/app/algorithms/pytorch/rife/solver.py",
                "backend/app/algorithms/pytorch/rife/onnx_solver.py",
            )
        )
    ),
    _forbid(
        "rife-legacy-config",
        "backend/app/algorithms/pytorch/rife/_model_spec.py",
        r"\bMODEL_CONFIGS\b|^\s*def\s+_to_legacy_dict\b|__all__\s*=\s*\[[^\]]*[\"']replace[\"']",
        "legacy RIFE model config surface",
    ),
    _forbid(
        "rife-write-only-state",
        "backend/app/algorithms/pytorch/rife/solver.py",
        r"self\._(?:model_version|scale|fp16|config|encode_channel|padding|orig_h|orig_w|encode_cache)\b|^\s*def\s+(?:device|dtype|modulo|has_head)\b",
        "RIFE write-only state or zero-call property",
    ),
    _forbid(
        "onnx-rife-write-only-state",
        "backend/app/algorithms/pytorch/rife/onnx_solver.py",
        r"self\._model_version\b|\bMODEL_CONFIGS\b",
        "ONNX RIFE dead state",
    ),
    _forbid(
        "anime-write-only-state",
        "backend/app/processing/anime_optimization.py",
        r"self\._(?:tensor_backend|duplicate_threshold)\b",
        "anime write-only state",
    ),
    _forbid(
        "metrics-dead-timing-api",
        "backend/app/processing/streaming/metrics.py",
        r"^\s*def\s+(?:timed|record_stage_duration)\b|\bstage_durations\b",
        "unused pipeline metrics timing API",
    ),
    _forbid(
        "stage-worker-helper-definitions",
        "backend/app/processing/streaming/stage_worker.py",
        r"^\s*(?:class\s+RawVideoFrameError\b|def\s+(?:read_rgb_frame|write_rgb_frame|emit_stage_event|_create_backend|_create_algorithm|_run_sequence_stage|_run_interpolation_stage|_run_single_frame_stage)\b)",
        "stage worker helper implementation",
    ),
    _forbid(
        "worker-process-helper-definitions",
        "backend/app/processing/streaming/worker_processes.py",
        r"^\s*def\s+(?:parse_stage_event_line|read_worker_stderr|write_decoded_frames_to_worker|drain_final_worker_output|close_pipe)\b",
        "worker process event or IO implementation",
    ),
    _forbid(
        "pipeline-runtime-coupling",
        "backend/app/processing/streaming/pipeline.py",
        r"from\s+app\.processing\.streaming\.(?:pipeline_raw|stage_file_pipeline|worker_pipeline)\s+import|\b(?:queue\.Queue|threading\.Thread|threading\.Event|run_stage_worker_pipeline)\b",
        "streaming entrypoint runtime coupling",
    ),
    _forbid(
        "raw-private-worker-coupling",
        "backend/app/processing/streaming/pipeline_raw.py",
        r"from\s+app\.processing\.streaming\.(?:encoder|encoder_worker)\s+import|\bstage_worker_runner\b|\bsignature\b",
        "raw pipeline private runtime coupling",
    ),
    _forbid(
        "worker-pipeline-process-io",
        "backend/app/processing/streaming/worker_pipeline.py",
        r"from\s+app\.processing\.streaming\.(?:worker_processes|worker_process_events|worker_process_io)\s+import",
        "worker pipeline process IO coupling",
    ),
    _forbid(
        "frontend-decode-form-business-rules",
        "frontend/src/composables/forms/useDecodeForm.ts",
        r"@/services/preset/",
        "decode composable business rule",
    ),
    _forbid(
        "frontend-encode-form-business-rules",
        "frontend/src/composables/forms/useEncodeForm.ts",
        r"@/services/preset/",
        "encode composable business rule",
    ),
    _forbid(
        "frontend-enhance-form-business-rules",
        "frontend/src/composables/forms/useEnhanceForm.ts",
        r"@/services/preset/|createAlgorithmLens|buildEnhanceViewModel|createDraftEditor",
        "enhance composable business rule",
    ),
    _forbid(
        "frontend-enhance-form-direct-rules",
        "frontend/src/composables/forms/enhance-form-bindings.ts",
        r"@/services/preset/(?:enhance-workflow|enhance-view-model)|createDraftEditor|createEnhanceFieldBindings",
        "enhance form direct business rule",
    ),
    _forbid(
        "frontend-io-view-rules-decode",
        "frontend/src/views/DecodeModuleView.vue",
        r"@/services/preset/(?:io-options|io-form-rules|profile-selection)|\bas\s+RateControlMode\b|\bNumber\s*\(",
        "decode view option conversion rule",
    ),
    _forbid(
        "frontend-io-view-rules-encode",
        "frontend/src/views/EncodeModuleView.vue",
        r"@/services/preset/(?:io-options|io-form-rules|profile-selection)|\bas\s+RateControlMode\b|\bNumber\s*\(",
        "encode view option conversion rule",
    ),
    _forbid(
        "frontend-enhance-view-rules",
        "frontend/src/views/EnhanceModuleView.vue",
        r"@/services/preset/enhance-options|useGpuCapabilities|\bas\s+(?:TensorBackend|InferenceEngine|ProcessOrder)\b|\bNumber\s*\(",
        "enhance view option conversion rule",
    ),
    _forbid(
        "frontend-default-workflow-hydration",
        "frontend/src/services/preset/defaults.ts",
        r"enhance-rules|pickDefault|tensorEngines|gpu\?\.adapters|\bvendor\b",
        "workflow environment hydration outside owner",
    ),
    _forbid(
        "ndjson-emitter-singleton",
        "backend/app/protocol/__init__.py",
        r"\bclass\s+NdjsonEmitter\b|\b_instance\b|^\s*def\s+__new__\b",
        "public or singleton NDJSON emitter",
    ),
    _forbid(
        "base-select-local-option-type",
        "frontend/src/components/forms/BaseSelect.vue",
        r"^\s*(?:export\s+)?interface\s+SelectOption\b",
        "local SelectOption type",
    ),
    *(
        _forbid(
            f"preset-local-option-type-{index}",
            path,
            r"^\s*(?:export\s+)?interface\s+SelectOption\b",
            "preset-local SelectOption type",
        )
        for index, path in enumerate(
            (
                "frontend/src/services/preset/enhance-options.ts",
                "frontend/src/services/preset/io-options.ts",
                "frontend/src/services/preset/rate-control.ts",
            )
        )
    ),
    _forbid(
        "batch-lifecycle-type-reexport",
        "frontend/src/services/task/batch/lifecycle/index.ts",
        r"\bexport\s+type\s*\{[^}]*\bBatchLifecycle(?:Deps)?\b",
        "batch lifecycle facade type re-export",
    ),
    _forbid(
        "batch-runner-duplicate-deps",
        "frontend/src/services/task/batch-runner.ts",
        r"^\s*interface\s+BatchRunnerDeps\b",
        "duplicate BatchRunnerDeps",
    ),
    _forbid(
        "batch-queue-unused-helpers",
        "frontend/src/services/task/batch/lifecycle/queue.ts",
        r"\b_helpers\s*:\s*CommonHelpers\b",
        "unused batch queue helpers dependency",
    ),
    _forbid(
        "stage-worker-config-implementation",
        "backend/app/processing/streaming/stage_worker.py",
        r"^\s*class\s+StageWorkerConfig\b|^\s+def\s+(?:from_mapping|from_json_file|to_jsonable)\b|\bnormalize_processing_step\b|\bjson\.load\b",
        "stage worker config implementation",
    ),
    _forbid(
        "pipeline-owned-lifecycle",
        "backend/app/processing/streaming/pipeline.py",
        r"\bResumeConflictError\b|\.prepare\s*\(|\bdecision\.kind\b|\.cleanup\s*\(|\bget_frame_count\s*\(|\bresume_status\b",
        "streaming lifecycle implementation",
    ),
    _forbid(
        "pipeline-owned-preflight",
        "backend/app/processing/streaming/pipeline.py",
        r"\b(?:normalize_processing_steps|resolve_video_info|build_stage_plan|build_signature|build_config_snapshot|should_use_stage_file_pipeline|stage_file_resume_source_frames|resolved_output_dimensions)\b|from\s+app\.processing\.streaming\.pipeline_rules\s+import",
        "streaming preflight implementation",
    ),
    _forbid(
        "pipeline-dispatch-worker-coupling",
        "backend/app/processing/streaming/pipeline_dispatch.py",
        r"from\s+app\.processing\.streaming\.worker_pipeline\s+import|\bstage_worker_runner\b|\brun_stage_worker_pipeline\b",
        "pipeline dispatch worker coupling",
    ),
    _forbid(
        "encoder-finalization-signature",
        "backend/app/processing/streaming/encoder_finalization.py",
        r"\bsignature\b",
        "encoder finalization signature forwarding",
    ),
    _forbid(
        "pipeline-lifecycle-finalization-signature",
        "backend/app/processing/streaming/pipeline_lifecycle.py",
        r"def\s+finalize_streaming_output\s*\([\s\S]*?\bsignature\s*:|finalize_segmented_output\s*\([\s\S]*?\bsignature\s*=",
        "pipeline lifecycle finalization signature forwarding",
    ),
    _forbid(
        "stage-file-finalization-signature",
        "backend/app/processing/streaming/stage_file_pipeline.py",
        r"finalize_segmented_output\s*\([\s\S]*?\bsignature\s*=",
        "stage-file finalization signature forwarding",
    ),
    _forbid(
        "pipeline-output-dimensions-backend",
        "backend/app/processing/streaming/pipeline_rules.py",
        r"def\s+resolved_output_dimensions\s*\([\s\S]*?\btensor_backend_name\b|\bdel\s+tensor_backend_name\b",
        "output dimensions backend parameter",
    ),
    _forbid(
        "worker-pipeline-plan-implementation",
        "backend/app/processing/streaming/worker_pipeline.py",
        r"^\s*(?:class\s+(?:StageWorkerPlan|StageChunkPlan)\b|def\s+(?:build_stage_worker_plans|build_stage_chunk_plans|boundary_schedule_for_stage_plan)\b)|from\s+app\.processing\.streaming\.worker_plans\s+import\s*\([\s\S]*\b(?:StageChunkPlan|StageWorkerPlan|boundary_schedule_for_stage_plan|build_stage_chunk_plans)\b|__all__\s*=\s*\[[\s\S]*[\"'](?:StageChunkPlan|StageWorkerPlan|boundary_schedule_for_stage_plan|build_stage_chunk_plans)[\"']",
        "worker plan implementation",
    ),
    _forbid(
        "stage-file-pipeline-chunk-implementation",
        "backend/app/processing/streaming/stage_file_pipeline.py",
        r"^\s*def\s+(?:_?run_single_stage_file_chunks|_?run_stage_chunk_to_file|_?stage_signature|_?safe_stage_name)\b|from\s+app\.processing\.streaming\.stage_file_rules\s+import|\bSegmentManifest\s*\(|\bstage_signature\s*\(|\bsafe_stage_name\s*\(",
        "stage-file chunk implementation",
    ),
    _forbid(
        "encoder-worker-segment-implementation",
        "backend/app/processing/streaming/encoder_worker.py",
        r"^\s*from\s+pathlib\s+import\s+Path\b|^\s*import\s+os\b|\bopen_rawvideo_encoder\b|\bwriter\.(?:write_frame|close)\s*\(|\bfinalize_chunk\s*\(|\bchunk_tmp_path\s*\(|\b(?:_?make_segment_progress_callback|_?resolve_segment_output_frame_count)\b|\bunlink\s*\(|\b(?:current_segment_input_frames|segment_index|tmp_path)\b",
        "encoder worker segment writer implementation",
    ),
    _forbid(
        "stage-file-chunks-runtime",
        "backend/app/processing/streaming/stage_file_chunks.py",
        r"^\s*def\s+run_stage_chunk_to_file\b|^\s*import\s+(?:queue|tempfile|threading)\b|\b(?:StageWorkerConfig|read_rgb_frame|spawn_stage_workers|write_decoded_frames_to_worker)\b|^from\s+app\.processing\.streaming\.stage_file_chunk_runtime\s+import\s+run_stage_chunk_to_file\s*$|\b_run_stage_chunk_to_file\s*\(|__all__\s*=\s*\[[\s\S]*[\"']run_stage_chunk_to_file[\"']",
        "stage-file chunk runtime implementation",
    ),
    _forbid(
        "stage-file-chunk-input-fps",
        "backend/app/processing/streaming/stage_file_chunks.py",
        r"def\s+run_single_stage_file_chunks\s*\([\s\S]*?\binput_fps\b|\bdel\s+input_fps\b",
        "stage-file chunk input_fps parameter",
    ),
    _forbid(
        "stage-file-input-fps-forwarding",
        "backend/app/processing/streaming/stage_file_pipeline.py",
        r"run_single_stage_file_chunks\s*\([\s\S]*?\binput_fps\s*=",
        "stage-file chunk input_fps forwarding",
    ),
    _forbid(
        "manifest-sidecar-reset-duplicate",
        "backend/app/planning/manifest.py",
        r"^\s*def\s+_reset_sidecar\b|\bself\._reset_sidecar\s*\(",
        "duplicate manifest sidecar reset lifecycle",
    ),
    _forbid(
        "stage-file-chunk-encoding-leak",
        "backend/app/processing/streaming/stage_file_chunk_runtime.py",
        r"\bread_rgb_frame\b|\bresolve_segment_output_frame_count\b|\bopen_rawvideo_encoder\b|\bwrite_frame\s*\(|\bwritten_frames\b|Stage chunk output frame count mismatch|\blambda\s+\*_[A-Za-z0-9_]*\s*,\s*\*\*_[A-Za-z0-9_]*\s*:\s*None\b",
        "stage-file chunk encoding implementation",
    ),
    _forbid(
        "obsolete-decode-queue-symbols",
        "backend/app/processing/streaming/queues.py",
        r"\bclass\s+DecodedFrame\b|\bDecodedFrame\b|\b_DECODE_END\b",
        "obsolete decode queue symbol",
    ),
    _forbid(
        "encoder-worker-decode-queue",
        "backend/app/processing/streaming/encoder_worker.py",
        r"\bdecode_queue\b",
        "obsolete encoder decode queue",
    ),
    _forbid(
        "raw-encoder-decode-queue",
        "backend/app/processing/streaming/pipeline_raw_encoder.py",
        r"\bdecode_queue\b",
        "obsolete raw encoder decode queue",
    ),
    *(
        _forbid(
            f"form-binding-param-export-{index}",
            path,
            r"^\s*export\s+(?:interface|type)\s+\w+BindingParams\b",
            "form binding parameter type export",
        )
        for index, path in enumerate(
            (
                "frontend/src/composables/forms/decode-form-bindings.ts",
                "frontend/src/composables/forms/decode-profile-bindings.ts",
                "frontend/src/composables/forms/decode-hardware-bindings.ts",
                "frontend/src/composables/forms/encode-form-bindings.ts",
                "frontend/src/composables/forms/encode-profile-bindings.ts",
                "frontend/src/composables/forms/encode-rate-control-bindings.ts",
                "frontend/src/composables/forms/encode-output-state.ts",
                "frontend/src/composables/forms/encode-output-setters.ts",
                "frontend/src/composables/forms/enhance-form-bindings.ts",
                "frontend/src/composables/forms/enhance-algorithm-bindings.ts",
                "frontend/src/composables/forms/enhance-view-bindings.ts",
                "frontend/src/composables/forms/enhance-effect-bindings.ts",
                "frontend/src/composables/forms/enhance-scalar-field-bindings.ts",
            )
        )
    ),
)


REQUIRED_PATTERN_RULES = (
    RequiredPatternRule(
        "ipc-command-keyof",
        "frontend/src/lib/ipc/contract.ts",
        r"\bexport\s+type\s+IpcCommand\s*=\s*keyof\s+IpcCommandArgs\b",
        "IPC command keyof source is missing",
    ),
    RequiredPatternRule(
        "pydantic-model-camel-alias",
        "backend/app/models/__init__.py",
        r"from\s+pydantic\.alias_generators\s+import\s+to_camel",
        "Pydantic camel alias must use library helper",
    ),
    RequiredPatternRule(
        "pydantic-payload-camel-alias",
        "backend/app/protocol/payloads.py",
        r"from\s+pydantic\.alias_generators\s+import\s+to_camel",
        "payload camel alias must use library helper",
    ),
    RequiredPatternRule(
        "typed-ndjson-errors",
        "backend/app/__main__.py",
        r"from\s+app\.protocol\s+import\s+ndjson[\s\S]*ndjson\.error\s*\([\s\S]*ndjson\.error\s*\(",
        "normal CLI failures must use typed NDJSON errors",
    ),
    RequiredPatternRule(
        "private-ndjson-emitter",
        "backend/app/protocol/__init__.py",
        r"\bclass\s+_NdjsonEmitter\b",
        "private NDJSON emitter is missing",
    ),
)


REFERENCE_RULES = (
    ForbiddenReferenceRule(
        "legacy-task-commands",
        roots=("README.md", "docs"),
        patterns=(r"\bpause_task\b", r"\bresume_task\b"),
        message="legacy task command reference",
        suffixes=(".md",),
    ),
    ForbiddenReferenceRule(
        "obsolete-streaming-imports",
        roots=("backend/app", "backend/tests"),
        patterns=(
            r"app\.processing\.streaming\.(?:decoder|processor(?:\b|_)|pipeline_raw_(?:runtime|state|stage|completion)|worker_pipeline_queue|stage_file_chunk_progress)\b",
            r"app\.processing\.streaming\._tensor_chain\b",
        ),
        message="obsolete streaming module reference",
        suffixes=(".py",),
        excludes=("backend/tests/test_architecture_contracts.py",),
    ),
    ForbiddenReferenceRule(
        "obsolete-frontend-binding-imports",
        roots=("frontend/src",),
        patterns=(
            r"enhance-field-bindings",
            r"encode-output-bindings",
            r"enhance-option-bindings",
            r"@/lib/ipc(?:['\"]|/index)",
        ),
        message="obsolete frontend facade reference",
        suffixes=(".ts", ".tsx", ".vue"),
    ),
    ForbiddenReferenceRule(
        "planning-test-private-aliases",
        roots=("backend/tests",),
        patterns=(
            r"from\s+app\.planning\s+import[\s\S]*?\bas\s+_resolve_(?:expected_output_frames|processing_steps)\b",
        ),
        message="planning test private alias",
        suffixes=(".py",),
        excludes=("backend/tests/test_architecture_contracts.py",),
    ),
    ForbiddenReferenceRule(
        "pipeline-test-private-aliases",
        roots=("backend/tests/test_processing",),
        patterns=(
            r"from\s+app\.processing\.streaming\.pipeline\s+import\s+[^\n]*\b_[A-Za-z0-9_]+\b",
            r"from\s+app\.processing\.streaming\.pipeline\s+import\s*\([\s\S]*?\b_[A-Za-z0-9_]+\b[\s\S]*?\)",
        ),
        message="pipeline test private alias",
        suffixes=(".py",),
    ),
    ForbiddenReferenceRule(
        "obsolete-model-metrics-imports",
        roots=("frontend/src",),
        patterns=(r"from\s+['\"](?:@/services|\.{1,2})/model-metrics['\"]",),
        message="obsolete model metrics barrel import",
        suffixes=(".ts", ".tsx", ".vue"),
    ),
    ForbiddenReferenceRule(
        "obsolete-decode-queue-references",
        roots=("backend/app", "backend/tests", "docs", "README.md"),
        patterns=(
            r"\bdecoder_worker\b",
            r"\bprocessor_worker\b",
            r"\bDecodedFrame\b",
            r"\b_DECODE_END\b",
            r"\bdecode_queue\b",
        ),
        message="obsolete decode queue reference",
        suffixes=(".py", ".md", ".rst", ".txt"),
        excludes=(
            "backend/tests/test_architecture_contracts.py",
            "backend/tests/test_architecture_contract_rule_engine.py",
        ),
    ),
)


RULES = (*ABSENT_PATH_RULES, *FORBIDDEN_PATTERN_RULES, *REQUIRED_PATTERN_RULES, *REFERENCE_RULES)
