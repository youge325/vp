// 领域层 — 业务联合类型与枚举,不依赖 vue / pinia / tauri。

export type ProcessOrder =
  | 'super_resolution_then_interpolation'
  | 'frame_interpolation_then_super_resolution'

export type FpsMode = 'multi' | 'target'
export type TensorBackend = 'pytorch' | 'paddle' | 'onnx'
export type TaskStatus = 'idle' | 'running' | 'paused' | 'cancelling' | 'completed' | 'error' | 'cancelled'
export type CodecFamily = 'cpu' | 'nvidia' | 'intel' | 'software'
export type GpuVendor = 'nvidia' | 'intel' | 'amd' | 'hygon' | 'other'
export type GpuDeviceType = 'integrated' | 'discrete' | 'virtual' | 'other'
export type InferenceEngine = 'cuda' | 'tensorrt' | 'dcu'
export type RateControlMode = 'crf' | 'cq' | 'qp' | 'bitrate'
export type EnvironmentCheckSource = 'cache' | 'probe'
