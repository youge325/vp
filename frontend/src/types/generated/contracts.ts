/* Generated from contracts/boundary.schema.json. Do not edit. */

export type AlgorithmFamily = "rife" | "onnx_super_resolution" | "paddlegan_vsr";
export type TensorBackend = "pytorch" | "paddle" | "onnx";
export type InputFrameMode = "none" | "editable_chunk" | "fixed_window";
export type BackendTaskErrorCode =
  | "missing_ffmpeg"
  | "missing_model"
  | "missing_tensor_backend"
  | "missing_python_dependency"
  | "cancelled"
  | "process_failed"
  | "invalid_input"
  | "invalid_config"
  | "resume_conflict"
  | "io_error"
  | "persistence_failed";
export type CapabilityOptionKind = "boolean" | "number" | "string" | "choice";
export type CodecProfileFamily = "cpu" | "nvidia" | "intel" | "software";
export type RateControlMode = "crf" | "cq" | "qp" | "bitrate";
export type DecodeMode = "software" | "hardware";
export type GpuVendor = "nvidia" | "intel" | "amd" | "hygon" | "other";
export type InferenceEngine = "cuda" | "tensorrt" | "dcu";
export type RuntimeMode = "external" | "bundled" | "expected-bundled";
export type EnvironmentCheckSource = "cache" | "probe";
export type FilterStepKind = "scale" | "crop" | "pad" | "sharpen" | "denoise" | "color" | "anime_cleanup";
export type FpsMode = "multi" | "target";
export type ProcessOrder = "super_resolution_then_interpolation" | "frame_interpolation_then_super_resolution";
export type ResumeInspectionEventType = "resume_inspection";
export type ResumePipelineKind = "streaming" | "format_conversion";
export type ResumeMode = "auto" | "force-fresh" | "force-resume";
export type ShellTaskErrorCode =
  | "process_failed"
  | "invalid_input"
  | "io_error"
  | "spawn_failed"
  | "runtime_panic"
  | "schema_mismatch"
  | "persistence_failed"
  | "backend_no_json"
  | "controller_unavailable"
  | "backend_probe_failed";
export type TaskCancelledReason = "user" | "stalled";
export type TaskControlKind = "pause" | "resume" | "cancel";
export type TaskErrorCode =
  | "missing_ffmpeg"
  | "missing_model"
  | "missing_tensor_backend"
  | "missing_python_dependency"
  | "cancelled"
  | "process_failed"
  | "invalid_input"
  | "invalid_config"
  | "resume_conflict"
  | "io_error"
  | "spawn_failed"
  | "runtime_panic"
  | "schema_mismatch"
  | "persistence_failed"
  | "backend_no_json"
  | "controller_unavailable"
  | "backend_probe_failed";

