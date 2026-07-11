import type { HardwareDeviceOptionSpec } from '@/types/protocol'

type DecoderHardwareProfile = {
  hardwareDevices?: readonly string[]
  hardwareDeviceOptions?: Readonly<Record<string, readonly HardwareDeviceOptionSpec[] | undefined>>
} | null

export function resolveDecoderHwaccel(
  profile: DecoderHardwareProfile,
  preferred = '',
): string {
  const devices = profile?.hardwareDevices ?? []
  if (preferred && devices.includes(preferred)) {
    return preferred
  }
  return devices[0] ?? ''
}

export function getDecoderHwaccelDeviceOptions(
  profile: DecoderHardwareProfile,
  hwaccel: string,
): HardwareDeviceOptionSpec[] {
  if (!hwaccel) {
    return []
  }
  return [...(profile?.hardwareDeviceOptions?.[hwaccel] ?? [])]
}

export function resolveDecoderHwaccelDevice(
  profile: DecoderHardwareProfile,
  hwaccel: string,
  preferred = '',
): string {
  const options = getDecoderHwaccelDeviceOptions(profile, hwaccel)
  if (preferred && options.some((option) => option.value === preferred)) {
    return preferred
  }
  return options[0]?.value ?? ''
}
