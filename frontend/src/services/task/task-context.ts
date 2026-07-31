import type { MediaItem, MediaRunState } from '@/types/domain/media'

export interface TaskContextLookup {
  getMediaItem: (id: string) => MediaItem | null
  getItemRunState: (id: string) => MediaRunState | null
}

export interface TaskContext {
  item: MediaItem | null
  runState: MediaRunState | null
}

export function resolveTaskContext(
  lookup: TaskContextLookup,
  id: string | null,
): TaskContext {
  const item = id ? lookup.getMediaItem(id) : null
  return {
    item,
    runState: item ? lookup.getItemRunState(item.id) : null,
  }
}

export function resolveConsoleTaskContext(
  lookup: TaskContextLookup,
  currentId: string | null,
  activeId: string | null,
): TaskContext {
  const current = resolveTaskContext(lookup, currentId)
  return current.item ? current : resolveTaskContext(lookup, activeId)
}
