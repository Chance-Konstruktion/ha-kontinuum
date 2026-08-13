# Archived prototypes

These modules are **archived reference code**, not part of the running
integration. They are intentionally kept out of `custom_components/` so
Home Assistant never loads them.

## Why they are here

They were the only surviving copies of three prototype ideas that lived in
old, now-obsolete feature branches (`claude/add-widget-prose-QKShq`,
`claude/review-codex-improvements-fDna0`, the `codex/…autonomous-action-loop…`
series). Those branches predate the extraction of the neuro-modules into the
[`kontinuum-core`](https://github.com/Chance-Konstruktion/kontinuum-core)
package, so they can no longer be merged. Harvesting these files first means
the branches can be deleted without losing the ideas.

## Status: prototype / not wired

All three target the **pre-core-extraction API** and would need adapting
before use:

- **`wearable_processor.py`** — turns smartwatch/phone metrics (steps, heart
  rate, sleep phase) into KONTINUUM context tokens. Calls
  `thalamus._bucket_value(...)`, a method from the old in-integration
  Thalamus; the equivalent now lives in `kontinuum_core.thalamus`.
- **`network_monitor.py`** — turns network/infra metrics (router client
  count, server CPU) into tokens. Self-contained; only the token shape
  (`room.semantic.state`) needs to match the current core contract.
- **`feedback_monitor.py`** — polls an entity's state to score an autonomous
  action's outcome (First Autonomous Action Loop). ⚠️ Uses a blocking
  `time.sleep` loop — must be rewritten async (or run in an executor) before
  any real use in HA. The current integration already scores outcomes via a
  non-blocking `async_create_task` + override/implicit-accept path in
  `__init__.py`, so this is mostly of historical interest.

Treat them as design notes, not drop-in modules.
