// Form-binding lens helpers — collapse the ``computed({get, set})`` boilerplate
// that piles up when a view edits many fields of the same draft config.
//
// ``fieldLens`` is the workhorse for "read this property of the root, patch
// the root by setting this property" — the common case for our preset draft
// editors. Use the more general ``defineLens`` when the read/write closures
// don't follow that single-field shape (e.g. side-effects, derived values).

import { computed, type WritableComputedRef } from 'vue'

/**
 * Build a writable computed from arbitrary read/write closures. Provided for
 * the cases that don't fit ``fieldLens`` (e.g. setters that need to mutate
 * multiple fields or sync derived state).
 */
export function defineLens<V>(
  read: () => V,
  write: (value: V) => void,
): WritableComputedRef<V> {
  return computed<V>({ get: read, set: write })
}

/**
 * Build a writable computed for a single field of a draft object. ``getRoot``
 * returns the latest immutable snapshot; ``patcher`` runs a mutator over a
 * clone and replaces the draft (the standard pattern used by our preset
 * store ``patchDecode`` / ``patchWorkflow`` / etc).
 */
export function fieldLens<TRoot extends object, V>(
  getRoot: () => TRoot,
  patcher: (mutator: (root: TRoot) => void) => void,
  selector: (root: TRoot) => V,
  setter: (root: TRoot, value: V) => void,
): WritableComputedRef<V> {
  return computed<V>({
    get: () => selector(getRoot()),
    set: (value: V) => patcher((root) => setter(root, value)),
  })
}
