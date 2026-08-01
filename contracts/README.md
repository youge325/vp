# VP Workbench contracts

These JSON Schema 2020-12 documents are the language-neutral boundary for
Vue, Tauri/Rust, and Python. Runtime code may use richer domain types, but IPC,
NDJSON, configuration, and persistence adapters must serialize exactly these
shapes. `application-defaults.schema.json` and `application-defaults.json`
separately own cross-layer product defaults; they are not part of IPC or any
persistence version.

`ipc-manifest.json` is the only command/event name registry. Run
`python scripts/generate_contracts.py --check` before committing; generated
language bindings must never be edited by hand.

The defaults contract generates read-only Python, TypeScript, and Rust
constants. PowerShell runtime and release tooling reads the same validated JSON
through `scripts/runtime-tools.ps1`, so model filenames and product defaults are
not copied into packaging scripts.

Manifest version 3 also owns the backend `process`/one-shot command policies,
protocol size limits, deadlines, terminal prefix, and stage-worker event
prefix. `runtime-config.schema.json` is shared by Rust and Python;
`stage-worker.schema.json` intentionally generates Python bindings only because
that protocol never crosses the Tauri or Vue boundary.

Canonical schemas compose shared configuration and payload shapes through
external `$ref` links. Required and nullable wire fields are declared only in
those source schemas; the generated `boundary.schema.json` aggregate does not
rewrite their semantics. Every object schema must explicitly declare
`additionalProperties`.

The duplicate-code gate scans this directory and excludes only the generated
aggregate. Shared source shapes must be factored into canonical schemas or
`$defs`, never added to the ignore list.
