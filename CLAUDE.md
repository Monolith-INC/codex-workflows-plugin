# Repository guidance

The plugin is provider-neutral. Keep workflow logic independent of tracker and SCM vendors; put provider-specific payloads, mappings, and transport in `scripts/integrations/`. Keep the orchestrator instruction-only. Durable work state and artifacts belong to the configured tracker.

Run `python3 scripts/quality.py check` before handing off changes. Use `python3 scripts/quality.py fix` to apply safe Python and Markdown fixes. Preserve unrelated files and use the repository's configured branch convention.
