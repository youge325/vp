# VP Workbench contracts

These JSON Schema 2020-12 documents are the language-neutral boundary for
Vue, Tauri/Rust, and Python. Runtime code may use richer domain types, but IPC,
NDJSON, configuration, and persistence adapters must serialize exactly these
shapes.

`ipc-manifest.json` is the only command/event name registry. Run
`python scripts/generate_contracts.py --check` before committing; generated
language bindings must never be edited by hand.

Canonical schemas compose shared configuration and payload shapes through
external `$ref` links. Required and nullable wire fields are declared only in
those source schemas; the generated `boundary.schema.json` aggregate does not
rewrite their semantics. Every object schema must explicitly declare
`additionalProperties`.

The duplicate-code gate scans this directory and excludes only the generated
aggregate. Shared source shapes must be factored into canonical schemas or
`$defs`, never added to the ignore list.