export interface VpBoundaryContracts {
  AlgorithmFamily: AlgorithmFamily;
  AlgorithmInfo: AlgorithmInfo;
  BackendTaskErrorCode: BackendTaskErrorCode;
  BackendTaskErrorPayload: BackendTaskErrorPayload;
  CapabilityChoice: CapabilityChoice;
  CapabilityOptionKind: CapabilityOptionKind;
  CapabilityOptionSpec: CapabilityOptionSpec;
  CodecProfileFamily: CodecProfileFamily;
  CodecProfileSpec: CodecProfileSpec;
  DecodeConfig: DecodeConfig;
  DecodeMode: DecodeMode;
  EncodeConfig: EncodeConfig;
  EnvironmentCacheEntry: EnvironmentCacheEntry;
  EnvironmentCheckPayload: EnvironmentCheckPayload;
  EnvironmentCheckResult: EnvironmentCheckResult;
  EnvironmentCheckSource: EnvironmentCheckSource;
  FfmpegInfo: FfmpegInfo;
  FilterPipelineConfig: FilterPipelineConfig;
  FilterStep: FilterStep;
  FilterStepKind: FilterStepKind;
  FpsMode: FpsMode;
  GpuAdapter: GpuAdapter;
  GpuInfo: GpuInfo;
  GpuVendor: GpuVendor;
  HardwareDeviceOptionSpec: HardwareDeviceOptionSpec;
  InferenceEngine: InferenceEngine;
  InputFrameMode: InputFrameMode;
  InterpolationConfig: InterpolationConfig;
  ModelEngineMetricInfo: ModelEngineMetricInfo;
  ModelMetricInfo: ModelMetricInfo;
  ModelVariantInfo: ModelVariantInfo;
  OutputConfig: OutputConfig;
  PostprocessConfig: PostprocessConfig;
  PreprocessConfig: PreprocessConfig;
  ProcessOrder: ProcessOrder;
  RateControlConfig: RateControlConfig;
  RateControlMode: RateControlMode;
  RateControlModeSpec: RateControlModeSpec;
  ResumeInspectionEventType: ResumeInspectionEventType;
  ResumeInspectionResult: ResumeInspectionResult;
  ResumeMode: ResumeMode;
  ResumePipelineKind: ResumePipelineKind;
  ResumeStatusPayload: ResumeStatusPayload;
  RuntimeMode: RuntimeMode;
  SegmentManifest: SegmentManifest;
  ShellTaskErrorCode: ShellTaskErrorCode;
  SuperResolutionConfig: SuperResolutionConfig;
  TaskCancelledPayload: TaskCancelledPayload;
  TaskCancelledReason: TaskCancelledReason;
  TaskCompletedPayload: TaskCompletedPayload;
  TaskControlKind: TaskControlKind;
  TaskErrorCode: TaskErrorCode;
  TaskErrorPayload: TaskErrorPayload;
  TaskLogPayload: TaskLogPayload;
  TaskProgressPayload: TaskProgressPayload;
  TaskRequest: TaskRequest;
  TensorBackend: TensorBackend;
  TensorEngines: TensorEngines;
  VideoInfo: VideoInfo;
  WorkbenchPreset: WorkbenchPreset;
  WorkbenchPresetEntry: WorkbenchPresetEntry;
  WorkflowConfig: WorkflowConfig;
}
export interface AlgorithmInfo {
  name: string;
  family: AlgorithmFamily;
  tensorBackends: TensorBackend[];
  models: string[];
  onnxModels: string[];
  modelDetails: ModelVariantInfo[];
  onnxModelDetails: ModelVariantInfo[];
  scaleFactors: number[];
  fixedScaleFactor: number | null;
  defaultNumFrames: number | null;
  inputFrameMode: InputFrameMode;
}
export interface ModelVariantInfo {
  name: string;
  label: string;
  metrics: ModelMetricInfo;
}
export interface ModelMetricInfo {
  parameterCount: number | null;
  parameterBytes: number | null;
  gflopsPerMegapixel: number | null;
  activationBytesPerMegapixel: number | null;
  runtimeOverheadBytes: number | null;
  runtimeFrameCount: number | null;
  inputModulo: number | null;
  analysisStatus: string;
  analysisNotes: string[];
  engineMetrics: {
    [k: string]: ModelEngineMetricInfo;
  };
}
export interface ModelEngineMetricInfo {
  gflopsPerMegapixel: number | null;
  activationBytesPerMegapixel: number | null;
  runtimeOverheadBytes: number | null;
  runtimeFrameCount: number | null;
  inputModulo: number | null;
  analysisStatus: string;
  analysisNotes: string[];
}
export interface BackendTaskErrorPayload {
  code: BackendTaskErrorCode;
  message: string;
  details?: {
    [k: string]: unknown;
  } | null;
}
export interface CapabilityChoice {
  label: string;
  value: string | number | boolean;
}
export interface CapabilityOptionSpec {
  name: string;
  label: string;
  type: CapabilityOptionKind;
  defaultValue: string | number | boolean | null;
  choices: CapabilityChoice[];
  min: number | null;
  max: number | null;
}
export interface CodecProfileSpec {
  name: string;
  label: string;
  family: CodecProfileFamily;
  codec: string;
  available: boolean;
  hardwareDevices: string[];
  options: CapabilityOptionSpec[];
  rateControlModes?: RateControlModeSpec[] | null;
  hardwareDeviceOptions?: {
    [k: string]: HardwareDeviceOptionSpec[];
  } | null;
}
export interface RateControlModeSpec {
  mode: RateControlMode;
  label: string;
  defaultValue: string | number;
  unit: string;
}
export interface HardwareDeviceOptionSpec {
  value: string;
  label: string;
}
export interface DecodeConfig {
  mode: DecodeMode;
  hwaccel: string | null;
  hwaccelDevice: string | null;
  decoder: string | null;
  options: {
    [k: string]: string | number | boolean;
  };
}
export interface EncodeConfig {
  codec: string;
  family: string;
  container: string;
  keepAudio: boolean;
  rateControl: RateControlConfig;
  options: {
    [k: string]: string | number | boolean;
  };
}
export interface RateControlConfig {
  mode: RateControlMode;
  value: string | number;
}
export interface EnvironmentCacheEntry {
  schemaVersion: 14;
  checkedAt: string;
  fingerprint: string;
  result: EnvironmentCheckResult;
}
export interface EnvironmentCheckResult {
  ffmpeg: FfmpegInfo;
  gpu: GpuInfo;
  tensorEngines: TensorEngines;
  interpolationAlgorithms: AlgorithmInfo[];
  superResolutionAlgorithms: AlgorithmInfo[];
  runtimeMode: RuntimeMode;
}
export interface FfmpegInfo {
  available: boolean;
  hwaccels: string[];
  encoderProfiles: CodecProfileSpec[];
  decoderProfiles: CodecProfileSpec[];
}
export interface GpuInfo {
  adapters: GpuAdapter[];
}
export interface GpuAdapter {
  name: string;
  vendor: GpuVendor;
}
export interface TensorEngines {
  pytorch: InferenceEngine[];
  paddle: InferenceEngine[];
  onnx: InferenceEngine[];
}
export interface EnvironmentCheckPayload {
  result: EnvironmentCheckResult;
  source: EnvironmentCheckSource;
  checkedAt: string;
}
export interface FilterPipelineConfig {
  enabled: boolean;
  filters: FilterStep[];
}
export interface FilterStep {
  kind: FilterStepKind;
  enabled: boolean;
  params: {
    [k: string]: unknown;
  };
}
export interface InterpolationConfig {
  enabled: boolean;
  targetFps: number;
  multi: number;
  algorithm: string;
  model: string;
  onnxModel: string | null;
  scale: number;
  fp16: boolean;
  tensorBackend: TensorBackend;
  engine: string;
}
export interface OutputConfig {
  outputDir: string | null;
  openOnComplete: boolean;
  segmentFrames: number;
}
export interface PostprocessConfig {
  enabled: boolean;
  filters: FilterStep[];
}
export interface PreprocessConfig {
  enabled: boolean;
  filters: FilterStep[];
}
export interface ResumeInspectionResult {
  type: ResumeInspectionEventType;
  pipeline_kind: ResumePipelineKind;
  outputPath: string;
  input_path: string;
  finalExists: boolean;
  sidecarExists: boolean;
  signatureMatch: boolean;
  completedChunks: number;
  completedOutputFrames: number;
  nextSourceFrame: number;
  totalOutputFrames: number;
}
export interface ResumeStatusPayload {
  resumed: boolean;
  completedChunks: number;
  completedOutputFrames: number;
  startSourceFrame: number;
  totalOutputFrames: number;
}
export interface SegmentManifest {
  version: 3;
  signature: string;
  created_at: string;
  input_path: string;
  output_path: string;
  config_snapshot: {
    [k: string]: unknown;
  };
}
export interface SuperResolutionConfig {
  enabled: boolean;
  scaleFactor: number;
  algorithm: string;
  onnxModel: string | null;
  tensorBackend: TensorBackend;
  engine: string;
  numFrames: number;
}
export interface TaskCancelledPayload {
  reason: TaskCancelledReason;
  details: {
    [k: string]: unknown;
  } | null;
}
export interface TaskCompletedPayload {
  outputPath: string;
  processedFrames: number;
  timeSeconds: number;
}
export interface TaskErrorPayload {
  code: TaskErrorCode;
  message: string;
  details: {
    [k: string]: unknown;
  } | null;
}
export interface TaskLogPayload {
  message: string;
}
export interface TaskProgressPayload {
  current: number;
  total: number;
  percent: number;
  stage: string;
  stageIndex: number;
  stageTotal: number;
  metrics?: {
    [k: string]: unknown;
  } | null;
}
export interface TaskRequest {
  inputPath: string;
  decodeConfig: DecodeConfig;
  workflowConfig: WorkflowConfig;
  encodeConfig: EncodeConfig;
  outputConfig: OutputConfig;
  resumeMode?: ResumeMode | null;
}
export interface WorkflowConfig {
  fpsMode: FpsMode;
  processOrder: ProcessOrder;
  interpolation: InterpolationConfig;
  superResolution: SuperResolutionConfig;
  preprocess: PreprocessConfig;
  postprocess: PostprocessConfig;
}
export interface VideoInfo {
  fps: number;
  width: number;
  height: number;
  videoCodec: string;
}
export interface WorkbenchPreset {
  decodeConfig: DecodeConfig;
  workflowConfig: WorkflowConfig;
  encodeConfig: EncodeConfig;
  outputConfig: OutputConfig;
}
export interface WorkbenchPresetEntry {
  schemaVersion: 2;
  preset: WorkbenchPreset;
}
