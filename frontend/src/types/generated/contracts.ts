/* Generated from contracts/boundary.schema.json. Do not edit. */

export type AlgorithmFamily = "rife" | "onnx_super_resolution" | "paddlegan_vsr" | "pytorch_vsr";
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
export type FilterStep =
  | ScaleFilterStep
  | CropFilterStep
  | PadFilterStep
  | SharpenFilterStep
  | DenoiseFilterStep
  | ColorFilterStep
  | AnimeCleanupFilterStep;
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
  | "backend_probe_failed"
  | "process_control_unsupported";
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
  | "backend_probe_failed"
  | "process_control_unsupported";

export interface VpBoundaryContracts {
  AlgorithmFamily: AlgorithmFamily;
  AlgorithmInfo: AlgorithmInfo;
  AnimeCleanupFilterParams: AnimeCleanupFilterParams;
  AnimeCleanupFilterStep: AnimeCleanupFilterStep;
  BackendTaskErrorCode: BackendTaskErrorCode;
  BackendTaskErrorPayload: BackendTaskErrorPayload;
  CapabilityChoice: CapabilityChoice;
  CapabilityOptionKind: CapabilityOptionKind;
  CapabilityOptionSpec: CapabilityOptionSpec;
  CodecProfileFamily: CodecProfileFamily;
  CodecProfileSpec: CodecProfileSpec;
  ColorFilterParams: ColorFilterParams;
  ColorFilterStep: ColorFilterStep;
  CropFilterParams: CropFilterParams;
  CropFilterStep: CropFilterStep;
  DecodeConfig: DecodeConfig;
  DecodeMode: DecodeMode;
  DenoiseFilterParams: DenoiseFilterParams;
  DenoiseFilterStep: DenoiseFilterStep;
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
  ModelLicenseInfo: ModelLicenseInfo;
  ModelMetricInfo: ModelMetricInfo;
  ModelVariantInfo: ModelVariantInfo;
  OutputConfig: OutputConfig;
  PadFilterParams: PadFilterParams;
  PadFilterStep: PadFilterStep;
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
  ScaleFilterParams: ScaleFilterParams;
  ScaleFilterStep: ScaleFilterStep;
  SegmentManifest: SegmentManifest;
  SharpenFilterParams: SharpenFilterParams;
  SharpenFilterStep: SharpenFilterStep;
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
  modelLicense: ModelLicenseInfo | null;
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
export interface ModelLicenseInfo {
  spdxId: string;
  usage: "non_commercial";
  sourceUrl: string;
}
export interface AnimeCleanupFilterParams {
  profile?: "clean-lines" | "thin-outline" | "balanced-cel";
  denoise?: number;
  edgeBoost?: number;
}
export interface AnimeCleanupFilterStep {
  kind: "anime_cleanup";
  enabled: boolean;
  params: AnimeCleanupFilterParams;
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
export interface ColorFilterParams {
  brightness?: number;
  contrast?: number;
  saturation?: number;
}
export interface ColorFilterStep {
  kind: "color";
  enabled: boolean;
  params: ColorFilterParams;
}
export interface CropFilterParams {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
}
export interface CropFilterStep {
  kind: "crop";
  enabled: boolean;
  params: CropFilterParams;
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
export interface DenoiseFilterParams {
  strength?: number;
  colorStrength?: number;
}
export interface DenoiseFilterStep {
  kind: "denoise";
  enabled: boolean;
  params: DenoiseFilterParams;
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
  schemaVersion: 15;
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
export interface ScaleFilterStep {
  kind: "scale";
  enabled: boolean;
  params: ScaleFilterParams;
}
export interface ScaleFilterParams {
  mode?: "factor" | "resolution";
  factor?: number;
  width?: number;
  height?: number;
  interpolation?: "lanczos4" | "cubic" | "area" | "linear";
}
export interface PadFilterStep {
  kind: "pad";
  enabled: boolean;
  params: PadFilterParams;
}
export interface PadFilterParams {
  top?: number;
  bottom?: number;
  left?: number;
  right?: number;
  color?: string;
}
export interface SharpenFilterStep {
  kind: "sharpen";
  enabled: boolean;
  params: SharpenFilterParams;
}
export interface SharpenFilterParams {
  amount?: number;
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
  engine: InferenceEngine;
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
  engine: InferenceEngine;
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
