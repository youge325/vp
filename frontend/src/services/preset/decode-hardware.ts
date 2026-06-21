type DecoderHardwareProfile = {
  hardwareDevices?: readonly string[]
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
