export function codedError(
  code: string,
  message: string,
  details: Record<string, unknown> | null = null,
): Error & { code: string; details: Record<string, unknown> | null } {
  return Object.assign(new Error(message), { code, details })
}
