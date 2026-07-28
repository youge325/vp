# brace-expansion compatibility adapter

This package preserves the callable CommonJS API expected by older minimatch
releases while delegating all expansion logic to the patched
`brace-expansion@5.0.8` implementation. The ESM entry point exposes the native
v5 named exports.

Remove this adapter once every transitive minimatch consumer supports the v5
API directly.
