// pure: no Vue / no Pinia / no Tauri
// 数字格式化工具。

export function formatNumber(value: number): string {
  if (Math.abs(value - Math.round(value)) < 0.01) {
    return `${Math.round(value)}`
  }
  return value.toFixed(2).replace(/\.?0+$/, '')
}
