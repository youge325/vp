// Application-facing facade. The framework-neutral implementation lives below
// both services and IPC so neither boundary depends on the other.
export { normalizeError } from '@/lib/errors/normalize'
