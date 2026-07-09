export interface VideoDimensions {
  width: number
  height: number
}

export interface RuntimeMetricEstimate {
  effectiveWidth: number
  effectiveHeight: number
  megapixels: number
  gflops: number | null
  vramBytes: number | null
}

export interface MetricRow {
  label: string
  value: string
}
